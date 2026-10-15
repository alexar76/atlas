"""Aggregator: fleet pins, TTL cache, viewport, detail."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from atlas.aggregator import Aggregator


@pytest.mark.asyncio
async def test_fleet_snapshot_has_pins(aggregator: Aggregator):
    snap = aggregator.snapshot()
    assert snap["status"] == "ok"
    assert snap["summary"]["stations"] >= 7
    assert snap["summary"]["live"] >= 1
    assert snap["summary"]["sim"] >= 1
    assert snap["summary"]["layer_counts"]
    assert snap["summary"]["layer_counts"]["weather"]["count_kind"] == "stations"
    assert snap.get("public_url")
    ids = {s["id"] for s in snap["stations"]}
    assert "om-wx-01" in ids
    assert "usgs-quake-01" in ids
    assert "ws-01" in ids
    by_id = {s["id"]: s for s in snap["stations"]}
    assert by_id["om-wx-01"]["live"] is True
    assert by_id["om-wx-01"]["mode"] == "live"
    assert by_id["ws-01"]["live"] is False
    assert by_id["ws-01"]["mode"] == "sim"
    assert by_id["ws-01"]["source"] is None


@pytest.mark.asyncio
async def test_registered_station_is_not_online_until_a_reading(settings):
    agg = Aggregator(settings)
    agg._fleet_by_id = {
        "usgs-geomag-brw": {
            "device_id": "usgs-geomag-brw",
            "online": True,
            "source": "https://geomag.usgs.gov/ws/data/",
        }
    }
    waiting = agg._pin_from_catalog("usgs-geomag-brw")
    assert waiting["registered"] is True
    assert waiting["online"] is False
    assert waiting["has_reading"] is False

    agg._store.put(
        "usgs-geomag-brw",
        {
            "id": "usgs-geomag-brw",
            "layer": "geomag",
            "online": True,
            "values": {"field_nt": 57117.4},
        },
    )
    live = agg._pin_from_catalog("usgs-geomag-brw")
    assert live["online"] is True
    assert live["has_reading"] is True

@pytest.mark.asyncio
async def test_viewport_berlin_fetches_readings(aggregator: Aggregator):
    result = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7, force=False
    )
    assert result["ok"] is True
    assert "om-wx-01" in result["requested"]
    by_id = {s["id"]: s for s in result["stations"]}
    assert by_id["om-wx-01"]["values"]["temperature_c"] == 21.5
    assert by_id["om-wx-01"]["has_reading"] is True
    assert "prefetch" in result
    # Background warm should eventually fill more of the catalog.
    if aggregator._warm_task:
        await aggregator._warm_task
    snap = aggregator.snapshot()
    assert snap["summary"]["cached_readings"] >= 1


@pytest.mark.asyncio
async def test_ensure_all_readings_warms_catalog(aggregator: Aggregator):
    stations = await aggregator.ensure_all_readings(force=False)
    assert len(stations) >= 7
    snap = aggregator.snapshot()
    assert snap["summary"]["cached_readings"] >= 7


@pytest.mark.asyncio
async def test_viewport_second_call_is_cache_hit(aggregator: Aggregator):
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    if aggregator._warm_task:
        await aggregator._warm_task
    second = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7
    )
    assert second["cache_hits"] >= 1
    # FIRMS is force-densified per viewport by design, so it is never a cache hit.
    cacheable = [i for i in second["requested"] if i != "firms-fire-01"]
    assert second["cache_hits"] == len(cacheable)


@pytest.mark.asyncio
async def test_viewport_force_bypasses_cache(aggregator: Aggregator):
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    forced = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7, force=True
    )
    assert forced["cache_hits"] == 0


@pytest.mark.asyncio
async def test_water_quality_cache_is_scoped_by_viewport_bbox(aggregator: Aggregator):
    calls: list[dict[str, Any]] = []
    original = aggregator._invoke

    async def tracking_invoke(
        capability_id: str,
        device_id: str | None = None,
        extra_input: dict[str, Any] | None = None,
    ):
        if capability_id == "gaia.water_quality.read@v1":
            calls.append(dict(extra_input or {}))
        return await original(capability_id, device_id, extra_input=extra_input)

    aggregator._invoke = tracking_invoke  # type: ignore[method-assign]
    first = await aggregator.refresh_viewport(
        west=12.5, south=52.3, east=14.0, north=52.7
    )
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    second_bbox = await aggregator.refresh_viewport(
        west=2.1, south=48.7, east=2.5, north=49.0
    )

    assert len(calls) == 2
    assert calls[0]["west"] == 12.5
    assert calls[1]["west"] == 2.1
    first_points = [p for p in first["map_points"] if p.get("layer") == "water_quality"]
    second_points = [
        p for p in second_bbox["map_points"] if p.get("layer") == "water_quality"
    ]
    assert len(first_points) == len(second_points) == 1
    assert first_points[0]["id"] != second_points[0]["id"]
    assert first_points[0]["observation_uptime_pct"] == 100.0
    assert first_points[0]["approval_status"] == "Provisional"
    assert first_points[0]["observation_metadata"]["water_temperature_c"]["qualifier"] == "Ice"
    detail = await aggregator.station_detail(first_points[0]["id"])
    assert detail["history_count"] == 1
    assert detail["history"][0]["approval_status"] == "Provisional"


@pytest.mark.asyncio
async def test_station_detail_human_readable(aggregator: Aggregator):
    detail = await aggregator.station_detail("om-wx-01")
    assert detail["id"] == "om-wx-01"
    assert "Berlin" in (detail.get("summary") or "")
    assert detail["metrics"]
    assert any(m["label"] == "Temperature" for m in detail["metrics"])


@pytest.mark.asyncio
async def test_station_detail_unknown(aggregator: Aggregator):
    with pytest.raises(KeyError):
        await aggregator.station_detail("no-such-device")


@pytest.mark.asyncio
async def test_quake_updates_coords_and_trail(aggregator: Aggregator):
    await aggregator._ensure_readings(["usgs-quake-01"], force=True)
    station = aggregator._readings["usgs-quake-01"]["station"]
    assert abs(station["lat"] - 35.1) < 0.01
    assert abs(station["lon"] - (-118.2)) < 0.01
    assert aggregator._quake_trail
    assert aggregator._quake_trail[-1]["magnitude"] == 4.8


@pytest.mark.asyncio
async def test_single_flight_concurrent_reads(aggregator: Aggregator):
    # Clear cache so both waiters share one fetch (force=False + TTL).
    aggregator._readings.pop("nws-01", None)
    calls = {"n": 0}
    real_fetch = aggregator._fetch_station_reading

    async def counting_fetch(device_id: str):
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return await real_fetch(device_id)

    aggregator._fetch_station_reading = counting_fetch  # type: ignore[method-assign]
    a, b = await asyncio.gather(
        aggregator._ensure_readings(["nws-01"], force=False),
        aggregator._ensure_readings(["nws-01"], force=False),
    )
    assert a and b
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_background_warm_uses_interactive_sized_batches(aggregator: Aggregator):
    ids = list(aggregator._fleet_by_id)[:9]
    aggregator._readings = {}
    batches: list[list[str]] = []

    async def record_batch(device_ids: list[str], *, force: bool = False, ttl=None):
        batches.append(list(device_ids))
        return []

    async def no_publish():
        return None

    aggregator._ensure_readings = record_batch  # type: ignore[method-assign]
    aggregator._publish = no_publish  # type: ignore[method-assign]
    aggregator._kick_warm(ids)
    assert aggregator._warm_task is not None
    await aggregator._warm_task

    assert [len(batch) for batch in batches] == [4, 4, 1]


@pytest.mark.asyncio
async def test_monitor_payload_shape(aggregator: Aggregator):
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    payload = aggregator.monitor_payload()
    assert payload["service"] == "atlas"
    assert payload["embed_url"].endswith("/embed")
    assert payload["station_count"] >= 1
    assert isinstance(payload["stations"], list)


@pytest.mark.asyncio
async def test_health_ok(aggregator: Aggregator):
    h = aggregator.health()
    assert h["ok"] is True
    assert h["service"] == "atlas"
    assert h["stations"] >= 1


def test_product_stations_fans_effis_cluster(aggregator: Aggregator):
    aggregator._store.put(
        "effis-01",
        {
            "id": "effis-01",
            "layer": "effis",
            "live": True,
            "mode": "live",
            "lat": 41.4,
            "lon": 2.1,
            "has_reading": True,
            "values": {"severity_score": 80.0, "latitude": 41.4, "longitude": 2.1},
            "hotspots": [
                {
                    "severity_score": 80.0,
                    "latitude": 41.4,
                    "longitude": 2.1,
                    "area_ha": 1200.0,
                },
                {
                    "severity_score": 50.0,
                    "latitude": 40.0,
                    "longitude": 0.5,
                    "area_ha": 400.0,
                },
            ],
        },
    )
    pins = aggregator.product_stations()
    ids = [str(p.get("id") or "") for p in pins if p.get("layer") == "effis"]
    assert "effis-01" not in ids
    hs = [i for i in ids if i.startswith("effis-hs-")]
    assert len(hs) == 2


def test_product_stations_fans_flood_cluster(aggregator: Aggregator):
    aggregator._store.put(
        "nws-flood-01",
        {
            "id": "nws-flood-01",
            "layer": "flood",
            "live": True,
            "mode": "live",
            "lat": 34.05,
            "lon": -118.25,
            "has_reading": True,
            "values": {"severity_score": 2.0, "latitude": 34.05, "longitude": -118.25},
            "hotspots": [
                {
                    "severity_score": 3.0,
                    "latitude": 34.05,
                    "longitude": -118.25,
                    "site": "LA",
                },
                {
                    "severity_score": 2.0,
                    "latitude": 33.9,
                    "longitude": -118.4,
                    "site": "SBA",
                },
            ],
        },
    )
    pins = aggregator.product_stations()
    ids = [str(p.get("id") or "") for p in pins if p.get("layer") == "flood"]
    assert "nws-flood-01" not in ids
    assert len([i for i in ids if i.startswith("flood-hs-")]) == 2


def test_product_stations_fans_lightning_volcano_alerts(aggregator: Aggregator):
    aggregator._store.put(
        "glm-01",
        {
            "id": "glm-01",
            "layer": "lightning",
            "live": True,
            "mode": "live",
            "lat": 25.0,
            "lon": -80.0,
            "has_reading": True,
            "values": {"energy_fj": 12.5, "latitude": 25.0, "longitude": -80.0},
            "hotspots": [
                {"energy_fj": 12.5, "latitude": 25.0, "longitude": -80.0},
                {"energy_fj": 8.0, "latitude": 25.1, "longitude": -80.1},
            ],
        },
    )
    aggregator._store.put(
        "usgs-volcano-01",
        {
            "id": "usgs-volcano-01",
            "layer": "volcano",
            "live": True,
            "mode": "live",
            "lat": 19.4,
            "lon": -155.2,
            "has_reading": True,
            "values": {"severity_score": 80.0, "latitude": 19.4, "longitude": -155.2},
            "hotspots": [
                {"severity_score": 80.0, "latitude": 19.4, "longitude": -155.2, "name": "Kilauea"},
            ],
        },
    )
    aggregator._store.put(
        "nws-alerts-01",
        {
            "id": "nws-alerts-01",
            "layer": "alerts",
            "live": True,
            "mode": "live",
            "lat": 35.5,
            "lon": -97.5,
            "has_reading": True,
            "values": {"severity_score": 95.0, "latitude": 35.5, "longitude": -97.5},
            "hotspots": [
                {"severity_score": 95.0, "latitude": 35.5, "longitude": -97.5, "event": "Tornado"},
            ],
        },
    )
    pins = aggregator.product_stations()
    lightning = [p for p in pins if p.get("layer") == "lightning"]
    volcano = [p for p in pins if p.get("layer") == "volcano"]
    alerts = [p for p in pins if p.get("layer") == "alerts"]
    assert "glm-01" not in {p.get("id") for p in lightning}
    assert len([p for p in lightning if str(p.get("id") or "").startswith("glm-hs-")]) == 2
    assert "usgs-volcano-01" not in {p.get("id") for p in volcano}
    assert len([p for p in volcano if str(p.get("id") or "").startswith("volc-ev-")]) == 1
    assert volcano[0].get("name") == "Kilauea"
    assert "nws-alerts-01" not in {p.get("id") for p in alerts}
    assert len([p for p in alerts if str(p.get("id") or "").startswith("cap-ev-")]) == 1


@pytest.mark.asyncio
async def test_space_weather_grid_points_are_clickable_details(aggregator: Aggregator):
    aggregator._store.put(
        "swpc-01",
        {
            "id": "swpc-01",
            "layer": "spacewx",
            "label": "NOAA SWPC Space Weather",
            "place": "OVATION aurora grid",
            "live": True,
            "mode": "live",
            "online": True,
            "lat": 67.2,
            "lon": 25.1,
            "has_reading": True,
            "values": {"kp_index": 5.0, "aurora_pct": 72.0, "latitude": 67.2, "longitude": 25.1},
            "hotspot_matched": 2,
            "hotspots": [
                {"kp_index": 5.0, "aurora_pct": 72.0, "latitude": 67.2, "longitude": 25.1},
                {"kp_index": 5.0, "aurora_pct": 18.0, "latitude": 54.5, "longitude": -3.0},
            ],
        },
    )
    # Count the CELLS, not the layer. The property under test is that the grid parent
    # is REPLACED by its cells rather than shown beside them; counting everything on
    # spacewx also swept in the layer's ordinary single-instrument stations (SWPC solar
    # wind, GOES X-ray, NASA DONKI), which is how this assertion came to encode a bug —
    # those three were being dropped as "cluster parents" with nothing to replace them,
    # and the number 2 quietly depended on their absence.
    pins = [p for p in aggregator.product_stations() if p.get("parent_id") == "swpc-01"]
    assert len(pins) == 2
    on_layer = {p.get("id") for p in aggregator.product_stations() if p.get("layer") == "spacewx"}
    assert "swpc-01" not in on_layer          # replaced by its cells
    assert {"swpc-solarwind-01", "swpc-xray-01"} <= on_layer   # and they are not cells
    point_id = "swpc-hs-sw01-672000_251000"
    detail = await aggregator.station_detail(point_id)
    assert detail["id"] == point_id
    assert detail["lat"] == 67.2
    assert any(row["label"] == "Aurora" and row["value"] == "72 %" for row in detail["metrics"])


@pytest.mark.asyncio
async def test_recent_visible_event_point_remains_exactly_addressable(aggregator: Aggregator):
    point_id = "glm-hs-glm01-250000_-800000"
    aggregator._remember_map_points(
        [
            {
                "id": point_id,
                "parent_id": "glm-01",
                "layer": "lightning",
                "kind": "event",
                "lat": 25.0,
                "lon": -80.0,
                "live": True,
                "mode": "live",
                "online": True,
                "source": "https://www.noaa.gov/nodd",
                "values": {"energy_fj": 12.5, "latitude": 25.0, "longitude": -80.0},
                "headline": "GLM 12 fJ",
                "has_reading": True,
            }
        ]
    )
    # The parent cluster may roll after the browser received this point; the
    # registry keeps the exact exposed evidence addressable for the UI window.
    aggregator._store.entries.pop("glm-01", None)
    detail = await aggregator.station_detail(point_id)
    assert detail["id"] == point_id
    assert detail["values"]["energy_fj"] == 12.5


@pytest.mark.asyncio
async def test_quake_trail_point_opens_exact_event_not_latest_parent(aggregator: Aggregator):
    aggregator._quake_trail = [
        {
            "id": "q-1-4.2",
            "parent_id": "usgs-quake-01",
            "lat": 34.2,
            "lon": -118.1,
            "magnitude": 4.2,
            "depth_km": 7.5,
            "at": "2026-08-13T10:00:00Z",
            "place": "Historic event",
            "source": "https://earthquake.usgs.gov",
        }
    ]
    detail = await aggregator.station_detail("q-1-4.2")
    assert detail["id"] == "q-1-4.2"
    assert detail["values"]["magnitude"] == 4.2
    assert detail["lat"] == 34.2


@pytest.mark.asyncio
async def test_argo_point_click_invokes_that_wmo_and_exposes_profile(aggregator: Aggregator):
    profile_url = (
        "https://data-argo.ifremer.fr/dac/coriolis/6901234/"
        "profiles/R6901234_007.nc"
    )
    aggregator._store.put(
        "argo-01",
        {
            "id": "argo-01",
            "layer": "argo",
            "label": "Global Argo Active Float Network",
            "place": "Official GDAC",
            "live": True,
            "mode": "live",
            "online": True,
            "has_reading": True,
            "values": {"latitude": -42.0, "longitude": 80.0},
            "hotspots": [
                {
                    "wmo": "6901234",
                    "latitude": -42.0,
                    "longitude": 80.0,
                    "observed_at": "2026-08-12T00:00:00Z",
                    "profile_url": profile_url,
                    "source_url": profile_url,
                }
            ],
        },
    )
    calls = []

    async def invoke(capability_id, device_id=None, *, extra_input=None):
        calls.append((capability_id, device_id, extra_input))
        return {
            "reading": {
                "wmo": "6901234",
                "observed_at": "2026-08-12T00:00:00Z",
                "profile_url": profile_url,
                "source_url": "https://erddap.ifremer.fr/erddap/tabledap/ArgoFloats.json",
                "values": {
                    "temperature_c": 4.6,
                    "salinity_psu": 34.7,
                    "pressure_dbar": 3.0,
                    "latitude": -42.0,
                    "longitude": 80.0,
                },
            }
        }

    aggregator._invoke = invoke  # type: ignore[method-assign]
    detail = await aggregator.station_detail("argo-wmo-6901234")
    assert calls == [("gaia.argo.read@v1", "argo-01", {"wmo": "6901234"})]
    assert detail["title"] == "Argo WMO 6901234"
    assert detail["profile_url"] == profile_url
    assert detail["invoke"]["input"]["wmo"] == "6901234"
    assert any(row["label"] == "Temperature" for row in detail["metrics"])


@pytest.mark.asyncio
async def test_a_station_is_never_dropped_with_nothing_to_replace_it(aggregator: Aggregator):
    """The whole weather layer used to disappear from products and from the map.

    `fleet.pin_from_catalog` marks `cluster_parent` for every station whose LAYER is in
    DENSE_EVENT_LAYERS — a property of the layer, not of the station — and both the
    product list and the viewport dropped on that flag. So an ordinary single-point
    station on a dense layer was removed as a "parent" that had no children to stand in
    for it: 98 stations across 27 layers, all 47 weather stations among them, absent
    from every composite SKU, from the Analyst's grounding context, and from the map
    (a Berlin viewport returned air, soil and solar pins and no weather at all).

    So the invariant, stated where it can be checked: a station leaves the list only
    when something in the list names it as parent.
    """
    await aggregator.refresh_viewport(west=12.5, south=52.3, east=14.0, north=52.7)
    stations = aggregator.snapshot().get("stations") or []
    products = aggregator.product_stations()
    kept = {str(s.get("id")) for s in products}
    stood_in_for = {str(p.get("parent_id")) for p in products if p.get("parent_id")}

    for station in stations:
        sid = str(station.get("id") or "")
        if sid in kept or sid in stood_in_for:
            continue
        # The only remaining reason to drop one is a fan-out held in the reading store.
        assert isinstance((aggregator._store.get_station(sid) or {}).get("hotspots"), list), (
            f"{sid} ({station.get('layer')}) vanished: no pin replaced it and it has no cluster"
        )

    assert "om-wx-01" in kept, "the weather layer is the one this was found on"


@pytest.mark.asyncio
async def test_world_viewport_exposes_all_401_space_weather_cells(aggregator: Aggregator):
    # Mirror NOAA OVATION's 0..360 longitude convention. The second latitude
    # row keeps all 401 source coordinates unique.
    hotspots = [
        {
            "kp_index": 4.0,
            "aurora_pct": float(5 + (i % 90)),
            "latitude": float(-80 + (i // 360)),
            "longitude": float(i % 360),
        }
        for i in range(401)
    ]
    aggregator._store.put(
        "swpc-01",
        {
            "id": "swpc-01",
            "layer": "spacewx",
            "label": "NOAA SWPC Space Weather",
            "place": "OVATION aurora grid",
            "live": True,
            "mode": "live",
            "online": True,
            "lat": 40.015,
            "lon": -105.27,
            "has_reading": True,
            "values": {"kp_index": 4.0, "aurora_pct": 94.0},
            "hotspots": hotspots,
            "hotspot_count": len(hotspots),
        },
    )

    viewport = await aggregator.refresh_viewport(
        west=-180.0,
        south=-90.0,
        east=180.0,
        north=90.0,
    )
    # By parent, not by layer — see the note in the clickable-details test above.
    points = [p for p in viewport["map_points"] if p.get("parent_id") == "swpc-01"]
    assert len(points) == 401
    assert len({p["id"] for p in points}) == 401
    assert all(-180.0 <= p["lon"] <= 180.0 for p in points)
    assert viewport["snapshot"]["summary"]["layer_counts"]["spacewx"]["count"] == 401


@pytest.mark.asyncio
async def test_wide_viewport_uses_stratified_fire_densify(aggregator: Aggregator):
    captured: list[dict[str, Any]] = []
    orig_invoke = aggregator._invoke

    async def tracking_invoke(
        capability_id: str,
        device_id: str | None = None,
        extra_input: dict[str, Any] | None = None,
    ):
        if device_id == "firms-fire-01" and extra_input:
            captured.append(dict(extra_input))
            return {
                "reading": {
                    "values": {
                        "brightness_k": 400.0,
                        "latitude": 30.0,
                        "longitude": 10.0,
                    },
                    "hotspots": [
                        {
                            "brightness_k": 400.0,
                            "confidence": 90.0,
                            "latitude": 30.0,
                            "longitude": 10.0,
                        }
                    ],
                    "hotspot_matched": 1200,
                    "hotspot_count": 1,
                    "hotspot_total": 1,
                }
            }
        return await orig_invoke(capability_id, device_id, extra_input=extra_input)

    aggregator._invoke = tracking_invoke  # type: ignore[method-assign]
    viewport = await aggregator.refresh_viewport(
        west=-25.0,
        south=-35.0,
        east=55.0,
        north=40.0,
    )
    assert viewport["fire_query"]["stratified"] is True
    assert viewport["fire_query"]["grid_deg"] == 5.0
    assert any(c.get("stratified") for c in captured)

    narrow = await aggregator.refresh_viewport(
        west=12.5,
        south=52.3,
        east=14.0,
        north=52.7,
    )
    assert narrow["fire_query"]["stratified"] is False
