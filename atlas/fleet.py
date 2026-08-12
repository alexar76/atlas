"""Fleet pin building + quake trail helpers for the aggregator."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from . import __version__
from .formatters import headline
from .geo import utc_now
from .stations import LAYER_META, STATION_CATALOG, resolve_mode

log = logging.getLogger("atlas.fleet")

InvokeFn = Callable[..., Awaitable[Optional[dict[str, Any]]]]

# Layers whose pin lat/lon come from the reading (not a fixed catalog anchor).
EVENT_LAYERS = frozenset({"quake", "fire", "radiation", "jamming", "traffic"})
# Default-on LIVE event pins shown even before a fleet read. Traffic feeders are
# opt-in (GAIA_FEEDER_ENABLED) — only appear when registered in the GAIA fleet.
CATALOG_EVENT_LAYERS = frozenset({"quake", "fire", "radiation", "jamming"})


def pin_from_catalog(
    device_id: str,
    *,
    fleet_dev: dict[str, Any] | None = None,
    cached: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = STATION_CATALOG[device_id]
    fleet_dev = fleet_dev or {}
    cached = cached or {}
    source = fleet_dev.get("source")
    values = cached.get("values") if isinstance(cached, dict) else {}
    values = values if isinstance(values, dict) else {}
    lat = float(cached.get("lat", meta["lat"])) if cached else float(meta["lat"])
    lon = float(cached.get("lon", meta["lon"])) if cached else float(meta["lon"])
    online = bool(fleet_dev.get("online", True)) if fleet_dev else True
    mode, live = resolve_mode(
        catalog_mode=str(meta.get("mode") or "live"),
        source=source,
        in_fleet=bool(fleet_dev),
    )
    pin = {
        "id": device_id,
        "layer": meta["layer"],
        "label": meta["label"],
        "place": meta["place"],
        "kind": meta["kind"],
        "lat": lat,
        "lon": lon,
        "online": online,
        "mode": mode,
        "live": live,
        "source": str(source) if source else None,
        "site": str(fleet_dev.get("site") or cached.get("site") or ""),
        "model": str(fleet_dev.get("model") or ""),
        "values": values or {},
        "headline": cached.get("headline") or ("—" if not values else headline(meta["layer"], values)),
        "color": LAYER_META.get(meta["layer"], {}).get("color", "#88a"),
        "has_reading": bool(values),
    }
    hotspots = cached.get("hotspots") if isinstance(cached, dict) else None
    if isinstance(hotspots, list) and hotspots:
        pin["hotspots"] = hotspots
    return pin


def remember_quake(
    trail: list[dict[str, Any]],
    station: dict[str, Any],
    *,
    history: int,
) -> list[dict[str, Any]]:
    vals = station.get("values") or {}
    try:
        lat = float(vals.get("latitude", station.get("lat")))
        lon = float(vals.get("longitude", station.get("lon")))
        mag = float(vals.get("magnitude", 0))
    except (TypeError, ValueError):
        return trail
    if abs(lat) < 1e-6 and abs(lon) < 1e-6:
        return trail
    event = {
        "id": f"q-{int(time.time())}-{mag}",
        "lat": lat,
        "lon": lon,
        "magnitude": mag,
        "depth_km": vals.get("depth_km"),
        "at": utc_now(),
        "place": station.get("place") or "event",
    }
    if trail:
        prev = trail[-1]
        if (
            abs(prev["lat"] - lat) < 1e-4
            and abs(prev["lon"] - lon) < 1e-4
            and abs(prev["magnitude"] - mag) < 1e-6
        ):
            return trail
    out = list(trail)
    out.append(event)
    return out[-history:]


def expand_fire_hotspots(
    stations: list[dict[str, Any]],
    *,
    expand: bool = True,
) -> list[dict[str, Any]]:
    """Fan event ``hotspots[]`` into one map pin per detection.

    Applies to fire (FIRMS), radiation (Safecast), quake (USGS), and jamming
    (CyberNews) when the reading carries a cluster. Catalog SKUs remain Hub
    device_ids; the map shows ``{prefix}-…`` pins so layer toggles match the
    full field (industry FIRMS-style behaviour).

    Pass ``expand=False`` for wire snapshots (sidebar totals only) — the map
    loads densified pins via viewport + client cache.
    """
    if not expand:
        out: list[dict[str, Any]] = []
        for station in stations:
            if not isinstance(station, dict):
                continue
            slim = {k: v for k, v in station.items() if k != "hotspots"}
            out.append(slim)
        return out
    cluster_meta: dict[str, dict[str, Any]] = {
        "fire": {
            "prefix": "firms-hs",
            "keys": ("brightness_k", "confidence", "latitude", "longitude"),
        },
        "radiation": {
            "prefix": "rad-hs",
            "keys": ("cpm", "latitude", "longitude"),
        },
        "quake": {
            "prefix": "quake-ev",
            "keys": ("magnitude", "depth_km", "latitude", "longitude"),
        },
        "jamming": {
            "prefix": "jam-ev",
            "keys": ("severity_score", "radius_km", "latitude", "longitude"),
        },
    }
    out = []
    for station in stations:
        layer = str(station.get("layer") or "")
        meta = cluster_meta.get(layer)
        raw = station.get("hotspots")
        if meta is None or not isinstance(raw, list) or not raw:
            slim = {k: v for k, v in station.items() if k != "hotspots"}
            out.append(slim)
            continue
        parent_id = str(station.get("id") or f"{layer}-01")
        # Stable short tag so multiple Safecast anchors don't collide.
        tag = parent_id.replace("safecast-", "sc").replace("firms-fire-", "ff")
        tag = tag.replace("usgs-quake-", "uq").replace("cybernews-jam-", "cj")
        tag = re.sub(r"[^a-zA-Z0-9_-]", "", tag)[:24] or "x"
        color = station.get("color") or LAYER_META.get(layer, {}).get("color", "#888")
        prefix = str(meta["prefix"])
        keys: tuple[str, ...] = meta["keys"]
        expanded = 0
        seen_ids: set[str] = set()
        for i, row in enumerate(raw):
            if not isinstance(row, dict):
                continue
            try:
                lat = float(row.get("latitude"))
                lon = float(row.get("longitude"))
            except (TypeError, ValueError):
                continue
            if abs(lat) < 1e-6 and abs(lon) < 1e-6:
                continue
            values = {k: row.get(k) for k in keys if row.get(k) is not None}
            values["latitude"] = lat
            values["longitude"] = lon
            values = {str(k): v for k, v in values.items() if v is not None}
            # Coordinate-derived id: stable across densifies so the client's
            # session point cache merges instead of corrupting (index-based ids
            # reused the same id space for every camera bbox).
            pin_id = f"{prefix}-{tag}-{round(lat * 1e4)}_{round(lon * 1e4)}"
            if pin_id in seen_ids:
                pin_id = f"{pin_id}-{i}"
            seen_ids.add(pin_id)
            # Slim pins — full catalog metadata on every FIRMS row froze snapshot
            # serialization (~100MB) and the asyncio loop.
            out.append(
                {
                    "id": pin_id,
                    "parent_id": parent_id,
                    "layer": layer,
                    "kind": "event",
                    "lat": lat,
                    "lon": lon,
                    "online": bool(station.get("online", True)),
                    "mode": station.get("mode") or "live",
                    "live": bool(station.get("live")),
                    "values": values,
                    "color": color,
                    "has_reading": True,
                    "label": station.get("label") or parent_id,
                    "headline": headline(layer, values),
                }
            )
            expanded += 1
        if expanded == 0:
            slim = {k: v for k, v in station.items() if k != "hotspots"}
            out.append(slim)
    return out


def parse_fleet_devices(fleet: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    devices_raw = (fleet or {}).get("devices") if isinstance(fleet, dict) else None
    devices_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(devices_raw, list):
        for d in devices_raw:
            if isinstance(d, dict) and d.get("device_id"):
                devices_by_id[str(d["device_id"])] = d
    return devices_by_id


def wanted_station_ids(devices_by_id: dict[str, dict[str, Any]]) -> list[str]:
    if devices_by_id:
        return [
            did
            for did, meta in STATION_CATALOG.items()
            if did in devices_by_id or meta["layer"] in CATALOG_EVENT_LAYERS
        ]
    return list(STATION_CATALOG.keys())


async def _drain_fire_hotspot_pages(
    *,
    invoke: InvokeFn,
    capability_id: str,
    device_id: str,
    first_reading: dict[str, Any],
    seed: list[dict[str, Any]],
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """Pull remaining FIRMS packets via ``next_cursor`` with idempotent retries.

    On transient failure we retry the **same** cursor (GAIA pages are idempotent).
    If retries exhaust we keep what we already have rather than wiping the cluster.
    """
    out = list(seed)
    cursor = first_reading.get("next_cursor")
    if not cursor:
        return out
    total = first_reading.get("hotspot_total")
    try:
        total_i = int(total) if total is not None else None
    except (TypeError, ValueError):
        total_i = None
    # Safety: never loop forever even if a buggy peer always returns next_cursor.
    # 250k @ 2000/page ≈ 125 pages; leave headroom.
    max_pages = 200
    pages = 0
    while cursor and pages < max_pages:
        if total_i is not None and len(out) >= total_i:
            break
        pages += 1
        attempt = 0
        body: dict[str, Any] | None = None
        while attempt <= max_retries:
            body = await invoke(
                capability_id,
                device_id,
                extra_input={"cursor": cursor, "page_size": 2000},
            )
            if isinstance(body, dict):
                break
            attempt += 1
            if attempt > max_retries:
                log.warning(
                    "%s: hotspot page resume failed after %s retries (kept %s/%s)",
                    device_id,
                    max_retries,
                    len(out),
                    total_i if total_i is not None else "?",
                )
                return out
            await asyncio.sleep(min(2.0, 0.25 * (2 ** (attempt - 1))))
        assert isinstance(body, dict)
        r = body.get("reading") if isinstance(body.get("reading"), dict) else body
        if not isinstance(r, dict):
            return out
        raw_hs = r.get("hotspots")
        if isinstance(raw_hs, list):
            out.extend(h for h in raw_hs if isinstance(h, dict))
        cursor = r.get("next_cursor")
        if not cursor:
            break
    return out


async def fetch_station_reading(
    device_id: str,
    *,
    fleet_by_id: dict[str, dict[str, Any]],
    invoke: InvokeFn,
    on_quake: Optional[Callable[[dict[str, Any]], None]] = None,
    fire_limit: int | None = None,
    fire_bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    meta = STATION_CATALOG.get(device_id)
    if not meta:
        raise KeyError(device_id)
    fleet_dev = fleet_by_id.get(device_id) or {}
    online = bool(fleet_dev.get("online", True)) if fleet_dev else True
    source = fleet_dev.get("source")
    mode, live = resolve_mode(
        catalog_mode=str(meta.get("mode") or "live"),
        source=source,
        in_fleet=bool(fleet_dev),
    )
    values: dict[str, Any] = {}
    # None = this read carries no cluster answer (failed read / count-only) —
    # ReadingStore then keeps the prior cluster. A successful cluster read sets
    # a real list (possibly empty), which is authoritative and clears stale data.
    hotspots: list[dict[str, Any]] | None = None
    site = str(fleet_dev.get("site") or "")
    extra: dict[str, Any] = {}
    if meta["layer"] == "fire":
        # Count/headline only unless a viewport bbox asks for map densify —
        # matched totals are global regardless of the collect cap, so max_total=1
        # avoids pinning a 250k-row session in GAIA for a sidebar number.
        limit = int(fire_limit if fire_limit is not None else 1)
        extra["max_total"] = limit
        if fire_bbox is not None:
            extra["page_size"] = 2000
            west, south, east, north = fire_bbox
            extra.update({"west": west, "south": south, "east": east, "north": north})
        else:
            # Count + headline only — first packet discarded for map pins.
            extra["page_size"] = 1
    if extra:
        reading = None
        attempts = 4 if meta["layer"] == "fire" else 1
        for attempt in range(attempts):
            reading = await invoke(str(meta["capability"]), device_id, extra_input=extra)
            if isinstance(reading, dict):
                break
            if attempt + 1 < attempts:
                await asyncio.sleep(min(4.0, 0.4 * (2 ** attempt)))
    else:
        reading = await invoke(str(meta["capability"]), device_id)
    if meta["layer"] == "fire" and not isinstance(reading, dict):
        # Do not clobber a good hotspot cluster with an empty pin on timeout/429.
        raise RuntimeError(f"{device_id}: GAIA fire read failed")
    if isinstance(reading, dict):
        r = reading.get("reading") if isinstance(reading.get("reading"), dict) else reading
        if isinstance(r, dict):
            vals = r.get("values")
            if isinstance(vals, dict):
                values = {str(k): v for k, v in vals.items()}
            site = str(r.get("site") or site)
            raw_hs = r.get("hotspots")
            if isinstance(raw_hs, list):
                hotspots = [h for h in raw_hs if isinstance(h, dict)]
            if meta["layer"] == "fire":
                if fire_bbox is not None:
                    # Viewport densify — drain every packet in-bbox for the map.
                    hotspots = await _drain_fire_hotspot_pages(
                        invoke=invoke,
                        capability_id=str(meta["capability"]),
                        device_id=device_id,
                        first_reading=r,
                        seed=hotspots,
                    )
                else:
                    # Count-only: do not set hotspots (ReadingStore keeps prior cluster).
                    hotspots = None
            matched = r.get("hotspot_matched")
            total = r.get("hotspot_total")
            try:
                if matched is not None:
                    station_matched = int(matched)
                elif total is not None:
                    station_matched = int(total)
                else:
                    station_matched = len(hotspots or [])
            except (TypeError, ValueError):
                station_matched = len(hotspots or [])
        else:
            station_matched = 0
    else:
        station_matched = 0

    lat = float(meta["lat"])
    lon = float(meta["lon"])
    if meta["layer"] in EVENT_LAYERS:
        try:
            lat = float(values.get("latitude", lat))
            lon = float(values.get("longitude", lon))
        except (TypeError, ValueError):
            pass

    station = {
        "id": device_id,
        "layer": meta["layer"],
        "label": meta["label"],
        "place": meta["place"],
        "kind": meta["kind"],
        "lat": lat,
        "lon": lon,
        "online": bool(online and (values or meta["layer"] in EVENT_LAYERS)),
        "mode": mode,
        "live": live,
        "source": str(source) if source else None,
        "site": site,
        "model": str(fleet_dev.get("model") or ""),
        "values": values,
        "headline": headline(meta["layer"], values),
        "color": LAYER_META.get(meta["layer"], {}).get("color", "#88a"),
        "has_reading": bool(values),
        "fetched_at": utc_now(),
    }
    if station_matched:
        station["hotspot_matched"] = int(station_matched)
    if hotspots is not None:
        # Fresh cluster answer is authoritative: an explicit empty list clears a
        # stale cluster (ReadingStore restores only when the key is absent).
        station["hotspots"] = hotspots
        station["hotspot_count"] = len(hotspots)
    if meta["layer"] == "quake" and on_quake:
        on_quake(station)
    return station


def assemble_fleet_snapshot(
    *,
    stations: list[dict[str, Any]],
    quake_trail: list[dict[str, Any]],
    gaia_url: str,
    public_url: str = "https://atlas.modelmarket.dev",
) -> dict[str, Any]:
    stations = expand_fire_hotspots(stations, expand=False)
    online = sum(1 for s in stations if s.get("online"))
    live_n = sum(1 for s in stations if s.get("mode") == "live" or s.get("live"))
    sim_n = sum(1 for s in stations if s.get("mode") == "sim")
    fire_n = sum(1 for s in stations if s.get("layer") == "fire")
    status = "ok" if stations else "error"
    if stations and online == 0:
        status = "degraded"
    return {
        "service": "atlas",
        "version": __version__,
        "status": status,
        "generated_at": utc_now(),
        "_monotonic": time.monotonic(),
        "age_ms": 0,
        "stale": False,
        "gaia_url": gaia_url.rstrip("/"),
        "public_url": (public_url or "https://atlas.modelmarket.dev").rstrip("/"),
        "layers": LAYER_META,
        "stations": stations,
        "quakes": list(quake_trail),
        "summary": {
            "stations": len(stations),
            "online": online,
            "live": live_n,
            "sim": sim_n,
            "layers": len({s["layer"] for s in stations}),
            "quakes": len(quake_trail),
            "fires": fire_n,
            "cached_readings": sum(1 for s in stations if s.get("has_reading")),
        },
    }
