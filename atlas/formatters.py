"""Human-readable labels and summaries for GAIA sensor readings."""

from __future__ import annotations

import time
from typing import Any

from .map_objects import NDW_NOTICE_IDS, TORONTO_ROADS_ID, without_expired_source_reading

FIELD_META: dict[str, dict[str, str]] = {
    **{f"{taxon}_pollen_grains_m3": {"label": f"{taxon.title()} pollen", "unit": "grains/m³",
                                   "hint": "Hourly concentration measured by MeteoSwiss"}
       for taxon in ("alder", "ash", "beech", "birch", "grass", "hazel", "oak")},
    "connector_count": {"label": "Connectors", "unit": "", "hint": "Reported connectors at this site"},
    "available_count": {"label": "Available connectors", "unit": "", "hint": "Operator-reported availability"},
    "max_power_kw": {"label": "Maximum rated power", "unit": "kW", "hint": "Highest published connector rating"},
    "area_ha": {"label": "Reported fire area", "unit": "ha", "hint": "Size reported for the incident"},
    "perimeter_area_ha": {"label": "Perimeter area", "unit": "ha", "hint": "Area of the published outline"},
    "perimeter_observation_unix": {"label": "Perimeter observed", "unit": "", "hint": "Source timestamp of the outline"},
    "ignition_unix": {"label": "Incident reported", "unit": "", "hint": "Reported start time"},
    "volcanic_alert_level": {"label": "Volcanic alert level", "unit": "", "hint": "GeoNet volcanic alert scale 0–5"},
    "hail_size_mm": {"label": "Reported hail diameter", "unit": "mm", "hint": "Preliminary NOAA SPC report"},
    "forecast_hour": {"label": "Forecast horizon", "unit": "h", "hint": "Hours after advisory issue"},
    "wave_qc_flag": {"label": "Wave quality flag", "unit": "", "hint": "Provider code 1 is good and 0 is unevaluated"},
    "sea_temperature_c": {"label": "Sea-surface temperature", "unit": "°C", "hint": "Measured by the buoy"},
    "wind_direction_deg": {"label": "Wind direction", "unit": "°", "hint": "Direction relative to true north"},
    "water_level_nn2000_m": {"label": "Water level", "unit": "m NN2000", "hint": "Relative to Norway’s NN2000 vertical datum"},
    "air_gap_m": {"label": "Bridge clearance", "unit": "m", "hint": "Distance from the designated bridge reference point to the water surface"},
    "air_gap_sigma_m": {"label": "Sample standard deviation", "unit": "m", "hint": "NOAA’s reported spread for the measurement interval"},
    "air_gap_outlier_count": {"label": "Outlier samples", "unit": "", "hint": "One-second samples outside NOAA’s three-sigma limit"},
    "air_gap_flat_flag": {"label": "Flat signal flag", "unit": "", "hint": "NOAA quality flag"},
    "air_gap_rate_flag": {"label": "Rate flag", "unit": "", "hint": "NOAA quality flag"},
    "air_gap_limit_flag": {"label": "Limit flag", "unit": "", "hint": "NOAA quality flag"},
    "sea_level_pressure_hpa": {"label": "Sea-level pressure", "unit": "hPa", "hint": "Pressure reported by the drifter when available"},
    "customers_affected": {"label": "Customers affected", "unit": "", "hint": "Count reported by UK Power Networks"},
    "bikes_available": {"label": "Bikes available", "unit": "", "hint": "Bicycles available to rent at the station"},
    "ebikes_available": {"label": "E-bikes available", "unit": "", "hint": "Electric bicycles included in the available bike count"},
    "docks_available": {"label": "Docks available", "unit": "", "hint": "Docks reported as available for returns"},
    "is_renting": {"label": "Rentals enabled", "unit": "", "hint": "Station status reported by Bike Share Toronto"},
    "is_returning": {"label": "Returns enabled", "unit": "", "hint": "Station status reported by Bike Share Toronto"},
    "coastal_water_height_m": {"label": "Water height", "unit": "m", "hint": "Above the local GeoNet pressure sensor"},
    "coastal_sensor_code": {"label": "Sensor code", "unit": "", "hint": "GeoNet local pressure sensor identifier"},
    "water_temperature_c": {"label": "Water temperature", "unit": "°C", "hint": "Measured water temperature"},
    "dose_equivalent_nsv_h": {"label": "Ambient dose rate", "unit": "nSv/h", "hint": "Measured ambient gamma dose equivalent per hour"},
    "drap_frequency_mhz": {"label": "1 dB threshold frequency", "unit": "MHz", "hint": "Highest modeled frequency affected by 1 dB of absorption"},
    "measurement_depth_m": {"label": "Measurement depth", "unit": "m", "hint": "Depth below the sea surface"},
    "salinity_psu": {"label": "Salinity", "unit": "PSU", "hint": "Practical salinity at the measurement depth"},
    "dissolved_oxygen_ml_l": {"label": "Dissolved oxygen", "unit": "mL/L", "hint": "Measured at the specified depth"},
    "current_speed_mps": {"label": "Current speed", "unit": "m/s", "hint": "Measured water current speed"},
    "current_direction_deg": {"label": "Current direction", "unit": "°", "hint": "Measured water current direction"},
    "forecast_smoke_pm2_5_ugm3": {"label": "Forecast PM2.5 in smoke plume", "unit": "µg/m³", "hint": "Modeled near-surface concentration within wildfire smoke plumes"},
    "forecast_run_unix": {"label": "Model run", "unit": "", "hint": "Time the source model run was initialized"},
    "temperature_c": {
        "label": "Temperature",
        "unit": "°C",
        "hint": "Air temperature at the station",
    },
    "humidity_pct": {
        "label": "Humidity",
        "unit": "%",
        "hint": "Relative humidity",
    },
    "pressure_hpa": {
        "label": "Pressure",
        "unit": "hPa",
        "hint": "Atmospheric pressure",
    },
    "wind_mps": {
        "label": "Wind",
        "unit": "m/s",
        "hint": "Wind speed",
    },
    "pm2_5_ugm3": {
        "label": "PM2.5",
        "unit": "µg/m³",
        "hint": "Fine particulate matter (≤2.5 µm)",
    },
    "pm10_ugm3": {
        "label": "PM10",
        "unit": "µg/m³",
        "hint": "Coarse particulate matter (≤10 µm)",
    },
    "co2_ppm": {
        "label": "CO₂",
        "unit": "ppm",
        "hint": "Carbon dioxide concentration",
    },
    "voc_index": {
        "label": "VOC index",
        "unit": "",
        "hint": "Volatile organic compounds (relative index)",
    },
    "air_quality_index": {
        "label": "UK DAQI",
        "unit": "",
        "hint": "UK Daily Air Quality Index (1 low … 10 very high)",
    },
    "water_level_maod": {
        "label": "Measured coastal water level",
        "unit": "mAOD",
        "hint": "15-minute mean relative to Ordnance Datum at Newlyn",
    },
    "forecast_stage_m": {
        "label": "Forecast peak stage",
        "unit": "m",
        "hint": "Highest available forecast sample in the next 72 hours, above local gage datum",
    },
    "forecast_issued_unix": {"label": "Forecast issued", "unit": "", "hint": "NOAA/NWS issue time"},
    "forecast_valid_unix": {"label": "Forecast peak valid at", "unit": "", "hint": "Time of the forecast sample"},
    "water_level_m": {
        "label": "Water level",
        "unit": "m",
        "hint": "Tide gauge height (MLLW, metric)",
    },
    "discharge_m3s": {
        "label": "Discharge",
        "unit": "m³/s",
        "hint": "River streamflow",
    },
    "gage_height_m": {
        "label": "Gage height",
        "unit": "m",
        "hint": "River stage above datum",
    },
    "flood_gage_level_m": {"label": "Gage water level", "unit": "m", "hint": "Level on the threshold's reference datum"},
    "flood_threshold_m": {"label": "Surveyed threshold", "unit": "m", "hint": "Water level at which local inundation is possible"},
    "flood_exceedance_m": {"label": "Above threshold", "unit": "m", "hint": "Provisional difference between gage level and threshold"},
    "groundwater_depth_m": {
        "label": "Depth to water",
        "unit": "m",
        "hint": "Measured from the local land surface, positive downward",
    },
    "forecast_hour": {"label": "Forecast lead", "unit": "h", "hint": ""},
    "base_ft": {"label": "Base altitude", "unit": "ft", "hint": "Source G-AIRMET base"},
    "top_ft": {"label": "Top altitude", "unit": "ft", "hint": "Source G-AIRMET top"},
    "level_ft": {"label": "Freezing level", "unit": "ft", "hint": "Source G-AIRMET contour"},
    "groundwater_reference_depth_m": {
        "label": "Depth to water from measuring reference",
        "unit": "m",
        "hint": "Measured from the station reference point, positive downward",
    },
    "groundwater_level_ngf_m": {
        "label": "Water elevation (NGF)",
        "unit": "m",
        "hint": "Water elevation on France's NGF vertical datum",
    },
    "source_updated_date": {"label": "Source update date", "unit": "", "hint": ""},
    "approval_status": {"label": "Review status", "unit": "", "hint": ""},
    "qualifier": {"label": "USGS qualifier", "unit": "", "hint": ""},
    "wave_height_m": {
        "label": "Wave height",
        "unit": "m",
        "hint": "Significant wave height",
    },
    "wave_period_s": {"label": "Wave period", "unit": "s", "hint": "Wave period reported by the source"},
    "wave_direction_deg": {"label": "Wave direction", "unit": "°", "hint": "Direction waves come from, clockwise from true north"},
    "snow_depth_cm": {"label": "Snow depth", "unit": "cm", "hint": "Depth of the snowpack"},
    "snow_water_equivalent_cm": {"label": "Snow-water equivalent", "unit": "cm", "hint": "Depth of water in the snowpack if melted"},
    "sst_c": {
        "label": "Sea surface temp",
        "unit": "°C",
        "hint": "Sea-surface temperature",
    },
    "carbon_intensity_gco2_kwh": {
        "label": "Carbon intensity",
        "unit": "gCO₂/kWh",
        "hint": "Grid electricity carbon intensity (UK)",
    },
    "magnitude": {
        "label": "Magnitude",
        "unit": "M",
        "hint": "Earthquake magnitude",
    },
    "depth_km": {
        "label": "Depth",
        "unit": "km",
        "hint": "Hypocenter depth",
    },
    "latitude": {
        "label": "Latitude",
        "unit": "°",
        "hint": "Event latitude",
    },
    "longitude": {
        "label": "Longitude",
        "unit": "°",
        "hint": "Event longitude",
    },
    "voltage_v": {
        "label": "Voltage",
        "unit": "V",
        "hint": "Mains voltage",
    },
    "current_a": {
        "label": "Current",
        "unit": "A",
        "hint": "Line current",
    },
    "power_w": {
        "label": "Power",
        "unit": "W",
        "hint": "Instantaneous real power",
    },
    "energy_wh": {
        "label": "Energy",
        "unit": "Wh",
        "hint": "Cumulative energy register",
    },
    "relay_on": {
        "label": "Relay",
        "unit": "",
        "hint": "Whether the plug's relay is closed (the socket is powered)",
    },
    "price_eur_mwh": {
        "label": "Day-ahead price",
        "unit": "€/MWh",
        "hint": "Exchange clearing price for the current quarter-hour; wholesale, not a tariff",
    },
    "price_min_24h_eur_mwh": {"label": "24 h low", "unit": "€/MWh", "hint": "Lowest price in the next 24 h"},
    "price_mean_24h_eur_mwh": {"label": "24 h mean", "unit": "€/MWh", "hint": "Mean price over the next 24 h"},
    "price_max_24h_eur_mwh": {"label": "24 h high", "unit": "€/MWh", "hint": "Highest price in the next 24 h"},
    "negative_intervals_24h": {
        "label": "Negative-price intervals",
        "unit": "",
        "hint": "Quarter-hours in the next 24 h at which the price is below zero",
    },
    "interval_start_unix": {"label": "Interval start", "unit": "", "hint": "Start of the priced interval"},
    "horizon_end_unix": {"label": "Prices known until", "unit": "", "hint": "End of the published day-ahead horizon"},
    "resolution_min": {"label": "Resolution", "unit": "min", "hint": "Length of one priced interval"},
    "ndvi": {"label": "NDVI", "unit": "", "hint": "Vegetation index, −1…1: dense green vegetation is above 0.6"},
    "ndwi": {"label": "NDWI", "unit": "", "hint": "Water index, −1…1: open water is above 0"},
    "nbr": {"label": "NBR", "unit": "", "hint": "Normalised burn ratio: a drop between images marks a burn scar"},
    "ndmi": {"label": "NDMI", "unit": "", "hint": "Moisture index: vegetation water content"},
    "reflectance_green": {"label": "Green reflectance", "unit": "", "hint": "Sentinel-2 B03 surface reflectance"},
    "reflectance_red": {"label": "Red reflectance", "unit": "", "hint": "Sentinel-2 B04 surface reflectance"},
    "reflectance_nir": {"label": "NIR reflectance", "unit": "", "hint": "Sentinel-2 B08 surface reflectance"},
    "reflectance_swir16": {"label": "SWIR 1.6 µm reflectance", "unit": "", "hint": "Sentinel-2 B11 surface reflectance"},
    "reflectance_swir22": {"label": "SWIR 2.2 µm reflectance", "unit": "", "hint": "Sentinel-2 B12 surface reflectance"},
    "scene_class": {
        "label": "Scene class",
        "unit": "",
        "hint": "Sentinel-2 SCL at the pixel: 4 vegetation, 5 bare soil, 6 water, 7 unclassified, 11 snow",
    },
    "scene_cloud_pct": {"label": "Scene cloud cover", "unit": "%", "hint": "Cloud cover of the whole Sentinel-2 tile"},
    "observation_unix": {"label": "Observed", "unit": "", "hint": "When the satellite took the image"},
    "observation_age_days": {"label": "Image age", "unit": "days", "hint": "Days since the satellite took the image"},
    "brightness_k": {
        "label": "Brightness",
        "unit": "K",
        "hint": "FIRMS fire pixel brightness temperature",
    },
    "confidence": {
        "label": "Confidence",
        "unit": "%",
        "hint": "Detection confidence",
    },
    "cpm": {
        "label": "Radiation",
        "unit": "cpm",
        "hint": "Safecast counts per minute",
    },
    "severity_score": {
        "label": "Severity",
        "unit": "",
        "hint": "Event severity score",
    },
    "radius_km": {
        "label": "Radius",
        "unit": "km",
        "hint": "Affected radius",
    },
    "degradation_score": {
        "label": "Degradation",
        "unit": "/100",
        "hint": "Derived delivery-path degradation; cause is not established",
    },
    "availability_pct": {
        "label": "Availability",
        "unit": "%",
        "hint": "Availability published by the source network",
    },
    "latency_s": {
        "label": "Delivery latency",
        "unit": "s",
        "hint": "Observation delivery latency, not RF power",
    },
    "altitude_m": {
        "label": "Altitude",
        "unit": "m",
        "hint": "Aircraft altitude",
    },
    "speed_mps": {
        "label": "Speed",
        "unit": "m/s",
        "hint": "Ground speed",
    },
    "sog_knots": {
        "label": "SOG",
        "unit": "kn",
        "hint": "AIS speed over ground",
    },
    "cog_deg": {
        "label": "COG",
        "unit": "°",
        "hint": "AIS course over ground",
    },
    "intensity_kn": {
        "label": "Intensity",
        "unit": "kn",
        "hint": "NHC maximum sustained wind",
    },
    "kp_index": {
        "label": "Planetary Kp",
        "unit": "Kp",
        "hint": "NOAA SWPC planetary K-index",
    },
    "aurora_pct": {
        "label": "Aurora",
        "unit": "%",
        "hint": "OVATION aurora probability",
    },
    "energy_j": {
        "label": "Flash energy",
        "unit": "J",
        "hint": "GOES GLM lightning flash energy",
    },
    "energy_fj": {
        "label": "Flash energy",
        "unit": "fJ",
        "hint": "GOES GLM lightning flash energy (femtojoules)",
    },
    "field_nt": {
        "label": "Magnetic field",
        "unit": "nT",
        "hint": "USGS observatory total field F",
    },
    "observation_age_s": {
        "label": "Observation age",
        "unit": "s",
        "hint": "Age of the latest non-null USGS sample at relay time",
    },
    "salinity_psu": {
        "label": "Salinity",
        "unit": "PSU",
        "hint": "Argo practical salinity",
    },
    "pressure_dbar": {
        "label": "Pressure",
        "unit": "dbar",
        "hint": "Argo hydrostatic pressure",
    },
    "demand_mw": {
        "label": "Demand",
        "unit": "MW",
        "hint": "EIA electricity demand",
    },
    "pool_elev_m": {
        "label": "Pool elevation",
        "unit": "m",
        "hint": "USACE reservoir pool elevation converted from feet",
    },
    "storage_m3": {
        "label": "Storage",
        "unit": "m³",
        "hint": "USACE reservoir storage converted from acre-feet",
    },
    "uv_index": {
        "label": "UV index",
        "unit": "",
        "hint": "EPA hourly UV forecast; not an in-situ measurement",
    },
    "rainfall_mm": {
        "label": "Rainfall",
        "unit": "mm",
        "hint": "Met Éireann reported rainfall",
    },
}

