"""Durable, append-only log of watchbox checks — the monitoring evidence artifact.

WHY THIS EXISTS, AND WHY IT IS THE PRODUCT

A signature over someone else's public fact is worth nothing: the other party fetches
NASA FIRMS themselves and our receipt adds a link to the chain of custody rather than
shortening it. A signature over *our own act of checking, at a time the buyer could not
have chosen after the fact*, is worth something — because "prove you were monitoring" is
a recurring obligation (permit conditions, EHS programmes, ISO 14001/45001 audits,
insurance warranties, and the notice deadlines in construction weather-delay clauses,
where the deadline is the dispute, not the weather).

That distinction is the whole design: this file records what WE did, not what the world
was. Each row says "at 09:56:10Z this instance evaluated watchbox wb-x against the live
fleet and saw N matches", signed with the same Ed25519 key as the manifest.

APPEND-ONLY, and enforced rather than promised: there is no UPDATE or DELETE of a check
row anywhere in this module, and SQLite triggers reject both at the database level, so a
bug (or a later contributor) cannot quietly rewrite history. Delivery attempts are a
separate table precisely so that retry bookkeeping never has to mutate a check.

DURABILITY. ATLAS previously had no persistent store beyond a JSON file inside the image
(atlas/data/watchboxes.json resolves to /app/data in the container, which `up -d --build`
wipes), while the only mounted volume is atlas_data:/data. This database therefore
defaults under /data. A monitoring log that does not survive a redeploy is not evidence,
so ATLAS_MONITOR_DB_PATH must point at mounted storage in production.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .geo import utc_now

# Retention is a real commitment, not a default to be inherited by accident: the buyer's
# obligation horizon (permit cycle, audit period, limitation period) decides it.
DEFAULT_RETENTION_DAYS = 1095  # 3 years


def _default_path() -> Path:
    return Path(os.environ.get("ATLAS_MONITOR_DB_PATH", "/data/atlas_monitor.db"))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    watchbox_id     TEXT    NOT NULL,
    evaluated_at    TEXT    NOT NULL,
    match_count     INTEGER NOT NULL,
    live_match_count INTEGER NOT NULL,
    layers          TEXT    NOT NULL,
    bbox            TEXT    NOT NULL,
    digest          TEXT    NOT NULL,
    signature_b64   TEXT    NOT NULL,
    public_key_b64  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checks_wb ON checks(watchbox_id, id);

CREATE TABLE IF NOT EXISTS deliveries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id      INTEGER NOT NULL REFERENCES checks(id),
    attempt       INTEGER NOT NULL,
    attempted_at  TEXT    NOT NULL,
    status_code   INTEGER,
    error         TEXT,
    delivered     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_deliveries_check ON deliveries(check_id);

-- Append-only is enforced here, not merely intended. A check row is evidence; if code
-- can edit it, it is not.
CREATE TRIGGER IF NOT EXISTS checks_no_update
BEFORE UPDATE ON checks
BEGIN
    SELECT RAISE(ABORT, 'checks is append-only');
END;
-- Deletes are refused outright. The earlier version allowed a delete when
-- `evaluated_at` fell below a `meta.retention_floor` row — but nothing ever wrote that
-- row and nothing protected it, so a single INSERT into `meta` unlocked deletion of the
-- entire log. An append-only guard whose escape hatch is a writable table is not a
-- guard. Retention pruning, when it exists, must be a deliberate, audited operation
-- that drops this trigger explicitly rather than tiptoeing through a condition.
CREATE TRIGGER IF NOT EXISTS checks_no_delete
BEFORE DELETE ON checks
BEGIN
    SELECT RAISE(ABORT, 'checks is append-only');
END;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class MonitorLog:
    """Append-only check log. One connection, guarded by a lock (ATLAS runs 1 worker)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # check_same_thread=False: the delivery loop and request handlers share it under
        # the lock above. WAL so a reader never blocks the appender.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            # `meta` is referenced by the delete trigger, so create it before the schema
            # that defines the trigger.
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.executescript(_SCHEMA)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── append ────────────────────────────────────────────────────────────────
    def append_check(
        self,
        *,
        watchbox_id: str,
        evaluated_at: str,
        match_count: int,
        live_match_count: int,
        layers: list[str],
        bbox: dict[str, float],
        digest: str,
        signature_b64: str,
        public_key_b64: str,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO checks (watchbox_id, evaluated_at, match_count, "
                "live_match_count, layers, bbox, digest, signature_b64, public_key_b64) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    watchbox_id,
                    evaluated_at,
                    int(match_count),
                    int(live_match_count),
                    json.dumps(layers, sort_keys=True),
                    json.dumps(bbox, sort_keys=True),
                    digest,
                    signature_b64,
                    public_key_b64,
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def record_delivery(
        self,
        *,
        check_id: int,
        attempt: int,
        status_code: int | None,
        error: str | None,
        delivered: bool,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO deliveries (check_id, attempt, attempted_at, status_code, "
                "error, delivered) VALUES (?,?,?,?,?,?)",
                (
                    int(check_id),
                    int(attempt),
                    utc_now(),
                    status_code,
                    (error or "")[:500] or None,
                    1 if delivered else 0,
                ),
            )
            self._conn.commit()

    # ── read ──────────────────────────────────────────────────────────────────
    def checks(self, watchbox_id: str, *, limit: int = 200, since: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        sql = "SELECT * FROM checks WHERE watchbox_id=?"
        args: list[Any] = [watchbox_id]
        if since:
            sql += " AND evaluated_at >= ?"
            args.append(since)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["layers"] = json.loads(d["layers"])
                d["bbox"] = json.loads(d["bbox"])
                dels = self._conn.execute(
                    "SELECT attempt, attempted_at, status_code, error, delivered "
                    "FROM deliveries WHERE check_id=? ORDER BY attempt",
                    (d["id"],),
                ).fetchall()
                d["deliveries"] = [dict(x) for x in dels]
                out.append(d)
            return out

    @staticmethod
    def _parse_ts(value: Any) -> float | None:
        from datetime import datetime

        text = str(value or "").strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None

    def gaps(self, watchbox_id: str, *, expected_interval_s: float) -> dict[str, Any]:
        """Continuity, computed — not implied by first/last.

        The summary used to report only count, first and last, which cannot express a
        gap: a log with a week-long outage in the middle still spans the whole period,
        so a dirty log looked identical to a continuous one. That is the single question
        an auditor asks, so it gets computed rather than left to inference. A gap is any
        interval between consecutive checks longer than 3x the expected cadence — wide
        enough that one slow tick is not an incident, narrow enough that a real outage
        cannot hide.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT evaluated_at FROM checks WHERE watchbox_id=? ORDER BY evaluated_at",
                (watchbox_id,),
            ).fetchall()
        stamps = [t for t in (self._parse_ts(r["evaluated_at"]) for r in rows) if t is not None]
        threshold = max(1.0, float(expected_interval_s) * 3.0)
        gaps: list[dict[str, Any]] = []
        longest = 0.0
        for prev, nxt in zip(stamps, stamps[1:]):
            delta = nxt - prev
            longest = max(longest, delta)
            if delta > threshold:
                gaps.append({
                    "after": rows[stamps.index(prev)]["evaluated_at"],
                    "seconds": round(delta, 1),
                })
        return {
            "expected_interval_s": float(expected_interval_s),
            "gap_threshold_s": threshold,
            "gap_count": len(gaps),
            "longest_interval_s": round(longest, 1),
            # Bounded: a pathological log must not turn one response into a megabyte.
            "gaps": gaps[:50],
            "gaps_truncated": len(gaps) > 50,
            "unparseable_timestamps": len(rows) - len(stamps),
        }

    def summary(self, watchbox_id: str) -> dict[str, Any]:
        """What an auditor actually asks: how continuously was this box watched?"""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n, MIN(evaluated_at) AS first, MAX(evaluated_at) AS last "
                "FROM checks WHERE watchbox_id=?",
                (watchbox_id,),
            ).fetchone()
            undelivered = self._conn.execute(
                "SELECT COUNT(*) AS n FROM checks c WHERE c.watchbox_id=? AND NOT EXISTS "
                "(SELECT 1 FROM deliveries d WHERE d.check_id=c.id AND d.delivered=1)",
                (watchbox_id,),
            ).fetchone()
        return {
            "watchbox_id": watchbox_id,
            "checks_recorded": int(row["n"] or 0),
            "first_check_at": row["first"],
            "last_check_at": row["last"],
            # Reported, never hidden: a gap in the log is the thing the buyer must be
            # able to see, because an evidence log that quietly omits failures is worse
            # than no log at all.
            "checks_never_delivered": int(undelivered["n"] or 0),
            # Declared, NOT enforced — and labelled as such. No pruning code exists in
            # either direction, so advertising a bare `retention_days` read as a
            # retention commitment we had not built. Nothing is deleted today (the
            # append-only trigger refuses it), which is the safe direction, but the
            # buyer must not infer a guarantee from a number.
            "retention_days_declared": int(
                os.environ.get("ATLAS_MONITOR_RETENTION_DAYS", DEFAULT_RETENTION_DAYS)
            ),
            "retention_enforced": False,
        }


STORE: MonitorLog | None = None


def get_store() -> MonitorLog:
    global STORE
    if STORE is None:
        STORE = MonitorLog()
    return STORE
