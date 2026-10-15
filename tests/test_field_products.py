"""ATLAS field products — in-situ mesh × certified math."""

from __future__ import annotations

import json
import math

import pytest

from atlas.field_math import aggregate, h0_persistence, halton, rbf_gp_posterior
from atlas.field_products import (
    field_consensus,
    field_posterior,
    field_shape,
    mesh_sample,
)
from atlas.products import invoke_product


def _ee(i: int, lat: float, lon: float, temp: float, *, live: bool = True) -> dict:
    return {
        "id": f"ee-wx-station-{i:02d}",
        "layer": "weather",
        "live": live,
        "mode": "live" if live else "sim",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": f"EE {i}",
        "values": {"temperature_c": temp},
        "source": "https://www.ilmateenistus.ee",
    }


EEST = [
    _ee(1, 59.40, 24.60, 8.1),
    _ee(2, 58.26, 26.46, 7.8),
    _ee(3, 58.38, 24.48, 8.4),
    _ee(4, 59.39, 28.11, 6.9),
    _ee(5, 58.26, 22.49, 9.2),
    _ee(6, 57.85, 27.02, 7.1),
]


def test_murmuration_equivalent_rejects_outlier():
    clean = [10.0, 10.1, 9.9, 10.2, 9.8, 10.05, 9.95, 10.15, 9.85, 10.0]
    poisoned = clean + [10_000.0]
    base = aggregate(clean)
    hit = aggregate(poisoned)
    assert abs(hit["biweight"] - base["biweight"]) < 0.5
    assert abs(sum(poisoned) / len(poisoned) - sum(clean) / len(clean)) > 100


def test_halton_is_deterministic():
    assert halton(4, 2, skip=3) == halton(4, 2, skip=3)
    assert halton(4, 2, skip=0) != halton(4, 2, skip=3)


def test_consensus_refuses_open_meteo():
    out = field_consensus({"mesh_id": "om-wx"}, EEST)
    assert out["ok"] is False
    assert "Open-Meteo" in out["refuse_reason"]


def test_consensus_refuses_sim_only():
    sims = [_ee(i, 59.0, 24.0, 10.0, live=False) for i in range(4)]
    out = field_consensus({"mesh_id": "ee-wx"}, sims)
    assert out["ok"] is False
    assert "all clear" in out["refuse_reason"]


def test_consensus_ignores_one_broken_station():
    stations = list(EEST) + [_ee(99, 59.4, 24.7, 999.0)]
    out = field_consensus({"mesh_id": "ee-wx"}, stations)
    assert out["ok"] is True
    assert out["claim_class"] == "in_situ_observation"
    assert out["quantity"] == "temperature_c"
    assert abs(out["consensus"]["biweight"] - 8.0) < 2.0
    assert out["consensus"]["biweight"] < 50
    assert out["sibling_oracle"] == "murmuration.aggregate@v1"
    assert out["receipt"]["digest"]
    assert out["live_count"] == 7


def test_mesh_sample_is_replayable_and_not_all_pins():
    a = mesh_sample({"mesh_id": "ee-wx", "count": 3, "skip": 0}, EEST)
    b = mesh_sample({"mesh_id": "ee-wx", "count": 3, "skip": 0}, EEST)
    c = mesh_sample({"mesh_id": "ee-wx", "count": 3, "skip": 7}, EEST)
    assert a["ok"] and b["ok"] and c["ok"]
    assert a["device_ids"] == b["device_ids"]
    assert a["method"] == "halton/van-der-corput"
    assert len(a["device_ids"]) == 3
    assert a["device_ids"] != c["device_ids"]


def test_sample_then_consensus_composes():
    sample = mesh_sample({"mesh_id": "ee-wx", "count": 4}, EEST)
    assert sample["ok"]
    fused = field_consensus(
        {"mesh_id": "ee-wx", "device_ids": sample["device_ids"], "min_live": 3},
        EEST,
    )
    assert fused["ok"] is True
    assert fused["live_count"] == 4
    assert {c["id"] for c in fused["citations"]} == set(sample["device_ids"])


def test_posterior_is_not_a_forecast():
    out = field_posterior({"mesh_id": "ee-wx", "lat": 58.6, "lon": 25.0}, EEST)
    assert out["ok"] is True
    assert out["posterior"]["std"] >= 0
    assert "forecast" in " ".join(out["limitations"]).lower()
    assert out["sibling_oracle"] == "gauss.field@v1"
    assert out["suggest"]["posterior_std"] >= 0


