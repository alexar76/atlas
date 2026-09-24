"""ATLAS composite products — more than the sum of GAIA pins.

Ship-first Hub SKUs (fail-closed LIVE honesty):

* ``atlas.watchbox.check@v1`` — evaluate a subscribed bbox (plumbing / agent poll)
* ``atlas.fire.weather@v1`` — FIRMS and/or EFFIS + nearest weather context
* ``atlas.situation.brief@v1`` — multi-layer scored brief (defaults to map layers)
* ``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s) on allowlisted layers
* ``atlas.point.read@v1`` — exact ATLAS point_id → addressable evidence object
* ``atlas.gnss.degradation.read@v1`` — point/bbox/route → GNSS integrity field
* ``atlas.mesh.sample@v1`` — Halton sample of a licensed in-situ mesh
* ``atlas.field.consensus@v1`` — Murmuration-equivalent consensus of LIVE in-situ readings
* ``atlas.field.posterior@v1`` — spatial GP posterior of the current snapshot
* ``atlas.field.shape@v1`` — H0 persistence of LIVE mesh pins

These are billable *decision artifacts*, not raw sensor resale.
GAIA reads stay operator-anchored (``device_id``); coordinate queries live on ATLAS.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

from . import __version__
from .config import get_settings
from .formatters import headline
from .geo import in_bbox, normalize_bbox, utc_now
from .gnss_index import grid_cell_id, state_for_score
from .stations import LAYER_META, STATION_CATALOG
from .watchboxes import ALLOWED_WATCHBOX_LAYERS, STORE, evaluate_watchbox

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

from .field_products import (  # noqa: E402
    FIELD_PRODUCT_CAPS,
    field_consensus,
    field_posterior,
    field_shape,
    mesh_sample,
)

PRODUCT_CAPS.extend(FIELD_PRODUCT_CAPS)

CAP_BY_ID = {str(c["capability_id"]): c for c in PRODUCT_CAPS}


def make_receipt(payload: dict[str, Any], *, capability_id: str) -> dict[str, Any]:
    """Tamper-evident content receipt.

    sha256 alone is forgeable by anyone who edits the payload and recomputes;
    the Ed25519 signature over the canonical body (same key as the manifest)
    is what makes the receipt attributable to this ATLAS instance. When PQC is
    enabled the exact same canonical bytes also carry an ML-DSA-65 signature.
    """
    body = {k: v for k, v in payload.items() if k not in ("receipt", "receipt_url", "verifier_url")}
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
        signature = signer.sign_payload(canonical)
        receipt["signature_alg"] = signature["algorithm"]
        receipt["signature_b64"] = signature["value"]
        receipt["public_key_b64"] = signature["public_key"]
        if signature.get("pq_value"):
            receipt["pq_signature_alg"] = signature["pq_algorithm"]
            receipt["pq_signature_b64"] = signature["pq_value"]
            receipt["pq_public_key_b64"] = signature["pq_public_key"]
        receipt["signature_status"] = "signed"
    except ModuleNotFoundError:
        # Developer environments created before cryptography became a required
        # runtime dependency may still exercise deterministic product logic.
        # Never disguise that digest as an attributable signature. In the Docker
        # build cryptography is mandatory; key/configuration errors fail closed.
        receipt["signature_status"] = "unavailable_missing_runtime_dependency"
    return receipt


VERIFIER_ORIGIN = "https://verify.modelmarket.dev"
_RECEIPT_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_RECEIPT_CACHE_MAX = 64

_STATE_RANK = {
    "severe_degradation": 5,
    "degraded": 4,
    "mild_degradation": 3,
    "normal": 2,
    "unknown": 1,
}
_CLAIM_RANK = {
    "spoofing_reported": 5,
    "jamming_reported": 4,
    "derived_degradation": 3,
    "observed_metric": 2,
    "historical_proxy": 1,
}


def remember_receipt(receipt: dict[str, Any]) -> None:
    digest = str(receipt.get("digest") or "")
    if not digest:
        return
    _RECEIPT_CACHE[digest] = dict(receipt)
    _RECEIPT_CACHE.move_to_end(digest)
    while len(_RECEIPT_CACHE) > _RECEIPT_CACHE_MAX:
        _RECEIPT_CACHE.popitem(last=False)


def lookup_receipt(digest: str) -> dict[str, Any] | None:
    row = _RECEIPT_CACHE.get(digest)
    return dict(row) if isinstance(row, dict) else None


def _receipt_links(receipt: dict[str, Any]) -> tuple[str, str]:
    digest = str(receipt.get("digest") or "")
    settings = get_settings()
    base = (settings.public_url or "https://atlas.modelmarket.dev").rstrip("/")
    receipt_url = f"{base}/api/v1/receipts/{digest}" if digest else f"{base}/api/v1/receipts"
    verifier_url = f"{VERIFIER_ORIGIN}/?receipt_url={quote(receipt_url, safe='')}"
    return receipt_url, verifier_url


def _worst_state(states: list[str]) -> str:
    return max(states, key=lambda s: _STATE_RANK.get(s, 0), default="unknown")


def _strongest_claim(levels: list[str]) -> str | None:
    ranked = [level for level in levels if level in _CLAIM_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda level: _CLAIM_RANK[level])


def _evidence_records(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Spec §8 evidence rows derived from the observations already in the envelope."""
    out: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        values = obs.get("values") if isinstance(obs.get("values"), dict) else {}
        out.append({
            "evidence_id": obs.get("id") or obs.get("point_id"),
            "point_id": obs.get("id") or obs.get("point_id"),
            "source_id": obs.get("parent_id") or obs.get("source"),
            "evidence_class": "ground_gnss_station",
            "claim_level": obs.get("claim_level") or "observed_metric",
            "claim_class": obs.get("claim_class"),
            "state": obs.get("state"),
            "degradation_score": obs.get("degradation_score"),
            "source": obs.get("source"),
            "lat": obs.get("lat") if obs.get("lat") is not None else values.get("latitude"),
            "lon": obs.get("lon") if obs.get("lon") is not None else values.get("longitude"),
        })
        for event in obs.get("interference_events") or []:
            if not isinstance(event, dict):
                continue
            out.append({
                "evidence_id": event.get("id") or event.get("point_id"),
                "point_id": event.get("id") or event.get("point_id"),
                "source_id": event.get("parent_id") or event.get("source"),
                "evidence_class": "curated_interference_event",
                "claim_level": event.get("claim_level") or "jamming_reported",
                "claim_class": event.get("claim_class") or "reported_interference",
                "source": event.get("source"),
                "distance_km": event.get("distance_km"),
            })
    return out


