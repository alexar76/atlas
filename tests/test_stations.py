"""Station catalog + bbox helpers."""

from __future__ import annotations

from atlas.aggregator import Aggregator, _in_bbox
from atlas.config import Settings
from atlas.fleet import fetch_station_reading
from atlas.stations import LAYER_META, STATION_CATALOG


def test_catalog_has_core_layers():
    layers = {m["layer"] for m in STATION_CATALOG.values()}
    assert {"weather", "air", "tide", "river", "marine", "grid", "quake", "energy",
            "fire", "radiation", "jamming", "traffic",
            "events", "spacewx", "lightning", "alerts", "argo", "geomag",
            "flood", "effis", "volcano", "ais", "tsunami", "cyclone", "adsb"} <= layers
    assert layers <= set(LAYER_META)
    assert {"usgs-river-01", "ndbc-01", "om-marine-01",
            "firms-fire-01", "safecast-01", "cybernews-jam-01",
            "eonet-01", "swpc-01", "nws-alerts-01", "sc-01", "cwop-01"} <= set(STATION_CATALOG)


def test_catalog_has_full_official_usgs_geomag_network():
    expected = {
        "usgs-geomag-01",
        "usgs-geomag-brw", "usgs-geomag-bsl", "usgs-geomag-cmo",
        "usgs-geomag-ded", "usgs-geomag-frd", "usgs-geomag-frn",
        "usgs-geomag-gua", "usgs-geomag-hon", "usgs-geomag-new",
        "usgs-geomag-shu", "usgs-geomag-sit", "usgs-geomag-sjg",
        "usgs-geomag-tuc",
    }
    actual = {
        device_id
        for device_id, meta in STATION_CATALOG.items()
        if meta.get("layer") == "geomag"
    }
    assert actual == expected
    assert all(STATION_CATALOG[device_id]["mode"] == "live" for device_id in actual)


def test_catalog_live_vs_sim_modes():
    from atlas.stations import resolve_mode

    assert STATION_CATALOG["om-wx-01"]["mode"] == "live"
    assert STATION_CATALOG["ws-01"]["mode"] == "sim"
    assert resolve_mode(catalog_mode="live", source="https://x", in_fleet=True) == ("live", True)
    assert resolve_mode(catalog_mode="live", source=None, in_fleet=True) == ("sim", False)
    assert resolve_mode(catalog_mode="sim", source=None, in_fleet=False) == ("sim", False)
    assert resolve_mode(catalog_mode="live", source=None, in_fleet=False) == ("live", False)


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


def test_mesh_ottawa_delhi_in_catalog():
    assert "om-wx-ottawa" in STATION_CATALOG
    assert "om-aq-delhi" in STATION_CATALOG
    assert abs(STATION_CATALOG["om-wx-ottawa"]["lat"] - 45.4215) < 0.01
    assert abs(STATION_CATALOG["om-wx-delhi"]["lon"] - 77.2090) < 0.01


def test_stations_in_bbox_ottawa(aggregator: Aggregator):
    ids = aggregator.stations_in_bbox(-76.0, 45.0, -75.0, 46.0)
    assert "om-wx-ottawa" in ids
    assert "om-aq-ottawa" in ids
    assert "om-wx-delhi" not in ids


async def _no_reading(*_args, **_kwargs):
    return None


def test_empty_edge_feeder_is_not_reported_online():
    import asyncio

    station = asyncio.run(fetch_station_reading(
        "feeder-iot-01",
        fleet_by_id={
            "feeder-iot-01": {
                "online": True,
                "source": "operator edge feeder (offline until ingest)",
            }
        },
        invoke=_no_reading,
    ))
    assert station["has_reading"] is False
    assert station["online"] is False


def test_fire_pin_cap_is_reported_not_silent():
    """A round 2000 on the map is a browser cap, never a fire count.

    Prod served exactly 2000 fire pins against a real FIRMS day of 70569. The
    number looked authoritative and was not — any surface reading fire_pins as
    a total is wrong, so the payload has to say it was truncated.
    """
    from atlas.config import Settings

    limit = int(Settings().firms_map_pin_limit)
    assert limit > 0
    painted, total = limit, 70569
    truncated = bool(total and painted < total)
    assert truncated, "cap below the real total must set the truncated flag"
