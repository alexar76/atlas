"""GAIA client pacing and transient-rate-limit recovery."""

from __future__ import annotations

import httpx
import pytest

from atlas.config import Settings
from atlas.gaia_client import GaiaClient


@pytest.mark.asyncio
async def test_invoke_retries_429_and_returns_output():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"detail": "rate limited"})
        return httpx.Response(
            200,
            json={"ok": True, "output": {"reading": {"device_id": "station-01"}}},
        )

    settings = Settings(
        gaia_url="https://gaia.test",
        gaia_requests_per_minute=1_000_000_000,
        gaia_max_retries=1,
        gaia_retry_base_s=0,
        gaia_retry_max_s=0,
    )
    client = GaiaClient(settings)
    client.raw = httpx.AsyncClient(
        base_url=settings.gaia_url,
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.invoke("gaia.geomag.read@v1", "station-01")
    finally:
        await client.close()

    assert calls == 2
    assert result == {"reading": {"device_id": "station-01"}}


@pytest.mark.asyncio
async def test_invoke_stops_after_configured_429_retries():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, json={"detail": "rate limited"})

    settings = Settings(
        gaia_url="https://gaia.test",
        gaia_requests_per_minute=1_000_000_000,
        gaia_max_retries=2,
        gaia_retry_base_s=0,
        gaia_retry_max_s=0,
    )
    client = GaiaClient(settings)
    client.raw = httpx.AsyncClient(
        base_url=settings.gaia_url,
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.invoke("gaia.geomag.read@v1", "station-01")
    finally:
        await client.close()

    assert result is None
    assert calls == 3
