"""ATLAS composite product SKUs."""

from __future__ import annotations

import pytest

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


# ── Named desks over the same brief rail ──────────────────────────────────────
#
# Every paying invoke this hub has recorded went to the generic situation brief, and
# a buyer who wanted a berth-window answer had to know which of 39 layers to ask for.
# A preset is the job title: fixed layer set, stated scope, same price.


def test_port_desk_preset_fixes_the_maritime_layer_set():
    stations = [
        _pin("noaa-tide-01", "tide", 37.8, -122.4, water_level_m=1.4),
        _pin("ndbc-marine-01", "marine", 37.75, -122.5, wave_height_m=2.1),
        _pin("fintraffic-ais-01", "ais", 37.79, -122.42, sog_kn=8.0),
        # In the bbox but outside a port desk's scope — must not be scored or cited.
        _fire(0, 37.7, -122.3, 360),
    ]
    out = situation_brief(
        {"west": -123, "south": 37, "east": -122, "north": 38, "preset": "port_desk"},
        stations,
    )
    assert out["ok"] is True
    assert out["preset"] == "port_desk"
    assert out["preset_overridden"] is None
    assert set(out["layers"]) == {
        "tide", "marine", "river", "flood", "alerts", "cyclone", "ais", "weather", "tsunami",
    }
    assert "fire" not in out["layers"]
    assert {c.get("layer") for c in out["citations"]} <= set(out["layers"])
    # The scope sentence is the product: it says what the answer is NOT.
    assert "not a pilotage decision" in out["preset_scope"]
    assert out["summary"].startswith("port_desk brief")


def test_campus_preset_is_a_named_site_not_a_fire_desk():
    stations = [
        _pin("om-wx-01", "weather", 39.04, -77.45, temperature_c=18.2),
        _pin("airnow-01", "air", 39.03, -77.46, pm25_ugm3=9.4),
        _pin("pjmdc-01", "grid", 39.05, -77.44, load_mw=412.0),
        _fire(0, 39.02, -77.41, 360),
    ]
    out = situation_brief(
        {"west": -77.52, "south": 39.00, "east": -77.38, "north": 39.08, "preset": "campus"},
        stations,
    )
    assert out["ok"] is True
    assert out["preset"] == "campus"
    assert set(out["layers"]) == {
        "weather", "air", "flood", "river", "alerts", "grid", "lightning",
    }
    assert "fire" not in out["layers"]
    assert "not a BMS" in out["preset_scope"]
    assert out["summary"].startswith("campus brief")


def test_cat_desk_and_corridor_presets_select_their_own_hazards():
    quake = _pin("usgs-quake-01", "quake", 34.05, -118.25, magnitude=4.4)
    volcano = _pin("usgs-volcano-01", "volcano", 34.2, -118.3, severity_score=1.0)
    traffic = _pin("edge-traffic-01", "traffic", 34.1, -118.1, vehicles_per_min=40.0)
    bbox = {"west": -120, "south": 32, "east": -116, "north": 36}

    cat = situation_brief({**bbox, "preset": "cat_desk"}, [quake, volcano, traffic])
    assert cat["ok"] is True
    assert "volcano" in cat["layers"] and "quake" in cat["layers"]
    assert "traffic" not in cat["layers"]
    assert "not a loss estimate" in cat["preset_scope"]

    corridor = situation_brief({**bbox, "preset": "corridor"}, [quake, volcano, traffic])
    assert corridor["ok"] is True
    assert "traffic" in corridor["layers"] and "quake" in corridor["layers"]
    assert "volcano" not in corridor["layers"]
    assert "not a track-level inspection" in corridor["preset_scope"]


def test_unknown_preset_is_refused_not_answered_with_the_default_layers():
    """A typo must not sell a 21-layer answer to someone who asked for one desk."""
    out = situation_brief(
        {"west": -120, "south": 32, "east": -116, "north": 36, "preset": "port-desk"},
        [_pin("noaa-tide-01", "tide", 34.0, -118.0, water_level_m=1.4)],
    )
    assert out["ok"] is False
    assert "unknown preset: port-desk" in out["refuse_reason"]
    assert "port_desk" in out["refuse_reason"] and "cat_desk" in out["refuse_reason"]
    assert "layers" not in out


