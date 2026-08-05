"""Thin async client for GAIA AIMarket v2 invoke."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from . import __version__
from .config import Settings

log = logging.getLogger("atlas.gaia_client")


class GaiaClient:
    """Owns the shared httpx client used by fleet + reading paths."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        if self._client:
            return
        limits = httpx.Limits(
            max_keepalive_connections=self.settings.gaia_concurrency,
            max_connections=self.settings.gaia_concurrency + 2,
        )
        self._client = httpx.AsyncClient(
            base_url=self.settings.gaia_url.rstrip("/"),
            timeout=self.settings.gaia_timeout_s,
            limits=limits,
            headers={"user-agent": f"atlas/{__version__} (ecosystem-map)"},
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def raw(self) -> httpx.AsyncClient | None:
        """Expose underlying client for test stubs that set ``_client``."""
        return self._client

    @raw.setter
    def raw(self, client: httpx.AsyncClient | None) -> None:
        self._client = client

    async def invoke(
        self, capability_id: str, device_id: str | None = None
    ) -> dict[str, Any] | None:
        if self._client is None:
            raise RuntimeError("GaiaClient is not open")
        payload: dict[str, Any] = {
            "product_id": self.settings.gaia_product_id,
            "capability_id": capability_id,
            "source_hub": "atlas",
            "input": {},
        }
        if device_id:
            payload["input"] = {"device_id": device_id}
        try:
            r = await self._client.post("/ai-market/v2/invoke", json=payload)
            if r.status_code != 200:
                return None
            body = r.json()
            if not isinstance(body, dict) or not body.get("ok", True):
                return None
            out = body.get("output")
            return out if isinstance(out, dict) else None
        except Exception as exc:
            log.debug("invoke %s/%s failed: %s", capability_id, device_id, exc)
            return None
