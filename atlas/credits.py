"""Prepaid credit accounts — the paid entrance ATLAS advertised and never had.

``payment_gate`` closed half of the contract: priced capabilities are metered, and a
caller who spends the free allowance gets a 402 quoting the price. The other half was
missing. That 402 said "open a payment channel at the hub and invoke through it", and
nothing in ATLAS could take money — not a channel, not a card, not a credit. Measured
rather than guessed: a desk that sells a paid plan on ATLAS evidence was capped at five
runs per hour, and routing it through the hub did not help, because the hub's own call to
ATLAS lands on the same anonymous allowance. The price list was honest about the price and
unreachable in practice.

So: an account, a balance, and a header the caller already sends (``X-API-Key``). The
operator issues accounts and credits them; an invoke debits one. No chain, no contract, no
signup flow — the same reasoning as the hub's ``credits`` module, which this deliberately
mirrors so one description covers both nodes.

Decisions worth keeping:

* **Millicents, not cents.** ATLAS SKUs are priced at $0.02 and $0.25; a future tenth-of-a-
  cent SKU must not be rounded up into a 100% overcharge. The unit here is 1/1000 of a
  cent, so every published price is exact through hold → capture.
* **Reserve before the work, resolve after.** The same auth/capture shape the free
  allowance already uses, for the same reason: the invoke path awaits, and a read-then-
  write would let concurrent calls all pass on one balance. The reservation is one
  conditional ``UPDATE ... WHERE balance_mc >= ?``.
* **Refusals are not billed.** A product that answers ``ok: false`` delivered nothing, so
  the hold is released. After a redeploy every read refuses until the sensor fleet warms,
  and charging for those would bill a buyer for the operator's restart.
* **A crash must not freeze a buyer's balance.** A held reservation whose request died is
  money the buyer can neither spend nor get back, so :func:`expire_stale_holds` releases
  anything still open past ``HOLD_MAX_AGE_SECONDS``. It runs at boot and opportunistically
  on the reserve path.
* **Fails CLOSED, unlike the free meter.** ``payment_gate.consume`` fails open on a broken
  ledger on purpose — under-charging a trial is recoverable and refusing the whole mesh is
  not. A credit ledger is different: serving a paid call it cannot record is money gone
  with no row to reconstruct it from, so a ledger error refuses the call instead.
* **Custody, stated plainly.** A prepaid balance is the operator holding somebody else's
  money. :func:`stats` publishes ``outstanding_credit_usd`` so the liability is a number
  the operator can read, and refunds are an operator action rather than an automatic one.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

log = logging.getLogger(__name__)

#: The header a buyer authenticates with. Deliberately the one every client in this
#: ecosystem already sends to a hub (``desk_kernel.hub``, ``core.aimarket_participant``,
#: the TypeScript SDK), so buying from ATLAS needs a new key value and no new code.
KEY_HEADER = "X-API-Key"
KEY_PREFIX = "atls_"
_KEY_BYTES = 24  # 192 bits — a guessable key is a free invoke

# 1 cent = 1000 millicents; $1.00 = 100_000 millicents.
MILLICENTS_PER_DOLLAR = 100_000

#: How long a reservation may stay open before it is assumed dead. Ten minutes is well
#: past the invoke path's own upstream timeouts, so a hold this old belongs to a request
#: that will never resolve it.
HOLD_MAX_AGE_SECONDS = 600

#: Response headers on a charged call. A buyer that only learns its balance by being refused
#: finds out at the worst possible moment — for an unattended desk, that is a customer's run
#: failing before its operator hears about the money. These are cheap enough to send on every
#: paid call, so the buyer's own monitoring can see the balance falling.
BALANCE_HEADER = "X-Atlas-Credit-Balance-Usd"
CHARGED_HEADER = "X-Atlas-Credit-Charged-Usd"
LOW_BALANCE_HEADER = "X-Atlas-Credit-Low"

#: Don't repeat the same low-balance warning on every call: a busy desk would print it
#: hundreds of times an hour and bury everything else in the log.
LOW_BALANCE_LOG_INTERVAL_S = 600.0

_lock = threading.Lock()
_low_warned: dict[str, float] = {}


def enabled() -> bool:
    """Is the credit rail switched on?

    Off by default: turning it on changes what a keyed caller gets back, and the operator
    has to mint accounts first. Keeping it separate from ``ATLAS_PAYMENT_ENFORCED`` is what
    makes a two-step rollout possible — deploy the code, mint the accounts with the admin
    route, hand out the keys, and only then flip this.
    """
    return os.getenv("ATLAS_CREDITS_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def db_path() -> Path:
    return Path(os.getenv("ATLAS_CREDITS_DB_PATH", "data/atlas_credits.db"))


def low_balance_usd() -> float:
    """Below this, a balance is worth telling somebody about.

    A dollar is ~17 calls at the dearest published SKU and ~50 at the cheapest, which is
    enough warning to top up before an unattended buyer starts failing its own customers.
    0 switches the warning off.
    """
    try:
        return max(0.0, float(os.getenv("ATLAS_CREDITS_LOW_BALANCE_USD", "1.0")))
    except (TypeError, ValueError):
        return 1.0


def _production() -> bool:
    return os.getenv("AIFACTORY_PROD", "").strip().lower() in ("1", "true", "yes", "on")


def durability_issue() -> str:
    """Why this ledger would not survive a redeploy, or "" if it would.

    The same trap as the trial ledger (``payment_gate.durability_issue``) with a worse
    outcome: a relative path resolves inside the image, so ``up -d --build`` would delete
    every buyer's balance — money the operator took and can no longer see, and keys that
    stop working with no way to tell a wiped account from a forged one.
    """
    path = db_path()
    if not path.is_absolute():
        return (
            f"ATLAS_CREDITS_DB_PATH={path} is relative, so it resolves inside the image and "
            f"a redeploy deletes every prepaid balance. Point it at the mounted volume "
            f"(/data/atlas_credits.db)."
        )
    app_root = Path(__file__).resolve().parent.parent
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved == app_root or app_root in resolved.parents:
        return (
            f"ATLAS_CREDITS_DB_PATH={path} is inside the application tree ({app_root}), "
            f"which is an image layer — a rebuild deletes every prepaid balance. Point it "
            f"at the mounted volume (/data/atlas_credits.db)."
        )
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return f"ATLAS_CREDITS_DB_PATH={path}: cannot create {parent} ({exc})."
    if not os.access(parent, os.W_OK):
        return f"ATLAS_CREDITS_DB_PATH={path}: {parent} is not writable, so no debit can be recorded."
    return ""


def assert_durable_ledger() -> None:
    """Refuse to boot a node that would take prepaid money it cannot remember."""
    if not enabled():
        return
    issue = durability_issue()
    if issue:
        raise RuntimeError(f"ATLAS refuses to start with ATLAS_CREDITS_ENABLED=1: {issue}")


def usd_to_mc(usd: float) -> int:
    try:
        return int(round(float(usd) * MILLICENTS_PER_DOLLAR))
    except (TypeError, ValueError):
        return 0


def mc_to_usd(mc: int) -> float:
    return round(int(mc or 0) / MILLICENTS_PER_DOLLAR, 6)


def hash_key(api_key: str) -> str:
    """Keys are stored hashed. 192 bits of entropy needs no salt or KDF, and a per-node
    salt would only break key portability across a restore."""
    return hashlib.sha256((api_key or "").strip().encode("utf-8")).hexdigest()


def mint_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(_KEY_BYTES)


def new_receipt_id() -> str:
    return "rcpt_" + secrets.token_hex(12)


def key_from_headers(headers: Any) -> str:
    """The buyer's key, or "" — never raises on a hostile header mapping."""
    try:
        raw = headers.get(KEY_HEADER) or headers.get(KEY_HEADER.lower()) or ""
    except Exception:  # noqa: BLE001 — a header container we do not control
        return ""
    return str(raw).strip()