def _attach_gnss_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Fill spec §7.3 fields: summary, evidence, receipt_url, verifier_url."""
    cells = [c for c in (payload.get("cells") or []) if isinstance(c, dict)]
    observations = [o for o in (payload.get("observations") or []) if isinstance(o, dict)]
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    states = [str(c.get("state") or "unknown") for c in cells] or [
        str(o.get("state") or "unknown") for o in observations
    ]
    scores = [
        float(c["degradation_score"])
        for c in cells
        if isinstance(c.get("degradation_score"), (int, float))
    ]
    claims = [str(o.get("claim_level")) for o in observations if o.get("claim_level")]
    unknown = int(coverage.get("unknown_integrity") or 0)
    station_n = int(coverage.get("stations") or 0)
    if payload.get("ok") and station_n and unknown == 0:
        coverage_label = "full"
    elif payload.get("ok") and station_n:
        coverage_label = "partial"
    else:
        coverage_label = "none"
    payload["summary"] = {
        "state": _worst_state(states) if payload.get("ok") else "unknown",
        "score": round(max(scores), 2) if scores and payload.get("ok") else None,
        "confidence": payload.get("confidence") if payload.get("ok") else 0.0,
        "coverage": coverage_label,
        "claim_level": _strongest_claim(claims) if payload.get("ok") else None,
    }
    payload["evidence"] = _evidence_records(observations) if payload.get("ok") else []
    if payload.get("ok"):
        payload["receipt"] = make_receipt(payload, capability_id="atlas.gnss.degradation.read@v1")
        remember_receipt(payload["receipt"])
        payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
    else:
        payload.setdefault("receipt_url", None)
        payload.setdefault("verifier_url", None)
    return payload



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
    citation = {
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
    for key in (
        "observed_at", "acq_date", "acq_time_utc", "satellite", "instrument",
        "daynight", "version", "frp_mw", "scan_km", "track_km", "event_id",
        "type", "region", "status", "start_date", "end_date", "severity",
        "confidence_pct", "attribution", "url", "area_ha", "firedate",
        "energy_fj", "name", "alert", "color",
        "wmo", "profile_url", "source_url", "directory_url", "profile_path",
        "dac", "doi", "profile_quality", "fetched_at", "reading_age_ms",
        "station_id", "network", "country", "source_status", "state",
        "claim_class", "claim_level", "cause", "source_url", "license", "license_url",
        "attribution", "modified", "measurement_basis", "evidence_boundary",
    ):
        if s.get(key) is not None:
            citation[key] = s[key]
    return citation


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
    exact = _citation(point)
    for key in (
        "kind", "label", "title", "subtitle", "summary", "metrics", "status_line",
        "blurb", "model", "site", "online", "has_reading", "cached", "age_ms",
        "upstream_evidence",
        "cell_id", "grid_scheme", "boundary", "station_ids", "source_count",
    ):
        if point.get(key) is not None:
            exact[key] = point[key]
    parent = _parent_capability(point)
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
        "point_invoke": _point_handoff(point_id),
    }
    payload["receipt"] = make_receipt(payload, capability_id="atlas.point.read@v1")
    return payload


def _point_segment_km(
    lat: float, lon: float, a_lat: float, a_lon: float, b_lat: float, b_lon: float
) -> float:
    """Local equirectangular projection; accurate enough for route corridors."""
    ref = math.radians((a_lat + b_lat + lat) / 3.0)
    x, y = lon * math.cos(ref), lat
    ax, ay = a_lon * math.cos(ref), a_lat
    bx, by = b_lon * math.cos(ref), b_lat
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    t = 0.0 if denom <= 1e-15 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / denom))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(x - px, y - py) * 111.195


def _grid_cell(lat: float, lon: float) -> tuple[str, str]:
    return grid_cell_id(lat, lon)


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
            return _attach_gnss_envelope({
                "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
                "refuse_reason": "route must contain valid [lon, lat] pairs",
            })
        query = {"kind": "route", "route": route_raw, "corridor_km": corridor_km}
        for point in points:
            try:
                lat, lon = float(point["lat"]), float(point["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            dist = min(_point_segment_km(lat, lon, *a, *b) for a, b in zip(route, route[1:]))
            if dist <= corridor_km:
                selected.append((point, dist))
    elif all(data.get(k) is not None for k in ("west", "south", "east", "north")):
        try:
            west, south, east, north = normalize_bbox(
                float(data["west"]), float(data["south"]), float(data["east"]), float(data["north"])
            )
        except (TypeError, ValueError):
            return _attach_gnss_envelope({
                "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
                "refuse_reason": "invalid bbox",
            })
        query = {"kind": "bbox", "west": west, "south": south, "east": east, "north": north}
        selected = [(p, None) for p in _stations_in_bbox(points, west=west, south=south, east=east, north=north)]
    elif data.get("lat") is not None and data.get("lon") is not None:
        try:
            qlat, qlon = float(data["lat"]), float(data["lon"])
        except (TypeError, ValueError):
            qlat = qlon = 999.0
        if not (-90 <= qlat <= 90 and -180 <= qlon <= 180):
            return _attach_gnss_envelope({
                "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
                "refuse_reason": "lat/lon out of range",
            })
        query = {"kind": "point", "lat": qlat, "lon": qlon, "max_km": max_km}
        for point in points:
            try:
                dist = _haversine_km(qlat, qlon, float(point["lat"]), float(point["lon"]))
            except (KeyError, TypeError, ValueError):
                continue
            if dist <= max_km:
                selected.append((point, dist))
    else:
        return _attach_gnss_envelope({
            "ok": False, "capability_id": "atlas.gnss.degradation.read@v1",
            "refuse_reason": "provide lat+lon, west+south+east+north, or route",
        })

    selected.sort(key=lambda pair: pair[1] if pair[1] is not None else 0.0)
    selected = selected[:limit]
    if not selected:
        return _attach_gnss_envelope({
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
                ev_dist = _haversine_km(lat, lon, float(event["lat"]), float(event["lon"]))
            except (KeyError, TypeError, ValueError):
                continue
            radius = float(ev_values.get("radius_km") or 0.0)
            if ev_dist <= max(50.0, radius):
                nearby_events.append({**_citation(event), "distance_km": round(ev_dist, 2)})
        for event in nearby_events:
            event["claim_level"] = _reported_claim(event)
            event["claim_class"] = "reported_interference"
        event_score = max((float((e.get("values") or {}).get("severity_score") or 0.0) for e in nearby_events), default=None)
        claim_class = point.get("claim_class") or "inventory_only"
        claim_level = point.get("claim_level") or ("derived_degradation" if score is not None else "observed_metric")
        state = _gnss_state(score)
        obs = {
            **_citation(point),
            "distance_km": round(distance, 2) if distance is not None else None,
            "degradation_score": round(score, 2) if score is not None else None,
            "reported_interference_score": round(event_score, 2) if event_score is not None else None,
            "state": state,
            "claim_class": claim_class,
            "claim_level": claim_level,
            "cause": "unestablished",
            "interference_events": nearby_events,
            "point_invoke": _point_handoff(point.get("id")),
        }
        observations.append(obs)
        cell_id, scheme = _grid_cell(lat, lon)
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
            "state": _gnss_state(score),
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
    return _attach_gnss_envelope(payload)


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


def _point_on_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> bool:
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    scale = max(1.0, abs(bx - ax), abs(by - ay))
    if abs(cross) > 1e-10 * scale:
        return False
    return min(ax, bx) - 1e-10 <= px <= max(ax, bx) + 1e-10 and min(ay, by) - 1e-10 <= py <= max(ay, by) + 1e-10


# A ring is unwrapped once, into a continuous longitude frame, then queried at
# every 360° branch that its own span can reach.
_Ring = tuple[list[tuple[float, float]], float, float]


def _unwrap_ring(ring: Any) -> _Ring | None:
    """Ring vertices in one continuous longitude frame, or None if unusable.

    Each vertex is placed on the branch nearest its PREDECESSOR, never on the
    branch nearest the query. Anchoring on the query looks equivalent and is not:
    a polygon straddling the meridian opposite the caller is torn into a band
    across the whole map, and the ray cast then reports containment for an asset
    on the other side of the planet (an Aleutian smoke polygon "covering"
    London). Real HMS rings are dense, so consecutive vertices are far under the
    180° that would make the unwrap ambiguous.
    """
    if not isinstance(ring, list) or len(ring) < 4:
        return None
    points: list[tuple[float, float]] = []
    x = 0.0
    for index, raw in enumerate(ring):
        if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
            return None
        try:
            raw_lon, raw_lat = float(raw[0]), float(raw[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (math.isfinite(raw_lon) and math.isfinite(raw_lat)) or not -90 <= raw_lat <= 90:
            return None
        x = raw_lon if index == 0 else x + ((raw_lon - x + 180.0) % 360.0) - 180.0
        points.append((x, raw_lat))
    xs = [point[0] for point in points]
    return points, min(xs), max(xs)


def _ray_cast(lat: float, x: float, points: list[tuple[float, float]]) -> bool:
    """Boundary-inclusive crossing test in the ring's own unwrapped frame."""
    inside = False
    for i in range(len(points)):
        ax, ay = points[i - 1]
        bx, by = points[i]
        if _point_on_segment(x, lat, ax, ay, bx, by):
            return True
        if (ay > lat) != (by > lat):
            crossing_x = (bx - ax) * (lat - ay) / (by - ay) + ax
            if x < crossing_x:
                inside = not inside
    return inside


