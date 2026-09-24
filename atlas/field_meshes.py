"""Licensed in-situ meshes ATLAS may fuse. Open-Meteo is not a mesh.

A mesh is a named, licence-gated set of GAIA device prefixes that share one
claim class (in-situ observation) and one scalar quantity family. Warning
products, models, and public AIS/ADS-B are not meshes.
"""

from __future__ import annotations

from typing import Any, Mapping

MeshSpec = dict[str, Any]

# Default quantity tried in order when the buyer omits `quantity`.
_WX = ("temperature_c", "humidity_pct", "pressure_hpa", "wind_mps")
_RIVER = ("discharge_m3s", "gage_height_m", "water_level_m")
_AIR = ("pm2_5_ugm3", "aqi", "aqhi", "psi")
_MARINE = ("wave_height_m", "sst_c")

FIELD_MESHES: dict[str, MeshSpec] = {
    "ee-wx": {
        "id": "ee-wx",
        "layer": "weather",
        "prefixes": ("ee-wx-",),
        "quantities": _WX,
        "licence": "CC BY 4.0",
        "attribution": "Estonian Weather Service (ilmateenistus.ee)",
        "geography": "Estonia",
        "claim_class": "in_situ_observation",
        "not": (
            "Not Open-Meteo. Not an official national forecast. Not an "
            "early-warning system — Estonia EWS here is the weather service XML."
        ),
    },
    "smhi-wx": {
        "id": "smhi-wx",
        "layer": "weather",
        "prefixes": ("smhi-wx-",),
        "quantities": _WX,
        "licence": "CC BY 4.0",
        "attribution": "SMHI MetObs",
        "geography": "Sweden",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Not smhi-hydro river gauges.",
    },
    "ch-wx": {
        "id": "ch-wx",
        "layer": "weather",
        "prefixes": ("ch-wx-",),
        "quantities": _WX,
        "licence": "CC BY 4.0",
        "attribution": "MeteoSwiss OGD",
        "geography": "Switzerland",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Not BAFU river gauges.",
    },
    "hko-wx": {
        "id": "hko-wx",
        "layer": "weather",
        "prefixes": ("hko-wx-",),
        "quantities": _WX,
        "licence": "DATA.GOV.HK attribution",
        "attribution": "Hong Kong Observatory via DATA.GOV.HK",
        "geography": "Hong Kong",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Not HK AQHI.",
    },
    "is-wx": {
        "id": "is-wx",
        "layer": "weather",
        "prefixes": ("is-wx-",),
        "quantities": _WX,
        "licence": "ODC-By",
        "attribution": "Icelandic Met Office AWS",
        "geography": "Iceland",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo.",
    },
    "sg-wx": {
        "id": "sg-wx",
        "layer": "weather",
        "prefixes": ("sg-wx-",),
        "quantities": _WX,
        "licence": "Singapore Open Data Licence",
        "attribution": "Singapore NEA via data.gov.sg",
        "geography": "Singapore",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Not regional PSI.",
    },
    "aemet-wx": {
        "id": "aemet-wx",
        "layer": "weather",
        "prefixes": ("aemet-wx-",),
        "quantities": _WX,
        "licence": "AEMET PSI reuse — Fuente: AEMET",
        "attribution": "AEMET OpenData",
        "geography": "Spain",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Offline when GAIA_AEMET_API_KEY is unset.",
    },
    "cwa-wx": {
        "id": "cwa-wx",
        "layer": "weather",
        "prefixes": ("cwa-wx-",),
        "quantities": _WX,
        "licence": "OGDL 1.0",
        "attribution": "Taiwan CWA OpenData",
        "geography": "Taiwan",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Offline when GAIA_CWA_API_KEY is unset.",
    },
    "mf-wx": {
        "id": "mf-wx",
        "layer": "weather",
        "prefixes": ("mf-wx-",),
        "quantities": _WX,
        "licence": "Etalab OL 2.0",
        "attribution": "Météo-France DPObs",
        "geography": "France",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo. Not Hub'Eau rivers. Offline without application id.",
    },
    "frost": {
        "id": "frost",
        "layer": "weather",
        "prefixes": ("frost-",),
        "quantities": _WX,
        "licence": "CC BY 4.0 + NLOD",
        "attribution": "MET Norway Frost",
        "geography": "Norway",
        "claim_class": "in_situ_observation",
        "not": "Not METAR. Not Open-Meteo locationforecast. Needs GAIA_FROST_CLIENT_ID.",
    },
    "dmi": {
        "id": "dmi",
        "layer": "weather",
        "prefixes": ("dmi-",),
        "quantities": _WX,
        "licence": "CC BY 4.0",
        "attribution": "DMI metObs",
        "geography": "Denmark",
        "claim_class": "in_situ_observation",
        "not": "Not Open-Meteo.",
    },
    "pegel": {
        "id": "pegel",
        "layer": "river",
        "prefixes": ("pegel-",),
        "quantities": _RIVER,
        "licence": "DL-DE-Zero",
        "attribution": "WSV PEGELONLINE",
        "geography": "Germany",
        "claim_class": "in_situ_observation",
        "not": "Not a flood warning. Not NL/FR gauges.",
    },
    "hubeau": {
        "id": "hubeau",
        "layer": "river",
        "prefixes": ("hubeau-",),
        "quantities": _RIVER,
        "licence": "Etalab OL 2.0",
        "attribution": "Hub'Eau hydrométrie",
        "geography": "France",
        "claim_class": "in_situ_observation",
        "not": "Not Vigicrues. Not PEGELONLINE.",
    },
    "ehyd": {
        "id": "ehyd",
        "layer": "river",
        "prefixes": ("ehyd-",),
        "quantities": _RIVER,
        "licence": "CC BY 4.0",
        "attribution": "eHYD / BMLUK (Datenquelle: ehyd.gv.at)",
        "geography": "Austria",
        "claim_class": "in_situ_observation",
        "not": "Not a flood CAP. Not PEGELONLINE.",
    },
    "bafu": {
        "id": "bafu",
        "layer": "river",
        "prefixes": ("bafu-",),
        "quantities": _RIVER,
        "licence": "OGD-CH Open-Use",
        "attribution": "BAFU/FOEN LINDAS",
        "geography": "Switzerland",
        "claim_class": "in_situ_observation",
        "not": "Not flood dangerLevel. Geodetic water level, not a warning.",
    },
    "ea-river": {
        "id": "ea-river",
        "layer": "river",
        "prefixes": ("ea-",),
        "exclude_ids": ("ea-flood-01",),
        "exclude_prefixes": ("ea-flood-",),
        "quantities": _RIVER,
        "licence": "OGL v3",
        "attribution": "UK Environment Agency Hydrology API",
        "geography": "England",
        "claim_class": "in_situ_observation",
        "not": "Not ea-flood-01 (warning product). Not SEPA/NRW.",
    },
    "sepa": {
        "id": "sepa",
        "layer": "river",
        "prefixes": ("sepa-",),
        "quantities": _RIVER,
        "licence": "OGL",
        "attribution": "SEPA KiWIS",
        "geography": "Scotland",
        "claim_class": "in_situ_observation",
        "not": "Not a flood CAP. Not EA England.",
    },
    "be-aq": {
        "id": "be-aq",
        "layer": "air",
        "prefixes": ("be-aq-",),
        "quantities": _AIR,
        "licence": "CC BY 4.0",
        "attribution": "IRCELINE SOS",
        "geography": "Belgium",
        "claim_class": "in_situ_observation",
        "not": "Not OpenAQ. Not Sensor.Community crowd density.",
    },
    "hk-aqhi": {
        "id": "hk-aqhi",
        "layer": "air",
        "prefixes": ("hk-aqhi-",),
        "quantities": _AIR,
        "licence": "DATA.GOV.HK",
        "attribution": "Hong Kong EPD AQHI",
        "geography": "Hong Kong",
        "claim_class": "in_situ_observation",
        "not": "AQHI is not PM2.5 µg/m³. Not HKO weather.",
    },
    "sg-psi": {
        "id": "sg-psi",
        "layer": "air",
        "prefixes": ("sg-psi-",),
        "quantities": _AIR,
        "licence": "Singapore Open Data Licence",
        "attribution": "Singapore NEA PSI",
        "geography": "Singapore",
        "claim_class": "in_situ_observation",
        "not": "24h regional index, not a reference-grade monitor.",
    },
    "cdip": {
        "id": "cdip",
        "layer": "marine",
        "prefixes": ("cdip-",),
        "quantities": _MARINE,
        "licence": "unrestricted + CDIP acknowledgement",
        "attribution": "CDIP / Scripps / USACE",
        "geography": "California",
        "claim_class": "in_situ_observation",
        "not": "Not NDBC East Coast. Not Open-Meteo Marine as in-situ.",
    },
}