def test_explicit_layers_override_a_preset_and_the_answer_says_so():
    """When layers win, the desk's scope sentence no longer describes the answer."""
    out = situation_brief(
        {
            "west": -120, "south": 32, "east": -116, "north": 36,
            "preset": "cat_desk", "layers": ["weather"],
        },
        [_wx(34.0, -118.0, temperature_c=28, humidity_pct=30, wind_mps=6)],
    )
    assert out["ok"] is True
    assert out["layers"] == ["weather"]
    assert out["preset"] is None
    assert out["preset_scope"] is None
    assert out["preset_overridden"] == "cat_desk"
    assert out["summary"].startswith("Situation brief")


def test_a_preset_refusal_still_names_the_desk_that_got_nothing():
    """The empty answer IS the coverage answer — and it is not billed."""
    out = situation_brief(
        {"west": -120, "south": 32, "east": -116, "north": 36, "preset": "port_desk"},
        [_fire(0, 34.1, -118.2, 360)],
    )
    assert out["ok"] is False
    assert out["preset"] == "port_desk"
    assert "not a pilotage decision" in out["preset_scope"]
    assert out["coverage"]["tide"]["live"] == 0


def test_every_preset_layer_is_a_real_atlas_layer():
    """A preset naming a layer that does not exist would quietly narrow the answer."""
    from atlas.products import SITUATION_BRIEF_PRESETS
    from atlas.stations import LAYER_META

    for name, spec in SITUATION_BRIEF_PRESETS.items():
        assert spec["layers"], name
        unknown = [layer for layer in spec["layers"] if layer not in LAYER_META]
        assert not unknown, f"{name} names non-existent layer(s): {unknown}"
        assert len(set(spec["layers"])) == len(spec["layers"]), name
        assert spec["scope"].strip()


def test_invoke_product_carries_the_preset_through():
    out = invoke_product(
        "atlas.situation.brief@v1",
        {"west": -123, "south": 37, "east": -122, "north": 38, "preset": "port_desk"},
        [_pin("noaa-tide-01", "tide", 37.8, -122.4, water_level_m=1.4)],
    )
    assert out["ok"] is True
    assert out["preset"] == "port_desk"


# ── atlas.geomag.window@v1 ────────────────────────────────────────────────────
#
# The brief deliberately excludes spacewx/geomag, so the two newest dense layers had
# no SKU. This one answers the question desks pay for — is the field quiet enough to
# run the operation — and it must never imply a local magnetometer we do not have.

from atlas.products import geomag_window  # noqa: E402


def _kp(kp: float, *, lat: float = 40.1375, lon: float = -105.2372, aurora: float | None = None) -> dict:
    values: dict = {"kp_index": kp, "latitude": lat, "longitude": lon}
    if aurora is not None:
        values["aurora_pct"] = aurora
    return {
        "id": f"swpc-hs-{round(lat*1e4)}_{round(lon*1e4)}",
        "layer": "spacewx",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": "SWPC",
        "values": values,
        "headline": f"Kp {kp:g}",
        "source": "https://services.swpc.noaa.gov",
    }


def _obs(name: str, lat: float, lon: float, *, field_nt: float = 52000.0, age_s: float = 90.0) -> dict:
    return {
        "id": f"usgs-geomag-{name.lower()}",
        "layer": "geomag",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": f"{name} observatory F",
        "values": {
            "field_nt": field_nt,
            "observation_age_s": age_s,
            "latitude": lat,
            "longitude": lon,
        },
        "headline": f"F {field_nt:.0f} nT",
        "source": "https://geomag.usgs.gov/ws/data/",
    }


