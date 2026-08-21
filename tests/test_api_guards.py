"""Public-edge guards: cache-bypass budget, operator token, AI budget.

ATLAS is unauthenticated on purpose, but ``force`` / ``fresh`` / ``/refresh``
bypass the reading cache (N GAIA invokes per call) and ``/api/ai/ask`` spends
provider tokens, so those paths get their own tight per-IP budgets.
"""

from __future__ import annotations

import pytest

import atlas.main as main_mod
from atlas.config import Settings
from atlas.main import RateLimiter


@pytest.mark.asyncio
async def test_force_viewport_is_budgeted(client, monkeypatch):
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(2))
    body = {"west": 12.0, "south": 52.0, "east": 14.0, "north": 53.0, "force": True}

    first = await client.post("/api/v1/viewport", json=body)
    second = await client.post("/api/v1/viewport", json=body)
    third = await client.post("/api/v1/viewport", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert "budget" in third.json()["detail"]


@pytest.mark.asyncio
async def test_unforced_viewport_is_not_budgeted(client, monkeypatch):
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(1))
    body = {"west": 12.0, "south": 52.0, "east": 14.0, "north": 53.0}
    for _ in range(3):
        r = await client.post("/api/v1/viewport", json=body)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_fresh_station_and_refresh_share_the_budget(client, monkeypatch):
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(1))
    ok = await client.get("/api/v1/stations/om-wx-01?fresh=1")
    blocked = await client.post("/api/v1/refresh")
    assert ok.status_code == 200
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_cached_station_read_is_free(client, monkeypatch):
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(1))
    for _ in range(3):
        r = await client.get("/api/v1/stations/om-wx-01")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_operator_token_skips_the_budget(client, monkeypatch):
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(1))
    monkeypatch.setattr(main_mod, "settings", Settings(operator_token="s3cret"))
    for _ in range(3):
        r = await client.post("/api/v1/refresh", headers={"X-ATLAS-Token": "s3cret"})
        assert r.status_code == 200
    # A wrong token is simply not an operator: it falls back to the budget
    # (which is 1 here) instead of being trusted.
    wrong = await client.post("/api/v1/refresh", headers={"X-ATLAS-Token": "nope"})
    again = await client.post("/api/v1/refresh", headers={"X-ATLAS-Token": "nope"})
    assert wrong.status_code == 200
    assert again.status_code == 429


@pytest.mark.asyncio
async def test_ai_ask_has_its_own_budget(client, monkeypatch):
    monkeypatch.setattr(main_mod, "ai_limiter", RateLimiter(1))
    first = await client.post("/api/ai/ask", json={"question": "temperature in Berlin?"})
    second = await client.post("/api/ai/ask", json={"question": "temperature in Berlin?"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["scope"] == "ai"


@pytest.mark.asyncio
async def test_ai_providers_get_is_not_ai_budgeted(client, monkeypatch):
    monkeypatch.setattr(main_mod, "ai_limiter", RateLimiter(1))
    for _ in range(3):
        r = await client.get("/api/ai/providers")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_version_header_tracks_package_version(client):
    from atlas import __version__

    r = await client.get("/api/v1/snapshot")
    assert r.headers["X-ATLAS-Version"] == __version__


@pytest.mark.asyncio
async def test_monitor_payload_ranks_and_caps_stations(client, monkeypatch):
    monkeypatch.setattr(main_mod.aggregator.settings, "monitor_station_limit", 5)
    r = await client.get("/api/v1/monitor")
    body = r.json()
    assert r.status_code == 200
    assert body["station_count"] > 5  # 50+ station fleet
    assert body["stations_shown"] == 5
    assert len(body["stations"]) == 5
    # Stations with a reading come first — never a dict-order slice.
    assert all(s["has_reading"] for s in body["stations"])


# ── review follow-ups ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_budget_cannot_be_reset_by_spoofing_x_forwarded_for(client, monkeypatch):
    """Only the hop nginx appends (rightmost) may key a budget.

    nginx sends ``$proxy_add_x_forwarded_for``: whatever the caller sent, plus the
    real peer. Reading the leftmost entry let a client rotate a fake IP per
    request and walk straight through the AI / cache-bypass caps.
    """
    monkeypatch.setattr(main_mod, "force_limiter", RateLimiter(1))
    body = {"west": 12.0, "south": 52.0, "east": 14.0, "north": 53.0, "force": True}
    first = await client.post(
        "/api/v1/viewport", json=body, headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.9"}
    )
    spoofed = await client.post(
        "/api/v1/viewport", json=body, headers={"X-Forwarded-For": "5.6.7.8, 203.0.113.9"}
    )
    assert first.status_code == 200
    assert spoofed.status_code == 429


def test_client_ip_reads_the_trusted_hop():
    from starlette.datastructures import Headers

    def _req(headers, peer="127.0.0.1"):
        return type(
            "R",
            (),
            {"headers": Headers(headers), "client": type("C", (), {"host": peer})()},
        )()

    # Behind our own nginx (loopback peer): X-Real-IP wins, else the last XFF hop.
    assert main_mod._client_ip(_req({"x-real-ip": "203.0.113.9"})) == "203.0.113.9"
    assert (
        main_mod._client_ip(_req({"x-forwarded-for": "1.2.3.4, 203.0.113.9"}))
        == "203.0.113.9"
    )
    assert main_mod._client_ip(_req({})) == "127.0.0.1"

    # Exposed directly (public peer — note ipaddress treats TEST-NET ranges as
    # private, so this uses a really public address): proxy headers are
    # attacker-controlled and must be ignored entirely.
    assert (
        main_mod._client_ip(
            _req({"x-real-ip": "10.0.0.1", "x-forwarded-for": "10.0.0.2"}, peer="8.8.8.8")
        )
        == "8.8.8.8"
    )


def test_operator_token_survives_a_non_ascii_header():
    """compare_digest() raises TypeError on non-ASCII str → would be a 500.

    Latin-1 is the wire encoding Starlette decodes headers with, so "pärol" is a
    value a real client can actually send.
    """
    from starlette.datastructures import Headers

    class _Req:
        def __init__(self, token):
            self.headers = Headers({"x-atlas-token": token})
            self.client = type("C", (), {"host": "10.0.0.1"})()

    original = main_mod.settings
    try:
        main_mod.settings = Settings(operator_token="s3cret")
        assert main_mod._operator_ok(_Req("pärol")) is False
        assert main_mod._operator_ok(_Req("s3cret")) is True
    finally:
        main_mod.settings = original
