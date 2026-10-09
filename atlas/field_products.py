"""ATLAS field products — in-situ mesh × certified math, one signed artifact.

Four Hub SKUs:

* ``atlas.mesh.sample@v1`` — Halton (Lattice-equivalent) pick of LIVE pins
* ``atlas.field.consensus@v1`` — Murmuration-equivalent robust consensus
* ``atlas.field.posterior@v1`` — spatial RBF GP over the current snapshot
* ``atlas.field.shape@v1`` — H0 persistence of the LIVE point set

None of these is a forecast, a national official, or Open-Meteo-as-station.
"""

from __future__ import annotations

import math
from typing import Any

from .field_math import aggregate, h0_persistence, halton, haversine_km, rbf_gp_posterior
from .field_meshes import (
    FIELD_MESHES,
    FORBIDDEN_MESH_HINTS,
    get_mesh,
    mesh_catalog,
    station_in_mesh,
)
from .geo import in_bbox, utc_now

_RECEIPT_OUT: dict[str, Any] = {
    "type": "object",
    "description": (
        "Tamper-evident content receipt: sha256 over the canonical payload, hybrid-signed "
        "with Ed25519 and, when enabled, ML-DSA-65."
    ),
    "required": ["algorithm", "digest", "service", "version", "ts", "capability_id"],
    "properties": {
        "algorithm": {"type": "string"},
        "digest": {"type": "string"},
        "service": {"type": "string"},
        "version": {"type": "string"},
        "ts": {"type": "string", "format": "date-time"},
        "capability_id": {"type": "string"},
        "signature_alg": {"type": "string"},
        "signature_b64": {"type": "string"},
        "public_key_b64": {"type": "string"},
        "pq_signature_alg": {"type": "string", "enum": ["ml-dsa-65"]},
        "pq_signature_b64": {"type": "string"},
        "pq_public_key_b64": {"type": "string"},
        "signature_status": {
            "type": "string",
            "enum": ["signed", "unavailable_missing_runtime_dependency"],
        },
    },
}

_MESH_ID_SCHEMA = {
    "type": "string",
    "minLength": 2,
    "maxLength": 32,
    "description": (
        "Named licensed in-situ mesh (ee-wx, pegel, hubeau, …). "
        "Open-Meteo prefixes are refused. List: GET /api/v1/field-meshes."
    ),
}


