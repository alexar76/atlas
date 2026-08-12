"""Fleet pins + viewport orchestration over GAIA (composes geo / client / readings / fleet)."""

from __future__ import annotations

import asyncio
import logging
import time
from contextvars import ContextVar
from typing import Any

from . import __version__
from .config import Settings, get_settings
from .formatters import build_detail
from .gaia_client import GaiaClient
from .geo import expand_bbox, in_bbox, lon_span, normalize_bbox, station_ids_in_bbox, utc_now
from . import fleet as fleet_mod
from .readings import ReadingStore
from .stations import LAYER_META, STATION_CATALOG

log = logging.getLogger("atlas.aggregator")

# Back-compat for tests that import ``_in_bbox`` from this module.
_in_bbox = in_bbox

# Per-task FIRMS query (bbox/limit). Instance fields race when two viewports overlap.
_FIRE_QUERY: ContextVar[dict[str, Any] | None] = ContextVar("atlas_fire_query", default=None)


class Aggregator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._fleet_lock = asyncio.Lock()
        self._snapshot: dict[str, Any] = self._empty_snapshot(status="starting")
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None
        self._warm_task: asyncio.Task | None = None
        # After a viewport FIRMS densify, skip fleet re-fetch briefly so a slow
        # global poll cannot overwrite the in-view cluster.
        self._fire_viewport_pin_until: float = 0.0
        self._gaia = GaiaClient(self.settings)
        self._store = ReadingStore(self.settings)
        self._poll_count = 0
        self._poll_errors = 0
        self._last_ok_at: float | None = None
        self._quake_trail: list[dict[str, Any]] = []
        self._fleet_by_id: dict[str, dict[str, Any]] = {}
        self._sem = asyncio.Semaphore(self.settings.gaia_concurrency)
        # Expanded public snapshot (stations list is huge for FIRMS) — rebuild
        # only when the reading store revision changes.
        self._public_snap: dict[str, Any] | None = None
        self._public_snap_rev: int = -1
        self._public_snap_built_at: float = 0.0
        # Honest global Wildfire total (FIRMS non-low). Map pins are viewport-only.
        # Newest-fetch-wins (matched is global regardless of bbox) — a ratchet
        # would pin the sidebar at the all-time peak after the day rolls over.
        self._fire_global_matched: int = 0
        self._fire_global_matched_at: float = 0.0
        # Last successful viewport densify (rounded bbox) — identical cameras
        # within the TTL reuse the cached cluster instead of re-hitting GAIA.
        self._fire_last_bbox: tuple[Any, ...] | None = None
        self._fire_last_at: float = 0.0

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
                "fires": 0,
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
        if self._warm_task and not self._warm_task.done():
            self._warm_task.cancel()
            try:
                await self._warm_task
            except asyncio.CancelledError:
                pass
            self._warm_task = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._gaia.close()

    def _note_fire_matched(self, matched: int, at: float) -> None:
        """Record the global FIRMS non-low total; newest fetch wins (no ratchet)."""
        if matched <= 0:
            return
        if at >= self._fire_global_matched_at:
            self._fire_global_matched = int(matched)
            self._fire_global_matched_at = float(at)

    def _catalog_ids(self) -> list[str]:
        stations = self._snapshot.get("stations") or []
        ids = [
            str(s["id"])
            for s in stations
            if isinstance(s, dict)
            and s.get("id")
            and str(s["id"]) in STATION_CATALOG
        ]
        if ids:
            return ids
        return list(STATION_CATALOG.keys())

    def _kick_warm(self, device_ids: list[str]) -> None:
        """Background TTL-respecting prefetch (neighbors / rest of catalog)."""
        wanted = [
            d for d in device_ids
            if d in STATION_CATALOG and d != "firms-fire-01"
        ]
        if not wanted:
            return
        ttl = self.settings.reading_ttl_s
        stale = [
            d
            for d in wanted
            if (age := self._cache_age(d)) is None or age >= ttl
        ]
        if not stale:
            return

        async def _run() -> None:
            try:
                await self._ensure_readings(stale, force=False)
                await self._publish()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.debug("background warm failed", exc_info=True)

        if self._warm_task and not self._warm_task.done():
            # Chain: let current finish; schedule follow-up for remaining.
            prev = self._warm_task

            async def _after() -> None:
                try:
                    await prev
                except Exception:
                    pass
                await _run()

            self._warm_task = asyncio.create_task(_after(), name="atlas-warm")
        else:
            self._warm_task = asyncio.create_task(_run(), name="atlas-warm")

    async def ensure_all_readings(self, *, force: bool = False) -> list[dict[str, Any]]:
        """Warm every catalog station into the shared reading cache (Analyst / ops)."""
        ids = self._catalog_ids()
        stations = await self._ensure_readings(ids, force=force)
        await self._publish()
        return stations

    def snapshot(self) -> dict[str, Any]:
        rev = int(getattr(self._store, "rev", 0) or 0)
        fleet_mono = self._snapshot.get("_monotonic")
        if (
            self._public_snap is not None
            and self._public_snap_rev == rev
            and self._public_snap.get("_fleet_mono") == fleet_mono
        ):
            snap = dict(self._public_snap)
            now = time.monotonic()
            generated = self._public_snap.get("_monotonic")
            if isinstance(generated, (int, float)):
                age_ms = int((now - generated) * 1000)
                snap["age_ms"] = max(0, age_ms)
                snap["stale"] = age_ms > int(self.settings.stale_after_s * 1000)
            snap.pop("_monotonic", None)
            snap.pop("_fleet_mono", None)
            return snap

        # Shallow shell — do NOT deepcopy tens of thousands of pins.
        snap = {
            k: v
            for k, v in self._snapshot.items()
            if k not in ("stations", "summary")
        }
        base: list[dict[str, Any]] = []
        for s in self._snapshot.get("stations") or []:
            if not isinstance(s, dict) or not s.get("id"):
                continue
            sid = str(s["id"])
            # Drop previously expanded event pins; parents carry hotspots[].
            if sid.startswith(("firms-hs-", "rad-hs-", "quake-ev-", "jam-ev-")):
                continue
            base.append(dict(s))
        by_id = {str(s["id"]): s for s in base}
        for device_id, entry in self._store.entries.items():
            station = entry.get("station")
            if not isinstance(station, dict):
                continue
            pin = by_id.get(device_id)
            age_ms = int((time.monotonic() - entry["fetched_at"]) * 1000)
            patch = {
                "values": station.get("values") or {},
                "headline": station.get("headline"),
                "online": station.get("online", True),
                "lat": station.get("lat"),
                "lon": station.get("lon"),
                "reading_age_ms": age_ms,
                "has_reading": bool(station.get("values")),
            }
            if "hotspots" in station:
                patch["hotspots"] = station.get("hotspots")
            for key in ("hotspot_count", "hotspot_matched"):
                if key in station:
                    patch[key] = station.get(key)
            try:
                matched = int(station.get("hotspot_matched") or 0)
            except (TypeError, ValueError):
                matched = 0
            if str(station.get("layer") or "") == "fire":
                self._note_fire_matched(matched, entry["fetched_at"])
            if pin:
                pin.update({k: v for k, v in patch.items() if v is not None or k in ("values", "hotspots")})
                if "hotspots" in station and not station.get("hotspots"):
                    pin.pop("hotspots", None)
            else:
                enriched = dict(station)
                enriched["reading_age_ms"] = age_ms
                enriched["has_reading"] = bool(station.get("values"))
                by_id[device_id] = enriched
        stations = fleet_mod.expand_fire_hotspots(list(by_id.values()), expand=False)
        snap["stations"] = stations
        generated = self._snapshot.get("_monotonic")
        now = time.monotonic()
        snap["_monotonic"] = generated if isinstance(generated, (int, float)) else now
        snap["_fleet_mono"] = fleet_mono
        if isinstance(snap["_monotonic"], (int, float)):
            age_ms = int((now - snap["_monotonic"]) * 1000)
            snap["age_ms"] = max(0, age_ms)
            snap["stale"] = age_ms > int(self.settings.stale_after_s * 1000)
        else:
            snap["age_ms"] = 0
            snap["stale"] = False
        from collections import Counter

        by_layer = Counter(str(s.get("layer") or "") for s in stations if s.get("layer"))
        # Dense event layers: sidebar shows cluster sizes from parent readings.
        for layer in ("radiation", "quake", "jamming"):
            total = 0
            for station in by_id.values():
                if str(station.get("layer") or "") != layer:
                    continue
                raw = station.get("hotspots")
                try:
                    matched = int(station.get("hotspot_matched") or 0)
                except (TypeError, ValueError):
                    matched = 0
                if not matched and isinstance(raw, list):
                    matched = len(raw)
                total += matched or 1
            if total:
                by_layer[layer] = total
        fire_total = max(int(self._fire_global_matched or 0), int(by_layer.get("fire") or 0))
        for station in by_id.values():
            if str(station.get("layer") or "") != "fire":
                continue
            try:
                matched = int(station.get("hotspot_matched") or 0)
            except (TypeError, ValueError):
                matched = 0
            if matched > fire_total:
                fire_total = matched
        if fire_total:
            by_layer["fire"] = fire_total
        summary = dict(self._snapshot.get("summary") or {})
        summary["stations"] = len(stations)
        summary["online"] = sum(1 for s in stations if s.get("online"))
        summary["live"] = sum(1 for s in stations if s.get("mode") == "live" or s.get("live"))
        summary["sim"] = sum(1 for s in stations if s.get("mode") == "sim")
        summary["layers"] = len(by_layer)
        summary["quakes"] = len(snap.get("quakes") or [])
        summary["fires"] = fire_total
        summary["fire_pins"] = 0  # map pins live in the client viewport cache
        summary["cached_readings"] = sum(1 for s in stations if s.get("has_reading"))
        summary["by_layer"] = dict(by_layer)
        snap["summary"] = summary
        # Keep cache internals for age math; strip on the wire copy.
        self._public_snap = snap
        self._public_snap_rev = rev
        self._public_snap_built_at = now
        out = dict(snap)
        out.pop("_monotonic", None)
        out.pop("_fleet_mono", None)
        return out

    def monitor_payload(self) -> dict[str, Any]:
        snap = self.snapshot()
        stations = snap.get("stations") or []
        # The monitor panel shows a slice of a 50+ station fleet — rank the
        # interesting ones first instead of cutting the catalog in dict order.
        ranked = sorted(
            stations,
            key=lambda s: (
                0 if s.get("has_reading") else 1,
                0 if (s.get("live") or s.get("mode") == "live") else 1,
                0 if s.get("online") else 1,
                str(s.get("id") or ""),
            ),
        )
        limit = max(1, int(self.settings.monitor_station_limit))
        return {
            "version": __version__,
            "service": "atlas",
            "status": snap.get("status"),
            "stale": snap.get("stale"),
            "generated_at": snap.get("generated_at"),
            "age_ms": snap.get("age_ms"),
            "station_count": len(stations),
            "online": sum(1 for s in stations if s.get("online")),
            "live": sum(1 for s in stations if s.get("live") or s.get("mode") == "live"),
            "sim": sum(1 for s in stations if s.get("mode") == "sim"),
            "layers": sorted({s.get("layer") for s in stations if s.get("layer")}),
            "quake_count": len(snap.get("quakes") or []),
            "embed_url": f"{self.settings.public_url.rstrip('/')}/embed",
            "map_url": self.settings.public_url.rstrip("/"),
            "stations_shown": min(limit, len(stations)),
            "stations": [
                {
                    "id": s.get("id"),
                    "layer": s.get("layer"),
                    "label": s.get("label"),
                    "place": s.get("place"),
                    "online": s.get("online"),
                    "mode": s.get("mode") or ("live" if s.get("live") else "sim"),
                    "live": bool(s.get("live")),
                    "source": s.get("source"),
                    "lat": s.get("lat"),
                    "lon": s.get("lon"),
                    "headline": s.get("headline") or "—",
                    "values": s.get("values") or {},
                    "has_reading": bool(s.get("has_reading")),
                }
                for s in ranked[:limit]
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

    async def _invoke(
        self,
        capability_id: str,
        device_id: str | None = None,
        *,
        extra_input: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Delegates to GaiaClient; kept patchable for tests."""
        return await self._gaia.invoke(capability_id, device_id, extra_input=extra_input)

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

        event_ids = [
            did for did in wanted_ids
            if (STATION_CATALOG.get(did) or {}).get("layer") in (
                "quake", "fire", "radiation", "jamming", "traffic"
            )
        ]
        if time.monotonic() < float(self._fire_viewport_pin_until or 0.0):
            event_ids = [d for d in event_ids if d != "firms-fire-01"]
        if event_ids:
            try:
                await self._ensure_readings(event_ids, force=False)
                for eid in event_ids:
                    q = self._store.get_station(eid)
                    if not isinstance(q, dict):
                        continue
                    for i, s in enumerate(stations):
                        if s["id"] == eid:
                            stations[i] = {
                                **s,
                                **{
                                    k: q[k]
                                    for k in (
                                        "lat",
                                        "lon",
                                        "values",
                                        "headline",
                                        "online",
                                        "has_reading",
                                        "hotspots",
                                        "hotspot_matched",
                                        "hotspot_count",
                                    )
                                    if k in q
                                },
                            }
                            if (STATION_CATALOG.get(eid) or {}).get("layer") == "quake":
                                self._remember_quake(q)
                            if (STATION_CATALOG.get(eid) or {}).get("layer") == "fire":
                                try:
                                    matched = int(q.get("hotspot_matched") or 0)
                                except (TypeError, ValueError):
                                    matched = 0
                                self._note_fire_matched(matched, time.monotonic())
                            break
            except Exception:
                log.debug("event pin refresh skipped", exc_info=True)

        snap = fleet_mod.assemble_fleet_snapshot(
            stations=stations,
            quake_trail=self._quake_trail,
            gaia_url=self.settings.gaia_url,
            public_url=self.settings.public_url,
        )
        if snap["status"] == "ok":
            self._last_ok_at = time.monotonic()
        if self.settings.warm_all_on_fleet:
            self._kick_warm(list(STATION_CATALOG.keys()))
        return snap

    async def _fetch_station_reading(self, device_id: str) -> dict[str, Any]:
        fire_limit: int | None = None
        fire_bbox: tuple[float, float, float, float] | None = None
        meta = STATION_CATALOG.get(device_id) or {}
        if meta.get("layer") == "fire":
            q = _FIRE_QUERY.get() or {}
            fire_limit = int(q.get("limit") or self.settings.firms_hotspot_limit or 500)
            bbox = q.get("bbox")
            if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                fire_bbox = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        async with self._sem:
            return await fleet_mod.fetch_station_reading(
                device_id,
                fleet_by_id=self._fleet_by_id,
                invoke=self._invoke,
                on_quake=self._remember_quake,
                fire_limit=fire_limit,
                fire_bbox=fire_bbox,
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
        # Accept any client viewport (Analyst bbox is not schema-validated).
        west, south, east, north = normalize_bbox(west, south, east, north)
        if not (self._snapshot.get("stations") or []):
            await self.refresh_fleet()
        stations_snap = self._snapshot.get("stations") or []
        # Synthetic map pins (firms-hs-*) are expanded from FIRMS clusters — only
        # catalog device_ids may be invoked against GAIA.
        ids = [
            i
            for i in station_ids_in_bbox(stations_snap, west, south, east, north)
            if i in STATION_CATALOG
        ]
        ttl = self.settings.reading_ttl_s
        cache_hits = sum(
            1
            for did in ids
            if not force and (age := self._cache_age(did)) is not None and age < ttl
        )

        # Wildfire: densify ONLY the visible camera bbox. Global FIRMS total is
        # tracked separately for the sidebar (hotspot_matched) — never dump the
        # full day onto the map from a world view.
        fire_id = "firms-fire-01"
        fire_refreshed = False
        fire_query_meta: dict[str, Any] | None = None
        if fire_id in STATION_CATALOG:
            fire_pad = 2.0
            fw, fs, fe, fn = (
                expand_bbox(west, south, east, north, fire_pad)
                if fire_pad > 0
                else (west, south, east, north)
            )
            span = lon_span(fw, fe)
            # Map densify = top-N brightest in camera (browser-safe). Sidebar total
            # still comes from hotspot_matched (full FIRMS day).
            map_limit = int(
                getattr(self.settings, "firms_map_pin_limit", None)
                or 2000
            )
            # Always densify the camera bbox (top-N brightest). Client paints every
            # pin in view from its session cache — no MapLibre clustering / "zoom in".
            query: dict[str, Any] = {
                "limit": max(1, map_limit),
                "bbox": (fw, fs, fe, fn),
            }
            fire_query_meta = dict(query)
            fire_query_meta["span_deg"] = span
            fire_query_meta["densify"] = True
            # Identical camera within the TTL reuses the cached cluster — the
            # unconditional force bypassed the force budget and let one panning
            # user queue back-to-back FIRMS drains behind the device lock.
            fire_ttl = float(getattr(self.settings, "firms_viewport_ttl_s", 20.0) or 0.0)
            bbox_key = (round(fw, 2), round(fs, 2), round(fe, 2), round(fn, 2), max(1, map_limit))
            fire_age = self._cache_age(fire_id)
            if (
                not force
                and self._fire_last_bbox == bbox_key
                and (time.monotonic() - self._fire_last_at) < fire_ttl
                and self._store.get_station(fire_id) is not None
            ):
                fire_refreshed = True
                fire_query_meta["cached"] = True
                if fire_id not in ids:
                    ids = [fire_id, *ids]
            else:
                token = _FIRE_QUERY.set(query)
                try:
                    await self._ensure_readings([fire_id], force=True, ttl=0.0)
                    fire_refreshed = True
                    cached_fire = self._store.get_station(fire_id)
                    try:
                        matched = int((cached_fire or {}).get("hotspot_matched") or 0)
                    except (TypeError, ValueError):
                        matched = 0
                    fire_age = self._cache_age(fire_id)
                    if fire_age is not None and fire_age < 5.0:
                        # Only a genuinely fresh densify pins the fleet loop out
                        # and marks the bbox cached — a failed fetch re-serving
                        # the stale entry must not suppress recovery for 120s.
                        self._note_fire_matched(matched, time.monotonic())
                        self._fire_viewport_pin_until = time.monotonic() + 120.0
                        self._fire_last_bbox = bbox_key
                        self._fire_last_at = time.monotonic()
                    if fire_id not in ids:
                        ids = [fire_id, *ids]
                finally:
                    _FIRE_QUERY.reset(token)

        other_ids = [i for i in ids if i != fire_id]
        stations = await self._ensure_readings(other_ids, force=force)
        if fire_refreshed:
            cached_fire = self._store.get_station(fire_id)
            if cached_fire:
                stations = [cached_fire, *stations]

        # Lazy ring: padded neighbors first, then the rest of the catalog.
        pad = float(self.settings.viewport_pad_deg or 0.0)
        neighbor_ids: list[str] = []
        if pad > 0:
            neighbor_ids = [
                i
                for i in station_ids_in_bbox(
                    stations_snap, west, south, east, north, pad_deg=pad
                )
                if i not in ids and i in STATION_CATALOG
            ]
        # Prefetch the padded ring only — full-catalog warm on every pan stampeded
        # GAIA (429) and starved FIRMS densify. Fleet poll still warms the rest.
        self._kick_warm(neighbor_ids)

        await self._publish()
        public = self.snapshot()
        # Map points: expand dense clusters for this camera (client merges into cache).
        dense_parents: list[dict[str, Any]] = []
        for device_id, entry in self._store.entries.items():
            station = entry.get("station")
            if not isinstance(station, dict):
                continue
            layer = str(station.get("layer") or "")
            if layer in ("fire", "radiation", "quake", "jamming"):
                dense_parents.append(station)
        map_points = fleet_mod.expand_fire_hotspots(dense_parents, expand=True)
        # Keep only points that fall in a lightly padded camera bbox.
        map_pad = 2.0
        mw, ms, me, mn = expand_bbox(west, south, east, north, map_pad)
        def _in_view(p: dict[str, Any]) -> bool:
            try:
                lat = float(p.get("lat"))
                lon = float(p.get("lon"))
            except (TypeError, ValueError):
                return False
            if lat < ms or lat > mn:
                return False
            if mw <= me:
                return mw <= lon <= me
            return lon >= mw or lon <= me
        map_points = [p for p in map_points if _in_view(p)]
        # Catalog / non-event pins from the public snapshot that are in view.
        for s in public.get("stations") or []:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id") or "")
            if sid.startswith(("firms-hs-", "rad-hs-", "quake-ev-", "jam-ev-")):
                continue
            if _in_view(s):
                map_points.append(s)
        if public.get("summary"):
            public["summary"] = dict(public["summary"])
            public["summary"]["fire_pins"] = sum(
                1 for p in map_points if p.get("layer") == "fire"
            )

        return {
            "ok": True,
            "bbox": {"west": west, "south": south, "east": east, "north": north},
            "pad_deg": pad,
            "requested": ids,
            "prefetch": neighbor_ids,
            "refreshed": len(stations),
            "cache_hits": cache_hits,
            # Slim wire copy — the raw clusters already ship expanded in
            # map_points; sending them twice doubled the payload per pan.
            "stations": fleet_mod.expand_fire_hotspots(stations, expand=False),
            "map_points": map_points,
            "quakes": list(self._quake_trail),
            "snapshot": public,
            "fire_query": fire_query_meta,
        }

    def product_stations(self) -> list[dict[str, Any]]:
        """Stations for composite SKUs — snapshot pins plus expanded event pins.

        The wire snapshot strips clusters (map pins travel via the viewport
        cache), but paid products must match per-detection pins in a bbox, so
        they get the store clusters fanned back out.
        """
        public = self.snapshot()
        out = [s for s in public.get("stations") or [] if isinstance(s, dict)]
        seen = {str(s.get("id")) for s in out}
        dense = [
            entry["station"]
            for entry in self._store.entries.values()
            if isinstance(entry.get("station"), dict)
            and str(entry["station"].get("layer") or "")
            in ("fire", "radiation", "quake", "jamming")
        ]
        for pin in fleet_mod.expand_fire_hotspots(dense, expand=True):
            sid = str(pin.get("id") or "")
            if sid and sid not in seen:
                out.append(pin)
                seen.add(sid)
        return out

    async def product_stations_for_bbox(
        self, west: float, south: float, east: float, north: float
    ) -> list[dict[str, Any]]:
        """Densify the bbox (fresh FIRMS top-N) and return pins for SKU matching."""
        vp = await self.refresh_viewport(west=west, south=south, east=east, north=north)
        return [p for p in vp.get("map_points") or [] if isinstance(p, dict)]

    async def station_detail(self, device_id: str, *, fresh: bool = False) -> dict[str, Any]:
        # Expanded event pins — rebuild from the reading-store clusters.
        if device_id.startswith(("firms-hs-", "rad-hs-", "quake-ev-", "jam-ev-")):
            dense = [
                entry["station"]
                for entry in self._store.entries.values()
                if isinstance(entry.get("station"), dict)
                and str(entry["station"].get("layer") or "")
                in ("fire", "radiation", "quake", "jamming")
            ]
            for pin in fleet_mod.expand_fire_hotspots(dense, expand=True):
                if isinstance(pin, dict) and pin.get("id") == device_id:
                    return build_detail(pin, cached=True, age_ms=0)
            raise KeyError(device_id)
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
