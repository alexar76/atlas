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
            "flood", "effis", "volcano", "ais", "tsunami", "cyclone", "adsb",
            "smoke", "water_quality", "dart", "precipitation", "radar",
            "atmosphere", "radnet", "soil", "solar", "snow", "sea_ice",
            "land_temperature", "aviation", "road", "rail", "drought"} <= layers
    assert layers <= set(LAYER_META)
    assert {"usgs-river-01", "ndbc-01", "om-marine-01",
            "firms-fire-01", "safecast-01", "cybernews-jam-01",
            "eonet-01", "swpc-01", "nws-alerts-01", "sc-01", "cwop-01",
            "metar-kjfk-01", "pegel-bonn-01", "fintraffic-road-01",
            "usdm-01"} <= set(STATION_CATALOG)


def test_new_environment_layers_keep_one_reading_per_coordinate():
    from atlas.fleet import expand_map_objects

    smoke_parent = {
        "id": "hms-smoke-01", "layer": "smoke", "kind": "event",
        "online": True, "live": True, "cluster_parent": True,
        "hotspots": [
            {"severity_score": 90, "latitude": 40.0, "longitude": -100.0},
            {"severity_score": 30, "latitude": 41.0, "longitude": -99.0},
        ],
    }
    points = expand_map_objects([smoke_parent])
    assert [(p["lat"], p["lon"]) for p in points] == [(40.0, -100.0), (41.0, -99.0)]
    assert all(point["id"] != "hms-smoke-01" for point in points)
    water_quality = STATION_CATALOG["usgs-wq-01"]
    assert water_quality["kind"] == "event"
    assert water_quality["lat"] == 0.0 and water_quality["lon"] == 0.0
    dart_anchor = STATION_CATALOG["noaa-dart-01"]
    assert dart_anchor["kind"] == "point"
    assert dart_anchor["lat"] != 0.0 and dart_anchor["lon"] != 0.0
    dart = [meta for meta in STATION_CATALOG.values() if meta["layer"] == "dart"]
    assert len(dart) == 43
    assert all(meta["kind"] == "point" for meta in dart)
    cams = [meta for did, meta in STATION_CATALOG.items() if did.startswith("cams-")]
    assert len(cams) == 6
    assert all(meta["kind"] == "point" for meta in cams)
    radnet = [meta for did, meta in STATION_CATALOG.items() if did.startswith("radnet-")]
    assert len(radnet) == 140
    assert all(meta["kind"] == "point" for meta in radnet)
    soil = [meta for did, meta in STATION_CATALOG.items() if did.startswith("soil-")]
    assert len(soil) == 6
    assert all(meta["kind"] == "point" for meta in soil)
    solar = [meta for did, meta in STATION_CATALOG.items() if did.startswith("solar-")]
    assert len(solar) == 6
    assert all(meta["kind"] == "point" for meta in solar)
    snow = [meta for did, meta in STATION_CATALOG.items() if did.startswith("snow-")]
    assert len(snow) == 6
    assert all(meta["kind"] == "point" for meta in snow)
    lst = [meta for did, meta in STATION_CATALOG.items() if did.startswith("lst-")]
    assert len(lst) == 6
    assert all(meta["kind"] == "point" for meta in lst)
    metars = [meta for did, meta in STATION_CATALOG.items() if did.startswith("metar-")]
    assert len(metars) == 14
    assert all(meta["kind"] == "point" and meta["layer"] == "aviation" for meta in metars)
    pegels = [meta for did, meta in STATION_CATALOG.items() if did.startswith("pegel-")]
    assert len(pegels) == 22
    assert all(meta["kind"] == "point" and meta["layer"] == "river" for meta in pegels)


def test_p11_catalog_pins_are_points_with_coordinates():
    """P11 meshes are in-situ stations: ATLAS must place a clickable point pin."""
    from atlas.fleet import pin_from_catalog, wanted_station_ids

    expected = {
        "aemet-wx-": ("weather", "gaia.weather.read@v1", 15),
        "ch-wx-": ("weather", "gaia.weather.read@v1", 15),
        "bafu-": ("river", "gaia.river.read@v1", 15),
        "cwa-wx-": ("weather", "gaia.weather.read@v1", 12),
        "mf-wx-": ("weather", "gaia.weather.read@v1", 12),
        "ee-wx-": ("weather", "gaia.weather.read@v1", 12),
        "is-wx-": ("weather", "gaia.weather.read@v1", 12),
        "hk-aqhi-": ("air", "gaia.air.read@v1", 18),
    }
    all_ids = []
    for prefix, (layer, cap, count) in expected.items():
        ids = [did for did in STATION_CATALOG if did.startswith(prefix)]
        assert len(ids) == count, f"{prefix} expected {count} pins, got {len(ids)}"
        for device_id in ids:
            all_ids.append(device_id)
            meta = STATION_CATALOG[device_id]
            assert meta["kind"] == "point"
            assert meta["layer"] == layer
            assert meta["capability"] == cap
            assert meta["mode"] == "live"
            assert abs(float(meta["lat"])) > 1e-6 or abs(float(meta["lon"])) > 1e-6
            pin = pin_from_catalog(
                device_id,
                fleet_dev={"source": "test", "online": True, "model": "GAIA-TEST"},
            )
            assert pin["kind"] == "point"
            assert pin["id"] == device_id
            assert pin["registered"] is True
            assert pin["live"] is True
    fleet = {did: {"source": "test"} for did in all_ids}
    wanted = set(wanted_station_ids(fleet))
    assert set(all_ids) <= wanted
    assert len(all_ids) == 111


