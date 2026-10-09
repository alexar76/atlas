"""Every product SKU must be able to say what it returns — and be held to it.

All six ATLAS products reached the public hub manifest with ``output_schema: {}``. The key
was never declared, so the crawler indexed emptiness and published it: six priced,
discoverable decision artifacts whose result shape a buyer could only learn by paying for
one. A capability that cannot state its output cannot be composed into anything.

Declaring the schemas is half of it. The other half is these tests, because a schema
maintained by hand next to the code that produces it is the drift the oracle family
already got burned by. So each declared schema is checked BOTH ways against a real
handler call:

  * the payload must satisfy the schema (the schema does not over-promise)
  * every key the payload carries must be declared (the schema does not fall behind)

The second direction is the one that catches a new field added to a handler six months
from now, which is exactly how ``output_schema: {}`` survived this long.
"""

from __future__ import annotations

import pathlib
import tempfile

import jsonschema
import pytest

from atlas.fleet import expand_map_objects
from atlas.products import (
    CAP_BY_ID,
    PRODUCT_CAPS,
    field_consensus,
    field_posterior,
    field_shape,
    fire_weather,
    geomag_window,
    gnss_degradation,
    mesh_sample,
    pv_irradiance_record,
    observability_attest,
    route_integrity,
    nearest_read,
    point_read,
    situation_brief,
    smoke_operations,
    watchbox_check,
)
from atlas.watchboxes import STORE

BBOX = {"west": -120, "south": 32, "east": -116, "north": 36}


def _wx(lat: float, lon: float, **vals: float) -> dict:
    return {
        "id": "om-wx-test", "layer": "weather", "live": True, "mode": "live",
        "has_reading": True, "lat": lat, "lon": lon, "place": "Test", "values": vals,
        "headline": "wx", "source": "https://api.open-meteo.com",
    }


def _fire(i: int, lat: float, lon: float, bright: float) -> dict:
    return {
        "id": f"firms-hs-{i:04d}", "parent_id": "firms-fire-01", "layer": "fire",
        "live": True, "mode": "live", "has_reading": True, "lat": lat, "lon": lon,
        "place": "Hotspot",
        "values": {"brightness_k": bright, "confidence": 90, "latitude": lat, "longitude": lon},
        "headline": f"Fire {bright:.0f} K",
        "source": "https://firms.modaps.eosdis.nasa.gov",
        "observed_at": "2026-08-11T12:05:00Z", "satellite": "N",
    }


def _air(lat: float, lon: float) -> dict:
    return {
        "id": "air-test", "layer": "air", "live": True, "mode": "live",
        "has_reading": True, "lat": lat, "lon": lon, "values": {"pm2_5_ugm3": 12.0},
        "source": "https://example.test/air",
    }


def _gnss_parent() -> dict:
    return {
        "id": "gnss-euref-01", "layer": "gnss", "label": "EUREF GNSS Integrity Network",
        "kind": "event", "online": True, "live": True, "mode": "live",
        "source": "EUREF EPN CC BY 4.0", "color": "#34d399",
        "values": {"latitude": 50.8, "longitude": 4.35},
        "hotspots": [{
            "point_id": "gnss-station:euref:BRUX00BEL", "station_id": "BRUX00BEL",
            "network": "EUREF EPN", "latitude": 50.7981, "longitude": 4.3586,
            "availability_pct": 98.0, "latency_s": 17.0, "degradation_score": 8.0,
            "confidence": 0.72, "state": "normal", "claim_class": "derived_degradation",
            "cause": "unestablished", "license": "CC BY 4.0",
        }],
        "hotspot_count": 1,
    }


def _fire_weather_payload() -> dict:
    stations = [
        _fire(0, 34.1, -118.2, 380),
        _fire(1, 34.2, -118.1, 330),
        _wx(34.05, -118.25, temperature_c=31, humidity_pct=18, wind_mps=12),
        _air(34.06, -118.26),
    ]
    return fire_weather({**BBOX, "include_air": True}, stations)


def _situation_brief_payload() -> dict:
    stations = [
        _fire(0, 34.1, -118.2, 350),
        _wx(34.05, -118.25, temperature_c=30, humidity_pct=20, wind_mps=8),
    ]
    return situation_brief({**BBOX, "layers": ["fire", "weather"]}, stations)


def _watchbox_payload(tmp_path, monkeypatch) -> dict:
    monkeypatch.setattr("atlas.products.STORE", STORE.__class__(path=tmp_path / "wb.json"))
    return watchbox_check({**BBOX, "layers": ["fire"]}, [_fire(0, 34.1, -118.2, 350)])


def _nearest_payload() -> dict:
    stations = [_wx(52.52, 13.40, temperature_c=19)]
    return nearest_read({"lat": 52.5, "lon": 13.4, "layer": "weather"}, stations)


