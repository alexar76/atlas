"""Known geographic anchors for GAIA live relays and simulators.

Buyers cannot pass lat/lon into GAIA invoke — anchors are operator-configured.
ATLAS maps those env defaults (and documented station sites) so the UI can place
pins. Quake events carry real lat/lon in the reading itself.

Honesty (same rule as GAIA Fleet.status): a pin is LIVE only when the upstream
device carries a provenance ``source`` URL/licence. Simulators have none.
Catalog ``mode`` is the intended class; fleet ``source`` is the ground truth.
"""

from __future__ import annotations

from typing import Any

from .extra_sensors import atlas_catalog_entries as extra_sensor_entries
from .om_mesh import atlas_catalog_entries

# Demo campus for GAIA simulators (no real lat/lon on the devices — map-only anchor).
_DEMO_LAT = 46.9480
_DEMO_LON = 7.4474

# layer keys: weather | air | tide | river | marine | grid | quake | energy |
# fire | radiation | jamming | traffic
# mode: live = public-API relay · sim = physics simulator (no upstream source)
STATION_CATALOG: dict[str, dict[str, Any]] = {
    # ── LIVE relays ───────────────────────────────────────────────────────
    "om-wx-01": {
        "layer": "weather",
        "label": "Open-Meteo Weather",
        "capability": "gaia.weather.read@v1",
        "lat": 52.52,
        "lon": 13.41,
        "place": "Berlin",
        "kind": "point",
        "mode": "live",
    },
    "nws-01": {
        "layer": "weather",
        "label": "NWS Station",
        "capability": "gaia.weather.read@v1",
        "lat": 40.7789,
        "lon": -73.9692,
        "place": "Central Park, NYC (KNYC)",
        "kind": "point",
        "mode": "live",
    },
    "om-aq-01": {
        "layer": "air",
        "label": "Open-Meteo Air Quality",
        "capability": "gaia.air.read@v1",
        "lat": 52.52,
        "lon": 13.41,
        "place": "Berlin",
        "kind": "point",
        "mode": "live",
    },
    "osm-01": {
        "layer": "air",
        "label": "openSenseMap Box",
        "capability": "gaia.air.read@v1",
        "lat": 52.5200,
        "lon": 13.4050,
        "place": "Berlin senseBox",
        "kind": "point",
        "mode": "live",
    },
    "sta-01": {
        "layer": "air",
        "label": "SensorThings",
        "capability": "gaia.air.read@v1",
        "lat": 52.5163,
        "lon": 13.3777,
        "place": "Berlin (SensorThings)",
        "kind": "point",
        "mode": "live",
    },
    "noaa-tide-01": {
        "layer": "tide",
        "label": "NOAA CO-OPS Tide",
        "capability": "gaia.tide.read@v1",
        "lat": 40.7006,
        "lon": -74.0142,
        "place": "The Battery, NYC",
        "kind": "point",
        "mode": "live",
    },
    "uk-grid-01": {
        "layer": "grid",
        "label": "UK Carbon Intensity",
        "capability": "gaia.grid.read@v1",
        "lat": 54.0,
        "lon": -2.0,
        "place": "United Kingdom",
        "kind": "region",
        "mode": "live",
    },
    "usgs-quake-01": {
        "layer": "quake",
        "label": "USGS Earthquake",
        "capability": "gaia.quake.read@v1",
        # Event coordinates come from the reading; catalog coords are fallback.
        "lat": 0.0,
        "lon": 0.0,
        "place": "Latest event",
        "kind": "event",
        "mode": "live",
    },
    "usgs-river-01": {
        "layer": "river",
        "label": "USGS River · Potomac at Little Falls",
        "capability": "gaia.river.read@v1",
        "lat": 38.9495,
        "lon": -77.1275,
        "place": "Potomac River, MD/DC",
        "kind": "point",
        "mode": "live",
    },
    "ndbc-01": {
        "layer": "marine",
        "label": "NDBC Buoy 44025 · NY Bight",
        "capability": "gaia.marine.read@v1",
        "lat": 40.251,
        "lon": -73.164,
        "place": "New York Bight",
        "kind": "point",
        "mode": "live",
    },
    "om-marine-01": {
        "layer": "marine",
        "label": "Open-Meteo Marine · NYC Harbor",
        "capability": "gaia.marine.read@v1",
        "lat": 40.70,
        "lon": -74.01,
        "place": "New York Harbor",
        "kind": "point",
        "mode": "live",
    },
    # Free-to-commercialize open relays (+ own edge feeders)
    "firms-fire-01": {
        "layer": "fire",
        "label": "NASA FIRMS Fire",
        "capability": "gaia.fire.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "VIIRS active-fire cluster (map expands hotspots)",
        "kind": "event",
        "mode": "live",
    },
    "safecast-01": {
        "layer": "radiation",
        "label": "Safecast Radiation",
        "capability": "gaia.radiation.read@v1",
        "lat": 37.42,
        "lon": 141.03,
        "place": "Fukushima region (default anchor)",
        "kind": "event",
        "mode": "live",
    },
    "cybernews-jam-01": {
        "layer": "jamming",
        "label": "CyberNews GNSS Jamming",
        "capability": "gaia.jamming.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Latest interference event",
        "kind": "event",
        "mode": "live",
    },
    "feeder-adsb-01": {
        "layer": "traffic",
        "label": "Edge ADS-B Feeder",
        "capability": "gaia.adsb.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Own dump1090 (offline until ingest)",
        "kind": "event",
        "mode": "live",
    },
    "feeder-ais-01": {
        "layer": "traffic",
        "label": "Edge AIS Feeder",
        "capability": "gaia.ais.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Own AIS receiver (offline until ingest)",
        "kind": "event",
        "mode": "live",
    },
    # ── SIM (physics simulators — always present on GAIA; no upstream source) ─
    "ws-01": {
        "layer": "weather",
        "label": "Weather Sim A",
        "capability": "gaia.weather.read@v1",
        "lat": _DEMO_LAT,
        "lon": _DEMO_LON,
        "place": "GAIA demo campus (sim)",
        "kind": "point",
        "mode": "sim",
    },
    "ws-02": {
        "layer": "weather",
        "label": "Weather Sim B",
        "capability": "gaia.weather.read@v1",
        "lat": _DEMO_LAT + 0.012,
        "lon": _DEMO_LON + 0.018,
        "place": "GAIA demo campus (sim)",
        "kind": "point",
        "mode": "sim",
    },
    "aq-01": {
        "layer": "air",
        "label": "Air Quality Sim",
        "capability": "gaia.air.read@v1",
        "lat": _DEMO_LAT - 0.008,
        "lon": _DEMO_LON + 0.022,
        "place": "GAIA demo campus (sim)",
        "kind": "point",
        "mode": "sim",
    },
    "em-01": {
        "layer": "energy",
        "label": "Energy Meter Sim",
        "capability": "gaia.energy.read@v1",
        "lat": _DEMO_LAT + 0.006,
        "lon": _DEMO_LON - 0.015,
        "place": "GAIA demo campus (sim)",
        "kind": "point",
        "mode": "sim",
    },
}

