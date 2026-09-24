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

Since 2026-09 there is a second rail underneath this one: :mod:`atlas.credits`. A caller
holding a credited account is charged the published price and never touches the allowance,
which is what makes a paid plan built on ATLAS evidence possible at all — the allowance is
five calls an hour, and until credits existed that was the ceiling for every buyer,
including one paying a desk for a monthly plan.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from atlas import credits

log = logging.getLogger(__name__)

VISITOR_HEADER = "X-AIMarket-Sandbox-Visitor"

# Same vocabulary as the hub's trial ledger, so one policy describes both.
_WINDOW_FORMATS = {
    "lifetime": "",
    "hourly": "%Y-%m-%dT%H",
    "daily": "%Y-%m-%d",
    "weekly": "%G-W%V",
}

_lock = threading.Lock()

#: The credit reservation ``reserve`` took for THIS request, carried to ``settle``.
#:
#: A ContextVar rather than an argument on purpose: every priced surface already funnels
#: through ``reserve``/``settle`` (guarded by ``test_priced_surface_has_no_bypass``), and
#: widening those signatures would mean touching each call site — the one change most
#: likely to leave a new route half-wired. FastAPI runs each request in its own context,
#: so two concurrent invokes cannot see each other's reservation, and the ``finally`` that
#: resolves it runs in the same task that took it.
_RESERVATION: ContextVar[dict[str, Any] | None] = ContextVar(
    "atlas_credit_reservation", default=None
)

#: What the buyer should be told about the charge once it is settled. Separate from the
#: reservation because it outlives it: ``settle`` clears the reservation and the route then
#: reads this to put the balance on the response.
_RECEIPT: ContextVar[dict[str, Any] | None] = ContextVar("atlas_credit_receipt", default=None)

#: Stale-hold sweeps are cheap but not free; once a minute is often enough to keep a dead
#: request's money from sitting frozen, and rare enough not to touch the ledger per invoke.
_SWEEP_INTERVAL_SECONDS = 60.0
_last_sweep = 0.0


def enforced() -> bool:
    return os.getenv("ATLAS_PAYMENT_ENFORCED", "0").strip().lower() in ("1", "true", "yes")


def _policy_path() -> Path:
    return Path(
        os.getenv("ATLAS_TRIAL_POLICY_PATH", "data/atlas_trial_policy.json")
    )


def _ledger_path() -> Path:
    return Path(os.getenv("ATLAS_TRIAL_DB_PATH", "data/atlas_trials.db"))


def _production() -> bool:
    return os.getenv("AIFACTORY_PROD", "").strip().lower() in ("1", "true", "yes", "on")


def durability_issue() -> str:
    """Why this ledger would not survive a redeploy, or "" if it would.

    ATLAS bills off SQLite and keeps doing so on purpose — one writer, one file, no
    server to operate. So "durable" here is not a question of engine but of WHERE the
    file lives, and the two ways to get that wrong are both silent:

      * the default path is relative (``data/atlas_trials.db``), and inside the
        container it resolves under the app root — an image layer. Every
        `up -d --build` wipes it, which hands every caller a fresh free tier on every
        redeploy, so the 402 the manifest advertises never arrives for anyone willing
        to wait for a deploy.
      * an unwritable directory is worse than a missing one, because `consume()` fails
        OPEN by design (a broken meter must not take the mesh down). That is the right
        call per request and the wrong state to run in for months — the meter reports
        `meter_error` into a log nobody reads and everything is free.

    Checked at startup rather than per request precisely because the request path
    forgives this. atlas/docker-compose.yml already points at /data on the volume;
    this is what stops the next deployment from quietly not doing that.
    """
    path = _ledger_path()
    if not path.is_absolute():
        return (
            f"ATLAS_TRIAL_DB_PATH={path} is relative, so it resolves inside the image "
            f"and a redeploy wipes the ledger. Point it at the mounted volume "
            f"(/data/atlas_trials.db)."
        )
    # The package's own tree is baked into the image; a path under it is durable
    # against nothing. The compose comment says as much about atlas/data/.
    app_root = Path(__file__).resolve().parent.parent
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved == app_root or app_root in resolved.parents:
        return (
            f"ATLAS_TRIAL_DB_PATH={path} is inside the application tree ({app_root}), "
            f"which is an image layer — a rebuild resets every caller's allowance. "
            f"Point it at the mounted volume (/data/atlas_trials.db)."
        )
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return (
            f"ATLAS_TRIAL_DB_PATH={path}: cannot create {parent} ({exc}). The meter "
            f"fails open on a write error, so this would serve every priced call free."
        )
    if not os.access(parent, os.W_OK):
        return (
            f"ATLAS_TRIAL_DB_PATH={path}: {parent} is not writable. The meter fails "
            f"open on a write error, so this would serve every priced call free."
        )
    return ""


