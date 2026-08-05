"""ATLAS Analyst — grounded ask over live snapshot (locale + LLM are separate modules)."""

from __future__ import annotations

import json
from typing import Any

import httpx  # noqa: F401 — re-exported for tests that patch ai_assistant.httpx

from . import __version__
from .aggregator import aggregator
from .ai_locale import (
    EMPTY_QUESTION,
    LOCALE_INSTRUCTIONS,
    detect_question_locale,
    normalize_locale,
    resolve_response_locale,
)
from .formatters import build_detail, headline
from .llm_providers import (
    DEFAULT_MODEL_HEAVY,
    DEFAULT_MODEL_LIGHT,
    DEFAULT_PROVIDER,
    any_provider_configured,
    generate_answer,
    list_providers,
    load_providers_config,
)
from .stations import LAYER_META, STATION_CATALOG

# Re-export for tests / callers that import from this module.
__all__ = [
    "ask",
    "list_providers",
    "any_provider_configured",
    "generate_answer",
    "load_providers_config",
    "build_live_context",
    "build_system_prompt",
    "wants_report",
    "normalize_locale",
    "detect_question_locale",
    "resolve_response_locale",
    "build_detail",
    "DEFAULT_PROVIDER",
    "DEFAULT_MODEL_HEAVY",
    "DEFAULT_MODEL_LIGHT",
    "LOCALE_INSTRUCTIONS",
    "EMPTY_QUESTION",
    "httpx",
]


def build_live_context(
    *,
    station_ids: list[str] | None = None,
    focus_detail: dict[str, Any] | None = None,
) -> str:
    """Compact JSON for the system prompt — always from server-side aggregator."""
    snap = aggregator.snapshot()
    stations = snap.get("stations") or []
    if station_ids:
        wanted = set(station_ids)
        stations = [s for s in stations if s.get("id") in wanted] or stations

    stations_out: list[dict[str, Any]] = []
    for s in stations[:24]:
        if not isinstance(s, dict):
            continue
        values = s.get("values") if isinstance(s.get("values"), dict) else {}
        stations_out.append(
            {
                "id": s.get("id"),
                "layer": s.get("layer"),
                "label": s.get("label"),
                "place": s.get("place"),
                "lat": s.get("lat"),
                "lon": s.get("lon"),
                "online": s.get("online"),
                "live": s.get("live"),
                "headline": s.get("headline") or headline(str(s.get("layer") or ""), values),
                "has_reading": bool(s.get("has_reading") or values),
                "values": values,
                "reading_age_ms": s.get("reading_age_ms"),
                "source": s.get("source"),
            }
        )

    payload = {
        "service": "atlas",
        "version": __version__,
        "status": snap.get("status"),
        "generated_at": snap.get("generated_at"),
        "fleet_age_ms": snap.get("age_ms"),
        "stale": snap.get("stale"),
        "gaia_url": snap.get("gaia_url"),
        "layers": LAYER_META,
        "summary": snap.get("summary") or {},
        "stations": stations_out,
        "quakes": (snap.get("quakes") or [])[:12],
        "catalog_size": len(STATION_CATALOG),
    }
    if focus_detail:
        payload["focused_station"] = {
            "id": focus_detail.get("id"),
            "title": focus_detail.get("title"),
            "summary": focus_detail.get("summary"),
            "metrics": focus_detail.get("metrics"),
            "status_line": focus_detail.get("status_line"),
            "values": focus_detail.get("values"),
        }
    return json.dumps(payload, ensure_ascii=False, default=str)