def test_shape_h0_not_betti_one():
    out = field_shape({"mesh_id": "ee-wx"}, EEST)
    assert out["ok"] is True
    assert out["homology"]["filtration"] == "vietoris-rips-h0"
    assert out["homology"]["series"][0]["components"] == len(EEST)
    assert "Betti-1" in " ".join(out["limitations"])


def test_shape_refuses_fewer_than_three_pins():
    out = field_shape({"mesh_id": "ee-wx"}, EEST[:2])
    assert out["ok"] is False
    assert "3" in out["refuse_reason"]
    assert out["capability_id"] == "atlas.field.shape@v1"


def test_gp_rejects_non_finite_train():
    with pytest.raises(ValueError, match="finite"):
        rbf_gp_posterior([(59.4, 24.6, float("nan")), (58.3, 26.5, 8.0)], [(59.0, 25.0)])


def test_h0_rejects_non_finite_points():
    with pytest.raises(ValueError, match="finite"):
        h0_persistence([(0.0, 0.0), (float("inf"), 1.0)])


def test_gp_interpolates_training_point_closely():
    train = [(59.4, 24.6, 8.0), (58.3, 26.5, 8.0), (58.4, 24.5, 8.0)]
    post = rbf_gp_posterior(train, [(59.4, 24.6)], length_km=80)[0]
    assert abs(post["mean"] - 8.0) < 0.3
    assert post["std"] < 0.5


def test_h0_starts_disconnected():
    out = h0_persistence([(0.0, 0.0), (10.0, 10.0), (20.0, 20.0)], max_km=50, steps=4)
    assert out["series"][0]["components"] == 3


def test_invoke_routes_field_skus():
    out = invoke_product("atlas.field.consensus@v1", {"mesh_id": "ee-wx"}, EEST)
    assert out["ok"] is True


def test_unknown_mesh_lists_known():
    out = field_consensus({"mesh_id": "narnia"}, EEST)
    assert out["ok"] is False
    assert "ee-wx" in out["refuse_reason"]


def test_ea_river_does_not_swallow_flood_warning():
    stations = [
        {
            "id": "ea-flood-01", "layer": "flood", "live": True, "lat": 51.5, "lon": -0.1,
            "values": {"discharge_m3s": 1.0}, "source": "warning",
        },
        {
            "id": "ea-kingston-01", "layer": "river", "live": True, "lat": 51.4, "lon": -0.3,
            "values": {"discharge_m3s": 40.0}, "source": "https://environment.data.gov.uk",
        },
        {
            "id": "ea-oxford-01", "layer": "river", "live": True, "lat": 51.75, "lon": -1.26,
            "values": {"discharge_m3s": 22.0}, "source": "https://environment.data.gov.uk",
        },
        {
            "id": "ea-reading-01", "layer": "river", "live": True, "lat": 51.46, "lon": -0.97,
            "values": {"discharge_m3s": 30.0}, "source": "https://environment.data.gov.uk",
        },
    ]
    out = field_consensus({"mesh_id": "ea-river", "min_live": 3}, stations)
    assert out["ok"] is True
    ids = {c["id"] for c in out["citations"]}
    assert "ea-flood-01" not in ids
    assert "ea-kingston-01" in ids


def test_sim_flag_or_mode_never_counts_as_live():
    """live=False or mode=sim must drop the pin even if the other flag lies."""
    mixed = [
        _ee(1, 59.40, 24.60, 8.1),
        _ee(2, 58.26, 26.46, 7.8),
        _ee(3, 58.38, 24.48, 8.4),
        {
            **_ee(4, 59.39, 28.11, 6.9, live=False),
            "mode": "live",  # inconsistent — still SIM
        },
        {
            **_ee(5, 58.26, 22.49, 9.2, live=True),
            "mode": "sim",  # inconsistent — still SIM
        },
    ]
    out = field_consensus({"mesh_id": "ee-wx", "min_live": 3}, mixed)
    assert out["ok"] is True
    assert out["live_count"] == 3
    assert out["dropped_sim_count"] == 2
    assert {c["id"] for c in out["citations"]} == {
        "ee-wx-station-01", "ee-wx-station-02", "ee-wx-station-03",
    }


