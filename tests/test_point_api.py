"""Exact ATLAS map objects are first-class agent-addressable capabilities."""

from __future__ import annotations

import pytest

import atlas.main as main_mod
from atlas.main import RateLimiter


@pytest.mark.asyncio
async def test_point_capability_reads_same_catalog_object_as_map(client):
    response = await client.post(
        "/ai-market/v2/invoke",
        json={
            "capability_id": "atlas.point.read@v1",
            "input": {"point_id": "om-wx-01", "fresh": True},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["point_id"] == "om-wx-01"
    assert body["point"]["id"] == "om-wx-01"
    assert body["parent_capability"]["capability_id"] == "gaia.weather.read@v1"
    assert body["receipt"]["digest"]


@pytest.mark.asyncio
async def test_point_capability_fails_closed_for_unknown_object(client):
    response = await client.post(
        "/ai-market/v2/invoke",
        json={
            "capability_id": "atlas.point.read@v1",
            "input": {"point_id": "no-such-point"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "not found" in body["refuse_reason"]


@pytest.mark.asyncio
async def test_point_convenience_endpoint_uses_same_contract(client):
    response = await client.post(
        "/api/v1/products/point",
        json={"point_id": "om-wx-01", "fresh": False},
    )
    assert response.status_code == 200
    assert response.json()["sku"] == "atlas.point.read@v1"


@pytest.mark.asyncio
async def test_forced_point_reads_use_cache_bypass_budget(client, monkeypatch):
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(1))
    payload = {
        "capability_id": "atlas.point.read@v1",
        "input": {"point_id": "om-wx-01", "fresh": True},
    }

    first = await client.post("/ai-market/v2/invoke", json=payload)
    second = await client.post("/ai-market/v2/invoke", json=payload)

    assert first.status_code == 200
    assert second.status_code == 429
    assert "budget" in second.json()["detail"]