_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS credit_accounts (
           account_id TEXT PRIMARY KEY,
           key_hash TEXT NOT NULL UNIQUE,
           label TEXT NOT NULL DEFAULT '',
           balance_mc INTEGER NOT NULL DEFAULT 0,
           held_mc INTEGER NOT NULL DEFAULT 0,
           spent_mc INTEGER NOT NULL DEFAULT 0,
           granted_mc INTEGER NOT NULL DEFAULT 0,
           status TEXT NOT NULL DEFAULT 'active',
           created_at TEXT NOT NULL DEFAULT (datetime('now'))
       )""",
    """CREATE TABLE IF NOT EXISTS credit_holds (
           receipt_id TEXT PRIMARY KEY,
           account_id TEXT NOT NULL,
           capability_id TEXT NOT NULL DEFAULT '',
           amount_mc INTEGER NOT NULL,
           status TEXT NOT NULL DEFAULT 'held',
           created_at TEXT NOT NULL DEFAULT (datetime('now')),
           resolved_at TEXT
       )""",
    "CREATE INDEX IF NOT EXISTS credit_holds_open ON credit_holds (status, created_at)",
    """CREATE TABLE IF NOT EXISTS credit_ledger (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           account_id TEXT NOT NULL,
           kind TEXT NOT NULL,
           amount_mc INTEGER NOT NULL,
           receipt_id TEXT NOT NULL DEFAULT '',
           note TEXT NOT NULL DEFAULT '',
           created_at TEXT NOT NULL DEFAULT (datetime('now'))
       )""",
    """CREATE TABLE IF NOT EXISTS credit_topups (
           reference TEXT PRIMARY KEY,
           account_id TEXT NOT NULL,
           amount_mc INTEGER NOT NULL,
           note TEXT NOT NULL DEFAULT '',
           created_at TEXT NOT NULL DEFAULT (datetime('now'))
       )""",
)


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # WAL so the operator can read balances while an invoke is debiting, and a busy
    # timeout so a concurrent writer waits instead of failing the buyer's call.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    for statement in _SCHEMA:
        conn.execute(statement)
    conn.commit()
    return conn


@contextmanager
def _ledger() -> Iterator[sqlite3.Connection]:
    """One transaction, then closed.

    ``with sqlite3.connect(...) as conn`` commits but does NOT close, so using it directly
    leaks a file handle and a WAL reader per request — which on a long-lived process shows
    up much later as "database is locked" rather than as the leak it is.
    """
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _changed(cursor: Any) -> bool:
    """Did the conditional UPDATE hit a row? An unknown rowcount counts as failure:
    refusing a good invoke is recoverable, serving an unpaid one is not."""
    count = getattr(cursor, "rowcount", None)
    return int(count) > 0 if count is not None else False


def _log_row(conn: sqlite3.Connection, account_id: str, kind: str, amount_mc: int,
             receipt_id: str = "", note: str = "") -> None:
    conn.execute(
        "INSERT INTO credit_ledger (account_id, kind, amount_mc, receipt_id, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (account_id, kind, int(amount_mc), receipt_id or "", (note or "")[:200]),
    )


# ── accounts ─────────────────────────────────────────────────────────────


def create_account(label: str = "", grant_usd: float = 0.0) -> dict[str, Any]:
    """Mint an account and return its key ONCE — only the hash is stored.

    Works whether or not the rail is enabled, which is what allows the operator to prepare
    accounts and hand out keys BEFORE flipping ``ATLAS_CREDITS_ENABLED=1``. Enabling it
    while the buyers still hold unknown keys would put every one of them on the anonymous
    free allowance at the exact moment they started expecting to be charged.
    """
    api_key = mint_key()
    account_id = "acct_" + secrets.token_hex(8)
    grant_mc = max(0, usd_to_mc(grant_usd))
    with _lock, _ledger() as conn:
        conn.execute(
            "INSERT INTO credit_accounts (account_id, key_hash, label, balance_mc, granted_mc) "
            "VALUES (?, ?, ?, ?, ?)",
            (account_id, hash_key(api_key), (label or "")[:120], grant_mc, grant_mc),
        )
        if grant_mc:
            _log_row(conn, account_id, "grant", grant_mc, note="opening balance")
    return {
        "account_id": account_id,
        "api_key": api_key,
        "balance_usd": mc_to_usd(grant_mc),
        "label": (label or "")[:120],
    }


def resolve(api_key: str) -> str:
    """API key → account id, or "" when the key is unknown or the account is disabled."""
    key = (api_key or "").strip()
    if not key:
        return ""
    with _ledger() as conn:
        row = conn.execute(
            "SELECT account_id, status FROM credit_accounts WHERE key_hash = ?",
            (hash_key(key),),
        ).fetchone()
    if not row or str(row["status"] or "active") != "active":
        return ""
    return str(row["account_id"])


def account(account_id: str) -> dict[str, Any] | None:
    with _ledger() as conn:
        row = conn.execute(
            "SELECT account_id, label, balance_mc, held_mc, spent_mc, granted_mc, status, "
            "created_at FROM credit_accounts WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "account_id": row["account_id"],
        "label": row["label"],
        "balance_usd": mc_to_usd(row["balance_mc"]),
        "held_usd": mc_to_usd(row["held_mc"]),
        "spent_usd": mc_to_usd(row["spent_mc"]),
        "granted_usd": mc_to_usd(row["granted_mc"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "low_balance": (
            low_balance_usd() > 0 and mc_to_usd(row["balance_mc"]) <= low_balance_usd()
        ),
    }


def balance_usd(account_id: str) -> float:
    with _ledger() as conn:
        row = conn.execute(
            "SELECT balance_mc FROM credit_accounts WHERE account_id = ?", (account_id,),
        ).fetchone()
    return mc_to_usd(row["balance_mc"]) if row else 0.0


def topup(account_id: str, amount_usd: float, *, reference: str = "",
          note: str = "") -> dict[str, Any]:
    """Add credit — the operator's action, once they have the money.

    ``reference`` (an invoice id, a chain transaction, a processor event) is unique across
    the ledger, so a retried curl or a replayed webhook credits the buyer once.
    """
    amount_mc = usd_to_mc(amount_usd)
    if amount_mc <= 0:
        return {"error": "top-up amount must be positive"}
    reference = (reference or "").strip()[:200]
    with _lock, _ledger() as conn:
        if reference:
            existing = conn.execute(
                "SELECT account_id, amount_mc FROM credit_topups WHERE reference = ?",
                (reference,),
            ).fetchone()
            if existing:
                if (str(existing["account_id"]) != account_id
                        or int(existing["amount_mc"]) != amount_mc):
                    return {"error": "reference already used for a different account or amount"}
                return {
                    "account_id": account_id,
                    "credited_usd": 0.0,
                    "balance_usd": _balance_in(conn, account_id),
                    "reference": reference,
                    "idempotent_replay": True,
                }
        cur = conn.execute(
            "UPDATE credit_accounts SET balance_mc = balance_mc + ?, granted_mc = granted_mc + ? "
            "WHERE account_id = ? AND status = 'active'",
            (amount_mc, amount_mc, account_id),
        )
        if not _changed(cur):
            return {"error": f"unknown or disabled account {account_id}"}
        if reference:
            conn.execute(
                "INSERT INTO credit_topups (reference, account_id, amount_mc, note) "
                "VALUES (?, ?, ?, ?)",
                (reference, account_id, amount_mc, (note or "")[:200]),
            )
        _log_row(conn, account_id, "grant", amount_mc, note=note or "operator top-up")
        return {
            "account_id": account_id,
            "credited_usd": mc_to_usd(amount_mc),
            "balance_usd": _balance_in(conn, account_id),
            "reference": reference,
            "idempotent_replay": False,
        }


def set_status(account_id: str, status: str) -> dict[str, Any]:
    if status not in ("active", "disabled"):
        return {"error": "status must be active or disabled"}
    with _lock, _ledger() as conn:
        cur = conn.execute(
            "UPDATE credit_accounts SET status = ? WHERE account_id = ?", (status, account_id),
        )
        if not _changed(cur):
            return {"error": f"unknown account {account_id}"}
    return {"account_id": account_id, "status": status}


def _balance_in(conn: sqlite3.Connection, account_id: str) -> float:
    row = conn.execute(
        "SELECT balance_mc FROM credit_accounts WHERE account_id = ?", (account_id,),
    ).fetchone()
    return mc_to_usd(row["balance_mc"]) if row else 0.0


# ── the money path ───────────────────────────────────────────────────────


def hold(account_id: str, amount_usd: float, receipt_id: str,
         capability_id: str = "") -> dict[str, Any]:
    """Reserve the price before the product runs.

    One conditional UPDATE rather than a read followed by a write: the invoke path awaits
    upstream sensors, and N concurrent calls on one account would otherwise all observe the
    same sufficient balance and discover the shortfall only after the work was done.
    """
    amount_mc = usd_to_mc(amount_usd)
    if amount_mc <= 0:
        return {"error": "hold amount must be positive"}
    if not receipt_id:
        return {"error": "hold requires a receipt id"}
    with _lock, _ledger() as conn:
        if conn.execute(
            "SELECT status FROM credit_holds WHERE receipt_id = ?", (receipt_id,),
        ).fetchone():
            return {"error": f"receipt {receipt_id} already used"}
        cur = conn.execute(
            "UPDATE credit_accounts SET balance_mc = balance_mc - ?, held_mc = held_mc + ? "
            "WHERE account_id = ? AND status = 'active' AND balance_mc >= ?",
            (amount_mc, amount_mc, account_id, amount_mc),
        )
        if not _changed(cur):
            return {
                "error": "insufficient_credit",
                "needed_usd": mc_to_usd(amount_mc),
                "balance_usd": _balance_in(conn, account_id),
            }
        conn.execute(
            "INSERT INTO credit_holds (receipt_id, account_id, capability_id, amount_mc, status) "
            "VALUES (?, ?, ?, ?, 'held')",
            (receipt_id, account_id, (capability_id or "")[:128], amount_mc),
        )
        _log_row(conn, account_id, "hold", amount_mc, receipt_id=receipt_id)
        remaining = _balance_in(conn, account_id)
    low = _note_low_balance(account_id, remaining, amount_usd)
    return {
        "receipt_id": receipt_id,
        "held_usd": mc_to_usd(amount_mc),
        "balance_usd": remaining,
        "low_balance": low,
    }


def _note_low_balance(account_id: str, remaining: float, price_usd: float) -> bool:
    """Warn the operator while there is still time to act, and only occasionally.

    Deliberately reported in calls rather than only in dollars: "$0.42 left" means nothing
    without the price of the thing being bought, while "about 7 more calls" is immediately
    actionable.
    """
    threshold = low_balance_usd()
    if threshold <= 0 or remaining > threshold:
        return False
    now = time.monotonic()
    if now - _low_warned.get(account_id, 0.0) >= LOW_BALANCE_LOG_INTERVAL_S:
        _low_warned[account_id] = now
        calls_left = int(remaining / price_usd) if price_usd > 0 else 0
        log.warning(
            "credits: %s is down to $%.2f (about %d more call(s) at $%.2f) — top it up "
            "before its buyer starts failing",
            account_id, remaining, calls_left, price_usd,
        )
    return True


def capture(receipt_id: str) -> dict[str, Any]:
    """Turn a reservation into a recorded debit. A no-op on an already-resolved hold, so a
    late exception on a settled invoke cannot double-charge."""
    with _lock, _ledger() as conn:
        row = conn.execute(
            "SELECT account_id, amount_mc, status FROM credit_holds WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        if not row:
            return {"error": f"no hold for receipt {receipt_id}"}
        if str(row["status"]) != "held":
            return {"captured_usd": 0.0, "already": str(row["status"])}
        amount_mc, account_id = int(row["amount_mc"]), str(row["account_id"])
        conn.execute(
            "UPDATE credit_accounts SET held_mc = held_mc - ?, spent_mc = spent_mc + ? "
            "WHERE account_id = ?",
            (amount_mc, amount_mc, account_id),
        )
        conn.execute(
            "UPDATE credit_holds SET status = 'captured', resolved_at = datetime('now') "
            "WHERE receipt_id = ?",
            (receipt_id,),
        )
        _log_row(conn, account_id, "capture", amount_mc, receipt_id=receipt_id)
        return {
            "account_id": account_id,
            "captured_usd": mc_to_usd(amount_mc),
            "balance_usd": _balance_in(conn, account_id),
        }


def release(receipt_id: str, note: str = "") -> dict[str, Any]:
    """Hand a reservation back. Idempotent, and never gated on the rail being enabled: an
    in-flight hold must resolve even if the operator flips the rail off mid-invoke,
    otherwise the buyer's balance stays frozen."""
    with _lock, _ledger() as conn:
        return _release_in(conn, receipt_id, note=note)