def _nearest_per_layer_payload() -> dict:
    stations = [_wx(52.52, 13.40, temperature_c=19), _air(52.51, 13.41)]
    return nearest_read(
        {"lat": 52.5, "lon": 13.4, "layers": ["weather", "air"], "per_layer": True}, stations
    )


def _point_read_payload() -> dict:
    points = expand_map_objects([_gnss_parent()])
    return point_read({"point_id": "gnss-station:euref:BRUX00BEL"}, points)


def _smoke_payload() -> dict:
    plume = [[-125.0, 35.0], [-100.0, 35.0], [-100.0, 45.0], [-125.0, 45.0], [-125.0, 35.0]]
    parent = {
        "id": "hms-smoke-01", "layer": "smoke", "live": True, "mode": "live",
        "online": True, "has_reading": True, "lat": 40.0, "lon": -112.5,
        "source": "https://www.ospo.noaa.gov/Products/land/hms.html",
        "values": {"severity_score": 90.0},
        "hotspots": [{
            "severity_score": 90.0, "latitude": 40.0, "longitude": -112.5,
            "density": "heavy", "satellite": "GOES-19",
            "start_time": "2026-08-27 18:00 UTC", "end_time": "2026-08-27 20:00 UTC",
            "geometry_type": "Polygon centroid", "polygon_id": "hms-schema-case",
            "geometry_digest": "d" * 64, "vertex_count": 5,
            "bbox": [-125.0, 35.0, -100.0, 45.0],
            "geometry": {"type": "Polygon", "coordinates": [plume]},
        }],
        "hotspot_count": 1, "inventory_total": 1, "inventory_complete": True,
        "upstream_evidence": {"attestation": {"algorithm": "ed25519", "value": "sig"}},
    }
    stations = expand_map_objects([parent], expand=True, include_private_geometry=True)
    air = {
        "id": "om-aq-coordinate", "layer": "air", "live": True, "mode": "live",
        "has_reading": True, "lat": 37.7749, "lon": -122.4194,
        "values": {"pm2_5_ugm3": 41.0, "us_aqi": 115.0},
        "units": {"pm2_5_ugm3": "ug/m3", "us_aqi": "US AQI"},
        "observed_at": "2026-08-27T19:00:00+00:00",
        "source": "https://customer-api.open-meteo.com",
        "attribution": "Open-Meteo.com",
    }
    return smoke_operations(
        {"lat": 37.7749, "lon": -122.4194, "asset_id": "yard-7"}, stations, air
    )


def _gnss_payload() -> dict:
    points = expand_map_objects([_gnss_parent()])
    return gnss_degradation({"lat": 50.8, "lon": 4.35, "max_km": 100}, points)


def _geomag_payload() -> dict:
    kp = {
        "id": "swpc-hs-401375_-1052372", "layer": "spacewx", "live": True, "mode": "live",
        "has_reading": True, "lat": 40.1375, "lon": -105.2372, "place": "SWPC",
        "values": {"kp_index": 6.0, "aurora_pct": 42.0, "latitude": 40.1375, "longitude": -105.2372},
        "source": "https://services.swpc.noaa.gov",
    }
    observatory = {
        "id": "usgs-geomag-01", "layer": "geomag", "live": True, "mode": "live",
        "has_reading": True, "lat": 40.1375, "lon": -105.2372,
        "place": "BOU observatory F (not INTERMAGNET)",
        "values": {
            "field_nt": 52310.0, "observation_age_s": 75.0,
            "latitude": 40.1375, "longitude": -105.2372,
        },
        "source": "https://geomag.usgs.gov/ws/data/",
    }
    return geomag_window({"lat": 40.0, "lon": -105.0, "asset_id": "rig-4"}, [kp, observatory])


def _pv_payload() -> dict:
    solar = {
        "id": "solar-berlin", "layer": "solar", "live": True, "mode": "live",
        "has_reading": True, "lat": 52.52, "lon": 13.405,
        "place": "Berlin POWER source grid cell",
        "values": {
            "solar_irradiation_kwh_m2_day": 3.184,
            "clear_sky_irradiation_kwh_m2_day": 5.02,
            "solar_observation_yyyymmdd": 20260824,
            "latitude": 52.52, "longitude": 13.405,
        },
        "source": "https://power.larc.nasa.gov/api/temporal/daily/point",
    }
    cams = {
        "id": "cams-berlin", "layer": "atmosphere", "live": True, "mode": "live",
        "has_reading": True, "lat": 52.52, "lon": 13.405,
        "place": "Berlin aerosol/dust/pollen grid cell",
        "values": {
            "aerosol_optical_depth": 0.61, "dust_ugm3": 8.4,
            "latitude": 52.52, "longitude": 13.405,
        },
        "source": "https://open-meteo.com",
    }
    return pv_irradiance_record(
        {"lat": 52.5, "lon": 13.4, "plant_id": "plant-a"},
        [solar, cams, _wx(52.51, 13.41, temperature_c=21.0)],
    )


