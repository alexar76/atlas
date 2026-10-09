"""A price nobody can pay is not a price.

``payment_gate`` made ATLAS charge; it could not make ATLAS *paid*. The free allowance is
five calls an hour per caller, the 402 pointed at a hub payment channel, and the hub's own
call to ATLAS lands on the same anonymous allowance — so the measured ceiling for a desk
selling a paid plan on ATLAS evidence was five runs an hour no matter how it connected.
These cover the rail that removes the ceiling, and every way it must not misfire.

The properties that matter here are about money rather than plumbing: a paying caller must
not also be rate-limited as a trialist, a refusal must not be billed, a crashed request must
not freeze somebody's balance, and a ledger that cannot be read must refuse the call instead
of serving a paid product it cannot record.
"""

from __future__ import annotations

import importlib
import sqlite3
import threading

import pytest

#: $0.02 — the cheapest priced SKU, so a small balance covers a long sequence.
PRICED = "atlas.watchbox.check@v1"
PRICE = 0.02


class _Headers(dict):
    """A header mapping shaped like Starlette's: case-insensitive, "" for absent."""

    def get(self, key, default=""):  # type: ignore[override]
        return dict.get(self, key, dict.get(self, str(key).lower(), default))


def _env(tmp_path, monkeypatch, *, credits_enabled="1", allowance="2"):
    monkeypatch.setenv("ATLAS_PAYMENT_ENFORCED", "1")
    monkeypatch.setenv("ATLAS_TRIAL_DB_PATH", str(tmp_path / "trials.db"))
    monkeypatch.setenv("ATLAS_TRIAL_POLICY_PATH", str(tmp_path / "policy.json"))
    monkeypatch.setenv("ATLAS_TRIAL_WINDOW", "lifetime")
    monkeypatch.setenv("ATLAS_TRIAL_MAX_PER_CALLER", allowance)
    monkeypatch.setenv("ATLAS_CREDITS_DB_PATH", str(tmp_path / "credits.db"))
    if credits_enabled is None:
        monkeypatch.delenv("ATLAS_CREDITS_ENABLED", raising=False)
    else:
        monkeypatch.setenv("ATLAS_CREDITS_ENABLED", credits_enabled)
    credits = importlib.reload(importlib.import_module("atlas.credits"))
    gate = importlib.reload(importlib.import_module("atlas.payment_gate"))
    return gate, credits


@pytest.fixture()
def rail(tmp_path, monkeypatch):
    return _env(tmp_path, monkeypatch)


def _buy(gate, key, *, delivered=True, capability=PRICED, host="203.0.113.7"):
    """One full invoke: reserve, then resolve it the way the invoke path does."""
    headers = _Headers({"X-API-Key": key} if key else {})
    due = gate.reserve(capability, headers, host)
    if due is not None:
        return due
    result = {"ok": True} if delivered else {"ok": False, "refuse_reason": "no coverage"}
    gate.settle(capability, headers, host, result=result)
    return None


def _caps():
    from atlas import products as products_mod

    return products_mod.CAP_BY_ID


def _backdate_hold(credits, receipt_id: str, delta: str) -> None:
    conn = sqlite3.connect(credits.db_path())
    with conn:
        conn.execute(
            "UPDATE credit_holds SET created_at = datetime('now', ?) WHERE receipt_id = ?",
            (delta, receipt_id),
        )
    conn.close()


# ── the ceiling this rail exists to remove ───────────────────────────────


def test_a_credited_account_is_not_capped_by_the_free_allowance(rail):
    """The whole point: eight paid calls where the trial would have allowed two.

    Also asserts the allowance is *untouched* rather than merely sufficient. Charging a
    paying buyer AND spending its trial would leave it capped an hour later for reasons no
    receipt explains — the failure this replaced, seen from one layer up.
    """
    gate, credits = rail
    account = credits.create_account(label="tideline", grant_usd=1.0)

    for i in range(8):
        assert _buy(gate, account["api_key"]) is None, f"call {i + 1} was refused"

    assert credits.balance_usd(account["account_id"]) == pytest.approx(1.0 - 8 * PRICE)
    assert gate.quota("ip:203.0.113.7")["used"] == 0, (
        "a paying caller also spent the anonymous trial, so it stays rate-limited"
    )


