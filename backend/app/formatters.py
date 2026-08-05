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
    "water_level_m": {
        "label": "Water level",
        "unit": "m",
        "hint": "Tide gauge height (MLLW, metric)",
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
}

LAYER_BLURB: dict[str, str] = {
    "weather": "Live weather observation from a public meteorological feed.",
    "air": "Air-quality sample (particulates and gases) from a public sensor feed.",
    "tide": "Coastal water level from a NOAA tide gauge.",
    "grid": "National electricity carbon intensity for the UK grid.",
    "quake": "Latest significant earthquake reported by USGS.",
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
            return f"PM2.5 {pm} µg/m³" if pm is not None else "Air quality"
        if layer == "tide":
            wl = _fmt_num(values.get("water_level_m"), digits=3)
            return f"Water {wl} m" if wl is not None else "Tide"
        if layer == "grid":
            ci = _fmt_num(values.get("carbon_intensity_gco2_kwh"), digits=0)
            return f"{ci} gCO₂/kWh" if ci is not None else "Grid"
        if layer == "quake":
            mag = _fmt_num(values.get("magnitude"), digits=1)
            return f"Magnitude {mag}" if mag is not None else "Earthquake"
    except (TypeError, ValueError):
        pass
    return "Live"


def metric_rows(values: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, raw in values.items():
        meta = FIELD_META.get(key, {"label": key.replace("_", " "), "unit": "", "hint": ""})
        digits = 3 if key in {"water_level_m", "latitude", "longitude"} else (0 if key.endswith("_kwh") else 1)
        if key in {"magnitude", "depth_km"}:
            digits = 1 if key == "magnitude" else 1
        formatted = _fmt_num(raw, digits=digits)
        if formatted is None:
            formatted = str(raw)
        unit = meta.get("unit") or ""
        display = f"{formatted} {unit}".strip()
        rows.append(
            {
                "key": key,
                "label": meta["label"],
                "value": display,
                "raw": formatted,
                "unit": unit,
                "hint": meta.get("hint") or "",
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
    metrics = metric_rows(values)
    place = station.get("place") or station.get("site") or "Unknown location"
    title = station.get("label") or station.get("id")
    hl = station.get("headline") or headline(layer, values)

    bits: list[str] = []
    if station.get("live"):
        bits.append("Live public-API relay")
    else:
        bits.append("Simulated or offline feed")
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
