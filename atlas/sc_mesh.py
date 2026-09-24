"""ATLAS Sensor.Community mesh — loads ``atlas/config/sc_mesh_cities.yaml``.

Must stay byte-identical to ``gaia/config/sc_mesh_cities.yaml``
(``./scripts/sync_physical_sensor_catalogs.sh`` + CI).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

import yaml


class ScCity(TypedDict, total=False):
    slug: str
    place: str
    lat: float
    lon: float
    radius_km: float
    aliases: list[str]


def _config_path() -> Path:
    # Local/monorepo: atlas/atlas/sc_mesh.py → atlas/config/
    # Docker image:   /app/atlas/sc_mesh.py → /app/config/
    return Path(__file__).resolve().parents[1] / "config" / "sc_mesh_cities.yaml"


@lru_cache(maxsize=1)
def _load_cities() -> tuple[ScCity, ...]:
    path = _config_path()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cities = raw.get("cities") or []
    out: list[ScCity] = []
    for row in cities:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue
        radius = float(row.get("radius_km") or 5.0)
        out.append(
            {
                "slug": slug,
                "place": str(row.get("place") or slug),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "radius_km": max(0.1, min(radius, 25.0)),
                "aliases": [str(a) for a in (row.get("aliases") or []) if str(a).strip()],
            }
        )
    if not out:
        raise RuntimeError(f"sc_mesh_cities.yaml empty or missing cities: {path}")
    return tuple(out)


SC_MESH_CITIES: tuple[ScCity, ...] = _load_cities()


def atlas_catalog_entries() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for city in SC_MESH_CITIES:
        slug = city["slug"]
        place = city["place"]
        out[f"sc-{slug}"] = {
            "layer": "air",
            "label": f"Sensor.Community · {place}",
            "capability": "gaia.air.read@v1",
            "lat": float(city["lat"]),
            "lon": float(city["lon"]),
            "place": f"{place} (ODbL — cite Sensor.Community; crowd ≠ reference)",
            "kind": "point",
            "mode": "live",
        }
    return out


def place_targets() -> dict[str, dict[str, Any]]:
    """Analyst flyTo targets for SC mesh cities (slug keys, merge-friendly)."""
    out: dict[str, dict[str, Any]] = {}
    for city in SC_MESH_CITIES:
        slug = city["slug"]
        place = city["place"]
        aliases = tuple(city.get("aliases") or (slug, place.lower()))
        out[slug] = {
            "aliases": aliases,
            "station_ids": (f"sc-{slug}",),
            "lon": float(city["lon"]),
            "lat": float(city["lat"]),
            "zoom": 10.5,
            "label": f"Sensor.Community · {place}",
        }
    return out
