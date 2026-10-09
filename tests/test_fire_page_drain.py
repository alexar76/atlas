"""ATLAS drains GAIA FIRMS hotspot pages with idempotent cursor retries."""

from __future__ import annotations

import pytest

from atlas.fleet import _drain_fire_hotspot_pages


@pytest.mark.asyncio
async def test_drain_fire_pages_retries_same_cursor():
    calls: list[str] = []

    async def invoke(capability_id, device_id, *, extra_input=None):
        cursor = (extra_input or {}).get("cursor")
        calls.append(str(cursor))
        # Fail twice on the first resume cursor, then succeed.
        if cursor == "c1" and calls.count("c1") < 3:
            return None
        if cursor == "c1":
            return {
                "reading": {
                    "hotspots": [{"latitude": 2.0, "longitude": 2.0, "brightness_k": 320}],
                    "next_cursor": "c2",
                    "hotspot_total": 3,
                }
            }
        if cursor == "c2":
            return {
                "reading": {
                    "hotspots": [{"latitude": 3.0, "longitude": 3.0, "brightness_k": 310}],
                    "next_cursor": None,
                    "hotspot_total": 3,
                }
            }
        return None

    first = {
        "hotspots": [{"latitude": 1.0, "longitude": 1.0, "brightness_k": 380}],
        "next_cursor": "c1",
        "hotspot_total": 3,
    }
    out = await _drain_fire_hotspot_pages(
        invoke=invoke,
        capability_id="gaia.fire.read@v1",
        device_id="firms-fire-01",
        first_reading=first,
        seed=list(first["hotspots"]),
        max_retries=3,
    )
    assert len(out) == 3
    assert calls.count("c1") == 3  # two failures + success
    assert "c2" in calls