def test_a_refusal_is_not_billed_on_the_credit_rail(rail):
    """A cold fleet refuses; the buyer must not pay for the operator's restart."""
    gate, credits = rail
    account = credits.create_account(grant_usd=0.5)

    for _ in range(5):
        assert _buy(gate, account["api_key"], delivered=False) is None

    assert credits.balance_usd(account["account_id"]) == pytest.approx(0.5)
    row = credits.account(account["account_id"])
    assert row["spent_usd"] == 0.0
    assert row["held_usd"] == 0.0, "a released reservation is still frozen"


def test_a_free_sku_is_never_charged_even_with_a_credited_key(rail):
    """Price 0 means free for everyone. Debiting here would invent a price."""
    gate, credits = rail
    account = credits.create_account(grant_usd=0.5)
    free = next(
        (cap_id for cap_id, cap in _caps().items()
         if float(cap.get("price_per_call_usd") or 0.0) <= 0),
        None,
    )
    if free is None:
        pytest.skip("no free capability published")
    assert _buy(gate, account["api_key"], capability=free) is None
    assert credits.balance_usd(account["account_id"]) == pytest.approx(0.5)


def test_the_rail_off_leaves_a_keyed_caller_exactly_where_it_was(tmp_path, monkeypatch):
    """Switching this on is an operator decision; an unconfigured node is unchanged."""
    gate, credits = _env(tmp_path, monkeypatch, credits_enabled=None)
    assert credits.enabled() is False

    assert _buy(gate, "atls_whatever") is None
    assert gate.quota("ip:203.0.113.7")["used"] == 1, (
        "with the rail off a keyed caller must still be metered as a trialist"
    )


# ── what a caller is told when it cannot pay ─────────────────────────────


def test_an_unrecognised_key_falls_back_to_the_allowance_and_says_so(rail):
    """The bug this rail was built to end, made visible.

    Four desks sold paid plans against the anonymous allowance for weeks because a key that
    is not an account here looked, from the outside, exactly like a key that had run out of
    money. Serving from the free tier keeps unrelated fleet callers working; the 402 has to
    say WHICH of the two happened.
    """
    gate, _credits = rail
    junk = "atls_not-an-account-here"

    assert _buy(gate, junk) is None
    assert _buy(gate, junk) is None
    body = _buy(gate, junk)

    assert body is not None and body["error"] == "payment_required"
    assert body["credit"] == {"recognized": False, "key_supplied": True}


def test_an_empty_account_falls_back_and_the_402_names_the_balance(rail):
    """A known buyer that ran out is told the balance, not just "payment required"."""
    gate, credits = rail
    account = credits.create_account(label="empty", grant_usd=0.0)

    assert _buy(gate, account["api_key"]) is None
    assert _buy(gate, account["api_key"]) is None
    body = _buy(gate, account["api_key"])

    assert body is not None
    assert body["credit"]["recognized"] is True
    assert body["credit"]["account_id"] == account["account_id"]
    assert body["credit"]["balance_usd"] == 0.0
    assert body["credit"]["needed_usd"] == pytest.approx(PRICE)


def test_a_disabled_account_cannot_spend_its_balance(rail):
    """Disabling is the answer to a leaked key: no new debits, balance untouched."""
    gate, credits = rail
    account = credits.create_account(grant_usd=1.0)
    credits.set_status(account["account_id"], "disabled")

    _buy(gate, account["api_key"])

    assert credits.balance_usd(account["account_id"]) == pytest.approx(1.0)


def test_the_402_advertises_the_paid_rail_when_it_is_on(rail):
    gate, _credits = rail
    body = gate.payment_required_body(
        PRICED, {"max": 2, "used": 2, "quota_window": "lifetime"}
    )
    assert any("X-API-Key" in step for step in body["how_to_continue"])


