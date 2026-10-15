"""Federation Hub slice + Analyst fire-pin prompt capping."""

from __future__ import annotations

import json

from atlas.ai_assistant import _select_stations_for_prompt
from atlas.federation_context import _compact_tool, clear_federation_cache, federation_slice


def test_compact_tool_strips_schemas():
    row = {
        "capability_id": "gaia.fire.read@v1",
        "description": "x" * 200,
        "input_schema": {"type": "object"},
        "source_hub": "https://iot.modelmarket.dev",
        "source_hub_name": "GAIA",
        "price_per_call_usd": 0.002,
        "trust_score": 0.4514,
    }
    out = _compact_tool(row)
    assert out is not None
    assert out["capability_id"] == "gaia.fire.read@v1"
    assert "input_schema" not in out
    assert len(out["description"]) <= 160
    assert out["price_per_call_usd"] == 0.002


def test_federation_slice_offline_safe(monkeypatch):
    clear_federation_cache()

    def boom(**kwargs):
        raise RuntimeError("no network in unit test")

    monkeypatch.setattr(
        "atlas.federation_context._fetch_federation_slice",
        boom,
    )
    payload = federation_slice(force=True)
    assert payload["ok"] is False
    assert payload["capabilities"] == []
    assert "unreachable" in (payload.get("note") or "").lower() or payload.get("error")


def test_select_stations_caps_fire_hotspots():
    stations = [
        {"id": "om-wx-01", "layer": "weather", "live": True, "values": {"temperature_c": 20}},
        {"id": "firms-fire-01", "layer": "fire", "live": True, "values": {"brightness_k": 400}},
    ]
    for i in range(40):
        stations.append(
            {
                "id": f"firms-hs-{i:04d}",
                "layer": "fire",
                "parent_id": "firms-fire-01",
                "live": True,
                "values": {"brightness_k": 300.0 + i, "latitude": i, "longitude": -i},
            }
        )
    selected, meta = _select_stations_for_prompt(stations, limit=60, fire_limit=10)
    fire_ids = [s["id"] for s in selected if s.get("layer") == "fire"]
    assert "firms-fire-01" in fire_ids
    assert meta["hotspots_total"] == 40
    assert meta["hotspots_in_prompt"] == 10
    hs_ids = {i for i in fire_ids if str(i).startswith("firms-hs-")}
    assert len(hs_ids) == 10
    # Must include the brightest hotspots (390..339), not the dimmest.
    assert "firms-hs-0039" in hs_ids
    assert "firms-hs-0000" not in hs_ids


def test_build_live_context_fire_meta(monkeypatch, aggregator):
    from atlas import ai_assistant as ai

    monkeypatch.setattr(ai, "aggregator", aggregator)
    monkeypatch.setattr(
        ai,
        "federation_slice",
        lambda: {"ok": False, "capabilities": [], "peers": [], "note": "offline"},
    )

    # Inject expanded fire pins into snapshot via store-less override of snapshot().
    base = aggregator.snapshot()
    stations = list(base.get("stations") or [])
    stations.append(
        {
            "id": "firms-fire-01",
            "layer": "fire",
            "live": True,
            "mode": "live",
            "has_reading": True,
            "values": {"brightness_k": 400, "latitude": 1, "longitude": 2},
            "hotspots": [
                {"brightness_k": 400 + i, "confidence": 90, "latitude": i, "longitude": -i}
                for i in range(30)
            ],
        }
    )
    # Re-expand through fleet helper
    from atlas.fleet import expand_fire_hotspots

    expanded = expand_fire_hotspots(stations)

    def fake_snap():
        snap = dict(base)
        snap["stations"] = expanded
        return snap

    monkeypatch.setattr(aggregator, "snapshot", fake_snap)
    data = json.loads(ai.build_live_context(include_federation=True))
    assert data["fire_prompt"]["hotspots_total"] >= 20
    assert data["fire_prompt"]["hotspots_in_prompt"] <= 24
    assert "layer_coverage" in data
