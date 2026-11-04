"""New relays keep observation/model semantics, location, and source validity."""

from datetime import UTC, datetime, timedelta

import pytest

from atlas.aggregator import Aggregator
from atlas.config import Settings
from atlas.fleet import expand_map_objects, fetch_station_reading
from atlas.formatters import build_detail
from atlas.layer_counts import build_layer_counts
from atlas.map_objects import source_cluster_next_expiry, without_expired_source_reading


def test_entur_counts_only_valid_positions_with_a_distinct_identity():
    now = datetime.now(UTC)
    observed = now - timedelta(minutes=2)
    expires = now + timedelta(minutes=1)
    row = {
        "train_number": "entur-opaque-id", "line_ref": "VYG:Line:R10",
        "observation_unix": observed.timestamp(), "observed_at": observed.isoformat(),
        "valid_until": expires.isoformat(), "latitude": 60, "longitude": 10,
    }
    station = {"id": "entur-rail-vyg-01", "layer": "rail", "online": True,
               "hotspots": [row, {**row, "valid_until": (now - timedelta(seconds=1)).isoformat()}]}
    [point] = expand_map_objects([station])
    assert point["id"] == "entur-tr-entur-opaque-id"
    assert point["label"] == "Entur · Vy · R10"
    assert point["headline"] == "Reported train position"
    assert build_layer_counts([station], ["rail"])["rail"]["count"] == 1
    assert source_cluster_next_expiry(station, now=now.timestamp()) == expires.timestamp()
    assert not without_expired_source_reading(point, now=expires.timestamp())["has_reading"]


def test_bfs_and_drap_do_not_inherit_other_sources_metrics():
    now = datetime.now(UTC)
    bfs = {"id": "bfs-odl-01", "layer": "radiation", "hotspots": [
        {"station_id": "091620005", "station_name": "München", "latitude": 48, "longitude": 11,
         "dose_equivalent_nsv_h": 74, "observed_at": now.isoformat(),
         "observation_unix": now.timestamp(), "cpm": 999},
    ]}
    drap = {"id": "swpc-drap-01", "layer": "hf_absorption", "hotspots": [
        {"latitude": 87, "longitude": -174, "drap_frequency_mhz": 0,
         "observed_at": now.isoformat(), "forecast_valid_unix": now.timestamp()},
    ]}
    station, cell = expand_map_objects([bfs, drap])
    assert (station["id"], station["label"], station["headline"]) == (
        "bfs-odl-st-091620005", "BfS · München", "74 nSv/h",
    )
    assert "cpm" not in station["values"]
    assert cell["id"].startswith("drap-cell-") and cell["headline"] == "1 dB threshold 0 MHz"
    assert "modeled" in build_detail(cell, cached=True, age_ms=0)["blurb"]
    assert not without_expired_source_reading(cell, now=(now + timedelta(minutes=15)).timestamp())["has_reading"]


def test_drap_viewport_reduction_keeps_native_grid_and_inspectable_tile_maxima():
    now = datetime.now(UTC).timestamp()
    parent = {"id": "swpc-drap-01", "layer": "hf_absorption", "hotspots": [
        {"latitude": lat, "longitude": lon, "drap_frequency_mhz": 8.1 if (lat, lon) == (85, -170) else 0,
         "forecast_valid_unix": now}
        for lat in range(89, -90, -2) for lon in range(-178, 180, 4)
    ]}
    wide = expand_map_objects([parent], drap_resolution="overview")
    assert len(wide) == 900
    [tile] = (p for p in wide if p["values"]["drap_frequency_mhz"])
    assert (tile["lat"], tile["lon"]) == (87, -174)
    assert tile["id"].startswith("drap-cell-overview-")
    assert "maximum" in build_detail(tile, cached=True, age_ms=0)["blurb"]
    local = expand_map_objects([parent], drap_bbox=(-179, 84, -169, 90))
    assert len(local) == 9
    [cell] = (p for p in local if p["values"]["drap_frequency_mhz"])
    assert (cell["lat"], cell["lon"]) == (85, -170)
    assert cell["drap_resolution"] == "native"
    assert len(expand_map_objects([parent])) == 8100


@pytest.mark.asyncio
async def test_eccc_uses_the_returned_cell_and_stops_at_target_time():
    now = datetime.now(UTC)
    valid = now + timedelta(minutes=30)
    run = now - timedelta(hours=6)
    values = {
        "latitude": 47.62, "longitude": -122.32, "forecast_smoke_pm2_5_ugm3": 0,
        "forecast_valid_unix": valid.timestamp(), "forecast_run_unix": run.timestamp(),
    }

    async def invoke(capability, device_id):
        assert capability == "gaia.smoke.forecast.read@v1"
        assert device_id == "eccc-smoke-seattle"
        return {"reading": {"values": values}}

    point = await fetch_station_reading(
        "eccc-smoke-seattle", fleet_by_id={"eccc-smoke-seattle": {"source": "https://geo.weather.gc.ca"}},
        invoke=invoke,
    )
    assert (point["lat"], point["lon"]) == (47.62, -122.32)
    assert point["headline"] == "Forecast PM2.5 0 µg/m³"
    assert not without_expired_source_reading(point, now=valid.timestamp())["online"]


@pytest.mark.asyncio
async def test_missed_fleet_poll_keeps_verified_provenance_for_new_readings(monkeypatch):
    agg = Aggregator(Settings(warm_all_on_fleet=False))
    device_id = "chmi-river-200100"
    source = "https://opendata.chmi.cz/hydrology/"
    polls = iter(({"devices": [{"device_id": device_id, "source": source}]}, None))

    async def invoke(capability_id, target=None, **kwargs):
        if capability_id == "gaia.fleet.status@v1":
            return next(polls)
        assert capability_id == "gaia.river.read@v1" and target == device_id
        return {"reading": {"values": {
            "gage_height_m": 0.4, "discharge_m3s": 33, "observation_unix": datetime.now(UTC).timestamp(),
        }}}

    async def skip_event_warm(*args, **kwargs):
        assert kwargs["deadline_s"] > 0
        assert "swpc-drap-01" in args[0][:3]
        return []

    monkeypatch.setattr(agg, "_invoke", invoke)
    monkeypatch.setattr(agg, "_ensure_readings", skip_event_warm)
    await agg.refresh_fleet()
    with pytest.raises(RuntimeError, match="keeping last confirmed inventory"):
        await agg.refresh_fleet()
    assert agg._poll_count == 1
    point = await agg._fetch_station_reading(device_id)
    assert point["live"] and point["source"] == source and point["online"]
