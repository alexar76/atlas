"""Typed ATLAS layer counts never confuse a parent SKU with one event."""

from __future__ import annotations

from types import SimpleNamespace

from atlas.layer_counts import build_layer_counts
from atlas.readings import ReadingStore


def test_cluster_layers_use_feed_counts_and_preserve_zero():
    counts = build_layer_counts(
        [
            {
                "id": "eonet-01",
                "layer": "events",
                "online": True,
                "hotspot_count": 100,
                "hotspots": [
                    {"latitude": float(i % 80), "longitude": float(i)} for i in range(100)
                ],
            },
            {
                "id": "glm-01",
                "layer": "lightning",
                "online": True,
                "hotspot_matched": 148,
                "hotspots": [
                    {"latitude": float(i % 80), "longitude": float(i)} for i in range(148)
                ],
            },
            {
                "id": "nws-alerts-01",
                "layer": "alerts",
                "online": True,
                "hotspots": [],
            },
        ],
        ("events", "lightning", "alerts"),
    )
    assert counts["events"]["count"] == 100
    assert counts["events"]["count_kind"] == "events"
    assert counts["lightning"]["count"] == 148
    assert counts["alerts"]["count"] == 0
    assert all(item["status"] == "live" for item in counts.values())


def test_unknown_event_feed_is_not_reported_as_one():
    counts = build_layer_counts(
        [{"id": "effis-01", "layer": "effis", "online": False}],
        ("effis",),
    )
    assert counts["effis"]["count"] is None
    assert counts["effis"]["status"] == "unavailable"
    assert counts["effis"]["total_sources"] == 1


def test_last_known_cluster_is_explicitly_stale():
    counts = build_layer_counts(
        [
            {
                "id": "nws-flood-01",
                "layer": "flood",
                "online": False,
                "hotspot_count": 17,
                "hotspots": [
                    {"latitude": float(i), "longitude": float(i)} for i in range(17)
                ],
            }
        ],
        ("flood",),
    )
    assert counts["flood"]["count"] == 17
    assert counts["flood"]["status"] == "stale"


def test_station_and_feeder_counts_expose_live_over_configured():
    counts = build_layer_counts(
        [
            {"id": "wx-1", "layer": "weather", "online": True, "lat": 1.0, "lon": 2.0},
            {"id": "wx-2", "layer": "weather", "online": False, "lat": 3.0, "lon": 4.0},
            {"id": "feeder", "layer": "iot", "online": False},
        ],
        ("weather", "iot"),
    )
    assert counts["weather"] == {
        "count": 1,
        "count_kind": "stations",
        "status": "partial",
        "live_sources": 1,
        "total_sources": 2,
    }
    assert counts["iot"]["count"] == 0
    assert counts["iot"]["count_kind"] == "sources"
    assert counts["iot"]["status"] == "configured"


def test_online_source_without_map_coordinates_does_not_inflate_count():
    counts = build_layer_counts(
        [{"id": "waiting", "layer": "weather", "online": True}],
        ("weather",),
    )
    assert counts["weather"]["count"] == 0
    assert counts["weather"]["live_sources"] == 1
    assert counts["weather"]["status"] == "configured"


def test_any_layer_with_geographic_array_counts_clickable_rows():
    counts = build_layer_counts(
        [
            {
                "id": "future-grid",
                "layer": "grid",
                "online": True,
                "hotspot_count": 4,
                "hotspots": [
                    {"latitude": 10.0, "longitude": 20.0},
                    {"latitude": 11.0, "longitude": 200.0},
                    {"latitude": 95.0, "longitude": 20.0},  # invalid latitude
                    {"latitude": None, "longitude": 20.0},
                ],
            }
        ],
        ("grid",),
    )
    assert counts["grid"]["count"] == 2
    assert counts["grid"]["count_kind"] == "observations"


def test_space_weather_grid_counts_every_actionable_map_point():
    counts = build_layer_counts(
        [
            {
                "id": "swpc-01",
                "layer": "spacewx",
                "online": True,
                "hotspot_count": 401,
                "hotspots": [
                    {
                        "latitude": float(-80 + (i // 360)),
                        "longitude": float(i % 360),
                    }
                    for i in range(401)
                ],
            }
        ],
        ("spacewx",),
    )
    assert counts["spacewx"]["count"] == 401
    assert counts["spacewx"]["count_kind"] == "observations"


def test_non_fire_metadata_count_without_coordinates_is_unavailable():
    counts = build_layer_counts(
        [
            {
                "id": "glm-01",
                "layer": "lightning",
                "online": True,
                "hotspot_count": 900,
            }
        ],
        ("lightning",),
    )
    assert counts["lightning"]["count"] is None
    assert counts["lightning"]["status"] == "unavailable"


def test_gnss_counts_inventory_when_stations_are_viewport_only():
    """Two GNSS parents on the wire still name the station inventory (§4.2)."""
    counts = build_layer_counts(
        [
            {
                "id": "gnss-euref-01",
                "layer": "gnss",
                "online": True,
                "cluster_parent": True,
                "inventory_total": 400,
                "hotspot_count": 400,
            },
            {
                "id": "gnss-ga-01",
                "layer": "gnss",
                "online": True,
                "cluster_parent": True,
                "inventory_total": 120,
                "hotspot_count": 120,
            },
        ],
        ("gnss",),
    )
    assert counts["gnss"]["count"] == 520
    assert counts["gnss"]["count_kind"] == "stations"
    assert counts["gnss"]["total_sources"] == 2
    assert counts["gnss"]["count"] != counts["gnss"]["total_sources"]


def test_non_paged_layer_count_never_exceeds_clickable_coordinates():
    counts = build_layer_counts(
        [
            {
                "id": "swpc-01",
                "layer": "spacewx",
                "online": True,
                "hotspot_matched": 401,
                "hotspot_count": 401,
                "hotspots": [{"latitude": 80.0, "longitude": 10.0}] * 400,
            }
        ],
        ("spacewx",),
    )
    assert counts["spacewx"]["count"] == 400


def test_transient_failure_keeps_only_last_known_cluster_count():
    store = ReadingStore(SimpleNamespace(reading_ttl_s=30.0))  # type: ignore[arg-type]
    store.put(
        "effis-01",
        {
            "id": "effis-01",
            "layer": "effis",
            "online": True,
            "hotspot_matched": 372,
            "hotspot_count": 25,
            "hotspots": [{"latitude": 1.0, "longitude": 2.0}],
        },
    )
    store.put("effis-01", {"id": "effis-01", "layer": "effis", "online": False})
    cached = store.get_station("effis-01")
    assert cached is not None
    assert cached["online"] is False
    assert cached["hotspot_matched"] == 372
    assert cached["hotspot_count"] == 25