def _common_output(description: str, extra: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = {
        "ok": {"type": "boolean"},
        "capability_id": {"type": "string"},
        "sku": {"type": "string"},
        "generated_at": {"type": "string", "format": "date-time"},
        "receipt": _RECEIPT_OUT,
        "refuse_reason": {"type": "string"},
        "mesh_id": {"type": ["string", "null"]},
        "artifact_type": {"type": "string"},
        "claim_class": {"type": "string"},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "attribution": {"type": "array", "items": {"type": "string"}},
        "receipt_url": {"type": ["string", "null"]},
        "verifier_url": {"type": ["string", "null"]},
    }
    props.update(extra)
    return {
        "type": "object",
        "description": description,
        "required": ["ok"],
        "properties": props,
    }


FIELD_PRODUCT_CAPS: list[dict[str, Any]] = [
    {
        "capability_id": "atlas.mesh.sample@v1",
        "name": "atlas.mesh.sample@v1",
        "description": (
            "Fair sample of a named licensed in-situ mesh. Halton / van der Corput "
            "(Lattice-equivalent) picks LIVE pins so an agent cannot cherry-pick "
            "convenient stations. Not ECVRF — Sortes is a sibling hop, not this SKU. "
            "Not Open-Meteo."
        ),
        "price_per_call_usd": 0.03,
        "p50_latency_ms": 60,
        "input_schema": {
            "type": "object",
            "required": ["mesh_id"],
            "properties": {
                "mesh_id": _MESH_ID_SCHEMA,
                "count": {"type": "integer", "minimum": 1, "maximum": 64, "default": 8},
                "skip": {"type": "integer", "minimum": 0, "default": 0},
                "quantity": {"type": "string"},
                "west": {"type": "number"},
                "south": {"type": "number"},
                "east": {"type": "number"},
                "north": {"type": "number"},
            },
        },
        "output_schema": _common_output(
            "Halton sample of LIVE in-situ pins. On refusal: ok, capability_id, refuse_reason.",
            {
                "method": {"type": "string"},
                "sibling_oracle": {"type": "string"},
                "quantity": {"type": ["string", "null"]},
                "catalog_live_count": {"type": "integer"},
                "requested_count": {"type": "integer"},
                "pins": {"type": "array", "items": {"type": "object"}},
                "device_ids": {"type": "array", "items": {"type": "string"}},
            },
        ),
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.field.consensus@v1",
        "name": "atlas.field.consensus@v1",
        "description": (
            "Robust consensus of a named licensed in-situ mesh: median, trimmed mean, "
            "Tukey biweight, DeGroot (Murmuration-equivalent). One broken station cannot "
            "move the number. LIVE readings only. Not a forecast, not an official national "
            "figure, not Open-Meteo-as-station."
        ),
        "price_per_call_usd": 0.06,
        "p50_latency_ms": 90,
        "input_schema": {
            "type": "object",
            "required": ["mesh_id"],
            "properties": {
                "mesh_id": _MESH_ID_SCHEMA,
                "quantity": {"type": "string"},
                "trim": {"type": "number", "minimum": 0.0, "maximum": 0.499, "default": 0.1},
                "device_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset, typically from atlas.mesh.sample@v1.",
                    "maxItems": 64,
                },
                "min_live": {"type": "integer", "minimum": 1, "maximum": 32, "default": 3},
                "west": {"type": "number"},
                "south": {"type": "number"},
                "east": {"type": "number"},
                "north": {"type": "number"},
            },
        },
        "output_schema": _common_output(
            "Robust consensus of LIVE in-situ readings. Not a forecast.",
            {
                "quantity": {"type": ["string", "null"]},
                "unit": {"type": ["string", "null"]},
                "consensus": {"type": "object"},
                "sibling_oracle": {"type": "string"},
                "live_count": {"type": "integer"},
                "dropped_sim_count": {"type": "integer"},
                "dropped_missing_quantity": {"type": "integer"},
                "citations": {"type": "array", "items": {"type": "object"}},
                "geography": {"type": "string"},
                "licence": {"type": "string"},
            },
        ),
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.field.posterior@v1",
        "name": "atlas.field.posterior@v1",
        "description": (
            "Spatial RBF Gaussian-process posterior over the current LIVE snapshot of a "
            "named in-situ mesh (Gauss-equivalent). Interpolates now, with calibrated "
            "variance, and names the next catalog pin of highest uncertainty. Not a "
            "forecast, not a national nowcast product."
        ),
        "price_per_call_usd": 0.08,
        "p50_latency_ms": 120,
        "input_schema": {
            "type": "object",
            "required": ["mesh_id"],
            "properties": {
                "mesh_id": _MESH_ID_SCHEMA,
                "quantity": {"type": "string"},
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "length_km": {"type": "number", "minimum": 5, "maximum": 2000, "default": 120},
                "device_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 64},
            },
        },
        "output_schema": _common_output(
            "Spatial GP posterior of a LIVE in-situ snapshot. Not a forecast.",
            {
                "quantity": {"type": ["string", "null"]},
                "query": {"type": ["object", "null"]},
                "posterior": {"type": ["object", "null"]},
                "suggest": {"type": ["object", "null"]},
                "train_count": {"type": "integer"},
                "sibling_oracle": {"type": "string"},
                "citations": {"type": "array", "items": {"type": "object"}},
            },
        ),
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.field.shape@v1",
        "name": "atlas.field.shape@v1",
        "description": (
            "H0 persistence (connected components vs radius) of LIVE pins on a named "
            "in-situ mesh. Answers whether the field is one cluster or several. Not "
            "Betti-1 loops — sibling betti.homology@v1 for full Vietoris–Rips. Not a "
            "quality index."
        ),
        "price_per_call_usd": 0.06,
        "p50_latency_ms": 80,
        "input_schema": {
            "type": "object",
            "required": ["mesh_id"],
            "properties": {
                "mesh_id": _MESH_ID_SCHEMA,
                "max_km": {"type": "number", "minimum": 10, "maximum": 2000, "default": 400},
                "device_ids": {"type": "array", "items": {"type": "string"}, "maxItems": 64},
            },
        },
        "output_schema": _common_output(
            "H0 shape of a LIVE in-situ point set. Not Betti-1, not an AQI.",
            {
                "homology": {"type": "object"},
                "sibling_oracle": {"type": "string"},
                "live_count": {"type": "integer"},
                "citations": {"type": "array", "items": {"type": "object"}},
            },
        ),
        "product_id": "atlas.products",
    },
]


