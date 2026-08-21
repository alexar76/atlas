"""Shared rules for objects that ATLAS can honestly place on the map.

Layer counters, viewport payloads and click details must agree on the same
geographic rows.  Keeping validation here prevents a feed from advertising
more objects than the map can expose (or silently dropping 0..360 longitudes).
"""

from __future__ import annotations

import math
from typing import Any

from .geo import wrap_lon


def normalize_map_point(lat_value: Any, lon_value: Any) -> tuple[float, float] | None:
    """Return a finite WGS84 point in ATLAS' -180..180 longitude convention."""
    try:
        lat = float(lat_value)
        lon = float(lon_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90.0 <= lat <= 90.0:
        return None
    return lat, wrap_lon(lon)


def normalized_hotspots(
    station: dict[str, Any],
) -> list[tuple[dict[str, Any], float, float]] | None:
    """Normalize every geolocated cluster row; ``None`` means no cluster payload."""
    raw = station.get("hotspots")
    if not isinstance(raw, list):
        return None
    out: list[tuple[dict[str, Any], float, float]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        lat_value = row.get("latitude")
        lon_value = row.get("longitude")
        if lat_value is None:
            lat_value = row.get("lat")
        if lon_value is None:
            lon_value = row.get("lon")
        point = normalize_map_point(
            lat_value,
            lon_value,
        )
        if point is not None:
            out.append((row, point[0], point[1]))
    return out


def is_actionable_station(station: dict[str, Any]) -> bool:
    """Whether a non-cluster station is presently representable and clickable."""
    if not station.get("online") or station.get("cluster_parent"):
        return False
    point = normalize_map_point(station.get("lat"), station.get("lon"))
    if point is None:
        return False
    lat, lon = point
    # Catalog event parents use Null Island until a real reading supplies a
    # coordinate. A genuine expanded observation at 0,0 has parent_id and is
    # allowed — 0,0 is a valid physical position.
    return not (
        station.get("kind") == "event"
        and abs(lat) < 1e-9
        and abs(lon) < 1e-9
        and not station.get("parent_id")
        and not station.get("has_reading")
    )
