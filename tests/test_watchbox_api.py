"""ATLAS watchbox HTTP API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas import watchboxes as wb_mod


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    store = wb_mod.WatchboxStore(path=tmp_path / "watchboxes.json")
    monkeypatch.setattr(wb_mod, "STORE", store)
    from atlas import products as products_mod

    monkeypatch.setattr(products_mod, "STORE", store)
    from atlas.main import app

    with TestClient(app) as c:
        yield c, store


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

    deleted = c.delete("/api/v1/watchboxes/wb-api-01")
    assert deleted.status_code == 200
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
