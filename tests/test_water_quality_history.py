"""Commercial invariants for the USGS station registry/history store."""

from __future__ import annotations

from atlas.fleet import expand_map_objects
from atlas.water_quality_history import WaterQualityHistoryStore


def _row(*, value: float = 7.2, observed_at: str = "2026-08-27T12:00:00Z"):
    return {
        "station_id": "12345678",
        "name": "Example River",
        "latitude": 38.9,
        "longitude": -77.1,
        "ph": value,
        "observed_at": observed_at,
        "available_parameters": ["ph"],
        "approval_status": "Provisional",
        "qualifiers": ["Ice"],
        "observation_metadata": {
            "ph": {
                "parameter_code": "00400",
                "observed_at": observed_at,
                "approval_status": "Provisional",
                "qualifier": "Ice",
            },
        },
    }


def test_history_is_bounded_deduplicated_persistent_and_uptime_is_poll_based(tmp_path):
    path = tmp_path / "water-quality.json"
    store = WaterQualityHistoryStore(str(path), history_limit=4)
    bbox = (-78.0, 38.0, -76.0, 40.0)

    store.observe(bbox, [_row()], polled_at="2026-08-27T12:00:01Z")
    store.observe(bbox, [_row()], polled_at="2026-08-27T12:05:01Z")
    summary = store.summary("12345678")
    assert summary["observation_uptime_pct"] == 100.0
    assert summary["uptime_checks"] == 2
    assert summary["history_count"] == 1  # redraw/poll did not invent a sample

    store.observe(bbox, [], polled_at="2026-08-27T12:10:01Z")
    assert store.summary("12345678")["observation_uptime_pct"] == 66.67

    store.observe(
        bbox,
        [_row(value=7.3, observed_at="2026-08-27T12:15:00Z")],
        polled_at="2026-08-27T12:15:01Z",
    )
    detail = WaterQualityHistoryStore(str(path), history_limit=4).detail("12345678")
    assert detail["uptime_checks"] == 4
    assert detail["uptime_successful_checks"] == 3
    assert detail["observation_uptime_pct"] == 75.0
    assert [sample["values"]["ph"] for sample in detail["history"]] == [7.2, 7.3]
    assert "fresh ATLAS polls" in detail["uptime_basis"]


def test_water_quality_map_has_one_nonempty_point_per_station():
    parent = {
        "id": "usgs-wq-01",
        "layer": "water_quality",
        "kind": "event",
        "online": True,
        "live": True,
        "source": "https://api.waterdata.usgs.gov",
        "hotspots": [
            _row(),
            _row(value=7.3),  # repeated series/page cannot create a second point
            {
                "station_id": "87654321",
                "latitude": 38.8,
                "longitude": -77.0,
                # registry coordinate but no contracted measurement
            },
        ],
    }

    points = expand_map_objects([parent])
    assert len(points) == 1
    assert points[0]["id"] == "usgs-wq-site-12345678"
    assert (points[0]["lat"], points[0]["lon"]) == (38.9, -77.1)
    assert points[0]["approval_status"] == "Provisional"
    assert points[0]["observation_metadata"]["ph"]["qualifier"] == "Ice"
