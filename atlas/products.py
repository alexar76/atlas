"""ATLAS composite products — more than the sum of GAIA pins.

Ship-first Hub SKUs (fail-closed LIVE honesty):

* ``atlas.watchbox.check@v1`` — evaluate a subscribed bbox (plumbing / agent poll)
* ``atlas.fire.weather@v1`` — FIRMS hotspot cluster + nearest weather context
* ``atlas.situation.brief@v1`` — multi-layer scored brief with citations
* ``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s) on allowlisted layers

These are billable *decision artifacts*, not raw sensor resale.
GAIA reads stay operator-anchored (``device_id``); coordinate queries live on ATLAS.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from . import __version__
from .formatters import headline
from .geo import in_bbox, normalize_bbox, utc_now
from .stations import LAYER_META
from .watchboxes import ALLOWED_WATCHBOX_LAYERS, STORE, evaluate_watchbox

# ── Catalog ───────────────────────────────────────────────────────────────────

PRODUCT_CAPS: list[dict[str, Any]] = [
    {
        "capability_id": "atlas.watchbox.check@v1",
        "name": "atlas.watchbox.check@v1",
        "description": (
            "Evaluate an ATLAS watchbox (bbox + layers) against the live fleet snapshot. "
            "Returns matches with LIVE/SIM flags and a content receipt. Agent poll SKU."
        ),
        "price_per_call_usd": 0.02,
        "p50_latency_ms": 80,
        "input_schema": {
            "type": "object",
            "properties": {
                "watchbox_id": {"type": "string"},
                "west": {"type": "number"},
                "south": {"type": "number"},
                "east": {"type": "number"},
                "north": {"type": "number"},
                "layers": {"type": "array", "items": {"type": "string"}},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.fire.weather@v1",
        "name": "atlas.fire.weather@v1",
        "description": (
            "Wildfire situation note: NASA FIRMS hotspot cluster in a bbox plus nearest "
            "LIVE weather (wind/humidity/temp). Cite NASA FIRMS. Refuse if no LIVE fire."
        ),
        "price_per_call_usd": 0.08,
        "p50_latency_ms": 200,
        "input_schema": {
            "type": "object",
            "properties": {
                "west": {"type": "number"},
                "south": {"type": "number"},
                "east": {"type": "number"},
                "north": {"type": "number"},
                "limit": {"type": "integer"},
                "include_air": {"type": "boolean"},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.situation.brief@v1",
        "name": "atlas.situation.brief@v1",
        "description": (
            "Cross-layer situation brief for a bbox: score, drivers, and cited LIVE pins "
            "across allowlisted ATLAS layers. Fail-closed when coverage is empty."
        ),
        "price_per_call_usd": 0.06,
        "p50_latency_ms": 150,
        "input_schema": {
            "type": "object",
            "properties": {
                "west": {"type": "number"},
                "south": {"type": "number"},
                "east": {"type": "number"},
                "north": {"type": "number"},
                "layers": {"type": "array", "items": {"type": "string"}},
                "max_citations": {"type": "integer"},
                "locale": {"type": "string"},
            },
            "required": ["west", "south", "east", "north"],
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.nearest.read@v1",
        "name": "atlas.nearest.read@v1",
        "description": (
            "Nearest LIVE ATLAS pin(s) to a lat/lon on allowlisted layers. Returns distance_km, "
            "values, and a content receipt. Fail-closed if nothing LIVE is within max_km. "
            "Coordinate queries live on ATLAS — GAIA reads stay device_id-anchored."
        ),
        "price_per_call_usd": 0.03,
        "p50_latency_ms": 60,
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "query latitude (−90…90)"},
                "lon": {"type": "number", "description": "query longitude (−180…180)"},
                "layer": {"type": "string", "description": "single layer (alias of layers=[…])"},
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "layers to search (default: weather)",
                },
                "max_km": {
                    "type": "number",
                    "description": "refuse if nearest LIVE is farther than this (default 2500)",
                },
                "per_layer": {
                    "type": "boolean",
                    "description": "if true, return nearest LIVE pin for each requested layer",
                },
            },
            "required": ["lat", "lon"],
        },
        "product_id": "atlas.products",
    },
]

CAP_BY_ID = {str(c["capability_id"]): c for c in PRODUCT_CAPS}


def make_receipt(payload: dict[str, Any], *, capability_id: str) -> dict[str, Any]:
    """Tamper-evident content receipt.

    sha256 alone is forgeable by anyone who edits the payload and recomputes;
    the Ed25519 signature over the canonical body (same key as the manifest)
    is what makes the receipt attributable to this ATLAS instance.
    """
    body = {k: v for k, v in payload.items() if k != "receipt"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    receipt = {
        "algorithm": "sha256",
        "digest": digest,
        "service": "atlas",
        "version": __version__,
        "ts": utc_now(),
        "capability_id": capability_id,
    }
    try:
        from .signing import get_signer

        signer = get_signer()
        receipt["signature_alg"] = "ed25519"
        receipt["signature_b64"] = signer.sign_canonical(canonical)
        receipt["public_key_b64"] = signer.public_key_b64
    except Exception:  # noqa: BLE001 — receipts degrade to digest-only
        pass
    return receipt


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _citation(s: dict[str, Any]) -> dict[str, Any]:
    values = s.get("values") if isinstance(s.get("values"), dict) else {}
    layer = str(s.get("layer") or "")
    return {
        "id": s.get("id"),
        "parent_id": s.get("parent_id"),
        "layer": layer,
        "place": s.get("place"),
        "lat": s.get("lat"),
        "lon": s.get("lon"),
        "live": bool(s.get("live")),
        "mode": s.get("mode"),
        "source": s.get("source"),
        "headline": s.get("headline") or headline(layer, values),
        "values": values,
    }


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


def _parse_bbox(data: dict[str, Any]) -> tuple[float, float, float, float] | None:
    keys = ("west", "south", "east", "north")
    if not all(k in data and data[k] is not None for k in keys):
        return None
    try:
        return normalize_bbox(
            float(data["west"]),
            float(data["south"]),
            float(data["east"]),
            float(data["north"]),
        )
    except (TypeError, ValueError):
        return None


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
        row = STORE.get(wid)
        if not row:
            return {
                "ok": False,
                "capability_id": "atlas.watchbox.check@v1",
                "refuse_reason": f"unknown watchbox: {wid}",
            }
        result = evaluate_watchbox(row, stations)
    else:
        bbox = _parse_bbox(data)
        layers = _normalize_layer_list(data.get("layers"))
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
    payload["receipt"] = make_receipt(payload, capability_id="atlas.watchbox.check@v1")
    return payload


def fire_weather(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.fire.weather@v1`` — FIRMS cluster + nearest weather (optional air)."""
    bbox = _parse_bbox(data)
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

    fire_all = _stations_in_bbox(
        stations, west=west, south=south, east=east, north=north, layers={"fire"}
    )
    live_fire = [s for s in fire_all if s.get("live") and (s.get("values") or s.get("has_reading"))]
    if not live_fire:
        return {
            "ok": False,
            "capability_id": "atlas.fire.weather@v1",
            "refuse_reason": "no LIVE fire readings in bbox (sparse ≠ covered)",
            "bbox": {"west": west, "south": south, "east": east, "north": north},
            "attribution": "NASA FIRMS — cite NASA FIRMS / disclaimer when publishing",
        }

    def _bright(s: dict[str, Any]) -> float:
        vals = s.get("values") if isinstance(s.get("values"), dict) else {}
        try:
            return float(vals.get("brightness_k") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    live_fire.sort(key=_bright, reverse=True)
    hotspots = [_citation(s) for s in live_fire[:limit]]
    anchor = live_fire[0]
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
        d = _haversine_km(alat, alon, lat, lon)
        if nearest_km is None or d < nearest_km:
            nearest_km = d
            nearest_wx = s

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
            d = _haversine_km(alat, alon, lat, lon)
            if air_km is None or d < air_km:
                air_km = d
                nearest_air = s

    wx_vals = (nearest_wx or {}).get("values") if nearest_wx else {}
    wx_vals = wx_vals if isinstance(wx_vals, dict) else {}
    wind = wx_vals.get("wind_mps")
    humidity = wx_vals.get("humidity_pct")
    temp = wx_vals.get("temperature_c")

    drivers: list[str] = [
        f"{len(hotspots)} LIVE FIRMS hotspot(s) in bbox (of {len(live_fire)} total)",
    ]
    if nearest_wx and nearest_km is not None:
        drivers.append(
            f"nearest LIVE weather {nearest_wx.get('id')} @ {nearest_km:.0f} km "
            f"(wind={wind}, humidity={humidity}, temp_c={temp})"
        )
    else:
        drivers.append("no LIVE weather pin available for context")

    # Lightweight desk score — not a forecast model.
    score = 40
    score += min(30, len(live_fire) * 2)
    top_b = _bright(anchor)
    if top_b >= 350:
        score += 15
    elif top_b >= 320:
        score += 8
    try:
        if wind is not None and float(wind) >= 8:
            score += 10
            drivers.append("elevated wind supports spread concern (context only)")
        if humidity is not None and float(humidity) <= 30:
            score += 8
            drivers.append("low humidity supports fire-weather concern (context only)")
    except (TypeError, ValueError):
        pass
    score = max(0, min(100, score))

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.fire.weather@v1",
        "sku": "atlas.fire.weather@v1",
        "generated_at": utc_now(),
        "bbox": {"west": west, "south": south, "east": east, "north": north},
        "score": score,
        "risk_note": (
            f"Wildfire desk note: {len(live_fire)} LIVE hotspot(s); "
            f"brightest {top_b:.0f} K at {alat:.2f},{alon:.2f}. "
            "Not an evacuation order or forecast — attested context only."
        ),
        "drivers": drivers,
        "hotspots": hotspots,
        "hotspot_count": len(live_fire),
        "weather": _citation(nearest_wx) if nearest_wx else None,
        "weather_distance_km": round(nearest_km, 1) if nearest_km is not None else None,
        "air": _citation(nearest_air) if nearest_air else None,
        "air_distance_km": round(air_km, 1) if air_km is not None else None,
        "attribution": "NASA FIRMS VIIRS — cite NASA FIRMS / disclaimer",
    }
    payload["receipt"] = make_receipt(payload, capability_id="atlas.fire.weather@v1")
    return payload


