"""Station catalog + bbox helpers."""

from __future__ import annotations

from app.aggregator import Aggregator, _in_bbox
from app.config import Settings
from app.stations import LAYER_META, STATION_CATALOG


def test_catalog_has_core_layers():
    layers = {m["layer"] for m in STATION_CATALOG.values()}
    assert {"weather", "air", "tide", "grid", "quake"} <= layers
    assert set(LAYER_META) == layers or layers <= set(LAYER_META)


def test_catalog_capabilities_present():
    for did, meta in STATION_CATALOG.items():
        assert meta["capability"].startswith("gaia.")
        assert -90 <= float(meta["lat"]) <= 90 or meta["layer"] == "quake"
        assert meta["kind"] in {"point", "region", "event"}


def test_in_bbox_simple():
    assert _in_bbox(52.5, 13.4, 12.0, 52.0, 14.0, 53.0)
    assert not _in_bbox(40.7, -74.0, 12.0, 52.0, 14.0, 53.0)


def test_in_bbox_antimeridian():
    # west > east → wrap across 180°
    assert _in_bbox(10.0, 179.0, 170.0, 0.0, -170.0, 20.0)
    assert _in_bbox(10.0, -179.0, 170.0, 0.0, -170.0, 20.0)
    assert not _in_bbox(10.0, 0.0, 170.0, 0.0, -170.0, 20.0)


def test_stations_in_bbox_berlin(aggregator: Aggregator):
    ids = aggregator.stations_in_bbox(12.5, 52.3, 14.0, 52.7)
    assert "om-wx-01" in ids
    assert "om-aq-01" in ids
    assert "nws-01" not in ids  # NYC