LAYER_BLURB: dict[str, str] = {
    "bridge_clearance": "Preliminary NOAA PORTS clearance measured at the designated reference point on each bridge.",
    "ocean_drifters": "Observed drifter position and sea-surface temperature from NOAA AOML OSMC (CC0 1.0).",
    "power_outages": "UK Power Networks incidents (CC BY 4.0). Map points represent approximate areas reported by the operator.",
    "bikeshare": "Bike Share Toronto station status (Open Government Licence – Toronto).",
    "weather": "Weather observation — Open-Meteo, NWS, SMHI MetObs, Frost, DMI, FMI, Singapore NEA, HKO, AEMET, MeteoSwiss, CWA, Météo-France, Estonia EWS, Iceland IMO, and other LIVE public feeds (or physics simulator).",
    "air": "Air-quality sample (particulates and gases) — LIVE public feed or simulator.",
    "tide": "Coastal water level from NOAA, UHSLC, the UK Environment Agency, or GeoNet.",
    "ocean_obs": "SMHI in-situ ocean observations at the displayed sensor depth (CC BY 4.0).",
    "smoke_forecast": "Environment and Climate Change Canada RAQDPS model, next UTC hour at the displayed 10 km model cell.",
    "hf_absorption": "NOAA SWPC D-RAP modeled frequency threshold for 1 dB of absorption on a 2° × 4° source grid.",
    "river_forecast": "NOAA/NWS river stage forecast on the local gage datum.",
    "river": "River discharge and stage — USGS, ECCC, SMHI hydro, PEGELONLINE, EA, RWS, SEPA, NRW, Hub'Eau, eHYD, BAFU/FOEN (geodetic water level, not USGS stage).",
    "marine": "Wave height and sea-surface temperature — NDBC buoy or Open-Meteo Marine.",
    "ev_charging": "NDW DOT-NL charging connector availability (CC0 1.0).",
    "wildfire_perimeters": "BC Wildfire Service incident status and reported outlines.",
    "pollen": "MeteoSwiss automatic station measurements of airborne pollen (CC BY 4.0).",
    "storm_reports": "NOAA SPC preliminary local reports of tornadoes, hail and wind.",
    "volcanic_ash": "NOAA Washington VAAC volcanic ash advisory geometry. Consult the official briefing for flight decisions.",
    "fire_hotspots": "Geoscience Australia satellite thermal detections (CC BY 4.0).",
    "grid": "National electricity carbon intensity for the UK grid.",
    "quake": "Latest significant earthquake — USGS, EMSC, GeoNet, and/or GeoShake.",
    "energy": "Household energy meter — physics simulator (no upstream public API).",
    "fire": "NASA FIRMS VIIRS active-fire hotspot (open data — cite NASA FIRMS).",
    "radiation": "Safecast citizen radiation measurement (CC0).",
    "jamming": "CyberNews GNSS interference event (CC BY 4.0).",
    "gnss": (
        "Public EUREF/Geoscience Australia GNSS station evidence. EPN delivery-path "
        "degradation is derived; inventory-only stations remain unknown. Neither "
        "independently proves RF jamming."
    ),
    "traffic": "Own-edge ADS-B / AIS feeder (operator receiver — not a third-party aggregator).",
    "events": "NASA EONET open natural events (cite NASA EONET; no NASA endorsement).",
    "spacewx": "NOAA SWPC Kp/aurora, solar wind, GOES X-ray, and/or NASA DONKI (U.S. PD / NASA open).",
    "lightning": "GOES-19/18 GLM lightning flashes via NOAA Open Data Dissemination (U.S. PD).",
    "alerts": "NWS CAP and/or Canada NAAD public alerts (empty ≠ all-clear).",
    "argo": "Official GDAC active float; click refreshes that WMO's latest T/S/P profile.",
    "geomag": "USGS geomagnetic observatory F (nT) — not INTERMAGNET.",
    "iot": "Own-edge IoT feeder (Tasmota / TTN / SenML) — not a third-party aggregator.",
    "flood": "NWS CAP US flood/flash-flood and/or UK EA OGL England warnings — not GloFAS, not an in-situ gauge.",
    "effis": "Copernicus EFFIS current fires (CC BY 4.0 — cite Copernicus EMS / JRC).",
    "volcano": "USGS elevated volcanoes (alert / aviation color, U.S. PD).",
    "ais": "Public AIS snapshot — Fintraffic (Finnish waters, CC BY 4.0) or Kystverket (Norwegian waters, NLOD). Not own-edge AIS.",
    "tsunami": "Tsunami warning product (NWS CAP and/or PTWC Atom). Not a tide gauge. Empty ≠ all-clear.",
    "cyclone": "NOAA NHC/CPHC active tropical cyclones (U.S. PD). Atlantic + East/Central Pacific — not JTWC, not EONET.",
    "adsb": "Public ADS-B via ADSB.lol (ODbL 1.0). Not own-edge dump1090, not OpenSky/ADSBx.",
    "aviation": "Airport METAR from NOAA Aviation Weather Center (U.S. PD). In-situ instruments — not a TAF.",
    "road": "Fintraffic Digitraffic road-weather stations (CC BY 4.0 — Finnish roads only).",
    "rail": "Published train positions from Fintraffic in Finland or Entur in Norway.",
    "drought": "U.S. Drought Monitor weekly state statistics (attribute NDMC / USDA / NOAA / NASA).",
    "smoke": "NOAA/NESDIS HMS qualitative smoke polygons (U.S. public domain). Polygon centroids, not PM2.5 sensors.",
    "water_quality": "USGS automated continuous water quality (U.S. public domain; values may be provisional).",
    "groundwater": "Pilot well observations from USGS or Hub'Eau with source-specific reference levels.",
    "dart": "NOAA/NDBC DART deep-ocean water-column height (U.S. public domain). Gauge, not a warning.",
    "precipitation": "NASA GPM IMERG Early Run V07 half-hour grid cells (NASA open data; preliminary).",
    "radar": "NOAA/NWS NEXRAD WSR-88D operational health per radar coordinate; not reflectivity pixels.",
    "atmosphere": "CAMS-derived aerosol, dust and pollen at any requested coordinate (CC BY 4.0 attribution).",
    "radnet": "U.S. EPA RadNet approved hourly gamma monitoring across all 140 official monitor coordinates; total CPM is derived from channels R02–R09.",
    "soil": "Copernicus CLMS global daily Soil Water Index SWI020 at any requested coordinate.",
    "solar": "NASA POWER daily surface solar irradiation at any requested coordinate.",
    "snow": "NOAA/NWS NOHRSC assimilated SNODAS snow depth and SWE at any requested CONUS coordinate.",
    "sea_ice": "NOAA/NSIDC Sea Ice Index v4 daily 25-km concentration cells; not for navigation.",
    "land_temperature": "Copernicus Sentinel-3 SLSTR Level-2 land-surface temperature at any requested coordinate.",
    "reservoir": "USACE CWMS reservoir pool elevation and storage (U.S. public domain).",
    "uv": "EPA Envirofacts hourly UV forecast by U.S. city ZIP; not an in-situ pyranometer.",
}

