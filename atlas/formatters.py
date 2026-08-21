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
}

LAYER_BLURB: dict[str, str] = {
    "weather": "Weather observation — LIVE public feed or physics simulator.",
    "air": "Air-quality sample (particulates and gases) — LIVE public feed or simulator.",
    "tide": "Coastal water level from a NOAA tide gauge.",
    "river": "River discharge and stage from USGS NWIS.",
    "marine": "Wave height and sea-surface temperature — NDBC buoy or Open-Meteo Marine.",
    "grid": "National electricity carbon intensity for the UK grid.",
    "quake": "Latest significant earthquake reported by USGS.",
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
    "spacewx": "NOAA SWPC planetary Kp and OVATION aurora (U.S. public domain).",
    "lightning": "GOES-19/18 GLM lightning flashes via NOAA Open Data Dissemination (U.S. PD).",
    "alerts": "NWS CAP active alerts (free for any purpose).",
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
}

_LAYER_FIELD_HINTS: dict[tuple[str, str], str] = {
    ("jamming", "severity_score"): "GNSS interference severity score",
    ("effis", "severity_score"): "EFFIS burnt-area score from polygon size",
    ("flood", "severity_score"): "Flood / flash-flood warning severity",
    ("volcano", "severity_score"): "USGS volcano alert score",
    ("events", "severity_score"): "NASA EONET event score",
    ("alerts", "severity_score"): "NWS CAP alert severity",
    ("tsunami", "severity_score"): "Tsunami warning-product severity",
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
    except (TypeError, ValueError):
        pass
    return "Reading"


def metric_rows(values: dict[str, Any], *, layer: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, raw in values.items():
        meta = FIELD_META.get(key, {"label": key.replace("_", " "), "unit": "", "hint": ""})
        digits = 3 if key in {"water_level_m", "gage_height_m", "latitude", "longitude"} else (
            2 if key in {"wave_height_m", "discharge_m3s"} else (
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


def build_detail(
    station: dict[str, Any],
    *,
    cached: bool,
    age_ms: int,
) -> dict[str, Any]:
    values = station.get("values") if isinstance(station.get("values"), dict) else {}
    layer = str(station.get("layer") or "")
    metrics = metric_rows(values, layer=layer)
    place = station.get("place") or station.get("site") or "Unknown location"
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
        f"{title} in {place}. {LAYER_BLURB.get(layer, 'Sensor reading.')} "
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
