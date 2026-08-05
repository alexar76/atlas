"""HTTP API tests (ASGI)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "atlas"
    assert body["ok"] is True


@pytest.mark.asyncio
async def test_snapshot(client):
    r = await client.get("/api/v1/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert "stations" in body
    assert "layers" in body
    assert body["service"] == "atlas"


@pytest.mark.asyncio
async def test_monitor(client):
    r = await client.get("/api/v1/monitor")
    assert r.status_code == 200
    body = r.json()
    assert "embed_url" in body
    assert "map_url" in body


@pytest.mark.asyncio
async def test_viewport_and_station(client):
    r = await client.post(
        "/api/v1/viewport",
        json={"west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "om-wx-01" in body["requested"]

    d = await client.get("/api/v1/stations/om-wx-01")
    assert d.status_code == 200
    detail = d.json()
    assert detail["id"] == "om-wx-01"
    assert detail["metrics"]


@pytest.mark.asyncio
async def test_station_404(client):
    r = await client.get("/api/v1/stations/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_viewport_validation(client):
    r = await client.post(
        "/api/v1/viewport",
        json={"west": 200, "south": 0, "east": 1, "north": 1},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_index_and_embed_html(client):
    idx = await client.get("/")
    emb = await client.get("/embed")
    assert idx.status_code == 200
    assert emb.status_code == 200
    assert "ATLAS" in idx.text
    assert "atlas.js" in idx.text
    assert "assistant.js" in idx.text


@pytest.mark.asyncio
async def test_assets(client):
    css = await client.get("/assets/atlas.css")
    js = await client.get("/assets/atlas.js")
    ai = await client.get("/assets/assistant.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert ai.status_code == 200


@pytest.mark.asyncio
async def test_ai_providers(client):
    r = await client.get("/api/ai/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["default_provider"] == "deepseek_api"
    assert body["default_model"] == "deepseek-v4-pro"
    assert any(p["id"] == "deepseek_api" for p in body["providers"])


@pytest.mark.asyncio
async def test_ai_ask_offline_stub(client, monkeypatch):
    import app.ai_assistant as ai

    monkeypatch.setattr(ai, "any_provider_configured", lambda: False)
    r = await client.post(
        "/api/ai/ask",
        json={
            "question": "Составь отчёт по датчикам",
            "locale": "ru",
            "report": True,
            "bbox": {"west": 12.5, "south": 52.3, "east": 14.0, "north": 52.7},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["offline"] is True
    assert body["meta"]["report"] is True
    assert "ATLAS" in body["answer"] or "датчик" in body["answer"].lower() or "station" in body["answer"].lower()


@pytest.mark.asyncio
async def test_ai_ask_empty_rejected(client):
    r = await client.post("/api/ai/ask", json={"question": ""})
    assert r.status_code == 422
