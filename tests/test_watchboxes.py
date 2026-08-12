"""Watchbox store + evaluation over free-to-commercialize layers."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas.watchboxes import (
    ALLOWED_WATCHBOX_LAYERS,
    WatchboxStore,
    evaluate_watchbox,
    point_in_bbox,
)


def test_allowed_layers_include_open_relays():
    assert {"fire", "radiation", "jamming", "traffic", "quake"} <= ALLOWED_WATCHBOX_LAYERS


def test_point_in_bbox_and_antimeridian():
    assert point_in_bbox(52.5, 13.4, west=12.0, south=52.0, east=14.0, north=53.0)
    assert not point_in_bbox(40.7, -74.0, west=12.0, south=52.0, east=14.0, north=53.0)
    assert point_in_bbox(0.0, 179.0, west=170.0, south=-10.0, east=-170.0, north=10.0)


def test_store_create_check_delete(tmp_path: Path):
    store = WatchboxStore(path=tmp_path / "watchboxes.json")
    row = store.create(
        west=-80.0,
        south=35.0,
        east=-70.0,
        north=45.0,
        layers=["fire", "quake", "bogus-nc"],
        label="US East events",
        watchbox_id="wb-test-01",
    )
    assert row["layers"] == ["fire", "quake"]
    assert store.get("wb-test-01")
    stations = [
        {
            "id": "firms-fire-01",
            "layer": "fire",
            "label": "Fire",
            "lat": 40.0,
            "lon": -75.0,
            "headline": "Fire 380 K",
            "live": True,
            "source": "https://firms.modaps.eosdis.nasa.gov",
            "values": {"brightness_k": 380.0},
        },
        {
            "id": "outside",
            "layer": "fire",
            "label": "Far",
            "lat": 10.0,
            "lon": 10.0,
            "headline": "x",
            "live": True,
            "values": {},
        },
        {
            "id": "unset-event",
            "layer": "fire",
            "label": "Unset",
            "lat": 0.0,
            "lon": 0.0,
            "headline": "—",
            "live": True,
            "values": {},
        },
    ]
    result = evaluate_watchbox(row, stations)
    assert result["match_count"] == 1
    assert result["matches"][0]["id"] == "firms-fire-01"
    assert result["sku"] == "atlas.watchbox.subscribe@v1"
    assert store.delete("wb-test-01")
    assert store.get("wb-test-01") is None


def test_rejects_empty_layers(tmp_path: Path):
    store = WatchboxStore(path=tmp_path / "watchboxes.json")
    with pytest.raises(ValueError):
        store.create(
            west=0, south=0, east=1, north=1, layers=["not-a-real-layer"]
        )


def test_rejects_localhost_webhook(tmp_path: Path):
    store = WatchboxStore(path=tmp_path / "watchboxes.json")
    with pytest.raises(ValueError):
        store.create(
            west=0,
            south=0,
            east=1,
            north=1,
            layers=["weather"],
            webhook_url="https://localhost/hook",
        )