def situation_brief(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.situation.brief@v1`` — multi-layer scored brief with citations."""
    bbox = _parse_bbox(data)
    if bbox is None:
        return {
            "ok": False,
            "capability_id": "atlas.situation.brief@v1",
            "refuse_reason": "west/south/east/north bbox required",
        }
    west, south, east, north = bbox
    layers = _normalize_layer_list(data.get("layers"))
    if not layers:
        layers = [
            k
            for k in (
                "weather", "air", "fire", "quake", "jamming", "radiation",
                "tide", "river", "marine", "grid", "traffic",
            )
            if k in LAYER_META
        ]
    try:
        max_citations = int(data.get("max_citations") or 24)
    except (TypeError, ValueError):
        max_citations = 24
    max_citations = max(4, min(max_citations, 48))

    layer_set = set(layers)
    inside = _stations_in_bbox(
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
            "coverage": coverage,
        }

    # Rank citations: LIVE + hazard layers first, then brightness/magnitude.
    _HAZARD = {"fire", "quake", "jamming", "radiation", "traffic"}

    def _rank(s: dict[str, Any]) -> tuple[int, int, float, str]:
        layer = str(s.get("layer") or "")
        live_b = 1 if s.get("live") else 0
        haz = 1 if layer in _HAZARD else 0
        vals = s.get("values") if isinstance(s.get("values"), dict) else {}
        weight = 0.0
        for key in ("brightness_k", "magnitude", "severity_score", "cpm", "wind_mps"):
            try:
                if vals.get(key) is not None:
                    weight = max(weight, float(vals[key]))
            except (TypeError, ValueError):
                pass
        return (-live_b, -haz, -weight, str(s.get("id") or ""))

    ranked = sorted(with_reading, key=_rank)
    citations = [_citation(s) for s in ranked[:max_citations]]

    drivers: list[str] = []
    score = 35
    live_layers = {str(s.get("layer")) for s in live}
    score += min(25, len(live_layers) * 6)
    drivers.append(f"{len(live)} LIVE reading(s) across {len(live_layers)} layer(s)")

    for layer in ("fire", "quake", "jamming", "radiation"):
        n = coverage.get(layer, {}).get("live", 0)
        if n:
            score += min(12, 4 + n)
            drivers.append(f"{layer}: {n} LIVE pin(s) in bbox")

    # Cross-layer links (explicit, evidence-bound).
    if coverage.get("fire", {}).get("live") and coverage.get("weather", {}).get("live"):
        drivers.append("fire + weather both LIVE in bbox — fused wildfire context available")
        score += 5
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
        "score": score,
        "summary": (
            f"Situation brief: score {score}/100 from {len(live)} LIVE citation(s) "
            f"in bbox across {len(live_layers)} layer(s). Not a forecast or insurance trigger."
        ),
        "drivers": drivers,
        "coverage": coverage,
        "citations": citations,
        "citation_count": len(citations),
        "live_count": len(live),
    }
    payload["receipt"] = make_receipt(payload, capability_id="atlas.situation.brief@v1")
    return payload


def _parse_query_point(data: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


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
        d = _haversine_km(lat, lon, slat, slon)
        if best_km is None or d < best_km:
            best_km = d
            best = s
    return best, best_km


def nearest_read(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s)."""
    point = _parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.nearest.read@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    layers = _nearest_layers(data)
    if not layers:
        return {
            "ok": False,
            "capability_id": "atlas.nearest.read@v1",
            "refuse_reason": (
                "no valid layers requested — allowed: "
                + ", ".join(sorted(ALLOWED_WATCHBOX_LAYERS))
            ),
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
            pin, dist = _nearest_candidate(stations, lat=lat, lon=lon, layers={layer})
            if pin is None or dist is None or dist > max_km:
                by_layer[layer] = None
                continue
            hits += 1
            by_layer[layer] = {
                **_citation(pin),
                "distance_km": round(dist, 2),
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
        payload["receipt"] = make_receipt(payload, capability_id="atlas.nearest.read@v1")
        return payload

    pin, dist = _nearest_candidate(stations, lat=lat, lon=lon, layers=set(layers))
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
            **_citation(pin),
            "distance_km": round(dist, 2),
        },
        "distance_km": round(dist, 2),
        "layer": pin.get("layer"),
        "values": (pin.get("values") if isinstance(pin.get("values"), dict) else {}),
    }
    payload["receipt"] = make_receipt(payload, capability_id="atlas.nearest.read@v1")
    return payload


def invoke_product(capability_id: str, data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """Route a Hub-style invoke to a composite product handler."""
    cap = str(capability_id or "").strip()
    if cap not in CAP_BY_ID:
        return {"ok": False, "refuse_reason": f"unknown capability: {cap}"}
    if not isinstance(data, dict):
        data = {}
    if cap == "atlas.watchbox.check@v1":
        return watchbox_check(data, stations)
    if cap == "atlas.fire.weather@v1":
        return fire_weather(data, stations)
    if cap == "atlas.situation.brief@v1":
        return situation_brief(data, stations)
    if cap == "atlas.nearest.read@v1":
        return nearest_read(data, stations)
    return {"ok": False, "refuse_reason": f"unhandled capability: {cap}"}


__all__ = [
    "PRODUCT_CAPS",
    "CAP_BY_ID",
    "make_receipt",
    "watchbox_check",
    "fire_weather",
    "situation_brief",
    "nearest_read",
    "invoke_product",
]