def test_the_manifest_advertises_the_rail_before_a_buyer_commits(rail):
    """A buyer decides whether to build on ATLAS from the manifest, not from a 402."""
    gate, credits = rail
    market_mod = importlib.reload(importlib.import_module("atlas.market"))

    terms = market_mod.well_known()["payment"]
    assert terms["credits"]["enabled"] is True
    assert terms["credits"]["key_header"] == credits.KEY_HEADER
    assert gate.enforced() is True


# ── failure modes that must not cost anybody money ───────────────────────


def test_a_broken_ledger_refuses_instead_of_serving_a_paid_product(rail, monkeypatch):
    """The free meter fails OPEN by design; a money ledger must not.

    Serving the call would hand over a paid product with no row to reconstruct the debit
    from. Refusing is recoverable — the caller retries and nothing was charged.
    """
    gate, credits = rail
    account = credits.create_account(grant_usd=1.0)

    def _boom(*_a, **_kw):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(credits, "resolve", _boom)
    body = _buy(gate, account["api_key"])

    assert body is not None and body["error"] == "credit_ledger_unavailable"
    assert body["retryable"] is True
    assert gate.quota("ip:203.0.113.7")["used"] == 0, (
        "a ledger failure spent the caller's free allowance as well"
    )


def test_concurrent_invokes_cannot_overdraw_one_account(rail):
    """Twelve callers, three calls' worth of credit, exactly three charges.

    The hold is one conditional UPDATE for this reason: a read-then-write lets every
    concurrent invoke observe the same sufficient balance and discover the shortfall only
    after the product has already done billable work.
    """
    _gate, credits = rail
    account = credits.create_account(grant_usd=3 * PRICE)
    results: list[dict] = []
    lock = threading.Lock()

    def worker(n: int) -> None:
        outcome = credits.hold(account["account_id"], PRICE, f"rcpt_race_{n}", PRICED)
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    granted = [r for r in results if not r.get("error")]
    assert len(granted) == 3, f"3 calls of credit admitted {len(granted)} holds"
    row = credits.account(account["account_id"])
    assert row["balance_usd"] == 0.0
    assert row["held_usd"] == pytest.approx(3 * PRICE)


def test_a_dead_request_does_not_freeze_the_balance(rail):
    """A killed worker leaves a hold nobody resolves — money the buyer can neither spend
    nor reclaim, and the only symptom is a balance that shrinks on every restart."""
    _gate, credits = rail
    account = credits.create_account(grant_usd=1.0)
    credits.hold(account["account_id"], PRICE, "rcpt_orphan", PRICED)
    _backdate_hold(credits, "rcpt_orphan", "-2 hours")

    assert credits.expire_stale_holds() == 1
    row = credits.account(account["account_id"])
    assert row["balance_usd"] == pytest.approx(1.0)
    assert row["held_usd"] == 0.0
    assert row["spent_usd"] == 0.0, "a stale hold was captured instead of released"


def test_a_live_reservation_is_not_swept_out_from_under_its_request(rail):
    """The sweeper must only touch holds old enough to be dead, or it would release a
    reservation the running request is about to capture — a served call, nobody charged."""
    _gate, credits = rail
    account = credits.create_account(grant_usd=1.0)
    credits.hold(account["account_id"], PRICE, "rcpt_inflight", PRICED)

    assert credits.expire_stale_holds() == 0
    assert credits.account(account["account_id"])["held_usd"] == pytest.approx(PRICE)


def test_a_settled_invoke_cannot_be_charged_twice(rail):
    """Capture is idempotent, so a retry or a late exception is not a second bill."""
    _gate, credits = rail
    account = credits.create_account(grant_usd=1.0)
    credits.hold(account["account_id"], PRICE, "rcpt_once", PRICED)

    assert credits.capture("rcpt_once")["captured_usd"] == pytest.approx(PRICE)
    assert credits.capture("rcpt_once")["captured_usd"] == 0.0
    assert credits.release("rcpt_once")["released_usd"] == 0.0

    row = credits.account(account["account_id"])
    assert row["spent_usd"] == pytest.approx(PRICE)
    assert row["balance_usd"] == pytest.approx(1.0 - PRICE)


