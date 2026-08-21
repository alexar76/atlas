"""AI assistant grounding / locale / report detection."""

from __future__ import annotations

import json

import pytest

from atlas import ai_assistant as ai
from atlas.aggregator import Aggregator


def test_default_provider_is_deepseek():
    assert ai.DEFAULT_PROVIDER == "deepseek_api"
    assert ai.DEFAULT_MODEL_HEAVY == "deepseek-v4-pro"
    listed = ai.list_providers()
    assert listed["default_provider"] == "deepseek_api"
    assert listed["default_model"] == "deepseek-v4-pro"


def test_locale_detection_ru_en():
    assert ai.detect_question_locale("Составь отчёт по погоде") == "ru"
    assert ai.detect_question_locale("Summarize air quality") == "en"
    assert ai.resolve_response_locale("Qué pasa con el aire", "en") == "es"


def test_locale_falls_back_to_ui_when_unclear():
    # Station id / jargon alone → unclear → UI locale.
    assert ai.detect_question_locale("om-wx-01?") is None
    assert ai.resolve_response_locale("om-wx-01?", "ru") == "ru"
    assert ai.resolve_response_locale("???", "fr") == "fr"
    assert ai.resolve_response_locale("PM2.5", "zh") == "zh"


def test_locale_detects_fr():
    assert ai.detect_question_locale("Quelle est la qualité de l'air à Berlin?") == "fr"
    assert ai.resolve_response_locale("Fais un rapport météo", "en") == "fr"

def test_wants_report():
    assert ai.wants_report("make a report please", False) is True
    assert ai.wants_report("Составь отчёт", False) is True
    assert ai.wants_report("что с погодой?", False) is False
    assert ai.wants_report("hello", True) is True


@pytest.mark.asyncio
async def test_build_live_context_contains_stations(aggregator: Aggregator, monkeypatch):
    monkeypatch.setattr(ai, "aggregator", aggregator)

    def fake_fed():
        return {"ok": True, "capabilities": [{"capability_id": "gaia.fire.read@v1"}], "peers": []}

    monkeypatch.setattr(ai, "federation_slice", fake_fed)
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    raw = ai.build_live_context(station_ids=["om-wx-01", "om-aq-01"])
    data = json.loads(raw)
    assert data["service"] == "atlas"
    ids = {s["id"] for s in data["stations"]}
    assert "om-wx-01" in ids
    wx = next(s for s in data["stations"] if s["id"] == "om-wx-01")
    assert wx["values"]["temperature_c"] == 21.5
    assert "layer_coverage" in data
    assert data["federation"]["ok"] is True
    assert data["federation"]["capabilities"][0]["capability_id"] == "gaia.fire.read@v1"


@pytest.mark.asyncio
async def test_system_prompt_report_sections():
    prompt = ai.build_system_prompt(
        locale="ru",
        live_json='{"stations":[]}',
        report=True,
    )
    assert "ATLAS SNAPSHOT" in prompt
    assert "Отвечай на русском" in prompt or "русском" in prompt
    assert "LANGUAGE:" in prompt
    assert "Overview" in prompt or "situation report" in prompt.lower()
    assert "ATLAS_SNAPSHOT_BEGIN" in prompt
    assert "mode=live" in prompt or "SIM" in prompt
    assert "AIMarket Hub" in prompt or "AIMarket" in prompt
    assert "GAIA" in prompt
    assert "ARGUS" in prompt
    assert "ECOSYSTEM BRIEF" in prompt or "ecosystem" in prompt.lower()
    assert "SCOPE LOCK" in prompt
    assert "STRICTLY scoped" in prompt
    assert "CROSS-LAYER" in prompt
    assert "FEDERATION" in prompt
    assert "correlate" in prompt.lower() or "layer_coverage" in prompt


def test_ecosystem_brief_covers_core_products():
    brief = ai.ecosystem_brief()
    for needle in ("AI-Factory", "Hub", "GAIA", "ATLAS", "ARGUS", "Metis", "SKOPOS", "ACEX"):
        assert needle in brief


@pytest.mark.asyncio
async def test_ask_rejects_off_topic(aggregator: Aggregator, monkeypatch):
    monkeypatch.setattr(ai, "aggregator", aggregator)
    monkeypatch.setattr(ai, "any_provider_configured", lambda: True)

    async def boom(**kwargs):
        raise AssertionError("LLM must not be called for out-of-scope")

    monkeypatch.setattr(ai, "generate_answer", boom)
    out = await ai.ask(question="Write me a poem about cats please", locale="en")
    assert out["meta"].get("firewall") == "topic_scope"
    assert "sensor" in out["answer"].lower() or "ecosystem" in out["answer"].lower()


@pytest.mark.asyncio
async def test_ask_offline_emits_map_actions(aggregator: Aggregator, monkeypatch):
    monkeypatch.setattr(ai, "aggregator", aggregator)
    monkeypatch.setattr(ai, "any_provider_configured", lambda: False)
    out = await ai.ask(question="Show Berlin weather on the map", locale="en")
    assert out["meta"]["offline"] is True
    assert out["actions"]
    assert any(a["type"] == "fly_to" for a in out["actions"])
    assert any(a.get("station_id") == "om-wx-01" for a in out["actions"])


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

    from atlas import llm_providers as llm

    llm.reset_config_cache()
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


