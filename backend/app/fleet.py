"""Fleet pin building + quake trail helpers for the aggregator."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from . import __version__
from .formatters import headline
from .geo import utc_now
from .stations import LAYER_META, STATION_CATALOG

log = logging.getLogger("atlas.fleet")

InvokeFn = Callable[[str, Optional[str]], Awaitable[Optional[dict[str, Any]]]]


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
    return {
        "id": device_id,
        "layer": meta["layer"],
        "label": meta["label"],
        "place": meta["place"],
        "kind": meta["kind"],
        "lat": lat,
        "lon": lon,
        "online": online,
        "live": bool(source),
        "source": str(source) if source else None,
        "site": str(fleet_dev.get("site") or cached.get("site") or ""),
        "model": str(fleet_dev.get("model") or ""),
        "values": values or {},
        "headline": cached.get("headline") or ("—" if not values else headline(meta["layer"], values)),
        "color": LAYER_META.get(meta["layer"], {}).get("color", "#88a"),
        "has_reading": bool(values),
    }


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
            if did in devices_by_id or meta["layer"] == "quake"
        ]
    return list(STATION_CATALOG.keys())


async def fetch_station_reading(
    device_id: str,
    *,
    fleet_by_id: dict[str, dict[str, Any]],
    invoke: InvokeFn,
    on_quake: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    meta = STATION_CATALOG.get(device_id)
    if not meta:
        raise KeyError(device_id)
    fleet_dev = fleet_by_id.get(device_id) or {}
    online = bool(fleet_dev.get("online", True)) if fleet_dev else True
    source = fleet_dev.get("source")
    values: dict[str, Any] = {}
    site = str(fleet_dev.get("site") or "")
    reading = await invoke(str(meta["capability"]), device_id)
    if isinstance(reading, dict):
        r = reading.get("reading") if isinstance(reading.get("reading"), dict) else reading
        if isinstance(r, dict):
            vals = r.get("values")
            if isinstance(vals, dict):
                values = {str(k): v for k, v in vals.items()}
            site = str(r.get("site") or site)

    lat = float(meta["lat"])
    lon = float(meta["lon"])
    if meta["layer"] == "quake":
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
        "online": bool(online and (values or meta["layer"] == "quake")),
        "live": bool(source),
        "source": str(source) if source else None,
        "site": site,
        "model": str(fleet_dev.get("model") or ""),
        "values": values,
        "headline": headline(meta["layer"], values),
        "color": LAYER_META.get(meta["layer"], {}).get("color", "#88a"),
        "has_reading": bool(values),
        "fetched_at": utc_now(),
    }
    if meta["layer"] == "quake" and on_quake:
        on_quake(station)
    return station


def assemble_fleet_snapshot(
    *,
    stations: list[dict[str, Any]],
    quake_trail: list[dict[str, Any]],
    gaia_url: str,
) -> dict[str, Any]:
    online = sum(1 for s in stations if s.get("online"))
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
        "layers": LAYER_META,
        "stations": stations,
        "quakes": list(quake_trail),
        "summary": {
            "stations": len(stations),
            "online": online,
            "layers": len({s["layer"] for s in stations}),
            "quakes": len(quake_trail),
            "cached_readings": sum(1 for s in stations if s.get("has_reading")),
        },
    }