def _release_in(conn: sqlite3.Connection, receipt_id: str, note: str = "") -> dict[str, Any]:
    row = conn.execute(
        "SELECT account_id, amount_mc, status FROM credit_holds WHERE receipt_id = ?",
        (receipt_id,),
    ).fetchone()
    if not row:
        return {"error": f"no hold for receipt {receipt_id}"}
    if str(row["status"]) != "held":
        return {"released_usd": 0.0, "already": str(row["status"])}
    amount_mc, account_id = int(row["amount_mc"]), str(row["account_id"])
    conn.execute(
        "UPDATE credit_accounts SET held_mc = held_mc - ?, balance_mc = balance_mc + ? "
        "WHERE account_id = ?",
        (amount_mc, amount_mc, account_id),
    )
    conn.execute(
        "UPDATE credit_holds SET status = 'released', resolved_at = datetime('now') "
        "WHERE receipt_id = ?",
        (receipt_id,),
    )
    _log_row(conn, account_id, "release", amount_mc, receipt_id=receipt_id, note=note)
    return {
        "account_id": account_id,
        "released_usd": mc_to_usd(amount_mc),
        "balance_usd": _balance_in(conn, account_id),
    }


def expire_stale_holds(max_age_seconds: int = HOLD_MAX_AGE_SECONDS) -> int:
    """Release reservations whose request died, and return how many were freed.

    Without this, a killed worker (a deploy, an OOM, a `finally` that could not reach the
    ledger) leaves money the buyer can neither spend nor reclaim, and the only symptom is
    a balance that quietly shrinks with every restart.
    """
    age = max(1, int(max_age_seconds))
    freed = 0
    with _lock, _ledger() as conn:
        rows = conn.execute(
            "SELECT receipt_id FROM credit_holds WHERE status = 'held' "
            "AND created_at <= datetime('now', ?) LIMIT 500",
            (f"-{age} seconds",),
        ).fetchall()
        for row in rows or []:
            result = _release_in(conn, str(row["receipt_id"]), note="stale hold expired")
            if result.get("released_usd"):
                freed += 1
    if freed:
        log.warning("credits: released %d reservation(s) left open by a dead request", freed)
    return freed