@pytest.mark.asyncio
async def test_generate_answer_anthropic(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"content": [{"type": "text", "text": "Claude sees 21.5 °C."}]}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            assert url.endswith("/messages")
            assert headers.get("anthropic-version")
            assert json["model"].startswith("claude")
            return FakeResp()

    from atlas import llm_providers as llm

    llm.reset_config_cache()
    monkeypatch.setattr(llm.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        llm,
        "load_providers_config",
        lambda: {
            "default_provider": "anthropic_cloud",
            "providers": {
                "anthropic_cloud": {
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "api_key": "sk-ant-test",
                    "base_url": "https://api.anthropic.com/v1",
                    "models": {"heavy": "claude-3-5-sonnet-latest", "light": "claude-3-5-haiku-latest"},
                    "provider_type": "anthropic",
                    "capabilities": {"max_tokens": 1024},
                }
            },
        },
    )
    text, meta = await ai.generate_answer(
        question="Temperature?",
        locale="en",
        system_prompt="You are ATLAS.",
        provider_id="anthropic_cloud",
        model_role="heavy",
    )
    assert "21.5" in text
    assert meta["provider_type"] == "anthropic"


@pytest.mark.asyncio
async def test_generate_answer_ollama_native(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"role": "assistant", "content": "Ollama: 21.5 °C"}}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            assert url.endswith("/api/chat")
            assert json["messages"][0]["role"] == "system"
            return FakeResp()

    from atlas import llm_providers as llm

    llm.reset_config_cache()
    monkeypatch.setattr(llm.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        llm,
        "load_providers_config",
        lambda: {
            "default_provider": "local_ollama",
            "providers": {
                "local_ollama": {
                    "api_key_env": None,
                    "base_url": "http://127.0.0.1:11434",
                    "models": {"heavy": "qwen2.5:14b", "light": "qwen2.5:7b"},
                    "provider_type": "local_ollama",
                    "capabilities": {"max_tokens": 1024},
                }
            },
        },
    )
    text, meta = await ai.generate_answer(
        question="Temperature?",
        locale="en",
        system_prompt="You are ATLAS.",
        provider_id="local_ollama",
    )
    assert "Ollama" in text
    assert meta["provider"] == "local_ollama"


@pytest.mark.asyncio
async def test_generate_answer_lm_studio_no_key(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "LM Studio ok"}}]}

    seen = {}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, headers=None, json=None):
            seen["auth"] = headers.get("Authorization")
            assert "chat/completions" in url
            return FakeResp()

    from atlas import llm_providers as llm

    llm.reset_config_cache()
    monkeypatch.setattr(llm.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        llm,
        "load_providers_config",
        lambda: {
            "default_provider": "lm_studio",
            "providers": {
                "lm_studio": {
                    "api_key_env": None,
                    "base_url": "http://127.0.0.1:1234/v1",
                    "models": {"heavy": "local-model", "light": "local-model"},
                    "provider_type": "openai_compatible",
                    "capabilities": {"max_tokens": 1024},
                }
            },
        },
    )
    text, meta = await ai.generate_answer(
        question="Hi",
        locale="en",
        system_prompt="You are ATLAS.",
        provider_id="lm_studio",
    )
    assert text == "LM Studio ok"
    assert seen.get("auth") is None
    assert meta["provider"] == "lm_studio"


def test_list_providers_includes_locals(monkeypatch):
    """Locals are listed, but NOT 'available' until the local opt-in is set."""
    from atlas import llm_providers as llm

    llm.reset_config_cache()
    monkeypatch.delenv("ATLAS_LOCAL_LLM_ENABLED", raising=False)
    monkeypatch.setattr(llm, "load_providers_config", llm.builtin_config)
    listed = llm.list_providers()
    ids = {p["id"] for p in listed["providers"]}
    assert "deepseek_api" in ids
    assert "anthropic_cloud" in ids
    assert "local_ollama" in ids
    assert "lm_studio" in ids
    ollama = next(p for p in listed["providers"] if p["id"] == "local_ollama")
    assert ollama["provider_type"] == "local_ollama"
    # Claiming a localhost backend on a server that has none is what killed the
    # offline stub and turned keyless deploys into HTTP 500s.
    assert ollama["available"] is False
    lm = next(p for p in listed["providers"] if p["id"] == "lm_studio")
    assert lm["available"] is False
    anth = next(p for p in listed["providers"] if p["id"] == "anthropic_cloud")
    assert anth["available"] is False  # no ANTHROPIC_API_KEY in test env


def test_local_providers_available_with_opt_in(monkeypatch):
    from atlas import llm_providers as llm

    llm.reset_config_cache()
    monkeypatch.setenv("ATLAS_LOCAL_LLM_ENABLED", "1")
    monkeypatch.setattr(llm, "load_providers_config", llm.builtin_config)
    listed = llm.list_providers()
    ollama = next(p for p in listed["providers"] if p["id"] == "local_ollama")
    lm = next(p for p in listed["providers"] if p["id"] == "lm_studio")
    assert ollama["available"] is True
    assert lm["available"] is True
    assert llm.any_provider_configured() is True


def test_no_provider_configured_without_keys_or_locals(monkeypatch):
    """The offline cache stub must be reachable on a keyless deployment."""
    from atlas import llm_providers as llm

    llm.reset_config_cache()
    monkeypatch.delenv("ATLAS_LOCAL_LLM_ENABLED", raising=False)
    for env in ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(llm, "load_providers_config", llm.builtin_config)
    assert llm.any_provider_configured() is False