_LAYER_FIELD_HINTS: dict[tuple[str, str], str] = {
    ("fire_hotspots", "brightness_k"): "Brightness temperature reported by Digital Earth Australia Hotspots",
    ("volcanic_ash", "base_ft"): "Base of the ash cloud in the VAAC bulletin",
    ("volcanic_ash", "top_ft"): "Top of the ash cloud in the VAAC bulletin",
    ("bridge_clearance", "observation_unix"): "Time of the NOAA clearance measurement",
    ("ocean_drifters", "observation_unix"): "Time of the drifter observation",
    ("bikeshare", "observation_unix"): "When the station last reported its availability",
    ("ev_charging", "observation_unix"): "When the operator last changed the site data",
    ("pollen", "observation_unix"): "Time of the hourly pollen sample",
    ("storm_reports", "observation_unix"): "Time of the reported severe weather",
    ("groundwater", "observation_unix"): "When the well measurement was taken",
    ("tide", "observation_unix"): "When the coastal water level was measured",
    ("marine", "observation_unix"): "Start of the wave sampling interval",
    ("snow", "observation_unix"): "Time of the paired SNOTEL snow measurements",
    ("river", "observation_unix"): "When the river gauge observation was made",
    ("radiation", "observation_unix"): "End of the BfS hourly measurement interval",
    ("ocean_obs", "observation_unix"): "Timestamp shared by the measurements at this depth",
    ("rail", "observation_unix"): "When the operator recorded the train position",
    ("hf_absorption", "forecast_valid_unix"): "UTC validity of the D-RAP model snapshot",
    ("smoke_forecast", "forecast_valid_unix"): "Target UTC hour of the ECCC forecast",
    ("jamming", "severity_score"): "GNSS interference severity score",
    ("effis", "severity_score"): "EFFIS burnt-area score from polygon size",
    ("flood", "severity_score"): "Flood / flash-flood warning severity",
    ("volcano", "severity_score"): "USGS volcano alert score",
    ("events", "severity_score"): "NASA EONET event score",
    ("alerts", "severity_score"): "NWS CAP alert severity",
    ("tsunami", "severity_score"): "Tsunami warning-product severity",
    ("smoke", "severity_score"): "HMS qualitative density score (light/medium/heavy)",
}


