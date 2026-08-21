"""ATLAS composite product SKUs."""

from __future__ import annotations

from atlas.products import (
    fire_weather,
    invoke_product,
    nearest_read,
    point_read,
    situation_brief,
    watchbox_check,
)
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
        "observed_at": "2026-08-11T12:05:00Z",
        "satellite": "N",
    }


def _air(lat: float, lon: float) -> dict:
    return {
        "id": "air-test",
        "layer": "air",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "values": {"pm2_5_ugm3": 12.0},
        "source": "https://example.test/air",
    }


def test_fire_weather_refuses_without_live_fire():
    stations = [_wx(34.0, -118.0, temperature_c=28, humidity_pct=20, wind_mps=9)]
    out = fire_weather(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is False
    assert "LIVE fire" in out["refuse_reason"]
    assert "EFFIS" in out["refuse_reason"]


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
    assert out["hotspots"][0]["observed_at"] == "2026-08-11T12:05:00Z"
    assert out["hotspots"][0]["satellite"] == "N"
    assert out["artifact_type"] == "evidence_snapshot"
    assert "score" not in out
    assert out["evidence"]["nearby_weather_available"] is True
    assert "not confirmed incident perimeters" in " ".join(out["limitations"])
    assert out["receipt"]["digest"]
    assert "NASA FIRMS" in out["attribution"]


def test_fire_weather_excludes_remote_weather_context():
    stations = [
        _fire(0, 34.1, -118.2, 380),
        _wx(40.71, -74.0, temperature_c=31, humidity_pct=18, wind_mps=12),
    ]
    out = fire_weather(
        {
            "west": -120,
            "south": 32,
            "east": -116,
            "north": 36,
            "max_weather_km": 100,
        },
        stations,
    )
    assert out["ok"] is True
    assert out["weather"] is None
    assert out["weather_distance_km"] is None
    assert out["evidence"]["nearby_weather_available"] is False
    assert out["nearest_weather_candidate"]["id"] == "om-wx-test"
    assert out["nearest_weather_candidate_distance_km"] > 100


def test_fire_weather_clamps_zero_distance_bound_in_direct_calls():
    stations = [
        _fire(0, 34.1, -118.2, 380),
        _wx(34.12, -118.18, temperature_c=31, humidity_pct=18, wind_mps=12),
    ]
    out = fire_weather(
        {
            "west": -120,
            "south": 32,
            "east": -116,
            "north": 36,
            "max_weather_km": 0,
        },
        stations,
    )
    assert out["max_weather_km"] == 1.0
    assert out["weather"] is None


def test_fire_weather_excludes_remote_optional_air_context():
    stations = [
        _fire(0, 34.1, -118.2, 380),
        _wx(34.05, -118.25, temperature_c=31, humidity_pct=18, wind_mps=12),
        _air(40.71, -74.0),
    ]
    out = fire_weather(
        {
            "west": -120,
            "south": 32,
            "east": -116,
            "north": 36,
            "include_air": True,
            "max_air_km": 100,
        },
        stations,
    )
    assert out["ok"] is True
    assert out["air"] is None
    assert out["air_distance_km"] is None
    assert out["nearest_air_candidate"]["id"] == "air-test"
    assert any("beyond max_air_km" in driver for driver in out["drivers"])


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
    assert out["nearest"]["point_invoke"]["capability_id"] == "atlas.point.read@v1"
    assert out["nearest"]["point_invoke"]["input"]["point_id"] == "om-wx-test"


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


def test_point_read_exact_catalog_sensor():
    point = {
        **_wx(52.52, 13.41, temperature_c=18.0),
        "id": "om-wx-01",
        "title": "Open-Meteo Weather",
        "metrics": [{"key": "temperature_c", "value": "18 °C"}],
        "upstream_evidence": {
            "device_id": "om-wx-01",
            "seq": 7,
            "attestation": {"algorithm": "ed25519", "value": "signed"},
        },
    }
    out = point_read({"point_id": "om-wx-01", "fresh": True}, [point])
    assert out["ok"] is True
    assert out["point_id"] == "om-wx-01"
    assert out["point"]["values"]["temperature_c"] == 18.0
    assert out["point"]["upstream_evidence"]["attestation"]["algorithm"] == "ed25519"
    assert out["parent_capability"]["capability_id"] == "gaia.weather.read@v1"
    assert out["parent_capability"]["targeting"] == "exact"
    assert out["resolution"]["kind"] == "source_addressable_read"
    assert out["receipt"]["capability_id"] == "atlas.point.read@v1"


def test_point_read_exact_event_explains_parent_snapshot_boundary():
    point = _fire(7, 34.1, -118.2, 381)
    out = invoke_product(
        "atlas.point.read@v1",
        {"point_id": point["id"]},
        [point],
    )
    assert out["ok"] is True
    assert out["point"]["id"] == point["id"]
    assert out["parent_capability"]["capability_id"] == "gaia.fire.read@v1"
    assert out["parent_capability"]["targeting"] == "parent_cluster"
    assert out["resolution"]["kind"] == "source_snapshot_selection"
    assert "not an individual event" in out["resolution"]["evidence_boundary"]


def test_point_read_refuses_unknown_id():
    out = point_read({"point_id": "no-such-point"}, [])
    assert out["ok"] is False
    assert out["point_id"] == "no-such-point"
    assert "not found" in out["refuse_reason"]


def _pin(i: str, layer: str, lat: float, lon: float, **vals: float) -> dict:
    return {
        "id": i,
        "layer": layer,
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": layer,
        "values": vals,
        "headline": layer,
        "source": f"https://example.test/{layer}",
    }


def _effis(i: int, lat: float, lon: float, area_ha: float) -> dict:
    return {
        "id": f"effis-fire-{i:04d}",
        "parent_id": "effis-eu-01",
        "layer": "effis",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": "EFFIS",
        "values": {"area_ha": area_ha, "severity_score": 3.0},
        "headline": f"EFFIS {area_ha:.0f} ha",
        "source": "https://effis.jrc.ec.europa.eu",
        "area_ha": area_ha,
        "attribution": "Copernicus EMS / JRC — CC BY 4.0",
    }


def test_fire_weather_accepts_effis_only():
    stations = [
        _effis(0, 41.4, 2.1, 1200),
        _wx(41.38, 2.17, temperature_c=29, humidity_pct=22, wind_mps=8),
    ]
    out = fire_weather(
        {"west": 1.5, "south": 41.0, "east": 2.8, "north": 42.0},
        stations,
    )
    assert out["ok"] is True
    assert out["hotspot_count"] == 0
    assert out["effis_count"] == 1
    assert out["effis_fires"][0]["id"] == "effis-fire-0000"
    assert out["evidence"]["live_effis_count"] == 1
    assert out["evidence"]["live_fire_detection_count"] == 0
    assert "Copernicus" in out["attribution"]
    assert "NASA FIRMS" not in out["attribution"]
    assert out["weather"]["id"] == "om-wx-test"
    assert "not a fire perimeter" in out["summary"].lower() or "not a fire perimeter" in " ".join(
        out["limitations"]
    ).lower()


def test_fire_weather_fuses_firms_and_effis_separately():
    stations = [
        _fire(0, 41.4, 2.1, 390),
        _effis(0, 41.41, 2.12, 800),
        _wx(41.38, 2.17, temperature_c=31, humidity_pct=18, wind_mps=11),
    ]
    out = fire_weather(
        {"west": 1.5, "south": 41.0, "east": 2.8, "north": 42.0},
        stations,
    )
    assert out["ok"] is True
    assert out["hotspot_count"] == 1
    assert out["effis_count"] == 1
    assert "NASA FIRMS" in out["attribution"]
    assert "Copernicus" in out["attribution"]
    assert "score" not in out


def test_fire_weather_refuses_when_neither_firms_nor_effis():
    stations = [_wx(41.4, 2.1, temperature_c=28, humidity_pct=20, wind_mps=9)]
    out = fire_weather(
        {"west": 1.5, "south": 41.0, "east": 2.8, "north": 42.0},
        stations,
    )
    assert out["ok"] is False
    assert "LIVE fire" in out["refuse_reason"]
    assert "EFFIS" in out["refuse_reason"]


def test_situation_brief_default_includes_p0_p1_layers():
    stations = [
        _pin("nws-flood-01", "flood", 34.05, -118.25, severity_score=2.0),
        _effis(0, 34.1, -118.2, 450),
        _pin("glm-ltng-01", "lightning", 34.08, -118.22, energy_fj=1.2e-6),
        _pin("usgs-volcano-01", "volcano", 34.2, -118.3, severity_score=1.0),
        _wx(34.0, -118.0, temperature_c=28, humidity_pct=30, wind_mps=6),
    ]
    out = situation_brief(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is True
    for layer in ("flood", "effis", "lightning", "volcano"):
        assert layer in out["layers"]
        assert out["coverage"][layer]["live"] >= 1
    cited_layers = {c.get("layer") for c in out["citations"]}
    assert {"flood", "effis", "lightning", "volcano"} <= cited_layers
    assert any(d.startswith("flood:") for d in out["drivers"])
    assert any(d.startswith("effis:") for d in out["drivers"])
    assert any(d.startswith("lightning:") for d in out["drivers"])
    assert any(d.startswith("volcano:") for d in out["drivers"])


def test_situation_brief_flood_river_pairing():
    stations = [
        _pin("nws-flood-01", "flood", 34.05, -118.25, severity_score=2.0),
        _pin("usgs-river-01", "river", 34.06, -118.24, gage_height_ft=8.1),
    ]
    out = situation_brief(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is True
    assert any("flood alerts + river" in d for d in out["drivers"])
    assert any("not a flood model" in d for d in out["drivers"])


def test_situation_brief_lightning_fire_is_copresence_not_ignition():
    stations = [
        _fire(0, 34.1, -118.2, 360),
        _pin("glm-ltng-01", "lightning", 34.08, -118.22, energy_fj=2.0e-6),
    ]
    out = situation_brief(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is True
    joined = " ".join(out["drivers"]).lower()
    assert "lightning + fire" in joined
    assert "ignition" in joined
    assert "risk" not in joined
    assert "caused" not in joined


def test_situation_brief_default_excludes_spacewx_geomag_argo():
    stations = [
        _pin("swpc-kp-01", "spacewx", 40.0, -105.3, kp_index=5.0),
        _pin("usgs-geomag-01", "geomag", 40.1, -105.2, f_nt=52000),
        _pin("argo-01", "argo", 40.05, -105.25, temperature_c=4.2),
    ]
    out = situation_brief(
        {"west": -106, "south": 39.5, "east": -104.5, "north": 40.7},
        stations,
    )
    assert out["ok"] is False
    for layer in ("spacewx", "geomag", "argo"):
        assert layer not in (out.get("layers") or [])


def test_situation_brief_default_includes_alerts_events_excludes_energy_iot():
    stations = [
        _pin("nws-alerts-01", "alerts", 34.05, -118.25, severity_score=80.0),
        _pin("eonet-01", "events", 34.1, -118.2, severity_score=70.0),
        _pin("ws-energy-01", "energy", 34.0, -118.1, kwh=1.2),
        _pin("feeder-iot-01", "iot", 34.02, -118.12, temperature_c=22.0),
    ]
    out = situation_brief(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is True
    for layer in ("alerts", "events"):
        assert layer in out["layers"]
        assert out["coverage"][layer]["live"] >= 1
    for layer in ("energy", "iot"):
        assert layer not in out["layers"]
        assert layer not in (out.get("coverage") or {})


def test_fire_weather_sorts_firms_by_brightness_effis_by_area():
    stations = [
        _fire(0, 41.40, 2.10, 330),
        _fire(1, 41.41, 2.11, 390),
        _effis(0, 41.42, 2.12, 400),
        _effis(1, 41.43, 2.13, 1200),
        _wx(41.38, 2.17, temperature_c=30, humidity_pct=20, wind_mps=8),
    ]
    out = fire_weather(
        {"west": 1.5, "south": 41.0, "east": 2.8, "north": 42.0},
        stations,
    )
    assert out["ok"] is True
    assert out["hotspots"][0]["id"] == "firms-hs-0001"
    assert out["effis_fires"][0]["id"] == "effis-fire-0001"
    assert out["hotspots"][0]["layer"] == "fire"
    assert out["effis_fires"][0]["layer"] == "effis"


def test_fire_weather_firms_only_omits_copernicus_attribution():
    stations = [
        _fire(0, 34.1, -118.2, 380),
        _wx(34.05, -118.25, temperature_c=31, humidity_pct=18, wind_mps=12),
    ]
    out = fire_weather(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        stations,
    )
    assert out["ok"] is True
    assert "NASA FIRMS" in out["attribution"]
    assert "Copernicus" not in out["attribution"]
    assert out["effis_count"] == 0
    assert out["effis_fires"] == []
    assert "score" not in out


def test_fire_weather_refuses_sim_fire_and_null_island():
    sim = _fire(0, 34.1, -118.2, 380)
    sim["live"] = False
    sim["mode"] = "sim"
    null_island = _effis(0, 0.0, 0.0, 900)
    out = fire_weather(
        {"west": -120, "south": 32, "east": -116, "north": 36},
        [sim, null_island, _wx(34.0, -118.0, temperature_c=28, humidity_pct=20, wind_mps=9)],
    )
    assert out["ok"] is False
    assert "EFFIS" in out["refuse_reason"]
