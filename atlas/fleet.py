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
from .gnss_index import materialize_gnss_cells
from .map_objects import (
    is_actionable_water_quality_hotspot,
    normalize_map_point,
    normalized_hotspots,
)
from .stations import LAYER_META, STATION_CATALOG, resolve_mode

log = logging.getLogger("atlas.fleet")

InvokeFn = Callable[..., Awaitable[Optional[dict[str, Any]]]]


def upstream_evidence(output: dict[str, Any] | None) -> dict[str, Any]:
    """Keep the compact GAIA proof chain that accompanied a relayed reading."""
    if not isinstance(output, dict):
        return {}
    reading = output.get("reading") if isinstance(output.get("reading"), dict) else output
    evidence: dict[str, Any] = {}
    if isinstance(reading, dict):
        for key in ("device_id", "seq", "ts", "observed_at"):
            if reading.get(key) is not None:
                evidence[key] = reading[key]
    attestation = output.get("attestation")
    if isinstance(attestation, dict):
        evidence["attestation"] = attestation
    for key in ("receipt", "provenance_receipt", "gateway_receipt"):
        if isinstance(output.get(key), dict):
            evidence[key] = output[key]
    return evidence

# Layers whose pin lat/lon come from the reading (not a fixed catalog anchor).
EVENT_LAYERS = frozenset({
    "quake", "fire", "radiation", "jamming", "gnss", "traffic",
    "events", "spacewx", "lightning", "alerts", "argo", "iot",
    "flood", "effis", "volcano", "cyclone", "adsb", "smoke", "water_quality",
    "precipitation", "radar", "sea_ice",
    "road", "rail", "drought", "uv", "weather",
})
# Default-on LIVE event pins shown even before a fleet read. Traffic/IoT feeders are
# opt-in (GAIA_FEEDER_ENABLED) — only appear when registered in the GAIA fleet.
CATALOG_EVENT_LAYERS = frozenset({
    "quake", "fire", "radiation", "jamming", "gnss",
    "events", "spacewx", "lightning", "alerts", "argo",
    "flood", "effis", "volcano", "cyclone", "smoke", "water_quality",
    "precipitation", "radar", "sea_ice",
    "road", "rail", "drought", "uv",
})
# Cluster layers fanned into map_points / paid SKU pins. Space weather carries
# a geographic OVATION grid: every sample is an inspectable ATLAS point.
# Geomag stations remain individual sources. Argo is one commercial relay whose
# official GDAC directory fans into one stable, clickable point per active WMO.
DENSE_EVENT_LAYERS = frozenset({
    "fire", "radiation", "quake", "jamming", "gnss",
    "events", "spacewx", "lightning", "alerts", "argo", "flood", "effis", "volcano",
    "ais", "tsunami", "cyclone", "adsb", "smoke", "water_quality",
    "precipitation", "radar", "sea_ice",
    "road", "rail", "drought", "uv", "weather",
})
DENSE_PIN_PREFIXES = (
    "firms-hs-", "rad-hs-", "quake-ev-", "jam-ev-",
    "eonet-ev-", "swpc-hs-", "glm-hs-", "cap-ev-", "flood-hs-", "effis-hs-", "volc-ev-",
    "ais-ves-", "tsu-ev-", "cyc-ev-", "adsb-ac-", "smoke-poly-", "usgs-wq-site-",
    "imerg-cell-", "nexrad-site-", "sea-ice-cell-",
    "road-st-", "rail-tr-", "drought-st-",
    "uv-us-", "wx-ie-",
    "argo-wmo-",
    "gnss-station:",
    "gnss-cell:",
    "atlas-pt-",
)


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
    normalized = normalize_map_point(lat, lon)
    if normalized is not None:
        lat, lon = normalized
    # Fleet status means "registered and not administratively dropped out".
    # It does not prove that the upstream answered this ATLAS process. A point
    # becomes online only after a usable cached reading; until then it remains
    # visible/clickable as configured, without inflating the live counter.
    registered_online = (
        bool(fleet_dev.get("online", True))
        if fleet_dev
        else bool(cached.get("online", False))
    )
    online = bool(registered_online and values and cached.get("online", True))
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
        "registered": bool(fleet_dev),
        "mode": mode,
        "live": live,
        "source": str(source) if source else None,
        "site": str(fleet_dev.get("site") or cached.get("site") or ""),
        "model": str(fleet_dev.get("model") or ""),
        "values": values or {},
        "headline": cached.get("headline") or ("—" if not values else headline(meta["layer"], values)),
        "color": LAYER_META.get(meta["layer"], {}).get("color", "#88a"),
        "has_reading": bool(values),
        # Cluster parents are commercial/source objects, not an extra physical
        # point. Their observations arrive through viewport map_points.
        "cluster_parent": meta["layer"] in DENSE_EVENT_LAYERS,
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
        "parent_id": station.get("id"),
        "lat": lat,
        "lon": lon,
        "magnitude": mag,
        "depth_km": vals.get("depth_km"),
        "at": utc_now(),
        "observed_at": station.get("observed_at") or station.get("fetched_at"),
        "place": station.get("place") or "event",
        "label": station.get("label") or "Earthquake",
        "source": station.get("source"),
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


