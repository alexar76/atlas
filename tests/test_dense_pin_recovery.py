"""A pin the client still shows must never answer "unknown station".

Event feeds roll (FIRMS re-drains daily, alerts expire, vessels leave the
receiver), the served-point index is memory-only and dies with the worker, and a
browser keeps its pins for a whole session. The pin id carries its layer and
coordinate, so the detail endpoint can always answer.
"""

from __future__ import annotations

import pytest

from atlas import fleet
from atlas.aggregator import Aggregator
from atlas.config import Settings


def _pin(lat: float, lon: float, *, brightness: float = 330.0) -> dict:
    return {"latitude": lat, "longitude": lon, "brightness_k": brightness, "confidence": "high"}


def _fire_parent(rows: list[dict]) -> dict:
    return {
        "id": "firms-fire-01",
        "layer": "fire",
        "kind": "event",
        "online": True,
        "live": True,
        "mode": "live",
        "source": "NASA FIRMS",
        "label": "FIRMS active fire",
        "hotspots": rows,
    }


@pytest.fixture()
def agg() -> Aggregator:
    return Aggregator(Settings(gaia_url="http://127.0.0.1:1", operator_token="t"))


def _seed(agg: Aggregator, parent: dict) -> None:
    agg._store.entries[str(parent["id"])] = {"station": parent, "at": 0.0}


class TestPinIdDecoding:
    @pytest.mark.parametrize(
        "pin_id,layer,lat,lon",
        [
            ("firms-hs-ff01-503515_571307", "fire", 50.3515, 57.1307),
            # A southern/western pin doubles the dash — the old parser's blind spot.
            ("firms-hs-ff01--16755_1139720", "fire", -1.6755, 113.9720),
            ("rad-hs-sc01-374932_1399331", "radiation", 37.4932, 139.9331),
            ("glm-hs-gl01-34667_-1281766", "lightning", 3.4667, -128.1766),
            ("smoke-poly-hms-smoke-01-635240_-1171011", "smoke", 63.5240, -117.1011),
            # Deduplicated pins carry a trailing index.
            ("cap-ev-na01-274564_-802018-7", "alerts", 27.4564, -80.2018),
        ],
    )
    def test_coordinate_pins_decode_to_layer_and_position(self, pin_id, layer, lat, lon):
        out = fleet.dense_pin_from_id(pin_id)
        assert out is not None, pin_id
        assert out["layer"] == layer
        assert out["lat"] == pytest.approx(lat)
        assert out["lon"] == pytest.approx(lon)

    @pytest.mark.parametrize(
        "pin_id",
        [
            "adsb-ac-4caa5c",          # stable id: aircraft hex
            "gnss-station:euref:AAER00FRA",
            "usgs-wq-site-01011000",
            "om-wx-01",
            "firms-hs-ff01-9990000_0",  # 999° is not a latitude
            "",
        ],
    )
    def test_non_coordinate_ids_decode_to_nothing(self, pin_id):
        assert fleet.dense_pin_from_id(pin_id) is None

    def test_every_cluster_layer_prefix_is_decodable(self):
        # Adding a layer to CLUSTER_META must not silently opt out of recovery.
        for layer, meta in fleet.CLUSTER_META.items():
            if meta.get("stable_id") and layer in {"gnss", "argo", "water_quality", "radar"}:
                continue  # keyed by station identity, not by coordinate
            pin_id = f"{meta['prefix']}-tag01-100000_200000"
            out = fleet.dense_pin_from_id(pin_id)
            assert out is not None and out["layer"] == layer, layer