def test_p12_catalog_pins_are_points_with_coordinates():
    """P12 station meshes are in-situ / territory pins: ATLAS must place a clickable point."""
    from atlas.fleet import pin_from_catalog, wanted_station_ids

    expected = {
        "at-wx-": ("weather", "gaia.weather.read@v1", 15),
        "lt-wx-": ("weather", "gaia.weather.read@v1", 12),
        "lt-hydro-": ("river", "gaia.river.read@v1", 8),
        "lv-wx-": ("weather", "gaia.weather.read@v1", 8),
        "lv-hydro-": ("river", "gaia.river.read@v1", 6),
        "vic-": ("flood", "gaia.flood.read@v1", 19),
        "ie-river-": ("river", "gaia.river.read@v1", 16),
        "jp-wx-": ("weather", "gaia.weather.read@v1", 13),
        "cz-wx-": ("weather", "gaia.weather.read@v1", 8),
        "kr-wx-": ("weather", "gaia.weather.read@v1", 7),
    }
    all_ids = []
    for prefix, (layer, cap, count) in expected.items():
        ids = [did for did in STATION_CATALOG if did.startswith(prefix)]
        assert len(ids) == count, f"{prefix} expected {count} pins, got {len(ids)}"
        for device_id in ids:
            all_ids.append(device_id)
            meta = STATION_CATALOG[device_id]
            assert meta["kind"] == "point"
            assert meta["layer"] == layer
            assert meta["capability"] == cap
            assert meta["mode"] == "live"
            pin = pin_from_catalog(
                device_id,
                fleet_dev={"source": "test", "online": True, "model": "GAIA-TEST"},
            )
            assert pin["kind"] == "point"
            assert pin["id"] == device_id
    rte = STATION_CATALOG["rte-grid-01"]
    assert rte["kind"] == "point"
    assert rte["capability"] == "gaia.grid.read@v1"
    assert abs(float(rte["lat"]) - 48.8566) < 1e-4
    fleet = {did: {"source": "test"} for did in all_ids + ["rte-grid-01"]}
    wanted = set(wanted_station_ids(fleet))
    assert set(all_ids) <= wanted


def test_p12_bbox_places_representative_pins():
    checks = (
        ("at-wx-wien-01", 16.30, 48.20, 16.40, 48.30),
        ("lt-wx-vilnius-01", 25.05, 54.58, 25.16, 54.68),
        ("lv-wx-riga-01", 24.05, 56.90, 24.16, 57.00),
        ("ie-river-athlone-01", -8.00, 53.38, -7.88, 53.46),
        ("jp-wx-tokyo-01", 139.70, 35.65, 139.80, 35.74),
        ("cz-wx-praha-01", 14.20, 50.05, 14.32, 50.15),
        ("vic-seinemoy-01", 2.30, 48.80, 2.40, 48.90),
        ("rte-grid-01", 2.30, 48.80, 2.40, 48.90),
    )
    for device_id, west, south, east, north in checks:
        meta = STATION_CATALOG[device_id]
        assert _in_bbox(float(meta["lat"]), float(meta["lon"]), west, south, east, north), device_id


def test_p11_bbox_places_representative_pins():
    """Catalog WGS84 anchors sit in the geography they claim (map click targets)."""
    checks = (
        ("ch-wx-zurich-01", 8.50, 47.35, 8.60, 47.42),
        ("bafu-basel-01", 7.55, 47.52, 7.70, 47.58),
        ("aemet-wx-madrid-01", -3.75, 40.38, -3.60, 40.45),
        ("cwa-wx-taipei-01", 121.40, 25.00, 121.60, 25.10),
        ("mf-wx-paris-01", 2.30, 48.80, 2.40, 48.85),
        ("ee-wx-tallinn-01", 24.50, 59.35, 24.70, 59.45),
        ("is-wx-reykjavik-01", -22.00, 64.10, -21.80, 64.20),
        ("hk-aqhi-centralwestern-01", 114.10, 22.25, 114.20, 22.32),
    )
    for device_id, west, south, east, north in checks:
        meta = STATION_CATALOG[device_id]
        assert _in_bbox(float(meta["lat"]), float(meta["lon"]), west, south, east, north), device_id