CLUSTER_META: dict[str, dict[str, Any]] = {
    "fire": {
        "prefix": "firms-hs",
        "keys": ("brightness_k", "confidence", "latitude", "longitude"),
        "provenance": (
            "observed_at", "acq_date", "acq_time_utc", "satellite",
            "instrument", "daynight", "version", "frp_mw", "scan_km", "track_km",
        ),
    },
    "radiation": {
        "prefix": "rad-hs",
        "keys": ("cpm", "latitude", "longitude"),
        "provenance": ("captured_at",),
    },
    "quake": {
        "prefix": "quake-ev",
        "keys": ("magnitude", "depth_km", "latitude", "longitude"),
    },
    "jamming": {
        "prefix": "jam-ev",
        "keys": ("severity_score", "radius_km", "latitude", "longitude"),
        "provenance": (
            "event_id", "type", "region", "status", "start_date", "end_date",
            "severity", "confidence_pct", "attribution", "url", "affected_systems",
            "affected_sectors", "sources",
        ),
    },
    "gnss": {
        "prefix": "gnss-station",
        "keys": (
            "degradation_score", "availability_pct", "latency_s", "confidence",
            "latitude", "longitude",
        ),
        "kind": "point",
        "stable_id": "station_id",
        "provenance": (
            "point_id", "station_id", "network", "name", "country", "source_status",
            "state", "claim_class", "claim_level", "cause", "source_url", "license",
            "license_url", "attribution", "modified", "measurement_basis",
        ),
    },
    "events": {
        "prefix": "eonet-ev",
        "keys": ("severity_score", "latitude", "longitude"),
        "provenance": ("event_id", "title", "category", "magnitude"),
    },
    "spacewx": {
        "prefix": "swpc-hs",
        "keys": (
            "kp_index", "aurora_pct", "solar_wind_kms", "bt_nt", "xray_flux",
            "severity_score", "latitude", "longitude",
        ),
        "provenance": ("message_type", "message_id"),
    },
    "lightning": {
        "prefix": "glm-hs",
        "keys": ("energy_fj", "latitude", "longitude"),
    },
    "alerts": {
        "prefix": "cap-ev",
        "keys": ("severity_score", "latitude", "longitude"),
        "provenance": ("event", "headline", "severity", "area", "issuer"),
    },
    "argo": {
        "prefix": "argo-wmo",
        "keys": ("latitude", "longitude"),
        "kind": "point",
        "stable_id": "wmo",
        "provenance": (
            "wmo", "observed_at", "profile_url", "source_url",
            "directory_url", "profile_path", "dac", "profiler_type",
            "institution", "date_updated",
        ),
    },
    "flood": {
        "prefix": "flood-hs",
        "keys": ("severity_score", "discharge_m3s", "latitude", "longitude"),
        "provenance": ("site", "status", "event", "headline", "severity", "area"),
    },
    "effis": {
        "prefix": "effis-hs",
        "keys": ("severity_score", "latitude", "longitude"),
        "provenance": ("area_ha", "firedate"),
    },
    "volcano": {
        "prefix": "volc-ev",
        "keys": ("severity_score", "latitude", "longitude"),
        "provenance": ("name", "alert", "color"),
    },
    "ais": {
        "prefix": "ais-ves",
        "keys": ("sog_knots", "cog_deg", "latitude", "longitude"),
        "provenance": ("mmsi", "nav_stat"),
    },
    "tsunami": {
        "prefix": "tsu-ev",
        "keys": ("severity_score", "latitude", "longitude"),
        "provenance": ("event", "headline", "severity", "area"),
    },
    "cyclone": {
        "prefix": "cyc-ev",
        "keys": ("intensity_kn", "pressure_hpa", "latitude", "longitude"),
        "provenance": ("name", "classification", "storm_id"),
    },
    "adsb": {
        "prefix": "adsb-ac",
        "keys": ("altitude_m", "speed_mps", "latitude", "longitude"),
        "stable_id": "icao",
        "provenance": ("icao", "flight"),
    },
    "smoke": {
        "prefix": "smoke-poly",
        "keys": ("severity_score", "latitude", "longitude"),
        "stable_id": "polygon_id",
        "provenance": (
            "density", "satellite", "start_time", "end_time", "geometry_type",
            "polygon_id", "geometry_digest", "vertex_count", "bbox",
            # HMS publishes one dated analysis per UTC day and the current day's
            # product does not exist for most of it. The date has to travel with the
            # polygon, or the containment brief cannot say which analysis it read.
            "product_date", "product_age_hours",
        ),
    },
    "water_quality": {
        "prefix": "usgs-wq-site",
        "keys": (
            "water_temperature_c", "ph", "dissolved_oxygen_mg_l",
            "specific_conductance_us_cm", "latitude", "longitude",
        ),
        "kind": "point",
        "stable_id": "station_id",
        "provenance": (
            "station_id", "name", "observed_at", "approval_status", "qualifier",
            "qualifiers", "available_parameters", "parameter_codes",
            "observation_metadata", "site_type", "state_name", "hydrologic_unit_code",
            "registry_id", "agency_code", "county_name", "country_name",
            "registry_revision_modified",
            "water_temperature_c_observed_at", "ph_observed_at",
            "dissolved_oxygen_mg_l_observed_at",
            "specific_conductance_us_cm_observed_at",
        ),
    },
    "precipitation": {
        "prefix": "imerg-cell",
        "keys": ("precipitation_mm_h", "latitude", "longitude"),
        "stable_id": "anchor",
        "provenance": ("anchor", "product", "observed_at"),
    },
    "radar": {
        "prefix": "nexrad-site",
        "keys": ("radar_latency_s", "reflectivity_calibration_db", "transmitter_power_w", "latitude", "longitude"),
        "stable_id": "radar_id",
        "provenance": ("radar_id", "name", "status", "operability", "vcp"),
    },
    "road": {
        "prefix": "road-st",
        "keys": ("temperature_c", "wind_mps", "latitude", "longitude"),
        "stable_id": "station_id",
        "provenance": ("station_id",),
    },
    "rail": {
        "prefix": "rail-tr",
        "keys": ("speed_kmh", "latitude", "longitude"),
        "stable_id": "train_number",
        "provenance": ("train_number",),
    },
    "drought": {
        "prefix": "drought-st",
        "keys": ("severity_score", "drought_pct", "latitude", "longitude"),
        "stable_id": "state",
        "provenance": ("state", "category", "map_date"),
    },
    "uv": {
        "prefix": "uv-us",
        "keys": ("uv_index", "latitude", "longitude"),
        "stable_id": "zip",
        "provenance": ("zip", "city", "hour_max"),
    },
    "weather": {
        "prefix": "wx-ie",
        "keys": (
            "temperature_c", "humidity_pct", "wind_mps", "rainfall_mm",
            "pressure_hpa", "latitude", "longitude",
        ),
        "kind": "point",
        "stable_id": "station",
        "provenance": ("station",),
    },
}