# ── reporting ────────────────────────────────────────────────────────────


def stats() -> dict[str, Any]:
    """Rail totals. ``outstanding_credit_usd`` is the solvency number: prepaid money the
    operator is holding for somebody else and has not earned."""
    with _ledger() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(balance_mc), 0) AS bal, "
            "COALESCE(SUM(held_mc), 0) AS held, COALESCE(SUM(spent_mc), 0) AS spent, "
            "COALESCE(SUM(granted_mc), 0) AS granted FROM credit_accounts"
        ).fetchone()
    return {
        "enabled": enabled(),
        "accounts": int(row["n"] or 0) if row else 0,
        "credits_earned_usd": mc_to_usd(row["spent"] if row else 0),
        "outstanding_credit_usd": mc_to_usd(
            (int(row["bal"] or 0) + int(row["held"] or 0)) if row else 0
        ),
        "held_usd": mc_to_usd(row["held"] if row else 0),
        "granted_usd": mc_to_usd(row["granted"] if row else 0),
    }


def recent(account_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 500))
    with _ledger() as conn:
        if account_id:
            rows = conn.execute(
                "SELECT account_id, kind, amount_mc, receipt_id, note, created_at "
                "FROM credit_ledger WHERE account_id = ? ORDER BY id DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT account_id, kind, amount_mc, receipt_id, note, created_at "
                "FROM credit_ledger ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [
        {
            "account_id": r["account_id"],
            "kind": r["kind"],
            "amount_usd": mc_to_usd(r["amount_mc"]),
            "receipt_id": r["receipt_id"],
            "note": r["note"],
            "created_at": r["created_at"],
        }
        for r in (rows or [])
    ]