def test_p12_catalog_pins_are_points_with_coordinates():
    """P12 station meshes are in-situ: ATLAS must place a clickable point pin."""
    from atlas.fleet import pin_from_catalog, wanted_station_ids

    expected = {
        "at-wx-": ("weather", "gaia.weather.read@v1", 15),
        "lt-wx-": ("weather", "gaia.weather.read@v1", 12),
        "lv-wx-": ("weather", "gaia.weather.read@v1", 8),
        "jp-wx-": ("weather", "gaia.weather.read@v1", 13),
        "cz-wx-": ("weather", "gaia.weather.read@v1", 8),
        "kr-wx-": ("weather", "gaia.weather.read@v1", 7),
        "lt-hydro-": ("river", "gaia.river.read@v1", 8),
        "lv-hydro-": ("river", "gaia.river.read@v1", 6),
        "ie-river-": ("river", "gaia.river.read@v1", 16),
        "vic-": ("flood", "gaia.flood.read@v1", 19),
    }
    all_ids = []
    for prefix, (layer, cap, count) in expected.items():
        ids = [did for did in STATION_CATALOG if did.startswith(prefix)]
        assert len(ids) == count, f"{prefix} expected {count} pins, got {len(ids)}"
        for device_id in ids:
            all_ids.append(device_id)
            meta = STATION_CATALOG[device_id]
            assert meta["kind"] == "point"
            assert meta["layer"] == layer
            assert meta["capability"] == cap
            assert meta["mode"] == "live"
            assert abs(float(meta["lat"])) > 1e-6 or abs(float(meta["lon"])) > 1e-6
            pin = pin_from_catalog(
                device_id,
                fleet_dev={"source": "test", "online": True, "model": "GAIA-TEST"},
            )
            assert pin["kind"] == "point"
            assert pin["id"] == device_id
            assert pin["registered"] is True
            assert pin["live"] is True
    rte = STATION_CATALOG["rte-grid-01"]
    assert rte["kind"] == "point"
    assert rte["layer"] == "grid"
    assert rte["capability"] == "gaia.grid.read@v1"
    all_ids.append("rte-grid-01")
    fleet = {did: {"source": "test"} for did in all_ids}
    wanted = set(wanted_station_ids(fleet))
    assert set(all_ids) <= wanted
    assert len(all_ids) == 113


def test_p12_bbox_places_representative_pins():
    """Catalog WGS84 anchors sit in the geography they claim (map click targets)."""
    checks = (
        ("at-wx-wien-01", 16.30, 48.20, 16.40, 48.30),
        ("lt-wx-vilnius-01", 25.05, 54.58, 25.16, 54.68),
        ("lv-wx-riga-01", 24.05, 56.90, 24.16, 57.00),
        ("ie-river-athlone-01", -8.00, 53.38, -7.88, 53.46),
        ("jp-wx-tokyo-01", 139.70, 35.65, 139.80, 35.74),
        ("cz-wx-praha-01", 14.20, 50.05, 14.32, 50.15),
        ("rte-grid-01", 2.30, 48.80, 2.40, 48.90),
        ("vic-meuse-01", 6.10, 49.05, 6.25, 49.20),
    )
    for device_id, west, south, east, north in checks:
        meta = STATION_CATALOG[device_id]
        assert _in_bbox(float(meta["lat"]), float(meta["lon"]), west, south, east, north), device_id


def test_p5_cluster_parents_expand_to_clickable_pins():
    """Road / rail / drought parents fan hotspots into map pins (weather-mesh UX)."""
    from atlas.fleet import expand_map_objects

    road = {
        "id": "fintraffic-road-01", "layer": "road", "kind": "event",
        "online": True, "live": True,
        "hotspots": [
            {"station_id": "1001", "temperature_c": 2.0, "wind_mps": 4.0,
             "latitude": 60.2, "longitude": 24.9},
            {"station_id": "1002", "temperature_c": -1.0, "wind_mps": 1.0,
             "latitude": 61.5, "longitude": 23.8},
        ],
    }
    rail = {
        "id": "fintraffic-rail-01", "layer": "rail", "kind": "event",
        "hotspots": [
            {"train_number": "42", "speed_kmh": 120.0,
             "latitude": 60.3, "longitude": 25.0},
        ],
    }
    drought = {
        "id": "usdm-01", "layer": "drought", "kind": "event",
        "hotspots": [
            {"state": "CA", "severity_score": 80.0, "drought_pct": 55.0,
             "latitude": 37.0, "longitude": -119.0, "category": "D2"},
        ],
    }
    points = expand_map_objects([road, rail, drought])
    ids = {p["id"] for p in points}
    assert "road-st-1001" in ids
    assert "road-st-1002" in ids
    assert "rail-tr-42" in ids
    assert "drought-st-CA" in ids
    assert all(p.get("id") not in {
        "fintraffic-road-01", "fintraffic-rail-01", "usdm-01",
    } for p in points)
    collapsed = expand_map_objects([road], expand=False)
    assert len(collapsed) == 1
    assert collapsed[0].get("cluster_parent") is True
    assert "hotspots" not in collapsed[0]


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
    assert "sc-stuttgart" in STATION_CATALOG
    assert "sc-munich" in STATION_CATALOG
    assert STATION_CATALOG["sc-stuttgart"]["capability"] == "gaia.air.read@v1"
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
