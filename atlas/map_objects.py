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
    "bfs-odl-01": (timedelta(0), timedelta(hours=2)),
    "aoml-drifters-01": (timedelta(0), timedelta(hours=6)),
}
TORONTO_ROADS_ID = "toronto-road-restrictions-01"
TORONTO_BIKE_ID = "toronto-bikeshare-01"
UKPN_ID = "ukpn-live-faults-01"
REGIONAL_CLUSTER_IDS = frozenset({"ndw-ev-charging-01", "dea-hotspots-01"})
_NEW_COMPLETE_IDS = frozenset({"bc-wildfire-01", "geonet-volcano-01", "noaa-spc-storm-reports-01", "noaa-vaac-ash-01"})
WAVE_EXPIRING_CLUSTERS = REGIONAL_CLUSTER_IDS | _NEW_COMPLETE_IDS
COMPLETE_CLUSTER_IDS = _NEW_COMPLETE_IDS | {TORONTO_ROADS_ID, TORONTO_BIKE_ID, UKPN_ID, "aoml-drifters-01"}
_POSITION_TTL_IDS = {"entur-rail-vyg-01", TORONTO_BIKE_ID}
_TIMED_CLUSTER_IDS = {"bfs-odl-01", "aoml-drifters-01", TORONTO_ROADS_ID} | _POSITION_TTL_IDS
_DRAP_TTL_S = 900
_OBSERVATION_TTL_S = {
    "ea-tide-": 7200, "fmi-marine-": 7200, "snotel-": 21600,
    "geonet-coastal-": 300, "chmi-river-": 7200, "smhi-ocean-": 10800,
    "bfs-odl-st-": 7200,
    "arso-river-": 7200, "kartverket-tide-": 7200, "noaa-airgap-": 1080,
    "aoml-drifter-": 21600,
    "ch-pollen-": 7200, "ie-buoy-": 7200, "au-wave-": 7200,
}
_FINTRAFFIC_NOTICE_IDS = {"fintraffic-road-announcements-01", "fintraffic-roadworks-01"}
NDW_NOTICE_IDS = frozenset({"ndw-road-srti-01", "ndw-road-closures-01"})
_SNAPSHOT_TTLS_S = {
    **dict.fromkeys(NDW_NOTICE_IDS, 300),
    TORONTO_ROADS_ID: 900, TORONTO_BIKE_ID: 300, UKPN_ID: 1800,
}
_SNAPSHOT_FIELDS = ("source_published_at", "source_expires_at")


