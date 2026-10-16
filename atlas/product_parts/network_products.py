"""Route and network products: route integrity and observability attestation."""

from __future__ import annotations

from typing import Any

from ..geo import utc_now


# ── atlas.route.integrity@v1 ──────────────────────────────────────────────────
#
# `atlas.gnss.degradation.read@v1` already accepts a route and almost nobody used it
# (one observation in thirty days), because a degradation field on its own is not a
# decision. This composes it with the reported-interference registry, the platform
# feeds that happen to be flying or sailing the same corridor, and the hazard alerts
# along it — per segment, with every honest bound carried through.
#
# What it is NOT is the important half: the station layer is an inventory plus
# reported zones, not live integrity, and nothing here is proof of jamming.


_ROUTE_HAZARD_LAYERS = ("alerts", "flood", "cyclone", "tsunami", "quake", "fire", "effis")


_ROUTE_PLATFORM_LAYERS = ("ais", "adsb")


def route_integrity(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.route.integrity@v1`` — per-segment GNSS, interference and hazard brief."""
    route = products._parse_route(data.get("route"))
    if route is None:
        return {
            "ok": False,
            "capability_id": "atlas.route.integrity@v1",
            "refuse_reason": "route must be 2–500 valid [lon, lat] pairs",
        }
    route_id = str(data.get("route_id") or "").strip()[:160] or None
    try:
        corridor_km = float(data.get("corridor_km") if data.get("corridor_km") is not None else 25.0)
    except (TypeError, ValueError):
        corridor_km = 25.0
    corridor_km = max(1.0, min(corridor_km, 200.0))
    length_km = round(products._route_length_km(route), 2)
    query = {
        "route_id": route_id,
        "corridor_km": corridor_km,
        "waypoints": len(route),
        "route_length_km": length_km,
    }

    # Component 1 — the existing GNSS field, in its own route mode.
    gnss = products.gnss_degradation(
        {"route": data.get("route"), "corridor_km": corridor_km}, stations
    )
    gnss_ok = gnss.get("ok") is True

    def _in_corridor(layers: tuple[str, ...]) -> list[tuple[dict[str, Any], float]]:
        hits: list[tuple[dict[str, Any], float]] = []
        for s in stations:
            if not isinstance(s, dict) or s.get("layer") not in layers or not s.get("live"):
                continue
            try:
                lat, lon = float(s["lat"]), float(s["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            dist = products._route_distance_km(route, lat, lon)
            if dist <= corridor_km:
                hits.append((s, dist))
        hits.sort(key=lambda pair: pair[1])
        return hits

    interference_raw = _in_corridor(("jamming",))
    interference = [
        {**products._citation(s), "distance_km": round(d, 2), "claim": products._reported_claim(s)}
        for s, d in interference_raw[:24]
    ]
    platforms_raw = _in_corridor(products._ROUTE_PLATFORM_LAYERS)
    platform_counts: dict[str, int] = {}
    for s, _ in platforms_raw:
        layer = str(s.get("layer"))
        platform_counts[layer] = platform_counts.get(layer, 0) + 1
    platforms = [
        {**products._citation(s), "distance_km": round(d, 2)} for s, d in platforms_raw[:24]
    ]
    hazards_raw = _in_corridor(products._ROUTE_HAZARD_LAYERS)
    hazard_counts: dict[str, int] = {}
    for s, _ in hazards_raw:
        layer = str(s.get("layer"))
        hazard_counts[layer] = hazard_counts.get(layer, 0) + 1
    hazards = [
        {**products._citation(s), "distance_km": round(d, 2)} for s, d in hazards_raw[:24]
    ]

    if not gnss_ok and not interference and not platforms and not hazards:
        return {
            "ok": False,
            "capability_id": "atlas.route.integrity@v1",
            "refuse_reason": (
                f"no LIVE GNSS, interference, platform or hazard evidence within "
                f"{corridor_km:g} km of the route"
            ),
            "query": query,
            "gnss_refuse_reason": str(gnss.get("refuse_reason") or "") or None,
        }

    # Per-segment breakdown. The corridor is what a buyer plans around, so the counts
    # have to be attributable to a leg rather than to the whole polyline.
    segments: list[dict[str, Any]] = []
    for index, (a, b) in enumerate(zip(route, route[1:])):
        seg_len = round(products._haversine_km(a[0], a[1], b[0], b[1]), 2)
        seg = {
            "index": index,
            "from": {"lat": a[0], "lon": a[1]},
            "to": {"lat": b[0], "lon": b[1]},
            "length_km": seg_len,
            "reported_interference": 0,
            "hazards": 0,
            "platform_observations": 0,
        }
        for bucket, rows in (
            ("reported_interference", interference_raw),
            ("hazards", hazards_raw),
            ("platform_observations", platforms_raw),
        ):
            for s, _ in rows:
                try:
                    lat, lon = float(s["lat"]), float(s["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                if products._point_segment_km(lat, lon, *a, *b) <= corridor_km:
                    seg[bucket] = int(seg[bucket]) + 1
        segments.append(seg)

    # The honest vocabulary, reused: what class of claim can this evidence support?
    if interference:
        integrity_claim = "reported_interference"
    elif gnss_ok:
        integrity_claim = "station_coverage_only"
    else:
        integrity_claim = "no_gnss_coverage"

    coverage = gnss.get("coverage") if isinstance(gnss.get("coverage"), dict) else {}
    drivers = [
        f"route {length_km:g} km over {len(segments)} segment(s), corridor ±{corridor_km:g} km",
    ]
    if gnss_ok:
        drivers.append(
            f"GNSS station evidence in corridor: {coverage.get('stations', 0)} station(s), "
            f"claim {coverage.get('claim') or 'unknown'}"
        )
    else:
        drivers.append(
            "no GNSS station evidence in corridor: "
            + (str(gnss.get("refuse_reason") or "unavailable"))
        )
    drivers.append(
        f"{len(interference)} reported interference zone(s) intersect the corridor"
        if interference else "no reported interference zone intersects the corridor"
    )
    if platform_counts:
        drivers.append(
            "platform presence in corridor: "
            + ", ".join(f"{layer} {n}" for layer, n in sorted(platform_counts.items()))
            + " — presence only, not an integrity measurement"
        )
    else:
        drivers.append("no LIVE AIS/ADS-B platform observation in the corridor")
    if hazard_counts:
        drivers.append(
            "hazard pins in corridor: "
            + ", ".join(f"{layer} {n}" for layer, n in sorted(hazard_counts.items()))
        )

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.route.integrity@v1",
        "sku": "atlas.route.integrity@v1",
        "generated_at": utc_now(),
        "query": query,
        "integrity_claim": integrity_claim,
        "summary": (
            f"{route_id or 'Route'}: {length_km:g} km, {len(segments)} segment(s), "
            f"{len(interference)} reported interference zone(s), "
            f"{sum(hazard_counts.values())} hazard pin(s) in a ±{corridor_km:g} km corridor; "
            f"integrity claim {integrity_claim}. Reported interference and station coverage "
            "are not proof of jamming or spoofing."
        ),
        "drivers": drivers,
        "segments": segments,
        "gnss": gnss if gnss_ok else None,
        "gnss_refuse_reason": None if gnss_ok else (str(gnss.get("refuse_reason") or "") or None),
        "reported_interference": interference,
        "reported_interference_count": len(interference),
        "platform_observations": platforms,
        "platform_observation_counts": platform_counts,
        "hazards": hazards,
        "hazard_counts": hazard_counts,
        "limitations": [
            "Derived GNSS degradation and reported interference zones are NOT proof of "
            "jamming or spoofing, and this SKU is not for safety-of-life navigation.",
            "The GNSS station layer is a public station inventory (EUREF EPN and "
            "Geoscience Australia) plus a curated interference registry — not a live "
            "integrity measurement along the route.",
            "AIS coverage is public coastal data (Finnish and Norwegian waters) and ADS-B "
            "is a public community feed; platform observations show presence in the "
            "corridor, not receiver performance.",
            "Hazard pins are upstream published detections and advisories, not a routing "
            "instruction or a clearance.",
        ],
        "attribution": [
            "EUREF Permanent GNSS Network / EPN Central Bureau · CC BY 4.0",
            "Geoscience Australia GNSS data · CC BY 3.0 Australia",
            "CyberNews GNSS interference registry · CC BY 4.0",
            "Fintraffic maritime traffic data · CC BY 4.0",
            "Norwegian Coastal Administration AIS via BarentsWatch · NLOD 2.0",
            "adsb.lol open API · ODbL 1.0 — cite ADSB.lol; isolate any derived database",
        ],
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.route.integrity@v1")
    products.remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = products._receipt_links(payload["receipt"])
    return payload


# ── atlas.observability.attest@v1 ─────────────────────────────────────────────
#
# The meta-product: not "what was the weather", but "what data existed, and was the
# instrument up". A NEXRAD outage is a routine reason a weather-dependent claim gets
# contested, and until now ATLAS could only answer for *now*.
#
# The archive knows only what it recorded, so two things must never be confused:
# a recorded degraded status (positive evidence) and a sampling gap (no evidence).


_DEGRADED_STATUS_WORDS = ("down", "out", "outage", "maint", "offline", "inop", "fail")


def _radar_station_id(pin: dict[str, Any]) -> str:
    return str(pin.get("radar_id") or pin.get("station_id") or pin.get("id") or "")


def _status_is_degraded(sample: dict[str, Any]) -> bool:
    text = " ".join(
        str(sample.get(key) or "") for key in ("status", "operability")
    ).lower()
    return any(word in text for word in products._DEGRADED_STATUS_WORDS)


def observability_attest(
    data: dict[str, Any],
    stations: list[dict[str, Any]],
    archive: Any | None = None,
) -> dict[str, Any]:
    """``atlas.observability.attest@v1`` — was the observation infrastructure up?"""
    from ..status_archive import ARCHIVE, parse_iso

    store = archive if archive is not None else ARCHIVE
    point = products._parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.observability.attest@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    event_id = str(data.get("event_id") or "").strip()[:160] or None
    try:
        max_km = float(data.get("max_km") if data.get("max_km") is not None else 250.0)
    except (TypeError, ValueError):
        max_km = 250.0
    # WSR-88D useful range is ~230 km; beyond ~460 km "the nearest radar" stops being
    # a meaningful statement about coverage of the event.
    max_km = max(1.0, min(max_km, 460.0))
    start = parse_iso(data.get("start"))
    end = parse_iso(data.get("end"))
    if start is not None and end is not None and end < start:
        return {
            "ok": False,
            "capability_id": "atlas.observability.attest@v1",
            "refuse_reason": "end must not precede start",
            "query": {"lat": lat, "lon": lon, "start": data.get("start"), "end": data.get("end")},
        }
    query = {
        "lat": lat,
        "lon": lon,
        "max_km": max_km,
        "event_id": event_id,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ") if start else None,
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ") if end else None,
    }

    nearby: list[tuple[dict[str, Any], float]] = []
    for pin in stations:
        if not isinstance(pin, dict) or pin.get("layer") != "radar":
            continue
        try:
            plat, plon = float(pin["lat"]), float(pin["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        dist = products._haversine_km(lat, lon, plat, plon)
        if dist <= max_km:
            nearby.append((pin, dist))
    nearby.sort(key=lambda pair: pair[1])
    nearby = nearby[:8]

    if not nearby:
        return {
            "ok": False,
            "capability_id": "atlas.observability.attest@v1",
            "refuse_reason": (
                f"no radar station within {max_km:g} km of the coordinate; coverage "
                "cannot be attested (NEXRAD covers United States territory)"
            ),
            "query": query,
        }

    station_ids = [products._radar_station_id(pin) for pin, _ in nearby]
    archived = store.window(
        layer="radar",
        station_ids=[s for s in station_ids if s],
        start=start,
        end=end,
    )
    by_station: dict[str, list[dict[str, Any]]] = {}
    for sample in archived["samples"]:
        by_station.setdefault(str(sample.get("station_id") or ""), []).append(sample)

    radars: list[dict[str, Any]] = []
    degraded_total = 0
    for pin, dist in nearby:
        station_id = products._radar_station_id(pin)
        samples = by_station.get(station_id, [])
        degraded = [s for s in samples if products._status_is_degraded(s)]
        degraded_total += len(degraded)
        radars.append({
            **products._citation(pin),
            "station_id": station_id or None,
            "distance_km": round(dist, 2),
            "status_now": pin.get("status"),
            "operability_now": pin.get("operability"),
            "vcp_now": pin.get("vcp"),
            "archive": {
                "samples": len(samples),
                "first_ts": samples[0]["ts"] if samples else None,
                "last_ts": samples[-1]["ts"] if samples else None,
                "degraded_samples": len(degraded),
                "degraded_first_ts": degraded[0]["ts"] if degraded else None,
                "degraded_last_ts": degraded[-1]["ts"] if degraded else None,
            },
            "point_invoke": products._point_handoff(pin.get("id")),
        })

    # Window coverage is the load-bearing field: an empty archive is "we cannot say",
    # never "nothing was wrong".
    archive_start = parse_iso(archived["archive_start"])
    archive_end = parse_iso(archived["archive_end"])
    if archived["sample_count"] == 0:
        coverage = "none"
    elif (
        start is not None
        and archive_start is not None
        and start < archive_start
    ) or (
        end is not None
        and archive_end is not None
        and end > archive_end
    ):
        coverage = "partial"
    else:
        coverage = "recorded"
    window_coverage = {
        "coverage": coverage,
        "requested_start": query["start"],
        "requested_end": query["end"],
        "archive_start": archived["archive_start"],
        "archive_end": archived["archive_end"],
        "samples_in_window": archived["sample_count"],
        "layer_sample_count": archived["layer_sample_count"],
        "truncated": bool(archived["truncated"]),
    }

    alerts = [
        {**products._citation(s), "distance_km": round(products._haversine_km(lat, lon, float(s["lat"]), float(s["lon"])), 2)}
        for s in stations
        if isinstance(s, dict) and s.get("layer") == "alerts" and s.get("live")
        and isinstance(s.get("lat"), (int, float)) and isinstance(s.get("lon"), (int, float))
        and products._haversine_km(lat, lon, float(s["lat"]), float(s["lon"])) <= max_km
    ][:12]
    weather_pin, weather_km = products._nearest_candidate(stations, lat=lat, lon=lon, layers={"weather"})
    weather = (
        {**products._citation(weather_pin), "distance_km": round(weather_km, 2)}
        if weather_pin is not None and weather_km is not None and weather_km <= max_km
        else None
    )

    drivers = [
        f"{len(radars)} radar station(s) within {max_km:g} km; nearest "
        f"{radars[0]['distance_km']} km ({radars[0].get('station_id') or 'unnamed'})",
    ]
    if coverage == "none":
        drivers.append(
            "the status archive holds no sample for these stations in the requested "
            "window — this attests missing evidence, not a healthy radar"
        )
    else:
        drivers.append(
            f"{archived['sample_count']} archived status sample(s) in the window "
            f"({archived['archive_start']} → {archived['archive_end']} held in total)"
        )
        drivers.append(
            f"{degraded_total} sample(s) recorded a degraded status"
            if degraded_total else "no archived sample recorded a degraded status"
        )
    if coverage == "partial":
        drivers.append(
            "the requested window extends beyond what the archive holds; the "
            "uncovered part is not attested either way"
        )
    drivers.append(
        f"{len(alerts)} active weather alert(s) currently within {max_km:g} km"
        if alerts else f"no active weather alert currently within {max_km:g} km"
    )

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.observability.attest@v1",
        "sku": "atlas.observability.attest@v1",
        "generated_at": utc_now(),
        "query": query,
        "attestation_kind": "data_availability",
        "window_coverage": window_coverage,
        "degraded_sample_count": degraded_total,
        "summary": (
            f"{event_id or 'Event'} at {lat:.4f},{lon:.4f}: {len(radars)} radar(s) within "
            f"{max_km:g} km, archive coverage {coverage}, {degraded_total} degraded "
            f"sample(s) recorded. Attests what evidence exists, not what the weather was."
        ),
        "drivers": drivers,
        "radars": radars,
        "active_alerts": alerts,
        "weather": weather,
        "limitations": [
            "This attests the availability and recorded status of observation "
            "infrastructure. It is not reflectivity, not a weather reconstruction, and "
            "not an adjudication of any claim.",
            "A gap in the archive is an absence of evidence, NOT evidence the radar was "
            "down; only samples with a recorded degraded status are positive evidence.",
            "The archive begins at its first recorded sample; windows before that are "
            "reported as uncovered rather than clean.",
            "NEXRAD and NWS alert products cover United States territory only.",
            "Active alerts are current at generation time; alert history is not archived.",
        ],
        "attribution": [
            "NOAA/NWS NEXRAD Radar Operations Center (station status)",
            "NOAA/NWS CAP alert products",
        ],
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.observability.attest@v1")
    products.remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = products._receipt_links(payload["receipt"])
    return payload


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