def test_no_money_is_created_or_destroyed(rail):
    """Every column has to add up after a mixed run: what was granted is either still
    available, spent, or held — never lost, never doubled."""
    gate, credits = rail
    account = credits.create_account(grant_usd=1.0)

    for _ in range(6):
        _buy(gate, account["api_key"])
    for _ in range(3):
        _buy(gate, account["api_key"], delivered=False)

    row = credits.account(account["account_id"])
    assert row["balance_usd"] + row["spent_usd"] + row["held_usd"] == pytest.approx(
        row["granted_usd"]
    )
    assert row["spent_usd"] == pytest.approx(6 * PRICE)


def test_a_top_up_with_a_reference_credits_once(rail):
    """The natural reaction to a timed-out top-up is to run it again."""
    _gate, credits = rail
    account = credits.create_account(grant_usd=0.0)

    first = credits.topup(account["account_id"], 25.0, reference="inv-2026-09-12-a")
    second = credits.topup(account["account_id"], 25.0, reference="inv-2026-09-12-a")

    assert first["credited_usd"] == pytest.approx(25.0)
    assert second["idempotent_replay"] is True
    assert credits.balance_usd(account["account_id"]) == pytest.approx(25.0)


def test_a_reference_cannot_be_reused_for_a_different_amount(rail):
    _gate, credits = rail
    account = credits.create_account(grant_usd=0.0)
    credits.topup(account["account_id"], 5.0, reference="inv-1")

    clash = credits.topup(account["account_id"], 50.0, reference="inv-1")

    assert "error" in clash
    assert credits.balance_usd(account["account_id"]) == pytest.approx(5.0)


def test_a_key_is_never_stored_in_the_clear(rail):
    """A stolen ledger file must not be a stolen wallet."""
    _gate, credits = rail
    account = credits.create_account(grant_usd=1.0)

    raw = credits.db_path().read_bytes()
    assert account["api_key"].encode() not in raw
    assert credits.hash_key(account["api_key"]).encode() in raw


def test_the_published_price_survives_the_round_trip_exactly(rail):
    """Millicents, not cents: $0.02 must debit as $0.02 and not round to a whole cent."""
    _gate, credits = rail
    account = credits.create_account(grant_usd=0.1)
    credits.hold(account["account_id"], PRICE, "rcpt_exact", PRICED)
    credits.capture("rcpt_exact")

    assert credits.account(account["account_id"])["spent_usd"] == 0.02


# ── boot guards ──────────────────────────────────────────────────────────


def test_a_node_refuses_to_take_prepaid_money_it_would_forget(tmp_path, monkeypatch):
    """A relative path resolves inside the image, so `up -d --build` deletes every balance.

    Refusing to boot is the only honest option: the alternative is a node that took money,
    lost the record, and cannot tell a wiped account from a forged key.
    """
    monkeypatch.setenv("ATLAS_CREDITS_ENABLED", "1")
    monkeypatch.setenv("ATLAS_CREDITS_DB_PATH", "data/atlas_credits.db")
    credits = importlib.reload(importlib.import_module("atlas.credits"))

    with pytest.raises(RuntimeError, match="mounted volume"):
        credits.assert_durable_ledger()


def test_the_boot_guard_only_binds_when_the_rail_is_on(tmp_path, monkeypatch):
    """A node that takes no prepaid money has no balances to protect and must still start."""
    monkeypatch.delenv("ATLAS_CREDITS_ENABLED", raising=False)
    monkeypatch.setenv("ATLAS_CREDITS_DB_PATH", "data/atlas_credits.db")
    credits = importlib.reload(importlib.import_module("atlas.credits"))

    credits.assert_durable_ledger()


# ── telling the buyer before it runs out ─────────────────────────────────


def test_a_charged_call_reports_the_price_and_what_is_left(rail):
    """A buyer must be able to watch its balance without asking a second question.

    An unattended desk that only learns it is empty by being refused learns it while a
    customer's run is failing — the balance has to arrive with the call that spent it.
    """
    gate, credits = rail
    account = credits.create_account(grant_usd=5.0)

    _buy(gate, account["api_key"])
    headers = gate.credit_headers()

    assert headers[credits.CHARGED_HEADER].startswith("0.02")
    assert float(headers[credits.BALANCE_HEADER]) == pytest.approx(4.98)
    assert credits.LOW_BALANCE_HEADER not in headers, "a healthy balance was flagged as low"