# Global Open-Meteo mesh (Ottawa, New Delhi, Tokyo, …) — keep in sync with GAIA.
STATION_CATALOG.update(atlas_catalog_entries())
# Operator one-command extras (gaia/config/extra_sensors.yaml mirror).
STATION_CATALOG.update(extra_sensor_entries())

# ``label`` = EN default; ``labels`` = EN/RU/ES/FR/ZH for map UI + landings.
LAYER_META: dict[str, dict[str, Any]] = {
    "weather": {
        "color": "#3dd6c6",
        "label": "Weather",
        "labels": {
            "en": "Weather", "ru": "Погода", "es": "Clima", "fr": "Météo", "zh": "天气",
        },
    },
    "air": {
        "color": "#7ec8ff",
        "label": "Air quality",
        "labels": {
            "en": "Air quality", "ru": "Воздух", "es": "Aire", "fr": "Air", "zh": "空气质量",
        },
    },
    "tide": {
        "color": "#4ea8de",
        "label": "Tide",
        "labels": {
            "en": "Tide", "ru": "Прилив", "es": "Marea", "fr": "Marée", "zh": "潮汐",
        },
    },
    "river": {
        "color": "#38bdf8",
        "label": "Rivers",
        "labels": {
            "en": "Rivers", "ru": "Реки", "es": "Ríos", "fr": "Rivières", "zh": "河流",
        },
    },
    "marine": {
        "color": "#2563eb",
        "label": "Marine",
        "labels": {
            "en": "Marine", "ru": "Море", "es": "Marino", "fr": "Marin", "zh": "海洋",
        },
    },
    "grid": {
        "color": "#c4a35a",
        "label": "Grid carbon",
        "labels": {
            "en": "Grid carbon", "ru": "Сеть (углерод)", "es": "Red (carbono)",
            "fr": "Réseau (carbone)", "zh": "电网碳强度",
        },
    },
    "quake": {
        "color": "#ff6b4a",
        "label": "Earthquakes",
        "labels": {
            "en": "Earthquakes", "ru": "Землетрясения", "es": "Sismos",
            "fr": "Séismes", "zh": "地震",
        },
    },
    "energy": {
        "color": "#e8b86d",
        "label": "Energy",
        "labels": {
            "en": "Energy", "ru": "Энергия", "es": "Energía", "fr": "Énergie", "zh": "能源",
        },
    },
    "fire": {
        "color": "#f97316",
        "label": "Wildfire",
        "labels": {
            "en": "Wildfire", "ru": "Пожары", "es": "Incendios", "fr": "Incendies", "zh": "野火",
        },
    },
    "radiation": {
        "color": "#a3e635",
        "label": "Radiation",
        "labels": {
            "en": "Radiation", "ru": "Радиация", "es": "Radiación",
            "fr": "Radiation", "zh": "辐射",
        },
    },
    "jamming": {
        "color": "#e879f9",
        "label": "GNSS jamming",
        "labels": {
            "en": "GNSS jamming", "ru": "GNSS-глушение", "es": "Interferencia GNSS",
            "fr": "Brouillage GNSS", "zh": "GNSS 干扰",
        },
    },
    "traffic": {
        "color": "#94a3b8",
        "label": "Edge traffic",
        "labels": {
            "en": "Edge traffic", "ru": "Трафик (edge)", "es": "Tráfico edge",
            "fr": "Trafic edge", "zh": "边缘交通",
        },
    },
}


def resolve_mode(*, catalog_mode: str, source: Any, in_fleet: bool) -> tuple[str, bool]:
    """Return (mode, live). LIVE only when a provenance source string is present."""
    if source:
        return "live", True
    if in_fleet:
        # Fleet device with no source ⇒ simulator (GAIA rule).
        return "sim", False
    mode = "sim" if catalog_mode == "sim" else "live"
    return mode, False
