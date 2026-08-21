"""Watchbox delivery loop + durable monitor log.

The gap this closes: `webhook_url` was accepted, validated and stored, and nothing ever
POSTed to it. Every watchbox was poll-only and the field was decoration. These tests pin
the half that was missing, and specifically the properties that make the log evidence
rather than telemetry:

* the check is logged BEFORE delivery, so a permanently unreachable receiver still
  leaves a record that we checked;
* the log is append-only at the DATABASE level, not by convention;
* failures are counted and surfaced, because a log that quietly omits gaps is worse
  than no log;
* the HMAC secret and the owner token are each returned exactly once and never echoed
  by a read endpoint;
* cancelling a subscription stops the checks without making the evidence unreachable.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from atlas import delivery as delivery_mod
from atlas import monitor_log as mlog
from atlas import watchboxes as watchbox_mod


class _FakeSigner:
    public_key_b64 = "fake-pub"

    def sign_canonical(self, canonical: str) -> str:
        return "sig:" + hashlib.sha256(canonical.encode()).hexdigest()[:16]


class _Resp:
    def __init__(self, code: int) -> None:
        self.status_code = code


class _FakeClient:
    """Async-context httpx stand-in that records posts and replays scripted codes."""

    def __init__(self, codes: list[int], sink: list[dict]) -> None:
        self._codes = codes
        self._sink = sink

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, content=None, headers=None):
        self._sink.append({"url": url, "body": content, "headers": dict(headers or {})})
        code = self._codes.pop(0) if self._codes else 200
        if code == 0:
            raise RuntimeError("connection refused")
        return _Resp(code)


def _isolate_registry(monkeypatch, tmp_path: Path):
    """Point the process-wide stores at tmp.

    `ATLAS_WATCHBOX_PATH` alone is not enough: `watchboxes.STORE` is built at import
    time, so a reload of `atlas.main` keeps the store that was constructed from the
    repo-relative default — and these tests then wrote real rows into
    `atlas/data/watchboxes.json`. That was invisible while DELETE hard-removed the row
    it created; now that DELETE is an unsubscribe, the leftovers collide with the next
    run. Bind the stores explicitly instead of trusting import order.
    """
    from atlas import products as products_mod

    store = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
    monkeypatch.setattr(watchbox_mod, "STORE", store)
    monkeypatch.setattr(products_mod, "STORE", store)
    monkeypatch.setattr(mlog, "STORE", mlog.MonitorLog(tmp_path / "log.db"))
    return store


def _wb(**kw):
    row = {
        "id": "wb-test",
        "label": "test box",
        "west": -10.0, "south": 35.0, "east": 30.0, "north": 60.0,
        "layers": ["fire"],
        "webhook_url": "https://receiver.example.com/hook",
        "webhook_secret": "s3cret",
    }
    row.update(kw)
    return row


def _result():
    return {
        "ok": True,
        "evaluated_at": "2026-08-13T10:00:00+00:00",
        "bbox": {"west": -10.0, "south": 35.0, "east": 30.0, "north": 60.0},
        "layers": ["fire"],
        "match_count": 1902,
        "live_match_count": 1900,
    }


def _loop(tmp_path: Path, codes: list[int], sink: list[dict], row=None):
    store = mlog.MonitorLog(tmp_path / "log.db")
    return store, delivery_mod.DeliveryLoop(
        evaluate=lambda r: _result(),
        signer=_FakeSigner(),
        interval_s=3600,
        store=store,
        client_factory=lambda: _FakeClient(codes, sink),
    )


class TestDelivery:
    @pytest.mark.asyncio
    async def test_check_is_logged_and_delivered(self, tmp_path):
        sink: list[dict] = []
        store, loop = _loop(tmp_path, [200], sink)
        assert await loop.check_and_deliver(_wb()) is True

        rows = store.checks("wb-test")
        assert len(rows) == 1
        assert rows[0]["match_count"] == 1902
        assert rows[0]["live_match_count"] == 1900
        assert rows[0]["signature_b64"].startswith("sig:")
        assert rows[0]["deliveries"][0]["delivered"] == 1

        assert len(sink) == 1
        assert sink[0]["url"] == "https://receiver.example.com/hook"

    @pytest.mark.asyncio
    async def test_hmac_signature_is_over_the_exact_bytes_sent(self, tmp_path):
        sink: list[dict] = []
        _store, loop = _loop(tmp_path, [200], sink)
        await loop.check_and_deliver(_wb())
        body = sink[0]["body"]
        expected = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
        assert sink[0]["headers"]["x-atlas-signature"] == f"sha256={expected}"
        # And the receiver can read the check without the signature to know what it is.
        parsed = json.loads(body)
        assert parsed["event"] == "atlas.watchbox.check"
        assert parsed["match_count"] == 1902

    @pytest.mark.asyncio
    async def test_evidence_survives_a_receiver_that_never_answers(self, tmp_path):
        """The log records that WE checked — not that anyone received it."""
        sink: list[dict] = []
        store, loop = _loop(tmp_path, [0, 0, 0, 0, 0], sink)
        delivery_mod.BACKOFF_BASE_S = 1.0  # keep the test fast; 1**n == 1
        await loop.check_and_deliver(_wb())

        rows = store.checks("wb-test")
        assert len(rows) == 1, "the check must be logged even when delivery fails"
        assert all(d["delivered"] == 0 for d in rows[0]["deliveries"])
        assert len(rows[0]["deliveries"]) == delivery_mod.MAX_ATTEMPTS
        # The gap is reported, not hidden.
        assert store.summary("wb-test")["checks_never_delivered"] == 1

    @pytest.mark.asyncio
    async def test_permanent_4xx_is_not_retried(self, tmp_path):
        """A 403 means "never send this again"; retrying looks like an attack."""
        sink: list[dict] = []
        store, loop = _loop(tmp_path, [403], sink)
        await loop.check_and_deliver(_wb())
        assert len(sink) == 1
        assert len(store.checks("wb-test")[0]["deliveries"]) == 1

    @pytest.mark.asyncio
    async def test_429_is_retried(self, tmp_path):
        sink: list[dict] = []
        store, loop = _loop(tmp_path, [429, 200], sink)
        delivery_mod.BACKOFF_BASE_S = 1.0
        await loop.check_and_deliver(_wb())
        assert len(sink) == 2
        assert store.checks("wb-test")[0]["deliveries"][-1]["delivered"] == 1

    @pytest.mark.asyncio
    async def test_a_watchbox_without_a_webhook_is_still_logged(self, tmp_path):
        sink: list[dict] = []
        store, loop = _loop(tmp_path, [200], sink)
        await loop.check_and_deliver(_wb(webhook_url=None, webhook_secret=None))
        assert len(store.checks("wb-test")) == 1
        assert sink == [], "nothing subscribed — nothing sent"

    @pytest.mark.asyncio
    async def test_stored_row_is_revalidated_before_posting(self, tmp_path):
        """A row outlives the validator that wrote it, so re-check at send time."""
        sink: list[dict] = []
        store, loop = _loop(tmp_path, [200], sink)
        await loop.check_and_deliver(_wb(webhook_url="http://127.0.0.1/steal"))
        assert sink == [], "loopback target must never be posted to"
        attempts = store.checks("wb-test")[0]["deliveries"]
        assert attempts and "refusing to deliver" in (attempts[0]["error"] or "")


class TestMonitorLogIsEvidence:
    def test_checks_cannot_be_updated(self, tmp_path):
        store = mlog.MonitorLog(tmp_path / "l.db")
        cid = store.append_check(
            watchbox_id="wb", evaluated_at="2026-08-13T10:00:00Z", match_count=1,
            live_match_count=1, layers=["fire"], bbox={}, digest="d",
            signature_b64="s", public_key_b64="p",
        )
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store._conn.execute("UPDATE checks SET match_count=99 WHERE id=?", (cid,))
            store._conn.commit()

    def test_summary_reports_the_watch_window(self, tmp_path):
        store = mlog.MonitorLog(tmp_path / "l.db")
        for ts in ("2026-08-01T00:00:00Z", "2026-08-13T00:00:00Z"):
            store.append_check(
                watchbox_id="wb", evaluated_at=ts, match_count=0, live_match_count=0,
                layers=["fire"], bbox={}, digest="d", signature_b64="s", public_key_b64="p",
            )
        s = store.summary("wb")
        assert s["checks_recorded"] == 2
        assert s["first_check_at"] == "2026-08-01T00:00:00Z"
        assert s["last_check_at"] == "2026-08-13T00:00:00Z"


class TestSecretHygiene:
    def test_public_row_strips_the_hmac_secret(self):
        pub = watchbox_mod.public_row(_wb())
        assert "webhook_secret" not in pub
        assert pub["webhook_configured"] is True

    def test_create_generates_a_secret_only_when_a_webhook_is_set(self, tmp_path):
        store = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        with_hook = store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"],
            webhook_url="https://a.example.com/h", watchbox_id="with-hook",
        )
        assert with_hook["webhook_secret"]
        without = store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="no-hook",
        )
        assert without["webhook_secret"] is None

    def test_public_row_strips_the_owner_token_and_its_digest(self, tmp_path):
        store = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        created = store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-owned",
        )
        pub = watchbox_mod.public_row(store.get("wb-owned"))
        assert "owner_token" not in pub and "owner_token_sha256" not in pub
        assert created["owner_token"] not in json.dumps(pub)

    def test_the_owner_token_is_stored_only_as_a_digest(self, tmp_path):
        """A registry file (or a backup of it) must not confer ownership."""
        store = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        created = store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-owned",
        )
        stored = store.get("wb-owned")
        assert "owner_token" not in stored
        assert stored["owner_token_sha256"] == watchbox_mod.hash_owner_token(
            created["owner_token"]
        )
        assert created["owner_token"] not in (tmp_path / "wb.json").read_text()

    def test_ownership_fails_closed(self, tmp_path):
        store = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        created = store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-owned",
        )
        row = store.get("wb-owned")
        assert watchbox_mod.owns(row, created["owner_token"]) is True
        assert watchbox_mod.owns(row, "not-the-token") is False
        assert watchbox_mod.owns(row, "") is False
        # A row minted before owner tokens existed carries no digest, so nothing can
        # claim it — it stays operator-only rather than becoming ownerless-and-open.
        assert watchbox_mod.owns(_wb(), "anything") is False
        assert watchbox_mod.owns(_wb(), "") is False
        assert watchbox_mod.owns(None, "anything") is False


class TestUnsubscribeKeepsTheEvidence:
    """DELETE used to drop the registry row and orphan the monitor log.

    The checks stayed in SQLite, but `GET /watchboxes/{id}/log` resolves the registry
    first — so cancelling (or, before the auth gate, anyone else cancelling) made the
    evidence unreachable while claiming success. For a product whose value is "prove you
    were monitoring", quietly losing the proof is worse than refusing to delete.
    """

    @pytest.mark.asyncio
    async def test_an_unsubscribed_box_is_no_longer_checked(self, tmp_path, monkeypatch):
        registry = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        monkeypatch.setattr(watchbox_mod, "STORE", registry)
        registry.create(
            west=-10, south=35, east=30, north=60, layers=["fire"], watchbox_id="wb-test",
        )
        store, loop = _loop(tmp_path, [200], [])

        assert await loop.tick() == 1, "a live watchbox is checked"
        registry.unsubscribe("wb-test")
        assert await loop.tick() == 0, "an unsubscribed watchbox is not checked again"

        # …and everything gathered up to the cancellation is still there.
        assert len(store.checks("wb-test")) == 1
        assert registry.get("wb-test") is not None

    def test_unsubscribe_is_idempotent_and_keeps_the_first_timestamp(self, tmp_path):
        registry = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        registry.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-x",
        )
        first = registry.unsubscribe("wb-x")
        again = registry.unsubscribe("wb-x")
        assert first["active"] is False
        assert again["unsubscribed_at"] == first["unsubscribed_at"]
        assert registry.unsubscribe("wb-missing") is None

    def test_purge_is_the_only_thing_that_removes_the_row(self, tmp_path):
        registry = watchbox_mod.WatchboxStore(tmp_path / "wb.json")
        registry.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-x",
        )
        registry.unsubscribe("wb-x")
        assert registry.get("wb-x") is not None
        assert registry.purge("wb-x") is True
        assert registry.get("wb-x") is None
        assert registry.purge("wb-x") is False

    def test_the_log_stays_readable_over_http_after_an_unsubscribe(
        self, monkeypatch, tmp_path
    ):
        """The end-to-end version of the orphaning bug, through the real routes."""
        from fastapi.testclient import TestClient

        monkeypatch.setenv("ATLAS_OPERATOR_TOKEN", "op-token")
        monkeypatch.setenv("ATLAS_MONITOR_DB_PATH", str(tmp_path / "log.db"))
        monkeypatch.setenv("ATLAS_WATCHBOX_DELIVERY", "0")
        _isolate_registry(monkeypatch, tmp_path)
        import importlib

        from atlas import config as cfg

        cfg.get_settings.cache_clear()
        from atlas import main as main_mod

        importlib.reload(main_mod)
        client = TestClient(main_mod.app)
        h = {"X-Atlas-Token": "op-token"}
        with client:
            created = client.post("/api/v1/watchboxes", headers=h, json={
                "id": "wb-evidence", "west": 1, "south": 1, "east": 2, "north": 2,
                "layers": ["fire"],
            })
            assert created.status_code == 200, created.text
            owner = {"X-Atlas-Watchbox-Token": created.json()["owner_token"]}

            mlog.get_store().append_check(
                watchbox_id="wb-evidence", evaluated_at="2026-08-13T10:00:00Z",
                match_count=3, live_match_count=3, layers=["fire"], bbox={},
                digest="d", signature_b64="s", public_key_b64="p",
            )

            assert client.delete("/api/v1/watchboxes/wb-evidence", headers=owner).json()[
                "purged"
            ] is False
            log = client.get("/api/v1/watchboxes/wb-evidence/log", headers=owner)
            assert log.status_code == 200, "unsubscribing must not orphan the evidence"
            assert log.json()["summary"]["checks_recorded"] == 1
            assert log.json()["active"] is False


class TestRegistryIsNotAnonymous:
    """The watchbox registry was fully anonymous in production.

    Verified against prod before the gate: `GET /api/v1/watchboxes` published every
    watchbox id and bbox, and an anonymous `DELETE /api/v1/watchboxes/{id}` returned
    `{"ok": true}`. Because the log endpoint resolves the registry first, a stranger who
    read an id off the public list could stop the monitoring AND make the evidence log
    answer 404 — the two things an evidence product must never allow.
    """

    TOKEN = "test-operator-token"

    def _client(self, monkeypatch, tmp_path):
        from fastapi.testclient import TestClient
        monkeypatch.setenv("ATLAS_OPERATOR_TOKEN", self.TOKEN)
        monkeypatch.setenv("ATLAS_WATCHBOX_PATH", str(tmp_path / "wb.json"))
        monkeypatch.setenv("ATLAS_MONITOR_DB_PATH", str(tmp_path / "log.db"))
        monkeypatch.setenv("ATLAS_WATCHBOX_DELIVERY", "0")
        _isolate_registry(monkeypatch, tmp_path)
        import importlib
        from atlas import config as cfg
        cfg.get_settings.cache_clear()
        from atlas import main as main_mod
        importlib.reload(main_mod)
        return TestClient(main_mod.app), main_mod

    def test_every_registry_route_refuses_anonymous_callers(self, monkeypatch, tmp_path):
        client, main_mod = self._client(monkeypatch, tmp_path)
        from fastapi import HTTPException
        assert not issubclass(main_mod.OperatorRequired, HTTPException)
        with client:
            for method, path in (
                ("get", "/api/v1/watchboxes"),
                ("post", "/api/v1/watchboxes"),
                ("get", "/api/v1/watchboxes/wb-x"),
                ("get", "/api/v1/watchboxes/wb-x/log"),
                ("delete", "/api/v1/watchboxes/wb-x"),
            ):
                kwargs = {}
                if method == "post":
                    kwargs["json"] = {
                        "west": 1, "south": 1, "east": 2, "north": 2, "layers": ["fire"],
                    }
                r = getattr(client, method)(path, **kwargs)
                assert r.status_code == 401, f"{method.upper()} {path} -> {r.status_code} {r.text}"
                assert r.status_code != 400
                assert "token" in r.json()["detail"].lower()

    def test_operator_token_still_works_end_to_end(self, monkeypatch, tmp_path):
        client, _ = self._client(monkeypatch, tmp_path)
        h = {"X-Atlas-Token": self.TOKEN}
        with client:
            created = client.post("/api/v1/watchboxes", headers=h, json={
                "id": "wb-authed", "west": 1, "south": 1, "east": 2, "north": 2,
                "layers": ["fire"],
            })
            assert created.status_code == 200, created.text
            assert client.get("/api/v1/watchboxes", headers=h).status_code == 200
            assert client.get("/api/v1/watchboxes/wb-authed/log", headers=h).status_code == 200
            assert client.delete("/api/v1/watchboxes/wb-authed", headers=h).status_code == 200


class TestRetentionIsNotOversold:
    def test_summary_labels_retention_as_declared_not_enforced(self, tmp_path):
        store = mlog.MonitorLog(tmp_path / "r.db")
        s = store.summary("wb")
        assert s["retention_enforced"] is False
        assert "retention_days" not in s, "a bare retention_days reads as a guarantee"
        assert s["retention_days_declared"] >= 1

    def test_deletes_are_refused_outright(self, tmp_path):
        """The old trigger let a delete through when meta.retention_floor was set —
        and nothing wrote or protected that row, so one INSERT unlocked the whole log."""
        import sqlite3
        store = mlog.MonitorLog(tmp_path / "d.db")
        cid = store.append_check(
            watchbox_id="wb", evaluated_at="2026-08-13T10:00:00Z", match_count=1,
            live_match_count=1, layers=["fire"], bbox={}, digest="d",
            signature_b64="s", public_key_b64="p",
        )
        store._conn.execute("INSERT OR REPLACE INTO meta VALUES ('retention_floor','2099-01-01')")
        store._conn.commit()
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store._conn.execute("DELETE FROM checks WHERE id=?", (cid,))
            store._conn.commit()


class TestContinuityIsComputed:
    """count+first+last cannot express a gap — so continuity is computed.

    A log with a week-long outage in the middle still spans the whole period, so a
    dirty log was indistinguishable from a continuous one. That is the one question an
    auditor asks about a monitoring record.
    """

    def _log(self, tmp_path, stamps):
        store = mlog.MonitorLog(tmp_path / "c.db")
        for ts in stamps:
            store.append_check(
                watchbox_id="wb", evaluated_at=ts, match_count=0, live_match_count=0,
                layers=["fire"], bbox={}, digest="d", signature_b64="s", public_key_b64="p",
            )
        return store

    def test_a_week_long_outage_is_reported(self, tmp_path):
        store = self._log(tmp_path, [
            "2026-08-01T00:00:00Z", "2026-08-01T00:05:00Z", "2026-08-08T00:00:00Z",
        ])
        g = store.gaps("wb", expected_interval_s=300)
        assert g["gap_count"] == 1
        assert g["longest_interval_s"] > 600_000
        assert g["gaps"][0]["after"] == "2026-08-01T00:05:00Z"
        # And the summary alone still cannot show it — which is why gaps() exists.
        s = store.summary("wb")
        assert s["checks_recorded"] == 3

    def test_a_continuous_log_reports_no_gap(self, tmp_path):
        store = self._log(tmp_path, [
            "2026-08-01T00:00:00Z", "2026-08-01T00:05:00Z", "2026-08-01T00:10:00Z",
        ])
        g = store.gaps("wb", expected_interval_s=300)
        assert g["gap_count"] == 0
        assert g["longest_interval_s"] == 300.0

    def test_one_slow_tick_is_not_an_incident(self, tmp_path):
        """Threshold is 3x cadence: a single late tick must not read as an outage."""
        store = self._log(tmp_path, ["2026-08-01T00:00:00Z", "2026-08-01T00:12:00Z"])
        assert store.gaps("wb", expected_interval_s=300)["gap_count"] == 0

    def test_unparseable_timestamps_are_counted_not_hidden(self, tmp_path):
        store = self._log(tmp_path, ["2026-08-01T00:00:00Z", "not-a-timestamp"])
        assert store.gaps("wb", expected_interval_s=300)["unparseable_timestamps"] == 1