class TestRecovery:
    @pytest.mark.asyncio
    async def test_a_redrained_detection_is_matched_by_position(self, agg):
        # The feed now keys the same fire a few metres away.
        _seed(agg, _fire_parent([_pin(50.3516, 57.1309)]))
        detail = await agg.station_detail("firms-hs-ff01-503515_571307")
        assert detail["id"] == "firms-hs-ff01-503515_571307"
        assert detail["matched_by"] == "position"
        assert "matched by position" in detail["status_line"]
        assert detail["layer"] == "fire"
        assert detail["values"]["brightness_k"] == 330.0

    @pytest.mark.asyncio
    async def test_a_cleared_detection_answers_with_its_own_position(self, agg):
        _seed(agg, _fire_parent([_pin(-33.0, 18.0)]))  # nothing near the clicked pin
        detail = await agg.station_detail("firms-hs-ff01-503515_571307")
        assert detail["dropped"] is True
        assert detail["lat"] == pytest.approx(50.3515)
        assert detail["lon"] == pytest.approx(57.1307)
        assert "cleared from the live window" in detail["status_line"]
        assert detail["source"] == "NASA FIRMS"
        assert detail["online"] is False

    @pytest.mark.asyncio
    async def test_a_far_away_detection_is_not_passed_off_as_the_clicked_one(self, agg):
        # 0.5° away is ~55 km: a different fire, so no match by position.
        _seed(agg, _fire_parent([_pin(50.85, 57.63)]))
        detail = await agg.station_detail("firms-hs-ff01-503515_571307")
        assert detail.get("matched_by") is None
        assert detail["dropped"] is True

    @pytest.mark.asyncio
    async def test_a_stable_id_pin_still_gets_a_card(self, agg):
        detail = await agg.station_detail("adsb-ac-4caa5c")
        assert detail["dropped"] is True
        assert detail["id"] == "adsb-ac-4caa5c"
        assert "cleared from the live window" in detail["status_line"]

    @pytest.mark.asyncio
    async def test_an_unknown_non_pin_id_is_still_a_404(self, agg):
        with pytest.raises(KeyError):
            await agg.station_detail("not-a-station-at-all")

    @pytest.mark.asyncio
    async def test_a_live_pin_is_served_from_the_cluster_untouched(self, agg):
        _seed(agg, _fire_parent([_pin(50.3515, 57.1307, brightness=412.5)]))
        detail = await agg.station_detail("firms-hs-ff01-503515_571307")
        assert detail.get("dropped") is None
        assert detail.get("matched_by") is None
        assert detail["values"]["brightness_k"] == 412.5


class TestDetailBudget:
    """A click answers within a budget — the read keeps going in the background."""

    @pytest.mark.asyncio
    async def test_a_slow_first_read_answers_from_the_catalog_pin(self, agg, monkeypatch):
        import asyncio

        monkeypatch.setattr(agg.settings, "detail_budget_s", 0.05, raising=False)

        async def never(device_id: str):
            await asyncio.sleep(30)
            raise AssertionError("should not be awaited to completion")

        monkeypatch.setattr(agg, "_fetch_station_reading", never)
        detail = await agg.station_detail("om-wx-01")
        assert detail["refreshing"] is True
        assert "first reading still warming" in detail["status_line"]
        assert detail["id"] == "om-wx-01"

    @pytest.mark.asyncio
    async def test_a_slow_refresh_keeps_showing_the_last_good_reading(self, agg, monkeypatch):
        import asyncio

        station = {
            "id": "om-wx-01",
            "layer": "weather",
            "label": "Open-Meteo Weather",
            "online": True,
            "live": True,
            "mode": "live",
            "lat": 52.5,
            "lon": 13.4,
            "values": {"temperature_c": 19.5},
            "has_reading": True,
        }
        agg._store.put("om-wx-01", station)
        monkeypatch.setattr(agg.settings, "detail_budget_s", 0.05, raising=False)
        monkeypatch.setattr(agg.settings, "detail_fresh_s", 0.0, raising=False)  # force a re-read

        async def never(device_id: str):
            await asyncio.sleep(30)
            raise AssertionError("should not be awaited to completion")

        monkeypatch.setattr(agg, "_fetch_station_reading", never)
        detail = await agg.station_detail("om-wx-01")
        # ReadingStore serves the previous value while the read runs on — the
        # card must say it is refreshing rather than present it as fresh.
        assert detail["refreshing"] is True
        assert detail["values"]["temperature_c"] == 19.5
        assert "refreshing" in detail["status_line"]
        assert "fresh reading" not in detail["status_line"]

    @pytest.mark.asyncio
    async def test_operator_fresh_reads_are_not_budgeted(self, agg, monkeypatch):
        seen = {}

        async def ensure(device_ids, *, force=False, ttl=None, deadline_s=None):
            seen["deadline"] = deadline_s
            return [{"id": device_ids[0], "layer": "weather", "values": {}}]

        monkeypatch.setattr(agg, "_ensure_readings", ensure)
        monkeypatch.setattr(agg, "_publish", lambda: _noop())
        await agg.station_detail("om-wx-01", fresh=True)
        assert seen["deadline"] is None
        await agg.station_detail("om-wx-01")
        assert seen["deadline"] == pytest.approx(agg.settings.detail_budget_s)


async def _noop():
    return None
