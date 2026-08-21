"""A published price is a promise to charge.

ATLAS advertised price_per_call_usd and served every invoke free. These cover the
missing half of the contract, and the ways enforcement must NOT misfire.
"""

import importlib

import pytest


def _gate(tmp_path, monkeypatch, *, enforced="1", window=None, maximum=None, policy=None):
    import json
    monkeypatch.setenv("ATLAS_PAYMENT_ENFORCED", enforced)
    monkeypatch.setenv("ATLAS_TRIAL_DB_PATH", str(tmp_path / "trials.db"))
    policy_path = tmp_path / "policy.json"
    if policy is not None:
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setenv("ATLAS_TRIAL_POLICY_PATH", str(policy_path))
    for key, value in (("ATLAS_TRIAL_WINDOW", window), ("ATLAS_TRIAL_MAX_PER_CALLER", maximum)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, str(value))
    return importlib.reload(importlib.import_module("atlas.payment_gate"))


class _Headers(dict):
    def get(self, k, default=""):
        return dict.get(self, k, default)


def test_disabled_by_default_so_deploying_this_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("ATLAS_PAYMENT_ENFORCED", raising=False)
    gate = _gate(tmp_path, monkeypatch, enforced="0")
    assert gate.enforced() is False
    assert gate.reserve("atlas.watchbox.check@v1", _Headers(), "1.2.3.4") is None


def test_a_priced_capability_runs_free_then_answers_402(tmp_path, monkeypatch):
    gate = _gate(tmp_path, monkeypatch, window="lifetime", maximum=2)
    h, ip = _Headers(), "1.2.3.4"
    for _ in range(2):
        assert gate.reserve("atlas.watchbox.check@v1", h, ip) is None
        gate.settle("atlas.watchbox.check@v1", h, ip, result={"ok": True})
    due = gate.reserve("atlas.watchbox.check@v1", h, ip)
    assert due is not None
    assert due["error"] == "payment_required"
    assert due["price_per_call_usd"] > 0
    assert due["free_allowance"]["used"] == 2


def test_a_free_capability_never_consumes_the_allowance(tmp_path, monkeypatch):
    """Spending a trial on a free call reports the wrong limit later."""
    gate = _gate(tmp_path, monkeypatch, maximum=1)
    monkeypatch.setattr(gate, "price_of", lambda cap: 0.0)
    for _ in range(5):
        assert gate.reserve("atlas.free.thing@v1", _Headers(), "9.9.9.9") is None
        gate.settle("atlas.free.thing@v1", _Headers(), "9.9.9.9", result={"ok": True})
    assert gate.quota(gate.caller_id(_Headers(), "9.9.9.9"))["used"] == 0


def test_a_declared_caller_id_holds_its_own_allowance(tmp_path, monkeypatch):
    """Otherwise everyone behind one NAT shares a single allowance."""
    gate = _gate(tmp_path, monkeypatch, maximum=1)
    mine = _Headers({gate.VISITOR_HEADER: "agent-alpha-01"})
    theirs = _Headers({gate.VISITOR_HEADER: "agent-beta-02"})
    assert gate.reserve("atlas.watchbox.check@v1", mine, "5.5.5.5") is None
    gate.settle("atlas.watchbox.check@v1", mine, "5.5.5.5", result={"ok": True})
    assert gate.reserve("atlas.watchbox.check@v1", mine, "5.5.5.5") is not None
    assert gate.reserve("atlas.watchbox.check@v1", theirs, "5.5.5.5") is None


def test_a_too_short_caller_id_falls_back_to_the_address(tmp_path, monkeypatch):
    gate = _gate(tmp_path, monkeypatch)
    assert gate.caller_id(_Headers({gate.VISITOR_HEADER: "short"}), "7.7.7.7") == "ip:7.7.7.7"
    assert gate.caller_id(_Headers({gate.VISITOR_HEADER: "long-enough-id"}), "7.7.7.7").startswith("v:")


def test_the_window_renews_the_allowance(tmp_path, monkeypatch):
    gate = _gate(tmp_path, monkeypatch, window="hourly", maximum=1)
    h, ip = _Headers(), "8.8.8.8"
    assert gate.reserve("atlas.watchbox.check@v1", h, ip) is None
    gate.settle("atlas.watchbox.check@v1", h, ip, result={"ok": True})
    assert gate.reserve("atlas.watchbox.check@v1", h, ip) is not None
    import time as _t
    monkeypatch.setattr(gate, "window_key", lambda now=None: _t.strftime("%Y-%m-%dT%H", _t.gmtime(_t.time() + 3600)))
    assert gate.reserve("atlas.watchbox.check@v1", h, ip) is None


def test_an_unknown_window_does_not_grant_an_unlimited_allowance(tmp_path, monkeypatch):
    gate = _gate(tmp_path, monkeypatch, window="fortnightly")
    assert gate.quota_window() == "lifetime"


