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

import jsonschema
import pytest

from atlas.fleet import expand_map_objects
from atlas.products import (
    CAP_BY_ID,
    PRODUCT_CAPS,
    fire_weather,
    gnss_degradation,
    nearest_read,
    point_read,
    situation_brief,
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


def _gnss_payload() -> dict:
    points = expand_map_objects([_gnss_parent()])
    return gnss_degradation({"lat": 50.8, "lon": 4.35, "max_km": 100}, points)


# (capability_id, builder) — every builder returns a SUCCESSFUL payload.
SUCCESS_CASES = [
    ("atlas.fire.weather@v1", _fire_weather_payload),
    ("atlas.situation.brief@v1", _situation_brief_payload),
    ("atlas.nearest.read@v1", _nearest_payload),
    ("atlas.nearest.read@v1", _nearest_per_layer_payload),
    ("atlas.point.read@v1", _point_read_payload),
    ("atlas.gnss.degradation.read@v1", _gnss_payload),
]


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
