"""A failed USGS cluster read must not crash the routes built on it.

`fleet.fetch_station_reading` raises `RuntimeError("… GAIA read failed")` rather than
fabricating an empty (offline-painting) reading. The water-quality viewport awaited it
bare, so every product that asks for a viewport — the priced situation brief among them —
answered 500 while GAIA was slow. The viewport now answers with its last cluster for that
bbox (marked stale), or with nothing.
"""
from __future__ import annotations

import asyncio

import pytest
from atlas.aggregator import Aggregator

from atlas.config import Settings

BBOX = (-75.0, 40.0, -73.0, 41.0)


def _aggregator(monkeypatch, answers: list) -> tuple[Aggregator, list[str]]:
    agg = Aggregator(Settings(gaia_url="http://127.0.0.1:1", operator_token="t"))
    calls: list[str] = []

    async def fetch(device_id: str) -> dict:
        calls.append(device_id)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(agg, "_fetch_station_reading", fetch)
    return agg, calls


@pytest.mark.asyncio
async def test_a_failed_refresh_serves_the_last_cluster_as_stale(monkeypatch):
    cluster = {"id": "usgs-wq-01", "online": True, "hotspots": [{"id": "s1", "lat": 40.5, "lon": -74.0}]}
    agg, calls = _aggregator(monkeypatch, [cluster, RuntimeError("usgs-wq-01: GAIA read failed")])
    fresh, cached = await agg._water_quality_viewport(BBOX, force=False, deadline_s=None)
    assert fresh["hotspots"] == cluster["hotspots"] and cached is False
    stale, cached = await agg._water_quality_viewport(BBOX, force=True, deadline_s=None)
    assert stale["hotspots"] == cluster["hotspots"] and stale["stale"] is True and cached is True
    # The failure is cached for the TTL like a success: the next viewport does not re-ask.
    again, cached = await agg._water_quality_viewport(BBOX, force=False, deadline_s=None)
    assert again["stale"] is True and cached is True and len(calls) == 2


@pytest.mark.asyncio
async def test_a_first_read_that_fails_answers_nothing_rather_than_raising(monkeypatch):
    agg, _ = _aggregator(monkeypatch, [RuntimeError("usgs-wq-01: GAIA read failed")])
    assert await agg._water_quality_viewport(BBOX, force=False, deadline_s=0.5) == (None, False)
    await asyncio.sleep(0)   # the done-callback retrieves the exception: no loop warning