def _route_payload() -> dict:
    points = expand_map_objects([_gnss_parent()])
    jamming = {
        "id": "cybernews-jam-01", "layer": "jamming", "live": True, "mode": "live",
        "has_reading": True, "lat": 50.85, "lon": 4.4, "place": "reported zone",
        "values": {"severity": "high", "type": "jamming", "latitude": 50.85, "longitude": 4.4},
        "source": "https://www.cybernews.space",
    }
    return route_integrity(
        {"route": [[4.30, 50.78], [4.45, 50.86]], "corridor_km": 40, "route_id": "leg-1"},
        [*points, jamming],
    )


def _observability_payload() -> dict:
    from atlas.status_archive import StatusArchive

    radar = {
        "id": "nexrad-site-KTLX", "layer": "radar", "live": True, "mode": "live",
        "has_reading": True, "lat": 35.3331, "lon": -97.2778,
        "place": "Oklahoma City WSR-88D", "radar_id": "KTLX", "name": "KTLX",
        "status": "Operational", "operability": "RDA - On-line", "vcp": "212",
        "values": {"radar_latency_s": 41.0, "latitude": 35.3331, "longitude": -97.2778},
        "source": "https://api.weather.gov/radar/stations",
    }
    tmp = tempfile.mkdtemp()
    archive = StatusArchive(pathlib.Path(tmp) / "status.jsonl")
    archive.append("radar", [radar])
    return observability_attest(
        {"lat": 35.22, "lon": -97.44, "event_id": "claim-88"},
        [radar, _wx(35.3, -97.5, temperature_c=24.0)],
        archive,
    )


def _ee_mesh() -> list[dict]:
    pins = []
    stations = [
        ("ee-wx-tallinn-01", "Tallinn-Harku", 59.3981, 24.6029, 8.1),
        ("ee-wx-tartu-01", "Tartu-Tõravere", 58.2641, 26.4613, 7.8),
        ("ee-wx-parnu-01", "Pärnu", 58.3846, 24.4852, 8.4),
        ("ee-wx-narva-01", "Narva", 59.3895, 28.1093, 6.9),
        ("ee-wx-kuressaare-01", "Kuressaare", 58.2642, 22.4894, 9.2),
        ("ee-wx-voru-01", "Võru", 57.8463, 27.0195, 7.1),
    ]
    for sid, place, lat, lon, temp in stations:
        pins.append({
            "id": sid, "layer": "weather", "live": True, "mode": "live",
            "has_reading": True, "lat": lat, "lon": lon, "place": place,
            "values": {"temperature_c": temp},
            "source": "https://www.ilmateenistus.ee",
        })
    return pins


def _pegel_mesh() -> list[dict]:
    pins = []
    stations = [
        ("pegel-bonn-01", "Rhine at Bonn", 50.7364, 7.1080, 1450.0),
        ("pegel-koeln-01", "Rhine at Köln", 50.9369, 6.9633, 1680.0),
        ("pegel-mainz-01", "Rhine at Mainz", 50.0040, 8.2753, 1320.0),
        ("pegel-dresden-01", "Elbe at Dresden", 51.0545, 13.7388, 310.0),
    ]
    for sid, place, lat, lon, q in stations:
        pins.append({
            "id": sid, "layer": "river", "live": True, "mode": "live",
            "has_reading": True, "lat": lat, "lon": lon, "place": place,
            "values": {"discharge_m3s": q},
            "source": "https://www.pegelonline.wsv.de",
        })
    return pins


def _mesh_sample_payload() -> dict:
    return mesh_sample({"mesh_id": "ee-wx", "count": 4}, _ee_mesh())


def _field_consensus_payload() -> dict:
    return field_consensus({"mesh_id": "ee-wx"}, _ee_mesh())


def _field_posterior_payload() -> dict:
    return field_posterior({"mesh_id": "ee-wx", "lat": 58.6, "lon": 25.0}, _ee_mesh())


def _field_shape_payload() -> dict:
    return field_shape({"mesh_id": "pegel"}, _pegel_mesh())


