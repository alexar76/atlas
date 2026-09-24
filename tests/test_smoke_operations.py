"""``atlas.smoke.operations@v1`` — exact HMS containment, not centroid proximity.

The whole point of this SKU is the question a centroid cannot answer: is THIS
asset inside the smoke polygon? Every test below feeds the pins through the real
``expand_map_objects`` fan-out, so a shape change in the map pipeline fails here
instead of quietly turning the paid answer into "outside".
"""

from __future__ import annotations

from typing import Any

import pytest

from atlas.aggregator import Aggregator
from atlas.fleet import expand_map_objects
from atlas.products import (
    invoke_product,
    point_in_smoke_geometry,
    smoke_geometry_evaluable,
    smoke_operations,
)

# A single western-US plume: 25° wide, centroid near (40, -112.5). San Francisco
# is inside it and roughly 900 km from that centroid.
PLUME = [[-125.0, 35.0], [-100.0, 35.0], [-100.0, 45.0], [-125.0, 45.0], [-125.0, 35.0]]
# Straddles the antimeridian; its antipodal meridian runs through Europe.
ALEUTIAN = [[179.0, 50.0], [-179.0, 50.0], [-179.0, 52.0], [179.0, 52.0], [179.0, 50.0]]
SF = (37.7749, -122.4194)


def _row(
    polygon_id: str,
    rings: list[list[list[float]]],
    *,
    density: str = "heavy",
    severity: float = 90.0,
    product_date: str | None = "2026-08-27",
    product_age_hours: float | None = 25.5,
) -> dict[str, Any]:
    """One HMS hotspot exactly as GAIA signs it into the cluster."""
    anchor = rings[0][:-1]
    return {
        "severity_score": severity,
        "latitude": sum(point[1] for point in anchor) / len(anchor),
        "longitude": sum(point[0] for point in anchor) / len(anchor),
        "density": density,
        "satellite": "GOES-19",
        "start_time": "2026-08-27 18:00 UTC",
        "end_time": "2026-08-27 20:00 UTC",
        "geometry_type": "Polygon centroid",
        "polygon_id": polygon_id,
        "geometry_digest": f"digest-{polygon_id}",
        "vertex_count": sum(len(ring) for ring in rings),
        "bbox": [
            min(point[0] for point in rings[0]),
            min(point[1] for point in rings[0]),
            max(point[0] for point in rings[0]),
            max(point[1] for point in rings[0]),
        ],
        "geometry": {"type": "Polygon", "coordinates": rings},
        **({"product_date": product_date} if product_date is not None else {}),
        **({"product_age_hours": product_age_hours} if product_age_hours is not None else {}),
    }


def _pins(
    rows: list[dict[str, Any]],
    *,
    complete: bool = True,
    total: int | None = None,
    private: bool = True,
) -> list[dict[str, Any]]:
    parent = {
        "id": "hms-smoke-01",
        "layer": "smoke",
        "live": True,
        "mode": "live",
        "online": True,
        "has_reading": True,
        "lat": rows[0]["latitude"],
        "lon": rows[0]["longitude"],
        "source": "https://www.ospo.noaa.gov/Products/land/hms.html",
        "values": {"severity_score": rows[0]["severity_score"]},
        "hotspots": rows,
        "hotspot_count": len(rows),
        "inventory_total": len(rows) if total is None else total,
        "upstream_evidence": {"attestation": {"algorithm": "ed25519", "value": "sig"}},
    }
    if complete:
        parent["inventory_complete"] = True
    return expand_map_objects([parent], expand=True, include_private_geometry=private)


