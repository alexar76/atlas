"""Known geographic anchors for GAIA live relays.

Buyers cannot pass lat/lon into GAIA invoke — anchors are operator-configured.
ATLAS maps those env defaults (and documented station sites) so the UI can place
pins. Quake events carry real lat/lon in the reading itself.
"""

from __future__ import annotations

from typing import Any

# layer: weather | air | tide | grid | quake
STATION_CATALOG: dict[str, dict[str, Any]] = {
    "om-wx-01": {
        "layer": "weather",
        "label": "Open-Meteo Weather",
        "capability": "gaia.weather.read@v1",
        "lat": 52.52,
        "lon": 13.41,
        "place": "Berlin",
        "kind": "point",
    },
    "nws-01": {
        "layer": "weather",
        "label": "NWS Station",
        "capability": "gaia.weather.read@v1",
        "lat": 40.7789,
        "lon": -73.9692,
        "place": "Central Park, NYC (KNYC)",
        "kind": "point",
    },
    "om-aq-01": {
        "layer": "air",
        "label": "Open-Meteo Air Quality",
        "capability": "gaia.air.read@v1",
        "lat": 52.52,
        "lon": 13.41,
        "place": "Berlin",
        "kind": "point",
    },
    "osm-01": {
        "layer": "air",
        "label": "openSenseMap Box",
        "capability": "gaia.air.read@v1",
        "lat": 52.5200,
        "lon": 13.4050,
        "place": "Berlin senseBox",
        "kind": "point",
    },
    "sta-01": {
        "layer": "air",
        "label": "SensorThings",
        "capability": "gaia.air.read@v1",
        "lat": 52.5163,
        "lon": 13.3777,
        "place": "Berlin (SensorThings)",
        "kind": "point",
    },
    "noaa-tide-01": {
        "layer": "tide",
        "label": "NOAA CO-OPS Tide",
        "capability": "gaia.tide.read@v1",
        "lat": 40.7006,
        "lon": -74.0142,
        "place": "The Battery, NYC",
        "kind": "point",
    },
    "uk-grid-01": {
        "layer": "grid",
        "label": "UK Carbon Intensity",
        "capability": "gaia.grid.read@v1",
        "lat": 54.0,
        "lon": -2.0,
        "place": "United Kingdom",
        "kind": "region",
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
    },
}

LAYER_META: dict[str, dict[str, str]] = {
    "weather": {"color": "#3dd6c6", "label": "Weather"},
    "air": {"color": "#7ec8ff", "label": "Air quality"},
    "tide": {"color": "#4ea8de", "label": "Tide"},
    "grid": {"color": "#c4a35a", "label": "Grid carbon"},
    "quake": {"color": "#ff6b4a", "label": "Earthquakes"},
}
