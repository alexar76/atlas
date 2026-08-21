"""Watchbox check delivery — the loop that was missing.

`webhook_url` has been accepted, validated and stored since watchboxes existed, and
nothing ever POSTed to it: every watchbox was poll-only and the field was decoration.
This module is the other half — it evaluates each subscribed watchbox on an interval,
appends the result to the append-only monitor log, and delivers it.

DESIGN NOTES THAT MATTER

* The log is written BEFORE delivery is attempted. The evidence is that we checked, not
  that someone received it; if delivery fails forever the check still happened and the
  log still says so (and `checks_never_delivered` surfaces it rather than hiding it).
* Deliveries are HMAC-SHA256 signed with a per-watchbox secret, so the receiver can tell
  our POST from anyone who learned the URL. The secret is returned once, at creation.
* Retries are bounded with exponential backoff and every attempt is recorded. An
  unbounded retry loop against a customer endpoint is an outage amplifier, and silent
  retries make a delivery log useless for proving notice.
* Outbound requests are SSRF-guarded at creation (`https://` only, no loopback), and the
  loop re-validates before each POST because a stored row outlives the code that wrote it.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import hmac
import json
import logging
import os
from typing import Any

import httpx

from . import monitor_log, watchboxes as watchbox_mod
from .geo import utc_now

logger = logging.getLogger("atlas.delivery")

MAX_ATTEMPTS = 5
# 2s, 8s, 32s, 128s — bounded, and long enough that a receiver restart is survivable.
BACKOFF_BASE_S = 2.0


def sign_body(secret: str, body: bytes) -> str:
    """HMAC-SHA256 over the exact bytes we send, hex, prefixed by the scheme.

    Signing the serialized bytes rather than the dict means the receiver verifies what
    arrived, with no need to agree on a canonical JSON form.
    """
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


class DeliveryLoop:
    """Periodically evaluate subscribed watchboxes, log, and deliver."""

    def __init__(
        self,
        *,
        evaluate: Any,
        signer: Any,
        interval_s: float | None = None,
        store: monitor_log.MonitorLog | None = None,
        client_factory: Any = None,
    ) -> None:
        # `evaluate(watchbox_row) -> dict` is injected rather than imported so the loop is
        # testable without a live fleet, and so the check logic stays in one place.
        self._evaluate = evaluate
        self._signer = signer
        self._interval = float(
            interval_s
            if interval_s is not None
            else os.environ.get("ATLAS_WATCHBOX_INTERVAL_S", 300)
        )
        self._store = store
        self._client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=15))
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    @property
    def store(self) -> monitor_log.MonitorLog:
        if self._store is None:
            self._store = monitor_log.get_store()
        return self._store

    async def start(self) -> None:
        if os.environ.get("ATLAS_WATCHBOX_DELIVERY", "1") not in ("1", "true", "TRUE"):
            logger.info("watchbox delivery disabled (ATLAS_WATCHBOX_DELIVERY)")
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown path
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                # One bad watchbox must never kill the loop for every other one.
                logger.exception("watchbox delivery tick failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def tick(self) -> int:
        """One pass over every watchbox. Returns how many checks were logged."""
        logged = 0
        # Unsubscribed boxes are skipped here and nowhere else: the row survives so the
        # owner can still read the evidence they already paid for, but we stop adding to
        # it — continuing to check a cancelled subscription would bill work nobody asked
        # for and would make the log claim a watch that was called off.
        for row in watchbox_mod.STORE.list(include_inactive=False):
            try:
                logged += 1 if await self.check_and_deliver(row) else 0
            except Exception:  # noqa: BLE001
                logger.exception("watchbox %s failed", row.get("id"))
        return logged

    async def check_and_deliver(self, row: dict[str, Any]) -> bool:
        # `evaluate` may be sync (tests) or async (the real path goes through the same
        # bbox-densifying station fetch the paid check SKU uses).
        result = self._evaluate(row)
        if inspect.isawaitable(result):
            result = await result
        if not result or not result.get("ok", True):
            return False

        payload = {
            "event": "atlas.watchbox.check",
            "watchbox_id": row.get("id"),
            "label": row.get("label"),
            "evaluated_at": result.get("evaluated_at") or utc_now(),
            "bbox": result.get("bbox") or {},
            "layers": result.get("layers") or [],
            "match_count": int(result.get("match_count") or 0),
            "live_match_count": int(result.get("live_match_count") or 0),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        signature = self._signer.sign_canonical(canonical)

        # Evidence first: the log records that WE checked, independently of whether the
        # receiver was reachable.
        check_id = self.store.append_check(
            watchbox_id=str(row.get("id")),
            evaluated_at=str(payload["evaluated_at"]),
            match_count=int(payload["match_count"]),
            live_match_count=int(payload["live_match_count"]),
            layers=list(payload["layers"]),
            bbox=dict(payload["bbox"]),
            digest=digest,
            signature_b64=signature,
            public_key_b64=self._signer.public_key_b64,
        )

        url = (row.get("webhook_url") or "").strip()
        if not url:
            return True  # logged; nothing subscribed to receive it
        await self._deliver(check_id, url, row, payload, digest, signature)
        return True

    async def _deliver(
        self,
        check_id: int,
        url: str,
        row: dict[str, Any],
        payload: dict[str, Any],
        digest: str,
        signature: str,
    ) -> None:
        # Re-validate: the stored row outlives the code that wrote it, and a row could
        # have been written by an older, laxer validator.
        try:
            url = watchbox_mod._validate_webhook(url)
        except ValueError as exc:
            self.store.record_delivery(
                check_id=check_id, attempt=0, status_code=None,
                error=f"refusing to deliver: {exc}", delivered=False,
            )
            return

        body = json.dumps(
            {**payload, "digest": digest, "signature_b64": signature,
             "public_key_b64": self._signer.public_key_b64},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")

        secret = row.get("webhook_secret") or ""
        headers = {
            "content-type": "application/json",
            "user-agent": "ATLAS-watchbox/1 (+https://atlas.modelmarket.dev)",
            "x-atlas-check-id": str(check_id),
            "x-atlas-digest": digest,
        }
        if secret:
            headers["x-atlas-signature"] = sign_body(secret, body)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self._stopping.is_set():
                self.store.record_delivery(
                    check_id=check_id, attempt=attempt, status_code=None,
                    error="shutting down before delivery", delivered=False,
                )
                return
            try:
                async with self._client_factory() as client:
                    resp = await client.post(url, content=body, headers=headers)
                code = int(resp.status_code)
                ok = 200 <= code < 300
                self.store.record_delivery(
                    check_id=check_id, attempt=attempt, status_code=code,
                    error=None if ok else f"HTTP {code}", delivered=ok,
                )
                if ok:
                    return
                # 4xx other than 408/429 is the receiver saying "never send this again";
                # retrying is pointless and looks like an attack from their side.
                if 400 <= code < 500 and code not in (408, 429):
                    return
            except Exception as exc:  # noqa: BLE001
                self.store.record_delivery(
                    check_id=check_id, attempt=attempt, status_code=None,
                    error=f"{type(exc).__name__}: {exc}", delivered=False,
                )
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BACKOFF_BASE_S ** attempt)


LOOP: DeliveryLoop | None = None
