"""A free station-detail click must not queue an unbounded upstream invoke.

`station_detail`'s dense-pin branches (`argo-wmo-*`, `gnss-station:{euref,ga}:*`) called
`_invoke` on EVERY request: no TTL, no per-device dedup lock, no deadline, outside `_sem`
and outside `max_detached_reads`. They also run regardless of `fresh`, so they never passed
through `_guard_cache_bypass` — the budget this module defines for "the expensive path into
GAIA".

`GaiaClient._pace()` sleeps while HOLDING its FIFO lock at `gaia_requests_per_minute`, while
ATLAS's own limiter admits far more requests per minute per IP. So one anonymous client
repeating a single valid float id could enqueue several times the upstream's whole budget
and put every viewport, every fleet poll and every paid SKU behind that queue.
readings.py already records this failure in prose: "a viewport answered in 6s and the next
one took 199s behind 42 queued strays".
"""

from __future__ import annotations

import asyncio

import pytest

from atlas.aggregator import Aggregator


@pytest.fixture()
def agg():
    a = Aggregator()
    a._loop = asyncio.get_event_loop_policy().new_event_loop()
    return a


def test_a_repeated_read_hits_the_cache_instead_of_the_upstream(agg):
    calls = []

    async def fake_invoke(cap, dev=None, *, extra_input=None):
        calls.append((cap, dev, tuple(sorted((extra_input or {}).items()))))
        return {"reading": {"values": {"t": 1}}}

    agg._invoke = fake_invoke

    async def run():
        for _ in range(25):
            await agg._dense_pin_read("argo:4901234", "gaia.argo.read@v1", "argo-01",
                                      extra_input={"wmo": "4901234"})

    asyncio.run(run())
    assert len(calls) == 1, f"{len(calls)} upstream invokes for one float within the TTL"


def test_simultaneous_readers_of_one_pin_collapse_into_one_invoke(agg):
    calls = []

    async def slow_invoke(cap, dev=None, *, extra_input=None):
        calls.append(cap)
        await asyncio.sleep(0.05)
        return {"reading": {"values": {"t": 1}}}

    agg._invoke = slow_invoke

    async def run():
        await asyncio.gather(*[
            agg._dense_pin_read("argo:1", "gaia.argo.read@v1", "argo-01") for _ in range(12)
        ])

    asyncio.run(run())
    assert len(calls) == 1, f"a dogpile of 12 concurrent readers made {len(calls)} invokes"


def test_different_pins_are_cached_separately(agg):
    calls = []

    async def fake_invoke(cap, dev=None, *, extra_input=None):
        calls.append((extra_input or {}).get("wmo"))
        return {"reading": {"values": {}}}

    agg._invoke = fake_invoke

    async def run():
        for wmo in ("1", "2", "3"):
            await agg._dense_pin_read(f"argo:{wmo}", "gaia.argo.read@v1", "argo-01",
                                      extra_input={"wmo": wmo})

    asyncio.run(run())
    assert calls == ["1", "2", "3"], calls


def test_the_cache_is_bounded(agg):
    async def fake_invoke(cap, dev=None, *, extra_input=None):
        return {"reading": {}}

    agg._invoke = fake_invoke

    async def run():
        for i in range(4600):
            await agg._dense_pin_read(f"argo:{i}", "gaia.argo.read@v1", "argo-01")

    asyncio.run(run())
    assert len(agg._dense_reads) <= 4096, (
        f"the cache holds {len(agg._dense_reads)} entries — one per pin ever asked for"
    )


def test_both_dense_branches_go_through_the_capped_reader():
    """The wiring: a cache nothing calls is not a cache."""
    import inspect

    from atlas import aggregator

    src = inspect.getsource(aggregator.Aggregator.station_detail)
    assert "gaia.argo.read@v1" in src and "gaia.gnss.integrity.read@v1" in src
    for cap in ("gaia.argo.read@v1", "gaia.gnss.integrity.read@v1"):
        before = src[: src.index(cap)]
        call = before[before.rfind("await self.") :]
        assert "_dense_pin_read" in call, f"{cap} still reaches _invoke directly"
