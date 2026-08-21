"""Map navigation actions for ATLAS Analyst (fly / open station).

Deterministic (like Alien Monitor ``ai_nav_actions``): parse the question for
places and station ids, return client actions. The LLM still writes the answer;
the UI executes flyTo + openDetail.
"""

from __future__ import annotations

import re
from typing import Any

from .extra_sensors import place_targets as extra_place_targets
from .om_mesh import place_targets
from .stations import STATION_CATALOG

# Place → preferred station ids (first = primary focus) + map center.
PLACE_TARGETS: dict[str, dict[str, Any]] = {
    "berlin": {
        "aliases": ("berlin", "берлин", "berlín", "berlino", "柏林"),
        "station_ids": ("om-wx-01", "om-aq-01", "osm-01", "sta-01"),
        "lon": 13.41,
        "lat": 52.52,
        "zoom": 9.5,
        "label": "Berlin",
    },
    "nyc": {
        "aliases": (
            "nyc", "new york", "new-york", "manhattan", "central park",
            "нью-йорк", "нью йорк", "battery", "the battery",
            "nueva york", "new york city", "纽约", "紐約",
        ),
        "station_ids": ("nws-01", "noaa-tide-01", "ndbc-01", "om-marine-01"),
        "lon": -74.0,
        "lat": 40.74,
        "zoom": 10.0,
        "label": "New York",
    },
    "potomac": {
        "aliases": ("potomac", "little falls", "потомак", "usgs river"),
        "station_ids": ("usgs-river-01",),
        "lon": -77.1275,
        "lat": 38.9495,
        "zoom": 10.0,
        "label": "Potomac River",
    },
    "uk": {
        "aliases": (
            "united kingdom", "britain", "uk grid", "uk carbon", "london",
            "великобритан", "лондон", "royaume-uni", "reino unido", "英国", "英國",
        ),
        "station_ids": ("uk-grid-01",),
        "lon": -2.0,
        "lat": 54.0,
        "zoom": 5.0,
        "label": "United Kingdom",
    },
    "demo": {
        "aliases": (
            "demo campus", "gaia demo", "sim campus", "bern", "switzerland",
            "берн", "швейцар", "suisse", "suiza", "伯尔尼", "瑞士",
        ),
        "station_ids": ("ws-01", "ws-02", "aq-01", "em-01"),
        "lon": 7.4474,
        "lat": 46.9480,
        "zoom": 11.0,
        "label": "GAIA demo campus",
    },
    "quake": {
        "aliases": (
            "earthquake", "quake", "seism", "землетряс", "сейсм",
            "terremoto", "séisme", "seisme", "地震",
        ),
        "station_ids": ("usgs-quake-01",),
        "lon": None,  # filled from live reading when available
        "lat": None,
        "zoom": 4.5,
        "label": "Earthquake",
    },
}
PLACE_TARGETS.update(place_targets())
PLACE_TARGETS.update(extra_place_targets())

LAYER_HINTS: dict[str, tuple[str, ...]] = {
    "weather": ("weather", "температ", "погод", "météo", "meteo", "clima", "天气", "溫度", "温度"),
    "air": ("air quality", "воздух", "pm2", "pm10", "aqi", "calidad del aire", "qualité de l'air", "空气"),
    "tide": ("tide", "прилив", "marea", "marée", "maree", "潮汐"),
    "river": ("river", "stream", "discharge", "река", "gauge", "gage", "flood", "паводок", "rivière", "河流"),
    "marine": ("marine", "buoy", "wave", "ocean", "море", "волн", "буй", "mer", "vague", "海浪", "浮标"),
    "grid": ("grid", "carbon", "углерод", "gco2", "碳强度", "电网"),
    "quake": ("earthquake", "quake", "землетряс", "terremoto", "séisme", "地震"),
    "energy": ("energy", "энерг", "énergie", "energia", "能源"),
    "fire": ("fire", "wildfire", "firms", "пожар", "incendie", "火灾", "野火"),
    "radiation": ("radiation", "safecast", "cpm", "радиац", "radiation", "辐射"),
    "jamming": ("jamming", "gnss", "spoofing", "gps jam", "глушен", "干扰"),
    "gnss": ("gnss integrity", "gps integrity", "degradation", "целостность gnss", "деградац", "完整性"),
    "traffic": ("ads-b", "adsb", "aircraft", "feeder", "самолёт", "飞机"),
    "ais": ("ais", "fintraffic", "digitraffic", "vessel", "судно", "barco", "navire", "船舶"),
    "events": ("eonet", "natural event", "катастроф", "стихийн", "événement naturel", "自然灾害"),
    "spacewx": ("space weather", "kp index", "aurora", "космическ", "aurora", "空间天气", "полярн"),
    "lightning": ("lightning", "glm", "молни", "rayo", "foudre", "闪电"),
    "alerts": ("nws alert", "cap", "warning", "watch", "оповещ", "alerta", "预警"),
    "argo": ("argo", "float", "salinity", "арго", "flotteur", "浮标"),
    "geomag": ("geomag", "magnet", "nT", "геомагн", "地磁"),
    "iot": ("iot", "tasmota", "ttn", "senml", "датчик"),
    "flood": ("flood", "waterwatch", "nws-flood", "паводок", "inundac", "crue", "洪水"),
    "effis": ("effis", "copernicus fire", "burned", "европ пожар"),
    "volcano": ("volcano", "вулкан", "volcán", "volcan", "火山"),
    "tsunami": ("tsunami", "цунами", "maremoto", "raz-de-marée", "海啸"),
}

