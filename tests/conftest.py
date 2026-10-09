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
        water_quality_history_path="",
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
            # The paid smoke brief refuses SIM pins, so the relay has to be LIVE
            # here (a `source` URL) for the product path to be testable at all.
            "device_id": "hms-smoke-01",
            "model": "GAIA-SMOKE (NOAA HMS)",
            "site": "noaa-hms",
            "online": True,
            "source": "https://www.ospo.noaa.gov/Products/land/hms.html",
            "fields": {"severity_score": "score"},
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


# One heavy HMS polygon over the western US. The centroid sits ~900 km from San
# Francisco, so any test that answers "is this asset in smoke?" from the centroid
# gets the wrong answer — which is the whole reason the geometry is relayed.
HMS_TEST_PLUME = [
    [-125.0, 35.0], [-100.0, 35.0], [-100.0, 45.0], [-125.0, 45.0], [-125.0, 35.0],
]


def _hms_smoke_reading() -> dict[str, Any]:
    return {
        "reading": {
            "device_id": "hms-smoke-01",
            "site": "noaa-hms",
            "ts": "2026-08-27T19:05:00+00:00",
            "seq": 4,
            "values": {"severity_score": 90.0, "latitude": 40.0, "longitude": -112.5},
            "hotspots": [{
                "severity_score": 90.0,
                "latitude": 40.0,
                "longitude": -112.5,
                "density": "heavy",
                "satellite": "GOES-19",
                "start_time": "2026-08-27 18:00 UTC",
                "end_time": "2026-08-27 20:00 UTC",
                "geometry_type": "Polygon centroid",
                "polygon_id": "hms-testplume",
                "geometry_digest": "e" * 64,
                "vertex_count": 5,
                "bbox": [-125.0, 35.0, -100.0, 45.0],
                "geometry": {"type": "Polygon", "coordinates": [HMS_TEST_PLUME]},
            }],
            "hotspot_count": 1,
            "inventory_total": 1,
            "inventory_complete": True,
            "attribution": "NOAA/NESDIS Hazard Mapping System (HMS)",
        },
        "attestation": {"algorithm": "ed25519", "value": "smoke-sig", "canonical":
                        "device|model|seq|ts|values_sha256|hotspots_sha256"},
    }


def _coordinate_air_reading(latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "reading": {
            "device_id": "om-aq-01",
            "site": "live-air-coordinate",
            "ts": "2026-08-27T19:00:00+00:00",
            "values": {
                "pm2_5_ugm3": 41.0,
                "pm10_ugm3": 58.0,
                "us_aqi": 115.0,
                "european_aqi": 62.0,
                "latitude": latitude,
                "longitude": longitude,
            },
            "units": {"pm2_5_ugm3": "ug/m3", "us_aqi": "US AQI"},
            "attribution": "Open-Meteo.com",
        },
        "attestation": {"algorithm": "ed25519", "value": "air-sig"},
    }


@pytest_asyncio.fixture
async def aggregator(settings: Settings) -> Aggregator:
    agg = Aggregator(settings)
    # Fake client so start() is happy; we stub _invoke instead of HTTP.
    agg._client = AsyncMock()

    async def fake_invoke(
        capability_id: str,
        device_id: str | None = None,
        extra_input: dict[str, Any] | None = None,
    ):
        if capability_id == "gaia.fleet.status@v1":
            return {"devices": _fleet_devices()}
        if capability_id == "gaia.smoke.read@v1":
            return _hms_smoke_reading()
        if capability_id == "gaia.air.read@v1" and (extra_input or {}).get("latitude") is not None:
            return _coordinate_air_reading(
                float(extra_input["latitude"]), float(extra_input["longitude"])
            )
        if capability_id == "gaia.water_quality.read@v1" and extra_input:
            west = float(extra_input["west"])
            south = float(extra_input["south"])
            east = float(extra_input["east"])
            north = float(extra_input["north"])
            return {
                "reading": {
                    "site": "usgs-continuous-network",
                    "values": {},
                    "hotspots": [{
                        "station_id": f"test-{west:.2f}-{south:.2f}",
                        "name": "USGS test continuous site",
                        "water_temperature_c": 17.2,
                        "latitude": (south + north) / 2.0,
                        "longitude": (west + east) / 2.0,
                        "observed_at": "2026-08-27T00:00:00Z",
                        "approval_status": "Provisional",
                        "qualifiers": ["Ice"],
                        "available_parameters": ["water_temperature_c"],
                        "observation_metadata": {
                            "water_temperature_c": {
                                "parameter_code": "00010",
                                "observed_at": "2026-08-27T00:00:00Z",
                                "approval_status": "Provisional",
                                "qualifier": "Ice",
                            },
                        },
                    }],
                }
            }
        if device_id:
            return _reading_for(device_id)
        return None

    agg._invoke = fake_invoke  # type: ignore[method-assign]
    await agg.refresh_fleet()
    # Production warming is intentionally background/batched. Tests await the
    # initial fake warm so no leftover task races the behaviour under test.
    if agg._warm_task:
        await agg._warm_task
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