def _fmt_num(value: Any, *, digits: int = 1) -> str | None:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if digits == 0:
        return f"{n:.0f}"
    text = f"{n:.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


_INDEX_FIELDS = frozenset({"ndvi", "ndwi", "nbr", "ndmi"})


def _fmt_unix(value: Any) -> str | None:
    """``2026-10-16 07:00 UTC`` for an epoch-seconds field, not a ten-digit number."""
    try:
        return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(float(value)))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _fmt_relay(value: Any) -> str | None:
    try:
        return "on" if float(value) >= 0.5 else "off"
    except (TypeError, ValueError):
        return None


def headline(layer: str, values: dict[str, Any]) -> str:
    if not values:
        return "Waiting for reading…"
    try:
        if layer == "weather":
            t = _fmt_num(values.get("temperature_c"), digits=1)
            return f"{t} °C" if t is not None else "Weather"
        if layer == "air":
            pm = _fmt_num(values.get("pm2_5_ugm3"), digits=1)
            if pm is not None:
                return f"PM2.5 {pm} µg/m³"
            daqi = _fmt_num(values.get("air_quality_index"), digits=0)
            return f"UK DAQI {daqi}/10" if daqi is not None else "Air quality"
        if layer == "tide":
            nn2000 = _fmt_num(values.get("water_level_nn2000_m"), digits=3)
            if nn2000 is not None:
                return f"Water {nn2000} m NN2000"
            sensor = _fmt_num(values.get("coastal_water_height_m"), digits=3)
            if sensor is not None:
                return f"Water {sensor} m above sensor"
            maod = _fmt_num(values.get("water_level_maod"), digits=3)
            if maod is not None:
                return f"Water {maod} mAOD"
            wl = _fmt_num(values.get("water_level_m"), digits=3)
            return f"Water {wl} m" if wl is not None else "Tide"
        if layer == "river_forecast":
            peak = _fmt_num(values.get("forecast_stage_m"), digits=2)
            return f"Forecast peak {peak} m" if peak is not None else "River forecast"
        if layer == "bridge_clearance":
            gap = _fmt_num(values.get("air_gap_m"), digits=2)
            return f"Clearance {gap} m" if gap is not None else "Bridge clearance"
        if layer == "ocean_drifters":
            sst = _fmt_num(values.get("sst_c"), digits=1)
            return f"Sea surface {sst} °C" if sst is not None else "Ocean drifter"
        if layer == "power_outages":
            if values.get("power_outage_count") == 0:
                return "No current outages reported"
            customers = _fmt_num(values.get("customers_affected"), digits=0)
            return f"{customers} customers affected" if customers is not None else "Reported power outage"
        if layer == "bikeshare":
            bikes, docks = (_fmt_num(values.get(key), digits=0) for key in ("bikes_available", "docks_available"))
            return f"{bikes} bikes · {docks} docks" if bikes is not None and docks is not None else "Bike share"
        if layer == "ev_charging":
            available, total = (_fmt_num(values.get(key), digits=0) for key in ("available_count", "connector_count"))
            return f"{available}/{total} connectors available" if available is not None and total is not None else "EV charging"
        if layer == "pollen":
            samples = [float(value) for key, value in values.items() if key.endswith("_pollen_grains_m3")]
            return f"Pollen up to {_fmt_num(max(samples), digits=1)} grains/m³" if samples else "Measured pollen"
        if layer == "wildfire_perimeters":
            area = _fmt_num(values.get("area_ha"), digits=3)
            return f"Reported area {area} ha" if area is not None else "Wildfire incident"
        if layer == "fire_hotspots":
            brightness = _fmt_num(values.get("brightness_k"), digits=1)
            return f"Brightness {brightness} K" if brightness is not None else "Satellite thermal detection"
        if layer == "river":
            q = _fmt_num(values.get("discharge_m3s"), digits=1)
            return f"Q {q} m³/s" if q is not None else "River"
        if layer == "reservoir":
            elev = _fmt_num(values.get("pool_elev_m"), digits=2)
            return f"Pool {elev} m" if elev is not None else "Reservoir"
        if layer == "uv":
            uv = _fmt_num(values.get("uv_index"), digits=1)
            return f"UV {uv}" if uv is not None else "UV forecast"
        if layer == "marine":
            wh = _fmt_num(values.get("wave_height_m"), digits=2)
            return f"Waves {wh} m" if wh is not None else "Marine"
        if layer == "ocean_obs":
            sal = _fmt_num(values.get("salinity_psu"), digits=2)
            current = _fmt_num(values.get("current_speed_mps"), digits=2)
            if sal is not None:
                return f"Salinity {sal} PSU"
            return f"Current {current} m/s" if current is not None else "Ocean observations"
        if layer == "smoke_forecast":
            pm = _fmt_num(values.get("forecast_smoke_pm2_5_ugm3"), digits=1)
            return f"Forecast PM2.5 {pm} µg/m³" if pm is not None else "Smoke forecast"
        if layer == "hf_absorption":
            freq = _fmt_num(values.get("drap_frequency_mhz"), digits=1)
            return f"1 dB threshold {freq} MHz" if freq is not None else "D-RAP model"
        if layer == "grid":
            ci = _fmt_num(values.get("carbon_intensity_gco2_kwh"), digits=0)
            return f"{ci} gCO₂/kWh" if ci is not None else "Grid"
        if layer == "quake":
            mag = _fmt_num(values.get("magnitude"), digits=1)
            return f"Magnitude {mag}" if mag is not None else "Earthquake"
        if layer == "energy":
            pw = _fmt_num(values.get("power_w"), digits=0)
            return f"{pw} W" if pw is not None else "Energy"
        if layer == "fire":
            b = _fmt_num(values.get("brightness_k"), digits=0)
            return f"Fire {b} K" if b is not None else "Wildfire"
        if layer == "radiation":
            dose = _fmt_num(values.get("dose_equivalent_nsv_h"), digits=1)
            if dose is not None:
                return f"{dose} nSv/h"
            c = _fmt_num(values.get("cpm"), digits=1)
            return f"{c} cpm" if c is not None else "Radiation"
        if layer == "rail" and "observation_unix" in values:
            return "Reported train position"
        if layer == "jamming":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"GNSS sev {s}" if s is not None else "Jamming"
        if layer == "gnss":
            score = _fmt_num(values.get("degradation_score"), digits=0)
            availability = _fmt_num(values.get("availability_pct"), digits=1)
            if score is not None:
                return f"GNSS degradation {score}/100"
            if availability is not None:
                return f"GNSS availability {availability}%"
            return "GNSS station · integrity unknown"
        if layer == "traffic":
            if "altitude_m" in values:
                a = _fmt_num(values.get("altitude_m"), digits=0)
                return f"ADS-B {a} m" if a is not None else "ADS-B"
            sog = _fmt_num(values.get("sog_knots"), digits=1)
            return f"AIS {sog} kn" if sog is not None else "AIS"
        if layer == "events":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"EONET {s}" if s is not None else "Natural event"
        if layer == "spacewx":
            k = _fmt_num(values.get("kp_index"), digits=1)
            return f"Kp {k}" if k is not None else "Space weather"
        if layer == "lightning":
            e = _fmt_num(values.get("energy_fj"), digits=0)
            return f"GLM {e} fJ" if e is not None else "GLM flash"
        if layer == "alerts":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"Alert {s}" if s is not None else "NWS alert"
        if layer == "argo":
            t = _fmt_num(values.get("temperature_c"), digits=1)
            return f"Argo {t} °C" if t is not None else "Argo"
        if layer == "geomag":
            f = _fmt_num(values.get("field_nt"), digits=0)
            return f"{f} nT" if f is not None else "Geomag"
        if layer == "iot":
            t = _fmt_num(values.get("temperature_c"), digits=1)
            return f"IoT {t} °C" if t is not None else "IoT"
        if layer == "flood":
            exceedance = _fmt_num(values.get("flood_exceedance_m"), digits=2)
            if exceedance is not None:
                return f"Provisional · {exceedance} m above threshold"
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"Flood {s}" if s is not None else "Flood"
        if layer == "effis":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"EFFIS {s}" if s is not None else "EFFIS"
        if layer == "volcano":
            level = _fmt_num(values.get("volcanic_alert_level"), digits=0)
            if level is not None:
                return f"Volcanic alert level {level}"
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"Volcano {s}" if s is not None else "Volcano"
        if layer == "ais":
            sog = _fmt_num(values.get("sog_knots"), digits=1)
            return f"AIS {sog} kn" if sog is not None else "Public AIS"
        if layer == "tsunami":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"Tsunami {s}" if s is not None else "Tsunami alert"
        if layer == "cyclone":
            kn = _fmt_num(values.get("intensity_kn"), digits=0)
            return f"Cyclone {kn} kn" if kn is not None else "Tropical cyclone"
        if layer == "adsb":
            a = _fmt_num(values.get("altitude_m"), digits=0)
            return f"ADS-B {a} m" if a is not None else "Public ADS-B"
        if layer == "smoke":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"Smoke {s}" if s is not None else "Smoke polygon"
        if layer == "water_quality":
            ph = _fmt_num(values.get("ph"), digits=1)
            return f"Water pH {ph}" if ph is not None else "Water quality"
        if layer == "groundwater":
            depth = _fmt_num(values.get("groundwater_depth_m"), digits=2)
            reference_depth = _fmt_num(values.get("groundwater_reference_depth_m"), digits=2)
            if reference_depth is not None:
                return f"Depth from measuring reference {reference_depth} m"
            return f"Depth to water {depth} m" if depth is not None else "Groundwater well"
        if layer == "dart":
            h = _fmt_num(values.get("water_column_height_m"), digits=3)
            return f"DART {h} m" if h is not None else "DART gauge"
        if layer == "precipitation":
            p = _fmt_num(values.get("precipitation_mm_h"), digits=1)
            return f"IMERG {p} mm/h" if p is not None else "IMERG precipitation"
        if layer == "radar":
            latency = _fmt_num(values.get("radar_latency_s"), digits=1)
            return f"NEXRAD {latency} s" if latency is not None else "NEXRAD status"
        if layer == "atmosphere":
            dust = _fmt_num(values.get("dust_ugm3"), digits=1)
            return f"CAMS dust {dust} µg/m³" if dust is not None else "CAMS atmosphere"
        if layer == "radnet":
            dose = _fmt_num(values.get("dose_equivalent_nsv_h"), digits=1)
            return f"RadNet {dose} nSv/h" if dose is not None else "EPA RadNet"
        if layer == "soil":
            swi = _fmt_num(values.get("soil_water_index_pct"), digits=1)
            return f"Soil SWI {swi}%" if swi is not None else "Soil moisture"
        if layer == "solar":
            solar = _fmt_num(values.get("solar_irradiation_kwh_m2_day"), digits=2)
            return f"Solar {solar} kWh/m²/day" if solar is not None else "Solar irradiation"
        if layer == "snow":
            depth = _fmt_num(values.get("snow_depth_cm"), digits=1)
            return f"Snow depth {depth} cm" if depth is not None else "NOHRSC snowpack"
        if layer == "sea_ice":
            ice = _fmt_num(values.get("sea_ice_concentration_pct"), digits=1)
            return f"Sea ice {ice}%" if ice is not None else "Sea ice concentration"
        if layer == "power_price":
            price = _fmt_num(values.get("price_eur_mwh"), digits=2)
            return f"{price} €/MWh" if price is not None else "Day-ahead price"
        if layer == "imagery":
            ndvi = _fmt_num(values.get("ndvi"), digits=2)
            return f"NDVI {ndvi}" if ndvi is not None else "Sentinel-2"
        if layer == "actuator":
            relay = _fmt_relay(values.get("relay_on"))
            pw = _fmt_num(values.get("power_w"), digits=0)
            if relay is None:
                return "Actuator"
            return f"Relay {relay} · {pw} W" if pw is not None else f"Relay {relay}"
        if layer == "land_temperature":
            temp = _fmt_num(values.get("land_surface_temperature_c"), digits=1)
            return f"Land surface {temp} °C" if temp is not None else "Land temperature"
    except (TypeError, ValueError):
        pass
    return "Reading"


