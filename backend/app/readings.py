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
        self.entries[device_id] = {
            "station": station,
            "fetched_at": time.monotonic(),
        }

    async def ensure(
        self,
        device_ids: list[str],
        *,
        fetch: FetchFn,
        force: bool = False,
        ttl: float | None = None,
    ) -> list[dict[str, Any]]:
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

        results = await asyncio.gather(*[one(did) for did in device_ids])
        for item in results:
            if isinstance(item, dict):
                out.append(item)
        return out
