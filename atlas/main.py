"""ATLAS FastAPI entry — cached GAIA map API + static map UI."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import mimetypes
import re
import sqlite3
from collections.abc import Awaitable, Callable
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, ORJSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints

from . import __version__
from .aggregator import aggregator
from .ai_assistant import ask as ai_ask
from .ai_assistant import list_providers as ai_list_providers
from .config import get_settings
from .geo import utc_now
from . import market as market_mod
from . import products as products_mod
from . import watchboxes as watchbox_mod

log = logging.getLogger("atlas")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

def _static_roots() -> list[Path]:
    """Resolve SPA roots for Docker, monorepo, and installed wheel layouts."""
    here = Path(__file__).resolve().parent  # …/atlas (package dir)
    candidates: list[Path] = [
        here / "_static",  # packaged wheel (frontend/public → atlas/_static)
        here.parent / "frontend" / "dist",
        here.parent / "frontend" / "public",
        Path("/app/frontend/dist"),
        Path("/app/frontend/public"),
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.is_dir():
            out.append(p)
    return out


STATIC_ROOTS = _static_roots()


class RateLimiter:
    """Simple sliding-window limiter (per client IP). In-process only — fine for
    a single uvicorn worker behind nginx which also rate-limits at the edge."""

    def __init__(self, per_min: int) -> None:
        self.per_min = max(1, per_min)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            q = self._hits[key]
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= self.per_min:
                return False
            q.append(now)
            # Bound memory for abusive IPs that rotate rarely.
            if len(self._hits) > 10_000:
                stale = [k for k, v in self._hits.items() if not v or now - v[-1] > 120]
                for k in stale[:1000]:
                    self._hits.pop(k, None)
            return True


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Before anything serves: a metered production node whose ledger does not survive
    # a redeploy is a node that charges nobody, and it says so in a log line instead of
    # failing. See payment_gate.durability_issue.
    from . import credits as credits_mod
    from . import payment_gate as payment_gate_mod

    payment_gate_mod.assert_durable_ledger()
    # Prepaid balances are somebody else's money, so the same durability rule applies with
    # a harsher consequence: a ledger inside an image layer loses the balances themselves,
    # not just an allowance. Then hand back reservations belonging to requests that died
    # with the previous process — that money is frozen until somebody releases it.
    credits_mod.assert_durable_ledger()
    if credits_mod.enabled():
        try:
            credits_mod.expire_stale_holds()
        except Exception:  # noqa: BLE001
            log.exception("credits: releasing holds left by the previous process failed")
    await aggregator.start()
    # Watchbox delivery: evaluates each subscribed box on an interval, appends the result
    # to the append-only monitor log, then POSTs it. Until this existed, `webhook_url` was
    # stored and never used and every watchbox was poll-only.
    from . import delivery as delivery_mod
    from .signing import get_signer

    async def _evaluate_for_delivery(row: dict[str, Any]) -> dict[str, Any]:
        # Deliberately the SAME path as POST /watchboxes/{id}/check, so the logged
        # evidence is byte-for-byte the product the buyer pays for — a monitoring log
        # that records something subtly different from the paid SKU proves nothing
        # about the paid SKU.
        stations = await _product_stations(row)
        return products_mod.watchbox_check({"watchbox_id": row.get("id")}, stations)

    delivery_mod.LOOP = delivery_mod.DeliveryLoop(
        evaluate=_evaluate_for_delivery,
        signer=get_signer(),
    )
    await delivery_mod.LOOP.start()
    # Instrument status archive. atlas.observability.attest@v1 can only attest what was
    # recorded, so the writer has to run whether or not anyone is asking — and it asks
    # the aggregator for exactly the rows a paid product would be served.
    from . import status_sampler as sampler_mod

    sampler_mod.LOOP = sampler_mod.StatusSampler(
        fetch=aggregator.ensure_layer_readings,
    )
    await sampler_mod.LOOP.start()
    yield
    if sampler_mod.LOOP is not None:
        await sampler_mod.LOOP.stop()
    if delivery_mod.LOOP is not None:
        await delivery_mod.LOOP.stop()
    await aggregator.stop()


settings = get_settings()
limiter = RateLimiter(settings.rate_limit_per_min)
# Paid paths get their own budgets: LLM calls cost money, force/fresh bypass
# the reading cache and multiply into GAIA invokes.
ai_limiter = RateLimiter(settings.rate_limit_ai_per_min)
force_limiter = RateLimiter(settings.rate_limit_force_per_min)

app = FastAPI(
    title="ATLAS",
    version=__version__,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS", "POST", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=512)


def _peer_is_local_proxy(host: str) -> bool:
    """True when the direct peer can be our own reverse proxy."""
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host == "localhost"
    return ip.is_loopback or ip.is_private or ip.is_link_local


def _client_ip(request: Request) -> str:
    """Budget key: the caller, never a value the caller can choose.

    Proxy headers are honoured ONLY when the direct peer is a local/private
    address (our nginx). ATLAS binds loopback behind nginx, which overwrites
    ``X-Real-IP`` and appends to ``X-Forwarded-For``, so the rightmost hop is
    ours. Exposed directly, the headers are ignored — otherwise anyone could
    rotate a fake IP per request and walk through the AI / cache-bypass budgets.
    """
    peer = request.client.host if request.client else ""
    if int(settings.trusted_proxy_hops) > 0 and _peer_is_local_proxy(peer):
        real = (request.headers.get("x-real-ip") or "").strip()
        if real:
            return real
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in forwarded.split(",") if h.strip()]
            if hops:
                trusted = int(settings.trusted_proxy_hops)
                return hops[-trusted] if len(hops) >= trusted else hops[-1]
    return peer or "unknown"


def _operator_ok(request: Request) -> bool:
    """True when ATLAS_OPERATOR_TOKEN is configured and matches the header."""
    token = (settings.operator_token or "").strip()
    if not token:
        return False
    supplied = (request.headers.get("x-atlas-token") or "").strip()
    if not supplied:
        return False
    # Compare bytes: compare_digest() raises TypeError on non-ASCII str, which
    # would turn a junk header into an unhandled 500.
    return secrets.compare_digest(supplied.encode("utf-8"), token.encode("utf-8"))


OPERATOR_REQUIRED_DETAIL = (
    "watchbox registry requires an operator token (X-Atlas-Token); "
    "set ATLAS_OPERATOR_TOKEN on the server"
)


class OperatorRequired(Exception):
    """Uncredentialed watchbox-registry access. Not an HTTPException on purpose.

    FastAPI/Starlette map HTTPException through a generic handler. A stray
    catch-all that re-raises HTTPException(400, detail=str(exc)) would keep
    this exact message and rewrite 401 → 400 — the gate still works, the
    status lies. A dedicated exception + handler cannot be remapped that way.

    Every "you need a credential" refusal on the registry goes through here,
    whether the missing credential is the operator token or a watchbox owner
    token, so there is exactly one 401 path to reason about.
    """

    def __init__(self, detail: str = OPERATOR_REQUIRED_DETAIL) -> None:
        super().__init__(detail)
        self.detail = detail


@app.exception_handler(OperatorRequired)
async def _operator_required_handler(_request: Request, exc: OperatorRequired) -> ORJSONResponse:
    return ORJSONResponse(
        {"detail": exc.detail},
        status_code=401,
        headers={"WWW-Authenticate": 'X-Atlas-Token realm="atlas"'},
    )


def _require_operator_control(request: Request, action: str) -> None:
    """Operator-only control path — a per-IP budget is not enough for these.

    ``force``/``fresh`` cost one bbox, so a tight budget is a fair trade for
    keeping them open. A full fleet refresh re-reads the WHOLE catalog through
    GAIA's 72/min pacer, so one anonymous caller could push every interactive
    viewport behind minutes of queued upstream work. Fails closed: with no
    ATLAS_OPERATOR_TOKEN configured nobody may call it.
    """
    if _operator_ok(request):
        return
    raise HTTPException(
        status_code=401,
        detail=(
            f"{action} requires an operator token (X-Atlas-Token); "
            "set ATLAS_OPERATOR_TOKEN on the server"
        ),
    )


async def _guard_cache_bypass(request: Request) -> None:
    """Cache-bypass (force / fresh / refresh) is the expensive path into GAIA."""
    if _operator_ok(request):
        return
    if not await force_limiter.allow(_client_ip(request)):
        raise HTTPException(
            status_code=429,
            detail=(
                "cache-bypass budget exhausted — retry without force/fresh "
                "or use an operator token"
            ),
        )


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    # Health + static assets stay cheap; API/SSE/Hub-invoke are limited.
    if (
        path.startswith("/api/")
        or path.startswith("/embed")
        or path.startswith("/ai-market/")
        or path.startswith("/.well-known/ai-market")
    ):
        ip = _client_ip(request)
        if not await limiter.allow(ip):
            return ORJSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)
        if path.startswith("/api/ai/") and request.method == "POST":
            if not await ai_limiter.allow(ip):
                return ORJSONResponse(
                    {"ok": False, "error": "rate_limited", "scope": "ai"},
                    status_code=429,
                )
    response = await call_next(request)
    response.headers["X-ATLAS-Version"] = __version__
    # Allow Alien Monitor (and same-origin) to iframe /embed.
    response.headers["Content-Security-Policy"] = (
        "frame-ancestors 'self' https://magic-ai-factory.com https://*.modelmarket.dev"
    )
    if path.startswith("/api/") and response.status_code < 400:
        response.headers["Cache-Control"] = "public, max-age=5, stale-while-revalidate=30"
    return response


@app.get("/api/v1/receipts/{digest}")
async def receipt_get(digest: str) -> dict[str, Any]:
    """Public fetch of a recently issued ATLAS content receipt (spec §7.3)."""
    row = products_mod.lookup_receipt(digest)
    if not row:
        raise HTTPException(status_code=404, detail="unknown receipt")
    return {"ok": True, "receipt": row}


@app.get("/health")
async def health() -> dict[str, Any]:
    return aggregator.health()


@app.get("/api/v1/snapshot")
async def snapshot() -> dict[str, Any]:
    return aggregator.snapshot()


@app.get("/api/v1/monitor")
async def monitor() -> dict[str, Any]:
    """Slim payload for Alien Monitor node detail."""
    return aggregator.monitor_payload()


@app.get("/api/v1/layers")
async def layers() -> dict[str, Any]:
    snap = aggregator.snapshot()
    return {"layers": snap.get("layers") or {}, "summary": snap.get("summary") or {}}


class ViewportBody(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    force: bool = False


@app.post("/api/v1/viewport")
async def viewport(body: ViewportBody, request: Request) -> dict[str, Any]:
    """Refresh readings for sensors inside the visible map bbox (TTL-cached)."""
    if body.force:
        await _guard_cache_bypass(request)
    return await aggregator.refresh_viewport(
        west=body.west,
        south=body.south,
        east=body.east,
        north=body.north,
        force=body.force,
    )


@app.get("/api/v1/stations/{device_id}")
async def station_detail(
    device_id: str,
    request: Request,
    fresh: bool = Query(False, description="Bypass cache and re-read from GAIA"),
    brief: bool = Query(
        False,
        description="Drop the raw hotspots[] cluster; keep the counts. "
                    "The detail card needs a headline and metrics, not 4269 "
                    "Argo floats — those already ship expanded in /viewport.",
    ),
) -> dict[str, Any]:
    """Human-readable station card — used on pin / list click."""
    if fresh:
        await _guard_cache_bypass(request)
    try:
        detail = await aggregator.station_detail(device_id, fresh=fresh)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown station: {device_id}") from None
    if brief and isinstance(detail, dict) and "hotspots" in detail:
        detail = dict(detail)
        # hotspot_count / hotspot_matched stay — the card shows the number.
        detail["hotspots"] = []
        detail["hotspots_omitted"] = True
    return detail


class AskBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    locale: str = "en"
    provider: Optional[str] = None
    model_role: str = Field("heavy", pattern="^(heavy|light)$")
    station_ids: Optional[List[str]] = None
    bbox: Optional[Dict[str, float]] = None
    report: bool = False


@app.get("/api/ai/providers")
async def ai_providers() -> dict[str, Any]:
    return ai_list_providers()


@app.post("/api/ai/ask")
async def ai_ask_route(body: AskBody) -> dict[str, Any]:
    """Grounded analyst chat — live ATLAS snapshot injected server-side."""
    try:
        return await ai_ask(
            question=body.question,
            locale=body.locale,
            provider=body.provider,
            model_role=body.model_role,
            station_ids=body.station_ids,
            bbox=body.bbox,
            report=body.report,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM upstream error: {exc.response.status_code}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("ai ask failed")
        raise HTTPException(status_code=500, detail=str(exc)) from None


@app.post("/api/v1/refresh")
async def refresh(request: Request) -> dict[str, Any]:
    """Operator nudge — fleet + forced re-read of every cached station."""
    _require_operator_control(request, "a full fleet refresh")
    return await aggregator.refresh()


class WatchboxCreateBody(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    layers: List[str] = Field(..., min_length=1)
    label: str = Field("", max_length=120)
    webhook_url: Optional[str] = None
    id: Optional[str] = Field(None, max_length=64)


# Ownership credential for exactly one watchbox. Distinct from X-Atlas-Token, which is
# the operator's master key over the whole registry.
WATCHBOX_TOKEN_HEADER = "X-Atlas-Watchbox-Token"


def _supplied_owner_token(request: Request) -> str:
    """The caller's per-watchbox token, from its own header or a bearer credential."""
    token = (request.headers.get(WATCHBOX_TOKEN_HEADER.lower()) or "").strip()
    if token:
        return token
    auth = (request.headers.get("authorization") or "").strip()
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    return ""


