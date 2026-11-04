"""Shared rules for objects that ATLAS can honestly place on the map.

Layer counters, viewport payloads and click details must agree on the same
geographic rows.  Keeping validation here prevents a feed from advertising
more objects than the map can expose (or silently dropping 0..360 longitudes).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .geo import wrap_lon

WATER_QUALITY_VALUE_FIELDS = (
    "water_temperature_c", "ph", "dissolved_oxygen_mg_l",
    "specific_conductance_us_cm",
)

_CLUSTER_OBSERVATION_AGE = {
    "usgs-rtfi-01": (-timedelta(minutes=5), timedelta(hours=2)),
    "usgs-groundwater-01": (timedelta(0), timedelta(hours=24)),
    "hubeau-groundwater-01": (timedelta(0), timedelta(hours=24)),
}
_FINTRAFFIC_NOTICE_IDS = {"fintraffic-road-announcements-01", "fintraffic-roadworks-01"}
NDW_NOTICE_IDS = frozenset({"ndw-road-srti-01", "ndw-road-closures-01"})


def _timestamp(raw: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else None


def is_fresh_cluster_observation(
    parent_id: str, row: dict[str, Any], *, now: datetime | None = None,
) -> bool:
    """Apply source-time limits for clusters whose upstream samples can age out."""
    if parent_id in _FINTRAFFIC_NOTICE_IDS or parent_id in NDW_NOTICE_IDS:
        current = now if now is not None else datetime.now(timezone.utc)
        start, end = _timestamp(row.get("valid_from")), _timestamp(row.get("valid_until"))
        if not start or start > current or (row.get("valid_until") and (not end or end <= current)):
            return False
        if parent_id in NDW_NOTICE_IDS:
            published = _timestamp(row.get("source_published_at"))
            expires = _timestamp(row.get("source_expires_at"))
            return bool(published and expires and published <= current < expires <= published + timedelta(minutes=5))
        read_at = _timestamp(row.get("source_read_at"))
        return bool(read_at and current - timedelta(minutes=30) <= read_at <= current + timedelta(minutes=2))
    if parent_id == "awc-gairmet-01":
        current = now if now is not None else datetime.now(timezone.utc)
        issued, valid = _timestamp(row.get("issue_at")), _timestamp(row.get("valid_at"))
        return bool(issued and valid and current - timedelta(hours=7) <= issued <= current
                    and current <= valid <= current + timedelta(hours=3))
    age_range = _CLUSTER_OBSERVATION_AGE.get(parent_id)
    if age_range is None:
        return True
    observed = _timestamp(row.get("observed_at"))
    if observed is None:
        return False
    age = (now if now is not None else datetime.now(timezone.utc)) - observed
    return age_range[0] <= age <= age_range[1]


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


def source_reading_expiry(station: dict[str, Any]) -> float | None:
    """Last usable source time for time-bounded readings and NDW snapshots."""
    values = station.get("values")
    if not isinstance(values, dict) or not values:
        return None
    device_id = str(station.get("id") or "")
    try:
        if device_id.startswith(("ea-tide-", "fmi-marine-")):
            expiry = float(values["observation_unix"]) + 2 * 3600
        elif device_id.startswith("snotel-"):
            expiry = float(values["observation_unix"]) + 6 * 3600
        elif device_id.startswith("nwps-"):
            expiry = min(
                float(values["forecast_issued_unix"]) + 24 * 3600,
                float(values["forecast_valid_unix"]),
            )
        elif device_id in NDW_NOTICE_IDS:
            published = _timestamp(station.get("source_published_at"))
            expires = _timestamp(station.get("source_expires_at"))
            if not published or not expires or not published < expires <= published + timedelta(minutes=5):
                return 0.0
            expiry = expires.timestamp()
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return 0.0
    return expiry if math.isfinite(expiry) else 0.0


def without_expired_source_reading(station: dict[str, Any], *, now: float) -> dict[str, Any]:
    expiry = source_reading_expiry(station)
    if expiry is None or now < expiry:
        return station
    expired = {**station, "values": {}, "online": False, "has_reading": False,
               "headline": "Source data expired", "stale": True}
    if station.get("id") in NDW_NOTICE_IDS and "hotspots" in station:
        expired.update(hotspots=[], hotspot_count=0, hotspot_matched=0)
    return expired


def normalized_hotspots(
    station: dict[str, Any],
) -> list[tuple[dict[str, Any], float, float]] | None:
    """Normalize every geolocated cluster row; ``None`` means no cluster payload."""
    raw = station.get("hotspots")
    if not isinstance(raw, list):
        return None
    source_id = str(station.get("id") or "")
    now = datetime.now(timezone.utc) if source_id in _CLUSTER_OBSERVATION_AGE else None
    out: list[tuple[dict[str, Any], float, float]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        if source_id in _FINTRAFFIC_NOTICE_IDS:
            row = {**row, "source_read_at": station.get("source_read_at")}
        if not is_fresh_cluster_observation(source_id, row, now=now):
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


def is_actionable_water_quality_hotspot(row: dict[str, Any]) -> bool:
    """A sellable USGS point has station identity and at least one finite value."""
    if not str(row.get("station_id") or "").strip():
        return False
    for field in WATER_QUALITY_VALUE_FIELDS:
        value = row.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if math.isfinite(float(value)):
            return True
    return False


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
