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
    "/api/v1/products/smoke-operations": {"lat": 37.7749, "lon": -122.4194},
    "/api/v1/products/geomag-window": {"lat": 40.0, "lon": -105.0},
    "/api/v1/products/pv-irradiance-record": {"lat": 52.5, "lon": 13.4},
    "/api/v1/products/route-integrity": {"route": [[24.94, 60.17], [18.07, 59.33]]},
    "/api/v1/products/observability-attest": {"lat": 35.22, "lon": -97.44},
    "/api/v1/products/mesh-sample": {"mesh_id": "ee-wx"},
    "/api/v1/products/field-consensus": {"mesh_id": "ee-wx"},
    "/api/v1/products/field-posterior": {"mesh_id": "ee-wx", "lat": 58.6, "lon": 25.0},
    "/api/v1/products/field-shape": {"mesh_id": "ee-wx"},
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
        and "POST" in (getattr(r, "methods", None) or set())
    }
    assert routes == set(PRODUCT_BODIES), (
        "product routes not covered by the metering test: "
        f"{sorted(routes - set(PRODUCT_BODIES))}"
    )


def test_no_priced_sku_is_served_by_a_route_that_never_calls_the_gate():
    """Bound the priced surface by WHAT a route produces, not by where the route lives.

    Two guards failed here before this one worked.

    The inventory guard above scopes itself to `/api/v1/products/`, so
    `POST /api/v1/watchboxes/{id}/check` — which returned `atlas.watchbox.check@v1` ($0.02)
    with the same signed receipt as its metered twin and never touched the allowance — was
    invisible to it by construction.

    The first replacement searched each handler for a QUOTED priced capability id. It passed
    with the fix removed, because the unmetered route named its SKU only in its docstring, in
    backticks. A guard that a regression walks straight through is worse than no guard.

    So: invert `products.invoke_product`'s dispatch table to learn which product FUNCTION
    emits which capability id, then require any route that calls a priced one to go through
    `_metered_product`. A route cannot serve the SKU without calling its producer.
    """
    import inspect
    import re

    from atlas import products as products_mod
    from atlas.main import app

    dispatch = dict(
        re.findall(
            r'if cap == "([^"]+)":\s*\n\s*return (\w+)\(',
            inspect.getsource(products_mod.invoke_product),
        )
    )
    assert dispatch, "could not read invoke_product's dispatch table — this guard is blind"
    priced_producers = {
        fn: cap_id
        for cap_id, fn in dispatch.items()
        if float((products_mod.CAP_BY_ID.get(cap_id) or {}).get("price_per_call_usd") or 0.0) > 0
    }
    assert priced_producers, "no priced producers resolved — the guard would pass vacuously"

    offenders = []
    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        path = getattr(route, "path", "")
        if endpoint is None or not path.startswith("/api/"):
            continue
        try:
            src = inspect.getsource(endpoint)
        except (OSError, TypeError):
            continue
        if "_metered_product" in src:
            continue
        called = sorted(
            {
                cap_id
                for fn, cap_id in priced_producers.items()
                if re.search(r"\bproducts_mod\.%s\s*\(" % re.escape(fn), src)
            }
        )
        if called:
            offenders.append((path, called))
    assert not offenders, (
        "these routes produce a priced SKU without going through the allowance: "
        f"{offenders}"
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


# --- 2026-09 re-audit: the gate and the dispatcher must agree on what an id IS -------
#
# `payment_gate.price_of()` looked `capability_id` up in CAP_BY_ID verbatim while
# `products.invoke_product()` stripped it first. So `"atlas.route.integrity@v1 "` priced at
# $0.00 — and `reserve()` returns None for anything priced at or below zero, by design —
# while the dispatcher normalised the same string and served the full priced product. One
# trailing space bought every priced SKU for free, on the protocol surface, unauthenticated.
#
# The same exact-equality mismatch also skipped the `== "atlas.watchbox.check@v1"` branch in
# `aimarket_invoke`, which is the ONLY place the per-watchbox owner token is enforced there,
# so a stranger could read another tenant's stored bbox and layers.

_WHITESPACE_VARIANTS = ("{id} ", " {id}", "\t{id}", "{id}\n", " {id}\t\n")


@pytest.mark.parametrize("shape", _WHITESPACE_VARIANTS)
def test_price_of_is_not_defeated_by_surrounding_whitespace(shape):
    """The gate must price the capability the dispatcher will actually run."""
    from atlas import payment_gate, products as products_mod

    priced = [
        cap_id
        for cap_id, cap in products_mod.CAP_BY_ID.items()
        if float(cap.get("price_per_call_usd") or 0.0) > 0
    ]
    assert priced, "no priced SKUs found — the fixture, not the guard, is wrong"
    for cap_id in priced:
        exact = payment_gate.price_of(cap_id)
        assert payment_gate.price_of(shape.format(id=cap_id)) == exact, (
            f"{cap_id!r} prices at {exact} but {shape.format(id=cap_id)!r} does not"
        )


@pytest.mark.parametrize("shape", _WHITESPACE_VARIANTS)
def test_reserve_still_charges_a_whitespace_padded_capability_id(shape):
    """`reserve` short-circuits on price <= 0, so a mispriced id is an unmetered id."""
    from atlas import payment_gate

    cap_id = "atlas.route.integrity@v1"
    assert payment_gate.price_of(shape.format(id=cap_id)) > 0


def test_invoke_normalises_capability_id_before_any_gate_reads_it():
    """Normalise at the boundary: every downstream comparison sees the same string.

    Checked on the model rather than through a request, because the product itself needs live
    upstream sensor data in this environment — the property under test is the normalisation,
    which is exactly what the two code paths disagreed about.
    """
    from atlas.main import ProductInvokeBody

    for shape in _WHITESPACE_VARIANTS:
        body = ProductInvokeBody(capability_id=shape.format(id="atlas.route.integrity@v1"))
        assert body.capability_id == "atlas.route.integrity@v1", (
            f"{shape!r} survived model validation as {body.capability_id!r}; "
            "the payment gate and the dispatcher will disagree about it"
        )


def test_watchbox_owner_token_branch_cannot_be_stepped_over_by_whitespace():
    """The owner-token branch is an exact `==`; normalisation is what keeps it reachable."""
    from atlas.main import ProductInvokeBody

    body = ProductInvokeBody(
        capability_id="atlas.watchbox.check@v1 ", input={"watchbox_id": "wb-victim-001"}
    )
    assert body.capability_id == "atlas.watchbox.check@v1"