def test_quiet_kp_opens_the_window_and_cites_the_nearest_observatory():
    out = geomag_window(
        {"lat": 40.0, "lon": -105.0, "asset_id": "rig-4"},
        [_kp(2.0), _obs("BOU", 40.1375, -105.2372)],
    )
    assert out["ok"] is True
    assert out["kp_index"] == 2.0
    assert out["kp_state"] == "quiet"
    assert out["window_status"] == "open"
    assert out["noaa_g_scale"] is None
    assert out["corroboration"] == "observatory"
    assert out["nearest_observatory"]["field_nt"] == 52000.0
    assert out["nearest_observatory"]["distance_km"] < 50
    assert out["query"]["asset_id"] == "rig-4"
    assert out["receipt"]["capability_id"] == "atlas.geomag.window@v1"


def test_storm_kp_holds_the_window_and_reports_the_noaa_g_scale():
    out = geomag_window({"lat": 40.0, "lon": -105.0}, [_kp(6.0), _obs("BOU", 40.1375, -105.2372)])
    assert out["window_status"] == "hold"
    assert out["kp_state"] == "moderate_storm"
    assert out["noaa_g_scale"] == "G2"
    assert any("Hold magnetic-reference-dependent work" in a for a in out["recommended_actions"])


def test_active_field_is_caution_not_hold():
    out = geomag_window({"lat": 40.0, "lon": -105.0}, [_kp(4.0)])
    assert out["kp_state"] == "active"
    assert out["window_status"] == "caution"
    assert out["noaa_g_scale"] is None


def test_kp_thresholds_follow_the_published_noaa_boundaries():
    from atlas.products import _kp_state

    assert [_kp_state(k)[0] for k in (0.0, 2.9, 3.0, 3.9, 4.0, 4.9)] == [
        "quiet", "quiet", "unsettled", "unsettled", "active", "active",
    ]
    assert [_kp_state(k)[2] for k in (5.0, 6.0, 7.0, 8.0, 9.0)] == ["G1", "G2", "G3", "G4", "G5"]
    assert all(_kp_state(k)[1] == "hold" for k in (5.0, 6.5, 7.2, 9.0))


def test_far_from_the_us_network_the_window_says_it_is_planetary_only():
    """The USGS network is United States territory. A North Sea rig gets Kp, and
    must be told that is all it got — not left to assume a local magnetometer."""
    out = geomag_window(
        {"lat": 56.5, "lon": 3.0},  # North Sea
        [_kp(5.0), _obs("BOU", 40.1375, -105.2372)],
    )
    assert out["ok"] is True
    assert out["corroboration"] == "planetary_only"
    assert out["nearest_observatory"] is None
    assert any("no USGS geomagnetic observatory within" in d for d in out["drivers"])
    assert any("planetary-only" in line for line in out["limitations"])


def test_no_live_kp_refuses_instead_of_answering_from_an_observatory():
    """The window keys on Kp; F alone is a field value, not a disturbance state."""
    out = geomag_window({"lat": 40.0, "lon": -105.0}, [_obs("BOU", 40.1375, -105.2372)])
    assert out["ok"] is False
    assert "no LIVE planetary Kp" in out["refuse_reason"]
    assert "receipt" not in out
    assert "kp_index" not in out


def test_a_sim_kp_pin_is_not_a_live_window():
    sim = _kp(3.0)
    sim["live"] = False
    sim["mode"] = "test"
    out = geomag_window({"lat": 40.0, "lon": -105.0}, [sim])
    assert out["ok"] is False
    assert "no LIVE planetary Kp" in out["refuse_reason"]


def test_disagreeing_kp_pins_report_the_worst_value():
    """A stale pin must not talk the window open."""
    out = geomag_window({"lat": 40.0, "lon": -105.0}, [_kp(1.0), _kp(6.0, lat=40.2, lon=-105.4)])
    assert out["kp_index"] == 6.0
    assert out["window_status"] == "hold"


def test_the_sku_never_claims_a_declination_correction():
    out = geomag_window({"lat": 40.0, "lon": -105.0}, [_kp(2.0), _obs("BOU", 40.1375, -105.2372)])
    joined = " ".join(out["limitations"]) + " " + out["summary"]
    assert "declination" in joined
    assert "Not a magnetic-declination correction" in out["summary"]
    assert any("total field f only" in line.lower() for line in out["limitations"])
    assert any("safety-of-life" in line for line in out["limitations"])


