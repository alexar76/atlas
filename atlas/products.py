"""ATLAS composite products — more than the sum of GAIA pins.

Ship-first Hub SKUs (fail-closed LIVE honesty):

* ``atlas.watchbox.check@v1`` — evaluate a subscribed bbox (plumbing / agent poll)
* ``atlas.fire.weather@v1`` — FIRMS and/or EFFIS + nearest weather context
* ``atlas.situation.brief@v1`` — multi-layer scored brief (defaults to map layers)
* ``atlas.nearest.read@v1`` — lat/lon → nearest LIVE pin(s) on allowlisted layers
* ``atlas.point.read@v1`` — exact ATLAS point_id → addressable evidence object
* ``atlas.gnss.degradation.read@v1`` — point/bbox/route → GNSS integrity field

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

# ── Catalog ───────────────────────────────────────────────────────────────────

# Every product payload carries the same content receipt (see ``make_receipt``), so the
# shape is declared once and referenced from each capability's output_schema.
_RECEIPT_OUT: dict[str, Any] = {
    "type": "object",
    "description": (
        "Tamper-evident content receipt: sha256 over the canonical payload, Ed25519-signed "
        "with the same key as the manifest. `signature_status` says whether the signature "
        "is present — a digest alone is not attributable."
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
        "capability_id": "atlas.situation.brief@v1",
        "name": "atlas.situation.brief@v1",
        "description": (
            "Cross-layer situation brief for a bbox: score, drivers, and cited LIVE pins "
            "across map layers (flood, EFFIS, lightning, volcano, alerts, events, public AIS, "
            "tsunami included by default). Fail-closed when coverage is empty. "
            "Not a forecast or insurance trigger."
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

CAP_BY_ID = {str(c["capability_id"]): c for c in PRODUCT_CAPS}


def make_receipt(payload: dict[str, Any], *, capability_id: str) -> dict[str, Any]:
    """Tamper-evident content receipt.

    sha256 alone is forgeable by anyone who edits the payload and recomputes;
    the Ed25519 signature over the canonical body (same key as the manifest)
    is what makes the receipt attributable to this ATLAS instance.
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
        receipt["signature_alg"] = "ed25519"
        receipt["signature_b64"] = signer.sign_canonical(canonical)
        receipt["public_key_b64"] = signer.public_key_b64
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
    layers = _normalize_layer_list(data.get("layers"))
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
    if cap == "atlas.point.read@v1":
        return point_read(data, stations)
    if cap == "atlas.gnss.degradation.read@v1":
        return gnss_degradation(data, stations)
    return {"ok": False, "refuse_reason": f"unhandled capability: {cap}"}


__all__ = [
    "PRODUCT_CAPS",
    "CAP_BY_ID",
    "make_receipt",
    "lookup_receipt",
    "remember_receipt",
    "watchbox_check",
    "fire_weather",
    "situation_brief",
    "nearest_read",
    "point_read",
    "gnss_degradation",
    "invoke_product",
]
