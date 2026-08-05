"""Fleet pins + viewport orchestration over GAIA (composes geo / client / readings / fleet)."""

from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from typing import Any

from . import __version__
from .config import Settings, get_settings
from .formatters import build_detail
from .gaia_client import GaiaClient
from .geo import in_bbox, station_ids_in_bbox, utc_now
from . import fleet as fleet_mod
from .readings import ReadingStore
from .stations import LAYER_META, STATION_CATALOG

log = logging.getLogger("atlas.aggregator")

# Back-compat for tests that import ``_in_bbox`` from this module.
_in_bbox = in_bbox


class Aggregator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._fleet_lock = asyncio.Lock()
        self._snapshot: dict[str, Any] = self._empty_snapshot(status="starting")
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._gaia = GaiaClient(self.settings)
        self._store = ReadingStore(self.settings)
        self._poll_count = 0
        self._poll_errors = 0
        self._last_ok_at: float | None = None
        self._quake_trail: list[dict[str, Any]] = []
        self._fleet_by_id: dict[str, dict[str, Any]] = {}
        self._sem = asyncio.Semaphore(self.settings.gaia_concurrency)

    # ── test / legacy aliases ──────────────────────────────────────────────
    @property
    def _client(self) -> Any:
        return self._gaia.raw

    @_client.setter
    def _client(self, value: Any) -> None:
        self._gaia.raw = value

    @property
    def _readings(self) -> dict[str, dict[str, Any]]:
        return self._store.entries

    @_readings.setter
    def _readings(self, value: dict[str, dict[str, Any]]) -> None:
        self._store.entries = value

    def _cache_age(self, device_id: str) -> float | None:
        return self._store.age(device_id)

    def _empty_snapshot(self, *, status: str) -> dict[str, Any]:
        return {
            "service": "atlas",
            "version": __version__,
            "status": status,
            "generated_at": utc_now(),
            "age_ms": 0,
            "stale": False,
            "gaia_url": self.settings.gaia_url.rstrip("/"),
            "layers": LAYER_META,
            "stations": [],
            "quakes": [],
            "summary": {
                "stations": 0,
                "online": 0,
                "layers": 0,
                "quakes": 0,
                "cached_readings": 0,
            },
        }

    async def start(self) -> None:
        if self._task:
            return
        await self._gaia.open()
        interval = self.settings.fleet_poll_interval_s or self.settings.poll_interval_s
        self._task = asyncio.create_task(self._fleet_loop(interval), name="atlas-fleet")
        log.info("aggregator started → %s (fleet every %.0fs)", self.settings.gaia_url, interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._gaia.close()

    def snapshot(self) -> dict[str, Any]:
        snap = deepcopy(self._snapshot)
        by_id = {s["id"]: s for s in snap.get("stations") or [] if isinstance(s, dict)}
        for device_id, entry in self._store.entries.items():
            station = entry.get("station")
            if not isinstance(station, dict):
                continue
            pin = by_id.get(device_id)
            age_ms = int((time.monotonic() - entry["fetched_at"]) * 1000)
            if pin:
                pin.update(
                    {
                        "values": station.get("values") or {},
                        "headline": station.get("headline"),
                        "online": station.get("online", pin.get("online")),
                        "lat": station.get("lat", pin.get("lat")),
                        "lon": station.get("lon", pin.get("lon")),
                        "reading_age_ms": age_ms,
                        "has_reading": bool(station.get("values")),
                    }
                )
            else:
                enriched = dict(station)
                enriched["reading_age_ms"] = age_ms
                enriched["has_reading"] = bool(station.get("values"))
                snap.setdefault("stations", []).append(enriched)
        generated = snap.get("_monotonic")
        now = time.monotonic()
        if isinstance(generated, (int, float)):
            age_ms = int((now - generated) * 1000)
            snap["age_ms"] = max(0, age_ms)
            snap["stale"] = age_ms > int(self.settings.stale_after_s * 1000)
        snap.pop("_monotonic", None)
        summary = snap.setdefault("summary", {})
        stations = snap.get("stations") or []
        summary["stations"] = len(stations)
        summary["online"] = sum(1 for s in stations if s.get("online"))
        summary["layers"] = len({s.get("layer") for s in stations if s.get("layer")})
        summary["quakes"] = len(snap.get("quakes") or [])
        summary["cached_readings"] = sum(1 for s in stations if s.get("has_reading"))
        return snap

    def monitor_payload(self) -> dict[str, Any]:
        snap = self.snapshot()
        stations = snap.get("stations") or []
        return {
            "version": __version__,
            "service": "atlas",
            "status": snap.get("status"),
            "stale": snap.get("stale"),
            "generated_at": snap.get("generated_at"),
            "age_ms": snap.get("age_ms"),
            "station_count": len(stations),
            "online": sum(1 for s in stations if s.get("online")),
            "layers": sorted({s.get("layer") for s in stations if s.get("layer")}),
            "quake_count": len(snap.get("quakes") or []),
            "embed_url": f"{self.settings.public_url.rstrip('/')}/embed",
            "map_url": self.settings.public_url.rstrip("/"),
            "stations": [
                {
                    "id": s.get("id"),
                    "layer": s.get("layer"),
                    "label": s.get("label"),
                    "place": s.get("place"),
                    "online": s.get("online"),
                    "lat": s.get("lat"),
                    "lon": s.get("lon"),
                    "headline": s.get("headline") or "—",
                    "values": s.get("values") or {},
                    "has_reading": bool(s.get("has_reading")),
                }
                for s in stations[:16]
            ],
            "quakes": (snap.get("quakes") or [])[:8],
        }

    def health(self) -> dict[str, Any]:
        snap = self.snapshot()
        return {
            "ok": snap.get("status") in {"ok", "degraded", "starting"},
            "service": "atlas",
            "version": __version__,
            "status": snap.get("status"),
            "stale": snap.get("stale"),
            "poll_count": self._poll_count,
            "poll_errors": self._poll_errors,
            "subscribers": len(self._subscribers),
            "stations": snap.get("summary", {}).get("stations", 0),
            "cached_readings": snap.get("summary", {}).get("cached_readings", 0),
            "gaia": self.settings.gaia_url.rstrip("/"),
        }

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2)
        self._subscribers.add(q)
        try:
            q.put_nowait(self.snapshot())
        except asyncio.QueueFull:
            pass
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def _publish(self) -> None:
        snap = self.snapshot()
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                if q.full():
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                q.put_nowait(snap)
            except Exception:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    async def _fleet_loop(self, interval: float) -> None:
        while True:
            try:
                await self.refresh_fleet()
            except Exception:
                self._poll_errors += 1
                log.exception("fleet poll failed")
            await asyncio.sleep(interval)

    async def refresh(self) -> dict[str, Any]:
        await self.refresh_fleet()
        ids = list(self._store.entries.keys())
        if ids:
            await self._ensure_readings(ids, force=True)
        await self._publish()
        return self.snapshot()

    async def refresh_fleet(self) -> dict[str, Any]:
        async with self._fleet_lock:
            snap = await self._build_fleet_snapshot()
            self._snapshot = snap
            self._poll_count += 1
            await self._publish()
            return self.snapshot()

    async def _invoke(self, capability_id: str, device_id: str | None = None) -> dict[str, Any] | None:
        """Delegates to GaiaClient; kept patchable for tests."""
        return await self._gaia.invoke(capability_id, device_id)

    def _pin_from_catalog(self, device_id: str, fleet_dev: dict[str, Any] | None = None) -> dict[str, Any]:
        return fleet_mod.pin_from_catalog(
            device_id,
            fleet_dev=fleet_dev or self._fleet_by_id.get(device_id),
            cached=self._store.get_station(device_id),
        )

    def _remember_quake(self, station: dict[str, Any]) -> None:
        self._quake_trail = fleet_mod.remember_quake(
            self._quake_trail,
            station,
            history=self.settings.quake_history,
        )

    async def _build_fleet_snapshot(self) -> dict[str, Any]:
        fleet = await self._invoke("gaia.fleet.status@v1")
        devices_by_id = fleet_mod.parse_fleet_devices(fleet if isinstance(fleet, dict) else None)
        self._fleet_by_id = devices_by_id
        wanted_ids = fleet_mod.wanted_station_ids(devices_by_id)
        stations = [self._pin_from_catalog(did, devices_by_id.get(did)) for did in wanted_ids]

        if "usgs-quake-01" in wanted_ids:
            try:
                await self._ensure_readings(["usgs-quake-01"], force=False)
                q = self._store.get_station("usgs-quake-01")
                if isinstance(q, dict):
                    for i, s in enumerate(stations):
                        if s["id"] == "usgs-quake-01":
                            stations[i] = {
                                **s,
                                **{
                                    k: q[k]
                                    for k in ("lat", "lon", "values", "headline", "online", "has_reading")
                                    if k in q
                                },
                            }
                            self._remember_quake(q)
                            break
            except Exception:
                log.debug("quake pin refresh skipped", exc_info=True)

        snap = fleet_mod.assemble_fleet_snapshot(
            stations=stations,
            quake_trail=self._quake_trail,
            gaia_url=self.settings.gaia_url,
        )
        if snap["status"] == "ok":
            self._last_ok_at = time.monotonic()
        return snap

    async def _fetch_station_reading(self, device_id: str) -> dict[str, Any]:
        async with self._sem:
            return await fleet_mod.fetch_station_reading(
                device_id,
                fleet_by_id=self._fleet_by_id,
                invoke=self._invoke,
                on_quake=self._remember_quake,
            )

    async def _ensure_readings(
        self, device_ids: list[str], *, force: bool = False, ttl: float | None = None
    ) -> list[dict[str, Any]]:
        return await self._store.ensure(
            device_ids,
            fetch=self._fetch_station_reading,
            force=force,
            ttl=ttl,
        )

    def stations_in_bbox(self, west: float, south: float, east: float, north: float) -> list[str]:
        return station_ids_in_bbox(self._snapshot.get("stations") or [], west, south, east, north)

    async def refresh_viewport(
        self,
        *,
        west: float,
        south: float,
        east: float,
        north: float,
        force: bool = False,
    ) -> dict[str, Any]:
        if not (self._snapshot.get("stations") or []):
            await self.refresh_fleet()
        ids = self.stations_in_bbox(west, south, east, north)
        ttl = self.settings.reading_ttl_s
        cache_hits = sum(
            1
            for did in ids
            if not force and (age := self._cache_age(did)) is not None and age < ttl
        )
        stations = await self._ensure_readings(ids, force=force)
        await self._publish()
        return {
            "ok": True,
            "bbox": {"west": west, "south": south, "east": east, "north": north},
            "requested": ids,
            "refreshed": len(stations),
            "cache_hits": cache_hits,
            "stations": stations,
            "quakes": list(self._quake_trail),
            "snapshot": self.snapshot(),
        }

    async def station_detail(self, device_id: str, *, fresh: bool = False) -> dict[str, Any]:
        if device_id not in STATION_CATALOG:
            raise KeyError(device_id)
        age = self._cache_age(device_id)
        force = fresh or age is None or age > self.settings.detail_fresh_s
        stations = await self._ensure_readings(
            [device_id],
            force=force,
            ttl=0.0 if force else self.settings.detail_fresh_s,
        )
        if not stations:
            pin = self._pin_from_catalog(device_id)
            return build_detail(pin, cached=False, age_ms=-1)
        station = stations[0]
        age_after = self._cache_age(device_id)
        age_ms = int((age_after or 0) * 1000)
        detail = build_detail(station, cached=not force, age_ms=age_ms)
        await self._publish()
        return detail


aggregator = Aggregator()
