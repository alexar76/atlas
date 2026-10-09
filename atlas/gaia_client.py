"""Thin async client for GAIA AIMarket v2 invoke."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from . import __version__
from .config import Settings

log = logging.getLogger("atlas.gaia_client")


class GaiaClient:
    """Owns the shared httpx client used by fleet + reading paths."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._pace_lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def open(self) -> None:
        if self._client:
            return
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._loop = loop
            self._pace_lock = asyncio.Lock()
            self._next_request_at = 0.0
        limits = httpx.Limits(
            max_keepalive_connections=self.settings.gaia_concurrency,
            max_connections=self.settings.gaia_concurrency + 2,
        )
        self._client = httpx.AsyncClient(
            base_url=self.settings.gaia_url.rstrip("/"),
            timeout=self.settings.gaia_timeout_s,
            limits=limits,
            headers={"user-agent": f"atlas/{__version__} (ecosystem-map)"},
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _pace(self) -> None:
        """Serialize request starts under GAIA's public per-client budget."""
        rpm = max(1.0, float(self.settings.gaia_requests_per_minute))
        gap = 60.0 / rpm
        async with self._pace_lock:
            now = time.monotonic()
            wait_s = self._next_request_at - now
            if wait_s > 0:
                await asyncio.sleep(wait_s)
                now = time.monotonic()
            self._next_request_at = max(now, self._next_request_at) + gap

    def _retry_delay(self, attempt: int, response: httpx.Response | None = None) -> float:
        raw = str(response.headers.get("retry-after") or "").strip() if response else ""
        try:
            retry_after = float(raw)
        except (TypeError, ValueError):
            retry_after = 0.0
        exponential = float(self.settings.gaia_retry_base_s) * (2 ** attempt)
        return max(
            0.0,
            min(float(self.settings.gaia_retry_max_s), max(retry_after, exponential)),
        )

    @property
    def raw(self) -> httpx.AsyncClient | None:
        """Expose underlying client for test stubs that set ``_client``."""
        return self._client

    @raw.setter
    def raw(self, client: httpx.AsyncClient | None) -> None:
        self._client = client

    async def invoke(
        self,
        capability_id: str,
        device_id: str | None = None,
        *,
        extra_input: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if self._client is None:
            raise RuntimeError("GaiaClient is not open")
        payload: dict[str, Any] = {
            "product_id": self.settings.gaia_product_id,
            "capability_id": capability_id,
            "source_hub": "atlas",
            "input": {},
        }
        if device_id:
            payload["input"]["device_id"] = device_id
        if extra_input:
            for key, value in extra_input.items():
                if value is not None:
                    payload["input"][key] = value
        retries = max(0, int(self.settings.gaia_max_retries))
        for attempt in range(retries + 1):
            try:
                await self._pace()
                r = await self._client.post("/ai-market/v2/invoke", json=payload)
                if (r.status_code == 429 or r.status_code >= 500) and attempt < retries:
                    await asyncio.sleep(self._retry_delay(attempt, r))
                    continue
                if r.status_code != 200:
                    return None
                body = r.json()
                if not isinstance(body, dict) or not body.get("ok", True):
                    return None
                out = body.get("output")
                return out if isinstance(out, dict) else None
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                log.debug("invoke %s/%s failed: %s", capability_id, device_id, exc)
                return None
            except Exception as exc:
                log.debug("invoke %s/%s failed: %s", capability_id, device_id, exc)
                return None
        return None