def test_a_refused_call_reports_a_zero_charge(rail):
    """Quoting the price on a refusal would tell the buyer it paid for nothing."""
    gate, credits = rail
    account = credits.create_account(grant_usd=1.0)

    _buy(gate, account["api_key"], delivered=False)
    headers = gate.credit_headers()

    assert float(headers[credits.CHARGED_HEADER]) == 0.0
    assert float(headers[credits.BALANCE_HEADER]) == pytest.approx(1.0)


def test_an_unpaid_call_gets_no_credit_headers(rail):
    """A free-allowance call was not charged, so there is no charge to report."""
    gate, _credits = rail

    _buy(gate, "")
    assert gate.credit_headers() == {}


def test_a_thinning_balance_is_flagged_to_the_buyer_and_the_operator(rail, monkeypatch, caplog):
    """Warn while there is still time to top up, and say it in calls, not just dollars."""
    gate, credits = rail
    monkeypatch.setenv("ATLAS_CREDITS_LOW_BALANCE_USD", "0.10")
    account = credits.create_account(grant_usd=0.12)

    with caplog.at_level("WARNING"):
        _buy(gate, account["api_key"])

    assert gate.credit_headers()[credits.LOW_BALANCE_HEADER] == "1"
    assert credits.account(account["account_id"])["low_balance"] is True
    assert any("top it up" in r.getMessage() for r in caplog.records), caplog.text


def test_the_low_balance_warning_does_not_repeat_on_every_call(rail, monkeypatch, caplog):
    """A busy desk would print it hundreds of times an hour and bury everything else."""
    gate, credits = rail
    monkeypatch.setenv("ATLAS_CREDITS_LOW_BALANCE_USD", "1.0")
    account = credits.create_account(grant_usd=0.5)

    with caplog.at_level("WARNING"):
        for _ in range(5):
            _buy(gate, account["api_key"])

    warnings = [r for r in caplog.records if "top it up" in (r.msg or "")]
    assert len(warnings) == 1, f"five calls produced {len(warnings)} identical warnings"


def test_headers_reach_the_buyer_over_http(http):
    """The whole point is that a real client sees them on a real response."""
    client, credits = http
    account = credits.create_account(grant_usd=1.0)

    r = client.post(
        "/ai-market/v2/invoke",
        json={
            "capability_id": "atlas.watchbox.check@v1",
            "input": {"west": -1.0, "south": 51.3, "east": 0.2, "north": 51.6,
                      "layers": ["flood"]},
        },
        headers={"X-API-Key": account["api_key"]},
    )

    # The product itself may refuse on a box with no sensor readings; either way the charge
    # has to be reported, and a refusal has to report zero.
    assert credits.CHARGED_HEADER in r.headers, dict(r.headers)
    assert float(r.headers[credits.BALANCE_HEADER]) <= 1.0


def test_no_compose_entry_shadows_a_secret_with_an_empty_default():
    """A configured secret must reach the container, not be overwritten by "".

    Found in production: ``ATLAS_OPERATOR_TOKEN: ${ATLAS_OPERATOR_TOKEN:-}`` sat in
    ``environment:``, which OVERRIDES ``env_file``, and compose interpolates ``${...}`` from
    the shell or from the ``.env`` beside the compose file — never from the ``../.env`` the
    operator had actually set. So a 48-character token was replaced by an empty string on
    every deploy and ``_operator_ok`` refused everyone, while every file involved looked
    correctly configured. Credit issuance sits behind that same check, so this guard is part
    of the paid rail rather than a tidiness rule.
    """
    import re
    from pathlib import Path

    compose = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    offenders = [
        line.strip()
        for line in compose.read_text(encoding="utf-8").splitlines()
        if re.search(r":\s*\$\{[A-Z0-9_]+:-\}\s*$", line)
    ]
    assert not offenders, (
        "these compose entries override env_file with an empty string, so a value set in "
        f"../.env can never reach the container: {offenders}"
    )


