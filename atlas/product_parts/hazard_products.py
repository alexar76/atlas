"""Hazard products: smoke operations, fire weather and the situation brief."""

from __future__ import annotations

import math
from typing import Any

from ..geo import utc_now
from ..stations import LAYER_META


# NOAA HMS analysis area: North America (Alaska and Canada to Mexico, Central America, Caribbean).
_HMS_SOUTH, _HMS_NORTH, _HMS_WEST, _HMS_EAST = 5.0, 84.0, -170.0, -50.0


def smoke_operations(
    data: dict[str, Any],
    stations: list[dict[str, Any]],
    air_reading: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Exact asset containment in HMS polygons, fused with colocated PM/AQI."""
    try:
        lat, lon = float(data.get("lat")), float(data.get("lon"))
    except (TypeError, ValueError):
        return {
            "ok": False,
            "capability_id": "atlas.smoke.operations@v1",
            "refuse_reason": "lat and lon are required",
        }
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return {
            "ok": False,
            "capability_id": "atlas.smoke.operations@v1",
            "refuse_reason": "lat/lon outside WGS84 bounds",
            "query": {"lat": lat, "lon": lon},
        }
    if not (products._HMS_SOUTH <= lat <= products._HMS_NORTH and products._HMS_WEST <= lon <= products._HMS_EAST):
        # HMS analyses North America only. Elsewhere "inside none of the polygons" is not
        # evidence of clean air, so containment is refused instead of reported.
        return {
            "ok": False,
            "capability_id": "atlas.smoke.operations@v1",
            "refuse_reason": "outside the NOAA HMS analysis area (North America); smoke containment cannot be stated here",
            "query": {"lat": lat, "lon": lon},
        }
    asset_id = str(data.get("asset_id") or "").strip()[:160] or None
    query = {"lat": lat, "lon": lon, "asset_id": asset_id}

    polygons = [
        station for station in stations
        if isinstance(station, dict)
        and station.get("layer") == "smoke"
        and station.get("live")
        and isinstance(station.get("geometry"), dict)
    ]
    totals = {
        int(station["inventory_total"])
        for station in polygons
        if isinstance(station.get("inventory_total"), int)
    }
    unique_ids = {str(station.get("polygon_id") or station.get("id") or "") for station in polygons}
    complete = bool(polygons) and all(station.get("inventory_complete") is True for station in polygons)
    inventory_total = max(totals) if totals else 0
    if not complete or inventory_total < 1 or len(unique_ids) < inventory_total:
        return {
            "ok": False,
            "capability_id": "atlas.smoke.operations@v1",
            "refuse_reason": "complete LIVE HMS polygon inventory unavailable; containment would be unsafe",
            "query": query,
        }

    if any(not products.smoke_geometry_evaluable(station.get("geometry")) for station in polygons):
        return {
            "ok": False,
            "capability_id": "atlas.smoke.operations@v1",
            "refuse_reason": (
                "at least one HMS polygon geometry could not be evaluated; "
                "containment cannot be proven for the whole inventory"
            ),
            "query": query,
        }

    air = air_reading if isinstance(air_reading, dict) else {}
    air_values = air.get("values") if isinstance(air.get("values"), dict) else {}
    air_fields = ("pm2_5_ugm3", "us_aqi", "european_aqi", "air_quality_index")
    if not air.get("live") or not any(isinstance(air_values.get(key), (int, float)) for key in air_fields):
        return {
            "ok": False,
            "capability_id": "atlas.smoke.operations@v1",
            "refuse_reason": "colocated LIVE PM2.5/AQI evidence unavailable; smoke-only brief refused",
            "query": query,
        }

    matched = [station for station in polygons if products.point_in_smoke_geometry(lat, lon, station["geometry"])]
    matched.sort(key=lambda station: products._num_value(station, "severity_score"), reverse=True)
    smoke_evidence = []
    for station in matched:
        smoke_evidence.append({
            "polygon_id": station.get("polygon_id") or station.get("id"),
            "density": station.get("density"),
            "severity_score": products._num_value(station, "severity_score"),
            "satellite": station.get("satellite"),
            "start_time": station.get("start_time"),
            "end_time": station.get("end_time"),
            "centroid": {"lat": station.get("lat"), "lon": station.get("lon")},
            "bbox": station.get("bbox"),
            "vertex_count": station.get("vertex_count"),
            "geometry_digest": station.get("geometry_digest"),
            "geometry": station.get("geometry"),
            "source": station.get("source"),
            "gaia_attestation": (station.get("upstream_evidence") or {}).get("attestation"),
        })

    pm25 = float(air_values["pm2_5_ugm3"]) if isinstance(air_values.get("pm2_5_ugm3"), (int, float)) else None
    aqi_values = [
        float(air_values[key]) for key in ("us_aqi", "european_aqi", "air_quality_index")
        if isinstance(air_values.get(key), (int, float))
    ]
    max_aqi = max(aqi_values) if aqi_values else None
    inside = bool(matched)
    worst_density = str((matched[0] if matched else {}).get("density") or "none")
    if inside and (worst_density == "heavy" or (pm25 is not None and pm25 >= 35.5) or (max_aqi is not None and max_aqi >= 101)):
        status = "action"
    elif inside or (pm25 is not None and pm25 >= 35.5) or (max_aqi is not None and max_aqi >= 101):
        status = "elevated"
    elif (pm25 is not None and pm25 >= 12.0) or (max_aqi is not None and max_aqi >= 51):
        status = "watch"
    else:
        status = "routine"

    # HMS writes one dated product per UTC day, and the current day's does not exist
    # until the first daytime analysis — so the brief must name the analysis it read
    # rather than assert "current". Dates are per-polygon; disagreement means the
    # inventory spans two products and the newest is the honest label.
    product_dates = sorted({
        str(station.get("product_date")) for station in polygons
        if str(station.get("product_date") or "").strip()
    })
    analysis_date = product_dates[-1] if product_dates else None
    analysis_ages = [
        float(station["product_age_hours"]) for station in polygons
        if isinstance(station.get("product_age_hours"), (int, float))
    ]
    analysis_age_hours = round(min(analysis_ages), 2) if analysis_ages else None
    dated = f"{analysis_date} HMS" if analysis_date else "current HMS"

    drivers = [
        f"asset is inside {len(matched)} of {inventory_total} {dated} polygon(s)"
        if inside
        else f"asset is outside all {inventory_total} {dated} polygon(s)",
        f"PM2.5 at asset coordinate: {pm25:.1f} µg/m³" if pm25 is not None else "PM2.5 unavailable; AQI supplied",
    ]
    if max_aqi is not None:
        drivers.append(f"maximum supplied AQI: {max_aqi:.0f}")
    if analysis_date:
        age_note = (
            f" ({analysis_age_hours:.1f} h since that UTC day began)"
            if analysis_age_hours is not None else ""
        )
        drivers.append(f"HMS analysis product date: {analysis_date}{age_note}")
    if len(product_dates) > 1:
        drivers.append(
            "inventory spans more than one HMS product date: " + ", ".join(product_dates)
        )
    actions = ["Recheck on the next HMS analysis cycle and retain this signed receipt."]
    if inside:
        actions.insert(0, "Review outdoor work, filtration/HVAC posture, and worker exposure controls.")
    if status in {"action", "elevated"}:
        actions.append("Corroborate with the nearest regulatory ground monitor before health or evacuation decisions.")

    payload = {
        "ok": True,
        "capability_id": "atlas.smoke.operations@v1",
        "sku": "atlas.smoke.operations@v1",
        "generated_at": utc_now(),
        "query": query,
        "inside_smoke": inside,
        "operational_status": status,
        "summary": (
            f"{asset_id or 'Asset'} at {lat:.4f},{lon:.4f} is "
            + (
                f"inside {len(matched)} of {inventory_total} {dated} smoke polygon(s), "
                f"worst covering density {worst_density}"
                if inside
                else f"outside all {inventory_total} {dated} smoke polygon(s)"
            )
            + (
                f"; PM2.5 {pm25:.1f} µg/m³ at the same coordinate"
                if pm25 is not None
                else "; PM2.5 unavailable, AQI only"
            )
            + f"; operational status {status}."
        ),
        "drivers": drivers,
        "recommended_actions": actions,
        "smoke": smoke_evidence,
        "smoke_polygon_count": len(smoke_evidence),
        "hms_inventory_total": inventory_total,
        "hms_inventory_complete": True,
        "hms_analysis_date": analysis_date,
        "hms_analysis_age_hours": analysis_age_hours,
        "air_quality": {
            "kind": "modeled_coordinate",
            "lat": lat,
            "lon": lon,
            "values": {key: air_values.get(key) for key in air_fields if air_values.get(key) is not None},
            "units": air.get("units") or {},
            "observed_at": air.get("observed_at"),
            "source": air.get("source"),
            "attribution": air.get("attribution") or "Open-Meteo.com",
            "gaia_attestation": (air.get("upstream_evidence") or {}).get("attestation"),
        },
        "limitations": [
            "NOAA HMS density is qualitative and cloud/imagery limited; it is not measured PM2.5.",
            (
                f"Containment was decided against the {analysis_date} HMS analysis product, "
                "not a live satellite pass; HMS publishes one dated product per UTC day."
                if analysis_date else
                "The HMS product date was not supplied with this inventory."
            ),
            "Open-Meteo air quality is modeled grid data at the coordinate, not an on-site regulatory monitor.",
            "This evidence brief is for operational screening, not a medical, evacuation, or emergency order.",
        ],
        "attribution": [
            "NOAA/NESDIS Hazard Mapping System (HMS)",
            "Air-quality data by Open-Meteo.com (CC BY 4.0)",
        ],
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.smoke.operations@v1")
    products.remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = products._receipt_links(payload["receipt"])
    return payload


def fire_weather(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.fire.weather@v1`` — FIRMS and/or EFFIS + bounded nearby weather."""
    bbox = products._parse_bbox(data)
    if bbox is None:
        # Default: CONUS-ish window is too opinionated — require bbox for honesty.
        return {
            "ok": False,
            "capability_id": "atlas.fire.weather@v1",
            "refuse_reason": "west/south/east/north bbox required",
        }
    west, south, east, north = bbox
    try:
        limit = int(data.get("limit") or 24)
    except (TypeError, ValueError):
        limit = 24
    limit = max(1, min(limit, 80))
    include_air = bool(data.get("include_air"))
    raw_max_weather_km = data.get("max_weather_km")
    try:
        max_weather_km = float(250.0 if raw_max_weather_km is None else raw_max_weather_km)
    except (TypeError, ValueError):
        max_weather_km = 250.0
    max_weather_km = max(1.0, min(max_weather_km, 1000.0))
    raw_max_air_km = data.get("max_air_km")
    try:
        max_air_km = float(max_weather_km if raw_max_air_km is None else raw_max_air_km)
    except (TypeError, ValueError):
        max_air_km = max_weather_km
    max_air_km = max(1.0, min(max_air_km, 1000.0))

    live_fire = products._live_valued(products._stations_in_bbox(
        stations, west=west, south=south, east=east, north=north, layers={"fire"}
    ))
    live_effis = products._live_valued(products._stations_in_bbox(
        stations, west=west, south=south, east=east, north=north, layers={"effis"}
    ))
    if not live_fire and not live_effis:
        return {
            "ok": False,
            "capability_id": "atlas.fire.weather@v1",
            "refuse_reason": "no LIVE fire or EFFIS readings in bbox (sparse ≠ covered)",
            "bbox": {"west": west, "south": south, "east": east, "north": north},
            "attribution": (
                "NASA FIRMS and/or Copernicus EFFIS — cite the source that is present"
            ),
        }

    live_fire.sort(key=lambda s: products._num_value(s, "brightness_k"), reverse=True)
    live_effis.sort(
        key=lambda s: (products._num_value(s, "area_ha"), products._num_value(s, "severity_score")),
        reverse=True,
    )
    hotspots = [products._citation(s) for s in live_fire[:limit]]
    effis_fires = [products._citation(s) for s in live_effis[:limit]]
    anchor = live_fire[0] if live_fire else live_effis[0]
    try:
        alat, alon = float(anchor["lat"]), float(anchor["lon"])
    except (TypeError, ValueError, KeyError):
        return {
            "ok": False,
            "capability_id": "atlas.fire.weather@v1",
            "refuse_reason": "fire pin missing coordinates",
        }

    weather_candidates = [
        s
        for s in stations
        if isinstance(s, dict)
        and s.get("layer") == "weather"
        and s.get("live")
        and (s.get("values") or s.get("has_reading"))
    ]
    nearest_wx: dict[str, Any] | None = None
    nearest_km: float | None = None
    for s in weather_candidates:
        try:
            lat, lon = float(s["lat"]), float(s["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        d = products._haversine_km(alat, alon, lat, lon)
        if nearest_km is None or d < nearest_km:
            nearest_km = d
            nearest_wx = s

    nearest_wx_candidate = nearest_wx
    nearest_wx_candidate_km = nearest_km
    if nearest_km is None or nearest_km > max_weather_km:
        nearest_wx = None

    nearest_air: dict[str, Any] | None = None
    air_km: float | None = None
    if include_air:
        for s in stations:
            if not isinstance(s, dict) or s.get("layer") != "air":
                continue
            if not (s.get("live") and (s.get("values") or s.get("has_reading"))):
                continue
            try:
                lat, lon = float(s["lat"]), float(s["lon"])
            except (TypeError, ValueError, KeyError):
                continue
            d = products._haversine_km(alat, alon, lat, lon)
            if air_km is None or d < air_km:
                air_km = d
                nearest_air = s
    nearest_air_candidate = nearest_air
    nearest_air_candidate_km = air_km
    if air_km is None or air_km > max_air_km:
        nearest_air = None

    wx_vals = (nearest_wx or {}).get("values") if nearest_wx else {}
    wx_vals = wx_vals if isinstance(wx_vals, dict) else {}
    wind = wx_vals.get("wind_mps")
    humidity = wx_vals.get("humidity_pct")
    temp = wx_vals.get("temperature_c")

    drivers: list[str] = []
    if live_fire:
        drivers.append(
            f"{len(hotspots)} LIVE FIRMS hotspot(s) in bbox (of {len(live_fire)} total)"
        )
    if live_effis:
        drivers.append(
            f"{len(effis_fires)} LIVE EFFIS fire(s) in bbox (of {len(live_effis)} total)"
        )
    if nearest_wx and nearest_km is not None:
        drivers.append(
            f"nearest LIVE weather {nearest_wx.get('id')} @ {nearest_km:.0f} km "
            f"(wind={wind}, humidity={humidity}, temp_c={temp})"
        )
    else:
        if nearest_wx_candidate and nearest_wx_candidate_km is not None:
            drivers.append(
                f"nearest LIVE weather is {nearest_wx_candidate_km:.0f} km away, "
                f"beyond max_weather_km={max_weather_km:.0f}; context excluded"
            )
        else:
            drivers.append("no LIVE weather pin available for context")
    if include_air and nearest_air is None:
        if nearest_air_candidate and nearest_air_candidate_km is not None:
            drivers.append(
                f"nearest LIVE air pin is {nearest_air_candidate_km:.0f} km away, "
                f"beyond max_air_km={max_air_km:.0f}; context excluded"
            )
        else:
            drivers.append("no LIVE air pin available for optional context")

    top_b = products._num_value(live_fire[0], "brightness_k") if live_fire else 0.0
    top_ha = products._num_value(live_effis[0], "area_ha") if live_effis else 0.0
    bits = []
    if live_fire:
        bits.append(f"{len(live_fire)} LIVE FIRMS detection(s); brightest {top_b:.0f} K")
    if live_effis:
        bits.append(f"{len(live_effis)} LIVE EFFIS polygon(s); largest {top_ha:.0f} ha")
    attr_parts = []
    if live_fire:
        attr_parts.append("NASA FIRMS VIIRS — cite NASA FIRMS / disclaimer")
    if live_effis:
        attr_parts.append("Copernicus EFFIS / EMS — CC BY 4.0, cite Copernicus EMS / JRC")

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.fire.weather@v1",
        "sku": "atlas.fire.weather@v1",
        "generated_at": utc_now(),
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "artifact_type": "evidence_snapshot",
        "summary": (
            "Fire + weather evidence snapshot: "
            + "; ".join(bits)
            + f" at {alat:.2f},{alon:.2f}. "
            "This is source-attributed context, not a fire perimeter, forecast, "
            "risk rating, or evacuation order. FIRMS and EFFIS are different products "
            "and are listed separately."
        ),
        "drivers": drivers,
        "evidence": {
            "live_fire_detection_count": len(live_fire),
            "returned_detection_count": len(hotspots),
            "live_effis_count": len(live_effis),
            "returned_effis_count": len(effis_fires),
            "nearby_weather_available": bool(nearest_wx),
        },
        "limitations": [
            "FIRMS reports satellite thermal anomalies; detections are not confirmed incident perimeters.",
            "EFFIS current-fire polygons are Copernicus EMS / JRC products (CC BY 4.0), not FIRMS pixels.",
            "Weather and optional air context are included only within their declared distance bounds.",
            "Independent operational validation is required.",
        ],
        "hotspots": hotspots,
        "hotspot_count": len(live_fire),
        "effis_fires": effis_fires,
        "effis_count": len(live_effis),
        "weather": products._citation(nearest_wx) if nearest_wx else None,
        "weather_distance_km": round(nearest_km, 1) if nearest_wx and nearest_km is not None else None,
        "max_weather_km": max_weather_km,
        "nearest_weather_candidate": (
            products._citation(nearest_wx_candidate) if nearest_wx_candidate else None
        ),
        "nearest_weather_candidate_distance_km": (
            round(nearest_wx_candidate_km, 1)
            if nearest_wx_candidate_km is not None else None
        ),
        "air": products._citation(nearest_air) if nearest_air else None,
        "air_distance_km": round(air_km, 1) if nearest_air and air_km is not None else None,
        "max_air_km": max_air_km,
        "nearest_air_candidate": (
            products._citation(nearest_air_candidate) if nearest_air_candidate else None
        ),
        "nearest_air_candidate_distance_km": (
            round(nearest_air_candidate_km, 1)
            if nearest_air_candidate_km is not None else None
        ),
        "attribution": " · ".join(attr_parts),
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.fire.weather@v1")
    return payload


def situation_brief(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.situation.brief@v1`` — multi-layer scored brief with citations."""
    bbox = products._parse_bbox(data)
    if bbox is None:
        return {
            "ok": False,
            "capability_id": "atlas.situation.brief@v1",
            "refuse_reason": "west/south/east/north bbox required",
        }
    west, south, east, north = bbox
    preset_key = str(data.get("preset") or "").strip().lower() or None
    if preset_key is not None and preset_key not in products.SITUATION_BRIEF_PRESETS:
        # A misspelled desk must not silently fall through to the 21-layer default:
        # the buyer would be billed for an answer about a scope they did not ask for.
        return {
            "ok": False,
            "capability_id": "atlas.situation.brief@v1",
            "refuse_reason": (
                "unknown preset: " + preset_key + "; known presets are "
                + ", ".join(sorted(products.SITUATION_BRIEF_PRESETS))
            ),
            "bbox": {"west": west, "south": south, "east": east, "north": north},
        }
    preset = products.SITUATION_BRIEF_PRESETS.get(preset_key) if preset_key else None
    layers = products._normalize_layer_list(data.get("layers"))
    # An explicit layer list wins, but then the preset's scope sentence no longer
    # describes the answer — so the preset is reported as overridden rather than
    # echoed as if it had shaped the brief.
    preset_overridden = bool(layers) and preset is not None
    if preset_overridden:
        preset = None
    if not layers and preset is not None:
        layers = [k for k in preset["layers"] if k in LAYER_META]
    if not layers:
        # P0/P1 hazard layers that are bbox-local. Not spacewx/geomag (planetary
        # pin) or argo (ocean float) — those are not a site brief.
        layers = [k for k in products.SITUATION_BRIEF_DEFAULT_LAYERS if k in LAYER_META]
    try:
        max_citations = int(data.get("max_citations") or 24)
    except (TypeError, ValueError):
        max_citations = 24
    max_citations = max(4, min(max_citations, 48))

    layer_set = set(layers)
    inside = products._stations_in_bbox(
        stations, west=west, south=south, east=east, north=north, layers=layer_set
    )
    with_reading = [
        s for s in inside if s.get("has_reading") or (isinstance(s.get("values"), dict) and s.get("values"))
    ]
    live = [s for s in with_reading if s.get("live")]

    coverage: dict[str, dict[str, int]] = {}
    for layer in layers:
        subset = [s for s in inside if s.get("layer") == layer]
        coverage[layer] = {
            "pins": len(subset),
            "with_reading": sum(
                1
                for s in subset
                if s.get("has_reading") or (isinstance(s.get("values"), dict) and s.get("values"))
            ),
            "live": sum(1 for s in subset if s.get("live")),
        }

    if not live:
        return {
            "ok": False,
            "capability_id": "atlas.situation.brief@v1",
            "refuse_reason": "no LIVE readings with values in bbox for requested layers",
            "bbox": {"west": west, "south": south, "east": east, "north": north},
            "layers": layers,
            # A desk that gets nothing must still be told which desk it asked for:
            # this refusal is the coverage answer, and it is not billed.
            "preset": preset_key if preset is not None else None,
            "preset_scope": preset["scope"] if preset is not None else None,
            "coverage": coverage,
        }

    # Rank citations: LIVE + hazard layers first, then brightness/magnitude/area.
    _HAZARD = {
        "fire", "effis", "flood", "lightning", "alerts", "events", "volcano",
        "quake", "jamming", "radiation", "traffic",
    }

    def _rank(s: dict[str, Any]) -> tuple[int, int, float, str]:
        layer = str(s.get("layer") or "")
        live_b = 1 if s.get("live") else 0
        haz = 1 if layer in _HAZARD else 0
        vals = s.get("values") if isinstance(s.get("values"), dict) else {}
        weight = 0.0
        for key in (
            "brightness_k", "magnitude", "severity_score", "cpm", "wind_mps",
            "area_ha", "energy_fj",
        ):
            try:
                raw = vals.get(key)
                if raw is not None:
                    weight = max(weight, float(raw))
            except (TypeError, ValueError):
                pass
        return (-live_b, -haz, -weight, str(s.get("id") or ""))

    ranked = sorted(with_reading, key=_rank)
    citations = [products._citation(s) for s in ranked[:max_citations]]

    drivers: list[str] = []
    score = 35
    live_layers = {str(s.get("layer")) for s in live}
    score += min(25, len(live_layers) * 6)
    drivers.append(f"{len(live)} LIVE reading(s) across {len(live_layers)} layer(s)")

    for layer in (
        "fire", "effis", "flood", "lightning", "alerts", "events", "volcano",
        "quake", "jamming", "radiation",
    ):
        n = coverage.get(layer, {}).get("live", 0)
        if n:
            score += min(12, 4 + n)
            drivers.append(f"{layer}: {n} LIVE pin(s) in bbox")

    # Cross-layer links (explicit, evidence-bound — not forecasts).
    if coverage.get("fire", {}).get("live") and coverage.get("weather", {}).get("live"):
        drivers.append("fire + weather both LIVE in bbox — fused wildfire context available")
        score += 5
    if coverage.get("effis", {}).get("live") and coverage.get("weather", {}).get("live"):
        drivers.append("EFFIS + weather both LIVE in bbox — Copernicus fire context available")
        score += 5
    if coverage.get("fire", {}).get("live") and coverage.get("effis", {}).get("live"):
        drivers.append("FIRMS + EFFIS both LIVE — two independent fire products, listed separately")
        score += 3
    if coverage.get("flood", {}).get("live") and coverage.get("river", {}).get("live"):
        drivers.append("flood alerts + river gauges both LIVE — hydrology pairing (not a flood model)")
        score += 4
    if coverage.get("lightning", {}).get("live") and coverage.get("fire", {}).get("live"):
        drivers.append(
            "lightning + fire both LIVE in bbox — co-presence only, not an ignition claim"
        )
        score += 3
    if coverage.get("quake", {}).get("live") and (
        coverage.get("tide", {}).get("live") or coverage.get("marine", {}).get("live")
    ):
        drivers.append("quake + coastal/marine LIVE — coastal situational pairing")
        score += 4
    if coverage.get("jamming", {}).get("live") and coverage.get("traffic", {}).get("live"):
        drivers.append("GNSS jamming + traffic LIVE — interference vs mobility pairing")
        score += 4

    sim_only = [s for s in with_reading if not s.get("live")]
    if sim_only and not live:
        pass  # already refused
    elif sim_only:
        drivers.append(f"{len(sim_only)} SIM pin(s) present — not used for score")

    score = max(0, min(100, score))

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.situation.brief@v1",
        "sku": "atlas.situation.brief@v1",
        "generated_at": utc_now(),
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "layers": layers,
        "preset": preset_key if preset is not None else None,
        "preset_scope": preset["scope"] if preset is not None else None,
        "preset_overridden": preset_key if preset_overridden else None,
        "score": score,
        "summary": (
            (f"{preset_key} brief" if preset is not None else "Situation brief")
            + f": score {score}/100 from {len(live)} LIVE citation(s) "
            + f"in bbox across {len(live_layers)} layer(s). Not a forecast or insurance trigger."
        ),
        "drivers": drivers,
        "coverage": coverage,
        "citations": citations,
        "citation_count": len(citations),
        "live_count": len(live),
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.situation.brief@v1")
    return payload


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