def assert_durable_ledger() -> None:
    """Refuse to boot a metered production node whose meter cannot remember.

    Only when enforcement is ON *and* production mode is on: a dev host, or a host
    that deliberately serves everything free, has no meter worth protecting and must
    still start.
    """
    if not (enforced() and _production()):
        return
    issue = durability_issue()
    if issue:
        raise RuntimeError(f"ATLAS refuses to start with ATLAS_PAYMENT_ENFORCED=1: {issue}")


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
    """The list price of a capability, or 0.0 if it is not a priced SKU.

    Normalises first, and that is a security property rather than politeness: `reserve()`
    below returns None for anything priced at or below zero, so any id shape this function
    fails to recognise is an id nobody is charged for. The dispatcher
    (`products.invoke_product`) strips before it resolves, so reading the raw string here let
    one trailing space price a $0.25 SKU at $0.00 and still serve it. Callers should hand in
    an already-normalised id (`ProductInvokeBody` does); this is the backstop for the ones
    that do not.
    """
    from atlas import products as products_mod

    cap = products_mod.CAP_BY_ID.get(str(capability_id or "").strip()) or {}
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


def payment_required_body(
    capability_id: str, state: dict[str, Any], credit: dict[str, Any] | None = None
) -> dict[str, Any]:
    """What a caller needs to know to get unstuck, not just that it is stuck.

    ``credit`` says what the credit rail made of this caller's key, and it is here because
    of the failure it makes visible: a buyer whose key is simply not an account on THIS node
    looked, from the outside, exactly like a buyer who had run out of money. Four desks sold
    paid plans for weeks against an anonymous five-an-hour allowance for that reason.
    """
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
        ],
    }
    if credits.enabled():
        body["credit"] = credit or {"recognized": False, "key_supplied": False}
        body["how_to_continue"].append(
            f"Pay per call with a credit account: send its key as {credits.KEY_HEADER}. "
            "The operator issues and tops up accounts."
        )
    else:
        body["how_to_continue"].append(
            "Open a payment channel at the hub and invoke through it: "
            "https://modelmarket.dev/.well-known/ai-market.json"
        )
    if window != "lifetime":
        body["how_to_continue"].insert(0, f"Wait for the {window} allowance to renew.")
    return body


def _sweep_stale_holds() -> None:
    """Free reservations left behind by requests that died, at most once a minute."""
    global _last_sweep
    now = time.monotonic()
    if now - _last_sweep < _SWEEP_INTERVAL_SECONDS:
        return
    _last_sweep = now
    try:
        credits.expire_stale_holds()
    except (sqlite3.Error, OSError):
        log.exception("credits: sweeping stale holds failed")


def _reserve_credit(capability_id: str, price: float, headers: Any) -> tuple[str, dict[str, Any]]:
    """Try to charge a credited account. Returns ``(verdict, note)``.

    ``verdict`` is one of:

    * ``"charged"`` — the price is held; the free allowance must not be touched.
    * ``"free"`` — this caller has no usable credit, so fall through to the allowance.
      ``note`` records WHY, and it is reported in any later 402 rather than swallowed:
      an unrecognised key silently served from the free tier is the exact bug this rail
      was built to end.
    * ``"refused"`` — the ledger could not be consulted. Serving the call would hand out a
      paid product with no row to reconstruct the debit from, so it is refused instead. The
      free meter fails OPEN for the opposite reason; a money ledger has to fail closed.
    """
    key = credits.key_from_headers(headers)
    if not key:
        return "free", {"recognized": False, "key_supplied": False}
    try:
        account_id = credits.resolve(key)
        if not account_id:
            # Truncated to a prefix: enough for the operator to tell WHICH key is wrong
            # when several desks share a host, and not enough to reuse from a log.
            log.warning(
                "credits: %s %s… is not an account on this node — serving %s from the free "
                "allowance instead", credits.KEY_HEADER, key[:10], capability_id,
            )
            return "free", {"recognized": False, "key_supplied": True}
        receipt_id = credits.new_receipt_id()
        held = credits.hold(account_id, price, receipt_id, capability_id)
    except (sqlite3.Error, OSError):
        log.exception("credits: ledger unavailable while reserving %s", capability_id)
        return "refused", {
            "error": "credit_ledger_unavailable",
            "capability_id": capability_id,
            "detail": "The credit ledger could not be read, so this call was not served "
                      "and nothing was charged. Retry shortly.",
            "retryable": True,
        }
    if held.get("error"):
        if held["error"] == "insufficient_credit":
            return "free", {
                "recognized": True,
                "key_supplied": True,
                "account_id": account_id,
                "balance_usd": held.get("balance_usd", 0.0),
                "needed_usd": held.get("needed_usd", price),
                "detail": "This account's balance is below the price of one call; "
                          "top it up with the operator.",
            }
        log.error("credits: hold failed for %s on %s: %s", account_id, capability_id, held["error"])
        return "refused", {
            "error": "credit_hold_failed",
            "capability_id": capability_id,
            "detail": "The credit reservation could not be taken, so this call was not "
                      "served and nothing was charged.",
            "retryable": True,
        }
    _RESERVATION.set(
        {
            "receipt_id": receipt_id,
            "account_id": account_id,
            "capability_id": capability_id,
            "price_usd": price,
            "balance_usd": held.get("balance_usd"),
            "low_balance": bool(held.get("low_balance")),
        }
    )
    return "charged", {}


