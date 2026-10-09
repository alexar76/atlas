"""GNSS integrity map and product contracts."""

from __future__ import annotations

from atlas.fleet import expand_map_objects
from atlas.gnss_index import integrity_counts
from atlas.layer_counts import build_layer_counts
from atlas.products import CAP_BY_ID, gnss_degradation, point_read
from atlas.stations import LAYER_META


def _parent() -> dict:
    return {
        "id": "gnss-euref-01",
        "layer": "gnss",
        "label": "EUREF GNSS Integrity Network",
        "kind": "event",
        "online": True,
        "live": True,
        "mode": "live",
        "source": "EUREF EPN CC BY 4.0",
        "color": "#34d399",
        "values": {"latitude": 50.8, "longitude": 4.35},
        "hotspots": [
            {
                "point_id": "gnss-station:euref:BRUX00BEL",
                "station_id": "BRUX00BEL",
                "network": "EUREF EPN",
                "latitude": 50.7981,
                "longitude": 4.3586,
                "availability_pct": 98.0,
                "latency_s": 17.0,
                "degradation_score": 8.0,
                "confidence": 0.72,
                "state": "normal",
                "claim_class": "derived_degradation",
                "cause": "unestablished",
                "source_url": "https://www.epncb.oma.be/_networkdata/stationlist.php",
                "license": "CC BY 4.0",
            },
            {
                "point_id": "gnss-station:euref:ONSA00SWE",
                "station_id": "ONSA00SWE",
                "network": "EUREF EPN",
                "latitude": 57.3953,
                "longitude": 11.9255,
                "degradation_score": 72.0,
                "confidence": 0.5,
                "state": "degraded",
                "claim_class": "derived_degradation",
                "cause": "unestablished",
            },
        ],
        "hotspot_count": 2,
    }


def test_every_gnss_station_becomes_exact_addressable_point():
    points = expand_map_objects([_parent()])
    station_ids = {p["id"] for p in points if p["id"].startswith("gnss-station:")}
    assert station_ids == {
        "gnss-station:euref:BRUX00BEL", "gnss-station:euref:ONSA00SWE",
    }
    cells = [p for p in points if p["id"].startswith("gnss-cell:")]
    assert cells
    assert all(len(cell["boundary"]) >= 5 for cell in cells)
    cell_read = point_read({"point_id": cells[0]["id"]}, points)
    assert cell_read["resolution"]["kind"] == "derived_integrity_cell"
    assert cell_read["point"]["station_ids"]
    exact = point_read({"point_id": points[0]["id"]}, [points[0]])
    assert exact["ok"] is True
    assert exact["parent_capability"]["targeting"] == "exact"
    assert exact["parent_capability"]["input"]["station_id"]
    assert exact["resolution"]["kind"] == "source_addressable_read"


def test_geoscience_australia_station_keeps_its_exact_network_identity():
    parent = {
        **_parent(),
        "id": "gnss-ga-01",
        "label": "Geoscience Australia GNSS Network",
        "source": "Geoscience Australia CC BY 3.0 AU",
        "hotspots": [{
            "point_id": "gnss-station:ga:ALIC",
            "station_id": "ALIC",
            "network": "Geoscience Australia",
            "latitude": -23.6701,
            "longitude": 133.8855,
            "state": "unknown",
            "claim_class": "inventory_only",
            "cause": "unestablished",
        }],
        "hotspot_count": 1,
    }
    points = expand_map_objects([parent])
    assert [p["id"] for p in points if p["id"].startswith("gnss-station:")] == ["gnss-station:ga:ALIC"]
    exact = point_read({"point_id": "gnss-station:ga:ALIC"}, points)
    assert exact["parent_capability"]["input"] == {
        "device_id": "gnss-ga-01", "station_id": "ALIC",
    }


def test_gnss_degradation_is_a_public_catalog_capability():
    cap = CAP_BY_ID["atlas.gnss.degradation.read@v1"]
    assert cap["price_per_call_usd"] == 0.05
    assert {"lat", "lon", "route", "west", "south", "east", "north"}.issubset(
        cap["input_schema"]["properties"]
    )


def test_gnss_layer_counter_counts_clickable_stations_not_parent_source():
    counts = build_layer_counts([_parent()], LAYER_META.keys())
    assert counts["gnss"]["count"] == 2
    assert counts["gnss"]["count_kind"] == "stations"


