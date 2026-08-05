"""Aggregator: fleet pins, TTL cache, viewport, detail."""

from __future__ import annotations

import asyncio

import pytest

from app.aggregator import Aggregator


@pytest.mark.asyncio
async def test_fleet_snapshot_has_pins(aggregator: Aggregator):
    snap = aggregator.snapshot()
    assert snap["status"] == "ok"
    assert snap["summary"]["stations"] >= 7
    ids = {s["id"] for s in snap["stations"]}
    assert "om-wx-01" in ids
    assert "usgs-quake-01" in ids


@pytest.mark.asyncio
async def test_viewport_berlin_fetches_readings(aggregator: Aggregator):
    result = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7, force=False
    )
    assert result["ok"] is True
    assert "om-wx-01" in result["requested"]
    by_id = {s["id"]: s for s in result["stations"]}
    assert by_id["om-wx-01"]["values"]["temperature_c"] == 21.5
    assert by_id["om-wx-01"]["has_reading"] is True


@pytest.mark.asyncio
async def test_viewport_second_call_is_cache_hit(aggregator: Aggregator):
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    second = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7
    )
    assert second["cache_hits"] >= 1
    assert second["cache_hits"] == len(second["requested"])


@pytest.mark.asyncio
async def test_viewport_force_bypasses_cache(aggregator: Aggregator):
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    forced = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7, force=True
    )
    assert forced["cache_hits"] == 0


@pytest.mark.asyncio
async def test_station_detail_human_readable(aggregator: Aggregator):
    detail = await aggregator.station_detail("om-wx-01")
    assert detail["id"] == "om-wx-01"
    assert "Berlin" in (detail.get("summary") or "")
    assert detail["metrics"]
    assert any(m["label"] == "Temperature" for m in detail["metrics"])


@pytest.mark.asyncio
async def test_station_detail_unknown(aggregator: Aggregator):
    with pytest.raises(KeyError):
        await aggregator.station_detail("no-such-device")


@pytest.mark.asyncio
async def test_quake_updates_coords_and_trail(aggregator: Aggregator):
    await aggregator._ensure_readings(["usgs-quake-01"], force=True)
    station = aggregator._readings["usgs-quake-01"]["station"]
    assert abs(station["lat"] - 35.1) < 0.01
    assert abs(station["lon"] - (-118.2)) < 0.01
    assert aggregator._quake_trail
    assert aggregator._quake_trail[-1]["magnitude"] == 4.8


@pytest.mark.asyncio
async def test_single_flight_concurrent_reads(aggregator: Aggregator):
    # Clear cache so both waiters share one fetch (force=False + TTL).
    aggregator._readings.pop("nws-01", None)
    calls = {"n": 0}
    real_fetch = aggregator._fetch_station_reading

    async def counting_fetch(device_id: str):
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return await real_fetch(device_id)

    aggregator._fetch_station_reading = counting_fetch  # type: ignore[method-assign]
    a, b = await asyncio.gather(
        aggregator._ensure_readings(["nws-01"], force=False),
        aggregator._ensure_readings(["nws-01"], force=False),
    )
    assert a and b
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_monitor_payload_shape(aggregator: Aggregator):
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    payload = aggregator.monitor_payload()
    assert payload["service"] == "atlas"
    assert payload["embed_url"].endswith("/embed")
    assert payload["station_count"] >= 1
    assert isinstance(payload["stations"], list)


@pytest.mark.asyncio
async def test_health_ok(aggregator: Aggregator):
    h = aggregator.health()
    assert h["ok"] is True
    assert h["service"] == "atlas"
    assert h["stations"] >= 1
