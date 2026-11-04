"""ATLAS preserves provider validity, identities and source-specific reading semantics."""

from datetime import UTC, datetime, timedelta

import pytest

from atlas.aggregator import Aggregator
from atlas.fleet import expand_map_objects
from atlas.formatters import build_detail, headline
from atlas.layer_counts import build_layer_counts
from atlas.map_objects import normalized_hotspots, source_reading_expiry


def test_toronto_road_pin_uses_source_geometry_and_active_window():
    now = datetime.now(UTC)
    published = (now - timedelta(minutes=1)).isoformat()
    expires = (now + timedelta(minutes=14)).isoformat()
    end = (now + timedelta(minutes=3)).isoformat()
    geometry = {"type": "LineString", "coordinates": [[-79.4, 43.6], [-79.39, 43.61]]}
    row = {"latitude": 43.6, "longitude": -79.4, "event_id": "Tor-25",
           "title": "Toronto · Pape Ave", "notice_type": "Lane restriction",
           "claim_class": "published_road_notice", "geometry": geometry,
           "event_bbox": [-79.4, 43.6, -79.39, 43.61],
           "valid_from": published, "valid_until": end, "issue_at": published}
    parent = {"id": "toronto-road-restrictions-01", "layer": "road_events", "online": True,
              "source_published_at": published, "source_expires_at": expires, "hotspots": [row]}
    [pin] = expand_map_objects([parent])
    assert pin["id"] == "toronto-road-notice-Tor-25"
    assert pin["event_geometry"] == geometry
    assert source_reading_expiry(pin) == datetime.fromisoformat(end).timestamp()
    assert "City of Toronto" in build_detail(pin, cached=False, age_ms=0)["summary"]
    assert expand_map_objects([{**parent, "hotspots": [{**row, "valid_until": published}]}]) == []


def test_complete_outage_snapshot_can_report_zero_and_retires_restored_point():
    now = datetime.now(UTC)
    source_times = {"source_published_at": (now - timedelta(minutes=1)).isoformat(),
                    "source_expires_at": (now + timedelta(minutes=29)).isoformat()}
    parent = {"id": "ukpn-live-faults-01", "layer": "power_outages", "live": True,
              "online": True, **source_times, "values": {"power_outage_count": 0}, "hotspots": []}
    counts = build_layer_counts([parent], ["power_outages"])
    assert counts["power_outages"]["count"] == 0
    assert counts["power_outages"]["status"] == "live"
    assert expand_map_objects([parent]) == []


@pytest.mark.asyncio
async def test_superseded_point_does_not_fall_back_to_a_recently_served_cache():
    now = datetime.now(UTC)
    published = (now - timedelta(minutes=1)).isoformat()
    expires = (now + timedelta(minutes=29)).isoformat()
    parent = {"id": "ukpn-live-faults-01", "layer": "power_outages", "live": True,
              "online": True, "source_published_at": published, "source_expires_at": expires,
              "hotspots": [{"latitude": 51.5, "longitude": -0.1, "incident_id": "INCD-1",
                            "title": "UKPN · Unplanned outage", "outage_type": "Unplanned",
                            "incident_status": "In progress", "customers_affected": 12}]}
    [pin] = expand_map_objects([parent])
    agg = Aggregator()
    agg._remember_map_points([pin])
    agg._store.put(parent["id"], {**parent, "hotspots": []})
    card = await agg.station_detail(pin["id"])
    assert card["dropped"] is True
    assert card["has_reading"] is False


def test_bike_and_drifter_age_is_based_on_the_actual_observation():
    now = datetime.now(UTC)
    current, old = (now - timedelta(minutes=1)), (now - timedelta(hours=7))
    bike = {"id": "toronto-bikeshare-01", "layer": "bikeshare", "online": True,
            "hotspots": [{"station_id": "7000", "title": "Fort York", "latitude": 43.6,
                          "longitude": -79.4, "observed_at": current.isoformat(),
                          "observation_unix": current.timestamp(),
                          "valid_until": (current + timedelta(minutes=5)).isoformat(),
                          "bikes_available": 0, "docks_available": 6}]}
    [pin] = expand_map_objects([bike])
    assert pin["id"] == "toronto-bike-st-7000"
    assert pin["headline"] == "0 bikes · 6 docks"
    assert build_layer_counts([bike], ["bikeshare"])["bikeshare"]["count_kind"] == "stations"

    drifters = {"id": "aoml-drifters-01", "layer": "ocean_drifters", "hotspots": [
        {"platform_code": "21724", "latitude": 15, "longitude": 127, "sst_c": 29.6,
         "observation_unix": current.timestamp(), "observed_at": current.isoformat()},
        {"platform_code": "21725", "latitude": 16, "longitude": 127, "sst_c": 29.5,
         "observation_unix": old.timestamp(), "observed_at": old.isoformat()},
    ]}
    assert len(normalized_hotspots(drifters)) == 1
    [drifter] = expand_map_objects([drifters])
    assert drifter["id"] == "aoml-drifter-21724"
    assert drifter["headline"] == "Sea surface 29.6 °C"


def test_fixed_readings_preserve_the_vertical_reference_and_expire():
    now = datetime.now(UTC).timestamp()
    assert headline("tide", {"water_level_nn2000_m": -0.494}) == "Water -0.494 m NN2000"
    assert headline("bridge_clearance", {"air_gap_m": 54.781}) == "Clearance 54.78 m"
    station = {"id": "noaa-airgap-8726371", "values": {"observation_unix": now}}
    assert source_reading_expiry(station) == now + 18 * 60