def credit_headers() -> dict[str, str]:
    """Headers naming the charge and what is left, or ``{}`` for an unpaid call.

    The buyer of a paid call has to be able to watch its own balance without asking: a desk
    that only discovers it is empty by being refused discovers it while a customer's run is
    failing. Reported on the response of the call that spent the money, so no extra request
    is needed to stay informed.
    """
    receipt = _RECEIPT.get()
    if not receipt:
        return {}
    headers = {credits.CHARGED_HEADER: f"{float(receipt.get('charged_usd') or 0.0):.6f}"}
    balance = receipt.get("balance_usd")
    if balance is not None:
        headers[credits.BALANCE_HEADER] = f"{float(balance):.6f}"
    if receipt.get("low_balance"):
        headers[credits.LOW_BALANCE_HEADER] = "1"
    return headers


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

    A credited account is charged first and skips the allowance entirely — otherwise a
    paying buyer would still be capped at the trial's five calls an hour, which is exactly
    the ceiling that made the published price unreachable for anyone building on it.
    """
    if not enforced():
        return None
    price = price_of(capability_id)
    if price <= 0:
        return None
    _RESERVATION.set(None)
    credit_note: dict[str, Any] | None = None
    if credits.enabled():
        _sweep_stale_holds()
        verdict, note = _reserve_credit(capability_id, price, headers)
        if verdict == "charged":
            return None
        if verdict == "refused":
            return note
        credit_note = note
    state = consume(caller_id(headers, client_host))
    if state.get("allowed"):
        return None
    return payment_required_body(capability_id, state, credit_note)


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

    A credit reservation is resolved here too, and the ``enforced()`` short-circuit below is
    deliberately checked BEFORE it only because a reservation cannot exist without it: the
    same request that took the hold took it under the same setting. A hold that somehow
    outlives the switch is freed by ``credits.expire_stale_holds`` rather than left frozen.
    """
    if not enforced():
        return None
    if price_of(capability_id) <= 0:
        return None
    reservation = _RESERVATION.get()
    if reservation:
        _RESERVATION.set(None)
        delivered = not (isinstance(result, dict) and result.get("ok") is False)
        try:
            if delivered:
                outcome = credits.capture(reservation["receipt_id"])
                _RECEIPT.set({
                    "charged_usd": outcome.get("captured_usd", reservation.get("price_usd")),
                    "balance_usd": outcome.get("balance_usd", reservation.get("balance_usd")),
                    "low_balance": reservation.get("low_balance"),
                })
                return outcome
            released = credits.release(reservation["receipt_id"], note="product refused")
            # A refusal is not billed, and the header has to say so rather than quoting the
            # price the caller was NOT charged.
            _RECEIPT.set({
                "charged_usd": 0.0,
                "balance_usd": released.get("balance_usd"),
                "low_balance": reservation.get("low_balance"),
            })
            return released
        except (sqlite3.Error, OSError):
            # Do not fall through to the free allowance: this caller paid, and spending a
            # trial on top would report the wrong limit to whoever reads the next 402. The
            # hold stays open and the sweeper hands it back.
            log.exception(
                "credits: resolving reservation %s failed; the sweeper will release it",
                reservation["receipt_id"],
            )
            return None
    if isinstance(result, dict) and result.get("ok") is False:
        return release(caller_id(headers, client_host))
    return None