def _require_operator(request: Request) -> None:
    """Operator-only gate: the whole registry, across every tenant."""
    if not _operator_ok(request):
        raise OperatorRequired()


def _authorize_watchbox(
    request: Request, watchbox_id: str, *, token: str = ""
) -> dict[str, Any]:
    """Resolve one watchbox for a caller who is entitled to it, or refuse.

    THE HOLE THIS CLOSES. Every registry route was once anonymous: `GET /watchboxes`
    published every watchbox id and bbox (who is watching what), and an anonymous
    `DELETE /watchboxes/{id}` succeeded. Because the log endpoint resolves the registry
    first, a stranger — including the opposing party, who could read the id straight off
    the public list — could stop the monitoring AND make the evidence log answer 404
    while the signed check rows still sat in SQLite. Verified against production.

    The first fix made the registry operator-only, which is safe but has no tenancy: the
    only credential that could read a buyer's log was the master key that reads
    everyone's. So each watchbox now carries its own token, minted at creation and
    handed to the buyer, which authorises that box and nothing else.

    A caller with no credential at all gets 401 (it says how to authenticate, and
    reveals nothing about which ids exist). A caller holding a token that does not match
    gets the same 404 as a caller asking for an id that was never issued — a wrong token
    must not become an existence oracle for other tenants' watchboxes.
    """
    operator = _operator_ok(request)
    supplied = (token or "").strip() or _supplied_owner_token(request)
    if not operator and not supplied:
        raise OperatorRequired(
            f"watchbox access requires its owner token ({WATCHBOX_TOKEN_HEADER}, "
            "issued once when the watchbox is created) or an operator token "
            "(X-Atlas-Token)"
        )
    row = watchbox_mod.STORE.get(watchbox_id)
    if row is None or not (operator or watchbox_mod.owns(row, supplied)):
        raise HTTPException(status_code=404, detail="unknown watchbox")
    return row


