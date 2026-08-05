"""ATLAS FastAPI entry — cached GAIA map API + static map UI."""

from __future__ import annotations

import asyncio
import json
import logging
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

from .aggregator import aggregator
from .ai_assistant import ask as ai_ask
from .ai_assistant import list_providers as ai_list_providers
from .config import get_settings

log = logging.getLogger("atlas")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

def _static_roots() -> list[Path]:
    """Resolve SPA roots for both Docker (/app) and monorepo (atlas/) layouts."""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parents[1] / "frontend" / "dist",  # Docker: /app/frontend/dist
        here.parents[1] / "frontend" / "public",  # Docker: /app/frontend/public
        here.parents[2] / "frontend" / "dist",  # Monorepo: atlas/frontend/dist
        here.parents[2] / "frontend" / "public",  # Monorepo: atlas/frontend/public
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

app = FastAPI(
    title="ATLAS",
    version="0.1.0",
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


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    # Health + static assets stay cheap; API/SSE are limited.
    if path.startswith("/api/") or path.startswith("/embed"):
        ip = _client_ip(request)
        if not await limiter.allow(ip):
            return ORJSONResponse({"ok": False, "error": "rate_limited"}, status_code=429)
    response = await call_next(request)
    response.headers["X-ATLAS-Version"] = "0.1.0"
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
async def viewport(body: ViewportBody) -> dict[str, Any]:
    """Refresh readings for sensors inside the visible map bbox (TTL-cached)."""
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
    fresh: bool = Query(False, description="Bypass cache and re-read from GAIA"),
) -> dict[str, Any]:
    """Human-readable station card — used on pin / list click."""
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
async def refresh() -> dict[str, Any]:
    """Operator nudge — fleet + re-read currently cached stations."""
    return await aggregator.refresh()


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
