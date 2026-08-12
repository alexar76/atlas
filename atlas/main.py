"""ATLAS FastAPI entry — cached GAIA map API + static map UI."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, ORJSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    await aggregator.start()
    yield
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
    allow_methods=["GET", "HEAD", "OPTIONS", "POST"],
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
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "public, max-age=5, stale-while-revalidate=30"
    return response


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
) -> dict[str, Any]:
    """Human-readable station card — used on pin / list click."""
    if fresh:
        await _guard_cache_bypass(request)
    try:
        return await aggregator.station_detail(device_id, fresh=fresh)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown station: {device_id}") from None


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
    await _guard_cache_bypass(request)
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


@app.get("/api/v1/watchboxes")
async def watchboxes_list() -> dict[str, Any]:
    return {
        "sku": "atlas.watchbox.subscribe@v1",
        "allowed_layers": sorted(watchbox_mod.ALLOWED_WATCHBOX_LAYERS),
        "watchboxes": watchbox_mod.STORE.list(),
    }


@app.post("/api/v1/watchboxes")
async def watchboxes_create(body: WatchboxCreateBody) -> dict[str, Any]:
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
    return {"ok": True, "watchbox": row}


@app.get("/api/v1/watchboxes/{watchbox_id}")
async def watchboxes_get(watchbox_id: str) -> dict[str, Any]:
    row = watchbox_mod.STORE.get(watchbox_id)
    if not row:
        raise HTTPException(status_code=404, detail="unknown watchbox")
    return {"watchbox": row}


@app.delete("/api/v1/watchboxes/{watchbox_id}")
async def watchboxes_delete(watchbox_id: str) -> dict[str, Any]:
    if not watchbox_mod.STORE.delete(watchbox_id):
        raise HTTPException(status_code=404, detail="unknown watchbox")
    return {"ok": True, "id": watchbox_id}


@app.post("/api/v1/watchboxes/{watchbox_id}/check")
async def watchboxes_check(watchbox_id: str) -> dict[str, Any]:
    """Paid-style evaluation — ``atlas.watchbox.check@v1``."""
    wb = watchbox_mod.STORE.get(watchbox_id)
    stations = await _product_stations(wb if isinstance(wb, dict) else None)
    result = products_mod.watchbox_check({"watchbox_id": watchbox_id}, stations)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("refuse_reason") or "check failed")
    return result


class ProductInvokeBody(BaseModel):
    capability_id: str = Field(..., min_length=3, max_length=128)
    input: Dict[str, Any] = Field(default_factory=dict)


class BboxProductBody(BaseModel):
    west: float = Field(..., ge=-180, le=180)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    north: float = Field(..., ge=-90, le=90)
    layers: Optional[List[str]] = None
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


@app.get("/.well-known/ai-market.json")
async def aimarket_well_known() -> dict[str, Any]:
    return market_mod.well_known()


@app.get("/ai-market/v2/manifest")
async def aimarket_manifest() -> dict[str, Any]:
    return market_mod.manifest()


@app.post("/ai-market/v2/invoke")
async def aimarket_invoke(body: ProductInvokeBody) -> dict[str, Any]:
    """Hub-compatible invoke for ATLAS composite products."""
    inp = body.input if isinstance(body.input, dict) else {}
    lookup = inp
    if body.capability_id == "atlas.watchbox.check@v1" and inp.get("watchbox_id"):
        wb = watchbox_mod.STORE.get(str(inp.get("watchbox_id") or ""))
        if isinstance(wb, dict):
            lookup = {**wb, **{k: v for k, v in inp.items() if v is not None}}
    stations = await _product_stations(lookup)
    result = products_mod.invoke_product(body.capability_id, inp, stations)
    if result.get("ok") is False and str(result.get("refuse_reason") or "").startswith("unknown"):
        raise HTTPException(status_code=404, detail=result.get("refuse_reason"))
    return result


@app.get("/api/v1/products")
async def products_catalog() -> dict[str, Any]:
    return {
        "service": "atlas",
        "version": __version__,
        "capabilities": products_mod.PRODUCT_CAPS,
        "well_known": "/.well-known/ai-market.json",
        "invoke": "/ai-market/v2/invoke",
    }


@app.post("/api/v1/products/fire-weather")
async def product_fire_weather(body: BboxProductBody) -> dict[str, Any]:
    payload = {
        "west": body.west,
        "south": body.south,
        "east": body.east,
        "north": body.north,
        "limit": body.limit,
        "include_air": body.include_air,
    }
    return products_mod.fire_weather(payload, await _product_stations(payload))


@app.post("/api/v1/products/situation-brief")
async def product_situation_brief(body: BboxProductBody) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "west": body.west,
        "south": body.south,
        "east": body.east,
        "north": body.north,
        "locale": body.locale,
    }
    if body.layers is not None:
        payload["layers"] = body.layers
    if body.max_citations is not None:
        payload["max_citations"] = body.max_citations
    return products_mod.situation_brief(payload, await _product_stations(payload))


@app.post("/api/v1/products/nearest")
async def product_nearest(body: NearestProductBody) -> dict[str, Any]:
    """``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s)."""
    stations = aggregator.product_stations()
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
    return products_mod.nearest_read(payload, stations if isinstance(stations, list) else [])


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


def _read_html(name: str) -> str:
    for root in STATIC_ROOTS:
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
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


@app.get("/favicon.svg", response_class=Response)
async def favicon() -> Response:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#0b1218"/>
  <circle cx="32" cy="32" r="18" fill="none" stroke="#3dd6c6" stroke-width="3"/>
  <circle cx="32" cy="32" r="4" fill="#ff6b4a"/>
  <path d="M32 8v6M32 50v6M8 32h6M50 32h6" stroke="#7ec8ff" stroke-width="2"/>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml")
