"""Power prices, Sentinel-2 showcase pins and the demo actuator on the ATLAS map."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

from atlas import fleet as fleet_mod
from atlas.stations import ATLAS_SMARD_ZONES, LAYER_META, STATION_CATALOG

LANGS = ("en", "ru", "es", "fr", "zh")
REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("layer", ["power_price", "imagery", "actuator"])
def test_new_layers_are_labelled_in_every_language(layer):
    meta = LAYER_META[layer]
    assert meta["color"].startswith("#") and len(meta["color"]) == 7
    assert set(meta["labels"]) == set(LANGS) and all(meta["labels"].values())


def test_every_smard_zone_has_a_pin_on_its_layer():
    pins = {k: v for k, v in STATION_CATALOG.items() if v["layer"] == "power_price"}
    assert len(pins) == len(ATLAS_SMARD_ZONES) == 15
    for zone, *_ in ATLAS_SMARD_ZONES:
        meta = pins[f"smard-price-{zone.lower()}"]
        assert meta["capability"] == "gaia.power.price.read@v1"
        assert "not a tariff" in meta["place"]


def test_the_zones_are_gaias_zones():
    gaia = REPO / "gaia"
    if not (gaia / "gaia" / "devices" / "live_power.py").exists():
        pytest.skip("standalone ATLAS checkout")
    sys.path.insert(0, str(gaia))
    try:
        from gaia.devices.live_power import SMARD_ZONES
    except ImportError as exc:  # GAIA's own dependencies may be absent here
        pytest.skip(f"GAIA not importable: {exc}")
    assert {z: (n, la, lo) for z, n, la, lo in ATLAS_SMARD_ZONES} == {
        z: (n, la, lo) for z, (_f, n, la, lo) in SMARD_ZONES.items()}


def test_imagery_pins_read_one_shared_device_at_their_own_place():
    pins = {k: v for k, v in STATION_CATALOG.items() if v["layer"] == "imagery"}
    assert len(pins) == 5
    for pid, meta in pins.items():
        assert meta["gaia_device"] == "s2-l2a-01" and meta["min_ttl_s"] >= 6 * 3600
        assert meta["query"]["latitude"] == meta["lat"]
        assert meta["query"]["longitude"] == meta["lon"]
        assert fleet_mod.gaia_device_id(pid) == "s2-l2a-01"


def test_shared_device_pins_are_wanted_when_the_device_is_in_the_fleet():
    wanted = set(fleet_mod.wanted_station_ids({"s2-l2a-01": {"source": "x"}}))
    assert {"s2-tempelhof", "s2-wannsee", "s2-sahara"} <= wanted
    assert "smard-price-de-lu" not in wanted
    assert "s2-tempelhof" not in fleet_mod.wanted_station_ids({"om-wx-01": {"source": "x"}})


def test_a_shared_device_pin_is_read_through_it_with_its_query():
    calls: list[tuple[str, str | None, dict[str, Any] | None]] = []

    async def invoke(cap, device_id=None, *, extra_input=None):
        calls.append((cap, device_id, extra_input))
        return {"reading": {"device_id": device_id, "values": {"ndvi": 0.58},
                            "units": {"ndvi": "index"}, "ts": "2026-10-16T10:00:00Z"}}

    asyncio.run(fleet_mod.fetch_station_reading(
        "s2-tempelhof", fleet_by_id={"s2-l2a-01": {"source": "Copernicus"}}, invoke=invoke))
    cap, device, extra = calls[0]
    assert (cap, device) == ("gaia.imagery.read@v1", "s2-l2a-01")
    assert extra == {"latitude": 52.473, "longitude": 13.402, "max_age_days": 60}


def test_min_ttl_holds_even_against_a_forced_refresh():
    from atlas.config import Settings
    from atlas.readings import ReadingStore

    store = ReadingStore(Settings())
    fetched: list[str] = []

    async def fetch(device_id):
        fetched.append(device_id)
        return {"device_id": device_id, "values": {"ndvi": 0.5}, "ok": True}

    async def run():
        await store.ensure(["s2-wannsee"], fetch=fetch)
        await store.ensure(["s2-wannsee"], fetch=fetch, force=True)
        await store.ensure(["smard-price-de-lu"], fetch=fetch)
        await store.ensure(["smard-price-de-lu"], fetch=fetch, force=True)

    asyncio.run(run())
    assert fetched == ["s2-wannsee", "smard-price-de-lu", "smard-price-de-lu"]


def test_the_demo_actuator_is_a_simulator_pin():
    meta = STATION_CATALOG["plug-sim-01"]
    assert meta["layer"] == "actuator" and meta["mode"] == "sim"
    assert "gaia.actuate@v1" in meta["place"]