@app.get("/api/v1/watchboxes")
async def watchboxes_list(request: Request) -> dict[str, Any]:
    """Scoped to the caller: an owner token lists that owner's boxes, nothing else.

    The unscoped version of this route was the reconnaissance step of the whole attack —
    it handed a stranger the ids and bboxes that the delete and log routes key on.
    """
    operator = _operator_ok(request)
    supplied = _supplied_owner_token(request)
    if not operator and not supplied:
        raise OperatorRequired(
            f"listing watchboxes requires an owner token ({WATCHBOX_TOKEN_HEADER}) "
            "or an operator token (X-Atlas-Token)"
        )
    rows = watchbox_mod.STORE.list()
    if not operator:
        # A token that owns nothing gets an empty list, not a 403: the response must not
        # differ between "you own none" and "these ids exist but are not yours".
        rows = [r for r in rows if watchbox_mod.owns(r, supplied)]
    return {
        "sku": "atlas.watchbox.subscribe@v1",
        "scope": "operator" if operator else "owner",
        "allowed_layers": sorted(watchbox_mod.ALLOWED_WATCHBOX_LAYERS),
        # public_row strips webhook_secret AND the owner-token digest — both are shown
        # exactly once, in the create response.
        "watchboxes": [watchbox_mod.public_row(r) for r in rows],
    }