def _point_in_unwrapped_ring(lat: float, lon: float, ring: _Ring) -> bool:
    points, min_x, max_x = ring
    # ±1e-9 so a vertex exactly on the ring's own edge of span is still tested.
    low = math.ceil((min_x - lon - 1e-9) / 360.0)
    high = math.floor((max_x - lon + 1e-9) / 360.0)
    for k in range(int(low), int(high) + 1):
        if _ray_cast(lat, lon + 360.0 * k, points):
            return True
    return False


def _polygon_rings(geometry: Any) -> list[list[_Ring]] | None:
    """Unwrapped [outer, *holes] per part, or None when the geometry is unusable.

    None is NOT "outside": a caller that cannot evaluate the geometry must
    refuse, because reporting "outside" for a polygon we failed to parse is the
    one wrong answer this SKU must never sell.
    """
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if kind == "Polygon":
        parts: list[Any] = [coordinates]
    elif kind == "MultiPolygon":
        if not isinstance(coordinates, list) or not coordinates:
            return None
        parts = list(coordinates)
    else:
        return None
    out: list[list[_Ring]] = []
    for part in parts:
        if not isinstance(part, list) or not part:
            return None
        rings: list[_Ring] = []
        for ring in part:
            unwrapped = _unwrap_ring(ring)
            if unwrapped is None:
                return None
            rings.append(unwrapped)
        out.append(rings)
    return out