def test_a_broken_meter_fails_open(tmp_path, monkeypatch):
    """Under-charging is recoverable; refusing every caller is not."""
    gate = _gate(tmp_path, monkeypatch, maximum=1)
    monkeypatch.setenv("ATLAS_TRIAL_DB_PATH", "/proc/cannot/write/here.db")
    gate = importlib.reload(importlib.import_module("atlas.payment_gate"))
    monkeypatch.setenv("ATLAS_PAYMENT_ENFORCED", "1")
    for _ in range(4):
        assert gate.reserve("atlas.watchbox.check@v1", _Headers(), "3.3.3.3") is None
        gate.settle("atlas.watchbox.check@v1", _Headers(), "3.3.3.3", result={"ok": True})


def test_the_402_says_how_to_continue(tmp_path, monkeypatch):
    gate = _gate(tmp_path, monkeypatch, window="hourly", maximum=1)
    h, ip = _Headers(), "4.4.4.4"
    assert gate.reserve("atlas.watchbox.check@v1", h, ip) is None   # spends the only one
    gate.settle("atlas.watchbox.check@v1", h, ip, result={"ok": True})
    due = gate.reserve("atlas.watchbox.check@v1", h, ip)
    joined = " ".join(due["how_to_continue"]).lower()
    assert "renew" in joined
    assert "modelmarket.dev" in joined
    assert due["free_allowance"]["renews"] is True


def test_policy_file_sets_the_terms_without_a_redeploy(tmp_path, monkeypatch):
    gate = _gate(tmp_path, monkeypatch, policy={"quota_window": "daily", "max_per_caller": 9})
    assert gate.quota_window() == "daily"
    assert gate.max_per_caller() == 9


def test_a_refused_call_is_not_billed(tmp_path, monkeypatch):
    """A malformed bbox must not burn the free tier: pay for data, not attempts."""
    gate = _gate(tmp_path, monkeypatch, window="lifetime", maximum=3)
    h, ip = _Headers(), "6.6.6.6"
    for _ in range(6):
        assert gate.reserve("atlas.situation.brief@v1", h, ip) is None
        gate.settle(
            "atlas.situation.brief@v1", h, ip,
            result={"ok": False, "refuse_reason": "west/south/east/north bbox required"},
        )
    assert gate.quota(gate.caller_id(h, ip))["used"] == 0, "refusals must be free"


def test_a_delivered_call_is_billed(tmp_path, monkeypatch):
    """reserve takes it, settle keeps it — the allowance stands at 1 afterwards."""
    gate = _gate(tmp_path, monkeypatch, window="lifetime", maximum=3)
    h, ip = _Headers(), "6.6.6.7"
    assert gate.reserve("atlas.situation.brief@v1", h, ip) is None
    gate.settle("atlas.situation.brief@v1", h, ip, result={"ok": True, "score": 1})
    assert gate.quota(gate.caller_id(h, ip))["used"] == 1


def test_the_allowance_holds_under_concurrency(tmp_path, monkeypatch):
    """The limit must bind even when many callers arrive at once.

    The first version of this gate read the ledger in ``check`` and wrote it in ``settle``,
    with the product's ``await`` in between. An adversarial review reproduced 100 concurrent
    callers all passing a limit of 5 and all being served, because no write had landed yet
    when they read. ``reserve`` does the read and the write in one locked transaction, so the
    ledger — not the arrival order — decides.
    """
    import asyncio

    gate = _gate(tmp_path, monkeypatch, window="lifetime", maximum=5)
    h, ip = _Headers(), "6.6.6.8"

    async def one():
        due = gate.reserve("atlas.watchbox.check@v1", h, ip)
        await asyncio.sleep(0)          # where the product's work would happen
        if due is None:
            gate.settle("atlas.watchbox.check@v1", h, ip, result={"ok": True})
        return due is None

    served = sum(asyncio.run(_gather(one, 100)))
    assert served == 5, f"limit of 5 admitted {served} concurrent callers"
    assert gate.quota(gate.caller_id(h, ip))["used"] == 5


async def _gather(coro_factory, n):
    import asyncio

    return await asyncio.gather(*[coro_factory() for _ in range(n)])


def test_a_refusal_hands_the_reservation_back(tmp_path, monkeypatch):
    """Fairness survives the move to reserve-first: refusals still cost nothing."""
    gate = _gate(tmp_path, monkeypatch, window="lifetime", maximum=2)
    h, ip = _Headers(), "6.6.6.9"
    for _ in range(6):
        assert gate.reserve("atlas.situation.brief@v1", h, ip) is None
        gate.settle(
            "atlas.situation.brief@v1", h, ip,
            result={"ok": False, "refuse_reason": "no LIVE readings in bbox"},
        )
    assert gate.quota(gate.caller_id(h, ip))["used"] == 0
    assert gate.quota(gate.caller_id(h, ip))["remaining"] == 2


def test_release_never_goes_negative(tmp_path, monkeypatch):
    """Releases run from a `finally`, so a stray double-release is a live possibility."""
    gate = _gate(tmp_path, monkeypatch, window="lifetime", maximum=3)
    h, ip = _Headers(), "6.6.7.0"
    caller = gate.caller_id(h, ip)
    for _ in range(4):
        gate.release(caller)
    assert gate.quota(caller)["used"] == 0
    gate.reserve("atlas.situation.brief@v1", h, ip)
    for _ in range(3):
        gate.release(caller)
    assert gate.quota(caller)["used"] == 0
