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
# fire | radiation | jamming | traffic | ais | tsunami | …
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
    "gnss-euref-01": {
        "layer": "gnss",
        "label": "EUREF GNSS Integrity Network",
        "capability": "gaia.gnss.integrity.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "EPN station inventory · delivery-path integrity · CC BY 4.0",
        "kind": "event",
        "mode": "live",
    },
    "gnss-ga-01": {
        "layer": "gnss",
        "label": "Geoscience Australia GNSS Network",
        "capability": "gaia.gnss.integrity.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Public station metadata · CC BY 3.0 Australia",
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
    "feeder-iot-01": {
        "layer": "iot",
        "label": "Edge IoT Feeder",
        "capability": "gaia.iot.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Own IoT / Tasmota / TTN (offline until ingest)",
        "kind": "event",
        "mode": "live",
    },
    # ── P0 ATLAS event layers ─────────────────────────────────────────────
    "eonet-01": {
        "layer": "events",
        "label": "NASA EONET Events",
        "capability": "gaia.events.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Open natural events (map expands hotspots)",
        "kind": "event",
        "mode": "live",
    },
    "swpc-01": {
        "layer": "spacewx",
        "label": "NOAA SWPC Space Weather",
        "capability": "gaia.spacewx.read@v1",
        "lat": 40.015,
        "lon": -105.270,
        "place": "Boulder · planetary Kp + OVATION aurora",
        "kind": "event",
        "mode": "live",
    },
    "glm-01": {
        "layer": "lightning",
        "label": "GOES GLM Lightning",
        "capability": "gaia.lightning.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "GLM-L2-LCFA flashes (NOAA NODD)",
        "kind": "event",
        "mode": "live",
    },
    "nws-alerts-01": {
        "layer": "alerts",
        "label": "NWS CAP Alerts",
        "capability": "gaia.alerts.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Active NWS alerts (CAP GeoJSON centroids)",
        "kind": "event",
        "mode": "live",
    },
    # ── P0 GAIA in-situ kinds ─────────────────────────────────────────────
    "sc-01": {
        "layer": "air",
        "label": "Sensor.Community",
        "capability": "gaia.air.read@v1",
        "lat": 52.52,
        "lon": 13.41,
        "place": "Berlin SDS011 (ODbL — cite Sensor.Community)",
        "kind": "point",
        "mode": "live",
    },
    "cwop-01": {
        "layer": "weather",
        "label": "CWOP / MADIS",
        "capability": "gaia.weather.read@v1",
        "lat": 40.22,
        "lon": -74.01,
        "place": "EW1156 (CWOP-only — no restricted mesonets)",
        "kind": "point",
        "mode": "live",
    },
    "argo-01": {
        "layer": "argo",
        "label": "Global Argo Active Float Network",
        "capability": "gaia.argo.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Official GDAC · active within 30 days · DOI 10.17882/42182",
        "kind": "event",
        "mode": "live",
    },
    "metno-01": {
        "layer": "weather",
        "label": "MET Norway METAR",
        "capability": "gaia.weather.read@v1",
        "lat": 60.1939,
        "lon": 11.1004,
        "place": "Oslo Gardermoen (ENGM) — CC BY 4.0 + NLOD",
        "kind": "point",
        "mode": "live",
    },
    "usgs-geomag-01": {
        "layer": "geomag",
        "label": "USGS Geomag Boulder",
        "capability": "gaia.geomag.read@v1",
        "lat": 40.1375,
        "lon": -105.2372,
        "place": "BOU observatory F (not INTERMAGNET)",
        "kind": "point",
        "mode": "live",
    },
    # ── P1 ────────────────────────────────────────────────────────────────
    "nws-flood-01": {
        "layer": "flood",
        "label": "NWS Flood Alerts",
        "capability": "gaia.flood.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Flood / flash-flood CAP (WaterWatch JSON retired)",
        "kind": "event",
        "mode": "live",
    },
    "effis-01": {
        "layer": "effis",
        "label": "Copernicus EFFIS",
        "capability": "gaia.effis.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Current fires (CC BY 4.0 — cite Copernicus EMS / JRC)",
        "kind": "event",
        "mode": "live",
    },
    "usgs-volcano-01": {
        "layer": "volcano",
        "label": "USGS Volcanoes",
        "capability": "gaia.volcano.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Elevated alert / aviation color",
        "kind": "event",
        "mode": "live",
    },
    "dwd-01": {
        "layer": "weather",
        "label": "DWD / Bright Sky",
        "capability": "gaia.weather.read@v1",
        "lat": 52.52,
        "lon": 13.41,
        "place": "Berlin SYNOP (DWD CC BY 4.0)",
        "kind": "point",
        "mode": "live",
    },
    "eccc-01": {
        "layer": "weather",
        "label": "ECCC MSC Ottawa",
        "capability": "gaia.weather.read@v1",
        "lat": 45.41,
        "lon": -75.68,
        "place": "Climate-hourly (End-use Licence + attribution)",
        "kind": "point",
        "mode": "live",
    },
    "aurn-01": {
        "layer": "air",
        "label": "Defra AURN Marylebone",
        "capability": "gaia.air.read@v1",
        "lat": 51.5225,
        "lon": -0.1546,
        "place": "MY1 (OGL — cite Defra UK-AIR)",
        "kind": "point",
        "mode": "live",
    },
    "geonet-01": {
        "layer": "quake",
        "label": "GeoNet NZ Earthquake",
        "capability": "gaia.quake.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "GNS Science GeoNet (CC BY 3.0 NZ)",
        "kind": "event",
        "mode": "live",
    },
    "uhslc-01": {
        "layer": "tide",
        "label": "UHSLC Honolulu",
        "capability": "gaia.tide.read@v1",
        "lat": 21.3069,
        "lon": -157.8583,
        "place": "UHSLC fast-delivery gauge 57",
        "kind": "point",
        "mode": "live",
    },
    # ── P2 (licence-pinned public relays) ─────────────────────────────────
    "fintraffic-ais-01": {
        "layer": "ais",
        "label": "Fintraffic AIS",
        "capability": "gaia.ais.public.read@v1",
        "lat": 60.1699,
        "lon": 24.9384,
        "place": "Finnish waters (CC BY 4.0 — credit Fintraffic; not own-edge AIS)",
        "kind": "event",
        "mode": "live",
    },
    "eccc-hydro-01": {
        "layer": "river",
        "label": "ECCC Hydrometric · Humber at Weston",
        "capability": "gaia.river.read@v1",
        "lat": 43.7008,
        "lon": -79.5183,
        "place": "Humber River at Weston, ON (End-use Licence + attribution)",
        "kind": "point",
        "mode": "live",
    },
    "fmi-01": {
        "layer": "weather",
        "label": "FMI Helsinki",
        "capability": "gaia.weather.read@v1",
        "lat": 60.1752,
        "lon": 24.9446,
        "place": "FMI open observations (CC BY 4.0)",
        "kind": "point",
        "mode": "live",
    },
    "nws-tsunami-01": {
        "layer": "tsunami",
        "label": "NWS Tsunami Alerts",
        "capability": "gaia.tsunami.read@v1",
        "lat": 0.0,
        "lon": 0.0,
        "place": "Tsunami CAP warning/watch/advisory (not a tide gauge)",
        "kind": "event",
        "mode": "live",
    },
    "smhi-hydro-01": {
        "layer": "river",
        "label": "SMHI Hydrology · Abisko",
        "capability": "gaia.river.read@v1",
        "lat": 68.1936,
        "lon": 19.9859,
        "place": "SMHI 15-min discharge (CC BY 4.0)",
        "kind": "point",
        "mode": "live",
    },
    # ── P3 (licence-pinned public relays) ─────────────────────────────────
    "nhc-cyclone-01": {
        "layer": "cyclone",
        "label": "NHC Tropical Cyclones",
        "capability": "gaia.cyclone.read@v1",
        "lat": 25.0,
        "lon": -70.0,
        "place": "NHC/CPHC CurrentStorms (U.S. PD — Atlantic + EPac + CPac, not JTWC)",
        "kind": "event",
        "mode": "live",
    },
    "emsc-01": {
        "layer": "quake",
        "label": "EMSC Earthquakes",
        "capability": "gaia.quake.read@v1",
        "lat": 45.0,
        "lon": 10.0,
        "place": "EMSC FDSN (CC BY 4.0 — cite EMSC; preliminary; not a USGS replacement)",
        "kind": "event",
        "mode": "live",
    },
    "ea-flood-01": {
        "layer": "flood",
        "label": "EA Flood Warnings",
        "capability": "gaia.flood.read@v1",
        "lat": 52.5,
        "lon": -1.5,
        "place": "Environment Agency flood warnings (OGL — England only, not SEPA/NRW)",
        "kind": "event",
        "mode": "live",
    },
    "ptwc-01": {
        "layer": "tsunami",
        "label": "PTWC Tsunami Alerts",
        "capability": "gaia.tsunami.read@v1",
        "lat": 21.3069,
        "lon": -157.8583,
        "place": "PTWC Atom warning product (U.S. PD — not a tide gauge; empty ≠ all-clear)",
        "kind": "event",
        "mode": "live",
    },
    "kystverket-ais-01": {
        "layer": "ais",
        "label": "Kystverket AIS",
        "capability": "gaia.ais.public.read@v1",
        "lat": 60.3913,
        "lon": 5.3221,
        "place": "Norwegian waters AIS via BarentsWatch (NLOD 2.0 — not Fintraffic, not own-edge)",
        "kind": "event",
        "mode": "live",
    },
    "adsb-lol-01": {
        "layer": "adsb",
        "label": "ADSB.lol (LHR)",
        "capability": "gaia.adsb.public.read@v1",
        "lat": 51.4700,
        "lon": -0.4543,
        "place": "adsb.lol ODbL 1.0 area query — not own-edge dump1090, not OpenSky/ADSBx",
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
    "gnss": {
        "color": "#34d399",
        "label": "GNSS integrity",
        "labels": {
            "en": "GNSS integrity", "ru": "Целостность GNSS", "es": "Integridad GNSS",
            "fr": "Intégrité GNSS", "zh": "GNSS 完整性",
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
    "events": {
        "color": "#f59e0b",
        "label": "Natural events",
        "labels": {
            "en": "Natural events", "ru": "Природные события", "es": "Eventos naturales",
            "fr": "Événements naturels", "zh": "自然灾害",
        },
    },
    "spacewx": {
        "color": "#818cf8",
        "label": "Space weather",
        "labels": {
            "en": "Space weather", "ru": "Космическая погода", "es": "Clima espacial",
            "fr": "Météo spatiale", "zh": "空间天气",
        },
    },
    "lightning": {
        "color": "#fde047",
        "label": "Lightning",
        "labels": {
            "en": "Lightning", "ru": "Молнии", "es": "Rayos",
            "fr": "Foudre", "zh": "闪电",
        },
    },
    "alerts": {
        "color": "#fb7185",
        "label": "Weather alerts",
        "labels": {
            "en": "Weather alerts", "ru": "Оповещения", "es": "Alertas",
            "fr": "Alertes", "zh": "天气预警",
        },
    },
    "argo": {
        "color": "#22d3ee",
        "label": "Argo floats",
        "labels": {
            "en": "Argo floats", "ru": "Арго-буи", "es": "Flotadores Argo",
            "fr": "Flotteurs Argo", "zh": "Argo 浮标",
        },
    },
    "geomag": {
        "color": "#c084fc",
        "label": "Geomagnetism",
        "labels": {
            "en": "Geomagnetism", "ru": "Геомагнетизм", "es": "Geomagnetismo",
            "fr": "Géomagnétisme", "zh": "地磁",
        },
    },
    "iot": {
        "color": "#2dd4bf",
        "label": "Edge IoT",
        "labels": {
            "en": "Edge IoT", "ru": "IoT (edge)", "es": "IoT edge",
            "fr": "IoT edge", "zh": "边缘物联网",
        },
    },
    "flood": {
        "color": "#38bdf8",
        "label": "Flood",
        "labels": {
            "en": "Flood", "ru": "Паводок", "es": "Inundación",
            "fr": "Crue", "zh": "洪水",
        },
    },
    "effis": {
        "color": "#ea580c",
        "label": "EFFIS fires",
        "labels": {
            "en": "EFFIS fires", "ru": "EFFIS пожары", "es": "Incendios EFFIS",
            "fr": "Feux EFFIS", "zh": "EFFIS 火情",
        },
    },
    "volcano": {
        "color": "#ef4444",
        "label": "Volcanoes",
        "labels": {
            "en": "Volcanoes", "ru": "Вулканы", "es": "Volcanes",
            "fr": "Volcans", "zh": "火山",
        },
    },
    "ais": {
        "color": "#0891b2",
        "label": "Public AIS",
        "labels": {
            "en": "Public AIS", "ru": "AIS (открытый)", "es": "AIS público",
            "fr": "AIS public", "zh": "公开 AIS",
        },
    },
    "tsunami": {
        "color": "#e11d48",
        "label": "Tsunami alerts",
        "labels": {
            "en": "Tsunami alerts", "ru": "Цунами", "es": "Alertas de tsunami",
            "fr": "Alertes tsunami", "zh": "海啸预警",
        },
    },
    "cyclone": {
        "color": "#7c3aed",
        "label": "Tropical cyclones",
        "labels": {
            "en": "Tropical cyclones", "ru": "Тропические циклоны",
            "es": "Ciclones tropicales", "fr": "Cyclones tropicaux", "zh": "热带气旋",
        },
    },
    "adsb": {
        "color": "#0ea5e9",
        "label": "Public ADS-B",
        "labels": {
            "en": "Public ADS-B", "ru": "ADS-B (открытый)", "es": "ADS-B público",
            "fr": "ADS-B public", "zh": "公开 ADS-B",
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