# A pin id carries its own provenance: ``{prefix}-{tag}-{lat*1e4}_{lon*1e4}``.
PIN_PREFIX_LAYERS: dict[str, str] = {
    str(meta["prefix"]): layer for layer, meta in CLUSTER_META.items()
}
_PIN_COORD_RE = re.compile(r"-(-?\d{1,7})_(-?\d{1,8})(?:-\d{1,4})?$")


def dense_pin_from_id(pin_id: str) -> dict[str, Any] | None:
    """Decode a coordinate-keyed map pin id back into layer, tag and position.

    Clusters roll (FIRMS re-drains daily, alerts expire) and the served-point
    index is memory-only, while a browser keeps its pins for the whole session.
    Without this, clicking a pin that is still on screen could only ever answer
    "unknown station". The id itself is enough to answer honestly.

    Returns ``None`` for ids that are not coordinate-keyed (stable-id pins such
    as ``adsb-ac-4caa5c``) or that decode to an impossible position.
    """
    text = str(pin_id or "")
    match = _PIN_COORD_RE.search(text)
    if match is None:
        return None
    lat = int(match.group(1)) / 1e4
    lon = int(match.group(2)) / 1e4
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    head = text[: match.start()]
    prefix = ""
    for candidate in PIN_PREFIX_LAYERS:
        if (head == candidate or head.startswith(candidate + "-")) and len(candidate) > len(prefix):
            prefix = candidate
    if not prefix and (head == "atlas-pt" or head.startswith("atlas-pt-")):
        prefix = "atlas-pt"  # generic geographic feed: a position without a layer
    if not prefix:
        return None
    return {
        "layer": PIN_PREFIX_LAYERS.get(prefix) or "",
        "prefix": prefix,
        "tag": head[len(prefix) + 1:],
        "lat": lat,
        "lon": lon,
    }


