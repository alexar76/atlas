"""The product catalogue: situation-brief defaults and presets, the receipt output schema, and
every product capability ATLAS sells.
"""

from __future__ import annotations

from typing import Any


# Default layers for atlas.situation.brief@v1 when the buyer omits `layers`.
# Keep in LAYER_META. Not spacewx/geomag/argo (planetary pin / ocean float).
SITUATION_BRIEF_DEFAULT_LAYERS: tuple[str, ...] = (
    "weather", "air", "fire", "effis", "lightning", "alerts", "flood",
    "events", "volcano", "quake", "jamming", "radiation",
    "tide", "river", "marine", "grid", "traffic", "ais", "tsunami",
    "cyclone", "adsb",
)


# Named desks over the same rail. Every paying invoke this hub has recorded went to
# the generic brief, and a buyer who wants a berth-window answer had to know which of
# 39 layers to ask for. A preset is the job title, not a discount: same price, fixed
# layer set, and a stated scope so an empty answer is a coverage fact rather than a
# guess about what the caller meant. `layers` still wins when both are supplied.
SITUATION_BRIEF_PRESETS: dict[str, dict[str, Any]] = {
    "port_desk": {
        "layers": (
            "tide", "marine", "river", "flood", "alerts", "cyclone", "ais",
            "weather", "tsunami",
        ),
        "scope": (
            "Berth and approach conditions. Tide/river/marine gauges are point stations "
            "and AIS is public coastal coverage (Finnish and Norwegian waters) — this is "
            "not a pilotage decision, a draught calculation, or a port closure order."
        ),
    },
    "corridor": {
        "layers": (
            "flood", "river", "quake", "alerts", "fire", "effis", "weather", "traffic",
        ),
        "scope": (
            "Linear rail/road corridor exposure from a bbox around the route. Hazard pins "
            "are upstream event feeds, not a track-level inspection or a speed order."
        ),
    },
    "cat_desk": {
        "layers": (
            "fire", "effis", "flood", "quake", "volcano", "cyclone", "events", "alerts",
        ),
        "scope": (
            "Catastrophe-desk daily exposure digest for a territory. Event feeds are "
            "published detections and advisories — not a loss estimate, a parametric "
            "trigger, or an insurability opinion."
        ),
    },
    "campus": {
        "layers": (
            "weather", "air", "flood", "river", "alerts", "grid", "lightning",
        ),
        "scope": (
            "Named building, campus, or colo bbox. Weather and air are public-sensor "
            "nowcasts; flood warnings and river gauges stay in separate lists — this is "
            "not a BMS, a 50-year siting index, a fire perimeter, or an insurer."
        ),
    },
}


# ── Catalog ───────────────────────────────────────────────────────────────────

