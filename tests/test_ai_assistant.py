"""AI assistant grounding / locale / report detection."""

from __future__ import annotations

import json

import pytest

from app import ai_assistant as ai
from app.aggregator import Aggregator


def test_default_provider_is_deepseek():
    assert ai.DEFAULT_PROVIDER == "deepseek_api"
    assert ai.DEFAULT_MODEL_HEAVY == "deepseek-v4-pro"
    listed = ai.list_providers()
    assert listed["default_provider"] == "deepseek_api"
    assert listed["default_model"] == "deepseek-v4-pro"


def test_locale_detection_ru_en():
    assert ai.detect_question_locale("Составь отчёт по погоде") == "ru"
    assert ai.detect_question_locale("Summarize air quality") == "en"
    assert ai.resolve_response_locale("Qué pasa", "en") == "es"


def test_wants_report():
    assert ai.wants_report("make a report please", False) is True
    assert ai.wants_report("Составь отчёт", False) is True
    assert ai.wants_report("что с погодой?", False) is False
    assert ai.wants_report("hello", True) is True


@pytest.mark.asyncio
async def test_build_live_context_contains_stations(aggregator: Aggregator, monkeypatch):
    monkeypatch.setattr(ai, "aggregator", aggregator)
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    raw = ai.build_live_context(station_ids=["om-wx-01", "om-aq-01"])
    data = json.loads(raw)
    assert data["service"] == "atlas"
    ids = {s["id"] for s in data["stations"]}
    assert "om-wx-01" in ids
    wx = next(s for s in data["stations"] if s["id"] == "om-wx-01")
    assert wx["values"]["temperature_c"] == 21.5


@pytest.mark.asyncio
async def test_system_prompt_report_sections():
    prompt = ai.build_system_prompt(
        locale="ru",
        live_json='{"stations":[]}',
        report=True,
    )
    assert "LIVE ATLAS SNAPSHOT" in prompt
    assert "Отвечай на русском" in prompt
    assert "Overview" in prompt or "situation report" in prompt.lower()


@pytest.mark.asyncio
async def test_ask_offline(aggregator: Aggregator, monkeypatch):
    monkeypatch.setattr(ai, "aggregator", aggregator)
    monkeypatch.setattr(ai, "any_provider_configured", lambda: False)
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    out = await ai.ask(
        question="Составь ситуационный отчёт",
        locale="ru",
        report=True,
        bbox={"west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7},
    )
    assert out["meta"]["offline"] is True
    assert out["meta"]["report"] is True
    assert out["meta"]["live_state"] is True
    assert len(out["answer"]) > 20


@pytest.mark.asyncio
async def test_ask_empty_question(monkeypatch, aggregator: Aggregator):
    monkeypatch.setattr(ai, "aggregator", aggregator)
    out = await ai.ask(question="  ", locale="en")
    assert "Ask about" in out["answer"] or "sensor" in out["answer"].lower()


@pytest.mark.asyncio
async def test_generate_answer_calls_openai_compatible(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Berlin is 21.5 °C."}}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            assert "chat/completions" in url
            assert json["model"] == "deepseek-v4-pro"
            assert json["messages"][0]["role"] == "system"
            return FakeResp()

    from app import llm_providers as llm

    monkeypatch.setattr(llm.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        llm,
        "load_providers_config",
        lambda: {
            "default_provider": "deepseek_api",
            "providers": {
                "deepseek_api": {
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "api_key": "sk-test",
                    "base_url": "https://api.deepseek.com/v1",
                    "models": {"heavy": "deepseek-v4-pro", "light": "deepseek-v4-flash"},
                    "provider_type": "openai_compatible",
                    "capabilities": {"max_tokens": 1024},
                }
            },
        },
    )
    text, meta = await ai.generate_answer(
        question="What is the temperature?",
        locale="en",
        system_prompt="You are ATLAS.",
        model_role="heavy",
    )
    assert "21.5" in text
    assert meta["provider"] == "deepseek_api"
    assert meta["model"] == "deepseek-v4-pro"
