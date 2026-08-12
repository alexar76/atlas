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
            {"cpm": 42.0, "latitude": 35.67, "longitude": 139.65},
            {"cpm": 38.0, "latitude": 35.70, "longitude": 139.70},
        ],
    }
    out = expand_fire_hotspots([parent])
    rad = [s for s in out if s["layer"] == "radiation"]
    assert len(rad) == 2
    assert all(s["id"].startswith("rad-hs-") for s in rad)
    assert rad[0]["values"]["cpm"] == 42.0
