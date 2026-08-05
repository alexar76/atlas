"""Locale detection / reply-language helpers for ATLAS Analyst."""

from __future__ import annotations

LOCALE_INSTRUCTIONS: dict[str, str] = {
    "en": "Reply in English.",
    "ru": "Отвечай на русском языке.",
    "es": "Responde en español.",
    "fr": "Réponds en français.",
    "zh": "请用中文回答。",
}

EMPTY_QUESTION: dict[str, str] = {
    "en": "Ask about the live sensors, air quality, weather, tides, or earthquakes.",
    "ru": "Спросите о живых датчиках, воздухе, погоде, приливах или землетрясениях.",
    "es": "Pregunta sobre sensores en vivo, aire, clima, mareas o terremotos.",
    "fr": "Posez une question sur les capteurs, l’air, la météo, les marées ou les séismes.",
    "zh": "请询问实时传感器、空气质量、天气、潮汐或地震。",
}


def normalize_locale(raw: str) -> str:
    code = (raw or "en").strip().lower()[:2]
    return code if code in LOCALE_INSTRUCTIONS else "en"


def detect_question_locale(question: str) -> str | None:
    text = (question or "").strip()
    if not text:
        return None
    cyrillic = sum(1 for c in text if "\u0400" <= c <= "\u04ff")
    latin = sum(1 for c in text if c.isalpha() and ord(c) < 128)
    lower = text.lower()
    if cyrillic >= 2 and cyrillic >= latin:
        return "ru"
    if any(c in lower for c in "áéíóúñü¿¡") or any(
        w in lower for w in ("qué", "cómo", "cuál", "dónde")
    ):
        return "es"
    if any("\u4e00" <= c <= "\u9fff" for c in text):
        return "zh"
    if latin >= 2:
        return "en"
    return None


def resolve_response_locale(question: str, ui_locale: str) -> str:
    return detect_question_locale(question) or normalize_locale(ui_locale)
