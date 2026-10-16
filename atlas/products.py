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
from .product_parts.catalog import (  # noqa: F401 - re-exported
    _RECEIPT_OUT,
    PRODUCT_CAPS,
    SITUATION_BRIEF_DEFAULT_LAYERS,
    SITUATION_BRIEF_PRESETS,
)
from .product_parts.receipts import (  # noqa: F401 - re-exported
    _attach_gnss_envelope,
    _citation,
    _CLAIM_RANK,
    _evidence_records,
    _RECEIPT_CACHE,
    _RECEIPT_CACHE_MAX,
    _receipt_links,
    _STATE_RANK,
    _strongest_claim,
    _worst_state,
    lookup_receipt,
    make_receipt,
    remember_receipt,
    VERIFIER_ORIGIN,
)
from .product_parts.geometry import (  # noqa: F401 - re-exported
    _grid_cell,
    _haversine_km,
    _parse_bbox,
    _parse_query_point,
    _parse_route,
    _point_in_unwrapped_ring,
    _point_on_segment,
    _point_segment_km,
    _polygon_rings,
    _ray_cast,
    _Ring,
    _route_distance_km,
    _route_length_km,
    _unwrap_ring,
    point_in_smoke_geometry,
    smoke_geometry_evaluable,
)
from .product_parts.point_products import (  # noqa: F401 - re-exported
    _gnss_state,
    _layers_with_live_readings,
    _live_valued,
    _nearest_candidate,
    _nearest_layers,
    _normalize_layer_list,
    _num_value,
    _parent_capability,
    _point_handoff,
    _reported_claim,
    _stations_in_bbox,
    gnss_degradation,
    nearest_read,
    point_read,
    watchbox_check,
)
from .product_parts.hazard_products import (  # noqa: F401 - re-exported
    _HMS_EAST,
    _HMS_NORTH,
    _HMS_SOUTH,
    _HMS_WEST,
    fire_weather,
    situation_brief,
    smoke_operations,
)
from .product_parts.sky_products import (  # noqa: F401 - re-exported
    _AOD_ELEVATED,
    _DUST_EVENT_UGM3,
    _kp_state,
    geomag_window,
    pv_irradiance_record,
)
from .product_parts.network_products import (  # noqa: F401 - re-exported
    _DEGRADED_STATUS_WORDS,
    _radar_station_id,
    _ROUTE_HAZARD_LAYERS,
    _ROUTE_PLATFORM_LAYERS,
    _status_is_degraded,
    observability_attest,
    route_integrity,
)

from .field_products import (  # noqa: E402
    FIELD_PRODUCT_CAPS,
    field_consensus,
    field_posterior,
    field_shape,
    mesh_sample,
)

PRODUCT_CAPS.extend(FIELD_PRODUCT_CAPS)

CAP_BY_ID = {str(c["capability_id"]): c for c in PRODUCT_CAPS}


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