def build_system_prompt(
    *,
    locale: str,
    live_json: str,
    report: bool = False,
) -> str:
    lang = LOCALE_INSTRUCTIONS.get(locale, LOCALE_INSTRUCTIONS["en"])
    role = (
        "You are ATLAS Analyst — the AI assistant for the ATLAS physical sensor map "
        "in the AICOM / AIMarket ecosystem. You analyze live weather, air quality, "
        "tide, grid-carbon and earthquake data relayed from the GAIA physical-oracle gateway."
    )
    rules = (
        "Rules:\n"
        "- Use ONLY the LIVE ATLAS SNAPSHOT below for numbers, stations, and timestamps.\n"
        "- Cite station ids (e.g. om-wx-01) and places when stating readings.\n"
        "- If a reading is missing (has_reading=false / empty values), say so — do not invent.\n"
        "- Distinguish LIVE public-API relays from simulated / offline pins.\n"
        "- Be concise and technical; use short sections with headings when useful.\n"
        "- Never claim you wrote to sensors or changed operator anchors — ATLAS is read-only.\n"
        f"- {lang}"
    )
    if report:
        rules += (
            "\n- Produce a structured situation report with sections: "
            "Overview, Weather, Air quality, Tide/Grid, Earthquakes, Risks & anomalies, Recommended next checks."
        )
    return (
        f"{role}\n\n{rules}\n\n"
        "LIVE ATLAS SNAPSHOT (server-authoritative JSON):\n"
        f"{live_json}"
    )


def wants_report(question: str, report_flag: bool) -> bool:
    if report_flag:
        return True
    q = (question or "").lower()
    markers = (
        "report", "ситуац", "отчёт", "отчет", "сводк", "анализ",
        "informe", "rapport", "报告", "briefing",
    )
    return any(m in q for m in markers)


async def ask(
    *,
    question: str,
    locale: str = "en",
    provider: str | None = None,
    model_role: str = "heavy",
    station_ids: list[str] | None = None,
    bbox: dict[str, float] | None = None,
    report: bool = False,
) -> dict[str, Any]:
    """High-level ask: optionally refresh viewport, ground prompt, call LLM."""
    q = (question or "").strip()
    loc = resolve_response_locale(q, locale)
    if not q:
        return {
            "answer": EMPTY_QUESTION.get(loc, EMPTY_QUESTION["en"]),
            "meta": {"provider": None, "model": None, "live_state": False},
        }

    if bbox and all(k in bbox for k in ("west", "south", "east", "north")):
        try:
            await aggregator.refresh_viewport(
                west=float(bbox["west"]),
                south=float(bbox["south"]),
                east=float(bbox["east"]),
                north=float(bbox["north"]),
                force=False,
            )
            if station_ids is None:
                station_ids = aggregator.stations_in_bbox(
                    float(bbox["west"]),
                    float(bbox["south"]),
                    float(bbox["east"]),
                    float(bbox["north"]),
                )
        except Exception:
            pass

    focus_detail = None
    if station_ids and len(station_ids) == 1:
        try:
            focus_detail = await aggregator.station_detail(station_ids[0], fresh=False)
        except Exception:
            focus_detail = None
    elif station_ids:
        try:
            await aggregator._ensure_readings(station_ids[:8], force=False)
        except Exception:
            pass

    report_mode = wants_report(q, report)
    live_json = build_live_context(station_ids=station_ids, focus_detail=focus_detail)
    system_prompt = build_system_prompt(locale=loc, live_json=live_json, report=report_mode)

    if not any_provider_configured():
        snap = aggregator.snapshot()
        stations = snap.get("stations") or []
        lines = [
            "ATLAS Analyst (offline — set DEEPSEEK_API_KEY for full answers).",
            f"Fleet status: {snap.get('status')} · stations: {len(stations)} · "
            f"cached readings: {(snap.get('summary') or {}).get('cached_readings', 0)}.",
        ]
        for s in stations[:6]:
            if s.get("has_reading") or s.get("values"):
                lines.append(
                    f"- {s.get('id')} ({s.get('place')}): {s.get('headline') or '—'}"
                )
        if report_mode:
            lines.insert(1, "Situation brief (cache-only):")
        return {
            "answer": "\n".join(lines),
            "meta": {
                "provider": None,
                "model": None,
                "live_state": True,
                "offline": True,
                "report": report_mode,
                "locale": loc,
            },
        }

    answer, meta = await generate_answer(
        question=q,
        locale=loc,
        system_prompt=system_prompt,
        provider_id=provider,
        model_role=model_role,
    )
    meta.update(
        {
            "live_state": True,
            "report": report_mode,
            "locale": loc,
            "stations_in_context": len(json.loads(live_json).get("stations") or []),
        }
    )
    return {"answer": answer, "meta": meta}
