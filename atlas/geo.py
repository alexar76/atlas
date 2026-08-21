"""Geographic helpers for ATLAS map / viewport filtering."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def wrap_lon(lon: float) -> float:
    """Wrap a longitude into [-180, 180] (in-range values pass through)."""
    lon = float(lon)
    if -180.0 <= lon <= 180.0:
        return lon
    return ((lon + 180.0) % 360.0) - 180.0


def normalize_bbox(
    west: float,
    south: float,
    east: float,
    north: float,
) -> tuple[float, float, float, float]:
    """Coerce any viewport into the ATLAS contract (lat ±90, lon ±180).

    Map clients (MapLibre) report unwrapped bounds when the world is narrower
    than the canvas — e.g. west=-239 / east=+240. Spans that cover the globe
    collapse to -180/180; anything else is wrapped (west > east is a valid
    antimeridian bbox for ``in_bbox``).
    """
    south = max(-90.0, min(90.0, float(south)))
    north = max(-90.0, min(90.0, float(north)))
    if south > north:
        south, north = north, south
    west = float(west)
    east = float(east)
    if abs(east - west) >= 360.0:
        return -180.0, south, 180.0, north
    return wrap_lon(west), south, wrap_lon(east), north


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


def lon_span(west: float, east: float) -> float:
    """Width of a bbox in degrees, wrap-aware (west > east crosses ±180)."""
    if west <= east:
        return east - west
    return (180.0 - west) + (east + 180.0)


def pad_lon(west: float, east: float, pad: float) -> tuple[float, float]:
    """Widen a longitude window by ``pad`` on both sides, wrap-aware.

    A wrapped window (west > east) must GROW when padded; naive ``west - pad`` /
    ``east + pad`` can flip west/east and silently turn the window into its own
    complement, which drops stations instead of adding neighbours.
    """
    pad = max(0.0, float(pad))
    if pad <= 0:
        return west, east
    if lon_span(west, east) + 2.0 * pad >= 360.0:
        return -180.0, 180.0
    return wrap_lon(west - pad), wrap_lon(east + pad)


def expand_bbox(
    west: float,
    south: float,
    east: float,
    north: float,
    pad_deg: float,
) -> tuple[float, float, float, float]:
    """Pad a viewport in degrees (lat clamped to ±90; lon wrap-aware)."""
    pad = max(0.0, float(pad_deg))
    if pad <= 0:
        return west, south, east, north
    south2 = max(-90.0, south - pad)
    north2 = min(90.0, north + pad)
    west2, east2 = pad_lon(west, east, pad)
    return west2, south2, east2, north2


def station_ids_in_bbox(
    stations: list[Any],
    west: float,
    south: float,
    east: float,
    north: float,
    *,
    region_pad: float = 4.0,
    pad_deg: float = 0.0,
) -> list[str]:
    """Filter a station list to ids whose anchors fall in the viewport (optional pad)."""
    if pad_deg:
        west, south, east, north = expand_bbox(west, south, east, north, pad_deg)
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
            # Wrap-aware padding: a wrapped window would otherwise invert here
            # and drop region pins (uk-grid-01) from the refresh set.
            rw, re_ = pad_lon(west, east, region_pad)
            if in_bbox(
                lat,
                lon,
                rw,
                max(-90.0, south - region_pad),
                re_,
                min(90.0, north + region_pad),
            ):
                ids.append(str(s["id"]))
            continue
        if s.get("layer") == "quake" and abs(lat) < 1e-6 and abs(lon) < 1e-6:
            ids.append(str(s["id"]))
            continue
        if in_bbox(lat, lon, west, south, east, north):
            ids.append(str(s["id"]))
    return ids
