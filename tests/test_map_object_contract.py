"""Every ATLAS section obeys one counter → map object → detail contract."""

from __future__ import annotations

from atlas.fleet import DENSE_EVENT_LAYERS, expand_map_objects
from atlas.layer_counts import build_layer_counts
from atlas.stations import LAYER_META


def test_every_layer_count_matches_its_expandable_map_objects():
    rows = []
    for index, layer in enumerate(LAYER_META):
        base = {
            "id": f"contract-{layer}",
            "layer": layer,
            "label": f"Contract {layer}",
            "kind": "point",
            "lat": float(-50 + index),
            "lon": float(10 + index),
            "online": True,
            "live": True,
            "has_reading": True,
        }
        if layer in DENSE_EVENT_LAYERS:
            base.update(
                {
                    "kind": "event",
                    "cluster_parent": True,
                    "hotspot_count": 2,
                    "hotspots": [
                        {
                            "severity_score": 70.0,
                            "latitude": float(-40 + index),
                            "longitude": float(20 + index),
                        },
                        {
                            "severity_score": 30.0,
                            "latitude": float(-39 + index),
                            "longitude": float(21 + index),
                        },
                    ],
                }
            )
        rows.append(base)

    counts = build_layer_counts(rows, LAYER_META.keys())
    expanded = expand_map_objects(rows)
    for layer in LAYER_META:
        map_count = sum(1 for point in expanded if point.get("layer") == layer)
        assert counts[layer]["count"] == map_count, layer
        assert map_count > 0, layer


def test_argo_points_use_stable_wmo_identity_not_moving_coordinates():
    parent = {
        "id": "argo-01",
        "layer": "argo",
        "label": "Global Argo",
        "online": True,
        "live": True,
        "hotspots": [
            {
                "wmo": "6901234",
                "latitude": -42.0,
                "longitude": 80.0,
                "observed_at": "2026-08-12T00:00:00Z",
                "profile_url": "https://data-argo.ifremer.fr/dac/coriolis/6901234/profiles/R6901234_007.nc",
            }
        ],
    }
    first = expand_map_objects([parent])[0]
    parent["hotspots"][0]["latitude"] = -41.5
    moved = expand_map_objects([parent])[0]
    assert first["id"] == moved["id"] == "argo-wmo-6901234"
    assert moved["wmo"] == "6901234"
