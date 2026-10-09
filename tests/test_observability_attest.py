"""``atlas.observability.attest@v1`` — was the observation infrastructure up?

The SKU exists because ATLAS could only answer "is this radar healthy now", while the
question a claims adjuster pays for is about a moment in the past. That makes the
archive load-bearing, and it makes one distinction the whole product rests on:

    a recorded degraded status is evidence the radar was impaired;
    a gap in our sampling is evidence of nothing at all.

Every test below exists to stop those two collapsing into each other, because the
collapse is silent and it turns "we did not look" into "nothing was wrong".
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from atlas.products import CAP_BY_ID, invoke_product, observability_attest
from atlas.status_archive import StatusArchive, parse_iso

KTLX = (35.3331, -97.2778)   # Oklahoma City WSR-88D
KFDR = (34.3622, -98.9764)   # Frederick, OK — ~180 km from KTLX
EVENT = (35.22, -97.44)      # the insured coordinate


def _radar(
    station: str,
    lat: float,
    lon: float,
    *,
    status: str = "Operational",
    operability: str = "RDA - On-line",
    latency_s: float = 41.0,
) -> dict[str, Any]:
    return {
        "id": f"nexrad-site-{station}",
        "layer": "radar",
        "live": True,
        "mode": "live",
        "has_reading": True,
        "lat": lat,
        "lon": lon,
        "place": f"{station} WSR-88D",
        "radar_id": station,
        "name": station,
        "status": status,
        "operability": operability,
        "vcp": "212",
        "values": {"radar_latency_s": latency_s, "latitude": lat, "longitude": lon},
        "headline": status,
        "source": "https://api.weather.gov/radar/stations",
    }


def _alert(lat: float, lon: float) -> dict[str, Any]:
    return {
        "id": "nws-alerts-01", "layer": "alerts", "live": True, "mode": "live",
        "has_reading": True, "lat": lat, "lon": lon, "place": "CAP alert",
        "values": {"severity_score": 80.0}, "headline": "Severe Thunderstorm Warning",
        "source": "https://api.weather.gov/alerts/active",
    }


def _wx(lat: float, lon: float) -> dict[str, Any]:
    return {
        "id": "om-wx-test", "layer": "weather", "live": True, "mode": "live",
        "has_reading": True, "lat": lat, "lon": lon, "place": "Test",
        "values": {"temperature_c": 24.0}, "headline": "wx",
        "source": "https://api.open-meteo.com",
    }


@pytest.fixture()
def archive(tmp_path) -> StatusArchive:
    return StatusArchive(tmp_path / "status-archive.jsonl")


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class TestArchiveMechanics:
    def test_append_writes_one_line_per_station(self, archive):
        written = archive.append("radar", [_radar("KTLX", *KTLX), _radar("KFDR", *KFDR)])
        assert written == 2
        lines = archive.path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["station_id"] == "KTLX"
        assert first["layer"] == "radar"
        assert first["values"]["radar_latency_s"] == 41.0

    def test_a_row_without_an_identity_is_not_archived(self, archive):
        anonymous = _radar("KTLX", *KTLX)
        anonymous.pop("radar_id")
        anonymous.pop("id")
        assert archive.append("radar", [anonymous, "not-a-dict", {}]) == 0

    def test_window_reports_the_archive_extent_not_just_the_matches(self, archive):
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        for hours in range(4):
            archive.append("radar", [_radar("KTLX", *KTLX)], ts=base + timedelta(hours=hours))
        out = archive.window(
            layer="radar", station_ids=["KTLX"],
            start=base + timedelta(hours=2), end=base + timedelta(hours=3),
        )
        assert out["sample_count"] == 2
        # Extent covers everything held, so the caller can tell "no samples in window"
        # from "nothing in the archive at all".
        assert out["archive_start"] == _iso(base)
        assert out["archive_end"] == _iso(base + timedelta(hours=3))
        assert out["layer_sample_count"] == 4

    def test_window_filters_by_station_and_layer(self, archive):
        archive.append("radar", [_radar("KTLX", *KTLX), _radar("KFDR", *KFDR)])
        archive.append("weather", [{"id": "om-wx", "lat": 1.0, "lon": 2.0, "values": {}}])
        out = archive.window(layer="radar", station_ids=["KFDR"])
        assert [s["station_id"] for s in out["samples"]] == ["KFDR"]
        assert out["layer_sample_count"] == 2

    def test_samples_come_back_in_time_order(self, archive):
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        for hours in (3, 0, 2, 1):
            archive.append("radar", [_radar("KTLX", *KTLX)], ts=base + timedelta(hours=hours))
        stamps = [s["ts"] for s in archive.window(layer="radar")["samples"]]
        assert stamps == sorted(stamps)

    def test_prune_drops_samples_past_the_retention_window(self, archive, monkeypatch):
        monkeypatch.setenv("ATLAS_STATUS_ARCHIVE_DAYS", "7")
        now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        archive.append("radar", [_radar("KTLX", *KTLX)], ts=now - timedelta(days=30))
        archive.append("radar", [_radar("KTLX", *KTLX)], ts=now - timedelta(days=1))
        assert archive.prune(now=now) == 1
        out = archive.window(layer="radar")
        assert out["sample_count"] == 1
        assert out["archive_start"] == _iso(now - timedelta(days=1))

    def test_prune_caps_total_rows(self, archive, monkeypatch):
        monkeypatch.setenv("ATLAS_STATUS_ARCHIVE_MAX_ROWS", "3")
        now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
        for minutes in range(6):
            archive.append("radar", [_radar("KTLX", *KTLX)], ts=now - timedelta(minutes=minutes))
        assert archive.prune(now=now) == 3
        assert archive.window(layer="radar")["sample_count"] == 3

    def test_a_corrupt_line_never_breaks_a_read(self, archive):
        archive.append("radar", [_radar("KTLX", *KTLX)])
        with archive.path.open("a", encoding="utf-8") as fh:
            fh.write("{not json\n\n")
        assert archive.window(layer="radar")["sample_count"] == 1

    def test_an_absent_archive_reads_as_empty_not_an_error(self, tmp_path):
        empty = StatusArchive(tmp_path / "nothing-here.jsonl")
        out = empty.window(layer="radar")
        assert out == {
            "samples": [], "sample_count": 0, "archive_start": None,
            "archive_end": None, "layer_sample_count": 0, "truncated": False,
        }

    def test_parse_iso_accepts_both_offset_and_z(self):
        assert parse_iso("2026-08-28T06:00:00Z").tzinfo is timezone.utc
        assert parse_iso("2026-08-28T06:00:00+00:00") == parse_iso("2026-08-28T06:00:00Z")
        assert parse_iso("") is None
        assert parse_iso("not a time") is None
        # A naive stamp is read as UTC rather than rejected or localised.
        assert parse_iso("2026-08-28T06:00:00").tzinfo is timezone.utc


class TestTheAttestationItself:
    def test_a_recorded_degraded_status_is_positive_evidence(self, archive):
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        archive.append("radar", [_radar("KTLX", *KTLX)], ts=base)
        archive.append(
            "radar",
            [_radar("KTLX", *KTLX, status="Down", operability="RDA - Off-line")],
            ts=base + timedelta(hours=1),
        )
        out = observability_attest(
            {
                "lat": EVENT[0], "lon": EVENT[1], "event_id": "claim-88",
                "start": _iso(base), "end": _iso(base + timedelta(hours=1)),
            },
            [_radar("KTLX", *KTLX), _alert(*EVENT), _wx(35.3, -97.5)],
            archive,
        )
        assert out["ok"] is True
        assert out["attestation_kind"] == "data_availability"
        assert out["degraded_sample_count"] == 1
        ktlx = next(r for r in out["radars"] if r["station_id"] == "KTLX")
        assert ktlx["archive"]["samples"] == 2
        assert ktlx["archive"]["degraded_samples"] == 1
        assert ktlx["archive"]["degraded_first_ts"] == _iso(base + timedelta(hours=1))
        assert out["window_coverage"]["coverage"] == "recorded"
        assert any("1 sample(s) recorded a degraded status" in d for d in out["drivers"])

    def test_a_window_reaching_past_the_last_sample_is_partial(self, archive):
        """The tail of the window has no samples, so it is not attested either."""
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        archive.append("radar", [_radar("KTLX", *KTLX)], ts=base)
        out = observability_attest(
            {
                "lat": EVENT[0], "lon": EVENT[1],
                "start": _iso(base), "end": _iso(base + timedelta(hours=6)),
            },
            [_radar("KTLX", *KTLX)],
            archive,
        )
        assert out["window_coverage"]["coverage"] == "partial"
        assert out["window_coverage"]["archive_end"] == _iso(base)

    def test_an_empty_archive_is_not_a_clean_bill_of_health(self, archive):
        """The failure this SKU exists to prevent: silence read as "all fine"."""
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1], "start": "2026-01-01T00:00:00Z",
             "end": "2026-01-02T00:00:00Z"},
            [_radar("KTLX", *KTLX)],
            archive,
        )
        assert out["ok"] is True
        assert out["window_coverage"]["coverage"] == "none"
        assert out["window_coverage"]["samples_in_window"] == 0
        assert out["degraded_sample_count"] == 0
        assert any(
            "attests missing evidence, not a healthy radar" in d for d in out["drivers"]
        )
        assert any(
            "absence of evidence, NOT evidence the radar was down" in line
            for line in out["limitations"]
        )

    def test_a_window_older_than_the_archive_is_partial_not_recorded(self, archive):
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        archive.append("radar", [_radar("KTLX", *KTLX)], ts=base)
        out = observability_attest(
            {
                "lat": EVENT[0], "lon": EVENT[1],
                "start": _iso(base - timedelta(days=30)),
                "end": _iso(base + timedelta(hours=1)),
            },
            [_radar("KTLX", *KTLX)],
            archive,
        )
        assert out["window_coverage"]["coverage"] == "partial"
        assert out["window_coverage"]["archive_start"] == _iso(base)
        assert any("extends beyond what the archive holds" in d for d in out["drivers"])
        assert any("reported as uncovered rather than clean" in line for line in out["limitations"])

    def test_radars_are_ordered_by_distance_and_carry_it(self, archive):
        archive.append("radar", [_radar("KTLX", *KTLX), _radar("KFDR", *KFDR)])
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1], "max_km": 400},
            [_radar("KTLX", *KTLX), _radar("KFDR", *KFDR)],
            archive,
        )
        ids = [r["station_id"] for r in out["radars"]]
        assert ids == ["KTLX", "KFDR"]
        assert out["radars"][0]["distance_km"] < out["radars"][1]["distance_km"]
        assert out["radars"][0]["status_now"] == "Operational"

    def test_a_radar_beyond_max_km_is_excluded(self, archive):
        archive.append("radar", [_radar("KFDR", *KFDR)])
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1], "max_km": 50},
            [_radar("KTLX", *KTLX), _radar("KFDR", *KFDR)],
            archive,
        )
        assert [r["station_id"] for r in out["radars"]] == ["KTLX"]

    def test_no_radar_in_range_refuses_and_names_the_geography(self, archive):
        out = observability_attest(
            {"lat": 48.85, "lon": 2.35, "max_km": 100},  # Paris
            [_radar("KTLX", *KTLX)],
            archive,
        )
        assert out["ok"] is False
        assert "no radar station within 100 km" in out["refuse_reason"]
        assert "United States territory" in out["refuse_reason"]
        assert "receipt" not in out

    def test_max_km_is_bounded_to_useful_radar_range(self, archive):
        archive.append("radar", [_radar("KTLX", *KTLX)])
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1], "max_km": 99999},
            [_radar("KTLX", *KTLX)],
            archive,
        )
        assert out["query"]["max_km"] == 460.0

    def test_an_inverted_window_refuses(self, archive):
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1],
             "start": "2026-08-20T12:00:00Z", "end": "2026-08-19T12:00:00Z"},
            [_radar("KTLX", *KTLX)],
            archive,
        )
        assert out["ok"] is False
        assert "end must not precede start" in out["refuse_reason"]

    @pytest.mark.parametrize("bad", [{"lat": 91.0, "lon": 0.0}, {"lat": 0.0, "lon": 181.0}, {}])
    def test_bad_coordinates_refuse(self, archive, bad):
        out = observability_attest(bad, [_radar("KTLX", *KTLX)], archive)
        assert out["ok"] is False
        assert "lat/lon required" in out["refuse_reason"]

    def test_alerts_are_labelled_current_because_history_is_not_archived(self, archive):
        archive.append("radar", [_radar("KTLX", *KTLX)])
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1]},
            [_radar("KTLX", *KTLX), _alert(*EVENT)],
            archive,
        )
        assert len(out["active_alerts"]) == 1
        assert any("currently within" in d for d in out["drivers"])
        assert any("alert history is not archived" in line for line in out["limitations"])

    def test_the_sku_never_claims_to_reconstruct_the_weather(self, archive):
        archive.append("radar", [_radar("KTLX", *KTLX)])
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1]}, [_radar("KTLX", *KTLX)], archive
        )
        joined = " ".join(out["limitations"]) + " " + out["summary"]
        assert "not a weather reconstruction" in joined
        assert "not an adjudication" in joined
        assert "not reflectivity" in joined
        assert "Attests what evidence exists, not what the weather was." in out["summary"]

    def test_status_words_that_mean_impaired_are_all_recognised(self, archive):
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        for i, (status, operability) in enumerate([
            ("Down", "RDA - Off-line"),
            ("Operational", "RDA - Maintenance"),
            ("Outage", ""),
            ("Operational", "Inoperable"),
            ("Failure", ""),
        ]):
            archive.append(
                "radar",
                [_radar("KTLX", *KTLX, status=status, operability=operability)],
                ts=base + timedelta(minutes=i),
            )
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1]}, [_radar("KTLX", *KTLX)], archive
        )
        assert out["degraded_sample_count"] == 5

    def test_a_healthy_run_of_samples_reports_zero_degraded(self, archive):
        base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        for i in range(6):
            archive.append("radar", [_radar("KTLX", *KTLX)], ts=base + timedelta(minutes=10 * i))
        out = observability_attest(
            {"lat": EVENT[0], "lon": EVENT[1]}, [_radar("KTLX", *KTLX)], archive
        )
        assert out["degraded_sample_count"] == 0
        assert out["window_coverage"]["coverage"] == "recorded"
        assert any("no archived sample recorded a degraded status" in d for d in out["drivers"])

    def test_the_declared_output_schema_covers_a_refusal_too(self, archive):
        import jsonschema

        refusal = observability_attest({"lat": 48.85, "lon": 2.35, "max_km": 10}, [], archive)
        assert refusal["ok"] is False
        jsonschema.validate(
            refusal, CAP_BY_ID["atlas.observability.attest@v1"]["output_schema"]
        )

    def test_invoke_product_routes_the_sku(self, archive):
        out = invoke_product(
            "atlas.observability.attest@v1",
            {"lat": EVENT[0], "lon": EVENT[1]},
            [_radar("KTLX", *KTLX)],
        )
        # Routed without an injected archive: it uses the process default, which in a
        # test process is empty — the honest answer is "coverage none", not a crash.
        assert out["ok"] is True
        assert out["sku"] == "atlas.observability.attest@v1"


class TestTheSampler:
    @pytest.mark.asyncio
    async def test_a_tick_archives_one_sample_per_station(self, archive):
        from atlas.status_sampler import StatusSampler

        async def fetch(layers):
            assert layers == {"radar"}
            return [_radar("KTLX", *KTLX), _radar("KFDR", *KFDR), _wx(35.3, -97.5)]

        sampler = StatusSampler(fetch=fetch, archive=archive, interval_s=30)
        assert await sampler.tick() == 2
        out = archive.window(layer="radar")
        assert {s["station_id"] for s in out["samples"]} == {"KTLX", "KFDR"}

    @pytest.mark.asyncio
    async def test_a_tick_with_no_pins_writes_nothing(self, archive):
        from atlas.status_sampler import StatusSampler

        async def fetch(_layers):
            return []

        sampler = StatusSampler(fetch=fetch, archive=archive, interval_s=30)
        assert await sampler.tick() == 0
        assert not archive.path.exists()

    @pytest.mark.asyncio
    async def test_the_interval_has_a_floor(self, archive):
        from atlas.status_sampler import StatusSampler

        async def fetch(_layers):
            return []

        assert StatusSampler(fetch=fetch, archive=archive, interval_s=1)._interval == 30.0
        assert StatusSampler(fetch=fetch, archive=archive, interval_s=900)._interval == 900.0

    @pytest.mark.asyncio
    async def test_sampling_can_be_switched_off(self, archive, monkeypatch):
        from atlas.status_sampler import StatusSampler

        monkeypatch.setenv("ATLAS_STATUS_ARCHIVE", "0")

        async def fetch(_layers):
            raise AssertionError("must not be called when sampling is disabled")

        sampler = StatusSampler(fetch=fetch, archive=archive, interval_s=30)
        await sampler.start()
        assert sampler._task is None
        await sampler.stop()
