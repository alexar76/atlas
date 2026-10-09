"""Periodic sampler that fills the instrument status archive.

``atlas.observability.attest@v1`` can only attest what was recorded, so the archive
needs a writer that runs whether or not anyone is asking. Same shape as the watchbox
delivery loop: env-gated, interval-driven, and a failing tick never kills the loop.

Nothing here fetches anything itself — it asks the aggregator for the layer, exactly
as a paid product would, so the archived samples are the same rows a buyer is served.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Awaitable, Callable, Iterable

from .status_archive import ARCHIVE, StatusArchive

logger = logging.getLogger("atlas.status_sampler")

# Only layers whose value is a *status over time*. Adding a hazard-event layer here
# would grow the file without making any question answerable.
SAMPLED_LAYERS: tuple[str, ...] = ("radar",)

DEFAULT_INTERVAL_S = 600.0
DEFAULT_PRUNE_EVERY = 24  # ticks; ~4 h at the default interval


def _enabled() -> bool:
    return (os.environ.get("ATLAS_STATUS_ARCHIVE", "1") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )


class StatusSampler:
    """Append one status sample per station per tick, then prune periodically."""

    def __init__(
        self,
        *,
        fetch: Callable[[set[str]], Awaitable[Iterable[dict[str, Any]]]],
        archive: StatusArchive | None = None,
        interval_s: float | None = None,
        layers: tuple[str, ...] = SAMPLED_LAYERS,
    ) -> None:
        self._fetch = fetch
        self._archive = archive if archive is not None else ARCHIVE
        raw = (
            interval_s
            if interval_s is not None
            else os.environ.get("ATLAS_STATUS_ARCHIVE_INTERVAL_S", DEFAULT_INTERVAL_S)
        )
        try:
            self._interval = max(30.0, float(raw))
        except (TypeError, ValueError):
            self._interval = DEFAULT_INTERVAL_S
        self._layers = tuple(layers)
        self._ticks = 0
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not _enabled():
            logger.info("status archive sampling disabled (ATLAS_STATUS_ARCHIVE)")
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001 - shutdown path
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("status archive tick failed")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    async def tick(self) -> int:
        """One sample per station across the sampled layers. Returns samples written."""
        written = 0
        for layer in self._layers:
            rows = list(await self._fetch({layer}))
            pins = [
                row for row in rows
                if isinstance(row, dict) and row.get("layer") == layer
            ]
            if not pins:
                logger.info("status archive: no %s pins to sample this tick", layer)
                continue
            written += self._archive.append(layer, pins)
        self._ticks += 1
        if self._ticks % DEFAULT_PRUNE_EVERY == 0:
            dropped = self._archive.prune()
            if dropped:
                logger.info("status archive pruned %d sample(s)", dropped)
        return written


LOOP: StatusSampler | None = None

__all__ = ["StatusSampler", "SAMPLED_LAYERS", "LOOP"]
