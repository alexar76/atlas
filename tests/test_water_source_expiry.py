"""The map and station card retire fixed-source water readings on source time."""

from __future__ import annotations

from atlas.aggregator import Aggregator
from atlas.formatters import build_detail, metric_rows
from atlas.stations import STATION_CATALOG


def test_snapshot_and_detail_expire_water_source_values(settings, monkeypatch):
    now = 1793736000.0
    aggregator = Aggregator(settings)
    tide_id, forecast_id = "ea-tide-e70039", "nwps-pttp1"
    for device_id, values in (
        (tide_id, {"water_level_maod": 0.442, "observation_unix": now - 7199}),
        (forecast_id, {
            "forecast_stage_m": 5.2426, "forecast_issued_unix": now - 3600,
            "forecast_valid_unix": now + 3,
        }),
    ):
        pin = {**STATION_CATALOG[device_id], "id": device_id, "live": True,
               "online": True, "has_reading": True, "values": values}
        aggregator._store.put(device_id, pin)

    def snapshot_at(epoch):
        monkeypatch.setattr("atlas.aggregator.time.time", lambda: epoch)
        return {row["id"]: row for row in aggregator.snapshot()["stations"]}

    fresh = snapshot_at(now)
    assert fresh[tide_id]["online"] and fresh[forecast_id]["online"]
    tide_expired = snapshot_at(now + 2)
    assert not tide_expired[tide_id]["online"] and tide_expired[forecast_id]["online"]
    all_expired = snapshot_at(now + 4)
    assert not all_expired[forecast_id]["online"]
    assert all_expired[forecast_id]["values"] == {}
    detail = build_detail(fresh[forecast_id], cached=True, age_ms=0)
    assert not detail["online"] and detail["metrics"] == []
    assert "fresh reading" not in detail["status_line"]


def test_tide_observation_time_describes_a_gauge_measurement():
    values = {"observation_unix": 1793736000.0}
    assert metric_rows(values, layer="tide")[0]["hint"] == "When the coastal water level was measured"
    assert metric_rows(values, layer="imagery")[0]["hint"] == "When the satellite took the image"


def test_fixed_buoy_and_snotel_cards_use_their_source_age(settings, monkeypatch):
    now = 1793736000.0
    aggregator = Aggregator(settings)
    buoy, snow = "fmi-marine-134220", "snotel-335"
    for device_id, values in (
        (buoy, {"wave_height_m": 0.6, "observation_unix": now - 7199}),
        (snow, {"snow_depth_cm": 0.0, "snow_water_equivalent_cm": 1.524, "observation_unix": now - 21597}),
    ):
        aggregator._store.put(device_id, {**STATION_CATALOG[device_id], "id": device_id,
                                          "live": True, "online": True, "has_reading": True, "values": values})

    def snapshot_at(epoch):
        monkeypatch.setattr("atlas.aggregator.time.time", lambda: epoch)
        return {row["id"]: row for row in aggregator.snapshot()["stations"]}

    fresh = snapshot_at(now)
    assert "wave buoy" in build_detail(fresh[buoy], cached=True, age_ms=0)["summary"]
    assert "SNOTEL in-situ" in build_detail(fresh[snow], cached=True, age_ms=0)["summary"]
    assert fresh[snow]["values"]["snow_depth_cm"] == 0.0
    assert not snapshot_at(now + 1)[buoy]["online"]
    assert snapshot_at(now + 2)[snow]["online"]
    assert not snapshot_at(now + 3)[snow]["online"]