def _air(
    *,
    pm25: float | None = 8.0,
    us_aqi: float | None = 34.0,
    live: bool = True,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if pm25 is not None:
        values["pm2_5_ugm3"] = pm25
    if us_aqi is not None:
        values["us_aqi"] = us_aqi
    return {
        "id": "om-aq-coordinate",
        "layer": "air",
        "live": live,
        "mode": "live",
        "has_reading": True,
        "lat": SF[0],
        "lon": SF[1],
        "values": values,
        "units": {"pm2_5_ugm3": "ug/m3", "us_aqi": "US AQI"},
        "observed_at": "2026-08-27T19:00:00+00:00",
        "source": "https://customer-api.open-meteo.com",
        "attribution": "Open-Meteo.com",
        "upstream_evidence": {"attestation": {"algorithm": "ed25519", "value": "sig"}},
    }


def _brief(rows: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    air = kw.pop("air", None)
    query = {"lat": SF[0], "lon": SF[1], "asset_id": "yard-7"}
    query.update(kw.pop("query", {}))
    return smoke_operations(query, _pins(rows, **kw), _air() if air is None else air)


class TestGeometryPredicate:
    def test_asset_hundreds_of_km_from_the_centroid_is_still_inside(self):
        geometry = {"type": "Polygon", "coordinates": [PLUME]}
        assert point_in_smoke_geometry(*SF, geometry) is True

    def test_a_hole_over_the_asset_is_not_coverage(self):
        hole = [[-123.0, 37.0], [-121.0, 37.0], [-121.0, 39.0], [-123.0, 39.0], [-123.0, 37.0]]
        assert point_in_smoke_geometry(*SF, {"type": "Polygon", "coordinates": [PLUME, hole]}) is False

    def test_boundary_vertices_and_edges_count_as_inside(self):
        geometry = {"type": "Polygon", "coordinates": [PLUME]}
        assert point_in_smoke_geometry(35.0, -125.0, geometry) is True
        assert point_in_smoke_geometry(35.0, -110.0, geometry) is True

    @pytest.mark.parametrize("lon", [179.9, -179.5, 179.0, -179.0])
    def test_an_antimeridian_polygon_covers_both_of_its_own_sides(self, lon: float):
        geometry = {"type": "Polygon", "coordinates": [ALEUTIAN]}
        assert point_in_smoke_geometry(51.0, lon, geometry) is True

    @pytest.mark.parametrize("lat,lon", [(51.5074, -0.1278), (48.8566, 2.3522), (55.75, 37.61)])
    def test_an_antimeridian_polygon_does_not_cover_the_antipodal_meridian(self, lat, lon):
        """Regression: unwrapping around the QUERY reported London as inside."""
        geometry = {"type": "Polygon", "coordinates": [ALEUTIAN]}
        assert point_in_smoke_geometry(lat, lon, geometry) is False

    def test_multipolygon_parts_are_each_tested(self):
        geometry = {"type": "MultiPolygon", "coordinates": [[ALEUTIAN], [PLUME]]}
        assert point_in_smoke_geometry(*SF, geometry) is True
        assert point_in_smoke_geometry(51.0, 179.9, geometry) is True

    @pytest.mark.parametrize(
        "geometry",
        [
            None,
            {"type": "Point", "coordinates": [-122.4, 37.7]},
            {"type": "Polygon", "coordinates": []},
            {"type": "Polygon", "coordinates": [[[-125.0, 35.0], [-100.0, 35.0]]]},
            {"type": "Polygon", "coordinates": [[["x", 35.0], [-100.0, 35.0], [-100.0, 45.0], [-125.0, 45.0]]]},
        ],
    )
    def test_unusable_geometry_is_never_silently_outside(self, geometry: Any):
        assert smoke_geometry_evaluable(geometry) is False


class TestContainmentIsNotProximity:
    def test_covering_polygon_is_returned_and_the_nearer_centroid_is_not(self):
        """A decoy polygon whose centroid is ~30 km away but excludes the asset."""
        decoy = [[-122.6, 38.0], [-122.2, 38.0], [-122.2, 38.2], [-122.6, 38.2], [-122.6, 38.0]]
        out = _brief([
            _row("hms-plume", [PLUME]),
            _row("hms-decoy", [decoy], density="light", severity=30.0),
        ])
        assert out["ok"] is True
        assert out["inside_smoke"] is True
        assert [item["polygon_id"] for item in out["smoke"]] == ["hms-plume"]
        assert out["smoke_polygon_count"] == 1
        assert out["smoke"][0]["geometry"]["coordinates"] == [PLUME]
        assert out["smoke"][0]["geometry_digest"] == "digest-hms-plume"
        assert out["smoke"][0]["gaia_attestation"]["value"] == "sig"
        # The centroid stays available as a map anchor, never as the proof.
        assert out["smoke"][0]["centroid"]["lat"] == pytest.approx(40.0)

    def test_an_asset_outside_every_polygon_is_answered_not_refused(self):
        out = _brief([_row("hms-plume", [PLUME])], query={"lat": 25.76, "lon": -80.19})
        assert out["ok"] is True
        assert out["inside_smoke"] is False
        assert out["smoke"] == []
        assert out["hms_inventory_total"] == 1
        assert "outside all 1 2026-08-27 HMS polygon(s)" in out["drivers"][0]

    def test_hole_over_the_asset_is_reported_as_outside(self):
        hole = [[-123.0, 37.0], [-121.0, 37.0], [-121.0, 39.0], [-123.0, 39.0], [-123.0, 37.0]]
        out = _brief([_row("hms-donut", [PLUME, hole])])
        assert out["ok"] is True
        assert out["inside_smoke"] is False

    def test_the_worst_covering_polygon_leads(self):
        wide = [[-130.0, 30.0], [-95.0, 30.0], [-95.0, 48.0], [-130.0, 48.0], [-130.0, 30.0]]
        out = _brief([
            _row("hms-light", [PLUME], density="light", severity=30.0),
            _row("hms-heavy", [wide], density="heavy", severity=90.0),
        ])
        assert [item["polygon_id"] for item in out["smoke"]] == ["hms-heavy", "hms-light"]
        assert out["operational_status"] == "action"


class TestRefusals:
    def test_missing_coordinates(self):
        out = smoke_operations({}, [], _air())
        assert out["ok"] is False
        assert "lat and lon are required" in out["refuse_reason"]

    def test_coordinates_outside_wgs84(self):
        out = _brief([_row("hms-plume", [PLUME])], query={"lat": 91.0})
        assert out["ok"] is False
        assert "WGS84" in out["refuse_reason"]

    def test_inventory_not_marked_complete(self):
        out = _brief([_row("hms-plume", [PLUME])], complete=False)
        assert out["ok"] is False
        assert "complete LIVE HMS polygon inventory" in out["refuse_reason"]

    def test_fewer_polygons_than_the_signed_inventory_total(self):
        """A truncated cluster must not answer "outside" for the missing rest."""
        out = _brief([_row("hms-plume", [PLUME])], total=4)
        assert out["ok"] is False
        assert "complete LIVE HMS polygon inventory" in out["refuse_reason"]

    def test_no_smoke_layer_at_all(self):
        out = smoke_operations({"lat": SF[0], "lon": SF[1]}, [], _air())
        assert out["ok"] is False
        assert "complete LIVE HMS polygon inventory" in out["refuse_reason"]

    def test_unevaluable_geometry_refuses_instead_of_reporting_outside(self):
        row = _row("hms-broken", [PLUME])
        row["geometry"] = {"type": "GeometryCollection", "geometries": []}
        out = smoke_operations(
            {"lat": SF[0], "lon": SF[1]},
            [{**_pins([_row("hms-plume", [PLUME])])[0], "geometry": row["geometry"]}],
            _air(),
        )
        assert out["ok"] is False
        assert "could not be evaluated" in out["refuse_reason"]

    @pytest.mark.parametrize(
        "air",
        [
            None,
            {},
            _air(pm25=None, us_aqi=None),
            _air(live=False),
            {"live": True, "values": {"pm2_5_ugm3": "high"}},
        ],
    )
    def test_no_colocated_air_evidence(self, air: Any):
        out = smoke_operations(
            {"lat": SF[0], "lon": SF[1]}, _pins([_row("hms-plume", [PLUME])]), air
        )
        assert out["ok"] is False
        assert "PM2.5/AQI" in out["refuse_reason"]

    def test_a_refusal_never_carries_evidence_or_a_receipt(self):
        out = _brief([_row("hms-plume", [PLUME])], air={})
        assert "smoke" not in out and "receipt" not in out and "air_quality" not in out


class TestOperationalStatus:
    def test_heavy_smoke_over_the_asset_is_action(self):
        out = _brief([_row("hms-plume", [PLUME])])
        assert out["operational_status"] == "action"
        assert out["recommended_actions"][0].startswith("Review outdoor work")

    def test_light_smoke_with_clean_air_is_elevated_not_action(self):
        out = _brief([_row("hms-plume", [PLUME], density="light", severity=30.0)])
        assert out["operational_status"] == "elevated"

    def test_light_smoke_with_unhealthy_pm25_escalates_to_action(self):
        out = _brief(
            [_row("hms-plume", [PLUME], density="light", severity=30.0)],
            air=_air(pm25=61.0, us_aqi=153.0),
        )
        assert out["operational_status"] == "action"

    def test_moderate_air_outside_the_smoke_is_a_watch(self):
        out = _brief(
            [_row("hms-plume", [PLUME])],
            query={"lat": 25.76, "lon": -80.19},
            air=_air(pm25=20.0, us_aqi=68.0),
        )
        assert out["inside_smoke"] is False
        assert out["operational_status"] == "watch"

    def test_clean_air_outside_the_smoke_is_routine(self):
        out = _brief([_row("hms-plume", [PLUME])], query={"lat": 25.76, "lon": -80.19})
        assert out["operational_status"] == "routine"


class TestEvidenceContract:
    def test_receipt_attribution_and_limitations_travel_with_the_answer(self):
        out = _brief([_row("hms-plume", [PLUME])])
        assert out["receipt"]["capability_id"] == "atlas.smoke.operations@v1"
        assert out["receipt"]["digest"]
        assert out["sku"] == "atlas.smoke.operations@v1"
        assert "NOAA/NESDIS Hazard Mapping System (HMS)" in out["attribution"]
        assert any("Open-Meteo" in line for line in out["attribution"])
        assert any("not measured PM2.5" in line for line in out["limitations"])
        assert out["air_quality"]["values"]["pm2_5_ugm3"] == 8.0
        assert out["air_quality"]["kind"] == "modeled_coordinate"
        assert out["air_quality"]["gaia_attestation"]["value"] == "sig"

    def test_asset_id_is_echoed_and_bounded(self):
        out = _brief([_row("hms-plume", [PLUME])], query={"asset_id": "x" * 400})
        assert len(out["query"]["asset_id"]) == 160

    def test_the_brief_names_the_hms_analysis_it_read(self):
        """HMS publishes one dated product per UTC day — "current" was a claim we cannot make.

        The current day's KML does not exist until the first daytime analysis, so the
        answer is routinely decided against an earlier product. Saying which one is the
        difference between evidence and an implied live satellite pass.
        """
        out = _brief([_row("hms-plume", [PLUME])])
        assert out["hms_analysis_date"] == "2026-08-27"
        assert out["hms_analysis_age_hours"] == 25.5
        assert "2026-08-27 HMS smoke polygon(s)" in out["summary"]
        assert "current HMS" not in out["summary"]
        assert any("HMS analysis product date: 2026-08-27" in line for line in out["drivers"])
        assert any(
            "2026-08-27 HMS analysis product" in line and "not a live satellite pass" in line
            for line in out["limitations"]
        )

    def test_an_inventory_spanning_two_product_dates_says_so(self):
        """Two dates in one inventory is a real state, and the buyer has to see it."""
        out = _brief([
            _row("hms-plume", [PLUME], product_date="2026-08-27", product_age_hours=25.5),
            _row("hms-aleutian", [ALEUTIAN], density="light", severity=10.0,
                 product_date="2026-08-28", product_age_hours=6.0),
        ])
        # Newest date labels the answer; the oldest polygon's age is the honest floor.
        assert out["hms_analysis_date"] == "2026-08-28"
        assert out["hms_analysis_age_hours"] == 6.0
        assert any(
            "spans more than one HMS product date" in line and "2026-08-27, 2026-08-28" in line
            for line in out["drivers"]
        )

    def test_a_polygon_without_a_product_date_does_not_invent_one(self):
        """An older GAIA build sends no date; the brief must not fabricate a day."""
        out = _brief([_row("hms-plume", [PLUME], product_date=None, product_age_hours=None)])
        assert out["ok"] is True
        assert out["hms_analysis_date"] is None
        assert out["hms_analysis_age_hours"] is None
        assert any("product date was not supplied" in line for line in out["limitations"])

    def test_invoke_product_routes_the_sku(self):
        out = invoke_product(
            "atlas.smoke.operations@v1",
            {"lat": SF[0], "lon": SF[1]},
            _pins([_row("hms-plume", [PLUME])]),
            air_reading=_air(),
        )
        assert out["ok"] is True
        assert out["inside_smoke"] is True

    def test_invoke_product_without_air_refuses_rather_than_reporting_unhandled(self):
        out = invoke_product(
            "atlas.smoke.operations@v1",
            {"lat": SF[0], "lon": SF[1]},
            _pins([_row("hms-plume", [PLUME])]),
        )
        assert out["ok"] is False
        assert "unhandled capability" not in out["refuse_reason"]
        assert "PM2.5/AQI" in out["refuse_reason"]


class TestGeometryStaysOffTheFreeSurfaces:
    def test_map_pins_carry_only_the_anchor_bbox_and_digest(self):
        pin = _pins([_row("hms-plume", [PLUME])], private=False)[0]
        assert "geometry" not in pin
        assert pin["polygon_id"] == "hms-plume"
        assert pin["geometry_digest"] == "digest-hms-plume"
        assert pin["bbox"] == [-125.0, 35.0, -100.0, 45.0]
        assert pin["id"] == "smoke-poly-hms-plume"

    def test_the_product_path_is_the_only_one_that_carries_geometry(self):
        pin = _pins([_row("hms-plume", [PLUME])])[0]
        assert pin["geometry"]["coordinates"] == [PLUME]
        assert pin["inventory_complete"] is True

    def test_the_point_registry_never_retains_paid_geometry(self, settings):
        """The registry answers free station-detail and ``atlas.point.read@v1``."""
        agg = Aggregator(settings)
        pin = _pins([_row("hms-plume", [PLUME])])[0]
        agg._remember_map_points([pin])
        cached = agg._recent_map_point(pin["id"])
        assert cached is not None
        assert "geometry" not in cached
        assert cached["geometry_digest"] == "digest-hms-plume"