def metric_rows(values: dict[str, Any], *, layer: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, raw in values.items():
        meta = FIELD_META.get(key, {"label": key.replace("_", " "), "unit": "", "hint": ""})
        digits = 3 if key in {"water_level_m", "water_level_maod", "coastal_water_height_m", "gage_height_m", "latitude", "longitude"} else (
            2 if key in {"wave_height_m", "discharge_m3s", "pool_elev_m", "groundwater_depth_m",
                         "groundwater_reference_depth_m", "groundwater_level_ngf_m",
                         "forecast_stage_m", "current_speed_mps", "salinity_psu"} else (
                0 if key.endswith("_kwh") else 1
            )
        )
        if key in {"magnitude", "depth_km"}:
            digits = 1 if key == "magnitude" else 1
        if key.startswith("reflectance_"):
            digits = 4  # surface reflectance is mostly 0.01–0.4
        elif key in _INDEX_FIELDS:
            digits = 3
        elif key.startswith("price_"):
            digits = 2
        elif key in {"scene_class", "negative_intervals_24h", "resolution_min"}:
            digits = 0
        if key.endswith("_unix"):
            formatted = _fmt_unix(raw)
        elif key == "relay_on":
            formatted = _fmt_relay(raw)
        else:
            formatted = _fmt_num(raw, digits=digits)
        if formatted is None:
            formatted = str(raw)
        unit = meta.get("unit") or ""
        display = f"{formatted} {unit}".strip()
        hint = _LAYER_FIELD_HINTS.get((layer, key)) or meta.get("hint") or ""
        label = meta["label"]
        if key == "forecast_valid_unix" and layer in {"hf_absorption", "smoke_forecast"}:
            label = "Model valid at" if layer == "hf_absorption" else "Forecast valid at"
        rows.append(
            {
                "key": key,
                "label": label,
                "value": display,
                "raw": formatted,
                "unit": unit,
                "hint": hint,
            }
        )
    return rows


def coord_place(station: dict[str, Any]) -> str | None:
    """``84.0°S 38.0°E`` from a pin's own coordinates.

    Densified event pins (an OVATION aurora cell, a FIRMS hotspot, a GLM flash)
    have no place NAME — there is nothing to name, they are grid cells and
    detections over ocean and ice. They used to render as "Unknown location"
    directly above a panel listing their exact latitude and longitude, which reads
    as a data failure on a map whose whole job is to say where something is.
    """
    lat = station.get("lat")
    lon = station.get("lon")
    values = station.get("values") if isinstance(station.get("values"), dict) else {}
    if lat is None:
        lat = values.get("latitude")
    if lon is None:
        lon = values.get("longitude")
    try:
        lat_f = float(lat)  # type: ignore[arg-type]
        lon_f = float(lon)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None
    return (
        f"{abs(lat_f):.1f}\u00b0{'S' if lat_f < 0 else 'N'} "
        f"{abs(lon_f):.1f}\u00b0{'W' if lon_f < 0 else 'E'}"
    )


def build_detail(
    station: dict[str, Any],
    *,
    cached: bool,
    age_ms: int,
) -> dict[str, Any]:
    current = without_expired_source_reading(station, now=time.time())
    expired = current is not station
    station = current
    values = station.get("values") if isinstance(station.get("values"), dict) else {}
    layer = str(station.get("layer") or "")
    metrics = metric_rows(values, layer=layer)
    named = station.get("place") or station.get("site")
    place = named or coord_place(station) or "Unknown location"
    # "in Boulder" reads right; "in 84.0°S 38.0°E" does not.
    located = f"in {place}" if named else (f"at {place}" if place != "Unknown location" else "at an unreported position")
    title = station.get("label") or station.get("id")
    hl = station.get("headline") or headline(layer, values)
    blurb = LAYER_BLURB.get(layer, "")
    device_id = str(station.get("id") or "")
    if device_id.startswith("fmi-marine-"):
        blurb = "Finnish Meteorological Institute in-situ wave buoy (CC BY 4.0)"
    elif device_id.startswith("snotel-"):
        blurb = "USDA NRCS SNOTEL in-situ snow depth and snow-water equivalent (U.S. public domain)"
    elif device_id.startswith("ie-buoy-"):
        blurb = "Irish Marine Institute / Met Éireann buoy observations (CC BY 4.0)."
    elif device_id.startswith("au-wave-"):
        blurb = "AODN / IMOS observed waves from an Australian wave buoy (CC BY 4.0)."
    elif device_id.startswith("geonet-volcano-status-"):
        blurb = "GeoNet New Zealand volcano status and time-stamped camera snapshots (CC BY 3.0 NZ)."
    elif device_id.startswith("geonet-coastal-"):
        blurb = "GeoNet coastal water height relative to the local pressure sensor (CC BY 3.0 NZ)."
    elif device_id.startswith("chmi-river-"):
        blurb = "Czech Hydrometeorological Institute observed river stage and discharge (CC BY 4.0)."
    elif device_id.startswith("arso-river-"):
        blurb = "Slovenian Environment Agency (ARSO) preliminary river observations. Stage refers to the local gauge datum."
    elif device_id.startswith("kartverket-tide-"):
        blurb = "Kartverket observed sea level relative to Norway’s NN2000 vertical datum (CC BY 4.0)."
    elif device_id.startswith("bfs-odl-"):
        blurb = "BfS ambient gamma dose equivalent rate, measured hourly (dl-de/by-2-0)."
    elif device_id.startswith("entur-tr-"):
        blurb = "Entur's latest reported Vy position (NLOD)."
    elif station.get("drap_resolution") == "overview":
        blurb = "NOAA SWPC D-RAP overview: maximum modeled 1 dB threshold within the 6° × 12° tile. Zoom in for source values."
    elif device_id.startswith("drap-cell-"):
        blurb = "NOAA SWPC D-RAP modeled 1 dB threshold for this native 2° × 4° grid cell."
    boundary = {}
    if layer == "volcano" and station.get("aviation_color_code"):
        boundary["evidence_boundary"] = f"Aviation color {station['aviation_color_code']}."
    if layer == "wildfire_perimeters" and station.get("status"):
        status = str(station["status"])
        outline = station.get("perimeter_observed_at")
        boundary["evidence_boundary"] = f"Status {status}." + (f" Perimeter observed {outline}." if outline else "")
    if layer == "volcanic_ash" and station.get("issue_at"):
        boundary["evidence_boundary"] = (
            f"Advisory issued {station['issue_at']}. Valid time {station.get('valid_at', '')}."
        )
    if station.get("claim_class") == "surveyed_flood_threshold_exceedance":
        blurb = "USGS surveyed flood impact threshold"
        boundary["evidence_boundary"] = (
            f"USGS gage {station.get('gage_id', '')} observed at {station.get('observed_at', '')}. "
            "The threshold exceedance indicates possible local inundation. "
            "Road closure and on-site flooding require separate confirmation."
        )
    if station.get("claim_class") == "published_road_notice":
        start = station.get("valid_from", "")
        end = station.get("valid_until") or "open-ended"
        parent_id = station.get("parent_id")
        if parent_id == TORONTO_ROADS_ID:
            provider = "City of Toronto"
        else:
            provider = "NDW" if parent_id in NDW_NOTICE_IDS else "Fintraffic"
        blurb = f"{provider} notice within its published dates"
        boundary["evidence_boundary"] = (
            f"Updated {station.get('issue_at', '')}. Published validity {start} to {end}. "
            f"Check {provider} for current restrictions and work schedules."
        )
    if layer == "power_outages" and station.get("outage_type"):
        details = [str(station["outage_type"])]
        if station.get("incident_status"):
            details.append(str(station["incident_status"]))
        if station.get("operating_zone"):
            details.append(str(station["operating_zone"]))
        if station.get("estimated_restoration_at"):
            details.append(f"Estimated restoration {station['estimated_restoration_at']}")
        elif station.get("estimated_restoration_local"):
            details.append(f"Estimated restoration {station['estimated_restoration_local']} (operator local time)")
        boundary["evidence_boundary"] = " · ".join(details)
    if station.get("claim_class") == "aviation_forecast_snapshot":
        blurb = "NOAA/NWS aviation forecast snapshot"
        boundary["evidence_boundary"] = (
            f"Issued {station.get('issue_at', '')}. Forecast valid at {station.get('valid_at', '')}. "
            "Obtain an official aviation weather briefing for flight decisions."
        )

    bits: list[str] = []
    mode = str(station.get("mode") or ("live" if station.get("live") else "sim"))
    if mode == "live" and station.get("live"):
        bits.append("LIVE public-API relay")
    elif mode == "live":
        bits.append("LIVE relay (awaiting provenance)")
    else:
        bits.append("SIM physics simulator")
    if station.get("online"):
        bits.append("online now")
    else:
        bits.append("currently offline")
    if cached and age_ms >= 0 and not expired:
        if age_ms < 2000:
            bits.append("fresh reading")
        else:
            bits.append(f"cached · {max(1, age_ms // 1000)}s ago")

    summary = (
        f"{title} {located}. {(blurb or 'Sensor reading').rstrip('.')}. "
        f"Latest: {hl}."
    )
    if metrics:
        top = ", ".join(f"{m['label']} {m['value']}" for m in metrics[:3])
        summary += f" Key metrics: {top}."
    if station.get("notice_text"):
        summary += f" {station['notice_text']}"

    return {
        **station,
        "title": title,
        "subtitle": f"{(blurb or layer).rstrip('.')} · {place}",
        "summary": summary,
        "metrics": metrics,
        "cached": cached,
        "age_ms": age_ms,
        "status_line": " · ".join(bits),
        "blurb": blurb,
        **boundary,
    }