@app.post("/api/v1/watchboxes")
async def watchboxes_create(body: WatchboxCreateBody, request: Request) -> dict[str, Any]:
    if not _operator_ok(request):
        if not settings.watchbox_open_signup:
            raise OperatorRequired(
                "creating a watchbox requires an operator token (X-Atlas-Token); "
                "set ATLAS_WATCHBOX_OPEN_SIGNUP=1 to allow self-serve creation"
            )
        # Self-serve is bounded: each box costs a fleet evaluation every interval and an
        # outbound POST, so an unbounded registry is a resource and amplification hole
        # even when every row is properly owned.
        live = sum(1 for r in watchbox_mod.STORE.list() if watchbox_mod.is_active(r))
        if live >= int(settings.watchbox_self_serve_max):
            raise HTTPException(
                status_code=429,
                detail="self-serve watchbox registry is full — contact the operator",
            )
    try:
        row = watchbox_mod.STORE.create(
            west=body.west,
            south=body.south,
            east=body.east,
            north=body.north,
            layers=body.layers,
            label=body.label,
            webhook_url=body.webhook_url,
            watchbox_id=body.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    out: dict[str, Any] = {"ok": True, "watchbox": watchbox_mod.public_row(row)}
    # The ONLY time the owner token is returned. It is the credential for this box's
    # evidence log; the store keeps only its digest, so a lost token cannot be recovered
    # from the registry and the box has to be re-created.
    out["owner_token"] = row["owner_token"]
    out["owner_token_header"] = WATCHBOX_TOKEN_HEADER
    out["owner_token_note"] = (
        "shown once — required to read, check or unsubscribe this watchbox and to read "
        "its monitoring log; store it now"
    )
    # The ONLY time the HMAC secret is returned. The receiver needs it to verify our
    # X-Atlas-Signature; list/get never echo it, so it cannot be recovered from the
    # registry later.
    if row.get("webhook_secret"):
        out["webhook_secret"] = row["webhook_secret"]
        out["webhook_signature_scheme"] = (
            "X-Atlas-Signature: sha256=HMAC_SHA256(webhook_secret, raw_request_body)"
        )
    return out


@app.get("/api/v1/watchboxes/{watchbox_id}")
async def watchboxes_get(watchbox_id: str, request: Request) -> dict[str, Any]:
    row = _authorize_watchbox(request, watchbox_id)
    return {"watchbox": watchbox_mod.public_row(row)}


@app.get("/api/v1/watchboxes/{watchbox_id}/log")
async def watchboxes_log(
    request: Request, watchbox_id: str, limit: int = 200, since: str = "",
) -> dict[str, Any]:
    """The monitoring-evidence artifact: what THIS instance checked, and when.

    This is the half of a watchbox that is worth paying for. A signature over a NASA
    FIRMS reading proves nothing the opposing party cannot fetch themselves; a signed,
    append-only record that we evaluated this bbox at 09:56:10Z — at a cadence the buyer
    did not choose after the fact — is what answers "prove you were monitoring".

    Readable by the owner (and the operator) for as long as the registry row exists —
    including after an unsubscribe, which is exactly when a buyer is most likely to need
    it.
    """
    row = _authorize_watchbox(request, watchbox_id)
    from . import monitor_log as mlog

    store = mlog.get_store()
    import os as _os
    interval = float(_os.environ.get("ATLAS_WATCHBOX_INTERVAL_S", 300) or 300)
    return {
        "sku": "atlas.watchbox.log@v1",
        "active": watchbox_mod.is_active(row),
        "unsubscribed_at": row.get("unsubscribed_at"),
        "summary": store.summary(watchbox_id),
        # Continuity is computed, not implied: count+first+last cannot express a gap, so
        # a log with an outage in the middle looked identical to a continuous one.
        "continuity": store.gaps(watchbox_id, expected_interval_s=interval),
        "checks": store.checks(watchbox_id, limit=limit, since=since or None),
    }


@app.delete("/api/v1/watchboxes/{watchbox_id}")
async def watchboxes_delete(
    watchbox_id: str,
    request: Request,
    purge: bool = Query(False, description="Operator-only: also destroy the registry row"),
) -> dict[str, Any]:
    """Unsubscribe by default; purge only on an explicit operator request.

    DELETE used to drop the registry row, which orphaned the monitor log — the signed
    checks survived in SQLite but nothing could reach them, because the log route
    resolves the registry first. Making evidence unreachable is a worse outcome than
    refusing to delete, so the default is a soft unsubscribe: the loop stops checking,
    the owner keeps reading. `?purge=true` is the deliberate, operator-only way to
    destroy the row, and it says in the response what it cost.
    """
    row = _authorize_watchbox(request, watchbox_id)
    if purge:
        _require_operator(request)
        watchbox_mod.STORE.purge(watchbox_id)
        return {
            "ok": True,
            "id": watchbox_id,
            "purged": True,
            "warning": (
                "registry row destroyed; the signed checks remain in the append-only "
                "monitor log but are no longer reachable over HTTP"
            ),
        }
    updated = watchbox_mod.STORE.unsubscribe(watchbox_id) or row
    return {
        "ok": True,
        "id": watchbox_id,
        "purged": False,
        "active": watchbox_mod.is_active(updated),
        "unsubscribed_at": updated.get("unsubscribed_at"),
        "log_url": f"/api/v1/watchboxes/{watchbox_id}/log",
        "note": "monitoring stopped; the evidence log stays readable with your owner token",
    }


@app.post("/api/v1/watchboxes/{watchbox_id}/check")
async def watchboxes_check(
    watchbox_id: str, request: Request, response: Response
) -> dict[str, Any]:
    """Paid-style evaluation — ``atlas.watchbox.check@v1``.

    Owner-gated like the rest: a stored watchbox's bbox and layers are the tenant's, and
    this route echoes both. Ephemeral bbox checks (no stored id) stay open on
    ``/ai-market/v2/invoke``.
    """
    wb = _authorize_watchbox(request, watchbox_id)

    async def produce() -> dict[str, Any]:
        stations = await _product_stations(wb if isinstance(wb, dict) else None)
        result = products_mod.watchbox_check({"watchbox_id": watchbox_id}, stations)
        if not result.get("ok"):
            raise HTTPException(
                status_code=404, detail=result.get("refuse_reason") or "check failed"
            )
        return result

    # Metered like every other priced route. This one was invisible to the bypass guard by
    # construction: `test_every_product_route_is_covered_by_this_test` builds its inventory
    # from routes under `/api/v1/products/`, and this SKU lives under `/api/v1/watchboxes/`,
    # so the guard written to stop exactly this could never see it. Owner-gated is not the
    # same as metered - the owner token is issued to every buyer, so this was the paid
    # "agent poll" SKU pollable without limit and without a ledger row, while the identical
    # call on /ai-market/v2/invoke cost an allowance and 402'd when spent.
    return await _metered_product("atlas.watchbox.check@v1", request, produce, response=response)


class ProductInvokeBody(BaseModel):
    # strip_whitespace is load-bearing, not tidiness. `payment_gate.price_of` looks the id up
    # in CAP_BY_ID verbatim and `reserve` returns None for anything priced <= 0, while
    # `products.invoke_product` strips before dispatching. So "atlas.route.integrity@v1 "
    # priced at $0.00 and still served the full priced product, and the same inequality
    # stepped over the `== "atlas.watchbox.check@v1"` branch below - the only place the
    # per-watchbox owner token is enforced on this surface. Normalise ONCE, here, so the two
    # halves of the request path can never disagree about what the caller named again.
    capability_id: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(
        ..., min_length=3, max_length=128
    )
    input: Dict[str, Any] = Field(default_factory=dict)


class BboxProductBody(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    layers: Optional[List[str]] = None
    # Named desk for atlas.situation.brief@v1. Bounded here so a typo is a 422 on the
    # REST twin and an unbilled refusal on the invoke path, never the default 21 layers.
    preset: Optional[str] = Field(None, min_length=1, max_length=32)
    limit: Optional[int] = Field(None, ge=1, le=80)
    include_air: bool = False
    max_citations: Optional[int] = Field(None, ge=4, le=48)
    locale: str = "en"


class NearestProductBody(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    layer: Optional[str] = None
    layers: Optional[List[str]] = None
    max_km: Optional[float] = Field(None, ge=1, le=20037)
    per_layer: bool = False


class ObservabilityAttestBody(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    start: Optional[str] = Field(None, max_length=40)
    end: Optional[str] = Field(None, max_length=40)
    max_km: Optional[float] = Field(None, ge=1, le=460)
    event_id: Optional[str] = Field(None, max_length=160)


class RouteIntegrityBody(BaseModel):
    route: List[List[float]] = Field(..., min_length=2, max_length=500)
    corridor_km: Optional[float] = Field(None, ge=1, le=200)
    route_id: Optional[str] = Field(None, max_length=160)


class PvIrradianceBody(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    max_km: Optional[float] = Field(None, ge=1, le=2000)
    plant_id: Optional[str] = Field(None, max_length=160)


class GeomagWindowBody(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    max_km: Optional[float] = Field(None, ge=1, le=20037)
    asset_id: Optional[str] = Field(None, max_length=160)


class PointProductBody(BaseModel):
    point_id: str = Field(..., min_length=1, max_length=160)
    fresh: bool = False


class GnssDegradationBody(BaseModel):
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    west: Optional[float] = Field(None, ge=-180, le=180)
    south: Optional[float] = Field(None, ge=-90, le=90)
    east: Optional[float] = Field(None, ge=-180, le=180)
    north: Optional[float] = Field(None, ge=-90, le=90)
    route: Optional[List[List[float]]] = None
    corridor_km: float = Field(100.0, ge=1, le=1000)
    max_km: float = Field(750.0, ge=1, le=5000)
    limit: int = Field(200, ge=1, le=500)


class SmokeOperationsBody(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    asset_id: Optional[str] = Field(None, max_length=160)


class FieldMeshBody(BaseModel):
    mesh_id: str = Field(..., min_length=2, max_length=32)
    quantity: Optional[str] = Field(None, min_length=1, max_length=40)
    count: Optional[int] = Field(None, ge=1, le=64)
    skip: Optional[int] = Field(None, ge=0)
    trim: Optional[float] = Field(None, ge=0.0, le=0.499)
    min_live: Optional[int] = Field(None, ge=1, le=32)
    device_ids: Optional[List[str]] = Field(None, max_length=64)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    length_km: Optional[float] = Field(None, ge=5, le=2000)
    max_km: Optional[float] = Field(None, ge=10, le=2000)
    west: Optional[float] = Field(None, ge=-180, le=180)
    south: Optional[float] = Field(None, ge=-90, le=90)
    east: Optional[float] = Field(None, ge=-180, le=180)
    north: Optional[float] = Field(None, ge=-90, le=90)


async def _product_stations(inp: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Pins for composite SKUs.

    Bbox inputs get a targeted FIRMS densify (paid fire products must see the
    per-detection cluster for THEIR bbox, not whatever camera a map user last
    panned to). The densify is deadline-bounded: when GAIA is slow or down the
    SKU answers from the store-wide expansion instead of hanging the invoke.
    """
    inp = inp or {}
    keys = ("west", "south", "east", "north")
    if all(inp.get(k) is not None for k in keys):
        deadline = float(getattr(settings, "product_densify_timeout_s", 10.0) or 10.0)
        try:
            return await asyncio.wait_for(
                aggregator.product_stations_for_bbox(
                    float(inp["west"]), float(inp["south"]),
                    float(inp["east"]), float(inp["north"]),
                ),
                timeout=deadline,
            )
        except (TypeError, ValueError, asyncio.TimeoutError):
            pass
    return aggregator.product_stations()


async def _nearest_stations(inp: dict[str, Any]) -> list[dict[str, Any]]:
    """Pins for ``atlas.nearest.read@v1``, with the requested layers warmed first.

    It used to read whatever the store happened to hold. Layers that are only fetched on
    demand were then empty unless a map viewer or another SKU had just warmed them, and
    the answer was "no LIVE readings" for data GAIA did have. Deadline-bounded like the
    bbox densify: a slow GAIA answers from the store instead of hanging the invoke.
    """
    layers = set(products_mod._nearest_layers(inp or {}))
    if layers:
        deadline = float(getattr(settings, "product_densify_timeout_s", 10.0) or 10.0)
        try:
            await asyncio.wait_for(aggregator.ensure_layer_readings(layers), timeout=deadline)
        except asyncio.TimeoutError:
            log.info("nearest: warming %s ran past %.0fs; answering from the store", sorted(layers), deadline)
        except Exception as exc:  # noqa: BLE001 — a broken upstream must not break the SKU
            log.warning("nearest: warming %s failed (%s); answering from the store", sorted(layers), exc)
    stations = aggregator.product_stations()
    return stations if isinstance(stations, list) else []


async def _field_stations(inp: dict[str, Any]) -> list[dict[str, Any]]:
    """Warm the mesh's own layer. A named mesh uses the full fleet, not a bbox crop.

    Unknown / refused mesh_ids still warm the four in-situ families so the handler
    can refuse honestly from a live store rather than an empty snapshot.
    """
    from .field_meshes import get_mesh

    spec = get_mesh(str(inp.get("mesh_id") or ""))
    layers = {str(spec["layer"])} if spec else {"weather", "river", "air", "marine"}
    stations = await aggregator.ensure_layer_readings(layers)
    return stations if isinstance(stations, list) else []


async def _smoke_product(inp: dict[str, Any]) -> dict[str, Any]:
    """``atlas.smoke.operations@v1`` — asset coordinate → exact HMS containment.

    Two different GAIA devices back one answer: the signed HMS polygon inventory
    (whose geometry only travels on this internal product path, never in the map
    viewport) and a PM2.5/AQI read at the buyer's own coordinate. They are warmed
    concurrently because the SKU promises a sub-second p50, and the product
    refuses rather than answering from the centroid when either side is missing.
    """
    try:
        lat, lon = float(inp.get("lat")), float(inp.get("lon"))
    except (TypeError, ValueError):
        lat = lon = None
    smoke_task = asyncio.ensure_future(aggregator.ensure_layer_readings({"smoke"}))
    air_task = (
        asyncio.ensure_future(aggregator.coordinate_air_reading(lat, lon))
        if lat is not None and -90 <= lat <= 90 and -180 <= lon <= 180
        else None
    )
    tasks = [smoke_task] + ([air_task] if air_task is not None else [])
    await asyncio.gather(*tasks, return_exceptions=True)

    if smoke_task.cancelled() or smoke_task.exception() is not None:
        log.warning("smoke brief: HMS layer warm failed", exc_info=smoke_task.exception())
        stations: list[dict[str, Any]] = []
    else:
        result = smoke_task.result()
        stations = result if isinstance(result, list) else []
    air: dict[str, Any] | None = None
    if air_task is not None:
        if air_task.cancelled() or air_task.exception() is not None:
            log.warning("smoke brief: colocated air read failed", exc_info=air_task.exception())
        else:
            answer = air_task.result()
            air = answer if isinstance(answer, dict) else None
    return products_mod.invoke_product(
        "atlas.smoke.operations@v1", inp, stations, air_reading=air
    )


async def _point_product(inp: dict[str, Any], request: Request) -> dict[str, Any]:
    """Resolve an exact public map id through the same detail path as a click."""
    point_id = str(inp.get("point_id") or "").strip()
    if not point_id or len(point_id) > 160:
        return products_mod.point_read(inp, [])
    fresh = bool(inp.get("fresh", False))
    if fresh:
        await _guard_cache_bypass(request)
    try:
        detail = await aggregator.station_detail(
            point_id,
            fresh=fresh,
        )
    except KeyError:
        return products_mod.point_read(inp, [])
    return products_mod.point_read(inp, [detail])


@app.get("/.well-known/ai-market.json")
async def aimarket_well_known() -> dict[str, Any]:
    return market_mod.well_known()


@app.get("/ai-market/v2/manifest")
async def aimarket_manifest() -> dict[str, Any]:
    return market_mod.manifest()


class CreditAccountBody(BaseModel):
    label: str = Field("", max_length=120)
    # Bounded so a slipped decimal point is a 422 rather than a $100k opening balance the
    # operator has to reconcile out of the ledger by hand.
    grant_usd: float = Field(0.0, ge=0, le=10_000)


class CreditTopupBody(BaseModel):
    amount_usd: float = Field(..., gt=0, le=10_000)
    #: An invoice id or chain transaction. Present → crediting twice is impossible, which
    #: matters because the natural reaction to a timed-out top-up is to run it again.
    reference: str = Field("", max_length=200)
    note: str = Field("", max_length=200)


@app.post("/ai-market/v2/accounts")
async def credits_create_account(body: CreditAccountBody, request: Request) -> dict[str, Any]:
    """Mint a prepaid account. Operator-only, and open signup is deliberately absent.

    The hub lets a stranger mint their own zero-balance key because its whole job is to be
    discovered. ATLAS is one publisher inside that market: a buyer who wants self-serve goes
    to the hub, and an account here is something the operator hands to a counterparty it has
    agreed terms with. No signup means no grant budget to defend and no farmed keys.

    Works with the rail switched off on purpose, so accounts and keys can be in place BEFORE
    ``ATLAS_CREDITS_ENABLED=1``. Flipping it first would put every buyer holding a not-yet-
    issued key onto the anonymous free allowance at the moment they expected to be charged.
    """
    _require_operator_control(request, "issuing a credit account")
    from atlas import credits

    try:
        return credits.create_account(label=body.label, grant_usd=body.grant_usd)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"credit ledger unavailable: {exc}") from exc


@app.post("/ai-market/v2/accounts/{account_id}/topup")
async def credits_topup(account_id: str, body: CreditTopupBody, request: Request) -> dict[str, Any]:
    """Add credit to an account once the operator has the money."""
    _require_operator_control(request, "topping up a credit account")
    from atlas import credits

    try:
        result = credits.topup(
            account_id, body.amount_usd, reference=body.reference, note=body.note
        )
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"credit ledger unavailable: {exc}") from exc
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/ai-market/v2/accounts/{account_id}/status")
async def credits_set_status(account_id: str, request: Request, status: str = "disabled") -> dict[str, Any]:
    """Disable (or re-enable) an account — the answer to a leaked key.

    Disabling stops new reservations and leaves the balance intact, because the money is
    still the buyer's: a leaked key is a reason to stop spending it, not to confiscate it.
    """
    _require_operator_control(request, "changing a credit account's status")
    from atlas import credits

    try:
        result = credits.set_status(account_id, status.strip().lower())
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"credit ledger unavailable: {exc}") from exc
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/ai-market/v2/accounts/me")
async def credits_whoami(request: Request) -> dict[str, Any]:
    """What the holder of this key can see: their own balance and spend, nothing else.

    A buyer that cannot read its own balance can only discover it has run out by being
    refused mid-run, which for an unattended desk means a customer's run failing before its
    operator hears about the money.
    """
    from atlas import credits

    key = credits.key_from_headers(request.headers)
    if not key:
        raise HTTPException(
            status_code=401,
            detail=f"send your account key as {credits.KEY_HEADER}",
        )
    try:
        account_id = credits.resolve(key)
        row = credits.account(account_id) if account_id else None
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"credit ledger unavailable: {exc}") from exc
    if not row:
        # Same 404 for an unknown key and a disabled account: distinguishing them would
        # turn this route into an oracle for which keys exist.
        raise HTTPException(status_code=404, detail="no active credit account for this key")
    return {**row, "rail_enabled": credits.enabled(), "price_list": "/ai-market/v2/manifest"}


@app.get("/ai-market/v2/credits/stats")
async def credits_stats(request: Request) -> dict[str, Any]:
    """Rail totals, including what the operator is holding for other people."""
    _require_operator_control(request, "reading credit totals")
    from atlas import credits

    try:
        return {**credits.stats(), "recent": credits.recent(limit=20)}
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"credit ledger unavailable: {exc}") from exc


@app.post("/ai-market/v2/invoke")
async def aimarket_invoke(
    body: ProductInvokeBody, request: Request, response: Response
) -> dict[str, Any]:
    """Hub-compatible invoke for ATLAS composite products."""
    # A published price is a promise to charge. Free capabilities and a disabled
    # gate pass straight through; a spent allowance answers 402 with the price and
    # the two ways to continue.
    from atlas import payment_gate

    # `_client_ip`, not request.client.host. ATLAS binds loopback behind nginx, so the
    # direct peer is the proxy for every caller on earth: the address fallback collapsed
    # into ONE bucket (`ip:172.23.0.1`, the docker gateway, observed holding the whole
    # allowance in production). Five header-less callers anywhere then exhausted the tier
    # for every other header-less caller — a global denial anyone could trigger by accident.
    # This helper already resolves the real peer, and only trusts proxy headers when the
    # direct peer is local, so it cannot be spoofed from outside.
    _client_host = _client_ip(request)
    # Reserve, not check-then-bill. The allowance is taken here, atomically, because the
    # work below awaits: a read here and a write after the await let 100 concurrent callers
    # all pass a limit of 5 (reproduced by an adversarial review of the first version).
    due = payment_gate.reserve(body.capability_id, request.headers, _client_host)
    if due is not None:
        raise HTTPException(status_code=402, detail=due)

    # Single release point, so the reservation is handed back on EVERY exit that does not
    # deliver: the 404 for an unknown SKU below, an authorization failure on a stored
    # watchbox, an unreachable sensor layer, or any unexpected exception. Releasing at each
    # return was the first shape and it already had a hole — the 404 kept the allowance for
    # a call that produced nothing — so the guard is structural rather than per-exit.
    resolved = False

    def _settle(result: Any) -> Any:
        """Keep the reservation when data was delivered; hand it back on a refusal."""
        nonlocal resolved
        payment_gate.settle(
            body.capability_id, request.headers, _client_host, result=result
        )
        resolved = True
        # What this call cost and what is left, for a buyer that has to notice an emptying
        # balance before it starts failing its own customers. Empty on an unpaid call.
        response.headers.update(payment_gate.credit_headers())
        return result

    try:
        inp = body.input if isinstance(body.input, dict) else {}
        if body.capability_id == "atlas.point.read@v1":
            return _settle(await _point_product(inp, request))
        if body.capability_id == "atlas.gnss.degradation.read@v1":
            stations = await aggregator.ensure_layer_readings({"gnss", "jamming"})
            return _settle(products_mod.gnss_degradation(inp, stations))
        if body.capability_id == "atlas.observability.attest@v1":
            stations = await aggregator.ensure_layer_readings({"radar", "alerts", "weather"})
            return _settle(products_mod.observability_attest(inp, stations))
        if body.capability_id == "atlas.route.integrity@v1":
            stations = await aggregator.ensure_layer_readings(
                {"gnss", "jamming", "ais", "adsb", "alerts", "flood", "cyclone",
                 "tsunami", "quake", "fire", "effis"}
            )
            return _settle(products_mod.route_integrity(inp, stations))
        if body.capability_id == "atlas.pv.irradiance.record@v1":
            stations = await aggregator.ensure_layer_readings(
                {"solar", "atmosphere", "weather"}
            )
            return _settle(products_mod.pv_irradiance_record(inp, stations))
        if body.capability_id == "atlas.geomag.window@v1":
            # Warm the two layers this answer is made of. The generic bbox path would
            # hand over whatever the map last expanded, and a planetary Kp pin plus 14
            # observatories are exactly the rows a cold store does not have.
            stations = await aggregator.ensure_layer_readings({"spacewx", "geomag"})
            return _settle(products_mod.geomag_window(inp, stations))
        if body.capability_id.startswith("atlas.mesh.") or body.capability_id.startswith(
            "atlas.field."
        ):
            stations = await _field_stations(inp)
            return _settle(products_mod.invoke_product(body.capability_id, inp, stations))
        if body.capability_id == "atlas.smoke.operations@v1":
            return _settle(await _smoke_product(inp))
        if body.capability_id == "atlas.nearest.read@v1":
            return _settle(products_mod.nearest_read(inp, await _nearest_stations(inp)))
        lookup = inp
        if body.capability_id == "atlas.watchbox.check@v1" and inp.get("watchbox_id"):
            # A STORED watchbox is a tenant resource — this SKU echoes its bbox, layers and
            # matches — so referencing one by id needs the owner token even here. The hub
            # forwards the invoke body rather than our headers, so the token is also accepted
            # as an input field; it is popped before the product sees it so it can never
            # reach a receipt or a log line. Ephemeral bbox+layers checks are unaffected.
            inp = dict(inp)
            owner_token = str(inp.pop("owner_token", "") or "").strip()
            wb = _authorize_watchbox(
                request, str(inp.get("watchbox_id") or ""), token=owner_token
            )
            lookup = {**wb, **{k: v for k, v in inp.items() if v is not None}}
        stations = await _product_stations(lookup)
        result = products_mod.invoke_product(body.capability_id, inp, stations)
        if result.get("ok") is False and str(result.get("refuse_reason") or "").startswith("unknown"):
            raise HTTPException(status_code=404, detail=result.get("refuse_reason"))
        return _settle(result)
    finally:
        if not resolved:
            # Must not raise out of `finally` — that would mask the real error — but must
            # never be silent either: a reservation nobody hands back is a caller charged
            # for a call that never produced anything.
            try:
                payment_gate.settle(
                    body.capability_id,
                    request.headers,
                    _client_host,
                    result={"ok": False, "refuse_reason": "invoke did not complete"},
                )
            except Exception:  # noqa: BLE001
                log.exception(
                    "invoke: releasing the reserved allowance for %s failed",
                    body.capability_id,
                )


@app.get("/api/v1/products")
async def products_catalog() -> dict[str, Any]:
    return {
        "service": "atlas",
        "version": __version__,
        "capabilities": products_mod.PRODUCT_CAPS,
        "well_known": "/.well-known/ai-market.json",
        "invoke": "/ai-market/v2/invoke",
    }


async def _metered_product(
    capability_id: str,
    request: Request,
    produce: Callable[[], Awaitable[dict[str, Any]]],
    response: Response | None = None,
) -> dict[str, Any]:
    """Run a REST product endpoint under the same allowance as its AI-market twin.

    These endpoints return the identical result to the priced SKU — same capability_id,
    same signed evidence — so leaving them open published a price list and then handed the
    same data away one URL over. A caller that made eight of them left no ledger row at
    all. Same reserve-then-resolve shape as the invoke handler: the allowance is taken
    before the work, and handed back when the product refuses.
    """
    from atlas import payment_gate

    host = _client_ip(request)
    due = payment_gate.reserve(capability_id, request.headers, host)
    if due is not None:
        raise HTTPException(status_code=402, detail=due)
    resolved = False
    try:
        result = await produce()
        payment_gate.settle(capability_id, request.headers, host, result=result)
        resolved = True
        if response is not None:
            response.headers.update(payment_gate.credit_headers())
        return result
    finally:
        if not resolved:
            try:
                payment_gate.settle(
                    capability_id, request.headers, host,
                    result={"ok": False, "refuse_reason": "product did not complete"},
                )
            except Exception:  # noqa: BLE001
                log.exception("releasing the reserved allowance for %s failed", capability_id)


@app.post("/api/v1/products/fire-weather")
async def product_fire_weather(body: BboxProductBody, request: Request, response: Response) -> dict[str, Any]:
    payload = {
        "west": body.west,
        "south": body.south,
        "east": body.east,
        "north": body.north,
        "limit": body.limit,
        "include_air": body.include_air,
    }

    async def produce() -> dict[str, Any]:
        return products_mod.fire_weather(payload, await _product_stations(payload))

    return await _metered_product("atlas.fire.weather@v1", request, produce, response=response)


@app.post("/api/v1/products/smoke-operations")
async def product_smoke_operations(
    body: SmokeOperationsBody, request: Request, response: Response
) -> dict[str, Any]:
    """``atlas.smoke.operations@v1`` — point-in-polygon smoke brief for one asset."""
    payload = body.model_dump(exclude_none=True)

    async def produce() -> dict[str, Any]:
        return await _smoke_product(payload)

    return await _metered_product("atlas.smoke.operations@v1", request, produce, response=response)


@app.post("/api/v1/products/situation-brief")
async def product_situation_brief(body: BboxProductBody, request: Request, response: Response) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "west": body.west,
        "south": body.south,
        "east": body.east,
        "north": body.north,
        "locale": body.locale,
    }
    if body.layers is not None:
        payload["layers"] = body.layers
    if body.preset is not None:
        payload["preset"] = body.preset
    if body.max_citations is not None:
        payload["max_citations"] = body.max_citations

    async def produce() -> dict[str, Any]:
        return products_mod.situation_brief(payload, await _product_stations(payload))

    return await _metered_product("atlas.situation.brief@v1", request, produce, response=response)


@app.post("/api/v1/products/nearest")
async def product_nearest(body: NearestProductBody, request: Request, response: Response) -> dict[str, Any]:
    """``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s)."""
    payload: dict[str, Any] = {
        "lat": body.lat,
        "lon": body.lon,
        "per_layer": body.per_layer,
    }
    if body.layer is not None:
        payload["layer"] = body.layer
    if body.layers is not None:
        payload["layers"] = body.layers
    if body.max_km is not None:
        payload["max_km"] = body.max_km

    async def produce() -> dict[str, Any]:
        stations = await _nearest_stations(payload)
        return products_mod.nearest_read(payload, stations)

    return await _metered_product("atlas.nearest.read@v1", request, produce, response=response)


@app.post("/api/v1/products/geomag-window")
async def product_geomag_window(body: GeomagWindowBody, request: Request, response: Response) -> dict[str, Any]:
    """``atlas.geomag.window@v1`` — coordinate → Kp window + observatory corroboration."""
    payload: dict[str, Any] = {"lat": body.lat, "lon": body.lon}
    if body.max_km is not None:
        payload["max_km"] = body.max_km
    if body.asset_id is not None:
        payload["asset_id"] = body.asset_id

    async def produce() -> dict[str, Any]:
        stations = await aggregator.ensure_layer_readings({"spacewx", "geomag"})
        return products_mod.geomag_window(
            payload, stations if isinstance(stations, list) else []
        )

    return await _metered_product("atlas.geomag.window@v1", request, produce, response=response)


@app.post("/api/v1/products/pv-irradiance-record")
async def product_pv_irradiance_record(
    body: PvIrradianceBody, request: Request, response: Response
) -> dict[str, Any]:
    """``atlas.pv.irradiance.record@v1`` — plant coordinate → dated irradiance record."""
    payload: dict[str, Any] = {"lat": body.lat, "lon": body.lon}
    if body.max_km is not None:
        payload["max_km"] = body.max_km
    if body.plant_id is not None:
        payload["plant_id"] = body.plant_id

    async def produce() -> dict[str, Any]:
        stations = await aggregator.ensure_layer_readings({"solar", "atmosphere", "weather"})
        return products_mod.pv_irradiance_record(
            payload, stations if isinstance(stations, list) else []
        )

    return await _metered_product("atlas.pv.irradiance.record@v1", request, produce, response=response)


@app.post("/api/v1/products/route-integrity")
async def product_route_integrity(body: RouteIntegrityBody, request: Request, response: Response) -> dict[str, Any]:
    """``atlas.route.integrity@v1`` — polyline → per-segment integrity and hazard brief."""
    payload: dict[str, Any] = {"route": body.route}
    if body.corridor_km is not None:
        payload["corridor_km"] = body.corridor_km
    if body.route_id is not None:
        payload["route_id"] = body.route_id

    async def produce() -> dict[str, Any]:
        stations = await aggregator.ensure_layer_readings(
            {"gnss", "jamming", "ais", "adsb", "alerts", "flood", "cyclone",
             "tsunami", "quake", "fire", "effis"}
        )
        return products_mod.route_integrity(
            payload, stations if isinstance(stations, list) else []
        )

    return await _metered_product("atlas.route.integrity@v1", request, produce, response=response)


@app.post("/api/v1/products/observability-attest")
async def product_observability_attest(
    body: ObservabilityAttestBody, request: Request, response: Response
) -> dict[str, Any]:
    """``atlas.observability.attest@v1`` — coordinate + window → what evidence exists."""
    payload: dict[str, Any] = {"lat": body.lat, "lon": body.lon}
    for field in ("start", "end", "max_km", "event_id"):
        value = getattr(body, field)
        if value is not None:
            payload[field] = value

    async def produce() -> dict[str, Any]:
        stations = await aggregator.ensure_layer_readings({"radar", "alerts", "weather"})
        return products_mod.observability_attest(
            payload, stations if isinstance(stations, list) else []
        )

    return await _metered_product("atlas.observability.attest@v1", request, produce, response=response)


@app.get("/api/v1/field-meshes")
async def product_field_meshes() -> dict[str, Any]:
    """Catalogue of licensed in-situ meshes. Not a priced SKU — the menu, not the meal."""
    from .field_meshes import mesh_catalog

    return {
        "service": "atlas",
        "claim_class": "in_situ_observation",
        "note": "Open-Meteo is not a mesh. Warning products are not a mesh.",
        "meshes": mesh_catalog(),
    }


@app.post("/api/v1/products/mesh-sample")
async def product_mesh_sample(body: FieldMeshBody, request: Request, response: Response) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)

    async def produce() -> dict[str, Any]:
        return products_mod.mesh_sample(payload, await _field_stations(payload))

    return await _metered_product("atlas.mesh.sample@v1", request, produce, response=response)


@app.post("/api/v1/products/field-consensus")
async def product_field_consensus(body: FieldMeshBody, request: Request, response: Response) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)

    async def produce() -> dict[str, Any]:
        return products_mod.field_consensus(payload, await _field_stations(payload))

    return await _metered_product("atlas.field.consensus@v1", request, produce, response=response)


@app.post("/api/v1/products/field-posterior")
async def product_field_posterior(body: FieldMeshBody, request: Request, response: Response) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)

    async def produce() -> dict[str, Any]:
        return products_mod.field_posterior(payload, await _field_stations(payload))

    return await _metered_product("atlas.field.posterior@v1", request, produce, response=response)


@app.post("/api/v1/products/field-shape")
async def product_field_shape(body: FieldMeshBody, request: Request, response: Response) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)

    async def produce() -> dict[str, Any]:
        return products_mod.field_shape(payload, await _field_stations(payload))

    return await _metered_product("atlas.field.shape@v1", request, produce, response=response)


@app.post("/api/v1/products/point")
async def product_point(body: PointProductBody, request: Request, response: Response) -> dict[str, Any]:
    """``atlas.point.read@v1`` — exact clickable point_id → signed evidence."""

    async def produce() -> dict[str, Any]:
        return await _point_product(
            {"point_id": body.point_id, "fresh": body.fresh}, request
        )

    return await _metered_product("atlas.point.read@v1", request, produce, response=response)


@app.post("/api/v1/products/gnss-degradation")
async def product_gnss_degradation(
    body: GnssDegradationBody, request: Request, response: Response
) -> dict[str, Any]:
    """Point/bbox/route → signed GNSS integrity field with claim boundaries."""
    payload = body.model_dump(exclude_none=True)

    async def produce() -> dict[str, Any]:
        stations = await aggregator.ensure_layer_readings({"gnss", "jamming"})
        return products_mod.gnss_degradation(payload, stations)

    return await _metered_product(
        "atlas.gnss.degradation.read@v1", request, produce, response=response
    )


@app.get("/api/v1/stream")
async def stream(request: Request) -> StreamingResponse:
    """Server-Sent Events fan-out of the shared snapshot."""

    async def event_gen() -> AsyncIterator[bytes]:
        q = aggregator.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    snap = await asyncio.wait_for(q.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    # Keepalive comment so proxies don't drop the stream.
                    yield b": keepalive\n\n"
                    continue
                payload = json.dumps(snap, separators=(",", ":"), default=str)
                yield f"event: snapshot\ndata: {payload}\n\n".encode()
        finally:
            aggregator.unsubscribe(q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


_BASEMAP_CFG_RE = re.compile(
    r'(<script id="atlas-basemap-config" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)


def _basemap_config() -> dict[str, str]:
    """Basemap provider the SPA may attach.

    A keyed provider is only ever announced together with its key — the client
    falls back to the keyless one otherwise, because keyless CARTO tiles come
    back with "API KEY REQUIRED" printed across the image.
    """
    provider = (settings.basemap_provider or "auto").strip().lower()
    if provider not in {"auto", "openfreemap", "carto", "none"}:
        provider = "auto"
    key = (settings.basemap_api_key or "").strip()
    if provider == "carto" and not key:
        provider = "openfreemap"
    return {"provider": provider, "key": key}


def _inject_basemap_config(html: str) -> str:
    payload = json.dumps(_basemap_config(), separators=(",", ":"))
    # </script> inside a JSON string would close the tag early.
    payload = payload.replace("<", "\\u003c")
    return _BASEMAP_CFG_RE.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)


def _read_html(name: str) -> str:
    for root in STATIC_ROOTS:
        path = root / name
        if path.is_file():
            return _inject_basemap_config(path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail=f"{name} not found — STATIC_ROOTS={STATIC_ROOTS}")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(_read_html("index.html"))


@app.get("/embed", response_class=HTMLResponse)
async def embed() -> HTMLResponse:
    return HTMLResponse(_read_html("embed.html"))


# Static assets (css/js) — first matching assets/ wins.
for _root in STATIC_ROOTS:
    assets = _root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
        break


# StaticFiles types responses from `mimetypes`, which reads /etc/mime.types — absent from the
# slim base image, so the fonts went out as text/plain. Browsers sniff woff2 and honour the
# `format('woff2')` in the stylesheet, so they rendered anyway; registering it keeps a correct
# Content-Type for anything downstream that is less forgiving.
mimetypes.add_type("font/woff2", ".woff2")

# The self-hosted webfonts index.html and embed.html declare. Mounted separately rather than
# tucked under assets/ so the <link> reads `fonts/fonts.css` exactly as it does on every other
# site in this repo — one shape for the mirror script to target. Without this mount the pages
# still render, in fallback fonts, and nothing errors; that silence is why it is worth a test.
for _root in STATIC_ROOTS:
    fonts = _root / "fonts"
    if fonts.is_dir():
        app.mount("/fonts", StaticFiles(directory=str(fonts)), name="fonts")
        break


@app.get("/favicon.svg", response_class=Response)
async def favicon() -> Response:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#0b1218"/>
  <circle cx="32" cy="32" r="18" fill="none" stroke="#3dd6c6" stroke-width="3"/>
  <circle cx="32" cy="32" r="4" fill="#ff6b4a"/>
  <path d="M32 8v6M32 50v6M8 32h6M50 32h6" stroke="#7ec8ff" stroke-width="2"/>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")
