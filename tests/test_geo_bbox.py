"""Viewport normalization — MapLibre bounds are not wrapped to ±180.

Regression: zoomed out (world narrower than the canvas) the map client sent
west=-239 / east=+240 and every POST /api/v1/viewport answered 422, so the
in-view panel showed "viewport error" on the default desktop view.
"""

from __future__ import annotations

import pytest

from atlas.geo import in_bbox, normalize_bbox, wrap_lon


def test_wrap_lon_passthrough_in_range():
    assert wrap_lon(0.0) == 0.0
    assert wrap_lon(-180.0) == -180.0
    assert wrap_lon(180.0) == 180.0
    assert wrap_lon(13.41) == pytest.approx(13.41)


def test_wrap_lon_wraps_out_of_range():
    assert wrap_lon(190.0) == pytest.approx(-170.0)
    assert wrap_lon(-190.0) == pytest.approx(170.0)
    assert wrap_lon(540.0) == pytest.approx(-180.0)


def test_normalize_bbox_keeps_valid_viewport():
    assert normalize_bbox(12.5, 52.3, 14.0, 52.7) == (12.5, 52.3, 14.0, 52.7)


def test_normalize_bbox_collapses_world_span():
    # What MapLibre reports at zoom ≈ 0.5 on a 1280px canvas.
    assert normalize_bbox(-239.34, -85.05, 240.65, 85.05) == (
        -180.0,
        -85.05,
        180.0,
        85.05,
    )


def test_normalize_bbox_wraps_antimeridian_window():
    west, south, east, north = normalize_bbox(170.0, -10.0, 190.0, 10.0)
    assert west == pytest.approx(170.0)
    assert east == pytest.approx(-170.0)
    assert (south, north) == (-10.0, 10.0)
    # west > east is a valid wrapped window for the bbox test.
    assert in_bbox(0.0, 179.0, west, south, east, north)
    assert in_bbox(0.0, -179.0, west, south, east, north)
    assert not in_bbox(0.0, 0.0, west, south, east, north)


def test_normalize_bbox_clamps_and_orders_latitude():
    assert normalize_bbox(0.0, 120.0, 1.0, -95.0) == (0.0, -90.0, 1.0, 90.0)


@pytest.mark.asyncio
async def test_refresh_viewport_accepts_unwrapped_bounds(aggregator):
    """Server-side safety net: the Analyst bbox is not schema-validated."""
    out = await aggregator.refresh_viewport(
        west=-239.34, south=-85.05, east=240.65, north=85.05
    )
    assert out["ok"] is True
    assert out["bbox"] == {
        "west": -180.0,
        "south": -85.05,
        "east": 180.0,
        "north": 85.05,
    }
    # Whole world → every catalog pin is inside the viewport.
    assert len(out["requested"]) >= 12


@pytest.mark.asyncio
async def test_viewport_route_accepts_normalized_world_bbox(client):
    r = await client.post(
        "/api/v1/viewport",
        json={"west": -180, "south": -85.05, "east": 180, "north": 85.05},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ── wrap-aware padding (review follow-up) ────────────────────────────────────


def test_lon_span_is_wrap_aware():
    from atlas.geo import lon_span

    assert lon_span(10.0, 20.0) == pytest.approx(10.0)
    assert lon_span(170.0, -170.0) == pytest.approx(20.0)


def test_pad_lon_grows_a_wrapped_window_instead_of_inverting_it():
    from atlas.geo import pad_lon

    west, east = pad_lon(170.0, -170.0, 4.0)
    # Still wrapped, and 8° wider — never flipped into its own complement.
    assert west == pytest.approx(166.0)
    assert east == pytest.approx(-166.0)
    assert west > east


def test_pad_lon_saturates_to_the_whole_world():
    from atlas.geo import pad_lon

    assert pad_lon(-170.0, 170.0, 25.0) == (-180.0, 180.0)


def test_region_pin_survives_a_wrapped_viewport():
    """uk-grid-01 is a `region` pin — padding must not drop it (or the world)."""
    from atlas.geo import station_ids_in_bbox

    stations = [
        {"id": "uk-grid-01", "lat": 54.0, "lon": -2.0, "kind": "region"},
        {"id": "om-wx-tokyo", "lat": 35.68, "lon": 139.65, "kind": "point"},
    ]
    # Wrapped window over the Pacific: neither station is inside it.
    ids = station_ids_in_bbox(stations, 150.0, 0.0, -150.0, 60.0)
    assert ids == []
    # Wrapped window that does contain Tokyo.
    ids = station_ids_in_bbox(stations, 100.0, 0.0, -150.0, 60.0)
    assert "om-wx-tokyo" in ids
    # A window around the UK keeps the region pin.
    ids = station_ids_in_bbox(stations, -10.0, 50.0, 5.0, 58.0)
    assert "uk-grid-01" in ids


def test_expand_bbox_keeps_a_wrapped_window_usable():
    from atlas.geo import expand_bbox, in_bbox

    west, south, east, north = expand_bbox(170.0, -10.0, -170.0, 10.0, 5.0)
    assert west > east  # still the wrapped form
    assert in_bbox(0.0, 179.0, west, south, east, north)
    assert not in_bbox(0.0, 0.0, west, south, east, north)
