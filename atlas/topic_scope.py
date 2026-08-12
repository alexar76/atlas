"""Strict topic scope for ATLAS Analyst — sensors + AICOM/AIMarket only.

Scope markers for map layers / Hub SKUs are **auto-derived** from
``STATION_CATALOG`` + ``LAYER_META`` + ``LAYER_HINTS`` so new capabilities
do not require editing this file.
"""

from __future__ import annotations

import re
from typing import Optional

from functools import lru_cache

from .capability_awareness import GENERIC_SCOPE_MARKERS, dynamic_scope_markers

_OFF_TOPIC_RES = [
    re.compile(r"\b(write|generate)\s+(me\s+)?(a\s+)?(poem|song|essay|novel)\b", re.I),
    re.compile(r"\b(recipe|cook|bake)\b", re.I),
    re.compile(r"\b(stock|crypto)\s+(tip|pick|predict)", re.I),
    re.compile(r"\bwho\s+won\s+(the\s+)?(election|match|game)\b", re.I),
    re.compile(r"\b(write|generate|debug)\s+(me\s+)?(some\s+)?(python|javascript|code)\b", re.I),
    re.compile(r"\bhack\s+(into|a)\b", re.I),
    re.compile(r"напиши\s+(стих|песн|рецепт|код)", re.I),
    re.compile(r"рецепт\s+", re.I),
]

OUT_OF_SCOPE: dict[str, str] = {
    "en": (
        "ATLAS Analyst only answers about (1) live GAIA sensor readings on this map "
        "(all ATLAS layers, including fire / radiation / jamming / traffic), "
        "(2) the live AIMarket Hub federation catalog (peers / capability ids), "
        "and (3) the AICOM / AIMarket ecosystem (Hub, ARGUS, Metis, oracles, …). "
        "Rephrase within that scope."
    ),
    "ru": (
        "ATLAS Analyst отвечает только про (1) показания датчиков GAIA на этой карте "
        "(все слои ATLAS, включая пожары / радиацию / глушение / трафик), "
        "(2) живой каталог федерации AIMarket Hub (peers / capability id), "
        "и (3) экосистему AICOM / AIMarket (Hub, ARGUS, Metis, оракулы…). "
        "Переформулируйте вопрос в этих рамках."
    ),
    "es": (
        "ATLAS Analyst solo responde sobre (1) lecturas de sensores GAIA en este mapa "
        "(todas las capas ATLAS, incl. fuego / radiación / jamming / tráfico), "
        "(2) el catálogo vivo de federación del Hub AIMarket, "
        "y (3) el ecosistema AICOM / AIMarket. Reformule dentro de ese alcance."
    ),
    "fr": (
        "ATLAS Analyst ne répond que sur (1) les lectures capteurs GAIA de cette carte "
        "(toutes les couches ATLAS, y compris feu / radiation / brouillage / trafic), "
        "(2) le catalogue de fédération Hub AIMarket en direct, "
        "et (3) l’écosystème AICOM / AIMarket. Reformulez dans ce périmètre."
    ),
    "zh": (
        "ATLAS Analyst 仅回答：(1) 本地图上的 GAIA 传感器读数"
        "（含野火 / 辐射 / GNSS 干扰 / 边缘交通等全部 ATLAS 图层）；"
        "(2) AIMarket Hub 联邦目录（peers / capability）；"
        "(3) AICOM / AIMarket 生态。请在此范围内重新提问。"
    ),
}


@lru_cache(maxsize=1)
def _scope_matchers() -> tuple[tuple[str, ...], "re.Pattern[str] | None"]:
    """Substring markers + a word-boundary regex for generic English words.

    "peer" / "manifest" / "catalog" / "invoke" are real federation-question
    signals but terrible substrings ("Shakespeare" contains "peer") — they
    only count as whole words.
    """
    substrings: list[str] = []
    generics: list[str] = []
    for m in dynamic_scope_markers():
        (generics if m in GENERIC_SCOPE_MARKERS else substrings).append(m)
    generic_re = (
        re.compile(r"\b(?:" + "|".join(re.escape(g) for g in generics) + r")\b")
        if generics
        else None
    )
    return tuple(substrings), generic_re


def _has_scope_marker(text: str) -> bool:
    lower = text.lower()
    substrings, generic_re = _scope_matchers()
    if any(m in lower for m in substrings):
        return True
    return bool(generic_re and generic_re.search(lower))


def out_of_scope_reason(text: str) -> Optional[str]:
    """Return a reason string if the question is outside Analyst scope."""
    t = (text or "").strip()
    if not t:
        return None
    if any(p.search(t) for p in _OFF_TOPIC_RES) and not _has_scope_marker(t):
        return "off_topic_pattern"
    # Longer questions with zero ecosystem/sensor markers → refuse (no free chat).
    if len(t) >= 24 and not _has_scope_marker(t):
        return "no_scope_markers"
    return None


def out_of_scope_answer(locale: str) -> str:
    return OUT_OF_SCOPE.get(locale) or OUT_OF_SCOPE["en"]