FORBIDDEN_MESH_HINTS = (
    "om-wx", "om-aq", "om-marine", "open-meteo", "openmeteo",
)


def get_mesh(mesh_id: str) -> MeshSpec | None:
    key = str(mesh_id or "").strip().lower()
    return FIELD_MESHES.get(key)


def mesh_catalog() -> list[dict[str, Any]]:
    rows = []
    for spec in FIELD_MESHES.values():
        rows.append({
            "id": spec["id"],
            "layer": spec["layer"],
            "geography": spec["geography"],
            "licence": spec["licence"],
            "attribution": spec["attribution"],
            "quantities": list(spec["quantities"]),
            "claim_class": spec["claim_class"],
            "not": spec["not"],
        })
    return rows


def _looks_like_open_meteo(station: Mapping[str, Any]) -> bool:
    """Model pins must never ride into an in-situ mesh via a spoofed parent_id."""
    for key in ("id", "parent_id"):
        text = str(station.get(key) or "").strip().lower()
        if any(hint in text for hint in FORBIDDEN_MESH_HINTS):
            return True
    return False


def station_in_mesh(station: Mapping[str, Any], spec: MeshSpec) -> bool:
    if _looks_like_open_meteo(station):
        return False
    sid = str(station.get("id") or "")
    parent = str(station.get("parent_id") or "")
    excluded = tuple(spec.get("exclude_ids") or ())
    if sid in excluded or parent in excluded:
        return False
    for pref in tuple(spec.get("exclude_prefixes") or ()):
        if sid.startswith(pref) or parent.startswith(pref):
            return False
    prefixes = tuple(spec.get("prefixes") or ())
    return any(sid.startswith(p) or parent.startswith(p) for p in prefixes)
