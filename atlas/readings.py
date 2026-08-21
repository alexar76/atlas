"""Per-station reading cache with TTL + single-flight locks."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .config import Settings
from .stations import STATION_CATALOG

log = logging.getLogger("atlas.readings")

FetchFn = Callable[[str], Awaitable[dict[str, Any]]]


class ReadingStore:
    """Shared reading cache: one GAIA fetch per device under concurrency."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.entries: dict[str, dict[str, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.rev: int = 0
        # Fetches that outran a caller's deadline keep running and land in the
        # cache; we hold references so the loop cannot garbage-collect them
        # mid-flight. Discarded on completion — this never grows unbounded.
        self._detached: set[asyncio.Task[Any]] = set()

    @property
    def in_flight(self) -> int:
        """Fetches still running after their caller gave up waiting."""
        return len(self._detached)

    def lock_for(self, device_id: str) -> asyncio.Lock:
        lock = self._locks.get(device_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[device_id] = lock
        return lock

    def age(self, device_id: str) -> float | None:
        entry = self.entries.get(device_id)
        if not entry:
            return None
        return time.monotonic() - float(entry["fetched_at"])

    def get_station(self, device_id: str) -> dict[str, Any] | None:
        entry = self.entries.get(device_id)
        station = entry.get("station") if entry else None
        return dict(station) if isinstance(station, dict) else None

    def put(self, device_id: str, station: dict[str, Any]) -> None:
        prev = self.entries.get(device_id, {}).get("station")
        merged = dict(station)
        # Count-only / failed densify must not wipe a good viewport cluster.
        if (
            isinstance(prev, dict)
            and "hotspots" not in station
            and isinstance(prev.get("hotspots"), list)
            and prev["hotspots"]
        ):
            merged["hotspots"] = prev["hotspots"]
            merged["hotspot_count"] = prev.get("hotspot_count", len(prev["hotspots"]))
        # A transient upstream failure returns an empty parent pin.  Keep the
        # last known aggregate count (but not the online flag) so the sidebar
        # can label it as stale instead of fabricating a catalog-row count of 1.
        authoritative_count = any(
            key in station
            for key in ("hotspots", "hotspot_count", "hotspot_matched", "inventory_total")
        )
        if isinstance(prev, dict) and not authoritative_count:
            for key in ("hotspot_count", "hotspot_matched", "inventory_total"):
                if key in prev:
                    merged[key] = prev[key]
        self.entries[device_id] = {
            "station": merged,
            "fetched_at": time.monotonic(),
        }
        self.rev += 1

    async def ensure(
        self,
        device_ids: list[str],
        *,
        fetch: FetchFn,
        force: bool = False,
        ttl: float | None = None,
        deadline_s: float | None = None,
    ) -> list[dict[str, Any]]:
        """Cached readings for ``device_ids``.

        With ``deadline_s`` this returns whatever is ready when the budget runs
        out instead of waiting for the slowest upstream. Stragglers are NOT
        cancelled — they keep their single-flight lock, finish in the
        background, and land in the cache for the next caller. One cold Argo
        directory therefore costs the next poll, not this user's viewport.
        """
        ttl = self.settings.reading_ttl_s if ttl is None else ttl
        out: list[dict[str, Any]] = []

        async def one(device_id: str) -> dict[str, Any] | None:
            if device_id not in STATION_CATALOG:
                return None
            age = self.age(device_id)
            if not force and age is not None and age < ttl:
                return self.get_station(device_id)

            async with self.lock_for(device_id):
                age = self.age(device_id)
                if not force and age is not None and age < ttl:
                    return self.get_station(device_id)
                try:
                    station = await fetch(device_id)
                except Exception:
                    log.debug("read %s failed", device_id, exc_info=True)
                    return self.get_station(device_id)
                self.put(device_id, station)
                return dict(station)

        if not deadline_s or deadline_s <= 0:
            results = await asyncio.gather(*[one(did) for did in device_ids])
            for item in results:
                if isinstance(item, dict):
                    out.append(item)
            return out

        tasks = {
            asyncio.ensure_future(one(did)): did for did in device_ids
        }
        if not tasks:
            return out
        done, pending = await asyncio.wait(tasks, timeout=deadline_s)
        for task in done:
            try:
                item = task.result()
            except Exception:
                log.debug("read %s failed", tasks[task], exc_info=True)
                item = self.get_station(tasks[task])
            if isinstance(item, dict):
                out.append(item)
        max_detached = max(0, int(getattr(self.settings, "max_detached_reads", 8)))
        for task in pending:
            # Detach, do not cancel: the work is already paid for upstream and
            # the cache entry it writes is what makes the next request fast.
            #
            # But only up to a cap. GaiaClient paces every request start through
            # one FIFO lock at gaia_requests_per_minute, so detached work sits in
            # the SAME queue as interactive traffic. Unbounded detaching moved the
            # stall out of the response and into the pacer: a viewport answered in
            # 6s and the next one took 199s behind 42 queued strays. Past the cap,
            # cancel and let the fleet poll warm it at its own pace.
            if len(self._detached) < max_detached:
                self._detached.add(task)
                task.add_done_callback(self._detached.discard)
            else:
                task.cancel()
            stale = self.get_station(tasks[task])
            if isinstance(stale, dict):
                # Serve the previous value rather than dropping the pin off the
                # map while its refresh is still in flight.
                stale["stale"] = True
                out.append(stale)
        if pending:
            log.info(
                "viewport budget %.1fs: served %d, %d still fetching (%s)",
                deadline_s, len(done), len(pending),
                ", ".join(sorted(tasks[t] for t in pending)[:6]),
            )
        return out