def smoke_geometry_evaluable(geometry: Any) -> bool:
    """True when containment can be decided against this geometry at all."""
    return _polygon_rings(geometry) is not None


def point_in_smoke_geometry(lat: float, lon: float, geometry: Any) -> bool:
    """Boundary-inclusive point-in-polygon with KML holes and date-line support."""
    parts = _polygon_rings(geometry)
    if parts is None:
        return False
    for rings in parts:
        if _point_in_unwrapped_ring(lat, lon, rings[0]) and not any(
            _point_in_unwrapped_ring(lat, lon, hole) for hole in rings[1:]
        ):
            return True
    return False


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

    if any(not smoke_geometry_evaluable(station.get("geometry")) for station in polygons):
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

    matched = [station for station in polygons if point_in_smoke_geometry(lat, lon, station["geometry"])]
    matched.sort(key=lambda station: _num_value(station, "severity_score"), reverse=True)
    smoke_evidence = []
    for station in matched:
        smoke_evidence.append({
            "polygon_id": station.get("polygon_id") or station.get("id"),
            "density": station.get("density"),
            "severity_score": _num_value(station, "severity_score"),
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
    payload["receipt"] = make_receipt(payload, capability_id="atlas.smoke.operations@v1")
    remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
    return payload


def fire_weather(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.fire.weather@v1`` — FIRMS and/or EFFIS + bounded nearby weather."""
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

    live_fire = _live_valued(_stations_in_bbox(
        stations, west=west, south=south, east=east, north=north, layers={"fire"}
    ))
    live_effis = _live_valued(_stations_in_bbox(
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

    live_fire.sort(key=lambda s: _num_value(s, "brightness_k"), reverse=True)
    live_effis.sort(
        key=lambda s: (_num_value(s, "area_ha"), _num_value(s, "severity_score")),
        reverse=True,
    )
    hotspots = [_citation(s) for s in live_fire[:limit]]
    effis_fires = [_citation(s) for s in live_effis[:limit]]
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
        d = _haversine_km(alat, alon, lat, lon)
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
            d = _haversine_km(alat, alon, lat, lon)
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

    top_b = _num_value(live_fire[0], "brightness_k") if live_fire else 0.0
    top_ha = _num_value(live_effis[0], "area_ha") if live_effis else 0.0
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
        "weather": _citation(nearest_wx) if nearest_wx else None,
        "weather_distance_km": round(nearest_km, 1) if nearest_wx and nearest_km is not None else None,
        "max_weather_km": max_weather_km,
        "nearest_weather_candidate": (
            _citation(nearest_wx_candidate) if nearest_wx_candidate else None
        ),
        "nearest_weather_candidate_distance_km": (
            round(nearest_wx_candidate_km, 1)
            if nearest_wx_candidate_km is not None else None
        ),
        "air": _citation(nearest_air) if nearest_air else None,
        "air_distance_km": round(air_km, 1) if nearest_air and air_km is not None else None,
        "max_air_km": max_air_km,
        "nearest_air_candidate": (
            _citation(nearest_air_candidate) if nearest_air_candidate else None
        ),
        "nearest_air_candidate_distance_km": (
            round(nearest_air_candidate_km, 1)
            if nearest_air_candidate_km is not None else None
        ),
        "attribution": " · ".join(attr_parts),
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
    preset_key = str(data.get("preset") or "").strip().lower() or None
    if preset_key is not None and preset_key not in SITUATION_BRIEF_PRESETS:
        # A misspelled desk must not silently fall through to the 21-layer default:
        # the buyer would be billed for an answer about a scope they did not ask for.
        return {
            "ok": False,
            "capability_id": "atlas.situation.brief@v1",
            "refuse_reason": (
                "unknown preset: " + preset_key + "; known presets are "
                + ", ".join(sorted(SITUATION_BRIEF_PRESETS))
            ),
            "bbox": {"west": west, "south": south, "east": east, "north": north},
        }
    preset = SITUATION_BRIEF_PRESETS.get(preset_key) if preset_key else None
    layers = _normalize_layer_list(data.get("layers"))
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
        layers = [k for k in SITUATION_BRIEF_DEFAULT_LAYERS if k in LAYER_META]
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
    citations = [_citation(s) for s in ranked[:max_citations]]

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
    # Some layers have no live source at all right now (soil, precipitation and others
    # wait on operator accounts upstream). Asking one of them answered "no LIVE readings
    # within 2500 km" from every point on Earth, which the hub scores as a provider miss,
    # so a buyer walking the layer list saw ATLAS "failing" systematically. Say which
    # layers cannot be served and which can, and serve the rest of a mixed request.
    live_layers = _layers_with_live_readings(stations)
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
            pin, dist = _nearest_candidate(stations, lat=lat, lon=lon, layers={layer})
            if pin is None or dist is None or dist > max_km:
                by_layer[layer] = None
                continue
            hits += 1
            by_layer[layer] = {
                **_citation(pin),
                "distance_km": round(dist, 2),
                "point_invoke": _point_handoff(pin.get("id")),
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
            "point_invoke": _point_handoff(pin.get("id")),
        },
        "distance_km": round(dist, 2),
        "layer": pin.get("layer"),
        "values": (pin.get("values") if isinstance(pin.get("values"), dict) else {}),
    }
    if unavailable:
        payload["unavailable_layers"] = unavailable
    payload["receipt"] = make_receipt(payload, capability_id="atlas.nearest.read@v1")
    return payload


# ── atlas.geomag.window@v1 ────────────────────────────────────────────────────
#
# `situation.brief` deliberately excludes spacewx and geomag — a planetary Kp pin is
# not a site brief — so the two newest dense layers (401 SWPC observations, 13 of 14
# USGS observatories LIVE) had no SKU at all. The job this answers is the one desks
# actually pay for: is the field quiet enough to run the operation right now.
#
# Kp thresholds are the published NOAA planetary-K / G-scale boundaries, not ours.


def _kp_state(kp: float) -> tuple[str, str, str | None]:
    """(state, window status, NOAA G-scale label) for a planetary Kp value."""
    if kp >= 9.0:
        return "extreme_storm", "hold", "G5"
    if kp >= 8.0:
        return "severe_storm", "hold", "G4"
    if kp >= 7.0:
        return "strong_storm", "hold", "G3"
    if kp >= 6.0:
        return "moderate_storm", "hold", "G2"
    if kp >= 5.0:
        return "minor_storm", "hold", "G1"
    if kp >= 4.0:
        return "active", "caution", None
    if kp >= 3.0:
        return "unsettled", "open", None
    return "quiet", "open", None


def geomag_window(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.geomag.window@v1`` — planetary Kp window plus local corroboration.

    Fail-closed on Kp: the whole answer keys on the planetary index, so a missing SWPC
    reading is a refusal rather than a window derived from an observatory alone.
    """
    point = _parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.geomag.window@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    asset_id = str(data.get("asset_id") or "").strip()[:160] or None
    try:
        max_km = float(data.get("max_km") if data.get("max_km") is not None else 1500.0)
    except (TypeError, ValueError):
        max_km = 1500.0
    max_km = max(1.0, min(max_km, 20037.0))
    query = {"lat": lat, "lon": lon, "max_km": max_km, "asset_id": asset_id}

    kp_pins = [
        s for s in stations
        if isinstance(s, dict) and s.get("layer") == "spacewx" and s.get("live")
        and isinstance(s.get("values"), dict)
        and isinstance(s["values"].get("kp_index"), (int, float))
    ]
    if not kp_pins:
        return {
            "ok": False,
            "capability_id": "atlas.geomag.window@v1",
            "refuse_reason": "no LIVE planetary Kp reading available; window refused",
            "query": query,
        }
    # Kp is planetary: every spacewx pin carries the same index, so the worst
    # reported value is the honest one if a stale pin disagrees.
    kp = max(float(s["values"]["kp_index"]) for s in kp_pins)
    kp_state, window_status, g_scale = _kp_state(kp)
    kp_pin = next(s for s in kp_pins if float(s["values"]["kp_index"]) == kp)

    observatory, obs_km = _nearest_candidate(stations, lat=lat, lon=lon, layers={"geomag"})
    obs_block: dict[str, Any] | None = None
    if observatory is not None and obs_km is not None and obs_km <= max_km:
        obs_values = observatory.get("values") if isinstance(observatory.get("values"), dict) else {}
        obs_block = {
            **_citation(observatory),
            "distance_km": round(obs_km, 2),
            "field_nt": obs_values.get("field_nt"),
            "observation_age_s": obs_values.get("observation_age_s"),
            "point_invoke": _point_handoff(observatory.get("id")),
        }
    # The USGS network is US territory only. Beyond the radius the window is Kp-only,
    # and saying so is the difference between a bounded product and an implied local
    # magnetometer the buyer does not have.
    corroboration = "observatory" if obs_block is not None else "planetary_only"

    aurora_pin, aurora_km = _nearest_candidate(stations, lat=lat, lon=lon, layers={"spacewx"})
    aurora_block: dict[str, Any] | None = None
    if aurora_pin is not None and aurora_km is not None and aurora_km <= max_km:
        aurora_values = aurora_pin.get("values") if isinstance(aurora_pin.get("values"), dict) else {}
        pct = aurora_values.get("aurora_pct")
        if isinstance(pct, (int, float)):
            aurora_block = {
                **_citation(aurora_pin),
                "distance_km": round(aurora_km, 2),
                "aurora_pct": float(pct),
            }

    drivers = [
        f"planetary Kp {kp:g} — {kp_state}" + (f" ({g_scale})" if g_scale else ""),
    ]
    if obs_block is not None:
        age = obs_block.get("observation_age_s")
        age_note = f", observation {float(age):.0f} s old" if isinstance(age, (int, float)) else ""
        drivers.append(
            f"nearest USGS observatory {obs_block.get('distance_km')} km away"
            f"{age_note} — total field F available for corroboration"
        )
    else:
        drivers.append(
            f"no USGS geomagnetic observatory within {max_km:g} km — window is planetary Kp only"
        )
    if aurora_block is not None:
        drivers.append(
            f"OVATION aurora probability {aurora_block['aurora_pct']:.0f}% "
            f"at {aurora_block['distance_km']} km"
        )

    actions: list[str] = []
    if window_status == "hold":
        actions.append(
            "Hold magnetic-reference-dependent work (MWD survey acceptance, magnetic "
            "compass checks) until the index falls back below Kp 5."
        )
        actions.append("Expect HF propagation degradation and elevated GNSS ionospheric error.")
    elif window_status == "caution":
        actions.append(
            "Tighten survey acceptance criteria and re-check before committing to a "
            "magnetic reference; the field is active but not in storm."
        )
    else:
        actions.append("No geomagnetic reason to defer magnetic-reference-dependent work.")
    actions.append("Recheck on the next SWPC 1-minute Kp update and retain this signed receipt.")

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.geomag.window@v1",
        "sku": "atlas.geomag.window@v1",
        "generated_at": utc_now(),
        "query": query,
        "kp_index": kp,
        "kp_state": kp_state,
        "noaa_g_scale": g_scale,
        "window_status": window_status,
        "corroboration": corroboration,
        "summary": (
            f"Geomagnetic window {window_status} at {lat:.4f},{lon:.4f}: planetary Kp {kp:g} "
            f"({kp_state}{', ' + g_scale if g_scale else ''}), "
            + (
                f"nearest USGS observatory {obs_block['distance_km']} km"
                if obs_block is not None
                else f"no observatory within {max_km:g} km"
            )
            + ". Not a magnetic-declination correction and not a safety-of-life service."
        ),
        "drivers": drivers,
        "recommended_actions": actions,
        "kp_source": _citation(kp_pin),
        "nearest_observatory": obs_block,
        "aurora": aurora_block,
        "limitations": [
            "Kp is a planetary 3-hour index published by NOAA SWPC; it is not a local "
            "magnetic measurement at the queried coordinate.",
            "USGS observatories report total field F only. This SKU does not compute or "
            "supply magnetic declination, and it is not an IFR-grade in-field reference.",
            "The USGS observatory network covers United States territory; elsewhere the "
            "window is planetary-only, which `corroboration` states explicitly.",
            "Operational screening, not a safety-of-life navigation or aviation service.",
        ],
        "attribution": [
            "NOAA Space Weather Prediction Center (planetary Kp, OVATION aurora)",
            "U.S. Geological Survey Geomagnetism Program (observatory total field F)",
        ],
    }
    payload["receipt"] = make_receipt(payload, capability_id="atlas.geomag.window@v1")
    remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
    return payload


# ── atlas.pv.irradiance.record@v1 ─────────────────────────────────────────────
#
# NASA POWER daily irradiation lags by days, which makes it useless as a nowcast and
# exactly right for the job this SKU sells: a retrospective, attributed record of what
# the sky and the air did over one plant coordinate, citable in a performance-ratio
# argument with an EPC or O&M contractor. It is deliberately NOT a yield model.
#
# Screening thresholds below are ours, not a standard, and the payload says so.
_AOD_ELEVATED = 0.5
_DUST_EVENT_UGM3 = 50.0


def pv_irradiance_record(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.pv.irradiance.record@v1`` — dated irradiance + aerosol record of fact."""
    point = _parse_query_point(data)
    if point is None:
        return {
            "ok": False,
            "capability_id": "atlas.pv.irradiance.record@v1",
            "refuse_reason": "lat/lon required (lat −90…90, lon −180…180)",
        }
    lat, lon = point
    plant_id = str(data.get("plant_id") or "").strip()[:160] or None
    try:
        max_km = float(data.get("max_km") if data.get("max_km") is not None else 100.0)
    except (TypeError, ValueError):
        max_km = 100.0
    max_km = max(1.0, min(max_km, 2000.0))
    query = {"lat": lat, "lon": lon, "max_km": max_km, "plant_id": plant_id}

    solar, solar_km = _nearest_candidate(stations, lat=lat, lon=lon, layers={"solar"})
    solar_values = (
        solar.get("values") if solar is not None and isinstance(solar.get("values"), dict) else {}
    )
    all_sky = solar_values.get("solar_irradiation_kwh_m2_day")
    if (
        solar is None
        or solar_km is None
        or solar_km > max_km
        or not isinstance(all_sky, (int, float))
    ):
        return {
            "ok": False,
            "capability_id": "atlas.pv.irradiance.record@v1",
            "refuse_reason": (
                f"no LIVE daily irradiation reading within {max_km:g} km of the plant "
                "coordinate; a record of fact cannot be issued from a distant cell"
            ),
            "query": query,
            "nearest_solar_candidate_distance_km": (
                round(solar_km, 2) if solar_km is not None else None
            ),
        }

    all_sky = float(all_sky)
    clear_raw = solar_values.get("clear_sky_irradiation_kwh_m2_day")
    clear_sky = float(clear_raw) if isinstance(clear_raw, (int, float)) else None
    cloud_loss = None
    cloud_loss_pct = None
    if clear_sky is not None and clear_sky > 0:
        cloud_loss = round(max(0.0, clear_sky - all_sky), 4)
        cloud_loss_pct = round(100.0 * cloud_loss / clear_sky, 2)

    observation_day = solar_values.get("solar_observation_yyyymmdd")
    observation_date = None
    if isinstance(observation_day, (int, float)):
        digits = f"{int(observation_day):08d}"
        if len(digits) == 8:
            observation_date = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    elif isinstance(observation_day, str) and len(observation_day.strip()) == 8:
        digits = observation_day.strip()
        observation_date = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"

    irradiance = {
        **_citation(solar),
        "distance_km": round(solar_km, 2),
        "observation_date": observation_date,
        "all_sky_kwh_m2_day": round(all_sky, 4),
        "clear_sky_kwh_m2_day": round(clear_sky, 4) if clear_sky is not None else None,
        "cloud_loss_kwh_m2_day": cloud_loss,
        "cloud_loss_pct": cloud_loss_pct,
        "point_invoke": _point_handoff(solar.get("id")),
    }

    aerosol_pin, aerosol_km = _nearest_candidate(stations, lat=lat, lon=lon, layers={"atmosphere"})
    aerosol: dict[str, Any] | None = None
    if aerosol_pin is not None and aerosol_km is not None and aerosol_km <= max_km:
        aerosol_values = (
            aerosol_pin.get("values") if isinstance(aerosol_pin.get("values"), dict) else {}
        )
        aod = aerosol_values.get("aerosol_optical_depth")
        dust = aerosol_values.get("dust_ugm3")
        if isinstance(aod, (int, float)) or isinstance(dust, (int, float)):
            aerosol = {
                **_citation(aerosol_pin),
                "distance_km": round(aerosol_km, 2),
                "aerosol_optical_depth": float(aod) if isinstance(aod, (int, float)) else None,
                "dust_ugm3": float(dust) if isinstance(dust, (int, float)) else None,
                "point_invoke": _point_handoff(aerosol_pin.get("id")),
            }

    weather_pin, weather_km = _nearest_candidate(stations, lat=lat, lon=lon, layers={"weather"})
    weather: dict[str, Any] | None = None
    if weather_pin is not None and weather_km is not None and weather_km <= max_km:
        weather = {**_citation(weather_pin), "distance_km": round(weather_km, 2)}

    drivers: list[str] = []
    if observation_date:
        drivers.append(f"NASA POWER daily record date: {observation_date}")
    else:
        drivers.append("NASA POWER record date was not supplied with this reading")
    drivers.append(
        f"all-sky irradiation {all_sky:.3f} kWh/m²/day at {irradiance['distance_km']} km"
    )
    if cloud_loss_pct is not None:
        drivers.append(
            f"clear-sky {clear_sky:.3f} kWh/m²/day — sky delivered {cloud_loss_pct:.1f}% "
            "below clear-sky at this coordinate"
        )
    else:
        drivers.append("clear-sky reference unavailable; cloud loss not derivable")

    soiling_drivers: list[str] = []
    if aerosol is not None:
        aod = aerosol.get("aerosol_optical_depth")
        dust = aerosol.get("dust_ugm3")
        if isinstance(aod, (int, float)):
            note = "elevated" if aod >= _AOD_ELEVATED else "background"
            soiling_drivers.append(
                f"aerosol optical depth {aod:.3f} ({note}, screening threshold "
                f"{_AOD_ELEVATED:g})"
            )
        if isinstance(dust, (int, float)):
            note = "dust event" if dust >= _DUST_EVENT_UGM3 else "no dust event"
            soiling_drivers.append(
                f"dust {dust:.1f} µg/m³ ({note}, screening threshold {_DUST_EVENT_UGM3:g})"
            )
    else:
        soiling_drivers.append(
            f"no LIVE aerosol/dust reading within {max_km:g} km — soiling driver not evidenced"
        )

    payload: dict[str, Any] = {
        "ok": True,
        "capability_id": "atlas.pv.irradiance.record@v1",
        "sku": "atlas.pv.irradiance.record@v1",
        "generated_at": utc_now(),
        "query": query,
        "record_kind": "retrospective_record_of_fact",
        "summary": (
            f"{plant_id or 'Plant'} at {lat:.4f},{lon:.4f}"
            + (f", record date {observation_date}" if observation_date else "")
            + f": all-sky {all_sky:.3f} kWh/m²/day"
            + (
                f", {cloud_loss_pct:.1f}% below clear-sky"
                if cloud_loss_pct is not None else ", clear-sky reference unavailable"
            )
            + (
                f"; aerosol optical depth {aerosol['aerosol_optical_depth']:.3f}"
                if aerosol is not None
                and isinstance(aerosol.get("aerosol_optical_depth"), (int, float))
                else "; no colocated aerosol evidence"
            )
            + ". Record of fact, not a yield forecast."
        ),
        "irradiance": irradiance,
        "aerosol": aerosol,
        "weather": weather,
        "drivers": drivers,
        "soiling_drivers": soiling_drivers,
        "limitations": [
            "NASA POWER daily irradiation is satellite-derived and published with a "
            "multi-day lag. This is a retrospective record, not a nowcast.",
            "Values describe the POWER source grid cell nearest the coordinate, at the "
            "reported distance — not a pyranometer on the plant.",
            "Aerosol and dust are CAMS-derived modelled composition at the coordinate, "
            "not a measured soiling rate on the modules.",
            "Aerosol/dust screening thresholds in `soiling_drivers` are ATLAS screening "
            "labels, not an industry standard.",
            "Not a yield forecast, not a soiling-loss model, and not a bankable energy "
            "assessment: no P50/P90 and no uncertainty band is supplied.",
        ],
        "attribution": [
            "NASA POWER (daily all-sky and clear-sky surface irradiation)",
            "Contains modified Copernicus Atmosphere Monitoring Service information",
        ],
    }
    payload["receipt"] = make_receipt(payload, capability_id="atlas.pv.irradiance.record@v1")
    remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
    return payload


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


def _parse_route(raw: Any) -> list[tuple[float, float]] | None:
    """``[[lon, lat], …]`` → ``[(lat, lon), …]``, or None when unusable."""
    if not isinstance(raw, list) or not (2 <= len(raw) <= 500):
        return None
    out: list[tuple[float, float]] = []
    try:
        for pair in raw:
            lon, lat = float(pair[0]), float(pair[1])
            if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                return None
            out.append((lat, lon))
    except (TypeError, ValueError, IndexError):
        return None
    return out


def _route_distance_km(route: list[tuple[float, float]], lat: float, lon: float) -> float:
    return min(_point_segment_km(lat, lon, *a, *b) for a, b in zip(route, route[1:]))


def _route_length_km(route: list[tuple[float, float]]) -> float:
    return sum(
        _haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(route, route[1:])
    )


def route_integrity(data: dict[str, Any], stations: list[dict[str, Any]]) -> dict[str, Any]:
    """``atlas.route.integrity@v1`` — per-segment GNSS, interference and hazard brief."""
    route = _parse_route(data.get("route"))
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
    length_km = round(_route_length_km(route), 2)
    query = {
        "route_id": route_id,
        "corridor_km": corridor_km,
        "waypoints": len(route),
        "route_length_km": length_km,
    }

    # Component 1 — the existing GNSS field, in its own route mode.
    gnss = gnss_degradation(
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
            dist = _route_distance_km(route, lat, lon)
            if dist <= corridor_km:
                hits.append((s, dist))
        hits.sort(key=lambda pair: pair[1])
        return hits

    interference_raw = _in_corridor(("jamming",))
    interference = [
        {**_citation(s), "distance_km": round(d, 2), "claim": _reported_claim(s)}
        for s, d in interference_raw[:24]
    ]
    platforms_raw = _in_corridor(_ROUTE_PLATFORM_LAYERS)
    platform_counts: dict[str, int] = {}
    for s, _ in platforms_raw:
        layer = str(s.get("layer"))
        platform_counts[layer] = platform_counts.get(layer, 0) + 1
    platforms = [
        {**_citation(s), "distance_km": round(d, 2)} for s, d in platforms_raw[:24]
    ]
    hazards_raw = _in_corridor(_ROUTE_HAZARD_LAYERS)
    hazard_counts: dict[str, int] = {}
    for s, _ in hazards_raw:
        layer = str(s.get("layer"))
        hazard_counts[layer] = hazard_counts.get(layer, 0) + 1
    hazards = [
        {**_citation(s), "distance_km": round(d, 2)} for s, d in hazards_raw[:24]
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
        seg_len = round(_haversine_km(a[0], a[1], b[0], b[1]), 2)
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
                if _point_segment_km(lat, lon, *a, *b) <= corridor_km:
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
    payload["receipt"] = make_receipt(payload, capability_id="atlas.route.integrity@v1")
    remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
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
    return any(word in text for word in _DEGRADED_STATUS_WORDS)


def observability_attest(
    data: dict[str, Any],
    stations: list[dict[str, Any]],
    archive: Any | None = None,
) -> dict[str, Any]:
    """``atlas.observability.attest@v1`` — was the observation infrastructure up?"""
    from .status_archive import ARCHIVE, parse_iso

    store = archive if archive is not None else ARCHIVE
    point = _parse_query_point(data)
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
        dist = _haversine_km(lat, lon, plat, plon)
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

    station_ids = [_radar_station_id(pin) for pin, _ in nearby]
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
        station_id = _radar_station_id(pin)
        samples = by_station.get(station_id, [])
        degraded = [s for s in samples if _status_is_degraded(s)]
        degraded_total += len(degraded)
        radars.append({
            **_citation(pin),
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
            "point_invoke": _point_handoff(pin.get("id")),
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
        {**_citation(s), "distance_km": round(_haversine_km(lat, lon, float(s["lat"]), float(s["lon"])), 2)}
        for s in stations
        if isinstance(s, dict) and s.get("layer") == "alerts" and s.get("live")
        and isinstance(s.get("lat"), (int, float)) and isinstance(s.get("lon"), (int, float))
        and _haversine_km(lat, lon, float(s["lat"]), float(s["lon"])) <= max_km
    ][:12]
    weather_pin, weather_km = _nearest_candidate(stations, lat=lat, lon=lon, layers={"weather"})
    weather = (
        {**_citation(weather_pin), "distance_km": round(weather_km, 2)}
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
    payload["receipt"] = make_receipt(payload, capability_id="atlas.observability.attest@v1")
    remember_receipt(payload["receipt"])
    payload["receipt_url"], payload["verifier_url"] = _receipt_links(payload["receipt"])
    return payload


def invoke_product(
    capability_id: str,
    data: dict[str, Any],
    stations: list[dict[str, Any]],
    *,
    air_reading: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Route a Hub-style invoke to a composite product handler.

    ``air_reading`` is the colocated PM2.5/AQI evidence the caller already
    fetched at the buyer's coordinate. Only the smoke SKU consumes it, and it
    refuses rather than guessing when the caller could not supply it.
    """
    cap = str(capability_id or "").strip()
    if cap not in CAP_BY_ID:
        return {"ok": False, "refuse_reason": f"unknown capability: {cap}"}
    if not isinstance(data, dict):
        data = {}
    if cap == "atlas.watchbox.check@v1":
        return watchbox_check(data, stations)
    if cap == "atlas.fire.weather@v1":
        return fire_weather(data, stations)
    if cap == "atlas.smoke.operations@v1":
        return smoke_operations(data, stations, air_reading)
    if cap == "atlas.situation.brief@v1":
        return situation_brief(data, stations)
    if cap == "atlas.nearest.read@v1":
        return nearest_read(data, stations)
    if cap == "atlas.point.read@v1":
        return point_read(data, stations)
    if cap == "atlas.gnss.degradation.read@v1":
        return gnss_degradation(data, stations)
    if cap == "atlas.geomag.window@v1":
        return geomag_window(data, stations)
    if cap == "atlas.pv.irradiance.record@v1":
        return pv_irradiance_record(data, stations)
    if cap == "atlas.route.integrity@v1":
        return route_integrity(data, stations)
    if cap == "atlas.observability.attest@v1":
        return observability_attest(data, stations)
    if cap == "atlas.mesh.sample@v1":
        return mesh_sample(data, stations)
    if cap == "atlas.field.consensus@v1":
        return field_consensus(data, stations)
    if cap == "atlas.field.posterior@v1":
        return field_posterior(data, stations)
    if cap == "atlas.field.shape@v1":
        return field_shape(data, stations)
    return {"ok": False, "refuse_reason": f"unhandled capability: {cap}"}


__all__ = [
    "PRODUCT_CAPS",
    "CAP_BY_ID",
    "make_receipt",
    "lookup_receipt",
    "remember_receipt",
    "watchbox_check",
    "fire_weather",
    "point_in_smoke_geometry",
    "smoke_geometry_evaluable",
    "smoke_operations",
    "situation_brief",
    "nearest_read",
    "point_read",
    "gnss_degradation",
    "geomag_window",
    "pv_irradiance_record",
    "route_integrity",
    "observability_attest",
    "SITUATION_BRIEF_PRESETS",
    "invoke_product",
    "mesh_sample",
    "field_consensus",
    "field_posterior",
    "field_shape",
]
