"""Honest, typed counters for the ATLAS layer switcher.

The catalog contains a mix of physical stations, upstream relays and parent
SKUs whose readings fan out into many event pins.  Counting catalog rows alone
therefore turns a failed or not-yet-fetched event feed into a misleading ``1``.
This module keeps the number and its meaning together.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from .map_objects import is_actionable_station, normalized_hotspots

if TYPE_CHECKING:
    from collections.abc import Iterable


LAYER_COUNT_KIND: dict[str, str] = {
    "fire": "detections",
    "radiation": "observations",
    "spacewx": "observations",
    "quake": "events",
    "jamming": "events",
    "gnss": "stations",
    "events": "events",
    "lightning": "events",
    "alerts": "events",
    "flood": "events",
    "effis": "events",
    "volcano": "events",
    "argo": "floats",
    "grid": "sources",
    "geomag": "sources",
    "traffic": "sources",
    "iot": "sources",
}

CLUSTER_COUNT_KINDS = frozenset({"detections", "observations", "events", "floats"})


def _non_negative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _cluster_count(station: dict[str, Any], layer: str) -> int | None:
    """Return the number represented by the layer's actionable map objects.

    FIRMS is the intentional exception: it is viewport-paged, so its global
    ``hotspot_matched`` can exceed the pins in the current packet. GNSS is the
    other: the wire snapshot keeps two cluster parents and densifies stations
    per viewport, so the sidebar total must come from inventory metadata, not
    from counting those parents as ``2`` (or ``1`` because one API exists).
    Other event layers must prefer the actual coordinate array; their sidebar
    total is a promise that the same number of objects can be inspected on the map.
    """
    points = normalized_hotspots(station)
    if layer == "gnss":
        for key in ("inventory_total", "hotspot_count", "hotspot_matched"):
            if key not in station:
                continue
            number = _non_negative_int(station.get(key))
            if number is not None:
                return number
        return len(points) if points is not None else None
    if layer != "fire":
        # Non-paged feeds may advertise metadata counts only after transporting
        # the coordinate array. Without it there is nothing a person can open.
        return len(points) if points is not None else None
    for key in ("hotspot_matched", "hotspot_count"):
        if key in station:
            number = _non_negative_int(station.get(key))
            if number is not None:
                return number
    if points is not None:
        return len(points)
    return None


def build_layer_counts(
    stations: Iterable[dict[str, Any]],
    layer_keys: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """Build UI-ready counts without conflating sources with observations.

    ``count`` is ``None`` when a cluster feed has not produced a count yet.  A
    stale but known cluster remains visible with ``status=stale``; point/source
    layers expose live/total sources so offline configured feeders show ``0/1``
    instead of pretending to be one live object.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for station in stations:
        if not isinstance(station, dict):
            continue
        layer = str(station.get("layer") or "")
        if layer:
            grouped[layer].append(station)

    result: dict[str, dict[str, Any]] = {}
    for layer in layer_keys:
        rows = grouped.get(str(layer), [])
        total_sources = len(rows)
        live_sources = sum(1 for row in rows if row.get("online"))
        has_cluster = any(
            normalized_hotspots(row) is not None
            or any(key in row for key in ("hotspot_count", "hotspot_matched"))
            for row in rows
        )
        count_kind = LAYER_COUNT_KIND.get(
            str(layer), "observations" if has_cluster else "stations"
        )
        dense_station_inventory = str(layer) == "gnss"
        if has_cluster and count_kind not in CLUSTER_COUNT_KINDS and not dense_station_inventory:
            count_kind = "observations"

        if count_kind in CLUSTER_COUNT_KINDS or dense_station_inventory:
            known = [
                number
                for row in rows
                if (number := _cluster_count(row, str(layer))) is not None
            ]
            count: int | None = sum(known) if known else None
            if known and live_sources:
                status = "live" if live_sources == total_sources else "partial"
            elif known:
                status = "stale"
            else:
                status = "unavailable"
        else:
            count = sum(1 for row in rows if is_actionable_station(row))
            if count == total_sources and total_sources:
                status = "live"
            elif count:
                status = "partial"
            elif total_sources:
                status = "configured"
            else:
                status = "unavailable"

        result[str(layer)] = {
            "count": count,
            "count_kind": count_kind,
            "status": status,
            "live_sources": live_sources,
            "total_sources": total_sources,
        }
    return result
