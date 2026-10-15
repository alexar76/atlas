"""Locale detection / reply-language helpers for ATLAS Analyst.

Policy: answer in the language of the question; if unclear → UI localization.
"""

from __future__ import annotations

import re

LOCALE_INSTRUCTIONS: dict[str, str] = {
    "en": (
        "Reply in English. Match the user's question language when it is clearly "
        "English; never switch to another language mid-answer."
    ),
    "ru": (
        "Отвечай на русском языке. Если вопрос явно на русском — только русский, "
        "без переключения на английский."
    ),
    "es": (
        "Responde en español. Si la pregunta está claramente en español, "
        "no cambies a otro idioma."
    ),
    "fr": (
        "Réponds en français. Si la question est clairement en français, "
        "ne passe pas à une autre langue."
    ),
    "zh": "请用中文回答。如果问题明显是中文，不要切换到其他语言。",
}

EMPTY_QUESTION: dict[str, str] = {
    "en": "Ask about live sensors — or anything in the AICOM / AIMarket ecosystem (GAIA, Hub, ARGUS, Metis…).",
    "ru": "Спросите о живых датчиках — или о всей экосистеме AICOM / AIMarket (GAIA, Hub, ARGUS, Metis…).",
    "es": "Pregunta por sensores en vivo — o por el ecosistema AICOM / AIMarket (GAIA, Hub, ARGUS, Metis…).",
    "fr": "Posez une question sur les capteurs — ou sur l’écosystème AICOM / AIMarket (GAIA, Hub, ARGUS, Metis…).",
    "zh": "请询问实时传感器，或 AICOM / AIMarket 生态中的任何组件（GAIA、Hub、ARGUS、Metis…）。",
}

# High-signal function words / markers (lowercase). Avoid station ids / English jargon alone.
_RU_MARKERS = (
    "что", "как", "где", "есть", "нет", "про", "по", "для", "или", "это",
    "сравни", "анализ", "отчёт", "отчет", "сводк", "погод", "воздух",
    "землетряс", "прилив", "датчик", "составь", "краткий", "разбор",
)
_ES_MARKERS = (
    "qué", "que", "cómo", "como", "cuál", "cual", "dónde", "donde",
    "está", "estan", "hay", "para", "por", "con", "los", "las", "una",
    "informe", "calidad", "aire", "clima", "marea", "terremoto", "sensor",
)
_FR_MARKERS = (
    "quoi", "comment", "où", "est", "les", "des", "une", "pour", "avec",
    "rapport", "qualité", "air", "météo", "meteo", "marée", "maree",
    "séisme", "seisme", "capteur", "analyse", "compare",
)
_EN_MARKERS = (
    "what", "how", "where", "why", "which", "the", "and", "for", "with",
    "about", "report", "compare", "weather", "air", "quality", "tide",
    "quake", "earthquake", "sensor", "station", "summary", "brief",
    "anomal", "please", "show", "give",
)

_ES_CHARS = set("áéíóúñü¿¡")
_FR_CHARS = set("àâæçéèêëïîôœùûüÿ")


def normalize_locale(raw: str) -> str:
    code = (raw or "en").strip().lower()[:2]
    return code if code in LOCALE_INSTRUCTIONS else "en"


def _alpha_counts(text: str) -> tuple[int, int, int, int]:
    """cyrillic, cjk, latin_ascii, latin_extended (accents)."""
    cyr = cjk = latin = accented = 0
    for c in text:
        o = ord(c)
        if "\u0400" <= c <= "\u04ff":
            cyr += 1
        elif "\u4e00" <= c <= "\u9fff":
            cjk += 1
        elif c.isalpha() and o < 128:
            latin += 1
        elif c.isalpha() and ("\u00c0" <= c <= "\u024f" or c in _ES_CHARS | _FR_CHARS):
            accented += 1
    return cyr, cjk, latin, accented


def _marker_hits(lower: str, markers: tuple[str, ...]) -> int:
    # Word-boundary-ish: spaces / punctuation around short markers.
    hits = 0
    for m in markers:
        if " " in m:
            if m in lower:
                hits += 1
        elif re.search(rf"(?<![a-zа-яё]){re.escape(m)}(?![a-zа-яё])", lower, re.I):
            hits += 1
    return hits


def detect_question_locale(question: str) -> str | None:
    """
    Return a confident language code, or None if unclear.

    Unclear → caller falls back to UI localization locale.
    """
    text = (question or "").strip()
    if not text:
        return None

    cyr, cjk, latin, accented = _alpha_counts(text)
    letters = cyr + cjk + latin + accented
    if letters < 2:
        return None

    lower = text.lower()

    # Script-dominant paths first.
    if cjk >= 2 and cjk >= max(cyr, latin + accented):
        return "zh"
    if cyr >= 2 and cyr >= (latin + accented):
        return "ru"

    # Accented Latin → prefer FR/ES over EN.
    es_chars = sum(1 for c in lower if c in _ES_CHARS)
    fr_chars = sum(1 for c in lower if c in _FR_CHARS)
    es_m = _marker_hits(lower, _ES_MARKERS)
    fr_m = _marker_hits(lower, _FR_MARKERS)
    en_m = _marker_hits(lower, _EN_MARKERS)

    if es_chars >= 1 or es_m >= 2:
        if fr_m > es_m and fr_chars >= es_chars:
            return "fr"
        return "es"
    if fr_chars >= 1 or fr_m >= 2:
        return "fr"

    # Pure ASCII Latin: need English markers, else unclear (→ UI locale).
    if latin + accented >= 2:
        if en_m >= 2 or (en_m >= 1 and letters >= 12):
            return "en"
        if es_m >= 2:
            return "es"
        if fr_m >= 2:
            return "fr"
        # Short / jargon-only ("om-wx-01?", "PM2.5") — not confident.
        return None

    return None


def resolve_response_locale(question: str, ui_locale: str) -> str:
    """Question language wins; if detection is unsure → UI / browser locale."""
    detected = detect_question_locale(question)
    if detected:
        return detected
    return normalize_locale(ui_locale)


def reply_language_rule(locale: str) -> str:
    """Hard system-prompt rule for the resolved reply language."""
    base = LOCALE_INSTRUCTIONS.get(locale, LOCALE_INSTRUCTIONS["en"])
    return (
        f"{base} "
        "Primary rule: answer in the language of the user's question when it is clear; "
        f"the resolved reply language for this turn is «{locale}» "
        "(fallback from UI localization when the question language was unclear)."
    )
