"""ATLAS watchbox HTTP API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas import watchboxes as wb_mod

OPERATOR_TOKEN = "test-operator-token"


def _wire(tmp_path: Path, monkeypatch, **env):
    """Isolated registry + monitor log, operator token configured."""
    store = wb_mod.WatchboxStore(path=tmp_path / "watchboxes.json")
    monkeypatch.setattr(wb_mod, "STORE", store)
    from atlas import products as products_mod

    monkeypatch.setattr(products_mod, "STORE", store)

    from atlas import monitor_log as mlog

    monkeypatch.setattr(mlog, "STORE", mlog.MonitorLog(tmp_path / "monitor.db"))
    # The delivery loop would otherwise tick against the real fleet during the test.
    monkeypatch.setenv("ATLAS_WATCHBOX_DELIVERY", "0")
    monkeypatch.setenv("ATLAS_OPERATOR_TOKEN", OPERATOR_TOKEN)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    from atlas import config as cfg

    cfg.get_settings.cache_clear()
    import atlas.main as main_mod

    monkeypatch.setattr(main_mod, "settings", cfg.get_settings())
    return main_mod.app, store


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    """Operator-authenticated client — exercises the authorised path.

    The registry is credentialed: it was fully anonymous in production, where
    `DELETE /api/v1/watchboxes/{id}` succeeded for anybody and the evidence log then
    answered 404. Refusals are pinned in `TestOwnershipIsEnforced` below and in
    test_watchbox_delivery.py::TestRegistryIsNotAnonymous.
    """
    app, store = _wire(tmp_path, monkeypatch)
    with TestClient(app, headers={"X-Atlas-Token": OPERATOR_TOKEN}) as c:
        yield c, store


@pytest.fixture
def anon(tmp_path: Path, monkeypatch):
    """No credentials at all — the stranger who knows an id."""
    app, store = _wire(tmp_path, monkeypatch)
    with TestClient(app) as c:
        yield c, store


def _uncredentialed(c) -> TestClient:
    """A second client onto the same app, carrying no operator header."""
    return TestClient(c.app)


def _create(c, **over):
    body = {
        "west": -80, "south": 35, "east": -70, "north": 45,
        "layers": ["fire"], "label": "box",
    }
    body.update(over)
    r = c.post("/api/v1/watchboxes", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_watchbox_crud_and_check(client):
    c, store = client
    r = c.get("/api/v1/watchboxes")
    assert r.status_code == 200
    body = r.json()
    assert body["sku"] == "atlas.watchbox.subscribe@v1"
    assert "fire" in body["allowed_layers"]

    created = c.post(
        "/api/v1/watchboxes",
        json={
            "id": "wb-api-01",
            "west": -80,
            "south": 35,
            "east": -70,
            "north": 45,
            "layers": ["fire", "quake", "gfw-nc-should-drop"],
            "label": "East US",
        },
    )
    assert created.status_code == 200
    assert created.json()["watchbox"]["layers"] == ["fire", "quake"]

    got = c.get("/api/v1/watchboxes/wb-api-01")
    assert got.status_code == 200

    check = c.post("/api/v1/watchboxes/wb-api-01/check")
    assert check.status_code == 200
    assert check.json()["sku"] == "atlas.watchbox.check@v1"
    assert "match_count" in check.json()
    assert "receipt" in check.json()

    # DELETE is an unsubscribe: monitoring stops, the row (and its log) survives.
    deleted = c.delete("/api/v1/watchboxes/wb-api-01")
    assert deleted.status_code == 200
    assert deleted.json()["purged"] is False
    assert c.get("/api/v1/watchboxes/wb-api-01").json()["watchbox"]["active"] is False

    # Purge is the explicit, operator-only way to destroy the row.
    purged = c.delete("/api/v1/watchboxes/wb-api-01?purge=true")
    assert purged.status_code == 200
    assert purged.json()["purged"] is True
    assert c.get("/api/v1/watchboxes/wb-api-01").status_code == 404


def test_watchbox_rejects_bad_layers(client):
    c, _ = client
    r = c.post(
        "/api/v1/watchboxes",
        json={
            "west": 0,
            "south": 0,
            "east": 1,
            "north": 1,
            "layers": ["not-real"],
        },
    )
    assert r.status_code == 400


class TestOwnershipIsEnforced:
    """Per-watchbox owner tokens: a buyer's credential for their box and nothing else.

    Operator-only was safe but had no tenancy — the only credential that could read a
    buyer's evidence log was the master key that reads everyone's.
    """

    def test_create_returns_the_owner_token_exactly_once(self, client):
        c, _ = client
        out = _create(c, id="wb-owned")
        token = out["owner_token"]
        assert token and out["owner_token_header"] == "X-Atlas-Watchbox-Token"
        # …and it is never echoed again, by any read route.
        assert "owner_token" not in out["watchbox"]
        assert "owner_token_sha256" not in out["watchbox"]

        got = c.get("/api/v1/watchboxes/wb-owned").json()["watchbox"]
        assert "owner_token" not in got and "owner_token_sha256" not in got
        assert token not in json.dumps(got)
        listed = c.get("/api/v1/watchboxes").json()
        assert token not in json.dumps(listed)
        assert all(
            "owner_token" not in w and "owner_token_sha256" not in w
            for w in listed["watchboxes"]
        )

    def test_the_store_persists_only_a_digest(self, tmp_path):
        store = wb_mod.WatchboxStore(tmp_path / "wb.json")
        created = store.create(west=1, south=1, east=2, north=2, layers=["fire"])
        token = created["owner_token"]
        raw = (tmp_path / "wb.json").read_text(encoding="utf-8")
        assert token not in raw, "the owner token must never be persisted in the clear"
        assert wb_mod.hash_owner_token(token) in raw
        assert store.get(created["id"]).get("owner_token") is None

    def test_the_owner_can_read_and_unsubscribe_without_the_operator_token(self, client):
        c, _ = client
        token = _create(c, id="wb-solo")["owner_token"]
        h = {"X-Atlas-Watchbox-Token": token}
        # A client with no operator header, only the owner token.
        owner = _uncredentialed(c)
        assert owner.get("/api/v1/watchboxes/wb-solo", headers=h).status_code == 200
        assert owner.get("/api/v1/watchboxes/wb-solo/log", headers=h).status_code == 200
        assert owner.delete("/api/v1/watchboxes/wb-solo", headers=h).status_code == 200
        # Unsubscribing does not take the evidence away — that is the whole point.
        log = owner.get("/api/v1/watchboxes/wb-solo/log", headers=h)
        assert log.status_code == 200
        assert log.json()["active"] is False

    def test_a_bearer_credential_is_accepted_too(self, client):
        c, _ = client
        token = _create(c, id="wb-bearer")["owner_token"]
        r = _uncredentialed(c).get(
            "/api/v1/watchboxes/wb-bearer",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    def test_the_list_does_not_leak_another_tenants_watchbox(self, client):
        c, _ = client
        mine = _create(c, id="wb-mine", label="mine")["owner_token"]
        _create(c, id="wb-theirs", label="theirs")

        body = _uncredentialed(c).get(
            "/api/v1/watchboxes", headers={"X-Atlas-Watchbox-Token": mine}
        ).json()
        assert [w["id"] for w in body["watchboxes"]] == ["wb-mine"]
        assert body["scope"] == "owner"
        assert "theirs" not in json.dumps(body)
        # No secret material in the scoped listing either.
        assert all(
            "owner_token" not in w and "owner_token_sha256" not in w
            and "webhook_secret" not in w
            for w in body["watchboxes"]
        )

        # The operator still sees the whole registry.
        assert len(c.get("/api/v1/watchboxes").json()["watchboxes"]) == 2

    def test_a_wrong_token_cannot_confirm_that_an_id_exists(self, client):
        c, _ = client
        _create(c, id="wb-secret-id")
        stranger = {"X-Atlas-Watchbox-Token": "not-the-right-token"}
        bad = _uncredentialed(c)
        # Identical answer for a real id and an invented one: no existence oracle.
        assert bad.get("/api/v1/watchboxes/wb-secret-id", headers=stranger).status_code == 404
        assert bad.get("/api/v1/watchboxes/wb-nope", headers=stranger).status_code == 404
        assert bad.delete("/api/v1/watchboxes/wb-secret-id", headers=stranger).status_code == 404
        assert bad.get("/api/v1/watchboxes/wb-secret-id/log", headers=stranger).status_code == 404
        # …and it is still there, still monitored.
        assert c.get("/api/v1/watchboxes/wb-secret-id").json()["watchbox"]["active"] is True

    def test_an_owner_cannot_purge_only_the_operator_can(self, client):
        c, _ = client
        token = _create(c, id="wb-keep")["owner_token"]
        r = _uncredentialed(c).delete(
            "/api/v1/watchboxes/wb-keep?purge=true",
            headers={"X-Atlas-Watchbox-Token": token},
        )
        assert r.status_code == 401
        assert c.get("/api/v1/watchboxes/wb-keep").status_code == 200


class TestAnonymousCallersAreRefused:
    """The exact production attack: read an id off the list, delete it, log goes 404."""

    def test_anonymous_delete_is_refused_and_the_watchbox_survives(self, anon, tmp_path):
        c, store = anon
        store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-victim",
        )
        assert c.delete("/api/v1/watchboxes/wb-victim").status_code == 401
        assert store.get("wb-victim") is not None

    def test_anonymous_log_read_is_refused(self, anon):
        c, store = anon
        store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-victim",
        )
        assert c.get("/api/v1/watchboxes/wb-victim/log").status_code == 401

    def test_anonymous_list_reveals_nothing(self, anon):
        c, store = anon
        store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-victim",
        )
        r = c.get("/api/v1/watchboxes")
        assert r.status_code == 401
        assert r.status_code != 400
        assert "token" in r.json()["detail"].lower()
        assert r.headers.get("www-authenticate", "").startswith("X-Atlas-Token")
        assert "wb-victim" not in r.text
        assert "Cache-Control" not in r.headers or "public" not in r.headers.get("Cache-Control", "")

    def test_anonymous_check_cannot_read_a_stored_bbox(self, anon):
        c, store = anon
        store.create(
            west=-1, south=1, east=2, north=3, layers=["fire"], watchbox_id="wb-victim",
        )
        assert c.post("/api/v1/watchboxes/wb-victim/check").status_code == 401
        # Same through the hub-compatible invoke path.
        r = c.post(
            "/ai-market/v2/invoke",
            json={
                "capability_id": "atlas.watchbox.check@v1",
                "input": {"watchbox_id": "wb-victim"},
            },
        )
        assert r.status_code == 401

    def test_an_ephemeral_bbox_check_stays_open(self, anon):
        """Only STORED watchboxes are tenant resources; ad-hoc bbox checks are the SKU."""
        c, _ = anon
        r = c.post(
            "/ai-market/v2/invoke",
            json={
                "capability_id": "atlas.watchbox.check@v1",
                "input": {
                    "west": -10, "south": 35, "east": 30, "north": 60,
                    "layers": ["fire"],
                },
            },
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_the_owner_token_works_as_an_invoke_input_field(self, anon):
        """The hub forwards the invoke body, not our headers."""
        c, store = anon
        created = store.create(
            west=-10, south=35, east=30, north=60, layers=["fire"], watchbox_id="wb-hub",
        )
        r = c.post(
            "/ai-market/v2/invoke",
            json={
                "capability_id": "atlas.watchbox.check@v1",
                "input": {
                    "watchbox_id": "wb-hub",
                    "owner_token": created["owner_token"],
                },
            },
        )
        assert r.status_code == 200
        payload = r.json()
        assert payload["ok"] is True
        # The credential must not survive into the signed receipt.
        assert created["owner_token"] not in json.dumps(payload, default=str)
        assert "owner_token" not in json.dumps(payload, default=str)


class TestSelfServeSignup:
    def test_self_serve_is_off_by_default(self, anon):
        c, _ = anon
        assert c.post("/api/v1/watchboxes", json={
            "west": 1, "south": 1, "east": 2, "north": 2, "layers": ["fire"],
        }).status_code == 401

    def test_self_serve_when_enabled_hands_back_an_owner_token(self, tmp_path, monkeypatch):
        app, _ = _wire(tmp_path, monkeypatch, ATLAS_WATCHBOX_OPEN_SIGNUP="1")
        with TestClient(app) as c:
            out = _create(c, id="wb-selfserve")
            token = out["owner_token"]
            h = {"X-Atlas-Watchbox-Token": token}
            assert c.get("/api/v1/watchboxes/wb-selfserve", headers=h).status_code == 200
            # …and it is still not a key to anyone else's registry.
            assert c.get("/api/v1/watchboxes", headers=h).json()["scope"] == "owner"

    def test_self_serve_is_bounded(self, tmp_path, monkeypatch):
        app, _ = _wire(
            tmp_path, monkeypatch,
            ATLAS_WATCHBOX_OPEN_SIGNUP="1", ATLAS_WATCHBOX_SELF_SERVE_MAX="1",
        )
        with TestClient(app) as c:
            _create(c, id="wb-first")
            r = c.post("/api/v1/watchboxes", json={
                "west": 1, "south": 1, "east": 2, "north": 2, "layers": ["fire"],
            })
            assert r.status_code == 429
