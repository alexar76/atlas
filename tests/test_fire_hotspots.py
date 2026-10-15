"""FIRMS hotspot fan-out on ATLAS Wildfire layer."""

from __future__ import annotations

from atlas.fleet import expand_fire_hotspots


def test_expand_fire_hotspots_fans_cluster():
    parent = {
        "id": "firms-fire-01",
        "layer": "fire",
        "label": "NASA FIRMS Fire",
        "online": True,
        "mode": "live",
        "live": True,
        "source": "https://firms.modaps.eosdis.nasa.gov",
        "values": {"brightness_k": 380.0, "confidence": 90.0, "latitude": 35.0, "longitude": -120.0},
        "headline": "Fire 380 K",
        "color": "#ff6b35",
        "has_reading": True,
        "hotspots": [
            {"brightness_k": 380.0, "confidence": 90.0, "latitude": 35.0, "longitude": -120.0},
            {"brightness_k": 330.5, "confidence": 50.0, "latitude": 34.1, "longitude": -118.2},
        ],
    }
    other = {
        "id": "om-wx-01",
        "layer": "weather",
        "lat": 52.5,
        "lon": 13.4,
        "online": True,
    }
    out = expand_fire_hotspots([other, parent])
    fire = [s for s in out if s["layer"] == "fire"]
    assert len(fire) == 2
    # Coordinate-derived ids: stable across densifies so the client point cache
    # merges the same detection instead of colliding on per-camera indices.
    assert {s["id"] for s in fire} == {
        "firms-hs-ff01-350000_-1200000",
        "firms-hs-ff01-341000_-1182000",
    }
    assert all(s.get("parent_id") == "firms-fire-01" for s in fire)
    assert "firms-fire-01" not in {s["id"] for s in out}
    assert any(s["id"] == "om-wx-01" for s in out)


def test_expand_fire_keeps_sku_without_cluster():
    parent = {
        "id": "firms-fire-01",
        "layer": "fire",
        "lat": 1.0,
        "lon": 2.0,
        "values": {},
    }
    out = expand_fire_hotspots([parent])
    assert len(out) == 1
    assert out[0]["id"] == "firms-fire-01"


def test_explicit_empty_cluster_never_becomes_fake_parent_point():
    parent = {
        "id": "nws-alerts-01",
        "layer": "alerts",
        "lat": 38.0,
        "lon": -77.0,
        "online": True,
        "hotspots": [],
        "hotspot_count": 0,
    }
    assert expand_fire_hotspots([parent]) == []


def test_unknown_future_cluster_is_automatically_clickable():
    parent = {
        "id": "future-grid-01",
        "layer": "grid",
        "label": "Future grid mesh",
        "online": True,
        "live": True,
        "hotspots": [
            {"demand_mw": 101.0, "latitude": 1.0, "longitude": 359.0},
            {"demand_mw": 99.0, "lat": 0.0, "lon": 0.0},
        ],
    }
    points = expand_fire_hotspots([parent])
    assert len(points) == 2
    assert all(str(point["id"]).startswith("atlas-pt-") for point in points)
    assert points[0]["lon"] == -1.0
    assert points[1]["lat"] == 0.0 and points[1]["lon"] == 0.0
    assert points[0]["values"]["demand_mw"] == 101.0


def test_expand_false_keeps_parent_without_fanout():
    parent = {
        "id": "firms-fire-01",
        "layer": "fire",
        "hotspots": [
            {"brightness_k": 380.0, "confidence": 90.0, "latitude": 35.0, "longitude": -120.0},
            {"brightness_k": 330.5, "confidence": 50.0, "latitude": 34.1, "longitude": -118.2},
        ],
    }
    out = expand_fire_hotspots([parent], expand=False)
    assert len(out) == 1
    assert out[0]["id"] == "firms-fire-01"
    assert "hotspots" not in out[0]


def test_expand_radiation_hotspots():
    parent = {
        "id": "safecast-tokyo",
        "layer": "radiation",
        "label": "Safecast · Tokyo",
        "live": True,
        "mode": "live",
        "hotspots": [
            {
                "cpm": 42.0,
                "latitude": 35.67,
                "longitude": 139.65,
                "captured_at": "2014-03-29T08:57:39.000Z",
            },
            {"cpm": 38.0, "latitude": 35.70, "longitude": 139.70},
        ],
    }
    out = expand_fire_hotspots([parent])
    rad = [s for s in out if s["layer"] == "radiation"]
    assert len(rad) == 2
    assert all(s["id"].startswith("rad-hs-") for s in rad)
    assert rad[0]["values"]["cpm"] == 42.0
    assert rad[0]["captured_at"].startswith("2014-")