def test_degradation_product_keeps_derived_and_reported_claims_separate():
    points = expand_map_objects([_parent()])
    event = {
        "id": "jam-ev-test", "parent_id": "cybernews-jam-01", "layer": "jamming",
        "lat": 50.81, "lon": 4.36, "live": True, "mode": "live",
        "source": "CyberNews CC BY 4.0", "values": {"severity_score": 80, "radius_km": 20},
    }
    out = gnss_degradation({"lat": 50.8, "lon": 4.35, "max_km": 100}, points + [event])
    assert out["ok"] is True
    assert out["coverage"]["stations"] == 1
    assert out["observations"][0]["claim_class"] == "derived_degradation"
    assert out["observations"][0]["claim_level"] == "derived_degradation"
    assert out["observations"][0]["degradation_score"] == 8.0
    assert out["observations"][0]["reported_interference_score"] == 80.0
    assert out["observations"][0]["interference_events"][0]["claim_level"] == "jamming_reported"
    assert out["observations"][0]["cause"] == "unestablished"
    assert out["cells"][0]["contributions"]
    assert out["cells"][0]["point_id"].startswith("gnss-cell:")
    assert out["receipt"]["digest"]
    assert out["receipt"]["signature_status"] in {
        "signed", "unavailable_missing_runtime_dependency",
    }
    assert "not RF power" in out["evidence_boundary"]
    for key in ("summary", "evidence", "receipt_url", "verifier_url"):
        assert key in out
    assert out["summary"]["state"] == "normal"
    assert out["summary"]["score"] == 8.0
    assert out["summary"]["claim_level"] in {"derived_degradation", "jamming_reported"}
    assert out["evidence"]
    assert "/api/v1/receipts/" in out["receipt_url"]
    assert "verify.modelmarket.dev" in out["verifier_url"]


def test_degradation_refuses_to_call_no_coverage_normal():
    out = gnss_degradation({"lat": -80, "lon": 0, "max_km": 1}, expand_map_objects([_parent()]))
    assert out["ok"] is False
    assert out["coverage"]["claim"] == "no_coverage"
    assert out["summary"]["state"] == "unknown"
    assert out["summary"]["score"] is None
    assert out["evidence"] == []
    assert "receipt_url" in out
    assert "verifier_url" in out


def test_integrity_counts_name_stations_not_two_parents():
    """Spec §4.2: sidebar totals come from inventory, not the wire parent count."""
    counts = integrity_counts([
        {
            "id": "gnss-euref-01", "layer": "gnss", "online": True,
            "inventory_total": 400, "hotspot_count": 400,
        },
        {
            "id": "gnss-ga-01", "layer": "gnss", "online": True,
            "inventory_total": 120, "hotspot_count": 120,
        },
    ])
    assert counts["stations_total"] == 520
    assert counts["stations_total"] != 2
    assert counts["reported_interference_zones"] == 0


def test_degradation_copy_does_not_claim_rf_sensing():
    """Keep gaia.jamming.read (curated intel) distinct from this derived field."""
    cap = CAP_BY_ID["atlas.gnss.degradation.read@v1"]
    text = cap["description"].lower()
    assert "not proof of rf jamming" in text
    assert "raw rf sensing" not in text


def test_antimeridian_bbox_selects_both_sides_of_the_world():
    parent = {
        **_parent(),
        "hotspots": [
            {
                "point_id": "gnss-station:euref:EAST00FJI", "station_id": "EAST00FJI",
                "network": "EUREF EPN", "latitude": -17.7, "longitude": 179.4,
                "state": "unknown", "claim_class": "inventory_only",
            },
            {
                "point_id": "gnss-station:euref:WEST00FJI", "station_id": "WEST00FJI",
                "network": "EUREF EPN", "latitude": -17.8, "longitude": -179.5,
                "state": "unknown", "claim_class": "inventory_only",
            },
        ],
        "hotspot_count": 2,
    }
    out = gnss_degradation(
        {"west": 170, "south": -20, "east": -170, "north": -15},
        expand_map_objects([parent]),
    )
    assert out["ok"] is True
    assert out["coverage"]["stations"] == 2
    assert all(cell["state"] == "unknown" for cell in out["cells"])
    assert out["grid_scheme"] in {"h3-r4", "atlas-r4-fallback"}
