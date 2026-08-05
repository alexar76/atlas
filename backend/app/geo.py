"""Geographic helpers for ATLAS map / viewport filtering."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def in_bbox(
    lat: float,
    lon: float,
    west: float,
    south: float,
    east: float,
    north: float,
) -> bool:
    """Return True if (lat, lon) lies inside the bbox (antimeridian-safe)."""
    if south > north:
        south, north = north, south
    if not (south <= lat <= north):
        return False
    if west <= east:
        return west <= lon <= east
    return lon >= west or lon <= east


def station_ids_in_bbox(
    stations: list[Any],
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    region_pad: float = 4.0,
) -> list[str]:
    """Filter a station list to ids whose anchors fall in the viewport."""
    ids: list[str] = []
    for s in stations:
        if not isinstance(s, dict):
            continue
        try:
            lat = float(s["lat"])
            lon = float(s["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if s.get("kind") == "region":
            if in_bbox(
                lat,
                lon,
                west - region_pad,
                south - region_pad,
                east + region_pad,
                north + region_pad,
            ):
                ids.append(str(s["id"]))
            continue
        if s.get("layer") == "quake" and abs(lat) < 1e-6 and abs(lon) < 1e-6:
            ids.append(str(s["id"]))
            continue
        if in_bbox(lat, lon, west, south, east, north):
            ids.append(str(s["id"]))
    return ids
