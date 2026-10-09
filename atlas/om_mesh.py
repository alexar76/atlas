"""ATLAS Open-Meteo mesh — loads ``atlas/config/om_mesh_cities.yaml``.

Must stay byte-identical to ``gaia/config/om_mesh_cities.yaml``
(``./scripts/sync_om_mesh_catalog.sh`` + CI).

Berlin remains on legacy catalog ids ``om-wx-01`` / ``om-aq-01``.

Developer onboarding: ``docs/add-gaia-atlas-sensor.md``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

import yaml


class OmCity(TypedDict, total=False):
    slug: str
    place: str
    lat: float
    lon: float
    aliases: list[str]


def _config_path() -> Path:
    # Local/monorepo: atlas/atlas/om_mesh.py → atlas/config/
    # Docker image:   /app/atlas/om_mesh.py → /app/config/
    return Path(__file__).resolve().parents[1] / "config" / "om_mesh_cities.yaml"


@lru_cache(maxsize=1)
def _load_cities() -> tuple[OmCity, ...]:
    path = _config_path()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cities = raw.get("cities") or []
    out: list[OmCity] = []
    for row in cities:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "").strip()
        if not slug:
            continue
        out.append(
            {
                "slug": slug,
                "place": str(row.get("place") or slug),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "aliases": [str(a) for a in (row.get("aliases") or []) if str(a).strip()],
            }
        )
    if not out:
        raise RuntimeError(f"om_mesh_cities.yaml empty or missing cities: {path}")
    return tuple(out)


OM_MESH_CITIES: tuple[OmCity, ...] = _load_cities()


def atlas_catalog_entries() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for city in OM_MESH_CITIES:
        slug = city["slug"]
        place = city["place"]
        lat = float(city["lat"])
        lon = float(city["lon"])
        out[f"om-wx-{slug}"] = {
            "layer": "weather",
            "label": f"Open-Meteo Weather · {place}",
            "capability": "gaia.weather.read@v1",
            "lat": lat,
            "lon": lon,
            "place": place,
            "kind": "point",
            "mode": "live",
        }
        out[f"om-aq-{slug}"] = {
            "layer": "air",
            "label": f"Open-Meteo Air · {place}",
            "capability": "gaia.air.read@v1",
            "lat": lat,
            "lon": lon,
            "place": place,
            "kind": "point",
            "mode": "live",
        }
    return out


def place_targets() -> dict[str, dict[str, Any]]:
    """Analyst flyTo targets for mesh cities (aliases from YAML)."""
    out: dict[str, dict[str, Any]] = {}
    for city in OM_MESH_CITIES:
        slug = city["slug"]
        place = city["place"]
        aliases = tuple(city.get("aliases") or (slug, place.lower()))
        out[slug] = {
            "aliases": aliases,
            "station_ids": (f"om-wx-{slug}", f"om-aq-{slug}"),
            "lon": float(city["lon"]),
            "lat": float(city["lat"]),
            "zoom": 9.5,
            "label": place,
        }
    return out
