"""Products about a point or an area: point reads, GNSS degradation, watchbox checks and the
nearest live reading.
"""

from __future__ import annotations

from typing import Any

from ..geo import in_bbox, normalize_bbox, utc_now
from ..gnss_index import state_for_score
from ..stations import STATION_CATALOG
from ..watchboxes import ALLOWED_WATCHBOX_LAYERS, evaluate_watchbox


def _point_handoff(point_id: Any) -> dict[str, Any]:
    """Machine-readable handoff from discovery SKUs to exact point reads."""
    return {
        "capability_id": "atlas.point.read@v1",
        "product_id": "atlas.products",
        "input": {"point_id": str(point_id or ""), "fresh": False},
        "invoke_path": "/ai-market/v2/invoke",
    }


def _parent_capability(point: dict[str, Any]) -> dict[str, Any] | None:
    """Describe the GAIA rail behind a point without claiming exact targeting.

    Catalog sensors and Argo WMO reads are directly addressable. Other dense
    event pins are exact observations selected by ATLAS from a parent cluster;
    invoking their parent GAIA capability refreshes the cluster, not that pixel.
    """
    point_id = str(point.get("id") or "")
    parent_id = str(point.get("parent_id") or "")
    device_id = parent_id if parent_id in STATION_CATALOG else point_id
    meta = STATION_CATALOG.get(device_id)
    if not meta:
        return None
    inp: dict[str, Any] = {"device_id": device_id}
    targeted = not bool(parent_id)
    if point_id.startswith("argo-wmo-"):
        wmo = str(point.get("wmo") or point_id.removeprefix("argo-wmo-"))
        inp["wmo"] = wmo
        targeted = True
    if point_id.startswith(("gnss-station:euref:", "gnss-station:ga:")):
        inp["station_id"] = str(
            point.get("station_id") or point_id.rsplit(":", 1)[-1]
        )
        targeted = True
    return {
        "capability_id": str(meta.get("capability") or ""),
        "product_id": "gaia.gateway",
        "device_id": device_id,
        "input": inp,
        "targeting": "exact" if targeted else "parent_cluster",
        "invoke_url": "https://iot.modelmarket.dev/ai-market/v2/invoke",
    }


