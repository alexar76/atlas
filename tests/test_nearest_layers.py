"""`atlas.nearest.read@v1` and layers that cannot be served right now.

A buyer walking the layer list hit layers with no live source anywhere (soil,
precipitation, …). Each answered "no LIVE readings within 2500 km", which the hub
scores as a provider miss, so the live feed showed ATLAS failing systematically. And the
hub door read whatever the store held, without warming the requested layers.
"""

from __future__ import annotations

import pytest

import atlas.main as main_mod
from atlas.products import nearest_read


def _pin(layer: str, lat: float, lon: float, pid: str, live: bool = True) -> dict:
    return {"id": pid, "layer": layer, "lat": lat, "lon": lon, "live": live,
            "has_reading": live, "values": {"v": 1.0} if live else {}, "place": pid,
            "label": pid, "kind": "station"}


STATIONS = [
    _pin("weather", 52.52, 13.41, "om-wx-berlin"),
    _pin("river", 52.4, 13.0, "river-havel"),
    _pin("soil", 50.0, 10.0, "soil-dark", live=False),
]


def test_a_layer_with_no_live_source_is_named_not_scored_as_a_miss():
    out = nearest_read({"lat": 52.5, "lon": 13.4, "layers": ["soil", "precipitation"]}, STATIONS)
    assert out["ok"] is False
    # "no valid …" is the shape the hub classifies as an incomplete request, which it
    # does not score against the provider — unlike "no LIVE readings within …".
    assert out["refuse_reason"].startswith("no valid layers requested: soil, precipitation")
    assert out["unavailable_layers"] == ["soil", "precipitation"]
    assert out["available_layers"] == ["river", "weather"]


def test_a_mixed_request_serves_the_live_layers_and_lists_the_rest():
    out = nearest_read({"lat": 52.5, "lon": 13.4, "layers": ["soil", "river"]}, STATIONS)
    assert out["ok"] is True
    assert out["layer"] == "river"
    assert out["unavailable_layers"] == ["soil"]
    per = nearest_read({"lat": 52.5, "lon": 13.4, "layers": ["soil", "weather"], "per_layer": True}, STATIONS)
    assert per["ok"] is True and per["unavailable_layers"] == ["soil"]
    assert set(per["nearest_by_layer"]) == {"weather"}


def test_a_coverage_gap_on_a_live_layer_is_still_an_honest_miss():
    out = nearest_read({"lat": -33.9, "lon": 151.2, "layers": ["river"], "max_km": 100}, STATIONS)
    assert out["ok"] is False
    assert "no LIVE readings within" in out["refuse_reason"]


@pytest.mark.asyncio
@pytest.mark.parametrize("door", ["invoke", "product"])
async def test_both_doors_warm_the_requested_layers_first(client, monkeypatch, door):
    warmed: list[set] = []

    async def ensure(layers, *, force=False):
        warmed.append(set(layers))
        return [s for s in STATIONS if s["layer"] in layers]

    monkeypatch.setattr(main_mod.aggregator, "ensure_layer_readings", ensure)
    monkeypatch.setattr(main_mod.aggregator, "product_stations", lambda: list(STATIONS))
    body = {"lat": 52.5, "lon": 13.4, "layers": ["river"]}
    if door == "invoke":
        response = await client.post("/ai-market/v2/invoke",
                                     json={"capability_id": "atlas.nearest.read@v1", "input": body})
    else:
        response = await client.post("/api/v1/products/nearest", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert warmed == [{"river"}]
