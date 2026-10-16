"""Geometry the products share: distances, grid cells, points on segments and in polygons,
smoke geometry, and parsing bounding boxes, points and routes.
"""

from __future__ import annotations

import math
from typing import Any

from ..geo import normalize_bbox
from ..gnss_index import grid_cell_id


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


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
        if products._point_on_segment(x, lat, ax, ay, bx, by):
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
        if products._ray_cast(lat, lon + 360.0 * k, points):
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
            unwrapped = products._unwrap_ring(ring)
            if unwrapped is None:
                return None
            rings.append(unwrapped)
        out.append(rings)
    return out


def smoke_geometry_evaluable(geometry: Any) -> bool:
    """True when containment can be decided against this geometry at all."""
    return products._polygon_rings(geometry) is not None


def point_in_smoke_geometry(lat: float, lon: float, geometry: Any) -> bool:
    """Boundary-inclusive point-in-polygon with KML holes and date-line support."""
    parts = products._polygon_rings(geometry)
    if parts is None:
        return False
    for rings in parts:
        if products._point_in_unwrapped_ring(lat, lon, rings[0]) and not any(
            products._point_in_unwrapped_ring(lat, lon, hole) for hole in rings[1:]
        ):
            return True
    return False


def _parse_query_point(data: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


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
    return min(products._point_segment_km(lat, lon, *a, *b) for a, b in zip(route, route[1:]))


def _route_length_km(route: list[tuple[float, float]]) -> float:
    return sum(
        products._haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(route, route[1:])
    )


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