NAV_VERBS = (
    "show", "open", "find", "zoom", "focus", "fly", "navigate", "go to", "take me",
    "center", "highlight", "select", "display", "bring", "look at", "check",
    "покаж", "найди", "открой", "перейди", "сфокус", "приблизь", "увелич", "выведи",
    "посмотри", "глянь", "проверь",
    "muéstr", "muestr", "encuentr", "abre", "naveg", "enfoc", "centr", "mira",
    "montre", "montr", "ouvre", "trouv", "navigu", "affich", "regarde",
    "显示", "顯示", "打开", "打開", "找到", "飞到", "飛到", "聚焦", "看看", "定位",
)

WHERE_MARKERS = (
    "where", "где", "dónde", "donde", "où", "哪里", "哪儿", "在哪",
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# Scripts without word boundaries (CJK and up) — plain substring is correct.
_NO_BOUNDARY_SCRIPT = 0x2E80


def _alias_hit(alias: str, q: str) -> bool:
    """Alias match against an already normalized (lowercased) question.

    Short Latin/Cyrillic aliases require token boundaries: without that a 2–4
    char alias matches inside unrelated words ("la" in *disp**la**y*, "nyc" in
    a hash) and hijacks the whole map action.
    """
    a = (alias or "").lower().strip()
    if not a:
        return False
    if any(ord(c) >= _NO_BOUNDARY_SCRIPT for c in a):
        return a in q
    if len(a) <= 4 and " " not in a:
        # Leading boundary only: it kills the "la" inside disp**la**y / ca**la**idad
        # while still matching inflected and localised forms that append letters
        # ("каир" → «в Каире», "bern" → "Berne" / "Berna", "дели" → "нью-дели").
        return re.search(rf"(?<![0-9a-zа-яё]){re.escape(a)}", q) is not None
    return a in q


def _match_place(question: str) -> str | None:
    q = _normalize(question)
    best: tuple[int, str] | None = None
    for place_id, spec in PLACE_TARGETS.items():
        for alias in spec["aliases"]:
            if _alias_hit(alias, q):
                score = len(alias)
                if best is None or score > best[0]:
                    best = (score, place_id)
    return best[1] if best else None


def _match_station_ids(question: str) -> list[str]:
    q = _normalize(question)
    found: list[str] = []
    for sid, meta in STATION_CATALOG.items():
        if sid.lower() in q:
            found.append(sid)
            continue
        label = str(meta.get("label") or "").lower()
        place = str(meta.get("place") or "").lower()
        if label and len(label) >= 6 and _alias_hit(label, q):
            found.append(sid)
        elif place and len(place) >= 5 and sid not in found and _alias_hit(place, q):
            # e.g. "Central Park"
            found.append(sid)
    # de-dupe preserve order
    out: list[str] = []
    for s in found:
        if s not in out:
            out.append(s)
    return out


def _match_layers(question: str) -> list[str]:
    q = _normalize(question)
    layers: list[str] = []
    for layer, hints in LAYER_HINTS.items():
        if any(h in q for h in hints):
            layers.append(layer)
    return layers


def _has_nav_intent(question: str) -> bool:
    q = _normalize(question)
    if any(v in q for v in NAV_VERBS):
        return True
    if any(m in q for m in WHERE_MARKERS):
        return True
    # Implicit: named place + sensor vocabulary → show on map.
    if _match_place(question) and (
        _match_layers(question) or _match_station_ids(question) or "sensor" in q
        or "датчик" in q or "station" in q or "станц" in q
    ):
        return True
    if _match_station_ids(question):
        return True
    return False


def _station_coords(station_id: str, snap: dict[str, Any] | None) -> tuple[float, float] | None:
    if snap:
        for s in snap.get("stations") or []:
            if isinstance(s, dict) and s.get("id") == station_id:
                try:
                    lat, lon = float(s["lat"]), float(s["lon"])
                    if abs(lat) > 1e-6 or abs(lon) > 1e-6:
                        return lon, lat
                except (KeyError, TypeError, ValueError):
                    pass
    meta = STATION_CATALOG.get(station_id) or {}
    try:
        lat, lon = float(meta["lat"]), float(meta["lon"])
        if abs(lat) > 1e-6 or abs(lon) > 1e-6:
            return lon, lat
    except (KeyError, TypeError, ValueError):
        pass
    return None


def resolve_map_actions(
    question: str,
    *,
    snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return client map actions for the ATLAS UI."""
    if not _has_nav_intent(question):
        return []

    station_ids = _match_station_ids(question)
    place_id = _match_place(question)
    layers = _match_layers(question)

    if place_id and not station_ids:
        spec = PLACE_TARGETS[place_id]
        candidates = list(spec["station_ids"])
        if layers:
            filtered = [
                sid
                for sid in candidates
                if (STATION_CATALOG.get(sid) or {}).get("layer") in layers
            ]
            station_ids = filtered or candidates
        else:
            station_ids = candidates

    if layers and not station_ids:
        # Layer-only: pick first catalog station per layer (prefer live).
        for layer in layers:
            live = [
                sid
                for sid, m in STATION_CATALOG.items()
                if m.get("layer") == layer and m.get("mode") == "live"
            ]
            sims = [
                sid
                for sid, m in STATION_CATALOG.items()
                if m.get("layer") == layer and m.get("mode") == "sim"
            ]
            pick = (live or sims)
            if pick:
                station_ids.append(pick[0])

    if not station_ids and not place_id:
        return []

    actions: list[dict[str, Any]] = []

    # Fly: prefer place center, else first station coords.
    if place_id:
        spec = PLACE_TARGETS[place_id]
        lon, lat = spec.get("lon"), spec.get("lat")
        if place_id == "quake" and station_ids:
            coords = _station_coords(station_ids[0], snapshot)
            if coords:
                lon, lat = coords
        if lon is not None and lat is not None:
            actions.append(
                {
                    "type": "fly_to",
                    "lon": float(lon),
                    "lat": float(lat),
                    "zoom": float(spec.get("zoom") or 6),
                    "label": spec.get("label") or place_id,
                    "place_id": place_id,
                }
            )
    elif station_ids:
        coords = _station_coords(station_ids[0], snapshot)
        if coords:
            lon, lat = coords
            kind = (STATION_CATALOG.get(station_ids[0]) or {}).get("kind")
            actions.append(
                {
                    "type": "fly_to",
                    "lon": lon,
                    "lat": lat,
                    "zoom": 4.0 if kind == "region" else 6.5,
                    "label": station_ids[0],
                    "station_id": station_ids[0],
                }
            )

    # Open detail panels (primary first; cap 3 to avoid spam).
    for sid in station_ids[:3]:
        if sid not in STATION_CATALOG:
            continue
        actions.append({"type": "focus_station", "station_id": sid})

    return actions


def map_action_station_ids(actions: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for a in actions:
        sid = a.get("station_id")
        if isinstance(sid, str) and sid not in ids:
            ids.append(sid)
    return ids


def append_map_hint(answer: str, actions: list[dict[str, Any]], locale: str) -> str:
    if not actions or not answer:
        return answer
    fly = next((a for a in actions if a.get("type") == "fly_to"), None)
    focuses = [a for a in actions if a.get("type") == "focus_station"]
    if not fly and not focuses:
        return answer
    label = str((fly or {}).get("label") or (focuses[0].get("station_id") if focuses else "map"))
    ids = ", ".join(str(a.get("station_id")) for a in focuses[:3])
    hints = {
        "en": f"\n\n— Map: flying to **{label}**"
        + (f" and opening {ids}." if ids else "."),
        "ru": f"\n\n— Карта: приближаю **{label}**"
        + (f" и открываю {ids}." if ids else "."),
        "es": f"\n\n— Mapa: volando a **{label}**"
        + (f" y abriendo {ids}." if ids else "."),
        "fr": f"\n\n— Carte : vol vers **{label}**"
        + (f" et ouverture de {ids}." if ids else "."),
        "zh": f"\n\n— 地图：飞向 **{label}**"
        + (f" 并打开 {ids}。" if ids else "。"),
    }
    # Avoid duplicating if the model already described the fly.
    lower = answer.lower()
    if "flying" in lower or "приближ" in lower or "volando" in lower or "飞向" in lower:
        return answer
    return answer + hints.get(locale, hints["en"])
