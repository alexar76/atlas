"""Charge for priced capabilities instead of advertising a price and giving them away.

ATLAS published a price list (``price_per_call_usd``) and served every invoke for
free: ``POST /ai-market/v2/invoke`` with no payment returned 200. That is not a
free tier, it is a price list nobody is asked to honour — the paid mesh looked
priced from the outside and was unmetered in fact.

What this adds is the missing half of the contract already published in
``.well-known/ai-market.json``: a per-caller free allowance, and a 402 once it is
spent. The allowance mirrors the hub's own trial terms, so an agent that discovers
either service sees the same deal.

Deliberately conservative:

* **Off by default.** ``ATLAS_PAYMENT_ENFORCED=1`` turns it on. Enforcement changes
  what existing callers get back, so it is an explicit operator decision — not a
  side effect of deploying this file.
* **Free capabilities never consume allowance.** A SKU priced at 0 is free, and
  spending a trial on it would hide the real limit behind an unrelated 429.
* **Fails open.** If the ledger cannot be read or written, the invoke proceeds.
  A broken meter must not take the mesh down; under-charging is recoverable,
  refusing every caller is not.
* **Refusals are not billed.** The allowance is checked before the call and spent
  only once the product returns data. The first version charged on entry, and a
  caller sending a malformed bbox burned its whole free tier on ``refuse_reason``
  without ever seeing a result — the worst possible introduction to a paid mesh.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

VISITOR_HEADER = "X-AIMarket-Sandbox-Visitor"

# Same vocabulary as the hub's trial ledger, so one policy describes both.
_WINDOW_FORMATS = {
    "lifetime": "",
    "hourly": "%Y-%m-%dT%H",
    "daily": "%Y-%m-%d",
    "weekly": "%G-W%V",
}

_lock = threading.Lock()


def enforced() -> bool:
    return os.getenv("ATLAS_PAYMENT_ENFORCED", "0").strip().lower() in ("1", "true", "yes")


def _policy_path() -> Path:
    return Path(
        os.getenv("ATLAS_TRIAL_POLICY_PATH", "data/atlas_trial_policy.json")
    )


def _ledger_path() -> Path:
    return Path(os.getenv("ATLAS_TRIAL_DB_PATH", "data/atlas_trials.db"))


def _policy() -> dict[str, Any]:
    """Operator overrides from disk; env wins, as it does on the hub."""
    data: dict[str, Any] = {}
    try:
        parsed = json.loads(_policy_path().read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            data = parsed
    except (OSError, ValueError):
        data = {}
    return data


def quota_window() -> str:
    raw = os.getenv("ATLAS_TRIAL_WINDOW")
    if raw is None:
        raw = str(_policy().get("quota_window") or "hourly")
    candidate = raw.strip().lower()
    # An unknown value must not grant an unlimited allowance.
    return candidate if candidate in _WINDOW_FORMATS else "lifetime"


def max_per_caller() -> int:
    raw = os.getenv("ATLAS_TRIAL_MAX_PER_CALLER")
    if raw is None:
        raw = _policy().get("max_per_caller", 5)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 5


def window_key(now: float | None = None) -> str:
    fmt = _WINDOW_FORMATS.get(quota_window(), "")
    if not fmt:
        return ""
    return time.strftime(fmt, time.gmtime(now if now is not None else time.time()))


def caller_id(headers: Any, client_host: str = "") -> str:
    """Who is asking. A declared visitor id wins; otherwise the network address.

    Falling back to the address means an agent that sends no header still gets a
    real allowance rather than being refused outright — and an agent that wants a
    stable identity across addresses can say so.
    """
    try:
        declared = (headers.get(VISITOR_HEADER) or "").strip()
    except Exception:
        declared = ""
    if declared:
        cleaned = "".join(c for c in declared if c.isalnum() or c in "_-")[:64]
        if len(cleaned) >= 8:
            return f"v:{cleaned}"
    host = (client_host or "").strip()
    return f"ip:{host}" if host else "ip:unknown"


def price_of(capability_id: str) -> float:
    from atlas import products as products_mod

    cap = products_mod.CAP_BY_ID.get(capability_id) or {}
    try:
        return float(cap.get("price_per_call_usd") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _connect() -> sqlite3.Connection:
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS caller_trials (
               caller_id TEXT NOT NULL,
               window_key TEXT NOT NULL,
               used INTEGER NOT NULL DEFAULT 0,
               updated_at TEXT NOT NULL,
               PRIMARY KEY (caller_id, window_key)
           )"""
    )
    return conn


def quota(caller: str) -> dict[str, Any]:
    window = window_key()
    used = 0
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT used FROM caller_trials WHERE caller_id = ? AND window_key = ?",
                (caller, window),
            ).fetchone()
            used = int(row[0]) if row else 0
    except (sqlite3.Error, OSError):
        used = 0
    allowance = max_per_caller()
    return {
        "max": allowance,
        "used": used,
        "remaining": max(0, allowance - used),
        "quota_window": quota_window(),
        "renews": quota_window() != "lifetime",
    }