def expand_map_objects(
    stations: list[dict[str, Any]],
    *,
    expand: bool = True,
    include_private_geometry: bool = False,
) -> list[dict[str, Any]]:
    """Fan event ``hotspots[]`` into one map pin per detection.

    Applies to geographic cluster readings (FIRMS, Safecast, SWPC OVATION,
    alerts and other event feeds). Catalog SKUs remain Hub
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
            if isinstance(station.get("hotspots"), list):
                slim["cluster_parent"] = True
            out.append(slim)
        return out
    cluster_meta = CLUSTER_META
    out = []
    for station in stations:
        layer = str(station.get("layer") or "")
        meta = cluster_meta.get(layer)
        points = normalized_hotspots(station)
        if points is None:
            slim = {k: v for k, v in station.items() if k != "hotspots"}
            out.append(slim)
            continue
        # An explicit empty/invalid cluster is authoritative: zero map objects,
        # never a fake source/headline pin.
        if not points:
            continue
        if meta is None:
            # Future geographic array feeds automatically become clickable
            # without adding another layer-specific allowlist entry.
            meta = {"prefix": "atlas-pt", "keys": ()}
        parent_id = str(station.get("id") or f"{layer}-01")
        # Stable short tag so multiple Safecast anchors don't collide.
        tag = parent_id.replace("safecast-", "sc").replace("firms-fire-", "ff")
        tag = tag.replace("usgs-quake-", "uq").replace("cybernews-jam-", "cj")
        tag = tag.replace("eonet-", "eo").replace("swpc-", "sw").replace("glm-", "gl")
        tag = tag.replace("nws-alerts-", "na").replace("nws-flood-", "fl").replace("usgs-flood-", "fl")
        tag = tag.replace("effis-", "ef").replace("usgs-volcano-", "vo")
        tag = tag.replace("geonet-", "gn")
        tag = tag.replace("fintraffic-ais-", "fa").replace("nws-tsunami-", "ts")
        tag = tag.replace("kystverket-ais-", "kv").replace("ptwc-", "pt")
        tag = tag.replace("emsc-", "em").replace("ea-flood-", "ea")
        tag = tag.replace("nhc-cyclone-", "nh").replace("adsb-lol-", "al")
        tag = tag.replace("fintraffic-road-", "fr").replace("fintraffic-rail-", "ft")
        tag = tag.replace("usdm-", "ud").replace("geoshake-", "gs").replace("naad-", "nd")
        tag = tag.replace("pegel-", "pg").replace("metar-", "mt")
        tag = tag.replace("epa-uv-", "eu").replace("met-ie-", "mi")
        tag = re.sub(r"[^a-zA-Z0-9_-]", "", tag)[:24] or "x"
        color = station.get("color") or LAYER_META.get(layer, {}).get("color", "#888")
        prefix = str(meta["prefix"])
        keys: tuple[str, ...] = meta["keys"]
        provenance_keys: tuple[str, ...] = meta.get("provenance", ())
        expanded = 0
        seen_ids: set[str] = set()
        for i, (row, lat, lon) in enumerate(points):
            values = {k: row.get(k) for k in keys if row.get(k) is not None}
            # A registry coordinate without one of the contracted observations
            # is not a sellable water-quality point. GAIA normally filters it;
            # this second boundary prevents malformed/replayed clusters from
            # becoming authoritative-looking empty pins.
            if layer == "water_quality" and not is_actionable_water_quality_hotspot(row):
                continue
            if not keys:
                values = {
                    str(k): v
                    for k, v in row.items()
                    if k not in ("latitude", "longitude", "lat", "lon")
                    and isinstance(v, (str, int, float, bool))
                }
            values["latitude"] = lat
            values["longitude"] = lon
            values = {str(k): v for k, v in values.items() if v is not None}
            provenance = {k: row.get(k) for k in provenance_keys if row.get(k) is not None}
            private: dict[str, Any] = {}
            if include_private_geometry and layer == "smoke" and isinstance(row.get("geometry"), dict):
                private["geometry"] = row["geometry"]
                private["inventory_complete"] = station.get("inventory_complete") is True
                private["inventory_total"] = station.get("inventory_total")
                if isinstance(station.get("upstream_evidence"), dict):
                    private["upstream_evidence"] = station["upstream_evidence"]
            # Moving platforms need identity-derived ids; event feeds use the
            # coordinate so repeated viewport packets merge deterministically.
            stable_key = str(meta.get("stable_id") or "")
            stable_raw = str(row.get(stable_key) or "") if stable_key else ""
            stable = re.sub(r"[^A-Za-z0-9_-]", "", stable_raw)[:64]
            explicit_id = str(row.get("point_id") or "")
            if re.fullmatch(r"gnss-station:(?:euref|ga):[A-Z0-9]{4,9}", explicit_id):
                pin_id = explicit_id
            else:
                pin_id = (
                    f"{prefix}-{stable}"
                    if stable
                    else f"{prefix}-{tag}-{round(lat * 1e4)}_{round(lon * 1e4)}"
                )
            if pin_id in seen_ids:
                # USGS station_id is the identity contract: one Atlas point per
                # station, even if an upstream page repeats a time series row.
                if layer == "water_quality" and stable:
                    continue
                pin_id = f"{pin_id}-{i}"
            seen_ids.add(pin_id)
            # Slim pins — full catalog metadata on every FIRMS row froze snapshot
            # serialization (~100MB) and the asyncio loop.
            out.append(
                {
                    "id": pin_id,
                    "parent_id": parent_id,
                    "layer": layer,
                    "kind": str(meta.get("kind") or "event"),
                    "lat": lat,
                    "lon": lon,
                    "online": bool(station.get("online", True)),
                    "mode": station.get("mode") or "live",
                    "live": bool(station.get("live")),
                    "source": station.get("source"),
                    "values": values,
                    "color": color,
                    "has_reading": True,
                    "label": station.get("label") or parent_id,
                    "headline": headline(layer, values),
                    **provenance,
                    **private,
                }
            )
            expanded += 1
        if expanded == 0:
            slim = {k: v for k, v in station.items() if k != "hotspots"}
            out.append(slim)
    return [*out, *materialize_gnss_cells(out)]


def expand_fire_hotspots(
    stations: list[dict[str, Any]],
    *,
    expand: bool = True,
) -> list[dict[str, Any]]:
    """Backward-compatible name for :func:`expand_map_objects`."""
    return expand_map_objects(stations, expand=expand)


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
    fire_stratified: bool = False,
    fire_grid_deg: float | None = None,
    geo_bbox: tuple[float, float, float, float] | None = None,
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
            if fire_stratified:
                extra["stratified"] = True
            if fire_grid_deg is not None:
                extra["grid_deg"] = fire_grid_deg
        else:
            # Count + headline only — first packet discarded for map pins.
            extra["page_size"] = 1
    elif meta["layer"] == "water_quality" and geo_bbox is not None:
        west, south, east, north = geo_bbox
        extra.update({
            "west": west, "south": south, "east": east, "north": north,
            "limit": 10_000,
        })
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
        evidence = upstream_evidence(reading)
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
            try:
                inventory_total = int(r["inventory_total"]) if r.get("inventory_total") is not None else None
            except (TypeError, ValueError):
                inventory_total = None
            inventory_complete = r.get("inventory_complete") is True
        else:
            station_matched = 0
            inventory_total = None
            inventory_complete = False
    else:
        evidence = {}
        station_matched = 0
        inventory_total = None
        inventory_complete = False

    lat = float(meta["lat"])
    lon = float(meta["lon"])
    if meta["layer"] in EVENT_LAYERS:
        try:
            lat = float(values.get("latitude", lat))
            lon = float(values.get("longitude", lon))
        except (TypeError, ValueError):
            pass
    normalized = normalize_map_point(lat, lon)
    if normalized is not None:
        lat, lon = normalized

    station = {
        "id": device_id,
        "layer": meta["layer"],
        "label": meta["label"],
        "place": meta["place"],
        "kind": meta["kind"],
        "lat": lat,
        "lon": lon,
        # Registration means an endpoint exists, not that it answered.  Own-edge
        # feeders are deliberately empty until ingest and must not inflate the
        # online count.
        "online": bool(online and values),
        "mode": mode,
        "live": live,
        "source": str(source) if source else None,
        "site": site,
        "model": str(fleet_dev.get("model") or ""),
        "values": values,
        "headline": headline(meta["layer"], values),
        "color": LAYER_META.get(meta["layer"], {}).get("color", "#88a"),
        "has_reading": bool(values),
        "cluster_parent": meta["layer"] in DENSE_EVENT_LAYERS or hotspots is not None,
        "fetched_at": utc_now(),
    }
    if evidence:
        station["upstream_evidence"] = evidence
    if station_matched:
        station["hotspot_matched"] = int(station_matched)
    if inventory_total is not None:
        station["inventory_total"] = int(inventory_total)
        if "hotspot_count" not in station:
            station["hotspot_count"] = int(inventory_total)
    if inventory_complete:
        station["inventory_complete"] = True
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
