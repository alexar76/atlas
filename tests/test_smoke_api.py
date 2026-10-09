"""The smoke brief over the wire: hub invoke, REST twin, and what stays free.

The handler and its schema existed for a while with no route and no dispatch
entry, so the manifest advertised a SKU that answered "unhandled capability".
These tests buy it the way a customer does.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import atlas.main as main_mod

# Inside the conftest HMS plume; ~900 km from its centroid.
ASSET_IN_SMOKE = {"lat": 37.7749, "lon": -122.4194, "asset_id": "yard-7"}
ASSET_CLEAR = {"lat": 25.7617, "lon": -80.1918, "asset_id": "miami-dock"}


async def _invoke(client, payload: dict[str, Any]):
    return await client.post(
        "/ai-market/v2/invoke",
        json={"capability_id": "atlas.smoke.operations@v1", "input": payload},
    )


@pytest.mark.asyncio
async def test_hub_invoke_answers_containment_not_centroid_distance(client):
    response = await _invoke(client, ASSET_IN_SMOKE)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True, body.get("refuse_reason")
    assert body["inside_smoke"] is True
    assert body["operational_status"] == "action"
    assert body["hms_inventory_complete"] is True
    assert body["smoke"][0]["polygon_id"] == "hms-testplume"
    assert body["smoke"][0]["geometry"]["type"] == "Polygon"
    assert body["smoke"][0]["gaia_attestation"]["value"] == "smoke-sig"
    # The colocated air read was actually performed at the asset coordinate.
    assert body["air_quality"]["values"]["pm2_5_ugm3"] == 41.0
    assert body["air_quality"]["lat"] == ASSET_IN_SMOKE["lat"]
    assert body["receipt"]["digest"]


@pytest.mark.asyncio
async def test_hub_invoke_answers_outside_for_a_clear_asset(client):
    body = (await _invoke(client, ASSET_CLEAR)).json()
    assert body["ok"] is True
    assert body["inside_smoke"] is False
    assert body["smoke"] == []
    # Real HMS coverage is North America only; a clear asset still gets its air,
    # and unhealthy air alone is "elevated" — never the in-smoke "action".
    assert body["air_quality"]["values"]["us_aqi"] == 115.0
    assert body["operational_status"] == "elevated"


@pytest.mark.asyncio
async def test_rest_twin_returns_the_same_sku(client):
    response = await client.post("/api/v1/products/smoke-operations", json=ASSET_IN_SMOKE)
    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "atlas.smoke.operations@v1"
    assert body["inside_smoke"] is True


@pytest.mark.asyncio
async def test_rest_twin_rejects_impossible_coordinates(client):
    response = await client.post("/api/v1/products/smoke-operations", json={"lat": 91, "lon": 0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_failing_air_read_refuses_instead_of_answering_from_smoke_alone(
    client, monkeypatch
):
    async def boom(latitude: float, longitude: float):
        raise RuntimeError("open-meteo licence endpoint unreachable")

    monkeypatch.setattr(main_mod.aggregator, "coordinate_air_reading", boom)
    body = (await _invoke(client, ASSET_IN_SMOKE)).json()
    assert body["ok"] is False
    assert "PM2.5/AQI" in body["refuse_reason"]


@pytest.mark.asyncio
async def test_a_failing_hms_read_refuses_instead_of_answering_outside(client, monkeypatch):
    async def boom(layers, *, force: bool = False):
        raise RuntimeError("GAIA smoke relay down")

    monkeypatch.setattr(main_mod.aggregator, "ensure_layer_readings", boom)
    body = (await _invoke(client, ASSET_IN_SMOKE)).json()
    assert body["ok"] is False
    assert "complete LIVE HMS polygon inventory" in body["refuse_reason"]


@pytest.mark.asyncio
async def test_a_sim_air_relay_is_not_sold_as_evidence(client, aggregator):
    """"LIVE only with provenance source" holds inside the paid brief too."""
    aggregator._fleet_by_id["om-aq-01"] = {
        **aggregator._fleet_by_id.get("om-aq-01", {}), "source": None,
    }
    assert await aggregator.coordinate_air_reading(37.7749, -122.4194) is None

    body = (await _invoke(client, ASSET_IN_SMOKE)).json()
    assert body["ok"] is False
    assert "PM2.5/AQI" in body["refuse_reason"]


@pytest.mark.asyncio
async def test_the_map_viewport_never_ships_polygon_geometry(client):
    response = await client.post(
        "/api/v1/viewport", json={"west": -130, "south": 30, "east": -95, "north": 50}
    )
    assert response.status_code == 200
    points = [
        point for point in response.json().get("map_points") or []
        if str(point.get("layer")) == "smoke"
    ]
    assert points, "the smoke layer did not reach the viewport at all"
    for point in points:
        assert "geometry" not in point
        assert point["geometry_digest"] == "e" * 64
        assert point["bbox"] == [-125.0, 35.0, -100.0, 45.0]


@pytest.mark.asyncio
async def test_the_free_point_read_stays_free_of_the_paid_geometry(client):
    """Regression: the product path indexed its private pins for free lookups."""
    paid = (await _invoke(client, ASSET_IN_SMOKE)).json()
    assert paid["ok"] is True  # this is what populated the point registry

    pin_id = "smoke-poly-hms-testplume"
    detail = await client.get(f"/api/v1/stations/{pin_id}")
    assert detail.status_code == 200
    # `geometry_type`/`geometry_digest` are public provenance; the ring is not.
    assert '"geometry":' not in json.dumps(detail.json())
    assert "coordinates" not in json.dumps(detail.json())

    point = await client.post("/api/v1/products/point", json={"point_id": pin_id})
    assert point.status_code == 200
    assert '"geometry":' not in json.dumps(point.json())
    assert "coordinates" not in json.dumps(point.json())