def test_expand_eonet_hotspots():
    parent = {
        "id": "eonet-01",
        "layer": "events",
        "live": True,
        "mode": "live",
        "hotspots": [
            {"severity_score": 85.0, "latitude": 19.4, "longitude": -155.2, "title": "Kilauea"},
            {"severity_score": 70.0, "latitude": 25.0, "longitude": -80.0, "title": "Storm"},
        ],
    }
    out = expand_fire_hotspots([parent])
    ev = [s for s in out if s["layer"] == "events"]
    assert len(ev) == 2
    assert all(s["id"].startswith("eonet-ev-") for s in ev)


def test_expand_space_weather_grid_into_clickable_points():
    parent = {
        "id": "swpc-01",
        "layer": "spacewx",
        "label": "NOAA SWPC Space Weather",
        "live": True,
        "mode": "live",
        "hotspots": [
            {"kp_index": 5.0, "aurora_pct": 72.0, "latitude": 67.2, "longitude": 25.1},
            # NOAA OVATION publishes 0..360 longitude; this cell is 3° W.
            {"kp_index": 5.0, "aurora_pct": 18.0, "latitude": 54.5, "longitude": 357.0},
        ],
    }
    out = expand_fire_hotspots([parent])
    points = [s for s in out if s["layer"] == "spacewx"]
    assert len(points) == 2
    assert all(s["id"].startswith("swpc-hs-") for s in points)
    assert all(s["parent_id"] == "swpc-01" for s in points)
    assert points[0]["values"]["aurora_pct"] == 72.0
    assert points[0]["headline"] == "Kp 5"
    assert points[1]["lon"] == -3.0
    assert points[1]["values"]["longitude"] == -3.0
    assert points[1]["id"] == "swpc-hs-sw01-545000_-30000"


def test_expand_effis_hotspots_keeps_area_ha():
    parent = {
        "id": "effis-01",
        "layer": "effis",
        "live": True,
        "mode": "live",
        "hotspots": [
            {
                "severity_score": 80.0,
                "latitude": 41.4,
                "longitude": 2.1,
                "area_ha": 1200.0,
                "firedate": "2026-08-12",
            },
            {
                "severity_score": 50.0,
                "latitude": 40.0,
                "longitude": 0.5,
                "area_ha": 400.0,
            },
        ],
    }
    out = expand_fire_hotspots([parent])
    fires = [s for s in out if s["layer"] == "effis"]
    assert len(fires) == 2
    assert all(s["id"].startswith("effis-hs-") for s in fires)
    assert all(s.get("parent_id") == "effis-01" for s in fires)
    areas = {s.get("area_ha") for s in fires}
    assert areas == {1200.0, 400.0}


def test_expand_lightning_flood_volcano_alerts_clusters():
    parents = [
        {
            "id": "glm-01",
            "layer": "lightning",
            "live": True,
            "hotspots": [
                {"energy_fj": 12.5, "latitude": 25.0, "longitude": -80.0},
                {"energy_fj": 8.0, "latitude": 25.1, "longitude": -80.1},
            ],
        },
        {
            "id": "nws-flood-01",
            "layer": "flood",
            "live": True,
            "hotspots": [
                {"severity_score": 80.0, "latitude": 35.0, "longitude": -90.0},
            ],
        },
        {
            "id": "usgs-volcano-01",
            "layer": "volcano",
            "live": True,
            "hotspots": [
                {"severity_score": 80.0, "latitude": 19.4, "longitude": -155.2, "name": "Kilauea"},
            ],
        },
        {
            "id": "nws-alerts-01",
            "layer": "alerts",
            "live": True,
            "hotspots": [
                {"severity_score": 95.0, "latitude": 35.5, "longitude": -97.5, "event": "Tornado"},
            ],
        },
    ]
    out = expand_fire_hotspots(parents)
    by_layer = {}
    for pin in out:
        by_layer.setdefault(pin["layer"], []).append(pin)
    assert len(by_layer["lightning"]) == 2
    assert all(p["id"].startswith("glm-hs-") for p in by_layer["lightning"])
    assert by_layer["flood"][0]["id"].startswith("flood-hs-")
    assert by_layer["volcano"][0]["id"].startswith("volc-ev-")
    assert by_layer["alerts"][0]["id"].startswith("cap-ev-")
    assert by_layer["volcano"][0].get("name") == "Kilauea"
