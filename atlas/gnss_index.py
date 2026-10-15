"""Materialized GNSS integrity cells shared by map, point reads and products.

The index is deliberately evidence-conservative: only station-derived scores
affect cell degradation. Curated interference events remain a separate overlay
and a separate claim class.
"""

from __future__ import annotations

import math
from .map_objects import normalized_hotspots


def state_for_score(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 25:
        return "normal"
    if score < 50:
        return "mild_degradation"
    if score < 75:
        return "degraded"
    return "severe_degradation"


def grid_cell_id(lat: float, lon: float) -> tuple[str, str]:
    """Return H3 resolution 4, with an explicitly-labelled deterministic fallback."""
    try:
        import h3  # type: ignore[import-not-found]

        return str(h3.latlng_to_cell(lat, lon, 4)), "h3-r4"
    except (ImportError, AttributeError, ValueError):
        return f"atlas-r4:{math.floor(lat / 2)}:{math.floor(lon / 2)}", "atlas-r4-fallback"


def _cell_shape(cell_id: str, scheme: str, seed_lat: float, seed_lon: float) -> tuple[float, float, list[list[float]]]:
    if scheme == "h3-r4":
        try:
            import h3  # type: ignore[import-not-found]

            lat, lon = h3.cell_to_latlng(cell_id)
            boundary = [[float(p_lon), float(p_lat)] for p_lat, p_lon in h3.cell_to_boundary(cell_id)]
            if boundary:
                boundary.append(list(boundary[0]))
            return float(lat), float(lon), boundary
        except (ImportError, AttributeError, ValueError):
            pass
    south = math.floor(seed_lat / 2) * 2.0
    west = math.floor(seed_lon / 2) * 2.0
    east = min(180.0, west + 2.0)
    north = min(90.0, south + 2.0)
    return south + 1.0, west + 1.0, [
        [west, south], [east, south], [east, north], [west, north], [west, south],
    ]


def materialize_gnss_cells(points: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate exact GNSS station points into exact, clickable field cells."""
    grouped: dict[str, dict[str, Any]] = {}
    for point in points:
        if not isinstance(point, dict) or not str(point.get("id") or "").startswith("gnss-station:"):
            continue
        try:
            lat, lon = float(point["lat"]), float(point["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        cell_id, scheme = grid_cell_id(lat, lon)
        cell = grouped.setdefault(cell_id, {
            "scheme": scheme, "seed_lat": lat, "seed_lon": lon, "scores": [],
            "confidence": [], "station_ids": [], "sources": set(), "live": False,
            "online": False,
        })
        values = point.get("values") if isinstance(point.get("values"), dict) else {}
        score = values.get("degradation_score")
        if isinstance(score, (int, float)):
            cell["scores"].append(float(score))
        confidence = values.get("confidence")
        if isinstance(confidence, (int, float)):
            cell["confidence"].append(float(confidence))
        cell["station_ids"].append(str(point.get("id") or ""))
        if point.get("source"):
            cell["sources"].add(str(point["source"]))
        cell["live"] = bool(cell["live"] or point.get("live"))
        cell["online"] = bool(cell["online"] or point.get("online"))

    out: list[dict[str, Any]] = []
    for cell_id, raw in sorted(grouped.items()):
        scores = raw["scores"]
        score = round(sum(scores) / len(scores), 2) if scores else None
        confidence_values = raw["confidence"]
        confidence = round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0.0
        state = state_for_score(score)
        lat, lon, boundary = _cell_shape(
            cell_id, str(raw["scheme"]), float(raw["seed_lat"]), float(raw["seed_lon"])
        )
        values: dict[str, Any] = {
            "latitude": lat, "longitude": lon,
            "station_count": len(raw["station_ids"]),
            "confidence": confidence,
        }
        if score is not None:
            values["degradation_score"] = score
        color = {
            "normal": "#34d399", "mild_degradation": "#f6c453",
            "degraded": "#ff7a66", "severe_degradation": "#ff4d67",
            "unknown": "#64748b",
        }[state]
        out.append({
            "id": f"gnss-cell:{cell_id}",
            "cell_id": cell_id,
            "grid_scheme": raw["scheme"],
            "layer": "gnss",
            "kind": "region",
            "lat": lat,
            "lon": lon,
            "boundary": boundary,
            "online": raw["online"],
            "live": raw["live"],
            "mode": "live",
            "has_reading": bool(scores),
            "label": "GNSS integrity cell",
            "headline": "GNSS integrity unknown" if score is None else f"GNSS degradation {score:.0f}/100",
            "color": color,
            "values": values,
            "state": state,
            "claim_class": "derived_degradation" if score is not None else "inventory_only",
            "claim_level": "derived_degradation" if score is not None else "observed_metric",
            "cause": "unestablished",
            "measurement_basis": "delivery_path_proxy" if score is not None else "station_inventory",
            "station_ids": raw["station_ids"],
            "source": "ATLAS materialized field from approved GNSS station evidence",
            "source_count": len(raw["sources"]),
            "evidence_boundary": (
                "This cell summarizes station inventory/delivery-path evidence. "
                "It does not independently prove RF jamming or spoofing."
            ),
        })
    return out


def _station_inventory_size(station: dict[str, Any]) -> int:
    points = normalized_hotspots(station)
    if points is not None:
        return len(points)
    for key in ("inventory_total", "hotspot_matched", "hotspot_count"):
        try:
            number = int(station.get(key))
        except (TypeError, ValueError):
            continue
        if number >= 0:
            return number
    return 0


def integrity_counts(stations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Spec §4.2 counters from in-memory parents, not the viewport pin list.

    The public snapshot keeps two GNSS cluster parents and densifies stations
    per viewport. Sidebar/product totals must still name the practical objects
    (stations, degraded cells, reported interference) even when those pins are
    not on the wire.
    """
    gnss_points: list[dict[str, Any]] = []
    stations_total = 0
    reporting = 0
    interference = 0
    for station in stations:
        if not isinstance(station, dict):
            continue
        layer = str(station.get("layer") or "")
        if layer == "gnss":
            points = normalized_hotspots(station)
            size = _station_inventory_size(station)
            stations_total += size
            if points:
                for row, lat, lon in points:
                    score = row.get("degradation_score")
                    state = str(row.get("state") or state_for_score(
                        float(score) if isinstance(score, (int, float)) else None
                    ))
                    if state not in ("unknown", ""):
                        reporting += 1
                    gnss_points.append({
                        "id": row.get("point_id") or f"gnss-station:{row.get('station_id')}",
                        "lat": lat,
                        "lon": lon,
                        "live": station.get("live"),
                        "online": station.get("online"),
                        "source": row.get("source") or station.get("source"),
                        "values": row,
                    })
            elif station.get("online") and size:
                # Inventory is known but the coordinate array is not on this
                # parent (count-only / stripped). Do not invent per-station state.
                pass
        elif layer == "jamming":
            points = normalized_hotspots(station)
            if points is not None:
                interference += len(points)
            else:
                try:
                    interference += int(station.get("hotspot_count") or station.get("hotspot_matched") or 0)
                except (TypeError, ValueError):
                    pass

    cells = materialize_gnss_cells(gnss_points) if gnss_points else []
    degraded = sum(1 for cell in cells if cell.get("state") == "degraded")
    severe = sum(1 for cell in cells if cell.get("state") == "severe_degradation")
    unknown_cells = sum(1 for cell in cells if cell.get("state") == "unknown")
    return {
        "stations_total": stations_total,
        "stations_reporting_now": reporting,
        "degraded_cells": degraded,
        "severe_cells": severe,
        "reported_interference_zones": interference,
        "aircraft_supporting_observations": 0,
        "vessel_supporting_observations": 0,
        "historical_satellite_samples": 0,
        "unknown_coverage_cells": unknown_cells,
    }


__all__ = ["grid_cell_id", "integrity_counts", "materialize_gnss_cells", "state_for_score"]
