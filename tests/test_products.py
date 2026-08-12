"""ATLAS composite product SKUs."""

from __future__ import annotations

from atlas.products import fire_weather, invoke_product, nearest_read, situation_brief, watchbox_check
from atlas.watchboxes import STORE


def _wx(lat: float, lon: float, **vals: float) -> dict:
    return {
        "id": "om-wx-test",
        "layer": "weather",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": "Test",
        "values": vals,
        "headline": "wx",
        "source": "https://api.open-meteo.com",
    }


def _fire(i: int, lat: float, lon: float, bright: float) -> dict:
    return {
        "id": f"firms-hs-{i:04d}",
        "parent_id": "firms-fire-01",
        "layer": "fire",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": "Hotspot",
        "values": {"brightness_k": bright, "confidence": 90, "latitude": lat, "longitude": lon},
        "headline": f"Fire {bright:.0f} K",
        "source": "https://firms.modaps.eosdis.nasa.gov",
    }


def test_fire_weather_refuses_without_live_fire():
    stations = [_wx(34.0, -118.0, temperature_c=28, humidity_pct=20, wind_mps=9)]
    out = fire_weather(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is False
    assert "LIVE fire" in out["refuse_reason"]


def test_fire_weather_fuses_weather():
    stations = [
        _fire(0, 34.1, -118.2, 380),
        _fire(1, 34.2, -118.1, 330),
        _wx(34.05, -118.25, temperature_c=31, humidity_pct=18, wind_mps=12),
    ]
    out = fire_weather(
        {"west": -120, "south": 32, "east": -116, "north": 36, "limit": 10},
        stations,
    )
    assert out["ok"] is True
    assert out["hotspot_count"] == 2
    assert out["weather"]["id"] == "om-wx-test"
    assert out["score"] >= 40
    assert out["receipt"]["digest"]
    assert "NASA FIRMS" in out["attribution"]


def test_situation_brief_cross_layer():
    stations = [
        _fire(0, 34.1, -118.2, 360),
        _wx(34.0, -118.0, temperature_c=30, humidity_pct=25, wind_mps=10),
        {
            "id": "usgs-quake-01",
            "layer": "quake",
            "live": True,
            "has_reading": True,
            "lat": 34.3,
            "lon": -118.4,
            "values": {"magnitude": 4.2, "latitude": 34.3, "longitude": -118.4},
            "headline": "Magnitude 4.2",
            "source": "https://earthquake.usgs.gov",
        },
    ]
    out = situation_brief(
        {
            "west": -120,
            "south": 32,
            "east": -116,
            "north": 36,
            "layers": ["fire", "weather", "quake"],
        },
        stations,
    )
    assert out["ok"] is True
    assert out["live_count"] >= 2
    assert any("fire + weather" in d for d in out["drivers"])
    assert out["receipt"]["capability_id"] == "atlas.situation.brief@v1"


def test_situation_brief_refuses_empty():
    out = situation_brief(
        {"west": 10, "south": 10, "east": 11, "north": 11, "layers": ["fire"]},
        [],
    )
    assert out["ok"] is False


def test_watchbox_check_ephemeral(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "atlas.products.STORE",
        STORE.__class__(path=tmp_path / "wb.json"),
    )
    stations = [_fire(0, 34.1, -118.2, 350)]
    out = watchbox_check(
        {
            "west": -120,
            "south": 32,
            "east": -116,
            "north": 36,
            "layers": ["fire"],
        },
        stations,
    )
    assert out["ok"] is True
    assert out["match_count"] == 1
    assert out["sku"] == "atlas.watchbox.check@v1"


def test_invoke_router():
    out = invoke_product("atlas.nope@v1", {}, [])
    assert out["ok"] is False


def test_nearest_read_picks_closest_live():
    stations = [
        _wx(52.52, 13.41, temperature_c=18.0),
        {
            **_wx(48.85, 2.35, temperature_c=22.0),
            "id": "om-wx-paris",
            "place": "Paris",
        },
        {
            **_wx(40.7, -74.0, temperature_c=25.0),
            "id": "om-wx-nyc",
            "live": False,
            "mode": "sim",
        },
    ]
    # Near Berlin
    out = nearest_read({"lat": 52.5, "lon": 13.4, "layer": "weather"}, stations)
    assert out["ok"] is True
    assert out["nearest"]["id"] == "om-wx-test"
    assert out["distance_km"] < 5
    assert out["values"]["temperature_c"] == 18.0
    assert out["receipt"]["capability_id"] == "atlas.nearest.read@v1"


def test_nearest_read_refuses_too_far():
    stations = [_wx(52.52, 13.41, temperature_c=18.0)]
    out = nearest_read(
        {"lat": -33.9, "lon": 151.2, "layer": "weather", "max_km": 100},
        stations,
    )
    assert out["ok"] is False
    assert "within" in out["refuse_reason"]


def test_nearest_read_per_layer():
    stations = [
        _wx(34.05, -118.25, temperature_c=30.0),
        _fire(0, 34.1, -118.2, 350),
    ]
    out = nearest_read(
        {
            "lat": 34.05,
            "lon": -118.25,
            "layers": ["weather", "fire"],
            "per_layer": True,
            "max_km": 50,
        },
        stations,
    )
    assert out["ok"] is True
    assert out["hit_count"] == 2
    assert out["nearest_by_layer"]["weather"]["id"] == "om-wx-test"
    assert out["nearest_by_layer"]["fire"]["id"].startswith("firms-hs-")


def test_invoke_nearest_sku():
    stations = [_wx(52.52, 13.41, temperature_c=11.0)]
    out = invoke_product(
        "atlas.nearest.read@v1",
        {"lat": 52.5, "lon": 13.4},
        stations,
    )
    assert out["ok"] is True
    assert out["sku"] == "atlas.nearest.read@v1"