# (capability_id, builder) — every builder returns a SUCCESSFUL payload.
SUCCESS_CASES = [
    ("atlas.fire.weather@v1", _fire_weather_payload),
    ("atlas.situation.brief@v1", _situation_brief_payload),
    ("atlas.nearest.read@v1", _nearest_payload),
    ("atlas.nearest.read@v1", _nearest_per_layer_payload),
    ("atlas.point.read@v1", _point_read_payload),
    ("atlas.gnss.degradation.read@v1", _gnss_payload),
    ("atlas.smoke.operations@v1", _smoke_payload),
    ("atlas.geomag.window@v1", _geomag_payload),
    ("atlas.pv.irradiance.record@v1", _pv_payload),
    ("atlas.route.integrity@v1", _route_payload),
    ("atlas.observability.attest@v1", _observability_payload),
    ("atlas.mesh.sample@v1", _mesh_sample_payload),
    ("atlas.field.consensus@v1", _field_consensus_payload),
    ("atlas.field.posterior@v1", _field_posterior_payload),
    ("atlas.field.shape@v1", _field_shape_payload),
]

# `watchbox` needs tmp_path/monkeypatch, so it is exercised by its own test below
# rather than through the parametrized table.
_COVERED_ELSEWHERE = {"atlas.watchbox.check@v1"}


def _ids(cases):
    return [f"{cid}:{fn.__name__}" for cid, fn in cases]


class TestSchemasAreDeclaredAtAll:
    def test_every_product_declares_a_usable_output_schema(self):
        """The regression: all six shipped with `output_schema: {}`."""
        assert PRODUCT_CAPS, "no products to check"
        for cap in PRODUCT_CAPS:
            schema = cap.get("output_schema")
            cid = cap["capability_id"]
            assert isinstance(schema, dict) and schema, f"{cid} declares no output schema"
            assert schema.get("type") == "object", cid
            props = schema.get("properties") or {}
            assert props, f"{cid} declares an output schema with no fields"
            assert "ok" in props, cid
            assert "refuse_reason" in props, f"{cid} must document its refusal shape"

    def test_every_product_promises_the_content_receipt(self):
        """The receipt is what makes a paid answer attributable; it must be in the contract."""
        for cap in PRODUCT_CAPS:
            receipt = (cap["output_schema"]["properties"]).get("receipt")
            assert receipt, f"{cap['capability_id']} does not declare its receipt"
            assert "digest" in (receipt.get("properties") or {}), cap["capability_id"]

    def test_every_product_is_held_to_its_schema_by_a_real_call(self):
        """Coverage guard: a declared schema nobody exercises is an unchecked promise.

        `atlas.smoke.operations@v1` shipped its schema and its handler while the
        route, the invoke dispatch and every test skipped it, so nothing noticed
        the SKU could not be bought at all.
        """
        exercised = {cid for cid, _ in SUCCESS_CASES} | _COVERED_ELSEWHERE
        missing = sorted({cap["capability_id"] for cap in PRODUCT_CAPS} - exercised)
        assert not missing, f"declared but never validated against a real call: {missing}"

    def test_the_declared_schemas_are_valid_json_schema(self):
        for cap in PRODUCT_CAPS:
            jsonschema.Draft202012Validator.check_schema(cap["output_schema"])


class TestHandlersHonourTheirDeclaredSchema:
    @pytest.mark.parametrize("capability_id,builder", SUCCESS_CASES, ids=_ids(SUCCESS_CASES))
    def test_real_output_validates(self, capability_id, builder, tmp_path, monkeypatch):
        payload = builder()
        assert payload.get("ok") is True, f"fixture did not produce a success: {payload}"
        jsonschema.validate(payload, CAP_BY_ID[capability_id]["output_schema"])

    @pytest.mark.parametrize("capability_id,builder", SUCCESS_CASES, ids=_ids(SUCCESS_CASES))
    def test_no_emitted_field_is_undeclared(self, capability_id, builder):
        """Catches the schema falling behind the handler — how `{}` survived this long."""
        payload = builder()
        declared = set(CAP_BY_ID[capability_id]["output_schema"]["properties"])
        undeclared = sorted(set(payload) - declared)
        assert not undeclared, f"{capability_id} emits undeclared fields: {undeclared}"

    def test_watchbox_output_validates(self, tmp_path, monkeypatch):
        payload = _watchbox_payload(tmp_path, monkeypatch)
        assert payload["ok"] is True
        schema = CAP_BY_ID["atlas.watchbox.check@v1"]["output_schema"]
        jsonschema.validate(payload, schema)
        assert not set(payload) - set(schema["properties"])


class TestRefusalsAlsoFitTheContract:
    def test_a_refusal_is_not_a_schema_violation(self):
        """A SKU that fails closed still answers in its declared envelope."""
        refusal = fire_weather(BBOX, [_wx(34.0, -118.0, temperature_c=28)])
        assert refusal["ok"] is False
        jsonschema.validate(refusal, CAP_BY_ID["atlas.fire.weather@v1"]["output_schema"])

    def test_a_missing_point_refuses_within_the_contract(self):
        refusal = point_read({"point_id": "no-such-point"}, [])
        assert refusal["ok"] is False
        jsonschema.validate(refusal, CAP_BY_ID["atlas.point.read@v1"]["output_schema"])