def point_read(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.point.read@v1`` — exact map object → signed evidence object."""
    point_id = str(data.get("point_id") or "").strip()
    if not point_id or len(point_id) > 160:
        return {
            "ok": False,
            "capability_id": "atlas.point.read@v1",
            "refuse_reason": "point_id required (1..160 characters)",
        }
    point = next(
        (
            item for item in stations
            if isinstance(item, dict) and str(item.get("id") or "") == point_id
        ),
        None,
    )
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.point.read@v1",
            "point_id": point_id,
            "refuse_reason": "point not found or no longer present in the ATLAS evidence window",
        }
    exact = products._citation(point)
    for key in (
        "kind", "label", "title", "subtitle", "summary", "metrics", "status_line",
        "blurb", "model", "site", "online", "has_reading", "cached", "age_ms",
        "upstream_evidence",
        "cell_id", "grid_scheme", "boundary", "station_ids", "source_count",
    ):
        if point.get(key) is not None:
            exact[key] = point[key]
    parent = products._parent_capability(point)
    is_derived_cell = point_id.startswith("gnss-cell:")
    snapshot_selected = bool(point.get("parent_id")) and not (
        point_id.startswith("argo-wmo-") or point_id.startswith(("gnss-station:euref:", "gnss-station:ga:"))
    )
    payload = {
        "ok": True,
        "capability_id": "atlas.point.read@v1",
        "sku": "atlas.point.read@v1",
        "generated_at": utc_now(),
        "point_id": point_id,
        "point": exact,
        "resolution": {
            "kind": (
                "derived_integrity_cell" if is_derived_cell else
                "source_snapshot_selection" if snapshot_selected else
                "source_addressable_read"
            ),
            "fresh_requested": bool(data.get("fresh", False)),
            "evidence_boundary": (
                "ATLAS selects this exact observation from its latest parent source snapshot; "
                "the parent capability refreshes the cluster, not an individual event."
                if snapshot_selected
                else "This point is a derived ATLAS integrity cell; its station_ids identify the source evidence."
                if is_derived_cell
                else "The point maps to a source-addressable sensor or platform read."
            ),
        },
        "parent_capability": parent,
        "point_invoke": products._point_handoff(point_id),
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.point.read@v1")
    return payload


def _gnss_state(score: float | None) -> str:
    return state_for_score(score)


def _reported_claim(event: dict[str, Any]) -> str:
    values = event.get("values") if isinstance(event.get("values"), dict) else {}
    kind = " ".join(str(values.get(k) or "") for k in ("type", "event", "severity")).lower()
    return "spoofing_reported" if "spoof" in kind else "jamming_reported"


def gnss_degradation(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an honest GNSS degradation field from currently cited evidence."""
    limit = max(1, min(int(data.get("limit") or 200), 500))
    max_km = max(1.0, min(float(data.get("max_km") or 750.0), 5000.0))
    corridor_km = max(1.0, min(float(data.get("corridor_km") or 100.0), 1000.0))
    points = [
        s for s in stations
        if isinstance(s, dict) and str(s.get("id") or "").startswith("gnss-station:")
    ]
    # Fan the relay's inventory out ourselves when the caller handed us cluster parents.
    # The fleet snapshot is built with expand=False (sidebar totals only; the map loads
    # densified pins per viewport), so a GNSS relay arrives as ONE `gnss-euref-01` row
    # carrying 520 stations in `hotspots[]` — and this product, which filters for
    # `gnss-station:` ids, saw zero and refused every query with `no_coverage` even
    # though the evidence was in its hands. Expanding here keeps the map path untouched.
    if not points:
        for parent in stations:
            if not isinstance(parent, dict) or parent.get("layer") != "gnss":
                continue
            for row in parent.get("hotspots") or []:
                if not isinstance(row, dict):
                    continue
                pid = str(row.get("point_id") or "")
                if not pid.startswith("gnss-station:"):
                    continue
                lat, lon = row.get("latitude"), row.get("longitude")
                if lat is None or lon is None:
                    continue
                points.append({
                    "id": pid,
                    "layer": "gnss",
                    "lat": lat,
                    "lon": lon,
                    # Provenance rides on the parent: the station row itself carries no
                    # licence, and dropping attribution here would silently strip the
                    # CC BY obligation from a paid artifact.
                    "source": row.get("source") or parent.get("source"),
                    "live": bool(parent.get("live")),
                    "online": bool(parent.get("online")),
                    "parent_id": parent.get("id"),
                    "values": row,
                })
    events = [s for s in stations if isinstance(s, dict) and s.get("layer") == "jamming"]

    query: dict[str, Any]
    selected: list[tuple[dict[str, Any], float | None]] = []
    route_raw = data.get("route")
    if isinstance(route_raw, list) and 2 <= len(route_raw) <= 500:
        route: list[tuple[float, float]] = []
        try:
            for pair in route_raw:
                lon, lat = float(pair[0]), float(pair[1])
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    raise ValueError
                route.append((lat, lon))
        except (TypeError, ValueError, IndexError):
            return products._attach_gnss_envelope({
                "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
                "refuse_reason": "route must contain valid [lon, lat] pairs",
            })
        query = {"kind": "route", "route": route_raw, "corridor_km": corridor_km}
        for point in points:
            try:
                lat, lon = float(point["lat"]), float(point["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            dist = min(products._point_segment_km(lat, lon, *a, *b) for a, b in zip(route, route[1:]))
            if dist <= corridor_km:
                selected.append((point, dist))
    elif all(data.get(k) is not None for k in ("west", "south", "east", "north")):
        try:
            west, south, east, north = normalize_bbox(
                float(data["west"]), float(data["south"]), float(data["east"]), float(data["north"])
            )
        except (TypeError, ValueError):
            return products._attach_gnss_envelope({
                "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
                "refuse_reason": "invalid bbox",
            })
        query = {"kind": "bbox", "west": west, "south": south, "east": east, "north": north}
        selected = [(p, None) for p in products._stations_in_bbox(points, west=west, south=south, east=east, north=north)]
    elif data.get("lat") is not None and data.get("lon") is not None:
        try:
            qlat, qlon = float(data["lat"]), float(data["lon"])
        except (TypeError, ValueError):
            qlat = qlon = 999.0
        if not (-90 <= qlat <= 90 and -180 <= qlon <= 180):
            return products._attach_gnss_envelope({
                "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
                "refuse_reason": "lat/lon out of range",
            })
        query = {"kind": "point", "lat": qlat, "lon": qlon, "max_km": max_km}
        for point in points:
            try:
                dist = products._haversine_km(qlat, qlon, float(point["lat"]), float(point["lon"]))
            except (KeyError, TypeError, ValueError):
                continue
            if dist <= max_km:
                selected.append((point, dist))
    else:
        return products._attach_gnss_envelope({
            "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
            "refuse_reason": "provide lat+lon, west+south+east+north, or route",
        })

    selected.sort(key=lambda pair: pair[1] if pair[1] is not None else 0.0)
    selected = selected[:limit]
    if not selected:
        return products._attach_gnss_envelope({
            "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
            "refuse_reason": "no GNSS station evidence in the requested area",
            "query": query,
            "coverage": {"stations": 0, "claim": "no_coverage"},
        })

    observations: list[dict[str, Any]] = []
    cells: dict[str, dict[str, Any]] = {}
    scheme = "h3-r4"
    for point, distance in selected:
        values = point.get("values") if isinstance(point.get("values"), dict) else {}
        try:
            lat, lon = float(point["lat"]), float(point["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        score_raw = values.get("degradation_score")
        score = float(score_raw) if isinstance(score_raw, (int, float)) else None
        nearby_events: list[dict[str, Any]] = []
        for event in events:
            ev_values = event.get("values") if isinstance(event.get("values"), dict) else {}
            try:
                ev_dist = products._haversine_km(lat, lon, float(event["lat"]), float(event["lon"]))
            except (KeyError, TypeError, ValueError):
                continue
            radius = float(ev_values.get("radius_km") or 0.0)
            if ev_dist <= max(50.0, radius):
                nearby_events.append({**products._citation(event), "distance_km": round(ev_dist, 2)})
        for event in nearby_events:
            event["claim_level"] = products._reported_claim(event)
            event["claim_class"] = "reported_interference"
        event_score = max((float((e.get("values") or {}).get("severity_score") or 0.0) for e in nearby_events), default=None)
        claim_class = point.get("claim_class") or "inventory_only"
        claim_level = point.get("claim_level") or ("derived_degradation" if score is not None else "observed_metric")
        state = products._gnss_state(score)
        obs = {
            **products._citation(point),
            "distance_km": round(distance, 2) if distance is not None else None,
            "degradation_score": round(score, 2) if score is not None else None,
            "reported_interference_score": round(event_score, 2) if event_score is not None else None,
            "state": state,
            "claim_class": claim_class,
            "claim_level": claim_level,
            "cause": "unestablished",
            "interference_events": nearby_events,
            "point_invoke": products._point_handoff(point.get("id")),
        }
        observations.append(obs)
        cell_id, scheme = products._grid_cell(lat, lon)
        cell = cells.setdefault(cell_id, {
            "cell_id": cell_id, "lat": lat, "lon": lon, "scores": [],
            "reported_scores": [], "station_ids": [], "claim_classes": set(),
            "claim_levels": set(), "contributions": [],
        })
        if score is not None:
            cell["scores"].append(score)
            cell["contributions"].append({
                "point_id": point.get("id"), "evidence_class": "ground_gnss_station",
                "claim_level": claim_level, "degradation_score": round(score, 2),
            })
        if event_score is not None:
            cell["reported_scores"].append(event_score)
            cell["contributions"].extend({
                "point_id": event.get("id"), "evidence_class": "curated_interference_event",
                "claim_level": event["claim_level"],
                "reported_interference_score": float((event.get("values") or {}).get("severity_score") or 0.0),
            } for event in nearby_events)
        cell["station_ids"].append(point.get("id"))
        cell["claim_classes"].add(claim_class)
        cell["claim_levels"].add(claim_level)

    cell_rows: list[dict[str, Any]] = []
    for cell in cells.values():
        scores = cell.pop("scores")
        reported_scores = cell.pop("reported_scores")
        classes = sorted(cell.pop("claim_classes"))
        levels = sorted(cell.pop("claim_levels"))
        score = round(sum(scores) / len(scores), 2) if scores else None
        cell_rows.append({
            **cell,
            "point_id": f"gnss-cell:{cell['cell_id']}",
            "degradation_score": score,
            "reported_interference_score": round(max(reported_scores), 2) if reported_scores else None,
            "state": products._gnss_state(score),
            "claim_classes": classes,
            "claim_levels": levels,
        })
    scored_confidence = [
        float((o.get("values") or {}).get("confidence") or 0.0)
        for o in observations if o.get("degradation_score") is not None
    ]
    payload = {
        "ok": True,
        "capability_id": "atlas.gnss.degradation.read@v1",
        "sku": "atlas.gnss.degradation.read@v1",
        "generated_at": utc_now(),
        "query": query,
        "grid_scheme": scheme,
        "cells": cell_rows,
        "observations": observations,
        "coverage": {
            "stations": len(observations),
            "cells": len(cell_rows),
            "reported_interference_events": sum(len(o["interference_events"]) for o in observations),
            "unknown_integrity": sum(1 for o in observations if o["state"] == "unknown"),
        },
        "confidence": round(sum(scored_confidence) / len(scored_confidence), 3) if scored_confidence else 0.0,
        "evidence_boundary": (
            "Station availability/latency describes observation delivery, not RF power. "
            "Reported interference remains source-attributed. No coverage is never reported as normal."
        ),
        # §7.3 / §12 / §16.9: attribution must be machine-readable and present in the
        # RESPONSE, not merely in a map tooltip. EUREF is CC BY 4.0 and Geoscience
        # Australia CC BY 3.0 AU, and this is a PAID artifact — a priced response that
        # redistributes CC BY data with no attribution is a licence breach, and the
        # envelope was shipping without the field at all.
        "source_attributions": sorted({
            str(p.get("source"))
            for p, _d in selected
            if p.get("source")
        }),
        # Spec §7.3 requires these two sentences in the envelope, not only in the UI.
        # This is the one product in the family where being read as an operational
        # advisory could hurt someone, so the disclaimer travels with the data.
        "limitations": [
            "Derived degradation is not proof of jamming or spoofing.",
            "Not for safety-of-life navigation.",
        ],
    }
    return products._attach_gnss_envelope(payload)


def _stations_in_bbox(
    stations: list[dict[str, Any]],
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    layers: set[str] | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in stations:
        if not isinstance(s, dict):
            continue
        layer = str(s.get("layer") or "")
        if layers is not None and layer not in layers:
            continue
        try:
            lat = float(s.get("lat"))
            lon = float(s.get("lon"))
        except (TypeError, ValueError):
            continue
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:
            continue
        if in_bbox(lat, lon, west, south, east, north):
            out.append(s)
    return out


def _normalize_layer_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        layer = str(item).strip().lower()
        if layer in ALLOWED_WATCHBOX_LAYERS and layer not in out:
            out.append(layer)
    return out


def watchbox_check(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.watchbox.check@v1``."""
    wid = str(data.get("watchbox_id") or "").strip()
    if wid:
        row = products.STORE.get(wid)
        if not row:
            return {
                "ok": False,
                "capability_id": "atlas.watchbox.check@v1",
                "refuse_reason": f"unknown watchbox: {wid}",
            }
        result = evaluate_watchbox(row, stations)
    else:
        bbox = products._parse_bbox(data)
        layers = products._normalize_layer_list(data.get("layers"))
        if bbox is None or not layers:
            return {
                "ok": False,
                "capability_id": "atlas.watchbox.check@v1",
                "refuse_reason": "provide watchbox_id or west/south/east/north + layers",
            }
        west, south, east, north = bbox
        ephemeral = {
            "id": "ephemeral",
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "layers": layers,
        }
        result = evaluate_watchbox(ephemeral, stations)

    live_hits = sum(1 for m in result.get("matches") or [] if m.get("live"))
    payload = {
        "ok": True,
        "capability_id": "atlas.watchbox.check@v1",
        "sku": "atlas.watchbox.check@v1",
        "evaluated_at": result.get("evaluated_at") or utc_now(),
        "watchbox_id": result.get("watchbox_id"),
        "bbox": result.get("bbox"),
        "layers": result.get("layers"),
        "match_count": result.get("match_count", 0),
        "live_match_count": live_hits,
        "matches": result.get("matches") or [],
    }
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.watchbox.check@v1")
    return payload


def _live_valued(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        s for s in stations
        if s.get("live") and (s.get("values") or s.get("has_reading"))
    ]


def _num_value(s: dict[str, Any], *keys: str) -> float:
    vals = s.get("values") if isinstance(s.get("values"), dict) else {}
    for key in keys:
        raw = vals.get(key) if vals.get(key) is not None else s.get(key)
        try:
            if raw is not None:
                return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def _nearest_layers(data: dict[str, Any]) -> list[str]:
    """Requested layers filtered to the allowlist.

    ``[]`` means every requested layer was invalid — the SKU must refuse, not
    silently answer a weather question nobody asked.
    """
    raw = data.get("layers")
    if raw is None and data.get("layer") is not None:
        raw = [data.get("layer")]
    if raw is None:
        return ["weather"]
    out: list[str] = []
    for item in raw if isinstance(raw, list) else [raw]:
        layer = str(item).strip().lower()
        if layer in ALLOWED_WATCHBOX_LAYERS and layer not in out:
            out.append(layer)
    return out


def _nearest_candidate(
    stations: list[dict[str, Any]],
    *,
    lat: float,
    lon: float,
    layers: set[str],
) -> tuple[dict[str, Any] | None, float | None]:
    best: dict[str, Any] | None = None
    best_km: float | None = None
    for s in stations:
        if not isinstance(s, dict):
            continue
        if str(s.get("layer") or "") not in layers:
            continue
        if not s.get("live"):
            continue
        vals = s.get("values") if isinstance(s.get("values"), dict) else {}
        if not (s.get("has_reading") or vals):
            continue
        try:
            slat, slon = float(s["lat"]), float(s["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if abs(slat) < 1e-6 and abs(slon) < 1e-6:
            continue
        d = products._haversine_km(lat, lon, slat, slon)
        if best_km is None or d < best_km:
            best_km = d
            best = s
    return best, best_km


def _layers_with_live_readings(stations: list[dict[str, Any]]) -> set[str]:
    """Layers that have at least one pin `_nearest_candidate` could answer with."""
    live: set[str] = set()
    for s in stations:
        if not isinstance(s, dict) or not s.get("live"):
            continue
        vals = s.get("values") if isinstance(s.get("values"), dict) else {}
        if not (s.get("has_reading") or vals):
            continue
        try:
            slat, slon = float(s["lat"]), float(s["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if abs(slat) < 1e-6 and abs(slon) < 1e-6:
            continue
        live.add(str(s.get("layer") or ""))
    return live


def nearest_read(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s)."""
    point = products._parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.nearest.read@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    layers = products._nearest_layers(data)
    if not layers:
        return {
            "ok": False,
            "capability_id": "atlas.nearest.read@v1",
            "refuse_reason": (
                "no valid layers requested — allowed: "
                + ", ".join(sorted(ALLOWED_WATCHBOX_LAYERS))
            ),
        }
    # Some layers have no live source at all right now (soil, precipitation and others
    # wait on operator accounts upstream). Asking one of them answered "no LIVE readings
    # within 2500 km" from every point on Earth, which the hub scores as a provider miss,
    # so a buyer walking the layer list saw ATLAS "failing" systematically. Say which
    # layers cannot be served and which can, and serve the rest of a mixed request.
    live_layers = products._layers_with_live_readings(stations)
    unavailable = [layer for layer in layers if layer not in live_layers]
    layers = [layer for layer in layers if layer in live_layers]
    if not layers:
        return {
            "ok": False,
            "capability_id": "atlas.nearest.read@v1",
            "refuse_reason": (
                "no valid layers requested: " + ", ".join(unavailable)
                + " has no live source right now; layers with live readings: "
                + (", ".join(sorted(live_layers)) or "none")
            ),
            "unavailable_layers": unavailable,
            "available_layers": sorted(live_layers),
        }
    try:
        max_km = float(data.get("max_km") if data.get("max_km") is not None else 2500.0)
    except (TypeError, ValueError):
        max_km = 2500.0
    max_km = max(1.0, min(max_km, 20037.0))  # ~half Earth
    per_layer = bool(data.get("per_layer"))

    if per_layer:
        by_layer: dict[str, Any] = {}
        hits = 0
        for layer in layers:
            pin, dist = products._nearest_candidate(stations, lat=lat, lon=lon, layers={layer})
            if pin is None or dist is None or dist > max_km:
                by_layer[layer] = None
                continue
            hits += 1
            by_layer[layer] = {
                **products._citation(pin),
                "distance_km": round(dist, 2),
                "point_invoke": products._point_handoff(pin.get("id")),
            }
        if hits == 0:
            return {
                "ok": False,
                "capability_id": "atlas.nearest.read@v1",
                "refuse_reason": (
                    f"no LIVE readings within {max_km:g} km for layers {layers}"
                ),
                "query": {"lat": lat, "lon": lon, "layers": layers, "max_km": max_km},
            }
        payload = {
            "ok": True,
            "capability_id": "atlas.nearest.read@v1",
            "sku": "atlas.nearest.read@v1",
            "generated_at": utc_now(),
            "query": {"lat": lat, "lon": lon, "layers": layers, "max_km": max_km, "per_layer": True},
            "nearest_by_layer": by_layer,
            "hit_count": hits,
        }
        if unavailable:
            payload["unavailable_layers"] = unavailable
        payload["receipt"] = products.make_receipt(payload, capability_id="atlas.nearest.read@v1")
        return payload

    pin, dist = products._nearest_candidate(stations, lat=lat, lon=lon, layers=set(layers))
    if pin is None or dist is None or dist > max_km:
        return {
            "ok": False,
            "capability_id": "atlas.nearest.read@v1",
            "refuse_reason": (
                f"no LIVE readings within {max_km:g} km for layers {layers}"
            ),
            "query": {"lat": lat, "lon": lon, "layers": layers, "max_km": max_km},
        }
    payload = {
        "ok": True,
        "capability_id": "atlas.nearest.read@v1",
        "sku": "atlas.nearest.read@v1",
        "generated_at": utc_now(),
        "query": {"lat": lat, "lon": lon, "layers": layers, "max_km": max_km, "per_layer": False},
        "nearest": {
            **products._citation(pin),
            "distance_km": round(dist, 2),
            "point_invoke": products._point_handoff(pin.get("id")),
        },
        "distance_km": round(dist, 2),
        "layer": pin.get("layer"),
        "values": (pin.get("values") if isinstance(pin.get("values"), dict) else {}),
    }
    if unavailable:
        payload["unavailable_layers"] = unavailable
    payload["receipt"] = products.make_receipt(payload, capability_id="atlas.nearest.read@v1")
    return payload


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