def test_aurora_cell_is_reported_when_one_is_in_range():
    out = geomag_window(
        {"lat": 64.8, "lon": -147.7, "max_km": 400},
        [_kp(6.0, lat=64.9, lon=-147.9, aurora=88.0), _obs("CMO", 64.874, -147.860)],
    )
    assert out["aurora"]["aurora_pct"] == 88.0
    assert out["aurora"]["distance_km"] < 400
    assert any("OVATION aurora probability 88%" in d for d in out["drivers"])


def test_geomag_bad_coordinates_refuse():
    for bad in ({"lat": 91.0, "lon": 0.0}, {"lat": 0.0, "lon": 181.0}, {}):
        out = geomag_window(bad, [_kp(2.0)])
        assert out["ok"] is False
        assert "lat/lon required" in out["refuse_reason"]


def test_invoke_product_routes_the_geomag_window():
    out = invoke_product(
        "atlas.geomag.window@v1",
        {"lat": 40.0, "lon": -105.0},
        [_kp(2.0), _obs("BOU", 40.1375, -105.2372)],
    )
    assert out["ok"] is True
    assert out["sku"] == "atlas.geomag.window@v1"


# ── atlas.pv.irradiance.record@v1 ─────────────────────────────────────────────
#
# NASA POWER lags by days. That makes it useless as a nowcast and exactly right for
# the job here: a dated, attributed record of what the sky and the air did over one
# plant coordinate, citable in a performance-ratio argument. Never a yield model.

from atlas.products import pv_irradiance_record  # noqa: E402


def _solar(lat: float, lon: float, *, all_sky: float = 3.184,
           clear: float | None = 5.02, day: int | None = 20260824) -> dict:
    values: dict = {
        "solar_irradiation_kwh_m2_day": all_sky,
        "latitude": lat,
        "longitude": lon,
    }
    if clear is not None:
        values["clear_sky_irradiation_kwh_m2_day"] = clear
    if day is not None:
        values["solar_observation_yyyymmdd"] = day
    return {
        "id": "solar-plant", "layer": "solar", "live": True, "mode": "live",
        "has_reading": True, "lat": lat, "lon": lon,
        "place": "POWER source grid cell", "values": values,
        "headline": f"{all_sky:.2f} kWh/m2/day",
        "source": "https://power.larc.nasa.gov/api/temporal/daily/point",
    }


def _cams(lat: float, lon: float, *, aod: float | None = 0.61, dust: float | None = 8.4) -> dict:
    values: dict = {"latitude": lat, "longitude": lon}
    if aod is not None:
        values["aerosol_optical_depth"] = aod
    if dust is not None:
        values["dust_ugm3"] = dust
    return {
        "id": "cams-plant", "layer": "atmosphere", "live": True, "mode": "live",
        "has_reading": True, "lat": lat, "lon": lon,
        "place": "aerosol/dust/pollen grid cell", "values": values,
        "headline": "CAMS", "source": "https://open-meteo.com",
    }


def test_the_record_derives_cloud_loss_from_all_sky_against_clear_sky():
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4, "plant_id": "plant-a"},
        [_solar(52.52, 13.405), _cams(52.52, 13.405)],
    )
    assert out["ok"] is True
    assert out["record_kind"] == "retrospective_record_of_fact"
    assert out["irradiance"]["all_sky_kwh_m2_day"] == 3.184
    assert out["irradiance"]["clear_sky_kwh_m2_day"] == 5.02
    assert out["irradiance"]["cloud_loss_kwh_m2_day"] == 1.836
    assert out["irradiance"]["cloud_loss_pct"] == 36.57
    assert out["irradiance"]["observation_date"] == "2026-08-24"
    assert out["query"]["plant_id"] == "plant-a"
    assert "36.6% below clear-sky" in out["summary"]


