"""Shared fixtures for ATLAS tests — no live GAIA network required."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from atlas.aggregator import Aggregator
from atlas.config import Settings
from atlas.om_mesh import OM_MESH_CITIES


@pytest.fixture
def settings() -> Settings:
    return Settings(
        public_url="http://test.atlas.local",
        gaia_url="https://gaia.test",
        fleet_poll_interval_s=3600,
        poll_interval_s=3600,
        reading_ttl_s=45.0,
        detail_fresh_s=20.0,
        gaia_concurrency=4,
        rate_limit_per_min=1000,
        quake_history=8,
    )


def _fleet_devices() -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = [
        {
            "device_id": "om-wx-01",
            "model": "GAIA-WS1 (Open-Meteo)",
            "site": "live-weather-eu",
            "online": True,
            "source": "https://open-meteo.com",
            "fields": {"temperature_c": "cel"},
        },
        {
            "device_id": "om-aq-01",
            "model": "GAIA-AQ1",
            "site": "live-air-eu",
            "online": True,
            "source": "https://open-meteo.com",
            "fields": {"pm2_5_ugm3": "ug/m3"},
        },
        {
            "device_id": "nws-01",
            "model": "GAIA-WS1 (NWS)",
            "site": "live-weather",
            "online": True,
            "source": "https://api.weather.gov",
            "fields": {"temperature_c": "cel"},
        },
        {
            "device_id": "noaa-tide-01",
            "model": "GAIA-TIDE",
            "site": "live-tide",
            "online": True,
            "source": "https://api.tidesandcurrents.noaa.gov",
            "fields": {"water_level_m": "m"},
        },
        {
            "device_id": "uk-grid-01",
            "model": "GAIA-GRID",
            "site": "live-grid-uk",
            "online": True,
            "source": "https://api.carbonintensity.org.uk",
            "fields": {"carbon_intensity_gco2_kwh": "gco2/kwh"},
        },
        {
            "device_id": "usgs-quake-01",
            "model": "GAIA-QUAKE",
            "site": "live-quake",
            "online": True,
            "source": "https://earthquake.usgs.gov",
            "fields": {"magnitude": "M"},
        },
        {
            "device_id": "osm-01",
            "model": "GAIA-AQ1",
            "site": "live-air",
            "online": True,
            "source": "https://api.opensensemap.org",
            "fields": {"pm2_5_ugm3": "ug/m3"},
        },
        {
            "device_id": "sta-01",
            "model": "GAIA-AQ1",
            "site": "live-air",
            "online": False,
            "source": "https://example.sensor.community",
            "fields": {"pm2_5_ugm3": "ug/m3"},
        },
        # Simulators — present on GAIA, no provenance source (honest SIM).
        {
            "device_id": "ws-01",
            "model": "GAIA-WS1",
            "site": "demo-site-1",
            "online": True,
            "source": None,
            "fields": {"temperature_c": "cel"},
        },
        {
            "device_id": "ws-02",
            "model": "GAIA-WS1",
            "site": "demo-site-1",
            "online": True,
            "source": None,
            "fields": {"temperature_c": "cel"},
        },
        {
            "device_id": "aq-01",
            "model": "GAIA-AQ1",
            "site": "demo-site-1",
            "online": True,
            "source": None,
            "fields": {"pm2_5_ugm3": "ug/m3"},
        },
        {
            "device_id": "em-01",
            "model": "GAIA-EM1",
            "site": "demo-site-1",
            "online": True,
            "source": None,
            "fields": {"power_w": "W"},
        },
    ]
    for city in OM_MESH_CITIES:
        slug = city["slug"]
        devices.append(
            {
                "device_id": f"om-wx-{slug}",
                "model": "GAIA-WS1 (Open-Meteo)",
                "site": f"live-om-{slug}",
                "online": True,
                "source": "https://open-meteo.com",
                "fields": {"temperature_c": "cel"},
            }
        )
        devices.append(
            {
                "device_id": f"om-aq-{slug}",
                "model": "GAIA-AQ1 (Open-Meteo)",
                "site": f"live-om-{slug}",
                "online": True,
                "source": "https://open-meteo.com",
                "fields": {"pm2_5_ugm3": "ug/m3"},
            }
        )
    return devices


def _reading_for(device_id: str) -> dict[str, Any] | None:
    catalog: dict[str, Any] = {
        "om-wx-01": {
            "reading": {
                "site": "live-weather-eu",
                "values": {
                    "temperature_c": 21.5,
                    "humidity_pct": 55.0,
                    "pressure_hpa": 1012.0,
                    "wind_mps": 3.2,
                },
            }
        },
        "om-aq-01": {
            "reading": {
                "site": "live-air-eu",
                "values": {"pm2_5_ugm3": 12.0, "pm10_ugm3": 18.0, "co2_ppm": 420.0},
            }
        },
        "nws-01": {
            "reading": {
                "site": "live-weather",
                "values": {
                    "temperature_c": 18.0,
                    "humidity_pct": 70.0,
                    "pressure_hpa": 1020.0,
                    "wind_mps": 1.0,
                },
            }
        },
        "noaa-tide-01": {
            "reading": {"site": "live-tide", "values": {"water_level_m": 0.42}}
        },
        "uk-grid-01": {
            "reading": {
                "site": "live-grid-uk",
                "values": {"carbon_intensity_gco2_kwh": 120.0},
            }
        },
        "usgs-quake-01": {
            "reading": {
                "site": "live-quake",
                "values": {
                    "magnitude": 4.8,
                    "depth_km": 12.0,
                    "latitude": 35.1,
                    "longitude": -118.2,
                },
            }
        },
        "osm-01": {
            "reading": {
                "site": "live-air",
                "values": {"pm2_5_ugm3": 8.5, "pm10_ugm3": 14.0},
            }
        },
        "sta-01": None,
        "ws-01": {
            "reading": {
                "site": "demo-site-1",
                "values": {
                    "temperature_c": 19.0,
                    "humidity_pct": 48.0,
                    "pressure_hpa": 1015.0,
                    "wind_mps": 2.0,
                },
            }
        },
        "ws-02": {
            "reading": {
                "site": "demo-site-1",
                "values": {
                    "temperature_c": 18.5,
                    "humidity_pct": 50.0,
                    "pressure_hpa": 1014.0,
                    "wind_mps": 1.5,
                },
            }
        },
        "aq-01": {
            "reading": {
                "site": "demo-site-1",
                "values": {"pm2_5_ugm3": 9.0, "pm10_ugm3": 15.0, "co2_ppm": 410.0},
            }
        },
        "em-01": {
            "reading": {
                "site": "demo-site-1",
                "values": {
                    "voltage_v": 230.0,
                    "current_a": 0.8,
                    "power_w": 180.0,
                    "energy_wh": 1200.0,
                },
            }
        },
    }
    if device_id.startswith("om-wx-") and device_id != "om-wx-01":
        return {
            "reading": {
                "site": f"live-om-{device_id.removeprefix('om-wx-')}",
                "values": {
                    "temperature_c": 22.0,
                    "humidity_pct": 50.0,
                    "pressure_hpa": 1010.0,
                    "wind_mps": 2.5,
                },
            }
        }
    if device_id.startswith("om-aq-") and device_id != "om-aq-01":
        return {
            "reading": {
                "site": f"live-om-{device_id.removeprefix('om-aq-')}",
                "values": {"pm2_5_ugm3": 10.0, "pm10_ugm3": 16.0, "co2_ppm": 430.0},
            }
        }
    return catalog.get(device_id)


@pytest_asyncio.fixture
async def aggregator(settings: Settings) -> Aggregator:
    agg = Aggregator(settings)
    # Fake client so start() is happy; we stub _invoke instead of HTTP.
    agg._client = AsyncMock()

    async def fake_invoke(capability_id: str, device_id: str | None = None):
        if capability_id == "gaia.fleet.status@v1":
            return {"devices": _fleet_devices()}
        if device_id:
            return _reading_for(device_id)
        return None

    agg._invoke = fake_invoke  # type: ignore[method-assign]
    await agg.refresh_fleet()
    yield agg
    await agg.stop()


@pytest_asyncio.fixture
async def client(aggregator: Aggregator, monkeypatch: pytest.MonkeyPatch):
    """FastAPI TestClient with the shared test aggregator wired in."""
    import atlas.aggregator as agg_mod
    import atlas.main as main_mod

    monkeypatch.setattr(agg_mod, "aggregator", aggregator)
    monkeypatch.setattr(main_mod, "aggregator", aggregator)

    # Avoid background fleet loop racing tests.
    async def _noop_start():
        return None

    monkeypatch.setattr(main_mod.aggregator, "start", _noop_start)
    monkeypatch.setattr(main_mod.aggregator, "stop", AsyncMock())

    from httpx import ASGITransport, AsyncClient

    # Model production: ATLAS sits behind nginx on loopback, so proxy headers
    # are only honoured for a local peer.
    transport = ASGITransport(app=main_mod.app, client=("127.0.0.1", 44444))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