def consume(caller: str) -> dict[str, Any]:
    """Take one from the allowance. Returns the quota state after the attempt."""
    window = window_key()
    allowance = max_per_caller()
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT used FROM caller_trials WHERE caller_id = ? AND window_key = ?",
                (caller, window),
            ).fetchone()
            used = int(row[0]) if row else 0
            if used >= allowance:
                return {
                    "allowed": False,
                    "used": used,
                    "max": allowance,
                    "remaining": 0,
                    "quota_window": quota_window(),
                    "renews": quota_window() != "lifetime",
                }
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn.execute(
                "INSERT INTO caller_trials (caller_id, window_key, used, updated_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(caller_id, window_key) "
                "DO UPDATE SET used = excluded.used, updated_at = excluded.updated_at",
                (caller, window, used + 1, stamp),
            )
            return {
                "allowed": True,
                "used": used + 1,
                "max": allowance,
                "remaining": max(0, allowance - used - 1),
                "quota_window": quota_window(),
                "renews": quota_window() != "lifetime",
            }
    except (sqlite3.Error, OSError):
        # A broken meter must not refuse the mesh. mkdir raising OSError on an
        # unwritable path is the likeliest failure and was not caught at first.
        return {"allowed": True, "used": 0, "max": allowance, "remaining": allowance,
                "quota_window": quota_window(), "renews": quota_window() != "lifetime",
                "meter_error": True}


def payment_required_body(capability_id: str, state: dict[str, Any]) -> dict[str, Any]:
    """What a caller needs to know to get unstuck, not just that it is stuck."""
    window = state.get("quota_window", quota_window())
    body: dict[str, Any] = {
        "error": "payment_required",
        "capability_id": capability_id,
        "price_per_call_usd": price_of(capability_id),
        "free_allowance": {
            "max": state.get("max"),
            "used": state.get("used"),
            "quota_window": window,
            "renews": window != "lifetime",
        },
        "how_to_continue": [
            f"Send {VISITOR_HEADER} with a stable id (8-64 chars) to hold your own allowance"
            " rather than sharing your network's.",
            "Open a payment channel at the hub and invoke through it: "
            "https://modelmarket.dev/.well-known/ai-market.json",
        ],
    }
    if window != "lifetime":
        body["how_to_continue"].insert(0, f"Wait for the {window} allowance to renew.")
    return body


def release(caller: str) -> dict[str, Any]:
    """Hand one allowance back. Floors at zero, and never reaches into a closed window."""
    window = window_key()
    allowance = max_per_caller()
    try:
        with _lock, _connect() as conn:
            row = conn.execute(
                "SELECT used FROM caller_trials WHERE caller_id = ? AND window_key = ?",
                (caller, window),
            ).fetchone()
            if not row:
                # A release with no matching reservation, or the window turned underneath
                # it. Inventing a negative balance would hand out free calls next window.
                return {"used": 0, "released": False, "max": allowance,
                        "remaining": allowance, "quota_window": quota_window()}
            used = int(row[0])
            new_used = max(0, used - 1)
            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            conn.execute(
                "UPDATE caller_trials SET used = ?, updated_at = ? "
                "WHERE caller_id = ? AND window_key = ?",
                (new_used, stamp, caller, window),
            )
            return {"used": new_used, "released": new_used < used, "max": allowance,
                    "remaining": max(0, allowance - new_used),
                    "quota_window": quota_window()}
    except (sqlite3.Error, OSError):
        return {"used": 0, "released": False, "max": allowance, "remaining": allowance,
                "quota_window": quota_window(), "meter_error": True}


def reserve(capability_id: str, headers: Any, client_host: str = "") -> dict[str, Any] | None:
    """``None`` to proceed with one allowance **held**, or a 402 body.

    Takes the allowance up front, which is what makes the limit hold. The first version
    read the ledger here and wrote it after the work, and the gap between the two is an
    ``await``: an adversarial review reproduced 100 concurrent callers all passing the read
    before any write landed, so an allowance of 5 served 100 calls. Reading and writing in
    one locked transaction closes that, and fairness is preserved on the other side —
    ``settle`` hands the reservation back when the product refused. This is the same shape
    the hub uses for a payment hold, for the same reason.

    Free capabilities and a disabled gate proceed without touching the ledger: spending an
    allowance on a free call would report the wrong limit.
    """
    if not enforced():
        return None
    if price_of(capability_id) <= 0:
        return None
    state = consume(caller_id(headers, client_host))
    if state.get("allowed"):
        return None
    return payment_required_body(capability_id, state)


def settle(
    capability_id: str,
    headers: Any,
    client_host: str = "",
    *,
    result: Any = None,
) -> dict[str, Any] | None:
    """Resolve the reservation ``reserve`` took: kept on delivery, handed back on refusal.

    A product that answers ``ok: false`` (bad input, empty coverage) delivered nothing, so
    it is not billed. ATLAS refuses rather than guessing whenever coverage is empty, and
    after a redeploy every call refuses until the sensor fleet warms — charging for those
    would bill a caller for the operator's restart.
    """
    if not enforced():
        return None
    if price_of(capability_id) <= 0:
        return None
    if isinstance(result, dict) and result.get("ok") is False:
        return release(caller_id(headers, client_host))
    return None