def _timestamp(raw: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else None


def _position_expiry(row: dict[str, Any]) -> datetime | None:
    observed, expires = _timestamp(row.get("observed_at")), _timestamp(row.get("valid_until"))
    return expires if observed and expires and observed < expires <= observed + timedelta(minutes=5) else None


def _snapshot_expiry(source_id: str, row: dict[str, Any]) -> datetime | None:
    published, expires = (_timestamp(row.get(key)) for key in _SNAPSHOT_FIELDS)
    ttl = timedelta(seconds=_SNAPSHOT_TTLS_S[source_id])
    return expires if published and expires and published < expires <= published + ttl else None


def is_fresh_cluster_observation(
    parent_id: str, row: dict[str, Any], *, now: datetime | None = None,
) -> bool:
    """Apply source-time limits for clusters whose upstream samples can age out."""
    if parent_id in WAVE_EXPIRING_CLUSTERS:
        current = now if now is not None else datetime.now(timezone.utc)
        end = _timestamp(row.get("valid_until"))
        observed = _timestamp(row.get("observed_at"))
        return bool(end and current < end and (observed is None or observed <= current))
    if parent_id in _FINTRAFFIC_NOTICE_IDS or parent_id in NDW_NOTICE_IDS or parent_id == TORONTO_ROADS_ID:
        current = now if now is not None else datetime.now(timezone.utc)
        start, end = _timestamp(row.get("valid_from")), _timestamp(row.get("valid_until"))
        if (not start or start > current or (parent_id == TORONTO_ROADS_ID and not end)
                or (row.get("valid_until") and (not end or end <= current))):
            return False
        if parent_id in _SNAPSHOT_TTLS_S:
            published = _timestamp(row.get("source_published_at"))
            expires = _snapshot_expiry(parent_id, row)
            return bool(published and expires and published <= current < expires)
        read_at = _timestamp(row.get("source_read_at"))
        return bool(read_at and current - timedelta(minutes=30) <= read_at <= current + timedelta(minutes=2))
    if parent_id == "awc-gairmet-01":
        current = now if now is not None else datetime.now(timezone.utc)
        issued, valid = _timestamp(row.get("issue_at")), _timestamp(row.get("valid_at"))
        return bool(issued and valid and current - timedelta(hours=7) <= issued <= current
                    and current <= valid <= current + timedelta(hours=3))
    if parent_id in _POSITION_TTL_IDS:
        current = now if now is not None else datetime.now(timezone.utc)
        observed, expires = _timestamp(row.get("observed_at")), _position_expiry(row)
        return bool(observed and expires and observed <= current < expires)
    if parent_id == UKPN_ID:
        current = now if now is not None else datetime.now(timezone.utc)
        published = _timestamp(row.get("source_published_at"))
        expires = _snapshot_expiry(parent_id, row)
        return bool(published and expires and published <= current < expires)
    if parent_id == "swpc-drap-01":
        current = now if now is not None else datetime.now(timezone.utc)
        try:
            stamp = float(row["forecast_valid_unix"])
        except (KeyError, TypeError, ValueError):
            return False
        return 0 <= current.timestamp() - stamp < _DRAP_TTL_S
    age_range = _CLUSTER_OBSERVATION_AGE.get(parent_id)
    if age_range is None:
        return True
    observed = _timestamp(row.get("observed_at"))
    if observed is None:
        return False
    age = (now if now is not None else datetime.now(timezone.utc)) - observed
    return age_range[0] <= age < age_range[1]


def source_cluster_next_expiry(station: dict[str, Any], *, now: float) -> float | None:
    """Invalidate memoized layer counts when the next cluster member ages out."""
    device_id = str(station.get("id") or "")
    rows = station.get("hotspots")
    if device_id not in (_TIMED_CLUSTER_IDS | WAVE_EXPIRING_CLUSTERS) or not isinstance(rows, list):
        return None
    nearest = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if device_id in _POSITION_TTL_IDS:
            expires = _position_expiry(row)
        elif device_id == TORONTO_ROADS_ID or device_id in WAVE_EXPIRING_CLUSTERS:
            expires = _timestamp(row.get("valid_until"))
        else:
            observed = _timestamp(row.get("observed_at"))
            expires = observed + _CLUSTER_OBSERVATION_AGE[device_id][1] if observed else None
        if expires:
            stamp = expires.timestamp()
            if stamp > now and (nearest is None or stamp < nearest):
                nearest = stamp
    return nearest


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
    snapshot_id = str(station.get("parent_id") or device_id)
    try:
        obs_ttl = next((age for prefix, age in _OBSERVATION_TTL_S.items() if device_id.startswith(prefix)), None)
        if device_id == "aoml-drifters-01" and "observation_unix" in values:
            expiry = float(values["observation_unix"]) + 21600
        elif obs_ttl is not None or device_id == "bfs-odl-01":
            expiry = float(values["observation_unix"]) + (obs_ttl or 7200)
        elif device_id.startswith("eccc-smoke-"):
            run = float(values["forecast_run_unix"])
            valid = float(values["forecast_valid_unix"])
            if not math.isfinite(run) or not math.isfinite(valid) or not 0 <= valid - run <= 72 * 3600:
                return 0.0
            expiry = min(run + 18 * 3600, valid)
        elif device_id == "swpc-drap-01" or device_id.startswith("drap-cell-"):
            expiry = float(values["forecast_valid_unix"]) + _DRAP_TTL_S
        elif device_id.startswith(("entur-tr-", "toronto-bike-st-")):
            expires = _position_expiry(station)
            expiry = expires.timestamp() if expires else 0.0
        elif device_id == "entur-rail-vyg-01" and isinstance(station.get("hotspots"), list):
            rows = station["hotspots"]
            if not rows:  # An explicit zero-position publication is a valid inventory.
                return None
            expiry = max((end.timestamp() for row in rows if isinstance(row, dict)
                          and (end := _position_expiry(row)) is not None), default=0.0)
        elif device_id.startswith("nwps-"):
            expiry = min(
                float(values["forecast_issued_unix"]) + 24 * 3600,
                float(values["forecast_valid_unix"]),
            )
        elif snapshot_id in WAVE_EXPIRING_CLUSTERS and device_id != snapshot_id:
            end = _timestamp(station.get("valid_until"))
            expiry = end.timestamp() if end else 0.0
        elif snapshot_id in WAVE_EXPIRING_CLUSTERS:
            end = values.get("source_expires_unix")
            if end is None and "snapshot_unix" in values:
                end = float(values["snapshot_unix"]) + 900
            if end is None:
                return None
            expiry = float(end)
        elif snapshot_id in _SNAPSHOT_TTLS_S:
            expires = _snapshot_expiry(snapshot_id, station)
            end = _timestamp(station.get("valid_until")) if snapshot_id == TORONTO_ROADS_ID else None
            if not expires:
                return 0.0
            expiry = min(expires, end).timestamp() if end else expires.timestamp()
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
    if (station.get("id") in _SNAPSHOT_TTLS_S or station.get("id") in WAVE_EXPIRING_CLUSTERS) and "hotspots" in station:
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
    source_has_age = (source_id in _CLUSTER_OBSERVATION_AGE or source_id in _TIMED_CLUSTER_IDS
                      or source_id in _SNAPSHOT_TTLS_S or source_id in WAVE_EXPIRING_CLUSTERS
                      or source_id == "swpc-drap-01")
    now = datetime.now(timezone.utc) if source_has_age else None
    out: list[tuple[dict[str, Any], float, float]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        if source_id in _FINTRAFFIC_NOTICE_IDS:
            row = {**row, "source_read_at": station.get("source_read_at")}
        elif source_id in {TORONTO_ROADS_ID, UKPN_ID}:
            row = {**{key: station.get(key) for key in _SNAPSHOT_FIELDS}, **row}
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
            if source_id == "swpc-drap-01":
                frequency = row.get("drap_frequency_mhz")
                if (not isinstance(frequency, (int, float)) or isinstance(frequency, bool)
                        or not 0 <= frequency <= 100
                        or point[0] % 2 != 1 or point[1] % 4 != 2):
                    continue
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