def test_the_record_date_is_always_stated_because_power_lags():
    """A record of fact with no date is not evidence in a contractual argument."""
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4}, [_solar(52.52, 13.405)]
    )
    assert any("record date: 2026-08-24" in d for d in out["drivers"])
    assert "record date 2026-08-24" in out["summary"]
    assert any("multi-day lag" in line for line in out["limitations"])
    assert any("retrospective record, not a nowcast" in line for line in out["limitations"])


def test_a_missing_record_date_is_reported_not_invented():
    out = pv_irradiance_record({"lat": 52.5, "lon": 13.4}, [_solar(52.52, 13.405, day=None)])
    assert out["ok"] is True
    assert out["irradiance"]["observation_date"] is None
    assert any("record date was not supplied" in d for d in out["drivers"])


def test_a_missing_clear_sky_reference_does_not_fabricate_a_loss():
    out = pv_irradiance_record({"lat": 52.5, "lon": 13.4}, [_solar(52.52, 13.405, clear=None)])
    assert out["ok"] is True
    assert out["irradiance"]["clear_sky_kwh_m2_day"] is None
    assert out["irradiance"]["cloud_loss_pct"] is None
    assert any("cloud loss not derivable" in d for d in out["drivers"])


def test_aerosol_thresholds_are_labelled_as_our_screening_not_a_standard():
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4}, [_solar(52.52, 13.405), _cams(52.52, 13.405, aod=0.61, dust=72.0)]
    )
    joined = " ".join(out["soiling_drivers"])
    assert "elevated" in joined and "screening threshold 0.5" in joined
    assert "dust event" in joined and "screening threshold 50" in joined
    assert any("ATLAS screening labels, not an industry standard" in line for line in out["limitations"])


def test_background_aerosol_is_not_called_elevated():
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4}, [_solar(52.52, 13.405), _cams(52.52, 13.405, aod=0.11, dust=3.0)]
    )
    joined = " ".join(out["soiling_drivers"])
    assert "background" in joined
    assert "no dust event" in joined
    assert "elevated" not in joined


def test_no_aerosol_in_range_says_the_soiling_driver_is_unevidenced():
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4, "max_km": 50},
        [_solar(52.52, 13.405), _cams(20.0, 30.0)],  # aerosol cell thousands of km away
    )
    assert out["ok"] is True
    assert out["aerosol"] is None
    assert any("soiling driver not evidenced" in d for d in out["soiling_drivers"])


def test_no_irradiance_within_range_refuses_and_reports_the_real_distance():
    """A record of fact must not be issued from a cell on another continent."""
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4, "max_km": 50}, [_solar(-23.55, -46.63)]
    )
    assert out["ok"] is False
    assert "no LIVE daily irradiation reading within 50 km" in out["refuse_reason"]
    assert out["nearest_solar_candidate_distance_km"] > 5000
    assert "receipt" not in out


def test_a_sim_solar_pin_cannot_back_a_record_of_fact():
    sim = _solar(52.52, 13.405)
    sim["live"] = False
    sim["mode"] = "test"
    out = pv_irradiance_record({"lat": 52.5, "lon": 13.4}, [sim])
    assert out["ok"] is False
    assert "no LIVE daily irradiation" in out["refuse_reason"]


def test_the_record_never_claims_to_be_a_yield_forecast_or_bankable():
    out = pv_irradiance_record({"lat": 52.5, "lon": 13.4}, [_solar(52.52, 13.405)])
    joined = " ".join(out["limitations"])
    assert "not a yield forecast" in joined.lower()
    assert "soiling-loss model" in joined
    assert "bankable energy" in joined
    assert "P50/P90" in joined
    assert "not a pyranometer on the plant" in joined
    assert "Record of fact, not a yield forecast." in out["summary"]


def test_distances_are_always_reported_so_the_buyer_can_judge_the_cell():
    out = pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4},
        [_solar(52.52, 13.405), _cams(52.7, 13.6), _wx(52.6, 13.5, temperature_c=21.0)],
    )
    assert out["irradiance"]["distance_km"] > 0
    assert out["aerosol"]["distance_km"] > 0
    assert out["weather"]["distance_km"] > 0