# Every product payload carries the same content receipt (see ``make_receipt``), so the
# shape is declared once and referenced from each capability's output_schema.
_RECEIPT_OUT: dict[str, Any] = {
    "type": "object",
    "description": (
        "Tamper-evident content receipt: sha256 over the canonical payload, hybrid-signed "
        "with Ed25519 and, when enabled, ML-DSA-65 using the same identities as the manifest. "
        "`signature_status` says whether the signature is present — a digest alone is not "
        "attributable."
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


# Output schemas mirror what the handlers below actually build. They were absent
# entirely, so all six SKUs reached the public hub manifest with `output_schema: {}` —
# priced, discoverable decision artifacts whose result shape a buyer could only learn by
# paying for one. A capability that cannot say what it returns cannot be composed.
PRODUCT_CAPS: list[dict[str, Any]] = [
    {
        "capability_id": "atlas.watchbox.check@v1",
        "name": "atlas.watchbox.check@v1",
        "description": (
            "Evaluate an ATLAS watchbox (bbox + layers) against the live fleet snapshot. "
            "Returns matches with LIVE/SIM flags and a content receipt. Agent poll SKU. "
            "Pass bbox+layers for an ephemeral check, or watchbox_id + owner_token to "
            "check a stored subscription."
        ),
        "price_per_call_usd": 0.02,
        "p50_latency_ms": 80,
        "input_schema": {
            "type": "object",
            "properties": {
                "watchbox_id": {"type": "string"},
                "owner_token": {
                    "type": "string",
                    "description": (
                        "Owner token issued once when the watchbox was created. "
                        "Required with watchbox_id; not used for ephemeral bbox checks."
                    ),
                },
                "west": {"type": "number"},
                "south": {"type": "number"},
                "east": {"type": "number"},
                "north": {"type": "number"},
                "layers": {"type": "array", "items": {"type": "string"}},
            },
            # The two ways in, said in schema rather than only in the description above.
            # A flat `required` list cannot express "either a stored subscription or a
            # bare bbox", so this capability declared nothing required at all — and a hub
            # brokering it had no basis to refuse a call that was obviously short. Every
            # such call crossed the network to be told "bbox or watchbox_id required",
            # which is a second spent to deliver a sentence the schema already knew.
            "anyOf": [
                {"required": ["watchbox_id", "owner_token"]},
                {"required": ["west", "south", "east", "north"]},
            ],
        },
        "output_schema": {
            "type": "object",
            "description": "Watchbox evaluation against the live fleet snapshot. On refusal the payload carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query where one was parsed).",
            "required": [
                "ok"
            ],
            "properties": {
                "ok": {
                    "type": "boolean"
                },
                "capability_id": {
                    "type": "string"
                },
                "sku": {
                    "type": "string"
                },
                "evaluated_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "receipt": _RECEIPT_OUT,
                "refuse_reason": {
                    "type": "string"
                },
                "watchbox_id": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "bbox": {
                    "type": "object",
                    "properties": {
                        "west": {
                            "type": "number"
                        },
                        "south": {
                            "type": "number"
                        },
                        "east": {
                            "type": "number"
                        },
                        "north": {
                            "type": "number"
                        }
                    }
                },
                "layers": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "match_count": {
                    "type": "integer",
                    "minimum": 0
                },
                "live_match_count": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Subset of matches whose pin is LIVE, not simulated."
                },
                "matches": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    }
                }
            }
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.fire.weather@v1",
        "name": "atlas.fire.weather@v1",
        "description": (
            "Fire + weather evidence snapshot: NASA FIRMS thermal-anomaly detections and/or "
            "Copernicus EFFIS current-fire polygons in a bbox, plus nearby LIVE weather. "
            "Not a forecast or risk rating. Dual attribution (NASA FIRMS / Copernicus EMS). "
            "Refuse if neither LIVE fire class is present."
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
                "max_weather_km": {"type": "number", "minimum": 1, "maximum": 1000},
                "max_air_km": {"type": "number", "minimum": 1, "maximum": 1000},
            },
        },
        "output_schema": {
            "type": "object",
            "description": "Fire + weather evidence snapshot. Not a perimeter, forecast or risk rating. On refusal the payload carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query where one was parsed).",
            "required": [
                "ok"
            ],
            "properties": {
                "ok": {
                    "type": "boolean"
                },
                "capability_id": {
                    "type": "string"
                },
                "sku": {
                    "type": "string"
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "receipt": _RECEIPT_OUT,
                "refuse_reason": {
                    "type": "string"
                },
                "bbox": {
                    "type": "object",
                    "properties": {
                        "west": {
                            "type": "number"
                        },
                        "south": {
                            "type": "number"
                        },
                        "east": {
                            "type": "number"
                        },
                        "north": {
                            "type": "number"
                        }
                    }
                },
                "artifact_type": {
                    "type": "string"
                },
                "summary": {
                    "type": "string"
                },
                "drivers": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "evidence": {
                    "type": "object",
                    "properties": {
                        "live_fire_detection_count": {
                            "type": "integer"
                        },
                        "returned_detection_count": {
                            "type": "integer"
                        },
                        "live_effis_count": {
                            "type": "integer"
                        },
                        "returned_effis_count": {
                            "type": "integer"
                        },
                        "nearby_weather_available": {
                            "type": "boolean"
                        }
                    }
                },
                "limitations": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "hotspots": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    },
                    "description": "NASA FIRMS thermal-anomaly detections."
                },
                "hotspot_count": {
                    "type": "integer",
                    "minimum": 0
                },
                "effis_fires": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    },
                    "description": "Copernicus EFFIS current-fire polygons."
                },
                "effis_count": {
                    "type": "integer",
                    "minimum": 0
                },
                "weather": {
                    "type": [
                        "object",
                        "null"
                    ],
                    "description": "Source-attributed pin: id, layer, source, coordinates, values."
                },
                "weather_distance_km": {
                    "type": [
                        "number",
                        "null"
                    ]
                },
                "max_weather_km": {
                    "type": "number"
                },
                "nearest_weather_candidate": {
                    "type": [
                        "object",
                        "null"
                    ],
                    "description": "Source-attributed pin: id, layer, source, coordinates, values."
                },
                "nearest_weather_candidate_distance_km": {
                    "type": [
                        "number",
                        "null"
                    ]
                },
                "air": {
                    "type": [
                        "object",
                        "null"
                    ],
                    "description": "Source-attributed pin: id, layer, source, coordinates, values."
                },
                "air_distance_km": {
                    "type": [
                        "number",
                        "null"
                    ]
                },
                "max_air_km": {
                    "type": "number"
                },
                "nearest_air_candidate": {
                    "type": [
                        "object",
                        "null"
                    ],
                    "description": "Source-attributed pin: id, layer, source, coordinates, values."
                },
                "nearest_air_candidate_distance_km": {
                    "type": [
                        "number",
                        "null"
                    ]
                },
                "attribution": {
                    "type": "string",
                    "description": "Required licence attribution for the sources used."
                }
            }
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.smoke.operations@v1",
        "name": "atlas.smoke.operations@v1",
        "description": (
            "Asset-coordinate Smoke Operations Brief: exact point-in-polygon against the "
            "complete Ed25519-bound NOAA HMS smoke geometry inventory, fused with licensed "
            "Open-Meteo PM2.5 and US/European AQI at the same coordinate. Returns the matching "
            "geometry and operational evidence; refuses on truncated HMS or missing air data. "
            "HMS publishes one dated analysis product per UTC day, so the brief names the "
            "`hms_analysis_date` it read instead of claiming a live pass. "
            "HMS is qualitative and cloud-limited, not a concentration measurement or evacuation order."
        ),
        "price_per_call_usd": 0.12,
        "p50_latency_ms": 350,
        "input_schema": {
            "type": "object",
            "required": ["lat", "lon"],
            "properties": {
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "asset_id": {"type": "string", "maxLength": 160},
            },
        },
        "output_schema": {
            "type": "object",
            "description": "Exact HMS smoke containment plus colocated modeled PM2.5/AQI evidence.",
            "required": ["ok"],
            "properties": {
                "ok": {"type": "boolean"},
                "capability_id": {"type": "string"},
                "sku": {"type": "string"},
                "generated_at": {"type": "string", "format": "date-time"},
                "receipt": _RECEIPT_OUT,
                "receipt_url": {"type": ["string", "null"]},
                "verifier_url": {"type": ["string", "null"]},
                "refuse_reason": {"type": "string"},
                "query": {"type": "object"},
                "inside_smoke": {"type": "boolean"},
                "operational_status": {"type": "string"},
                "summary": {"type": "string"},
                "drivers": {"type": "array", "items": {"type": "string"}},
                "recommended_actions": {"type": "array", "items": {"type": "string"}},
                "smoke": {"type": "array", "items": {"type": "object"}},
                "smoke_polygon_count": {"type": "integer", "minimum": 0},
                "hms_inventory_total": {"type": "integer", "minimum": 1},
                "hms_inventory_complete": {"type": "boolean"},
                "hms_analysis_date": {
                    "type": ["string", "null"],
                    "description": "UTC day of the HMS analysis product containment was decided against.",
                },
                "hms_analysis_age_hours": {"type": ["number", "null"], "minimum": 0},
                "air_quality": {"type": "object"},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "attribution": {"type": "array", "items": {"type": "string"}},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.situation.brief@v1",
        "name": "atlas.situation.brief@v1",
        "description": (
            "Cross-layer situation brief for a bbox: score, drivers, and cited LIVE pins "
            "across map layers (flood, EFFIS, lightning, volcano, alerts, events, public AIS, "
            "tsunami included by default). `preset` selects a named desk — port_desk, "
            "corridor or cat_desk — which fixes the layer set and returns the scope that "
            "answer is valid for; an explicit `layers` list overrides it. Fail-closed when "
            "coverage is empty. Not a forecast or insurance trigger."
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
                "preset": {
                    "type": "string",
                    "enum": ["port_desk", "corridor", "cat_desk"],
                    "description": (
                        "Named desk: fixes the layer set and states the scope the answer is "
                        "valid for. Ignored when `layers` is supplied. An unknown value is "
                        "refused rather than silently answered with the default layer set."
                    ),
                },
                "max_citations": {"type": "integer"},
                "locale": {"type": "string"},
            },
            "required": ["west", "south", "east", "north"],
        },
        "output_schema": {
            "type": "object",
            "description": "Cross-layer situation brief for a bbox. Not a forecast or insurance trigger. On refusal the payload carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query where one was parsed).",
            "required": [
                "ok"
            ],
            "properties": {
                "ok": {
                    "type": "boolean"
                },
                "capability_id": {
                    "type": "string"
                },
                "sku": {
                    "type": "string"
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "receipt": _RECEIPT_OUT,
                "refuse_reason": {
                    "type": "string"
                },
                "bbox": {
                    "type": "object",
                    "properties": {
                        "west": {
                            "type": "number"
                        },
                        "south": {
                            "type": "number"
                        },
                        "east": {
                            "type": "number"
                        },
                        "north": {
                            "type": "number"
                        }
                    }
                },
                "layers": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "preset": {
                    "type": ["string", "null"],
                    "description": "Named desk this brief was built for, or null for the default layer set."
                },
                "preset_scope": {
                    "type": ["string", "null"],
                    "description": "What the named desk's answer is, and is not, valid for."
                },
                "preset_overridden": {
                    "type": ["string", "null"],
                    "description": "Preset that was supplied but not applied because an explicit `layers` list won."
                },
                "score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100
                },
                "summary": {
                    "type": "string"
                },
                "drivers": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "coverage": {
                    "type": "object"
                },
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    },
                    "description": "LIVE pins the score was computed from."
                },
                "citation_count": {
                    "type": "integer",
                    "minimum": 0
                },
                "live_count": {
                    "type": "integer",
                    "minimum": 0
                }
            }
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
        "output_schema": {
            "type": "object",
            "description": "Nearest LIVE pin(s) on allowlisted layers. Single-nearest by default; `per_layer` returns one per layer and replaces `nearest` with `nearest_by_layer`. On refusal the payload carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query where one was parsed).",
            "required": [
                "ok"
            ],
            "properties": {
                "ok": {
                    "type": "boolean"
                },
                "capability_id": {
                    "type": "string"
                },
                "sku": {
                    "type": "string"
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "receipt": _RECEIPT_OUT,
                "refuse_reason": {
                    "type": "string"
                },
                "query": {
                    "type": "object",
                    "properties": {
                        "lat": {
                            "type": "number"
                        },
                        "lon": {
                            "type": "number"
                        },
                        "layers": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        },
                        "max_km": {
                            "type": "number"
                        },
                        "per_layer": {
                            "type": "boolean"
                        }
                    }
                },
                "nearest": {
                    "type": "object",
                    "description": "Single-nearest mode only."
                },
                "distance_km": {
                    "type": "number"
                },
                "layer": {
                    "type": [
                        "string",
                        "null"
                    ]
                },
                "values": {
                    "type": "object"
                },
                "nearest_by_layer": {
                    "type": "object",
                    "description": "`per_layer` mode only."
                },
                "hit_count": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "`per_layer` mode only."
                }
            }
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.point.read@v1",
        "name": "atlas.point.read@v1",
        "description": (
            "Read one exact clickable ATLAS map object by stable point_id. Returns the same "
            "values and provenance boundary as the map detail, the parent GAIA capability, "
            "and an Ed25519-attributed ATLAS content receipt. Catalog sensors and targeted "
            "platforms refresh at source; event pixels are selected from the latest source snapshot."
        ),
        "price_per_call_usd": 0.01,
        "p50_latency_ms": 90,
        "input_schema": {
            "type": "object",
            "properties": {
                "point_id": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 160,
                    "description": "exact id exposed by ATLAS viewport/nearest/map detail",
                },
                "fresh": {
                    "type": "boolean",
                    "description": (
                        "bypass the ATLAS freshness cache for source-addressable points "
                        "(default false; separately rate-limited)"
                    ),
                    "default": False,
                },
            },
            "required": ["point_id"],
        },
        "output_schema": {
            "type": "object",
            "description": "Addressable evidence object for one ATLAS point_id. On refusal the payload carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query where one was parsed).",
            "required": [
                "ok"
            ],
            "properties": {
                "ok": {
                    "type": "boolean"
                },
                "capability_id": {
                    "type": "string"
                },
                "sku": {
                    "type": "string"
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "receipt": _RECEIPT_OUT,
                "refuse_reason": {
                    "type": "string"
                },
                "point_id": {
                    "type": "string"
                },
                "point": {
                    "type": "object"
                },
                "resolution": {
                    "type": "object",
                    "properties": {
                        "kind": {
                            "type": "string",
                            "enum": [
                                "derived_integrity_cell",
                                "source_snapshot_selection",
                                "source_addressable_read"
                            ]
                        },
                        "fresh_requested": {
                            "type": "boolean"
                        },
                        "evidence_boundary": {
                            "type": "string"
                        }
                    }
                },
                "parent_capability": {
                    "type": [
                        "object",
                        "null"
                    ],
                    "description": "The capability that refreshes this point's cluster."
                },
                "point_invoke": {
                    "type": "object",
                    "description": "Ready-made invoke for this point."
                }
            }
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.geomag.window@v1",
        "name": "atlas.geomag.window@v1",
        "description": (
            "Geomagnetic operations window for one coordinate: NOAA SWPC planetary Kp "
            "mapped to the published NOAA state and G-scale, the nearest LIVE USGS "
            "observatory (distance, total field F, observation age) for corroboration, and "
            "the nearest OVATION aurora cell. Refuses when no LIVE Kp is available. "
            "Total field only — this is NOT a magnetic-declination correction, not an "
            "IFR-grade in-field reference, and not a safety-of-life service."
        ),
        "price_per_call_usd": 0.05,
        "p50_latency_ms": 120,
        "input_schema": {
            "type": "object",
            "required": ["lat", "lon"],
            "properties": {
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "max_km": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 20037,
                    "description": (
                        "Radius for observatory and aurora corroboration (default 1500 km). "
                        "Beyond it the window is planetary-only and says so."
                    ),
                },
                "asset_id": {"type": "string", "maxLength": 160},
            },
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "description": (
                "Kp-driven operations window plus local corroboration. On refusal the payload "
                "carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query)."
            ),
            "required": ["ok"],
            "properties": {
                "ok": {"type": "boolean"},
                "capability_id": {"type": "string"},
                "sku": {"type": "string"},
                "generated_at": {"type": "string", "format": "date-time"},
                "receipt": _RECEIPT_OUT,
                "receipt_url": {"type": ["string", "null"]},
                "verifier_url": {"type": ["string", "null"]},
                "refuse_reason": {"type": "string"},
                "query": {"type": "object"},
                "kp_index": {"type": "number", "minimum": 0, "maximum": 9},
                "kp_state": {
                    "type": "string",
                    "enum": [
                        "quiet", "unsettled", "active", "minor_storm",
                        "moderate_storm", "strong_storm", "severe_storm", "extreme_storm",
                    ],
                },
                "noaa_g_scale": {"type": ["string", "null"]},
                "window_status": {"type": "string", "enum": ["open", "caution", "hold"]},
                "corroboration": {
                    "type": "string",
                    "enum": ["observatory", "planetary_only"],
                    "description": (
                        "`planetary_only` means no USGS observatory was within `max_km` — the "
                        "network covers United States territory."
                    ),
                },
                "summary": {"type": "string"},
                "drivers": {"type": "array", "items": {"type": "string"}},
                "recommended_actions": {"type": "array", "items": {"type": "string"}},
                "kp_source": {"type": "object"},
                "nearest_observatory": {"type": ["object", "null"]},
                "aurora": {"type": ["object", "null"]},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "attribution": {"type": "array", "items": {"type": "string"}},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.pv.irradiance.record@v1",
        "name": "atlas.pv.irradiance.record@v1",
        "description": (
            "Retrospective irradiance and soiling-driver record for one PV plant "
            "coordinate: NASA POWER daily all-sky vs clear-sky surface irradiation (with "
            "the derived cloud loss), colocated CAMS aerosol optical depth and dust, and "
            "the nearest LIVE weather pin — each with its distance and the POWER record "
            "date. Refuses when no LIVE irradiation reading is within `max_km`. A record "
            "of fact for performance-ratio arguments; NOT a yield forecast, NOT a "
            "soiling-loss model, and NOT a bankable energy assessment (no P50/P90)."
        ),
        "price_per_call_usd": 0.15,
        "p50_latency_ms": 160,
        "input_schema": {
            "type": "object",
            "required": ["lat", "lon"],
            "properties": {
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "max_km": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 2000,
                    "description": (
                        "How far the POWER cell and aerosol reading may be from the plant "
                        "(default 100 km). The answer always reports the actual distance."
                    ),
                },
                "plant_id": {"type": "string", "maxLength": 160},
            },
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "description": (
                "Dated irradiance and aerosol record for one coordinate. On refusal the payload "
                "carries only `ok: false`, `capability_id`, `refuse_reason`, the echoed query and "
                "the nearest candidate distance."
            ),
            "required": ["ok"],
            "properties": {
                "ok": {"type": "boolean"},
                "capability_id": {"type": "string"},
                "sku": {"type": "string"},
                "generated_at": {"type": "string", "format": "date-time"},
                "receipt": _RECEIPT_OUT,
                "receipt_url": {"type": ["string", "null"]},
                "verifier_url": {"type": ["string", "null"]},
                "refuse_reason": {"type": "string"},
                "query": {"type": "object"},
                "nearest_solar_candidate_distance_km": {"type": ["number", "null"]},
                "record_kind": {"type": "string", "enum": ["retrospective_record_of_fact"]},
                "summary": {"type": "string"},
                "irradiance": {"type": "object"},
                "aerosol": {"type": ["object", "null"]},
                "weather": {"type": ["object", "null"]},
                "drivers": {"type": "array", "items": {"type": "string"}},
                "soiling_drivers": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "attribution": {"type": "array", "items": {"type": "string"}},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.route.integrity@v1",
        "name": "atlas.route.integrity@v1",
        "description": (
            "Per-segment route brief over a polyline corridor: the GNSS degradation field "
            "in its route mode, the reported-interference zones the corridor intersects, "
            "LIVE AIS/ADS-B platform presence along it, and the hazard pins beside it — "
            "each with its distance from the route. Refuses only when no component has "
            "evidence in the corridor. Reported interference and station coverage are NOT "
            "proof of jamming or spoofing, and this is not for safety-of-life navigation."
        ),
        "price_per_call_usd": 0.25,
        "p50_latency_ms": 320,
        "input_schema": {
            "type": "object",
            "required": ["route"],
            "properties": {
                "route": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 500,
                    "items": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 2,
                        "items": {"type": "number"},
                    },
                    "description": "Polyline as [lon, lat] pairs, same order as the GNSS SKU.",
                },
                "corridor_km": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Half-width of the corridor around the polyline (default 25 km).",
                },
                "route_id": {"type": "string", "maxLength": 160},
            },
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "description": (
                "Per-segment integrity and hazard brief for one route. On refusal the payload "
                "carries only `ok: false`, `capability_id`, `refuse_reason`, the echoed query "
                "and the GNSS component's own refusal reason."
            ),
            "required": ["ok"],
            "properties": {
                "ok": {"type": "boolean"},
                "capability_id": {"type": "string"},
                "sku": {"type": "string"},
                "generated_at": {"type": "string", "format": "date-time"},
                "receipt": _RECEIPT_OUT,
                "receipt_url": {"type": ["string", "null"]},
                "verifier_url": {"type": ["string", "null"]},
                "refuse_reason": {"type": "string"},
                "query": {"type": "object"},
                "integrity_claim": {
                    "type": "string",
                    "enum": ["reported_interference", "station_coverage_only", "no_gnss_coverage"],
                },
                "summary": {"type": "string"},
                "drivers": {"type": "array", "items": {"type": "string"}},
                "segments": {"type": "array", "items": {"type": "object"}},
                "gnss": {"type": ["object", "null"]},
                "gnss_refuse_reason": {"type": ["string", "null"]},
                "reported_interference": {"type": "array", "items": {"type": "object"}},
                "reported_interference_count": {"type": "integer", "minimum": 0},
                "platform_observations": {"type": "array", "items": {"type": "object"}},
                "platform_observation_counts": {"type": "object"},
                "hazards": {"type": "array", "items": {"type": "object"}},
                "hazard_counts": {"type": "object"},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "attribution": {"type": "array", "items": {"type": "string"}},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.observability.attest@v1",
        "name": "atlas.observability.attest@v1",
        "description": (
            "Data-availability attestation for a coordinate and time window: the nearest "
            "NEXRAD stations with their current status and their ARCHIVED status samples "
            "in that window, the archive's own extent, active CAP alerts and the nearest "
            "weather station. `window_coverage` states whether the window is covered at "
            "all — a gap in the archive is an absence of evidence, NOT evidence the radar "
            "was down. Attests what evidence exists; not reflectivity, not a weather "
            "reconstruction, and not an adjudication of a claim. United States only."
        ),
        "price_per_call_usd": 0.10,
        "p50_latency_ms": 220,
        "input_schema": {
            "type": "object",
            "required": ["lat", "lon"],
            "properties": {
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "start": {
                    "type": "string",
                    "description": "ISO-8601 start of the window; omit for the whole archive.",
                },
                "end": {
                    "type": "string",
                    "description": "ISO-8601 end of the window; omit for the whole archive.",
                },
                "max_km": {"type": "number", "minimum": 1, "maximum": 460},
                "event_id": {"type": "string", "maxLength": 160},
            },
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "description": (
                "What observation evidence exists for a coordinate and window. On refusal the "
                "payload carries only `ok: false`, `capability_id`, `refuse_reason` and the "
                "echoed query."
            ),
            "required": ["ok"],
            "properties": {
                "ok": {"type": "boolean"},
                "capability_id": {"type": "string"},
                "sku": {"type": "string"},
                "generated_at": {"type": "string", "format": "date-time"},
                "receipt": _RECEIPT_OUT,
                "receipt_url": {"type": ["string", "null"]},
                "verifier_url": {"type": ["string", "null"]},
                "refuse_reason": {"type": "string"},
                "query": {"type": "object"},
                "attestation_kind": {"type": "string", "enum": ["data_availability"]},
                "window_coverage": {
                    "type": "object",
                    "description": (
                        "`coverage` is none / partial / recorded. `none` means the archive "
                        "holds no sample for the window — it is not a clean bill of health."
                    ),
                },
                "degraded_sample_count": {"type": "integer", "minimum": 0},
                "summary": {"type": "string"},
                "drivers": {"type": "array", "items": {"type": "string"}},
                "radars": {"type": "array", "items": {"type": "object"}},
                "active_alerts": {"type": "array", "items": {"type": "object"}},
                "weather": {"type": ["object", "null"]},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "attribution": {"type": "array", "items": {"type": "string"}},
            },
        },
        "product_id": "atlas.products",
    },
    {
        "capability_id": "atlas.gnss.degradation.read@v1",
        "name": "atlas.gnss.degradation.read@v1",
        "description": (
            "GNSS integrity field for a point, bbox, or route. Fuses exact public GNSS "
            "station inventory and delivery-path observations with separately labelled interference "
            "events. Returns cells, source observations, coverage, claim classes and a "
            "signed content receipt. A derived degradation is not proof of RF jamming; "
            "cause remains unestablished unless a cited event source states otherwise."
        ),
        "price_per_call_usd": 0.05,
        "p50_latency_ms": 120,
        "input_schema": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "minimum": -90, "maximum": 90},
                "lon": {"type": "number", "minimum": -180, "maximum": 180},
                "west": {"type": "number", "minimum": -180, "maximum": 180},
                "south": {"type": "number", "minimum": -90, "maximum": 90},
                "east": {"type": "number", "minimum": -180, "maximum": 180},
                "north": {"type": "number", "minimum": -90, "maximum": 90},
                "route": {
                    "type": "array", "minItems": 2, "maxItems": 500,
                    "items": {
                        "type": "array", "minItems": 2, "maxItems": 2,
                        "items": {"type": "number"},
                        "description": "[lon, lat]",
                    },
                },
                "corridor_km": {"type": "number", "minimum": 1, "maximum": 1000},
                "max_km": {"type": "number", "minimum": 1, "maximum": 5000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
        },
        "output_schema": {
            "type": "object",
            "description": "GNSS integrity field for a point, bbox or route. Derived degradation is not proof of jamming or spoofing, and is not for safety-of-life navigation. On refusal the payload carries only `ok: false`, `capability_id` and `refuse_reason` (plus the echoed query where one was parsed).",
            "required": [
                "ok"
            ],
            "properties": {
                "ok": {
                    "type": "boolean"
                },
                "capability_id": {
                    "type": "string"
                },
                "sku": {
                    "type": "string"
                },
                "generated_at": {
                    "type": "string",
                    "format": "date-time"
                },
                "receipt": _RECEIPT_OUT,
                "refuse_reason": {
                    "type": "string"
                },
                "query": {
                    "type": "object"
                },
                "grid_scheme": {
                    "type": "string"
                },
                "cells": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    }
                },
                "observations": {
                    "type": "array",
                    "items": {
                        "type": "object"
                    }
                },
                "coverage": {
                    "type": "object",
                    "properties": {
                        "stations": {
                            "type": "integer"
                        },
                        "cells": {
                            "type": "integer"
                        },
                        "reported_interference_events": {
                            "type": "integer"
                        },
                        "unknown_integrity": {
                            "type": "integer"
                        }
                    }
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },
                "evidence_boundary": {
                    "type": "string"
                },
                "source_attributions": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Licence attribution for redistributed CC BY data."
                },
                "limitations": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "summary": {
                    "type": "object",
                    "description": "Spec §7.3 headline. `coverage: none` is never reported as normal.",
                    "properties": {
                        "state": {"type": "string"},
                        "score": {"type": ["number", "null"]},
                        "confidence": {"type": "number"},
                        "coverage": {"type": "string", "enum": ["full", "partial", "none"]},
                        "claim_level": {"type": ["string", "null"]}
                    }
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Per-observation evidence records; empty on refusal."
                },
                "receipt_url": {
                    "type": ["string", "null"]
                },
                "verifier_url": {
                    "type": ["string", "null"]
                }
            }
        },
        "product_id": "atlas.products",
    },
]


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