def _finish(payload: dict[str, Any], capability_id: str) -> dict[str, Any]:
    from .products import _receipt_links, make_receipt, remember_receipt

    payload.setdefault("capability_id", capability_id)
    payload.setdefault("sku", capability_id)
    if payload.get("ok"):
        payload["receipt"] = make_receipt(payload, capability_id=capability_id)
        remember_receipt(payload["receipt"])
        payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
    else:
        payload.setdefault("receipt_url", None)
        payload.setdefault("verifier_url", None)
    return payload


def _refuse(capability_id: str, reason: str, **extra: Any) -> dict[str, Any]:
    body = {
        "ok": False,
        "capability_id": capability_id,
        "sku": capability_id,
        "refuse_reason": reason,
    }
    body.update(extra)
    return body


def _bbox_of(data: dict[str, Any]) -> tuple[float, float, float, float] | None:
    keys = ("west", "south", "east", "north")
    if not all(data.get(k) is not None for k in keys):
        return None
    try:
        return (
            float(data["west"]), float(data["south"]),
            float(data["east"]), float(data["north"]),
        )
    except (TypeError, ValueError):
        return None


def resolve_mesh(data: dict[str, Any], capability_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw = str(data.get("mesh_id") or "").strip().lower()
    if not raw:
        return None, _refuse(capability_id, "mesh_id required")
    if any(hint in raw for hint in FORBIDDEN_MESH_HINTS):
        return None, _refuse(
            capability_id,
            "Open-Meteo is a model mesh, not in-situ. Use a licensed station net "
            "(ee-wx, pegel, hubeau, …). GET /api/v1/field-meshes",
            mesh_id=raw,
        )
    spec = get_mesh(raw)
    if spec is None:
        known = ", ".join(sorted(FIELD_MESHES))
        return None, _refuse(
            capability_id,
            f"unknown mesh_id {raw!r}. Licensed in-situ meshes: {known}",
            mesh_id=raw,
        )
    return spec, None


def _quantity_value(station: dict[str, Any], quantity: str) -> float | None:
    values = station.get("values") if isinstance(station.get("values"), dict) else {}
    raw = values.get(quantity)
    if raw is None:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _pick_quantity(stations: list[dict[str, Any]], spec: dict[str, Any], requested: str | None) -> str | None:
    wanted = [requested] if requested else list(spec["quantities"])
    for quantity in wanted:
        if quantity and any(_quantity_value(s, quantity) is not None for s in stations):
            return str(quantity)
    return str(requested) if requested else (spec["quantities"][0] if spec.get("quantities") else None)


def _is_live(station: dict[str, Any]) -> bool:
    """LIVE only when neither flag says SIM. Ambiguous pins are dropped."""
    mode = str(station.get("mode") or "").lower()
    if mode == "sim" or station.get("live") is False:
        return False
    if station.get("live") is True:
        return True
    return mode == "live"


def _finite_lat_lon(station: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat, lon = float(station["lat"]), float(station["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lon):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def collect_mesh_stations(
    data: dict[str, Any],
    stations: list[dict[str, Any]],
    spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    allow = data.get("device_ids")
    allowed: set[str] | None = None
    if isinstance(allow, list) and allow:
        allowed = {str(x) for x in allow if str(x).strip()}
    bbox = _bbox_of(data)
    dropped_sim = 0
    out: list[dict[str, Any]] = []
    for station in stations:
        if not isinstance(station, dict):
            continue
        if not station_in_mesh(station, spec):
            continue
        sid = str(station.get("id") or "")
        if allowed is not None and sid not in allowed:
            continue
        coords = _finite_lat_lon(station)
        if coords is None:
            continue
        if bbox is not None and not in_bbox(coords[0], coords[1], *bbox):
            continue
        if not _is_live(station):
            dropped_sim += 1
            continue
        out.append(station)
    return out, dropped_sim


def _citation(station: dict[str, Any], quantity: str | None) -> dict[str, Any]:
    coords = _finite_lat_lon(station)
    row: dict[str, Any] = {
        "id": station.get("id"),
        "layer": station.get("layer"),
        "place": station.get("place"),
        "lat": coords[0] if coords else None,
        "lon": coords[1] if coords else None,
        "live": True,
        "source": station.get("source"),
    }
    if quantity:
        number = _quantity_value(station, quantity)
        if number is not None:
            row["value"] = number
        row["quantity"] = quantity
    return row


def _limitations(spec: dict[str, Any], extra: list[str]) -> list[str]:
    lines = [
        str(spec.get("not") or ""),
        "LIVE in-situ only. SIM pins are dropped, never padded.",
        "This is an attested snapshot of a licensed mesh, not a forecast and not an official national figure.",
    ]
    lines.extend(extra)
    return [line for line in lines if line]


def mesh_sample(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    cap = "atlas.mesh.sample@v1"
    spec, refused = resolve_mesh(data, cap)
    if refused or spec is None:
        return refused or _refuse(cap, "mesh_id required")
    members, dropped_sim = collect_mesh_stations(data, stations, spec)
    quantity = _pick_quantity(members, spec, data.get("quantity") if isinstance(data.get("quantity"), str) else None)
    ranked = []
    for station in members:
        coords = _finite_lat_lon(station)
        if coords is None:
            continue
        lat, lon = coords
        ranked.append((str(station.get("id") or ""), lat, lon, station))
    ranked.sort(key=lambda row: row[0])
    if not ranked:
        return _refuse(
            cap,
            "no LIVE in-situ pins on this mesh (empty feed is not 'all clear')",
            mesh_id=spec["id"],
        )
    try:
        count = max(1, min(int(data.get("count") or min(8, len(ranked))), 64, len(ranked)))
        skip = max(0, int(data.get("skip") or 0))
    except (TypeError, ValueError):
        return _refuse(cap, "count and skip must be integers", mesh_id=spec["id"])
    lats = [row[1] for row in ranked]
    lons = [row[2] for row in ranked]
    lat_span = max(max(lats) - min(lats), 1e-6)
    lon_span = max(max(lons) - min(lons), 1e-6)
    points = halton(count, dim=2, skip=skip)
    used: set[str] = set()
    picked: list[dict[str, Any]] = []
    for u, v in points:
        qlat = min(lats) + u * lat_span
        qlon = min(lons) + v * lon_span
        best = None
        best_d = 1e12
        for sid, lat, lon, station in ranked:
            if sid in used:
                continue
            d = haversine_km(qlat, qlon, lat, lon)
            if d < best_d:
                best_d = d
                best = (sid, station, d)
        if best is None:
            break
        sid, station, dist = best
        used.add(sid)
        citation = _citation(station, quantity)
        citation["sample_distance_km"] = round(dist, 3)
        picked.append(citation)
    payload = {
        "ok": True,
        "capability_id": cap,
        "sku": cap,
        "generated_at": utc_now(),
        "mesh_id": spec["id"],
        "artifact_type": "fair_mesh_sample",
        "claim_class": spec["claim_class"],
        "method": "halton/van-der-corput",
        "sibling_oracle": "lattice.sequence@v1",
        "quantity": quantity,
        "catalog_live_count": len(ranked),
        "requested_count": count,
        "pins": picked,
        "device_ids": [p["id"] for p in picked],
        "limitations": _limitations(spec, [
            "Sampling is Lattice-equivalent Halton, not Sortes ECVRF. Replay with the same skip.",
            f"Dropped {dropped_sim} SIM pin(s).",
        ]),
        "attribution": [spec["attribution"], spec["licence"]],
    }
    return _finish(payload, cap)


def field_consensus(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    cap = "atlas.field.consensus@v1"
    spec, refused = resolve_mesh(data, cap)
    if refused or spec is None:
        return refused or _refuse(cap, "mesh_id required")
    members, dropped_sim = collect_mesh_stations(data, stations, spec)
    quantity = _pick_quantity(members, spec, data.get("quantity") if isinstance(data.get("quantity"), str) else None)
    try:
        min_live = max(1, min(int(data.get("min_live") or 3), 32))
        trim = float(data["trim"]) if data.get("trim") is not None else 0.1
    except (TypeError, ValueError):
        return _refuse(cap, "min_live and trim must be numeric", mesh_id=spec["id"])
    citations: list[dict[str, Any]] = []
    values: list[float] = []
    missing = 0
    if not quantity:
        return _refuse(cap, "no recognised quantity on this mesh", mesh_id=spec["id"])
    for station in members:
        number = _quantity_value(station, quantity)
        if number is None:
            missing += 1
            continue
        values.append(number)
        citations.append(_citation(station, quantity))
    if len(values) < min_live:
        return _refuse(
            cap,
            f"need {min_live} LIVE readings of {quantity}; got {len(values)}. "
            "Empty or thin coverage is not a consensus and is not 'all clear'.",
            mesh_id=spec["id"],
            quantity=quantity,
        )
    stats = aggregate(values, trim=trim)
    payload = {
        "ok": True,
        "capability_id": cap,
        "sku": cap,
        "generated_at": utc_now(),
        "mesh_id": spec["id"],
        "artifact_type": "in_situ_field_consensus",
        "claim_class": spec["claim_class"],
        "quantity": quantity,
        "unit": None,
        "consensus": {
            "n": stats["n"],
            "median": stats["median"],
            "trimmed_mean": stats["trimmed_mean"],
            "biweight": stats["biweight"],
            "converged_value": stats["converged_value"],
            "iterations": stats["iterations"],
            "algorithm": stats["algorithm"],
        },
        "sibling_oracle": stats["sibling_oracle"],
        "live_count": len(values),
        "dropped_sim_count": dropped_sim,
        "dropped_missing_quantity": missing,
        "citations": citations,
        "geography": spec["geography"],
        "licence": spec["licence"],
        "limitations": _limitations(spec, [
            "The headline number is the biweight (redescending). Median and trimmed mean are on the receipt. DeGroot converged_value equals the arithmetic mean on a complete graph — reported, not sold as robust.",
        ]),
        "attribution": [spec["attribution"], spec["licence"]],
    }
    return _finish(payload, cap)


def field_posterior(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    cap = "atlas.field.posterior@v1"
    spec, refused = resolve_mesh(data, cap)
    if refused or spec is None:
        return refused or _refuse(cap, "mesh_id required")
    members, dropped_sim = collect_mesh_stations(data, stations, spec)
    quantity = _pick_quantity(members, spec, data.get("quantity") if isinstance(data.get("quantity"), str) else None)
    if not quantity:
        return _refuse(cap, "no recognised quantity on this mesh", mesh_id=spec["id"])
    train: list[tuple[float, float, float]] = []
    citations: list[dict[str, Any]] = []
    for station in members:
        number = _quantity_value(station, quantity)
        coords = _finite_lat_lon(station)
        if coords is None or number is None:
            continue
        lat, lon = coords
        train.append((lat, lon, number))
        citations.append(_citation(station, quantity))
    if len(train) < 3:
        return _refuse(
            cap,
            f"need 3 LIVE readings of {quantity} to fit a spatial posterior; got {len(train)}",
            mesh_id=spec["id"],
            quantity=quantity,
        )
    try:
        length_km = float(data["length_km"]) if data.get("length_km") is not None else 120.0
    except (TypeError, ValueError):
        return _refuse(cap, "length_km must be a number", mesh_id=spec["id"])
    if not math.isfinite(length_km) or not (5.0 <= length_km <= 2000.0):
        return _refuse(cap, "length_km must be a finite number from 5 to 2000", mesh_id=spec["id"])
    query = None
    posterior = None
    if data.get("lat") is not None and data.get("lon") is not None:
        try:
            qlat, qlon = float(data["lat"]), float(data["lon"])
        except (TypeError, ValueError):
            return _refuse(cap, "lat and lon must be numbers", mesh_id=spec["id"])
        if not (
            math.isfinite(qlat) and math.isfinite(qlon)
            and -90.0 <= qlat <= 90.0 and -180.0 <= qlon <= 180.0
        ):
            return _refuse(cap, "lat and lon must be finite coordinates", mesh_id=spec["id"])
        query = {"lat": qlat, "lon": qlon}
        fit = rbf_gp_posterior(train, [(qlat, qlon)], length_km=length_km)[0]
        posterior = {
            "lat": fit["lat"],
            "lon": fit["lon"],
            "mean": fit["mean"],
            "std": fit["std"],
            "variance": fit["variance"],
        }
    suggest = None
    candidates: list[tuple[str, float, float]] = []
    trained_ids = {c["id"] for c in citations}
    for station in members:
        sid = str(station.get("id") or "")
        if sid in trained_ids:
            continue
        coords = _finite_lat_lon(station)
        if coords is None:
            continue
        lat, lon = coords
        candidates.append((sid, lat, lon))
    if not candidates:
        lats = [t[0] for t in train]
        lons = [t[1] for t in train]
        candidates.append(("bbox-corner", min(lats), min(lons)))
        candidates.append(("bbox-corner", max(lats), max(lons)))
        candidates.append(("bbox-corner", min(lats), max(lons)))
        candidates.append(("bbox-corner", max(lats), min(lons)))
    posts = rbf_gp_posterior(
        train, [(lat, lon) for _, lat, lon in candidates], length_km=length_km
    )
    best_i = max(range(len(posts)), key=lambda i: posts[i]["variance"])
    sid, slat, slon = candidates[best_i]
    suggest = {
        "id": sid,
        "lat": slat,
        "lon": slon,
        "posterior_std": posts[best_i]["std"],
        "reason": "highest posterior variance among unobserved candidates",
    }
    payload = {
        "ok": True,
        "capability_id": cap,
        "sku": cap,
        "generated_at": utc_now(),
        "mesh_id": spec["id"],
        "artifact_type": "spatial_gp_snapshot",
        "claim_class": spec["claim_class"],
        "quantity": quantity,
        "query": query,
        "posterior": posterior,
        "suggest": suggest,
        "train_count": len(train),
        "sibling_oracle": "gauss.field@v1",
        "citations": citations,
        "limitations": _limitations(spec, [
            "Interpolates the current LIVE snapshot. Not a forecast, not a met-service nowcast, not a 1-D time-series EI.",
            f"Dropped {dropped_sim} SIM pin(s). RBF length-scale {length_km} km (haversine).",
        ]),
        "attribution": [spec["attribution"], spec["licence"]],
    }
    return _finish(payload, cap)


def field_shape(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    cap = "atlas.field.shape@v1"
    spec, refused = resolve_mesh(data, cap)
    if refused or spec is None:
        return refused or _refuse(cap, "mesh_id required")
    members, dropped_sim = collect_mesh_stations(data, stations, spec)
    points: list[tuple[float, float]] = []
    citations: list[dict[str, Any]] = []
    for station in members:
        coords = _finite_lat_lon(station)
        if coords is None:
            continue
        points.append(coords)
        citations.append(_citation(station, None))
    if len(points) < 3:
        return _refuse(
            cap,
            f"need 3 LIVE pins to describe shape; got {len(points)}",
            mesh_id=spec["id"],
        )
    try:
        max_km = float(data["max_km"]) if data.get("max_km") is not None else 400.0
    except (TypeError, ValueError):
        return _refuse(cap, "max_km must be a number", mesh_id=spec["id"])
    if not math.isfinite(max_km) or not (10.0 <= max_km <= 2000.0):
        return _refuse(cap, "max_km must be a finite number from 10 to 2000", mesh_id=spec["id"])
    homology = h0_persistence(points, max_km=max_km)
    payload = {
        "ok": True,
        "capability_id": cap,
        "sku": cap,
        "generated_at": utc_now(),
        "mesh_id": spec["id"],
        "artifact_type": "field_h0_shape",
        "claim_class": spec["claim_class"],
        "homology": homology,
        "sibling_oracle": homology["sibling_oracle"],
        "live_count": len(points),
        "citations": citations,
        "limitations": _limitations(spec, [
            "H0 only (connected components vs radius). Loops (Betti-1) are not computed — buy betti.homology@v1 on the same coordinates if you need them.",
            "Shape of station locations, not of the measured field unless you filter device_ids.",
            f"Dropped {dropped_sim} SIM pin(s).",
        ]),
        "attribution": [spec["attribution"], spec["licence"]],
    }
    return _finish(payload, cap)


__all__ = [
    "FIELD_PRODUCT_CAPS",
    "mesh_catalog",
    "mesh_sample",
    "field_consensus",
    "field_posterior",
    "field_shape",
]