def test_pv_bad_coordinates_refuse():
    for bad in ({"lat": 91.0, "lon": 0.0}, {"lat": 0.0, "lon": 181.0}, {}):
        out = pv_irradiance_record(bad, [_solar(52.52, 13.405)])
        assert out["ok"] is False
        assert "lat/lon required" in out["refuse_reason"]


def test_invoke_product_routes_the_pv_record():
    out = invoke_product(
        "atlas.pv.irradiance.record@v1",
        {"lat": 52.5, "lon": 13.4},
        [_solar(52.52, 13.405), _cams(52.52, 13.405)],
    )
    assert out["ok"] is True
    assert out["sku"] == "atlas.pv.irradiance.record@v1"


# ── atlas.route.integrity@v1 ──────────────────────────────────────────────────
#
# The GNSS SKU already accepted a route and almost nobody used it, because a
# degradation field alone is not a decision. This composes it with the reported-zone
# registry, platform presence along the corridor, and the hazard pins beside it —
# and it must never turn "reported" into "proven".

from atlas.fleet import expand_map_objects  # noqa: E402
from atlas.products import route_integrity  # noqa: E402

BALTIC_ROUTE = [[24.94, 60.17], [22.0, 59.8], [18.07, 59.33]]


def _gnss_station_parent(stations: list[tuple[str, float, float]]) -> dict:
    return {
        "id": "gnss-euref-01", "layer": "gnss", "label": "EUREF GNSS Integrity Network",
        "kind": "event", "online": True, "live": True, "mode": "live",
        "source": "EUREF EPN CC BY 4.0", "color": "#34d399",
        "values": {"latitude": stations[0][1], "longitude": stations[0][2]},
        "hotspots": [
            {
                "point_id": f"gnss-station:euref:{name}", "station_id": name,
                "network": "EUREF EPN", "latitude": lat, "longitude": lon,
                "availability_pct": 97.0, "latency_s": 20.0, "degradation_score": 9.0,
                "confidence": 0.7, "state": "normal", "claim_class": "derived_degradation",
            }
            for name, lat, lon in stations
        ],
        "hotspot_count": len(stations),
    }


def _jam(lat: float, lon: float, *, kind: str = "jamming") -> dict:
    return {
        "id": f"cybernews-jam-{round(lat*1e4)}_{round(lon*1e4)}", "layer": "jamming",
        "live": True, "mode": "live", "has_reading": True, "lat": lat, "lon": lon,
        "place": "reported zone",
        "values": {"severity": "high", "type": kind, "latitude": lat, "longitude": lon},
        "headline": "reported", "source": "https://www.cybernews.space",
    }


def test_a_route_gets_per_segment_counts_not_one_polyline_total():
    stations = expand_map_objects([_gnss_station_parent([
        ("METS", 60.22, 24.40), ("SPT0", 57.72, 12.89),
    ])])
    out = route_integrity(
        {"route": BALTIC_ROUTE, "corridor_km": 60, "route_id": "leg-1"},
        [*stations, _jam(60.0, 24.5), _jam(59.4, 18.2)],
    )
    assert out["ok"] is True
    assert out["query"]["waypoints"] == 3
    assert out["query"]["route_length_km"] > 300
    assert len(out["segments"]) == 2
    assert [s["index"] for s in out["segments"]] == [0, 1]
    assert sum(s["length_km"] for s in out["segments"]) == pytest.approx(
        out["query"]["route_length_km"], rel=0.02
    )
    # Each reported zone belongs to the leg it sits beside, not to both.
    assert out["segments"][0]["reported_interference"] == 1
    assert out["segments"][1]["reported_interference"] == 1
    assert out["reported_interference_count"] == 2


def test_reported_interference_is_never_promoted_to_proof():
    out = route_integrity(
        {"route": BALTIC_ROUTE, "corridor_km": 60}, [_jam(60.0, 24.5, kind="spoofing")]
    )
    assert out["integrity_claim"] == "reported_interference"
    assert out["reported_interference"][0]["claim"] == "spoofing_reported"
    joined = " ".join(out["limitations"]) + " " + out["summary"]
    assert "not proof of jamming or spoofing" in joined
    assert "NOT proof of jamming or spoofing" in " ".join(out["limitations"])
    assert any("safety-of-life" in line for line in out["limitations"])


