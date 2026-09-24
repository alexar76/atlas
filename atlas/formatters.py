"""Human-readable labels and summaries for GAIA sensor readings."""

from __future__ import annotations

from typing import Any

FIELD_META: dict[str, dict[str, str]] = {
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
    "wave_height_m": {
        "label": "Wave height",
        "unit": "m",
        "hint": "Significant wave height",
    },
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
    "weather": "Weather observation — Open-Meteo, NWS, SMHI MetObs, Frost, DMI, FMI, Singapore NEA, HKO, AEMET, MeteoSwiss, CWA, Météo-France, Estonia EWS, Iceland IMO, and other LIVE public feeds (or physics simulator).",
    "air": "Air-quality sample (particulates and gases) — LIVE public feed or simulator.",
    "tide": "Coastal water level from a NOAA tide gauge or UHSLC fast-delivery.",
    "river": "River discharge and stage — USGS, ECCC, SMHI hydro, PEGELONLINE, EA, RWS, SEPA, NRW, Hub'Eau, eHYD, BAFU/FOEN (geodetic water level, not USGS stage).",
    "marine": "Wave height and sea-surface temperature — NDBC buoy or Open-Meteo Marine.",
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
    "rail": "Fintraffic Digitraffic train locations (CC BY 4.0 — Finnish rail only).",
    "drought": "U.S. Drought Monitor weekly state statistics (attribute NDMC / USDA / NOAA / NASA).",
    "smoke": "NOAA/NESDIS HMS qualitative smoke polygons (U.S. public domain). Polygon centroids, not PM2.5 sensors.",
    "water_quality": "USGS automated continuous water quality (U.S. public domain; values may be provisional).",
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
            wl = _fmt_num(values.get("water_level_m"), digits=3)
            return f"Water {wl} m" if wl is not None else "Tide"
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
            c = _fmt_num(values.get("cpm"), digits=1)
            return f"{c} cpm" if c is not None else "Radiation"
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
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"Flood {s}" if s is not None else "Flood"
        if layer == "effis":
            s = _fmt_num(values.get("severity_score"), digits=0)
            return f"EFFIS {s}" if s is not None else "EFFIS"
        if layer == "volcano":
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
        digits = 3 if key in {"water_level_m", "gage_height_m", "latitude", "longitude"} else (
            2 if key in {"wave_height_m", "discharge_m3s", "pool_elev_m"} else (
                0 if key.endswith("_kwh") else 1
            )
        )
        if key in {"magnitude", "depth_km"}:
            digits = 1 if key == "magnitude" else 1
        formatted = _fmt_num(raw, digits=digits)
        if formatted is None:
            formatted = str(raw)
        unit = meta.get("unit") or ""
        display = f"{formatted} {unit}".strip()
        hint = _LAYER_FIELD_HINTS.get((layer, key)) or meta.get("hint") or ""
        rows.append(
            {
                "key": key,
                "label": meta["label"],
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
    values = station.get("values") if isinstance(station.get("values"), dict) else {}
    layer = str(station.get("layer") or "")
    metrics = metric_rows(values, layer=layer)
    named = station.get("place") or station.get("site")
    place = named or coord_place(station) or "Unknown location"
    # "in Boulder" reads right; "in 84.0°S 38.0°E" does not.
    located = f"in {place}" if named else (f"at {place}" if place != "Unknown location" else "at an unreported position")
    title = station.get("label") or station.get("id")
    hl = station.get("headline") or headline(layer, values)

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
    if cached and age_ms >= 0:
        if age_ms < 2000:
            bits.append("fresh reading")
        else:
            bits.append(f"cached · {max(1, age_ms // 1000)}s ago")

    summary = (
        f"{title} {located}. {LAYER_BLURB.get(layer, 'Sensor reading.')} "
        f"Latest: {hl}."
    )
    if metrics:
        top = ", ".join(f"{m['label']} {m['value']}" for m in metrics[:3])
        summary += f" Key metrics: {top}."

    return {
        **station,
        "title": title,
        "subtitle": f"{LAYER_BLURB.get(layer, layer).rstrip('.')} · {place}",
        "summary": summary,
        "metrics": metrics,
        "cached": cached,
        "age_ms": age_ms,
        "status_line": " · ".join(bits),
        "blurb": LAYER_BLURB.get(layer, ""),
    }
