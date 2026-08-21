"""A slow upstream must cost the next poll, not this user's viewport.

Measured on prod before this budget existed: one cold Argo directory fetch held
an entire US viewport for 107 seconds, and the detail-panel request queued
behind it surfaced as "Could not load this sensor" in the UI.
"""

from __future__ import annotations

import asyncio

import pytest

from atlas.config import Settings
from atlas.readings import ReadingStore
from atlas.stations import STATION_CATALOG

FAST = "om-wx-01"
SLOW = "argo-01"


def _ids() -> tuple[str, str]:
    assert FAST in STATION_CATALOG and SLOW in STATION_CATALOG
    return FAST, SLOW


@pytest.mark.asyncio
async def test_budget_returns_fast_stations_without_waiting_for_the_slow_one():
    fast, slow = _ids()
    store = ReadingStore(Settings())
    started: list[str] = []

    async def fetch(device_id: str) -> dict:
        started.append(device_id)
        if device_id == slow:
            await asyncio.sleep(5.0)
        return {"id": device_id, "online": True}

    loop = asyncio.get_running_loop()
    t0 = loop.time()
    out = await store.ensure([fast, slow], fetch=fetch, deadline_s=0.2)
    elapsed = loop.time() - t0

    assert elapsed < 1.0, f"viewport waited {elapsed:.2f}s on a slow upstream"
    assert [s["id"] for s in out] == [fast]
    assert set(started) == {fast, slow}, "the slow fetch must still have started"


@pytest.mark.asyncio
async def test_the_straggler_is_not_cancelled_and_lands_in_the_cache():
    """Detach, don't cancel — the work is already paid for upstream."""
    fast, slow = _ids()
    store = ReadingStore(Settings())

    async def fetch(device_id: str) -> dict:
        if device_id == slow:
            await asyncio.sleep(0.3)
        return {"id": device_id, "online": True}

    await store.ensure([fast, slow], fetch=fetch, deadline_s=0.05)
    assert store.get_station(slow) is None, "not cached yet — that is the point"
    assert store.in_flight == 1

    await asyncio.sleep(0.5)
    assert store.get_station(slow) == {"id": slow, "online": True}
    assert store.in_flight == 0, "completed tasks must be released"

    # Next caller is now instant, with no fetch at all.
    calls: list[str] = []

    async def fetch2(device_id: str) -> dict:
        calls.append(device_id)
        return {"id": device_id}

    out = await store.ensure([slow], fetch=fetch2, deadline_s=0.05)
    assert calls == [], "second read should be a cache hit"
    assert [s["id"] for s in out] == [slow]


@pytest.mark.asyncio
async def test_a_pin_already_on_the_map_survives_a_slow_refresh():
    """A refresh that misses the budget must not blank an existing pin."""
    fast, slow = _ids()
    store = ReadingStore(Settings())
    store.put(slow, {"id": slow, "online": True, "lat": 1.0, "lon": 2.0})

    async def fetch(device_id: str) -> dict:
        await asyncio.sleep(5.0)
        return {"id": device_id}

    out = await store.ensure(
        [slow], fetch=fetch, force=True, ttl=0.0, deadline_s=0.1
    )
    served = {s["id"]: s for s in out}
    assert slow in served, "the old value must still be served"
    assert served[slow]["lat"] == 1.0
    assert served[slow]["stale"] is True, "and it must be labelled stale"


@pytest.mark.asyncio
async def test_no_deadline_keeps_the_old_blocking_contract():
    """Background warms still get to wait for everything."""
    fast, _ = _ids()
    store = ReadingStore(Settings())

    async def fetch(device_id: str) -> dict:
        await asyncio.sleep(0.05)
        return {"id": device_id}

    out = await store.ensure([fast], fetch=fetch)
    assert [s["id"] for s in out] == [fast]


@pytest.mark.asyncio
async def test_detached_backlog_is_capped():
    """Strays share GaiaClient's FIFO pacer with interactive traffic.

    Unbounded detaching does not remove the stall, it relocates it: on prod a
    viewport answered in 6s and the NEXT one took 199s queued behind 42 strays.
    """
    settings = Settings()
    settings.max_detached_reads = 3
    store = ReadingStore(settings)
    ids = [d for d in list(STATION_CATALOG)[:10]]

    async def fetch(device_id: str) -> dict:
        await asyncio.sleep(5.0)
        return {"id": device_id}

    await store.ensure(ids, fetch=fetch, deadline_s=0.05)
    assert store.in_flight <= 3, f"backlog {store.in_flight} exceeds the cap"