def test_station_coverage_without_a_reported_zone_is_its_own_claim():
    stations = expand_map_objects([_gnss_station_parent([("METS", 60.22, 24.40)])])
    out = route_integrity({"route": BALTIC_ROUTE, "corridor_km": 60}, stations)
    assert out["ok"] is True
    assert out["integrity_claim"] == "station_coverage_only"
    assert out["reported_interference_count"] == 0
    assert out["gnss"] is not None
    assert out["gnss_refuse_reason"] is None


def test_hazards_and_platforms_alone_still_produce_an_answer_with_the_gnss_gap_named():
    """A corridor with no GNSS station evidence is not an empty brief — but the gap
    has to be stated, not implied by an absent field."""
    out = route_integrity(
        {"route": BALTIC_ROUTE, "corridor_km": 60},
        [
            _pin("nws-alerts-01", "alerts", 59.9, 23.0, severity_score=70.0),
            _pin("fintraffic-ais-01", "ais", 59.6, 20.0, sog_kn=12.0),
        ],
    )
    assert out["ok"] is True
    assert out["integrity_claim"] == "no_gnss_coverage"
    assert out["gnss"] is None
    assert out["gnss_refuse_reason"]
    assert out["hazard_counts"]["alerts"] == 1
    assert out["platform_observation_counts"]["ais"] == 1
    assert any("no GNSS station evidence in corridor" in d for d in out["drivers"])


def test_platform_presence_is_labelled_as_presence_not_performance():
    out = route_integrity(
        {"route": BALTIC_ROUTE, "corridor_km": 60},
        [_pin("adsb-lol-01", "adsb", 59.7, 21.0, altitude_ft=34000.0)],
    )
    assert any("presence only, not an integrity measurement" in d for d in out["drivers"])
    assert any("not receiver performance" in line for line in out["limitations"])
    assert any("ODbL" in line for line in out["attribution"])


def test_evidence_outside_the_corridor_is_excluded():
    out = route_integrity(
        {"route": BALTIC_ROUTE, "corridor_km": 10},
        [_jam(45.0, 9.0), _pin("nws-alerts-01", "alerts", 40.0, -3.0, severity_score=70.0)],
    )
    assert out["ok"] is False
    assert "no LIVE GNSS, interference, platform or hazard evidence within 10 km" in out["refuse_reason"]
    assert "receipt" not in out


def test_a_sim_pin_is_not_corridor_evidence():
    sim = _jam(60.0, 24.5)
    sim["live"] = False
    sim["mode"] = "test"
    out = route_integrity({"route": BALTIC_ROUTE, "corridor_km": 60}, [sim])
    assert out["ok"] is False


@pytest.mark.parametrize("bad", [
    {"route": [[24.94, 60.17]]},
    {"route": [[24.94, 60.17], [200.0, 59.33]]},
    {"route": [[24.94, 60.17], [18.07, 95.0]]},
    {"route": "helsinki-stockholm"},
    {},
])
def test_an_unusable_route_refuses(bad):
    out = route_integrity(bad, [])
    assert out["ok"] is False
    assert "2–500 valid [lon, lat] pairs" in out["refuse_reason"]


def test_corridor_width_is_bounded():
    stations = expand_map_objects([_gnss_station_parent([("METS", 60.22, 24.40)])])
    wide = route_integrity({"route": BALTIC_ROUTE, "corridor_km": 99999}, stations)
    assert wide["query"]["corridor_km"] == 200.0
    narrow = route_integrity({"route": BALTIC_ROUTE, "corridor_km": -5}, stations)
    assert narrow["query"]["corridor_km"] == 1.0


def test_invoke_product_routes_the_route_integrity_sku():
    out = invoke_product(
        "atlas.route.integrity@v1",
        {"route": BALTIC_ROUTE, "corridor_km": 60},
        [_jam(60.0, 24.5)],
    )
    assert out["ok"] is True
    assert out["sku"] == "atlas.route.integrity@v1"