def test_open_meteo_cannot_spoof_mesh_via_parent_id():
    stations = [
        {
            "id": "om-wx-01",
            "parent_id": "ee-wx-01",
            "layer": "weather",
            "live": True,
            "mode": "live",
            "lat": 59.4,
            "lon": 24.6,
            "values": {"temperature_c": 99.0},
            "source": "https://open-meteo.com",
        },
        *_ee_list_for_min_live(),
    ]
    out = field_consensus({"mesh_id": "ee-wx", "min_live": 3}, stations)
    assert out["ok"] is True
    assert "om-wx-01" not in {c["id"] for c in out["citations"]}


def test_ea_flood_prefix_not_only_exact_id():
    stations = [
        {
            "id": "ea-flood-area-99", "layer": "flood", "live": True, "lat": 51.5, "lon": -0.1,
            "values": {"discharge_m3s": 1.0}, "source": "warning",
        },
        {
            "id": "ea-kingston-01", "layer": "river", "live": True, "lat": 51.4, "lon": -0.3,
            "values": {"discharge_m3s": 40.0}, "source": "https://environment.data.gov.uk",
        },
        {
            "id": "ea-oxford-01", "layer": "river", "live": True, "lat": 51.75, "lon": -1.26,
            "values": {"discharge_m3s": 22.0}, "source": "https://environment.data.gov.uk",
        },
        {
            "id": "ea-reading-01", "layer": "river", "live": True, "lat": 51.46, "lon": -0.97,
            "values": {"discharge_m3s": 30.0}, "source": "https://environment.data.gov.uk",
        },
    ]
    out = field_consensus({"mesh_id": "ea-river", "min_live": 3}, stations)
    assert out["ok"] is True
    assert "ea-flood-area-99" not in {c["id"] for c in out["citations"]}


def test_mesh_sample_omits_non_finite_pin_values():
    stations = [
        _ee(1, 59.40, 24.60, float("nan")),
        _ee(2, 58.26, 26.46, 7.8),
        _ee(3, 58.38, 24.48, 8.4),
        _ee(4, 59.39, 28.11, 6.9),
    ]
    out = mesh_sample({"mesh_id": "ee-wx", "count": 4}, stations)
    assert out["ok"] is True
    for pin in out["pins"]:
        if "value" in pin:
            assert math.isfinite(pin["value"])
    # Receipt body must be strict JSON (no NaN tokens).
    body = {k: v for k, v in out.items() if k not in ("receipt", "receipt_url", "verifier_url")}
    json.dumps(body, allow_nan=False)


def test_posterior_refuses_non_finite_query_and_length():
    out = field_posterior(
        {"mesh_id": "ee-wx", "lat": float("nan"), "lon": 25.0}, EEST,
    )
    assert out["ok"] is False
    assert "finite" in out["refuse_reason"]
    out = field_posterior({"mesh_id": "ee-wx", "length_km": float("nan")}, EEST)
    assert out["ok"] is False
    assert "length_km" in out["refuse_reason"]
    body = {k: v for k, v in out.items() if k not in ("receipt", "receipt_url", "verifier_url")}
    json.dumps(body, allow_nan=False)


def test_shape_refuses_non_finite_max_km():
    out = field_shape({"mesh_id": "ee-wx", "max_km": float("inf")}, EEST)
    assert out["ok"] is False
    assert "max_km" in out["refuse_reason"]


def test_non_finite_coordinates_are_dropped_not_trained():
    stations = [
        {**_ee(1, 59.40, 24.60, 8.1), "lat": float("nan")},
        _ee(2, 58.26, 26.46, 7.8),
        _ee(3, 58.38, 24.48, 8.4),
        _ee(4, 59.39, 28.11, 6.9),
    ]
    out = field_posterior({"mesh_id": "ee-wx", "lat": 58.5, "lon": 25.0}, stations)
    assert out["ok"] is True
    assert out["train_count"] == 3
    assert math.isfinite(out["posterior"]["mean"])
    assert "ee-wx-station-01" not in {c["id"] for c in out["citations"]}


def _ee_list_for_min_live():
    return [
        _ee(1, 59.40, 24.60, 8.1),
        _ee(2, 58.26, 26.46, 7.8),
        _ee(3, 58.38, 24.48, 8.4),
    ]
