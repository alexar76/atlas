"""Transport map pins retain geometry only while the source notice is usable."""

from datetime import UTC, datetime, timedelta

from atlas.fleet import expand_map_objects
from atlas.formatters import build_detail
from atlas.map_objects import is_fresh_cluster_observation, without_expired_source_reading


def test_road_shape_requires_recent_feed_fetch_even_for_open_end():
    now = datetime.now(UTC)
    geometry = {"type": "LineString", "coordinates": [[25, 60], [26, 60.2]]}
    parent = {
        "id": "fintraffic-roadworks-01", "layer": "road_events",
        "source_read_at": (now - timedelta(minutes=2)).isoformat(),
        "hotspots": [{
            "event_id": "GUID123", "title": "Road 101", "notice_text": "Work on the bridge.",
            "latitude": 60, "longitude": 25, "valid_from": (now - timedelta(days=3)).isoformat(),
            "geometry": geometry, "event_bbox": [25, 60, 26, 60.2], "claim_class": "published_road_notice",
        }],
    }
    [point] = expand_map_objects([parent])
    assert point["id"] == "road-notice-GUID123"
    assert point["event_geometry"] == geometry
    assert point["event_bbox"] == [25, 60, 26, 60.2]
    detail = build_detail(point, cached=True, age_ms=0)
    assert detail["title"] == "Road 101"
    assert "Work on the bridge." in detail["summary"]
    assert "open-ended" in detail["evidence_boundary"]

    parent["source_read_at"] = (now - timedelta(minutes=31)).isoformat()
    assert expand_map_objects([parent]) == []


def test_ndw_source_snapshot_expiry_is_distinct_from_road_validity():
    now = datetime.now(UTC)
    published, expires = now - timedelta(minutes=1), now + timedelta(minutes=4)
    geometry = {"type": "LineString", "coordinates": [[5, 52], [5.2, 52.1]]}
    parent_id = "ndw-road-closures-01"
    timing = {"source_published_at": published.isoformat(), "source_expires_at": expires.isoformat()}
    row = {**timing, "event_id": "ndw-1", "title": "Lane closure", "latitude": 52, "longitude": 5,
           "valid_from": (now - timedelta(hours=1)).isoformat(), "valid_until": (now + timedelta(hours=1)).isoformat(),
           "geometry": geometry, "event_bbox": [5, 52, 5.2, 52.1], "claim_class": "published_road_notice"}
    parent = {**timing, "id": parent_id, "layer": "road_events", "hotspots": [row],
              "values": {"transport_notice_count": 1}, "hotspot_count": 1, "online": True}
    [point] = expand_map_objects([parent])
    assert point["event_geometry"] == geometry
    assert point["source_expires_at"] == expires.isoformat()
    assert point["valid_until"] == row["valid_until"]
    detail = build_detail(point, cached=True, age_ms=0)
    assert "NDW notice" in detail["blurb"] and "Fintraffic" not in detail["summary"]
    assert is_fresh_cluster_observation(parent_id, row, now=now)
    assert not is_fresh_cluster_observation(parent_id, row, now=expires)
    assert not without_expired_source_reading(parent, now=expires.timestamp())["online"]
    assert without_expired_source_reading(parent, now=expires.timestamp())["hotspots"] == []