# ── the operator's surface ───────────────────────────────────────────────

OPERATOR_TOKEN = "operator-token-for-tests"


@pytest.fixture()
def http(rail, monkeypatch):
    """A live app with the rail on and an operator token configured."""
    from fastapi.testclient import TestClient

    import atlas.main as main_mod

    monkeypatch.setattr(main_mod.settings, "operator_token", OPERATOR_TOKEN)
    with TestClient(main_mod.app) as client:
        yield client, rail[1]


def test_issuing_an_account_needs_the_operator_token(http):
    """Minting credit is minting a liability. It is not a public route."""
    client, _credits = http

    anonymous = client.post("/ai-market/v2/accounts", json={"label": "stranger"})
    assert anonymous.status_code == 401

    issued = client.post(
        "/ai-market/v2/accounts",
        json={"label": "tideline", "grant_usd": 25.0},
        headers={"X-Atlas-Token": OPERATOR_TOKEN},
    )
    assert issued.status_code == 200
    body = issued.json()
    assert body["api_key"].startswith("atls_")
    assert body["balance_usd"] == 25.0


def test_a_buyer_can_read_its_own_balance_and_nothing_else(http):
    """An unattended buyer that cannot see its balance only learns it is empty by failing
    a customer's run."""
    client, credits = http
    account = credits.create_account(label="seamark", grant_usd=3.0)

    mine = client.get("/ai-market/v2/accounts/me", headers={"X-API-Key": account["api_key"]})
    assert mine.status_code == 200
    assert mine.json()["account_id"] == account["account_id"]
    assert mine.json()["balance_usd"] == 3.0

    assert client.get("/ai-market/v2/accounts/me").status_code == 401
    # Same answer for an unknown key and a disabled one: this route must not become an
    # oracle for which keys exist.
    unknown = client.get("/ai-market/v2/accounts/me", headers={"X-API-Key": "atls_nope"})
    assert unknown.status_code == 404


def test_topping_up_over_http_is_replay_safe(http):
    client, credits = http
    account = credits.create_account(grant_usd=0.0)
    payload = {"amount_usd": 10.0, "reference": "wire-4471"}
    headers = {"X-Atlas-Token": OPERATOR_TOKEN}
    url = f"/ai-market/v2/accounts/{account['account_id']}/topup"

    assert client.post(url, json=payload, headers=headers).status_code == 200
    replay = client.post(url, json=payload, headers=headers)

    assert replay.status_code == 200 and replay.json()["idempotent_replay"] is True
    assert credits.balance_usd(account["account_id"]) == pytest.approx(10.0)


def test_credit_totals_are_operator_only_and_name_the_liability(http):
    client, credits = http
    credits.create_account(grant_usd=4.0)

    assert client.get("/ai-market/v2/credits/stats").status_code == 401
    stats = client.get(
        "/ai-market/v2/credits/stats", headers={"X-Atlas-Token": OPERATOR_TOKEN}
    ).json()

    assert stats["outstanding_credit_usd"] == pytest.approx(4.0)
    assert stats["credits_earned_usd"] == 0.0


def test_accounts_can_be_issued_before_the_rail_is_switched_on(tmp_path, monkeypatch):
    """The rollout order that avoids a gap: mint accounts, hand out keys, THEN enable.

    Enabling first would put every buyer holding a not-yet-issued key onto the anonymous
    allowance at the exact moment it started expecting to be charged.
    """
    from fastapi.testclient import TestClient

    _gate, credits = _env(tmp_path, monkeypatch, credits_enabled=None)
    import atlas.main as main_mod

    monkeypatch.setattr(main_mod.settings, "operator_token", OPERATOR_TOKEN)
    with TestClient(main_mod.app) as client:
        issued = client.post(
            "/ai-market/v2/accounts",
            json={"label": "prepared", "grant_usd": 1.0},
            headers={"X-Atlas-Token": OPERATOR_TOKEN},
        )

    assert issued.status_code == 200
    assert credits.resolve(issued.json()["api_key"]) == issued.json()["account_id"]
