"""Every route that serves a priced product must go through the allowance.

ATLAS published ``price_per_call_usd`` and a manifest saying priced capabilities are
metered, while five REST endpoints served byte-identical results with no meter at all:
``POST /api/v1/products/situation-brief`` returned the same ``capability_id`` and the same
signed evidence as the priced SKU, and eight such calls left **no row in the ledger**. The
price list was bypassable by anyone who read the OpenAPI, which made the published claim
untrue rather than merely incomplete.

The test that matters here is the *inventory* one: it derives the set of routes to check
from the app itself, so a sixth product endpoint added later cannot quietly reintroduce the
bypass — the usual failure mode, since each endpoint is a plausible small addition on its
own.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A live app with enforcement on and a two-call allowance."""
    monkeypatch.setenv("ATLAS_PAYMENT_ENFORCED", "1")
    monkeypatch.setenv("ATLAS_TRIAL_DB_PATH", str(tmp_path / "trials.db"))
    monkeypatch.setenv("ATLAS_TRIAL_WINDOW", "lifetime")
    monkeypatch.setenv("ATLAS_TRIAL_MAX_PER_CALLER", "2")
    from atlas import payment_gate

    importlib.reload(payment_gate)
    from atlas.main import app

    return TestClient(app)


PRODUCT_BODIES = {
    "/api/v1/products/situation-brief": {"west": -20, "south": -40, "east": 60, "north": 40},
    "/api/v1/products/fire-weather": {"west": -20, "south": -40, "east": 60, "north": 40},
    "/api/v1/products/nearest": {"lat": 60.17, "lon": 24.94},
    "/api/v1/products/point": {"point_id": "does-not-exist"},
    "/api/v1/products/gnss-degradation": {"lat": 60.17, "lon": 24.94},
}


def test_every_product_route_is_covered_by_this_test():
    """Inventory guard: a new product endpoint must be added here, or this fails.

    Without it, the bypass returns the next time someone adds a sixth SKU — the endpoints
    are individually unremarkable, which is exactly how the first five slipped through.
    """
    from atlas.main import app

    routes = {
        r.path
        for r in app.routes
        if getattr(r, "path", "").startswith("/api/v1/products/")
        and getattr(r, "path", "") != "/api/v1/products"
    }
    assert routes == set(PRODUCT_BODIES), (
        "product routes not covered by the metering test: "
        f"{sorted(routes - set(PRODUCT_BODIES))}"
    )


@pytest.mark.parametrize("path", sorted(PRODUCT_BODIES))
def test_every_product_route_consults_the_allowance(client, monkeypatch, path):
    """Wiring, checked directly: the route must ask the gate, naming its own SKU.

    Deliberately not "hammer it until it 402s" — that was the first version of this test and
    it failed on all five routes for the *right* reason: a test environment has no sensor
    readings, so every product refuses, and refusals are correctly free. Depletion is
    covered separately below with a product that actually delivers.
    """
    from atlas import payment_gate

    asked: list[str] = []
    real_reserve = payment_gate.reserve
    monkeypatch.setattr(
        payment_gate,
        "reserve",
        lambda cap, headers, host="": asked.append(cap) or real_reserve(cap, headers, host),
    )

    visitor = f"wiring-probe-{path.rsplit('/', 1)[-1]}"
    try:
        client.post(path, json=PRODUCT_BODIES[path], headers={"X-AIMarket-Sandbox-Visitor": visitor})
    except Exception:
        # Some products need an open GAIA client this box does not have, so they raise
        # rather than refuse. That is fine here and worth exercising: the reservation is
        # taken before the work, so the exception path is precisely where a missing release
        # would silently charge a caller for a crash. Asserted below.
        pass

    assert asked, f"{path} served a priced product without consulting the allowance"
    assert asked[0].startswith("atlas."), asked
    assert payment_gate.price_of(asked[0]) > 0, (
        f"{path} reserved against {asked[0]}, which is not a priced SKU — the wrong "
        "capability id means the wrong price and the wrong meter"
    )
    assert payment_gate.quota(f"v:{visitor}")["used"] == 0, (
        f"{path} kept the reservation for a call that delivered nothing"
    )


def test_a_delivering_route_depletes_the_allowance(client, monkeypatch):
    """The other half: when the product does return data, the limit binds.

    ``nearest`` is stubbed to deliver because a test box has no LIVE readings; the point is
    the accounting around it, not the geodesy.
    """
    from atlas import payment_gate, products as products_mod

    monkeypatch.setattr(
        products_mod, "nearest_read", lambda payload, stations: {"ok": True, "matches": []}
    )
    headers = {"X-AIMarket-Sandbox-Visitor": "depletion-probe-01"}
    statuses = []
    for _ in range(5):
        r = client.post("/api/v1/products/nearest", json=PRODUCT_BODIES["/api/v1/products/nearest"], headers=headers)
        statuses.append(r.status_code)
        if r.status_code == 402:
            detail = r.json()["detail"]
            assert detail["error"] == "payment_required"
            assert detail["price_per_call_usd"] > 0
            break
    assert 402 in statuses, f"an allowance of 2 admitted {statuses}"
    assert statuses.count(200) == 2, statuses


def test_a_refusal_on_the_rest_surface_is_not_billed(client):
    """Same fairness rule as the protocol surface — a cold fleet must not cost anything.

    ``point`` with an unknown id is the cheapest deterministic refusal available, and it
    stands in for the common case: after a redeploy every read refuses until the sensor
    fleet warms.
    """
    from atlas import payment_gate

    headers = {"X-AIMarket-Sandbox-Visitor": "refusal-probe-rest"}
    for _ in range(5):
        client.post("/api/v1/products/point", json={"point_id": "nope"}, headers=headers)

    used = payment_gate.quota("v:refusal-probe-rest")["used"]
    assert used == 0, f"refusals on the REST surface were billed ({used} spent)"


def test_the_meter_is_off_by_default(tmp_path, monkeypatch):
    """Enforcement stays an operator decision, so an unconfigured deploy changes nothing."""
    monkeypatch.delenv("ATLAS_PAYMENT_ENFORCED", raising=False)
    monkeypatch.setenv("ATLAS_TRIAL_DB_PATH", str(tmp_path / "off.db"))
    from atlas import payment_gate

    importlib.reload(payment_gate)
    assert payment_gate.enforced() is False

    from atlas.main import app

    c = TestClient(app)
    headers = {"X-AIMarket-Sandbox-Visitor": "gate-off-probe"}
    for _ in range(8):
        r = c.post(
            "/api/v1/products/situation-brief",
            json={"west": -20, "south": -40, "east": 60, "north": 40},
            headers=headers,
        )
        assert r.status_code != 402
