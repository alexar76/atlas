"""ATLAS loader for ``atlas/config/extra_sensors.yaml`` (mirror of GAIA)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

KIND_META: dict[str, dict[str, str]] = {
    "open-meteo-weather": {
        "layer": "weather",
        "capability": "gaia.weather.read@v1",
        "mode": "live",
    },
    "open-meteo-air": {
        "layer": "air",
        "capability": "gaia.air.read@v1",
        "mode": "live",
    },
    "nws": {
        "layer": "weather",
        "capability": "gaia.weather.read@v1",
        "mode": "live",
    },
    "opensensemap": {
        "layer": "air",
        "capability": "gaia.air.read@v1",
        "mode": "live",
    },
    "noaa-tide": {
        "layer": "tide",
        "capability": "gaia.tide.read@v1",
        "mode": "live",
    },
    "openaq": {
        "layer": "air",
        "capability": "gaia.air.read@v1",
        "mode": "live",
    },
    "uk-grid": {
        "layer": "grid",
        "capability": "gaia.grid.read@v1",
        "mode": "live",
    },
    "usgs-quake": {
        "layer": "quake",
        "capability": "gaia.quake.read@v1",
        "mode": "live",
    },
    "usgs-river": {
        "layer": "river",
        "capability": "gaia.river.read@v1",
        "mode": "live",
    },
    "ndbc-buoy": {
        "layer": "marine",
        "capability": "gaia.marine.read@v1",
        "mode": "live",
    },
    "open-meteo-marine": {
        "layer": "marine",
        "capability": "gaia.marine.read@v1",
        "mode": "live",
    },
    "firms-fire": {
        "layer": "fire",
        "capability": "gaia.fire.read@v1",
        "mode": "live",
    },
    "safecast": {
        "layer": "radiation",
        "capability": "gaia.radiation.read@v1",
        "mode": "live",
    },
    "cybernews-jamming": {
        "layer": "jamming",
        "capability": "gaia.jamming.read@v1",
        "mode": "live",
    },
    "eonet": {
        "layer": "events",
        "capability": "gaia.events.read@v1",
        "mode": "live",
    },
    "swpc": {
        "layer": "spacewx",
        "capability": "gaia.spacewx.read@v1",
        "mode": "live",
    },
    "glm": {
        "layer": "lightning",
        "capability": "gaia.lightning.read@v1",
        "mode": "live",
    },
    "nws-cap": {
        "layer": "alerts",
        "capability": "gaia.alerts.read@v1",
        "mode": "live",
    },
    "sensor-community": {
        "layer": "air",
        "capability": "gaia.air.read@v1",
        "mode": "live",
    },
    "cwop": {
        "layer": "weather",
        "capability": "gaia.weather.read@v1",
        "mode": "live",
    },
    "argo": {
        "layer": "argo",
        "capability": "gaia.argo.read@v1",
        "mode": "live",
    },
    "metno-metar": {
        "layer": "weather",
        "capability": "gaia.weather.read@v1",
        "mode": "live",
    },
    "usgs-geomag": {
        "layer": "geomag",
        "capability": "gaia.geomag.read@v1",
        "mode": "live",
    },
    "sim-weather": {
        "layer": "weather",
        "capability": "gaia.weather.read@v1",
        "mode": "sim",
    },
    "sim-air": {
        "layer": "air",
        "capability": "gaia.air.read@v1",
        "mode": "sim",
    },
    "sim-energy": {
        "layer": "energy",
        "capability": "gaia.energy.read@v1",
        "mode": "sim",
    },
    "nhc-cyclone": {
        "layer": "cyclone",
        "capability": "gaia.cyclone.read@v1",
        "mode": "live",
    },
    "emsc-quake": {
        "layer": "quake",
        "capability": "gaia.quake.read@v1",
        "mode": "live",
    },
    "ea-flood": {
        "layer": "flood",
        "capability": "gaia.flood.read@v1",
        "mode": "live",
    },
    "ptwc-tsunami": {
        "layer": "tsunami",
        "capability": "gaia.tsunami.read@v1",
        "mode": "live",
    },
    "kystverket-ais": {
        "layer": "ais",
        "capability": "gaia.ais.public.read@v1",
        "mode": "live",
    },
    "adsb-lol": {
        "layer": "adsb",
        "capability": "gaia.adsb.public.read@v1",
        "mode": "live",
    },
}


def _config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "extra_sensors.yaml"


@lru_cache(maxsize=1)
def load_sensors() -> tuple[dict[str, Any], ...]:
    path = _config_path()
    if not path.is_file():
        return ()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = raw.get("sensors") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("enabled", True) is False:
            continue
        device_id = str(row.get("device_id") or "").strip()
        kind = str(row.get("kind") or "").strip()
        if not device_id or kind not in KIND_META:
            continue
        out.append(row)
    return tuple(out)


def atlas_catalog_entries() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in load_sensors():
        kind = str(row["kind"])
        meta = KIND_META[kind]
        device_id = str(row["device_id"])
        out[device_id] = {
            "layer": str(row.get("layer") or meta["layer"]),
            "label": str(row.get("label") or device_id),
            "capability": str(row.get("capability") or meta["capability"]),
            "lat": float(row.get("lat") or 0.0),
            "lon": float(row.get("lon") or 0.0),
            "place": str(row.get("place") or ""),
            "kind": str(row.get("pin_kind") or "point"),
            "mode": str(row.get("mode") or meta["mode"]),
        }
    return out


def place_targets() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in load_sensors():
        aliases = [str(a) for a in (row.get("aliases") or []) if str(a).strip()]
        place = str(row.get("place") or "").strip()
        device_id = str(row["device_id"])
        key = str(row.get("place_id") or device_id)
        if not aliases and place:
            aliases = [place.lower(), device_id]
        if not aliases:
            continue
        if key in out:
            prev = out[key]
            sids = list(prev.get("station_ids") or ())
            if device_id not in sids:
                sids.append(device_id)
            prev["station_ids"] = tuple(sids)
            continue
        out[key] = {
            "aliases": tuple(aliases),
            "station_ids": (device_id,),
            "lon": float(row.get("lon") or 0.0),
            "lat": float(row.get("lat") or 0.0),
            "zoom": float(row.get("zoom") or 9.5),
            "label": place or device_id,
        }
    return out
