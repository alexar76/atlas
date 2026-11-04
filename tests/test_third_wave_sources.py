"""Map semantics for new signed status, event geometry and regional inventories."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from atlas.aggregator import Aggregator
from atlas.fleet import expand_map_objects
from atlas.formatters import build_detail, metric_rows
from atlas.layer_counts import build_layer_counts
from atlas.map_objects import source_reading_expiry


def test_geonet_baseline_remains_a_status_pin_without_inflating_event_count():
    expires = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    camera = {"camera_id": "ruapehu", "url": "https://images.geonet.org.nz/volcano/cameras/latest/t-ruapehu.jpg?v=1"}
    parent = {"id": "geonet-volcano-01", "layer": "volcano", "online": True, "live": True, "hotspots": [
        {"volcano_id": "ruapehu", "latitude": -39.28, "longitude": 175.57, "valid_until": expires,
         "volcanic_alert_level": 0, "cameras": [camera], "aviation_color_code": "GREEN"},
        {"volcano_id": "whakaari", "latitude": -37.52, "longitude": 177.18, "valid_until": expires,
         "volcanic_alert_level": 2, "aviation_color_code": "YELLOW"},
    ]}
    pins = expand_map_objects([parent])
    assert len(pins) == 2
    assert pins[0]["id"] == "geonet-volcano-status-ruapehu"
    assert pins[0]["headline"] == "Volcanic alert level 0"
    assert pins[0]["cameras"] == [camera]
    assert build_layer_counts([parent], ["volcano"])["volcano"]["count"] == 1


def test_marine_card_formats_buoy_temperature_and_wind_direction():
    temperature, wind = metric_rows({"sea_temperature_c": 13.938, "wind_direction_deg": 271}, layer="marine")
    assert (temperature["label"], temperature["value"]) == ("Sea-surface temperature", "13.9 °C")
    assert (wind["label"], wind["value"]) == ("Wind direction", "271 °")


def test_ash_altitude_hints_credit_vaac_without_changing_gairmet():
    values = {"base_ft": 0, "top_ft": 14_000}
    assert all("VAAC" in row["hint"] for row in metric_rows(values, layer="volcanic_ash"))
    assert all("G-AIRMET" in row["hint"] for row in metric_rows(values, layer="aviation_hazards"))


def test_thermal_detection_hint_credits_its_provider():
    values = {"brightness_k": 310.1}
    assert "Digital Earth Australia" in metric_rows(values, layer="fire_hotspots")[0]["hint"]
    assert "FIRMS" in metric_rows(values, layer="fire")[0]["hint"]


@pytest.mark.parametrize("device,layer,prefix", [
    ("bc-wildfire-01", "wildfire_perimeters", "bc-fire"),
    ("noaa-vaac-ash-01", "volcanic_ash", "vaac-ash"),
])
def test_outlines_keep_provider_geometry_and_expiry(device, layer, prefix):
    now = datetime.now(UTC)
    expiry = now + timedelta(minutes=20)
    shape = {"type": "Polygon", "coordinates": [[[-125, 51], [-124, 51], [-124, 52], [-125, 51]]]}
    row = {"event_id": "sample", "latitude": 51.4, "longitude": -124.5, "geometry": shape,
           "event_bbox": [-125, 51, -124, 52], "valid_until": expiry.isoformat(),
           "perimeter_observed_at": (now - timedelta(days=4)).isoformat(), "status": "Being Held",
           "issue_at": now.isoformat(), "valid_at": expiry.isoformat()}
    parent = {"id": device, "layer": layer, "online": True, "live": True, "hotspots": [row]}
    [pin] = expand_map_objects([parent])
    assert pin["id"] == f"{prefix}-sample"
    assert pin["event_geometry"] == shape and pin["event_bbox"] == row["event_bbox"]
    assert source_reading_expiry(pin) == expiry.timestamp()
    detail = build_detail(pin, cached=True, age_ms=0)
    assert ("Perimeter observed" if layer == "wildfire_perimeters" else "Advisory issued") in detail["evidence_boundary"]
    assert expand_map_objects([{**parent, "hotspots": [{**row, "valid_until": now.isoformat()}]}]) == []


@pytest.mark.asyncio
async def test_regional_queries_use_separate_cache_keys_and_reuse_identical_requests(monkeypatch):
    aggregator = Aggregator()
    aggregator._fleet_by_id = {"ndw-ev-charging-01": {"online": True}}
    calls = []

    async def read(device_id, *, regional_bbox):
        calls.append((device_id, regional_bbox))
        await asyncio.sleep(0)
        return {"id": device_id, "values": {"west": regional_bbox[0]}}

    monkeypatch.setattr(aggregator, "_fetch_station_reading", read)
    first, second, duplicate = await asyncio.gather(*[
        aggregator._regional_viewport("ev_charging", bbox, force=False)
        for bbox in ((5.1, 52, 5.2, 52.2), (4.5, 52.3, 4.7, 52.5), (5.1, 52, 5.2, 52.2))
    ])
    assert len(calls) == 2
    assert first == duplicate and first != second
    assert await aggregator._regional_viewport("ev_charging", (-180, -90, 180, 90), force=False) == (None, False)
