"""Append-only archive of instrument status snapshots.

ATLAS could answer "is this radar healthy now" and nothing else, so the question a
claims adjuster actually pays for — *was the instrument up when the event happened* —
had no answer at all. This is the smallest store that makes it answerable: one JSON
line per station per sample, retained for a bounded number of days.

Two honesty rules are structural, not stylistic:

* The archive knows only what it recorded. A window that predates the first sample is
  reported as uncovered, never as "no problems found".
* A gap in our sampling is NOT evidence the instrument was down. Recorded degraded
  status is positive evidence; a missing sample is an absence of evidence, and
  ``window()`` keeps the two apart so the product cannot conflate them.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

_ARCHIVE_ENV = "ATLAS_STATUS_ARCHIVE_PATH"
_RETENTION_ENV = "ATLAS_STATUS_ARCHIVE_DAYS"
_MAX_ROWS_ENV = "ATLAS_STATUS_ARCHIVE_MAX_ROWS"

DEFAULT_RETENTION_DAYS = 120
# ~50 radars × 6 samples/hour × 120 days ≈ 864k rows. The cap is the backstop that
# keeps a misconfigured interval from filling the volume, not the normal bound.
DEFAULT_MAX_ROWS = 1_500_000

_ISO = "%Y-%m-%dT%H:%M:%SZ"


def _default_path() -> Path:
    """Archive location, env-overridable so prod can point at mounted storage.

    Same reasoning as the watchbox registry: the repo-relative default resolves inside
    the container, which a rebuild wipes, and an archive that resets on deploy can
    never attest a window older than the last deploy.
    """
    env = (os.environ.get(_ARCHIVE_ENV) or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "data" / "status-archive.jsonl"


def _int_env(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def parse_iso(value: Any) -> datetime | None:
    """Lenient UTC parse for the timestamps this archive and its callers exchange."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StatusArchive:
    """JSON-lines store of ``(layer, station_id, ts, status, values)`` samples."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else _default_path()
        self._lock = threading.Lock()

    # ── write ────────────────────────────────────────────────────────────────
    def append(self, layer: str, rows: Iterable[dict[str, Any]], *, ts: datetime | None = None) -> int:
        """Append one sample per row. Returns the number of samples written."""
        stamp = (ts or _utc_now()).strftime(_ISO)
        layer = str(layer or "").strip()
        if not layer:
            return 0
        lines: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            station_id = str(
                row.get("station_id") or row.get("radar_id") or row.get("id") or ""
            ).strip()
            if not station_id:
                continue
            values = row.get("values") if isinstance(row.get("values"), dict) else {}
            sample = {
                "ts": stamp,
                "layer": layer,
                "station_id": station_id[:96],
                "status": str(row.get("status") or "")[:48] or None,
                "operability": str(row.get("operability") or "")[:48] or None,
                "lat": _num_or_none(row.get("lat")),
                "lon": _num_or_none(row.get("lon")),
                "live": bool(row.get("live")),
                "values": {
                    k: v for k, v in values.items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                },
            }
            lines.append(json.dumps(sample, ensure_ascii=False, separators=(",", ":")))
        if not lines:
            return 0
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        return len(lines)

    def prune(self, *, now: datetime | None = None) -> int:
        """Drop samples older than the retention window, then cap total rows.

        Returns the number of samples dropped. Rewrites the file in place under the
        same lock the writer uses, so a concurrent append cannot interleave.
        """
        retention_days = _int_env(_RETENTION_ENV, DEFAULT_RETENTION_DAYS)
        max_rows = _int_env(_MAX_ROWS_ENV, DEFAULT_MAX_ROWS)
        cutoff = (now or _utc_now()) - timedelta(days=retention_days)
        with self._lock:
            if not self.path.is_file():
                return 0
            kept: list[str] = []
            dropped = 0
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        sample = json.loads(line)
                    except ValueError:
                        dropped += 1
                        continue
                    stamp = parse_iso(sample.get("ts"))
                    if stamp is None or stamp < cutoff:
                        dropped += 1
                        continue
                    kept.append(line)
            if len(kept) > max_rows:
                dropped += len(kept) - max_rows
                kept = kept[-max_rows:]
            if not dropped:
                return 0
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(("\n".join(kept) + "\n") if kept else "", encoding="utf-8")
            tmp.replace(self.path)
            return dropped

    # ── read ─────────────────────────────────────────────────────────────────
    def window(
        self,
        *,
        layer: str,
        station_ids: Iterable[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 20_000,
    ) -> dict[str, Any]:
        """Samples for ``station_ids`` in ``[start, end]``, plus archive extent.

        ``archive_start`` / ``archive_end`` are the extent of everything this archive
        holds for the layer — the caller needs them to say whether the requested window
        is covered at all, rather than reporting an empty result as a clean bill.
        """
        wanted = {str(s).strip() for s in (station_ids or ()) if str(s).strip()} or None
        samples: list[dict[str, Any]] = []
        archive_start: datetime | None = None
        archive_end: datetime | None = None
        total_layer_samples = 0
        if not self.path.is_file():
            return {
                "samples": [],
                "sample_count": 0,
                "archive_start": None,
                "archive_end": None,
                "layer_sample_count": 0,
                "truncated": False,
            }
        truncated = False
        with self._lock:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        sample = json.loads(line)
                    except ValueError:
                        continue
                    if str(sample.get("layer") or "") != layer:
                        continue
                    stamp = parse_iso(sample.get("ts"))
                    if stamp is None:
                        continue
                    total_layer_samples += 1
                    if archive_start is None or stamp < archive_start:
                        archive_start = stamp
                    if archive_end is None or stamp > archive_end:
                        archive_end = stamp
                    if wanted is not None and str(sample.get("station_id") or "") not in wanted:
                        continue
                    if start is not None and stamp < start:
                        continue
                    if end is not None and stamp > end:
                        continue
                    if len(samples) >= max(1, limit):
                        truncated = True
                        continue
                    samples.append(sample)
        samples.sort(key=lambda s: str(s.get("ts") or ""))
        return {
            "samples": samples,
            "sample_count": len(samples),
            "archive_start": archive_start.strftime(_ISO) if archive_start else None,
            "archive_end": archive_end.strftime(_ISO) if archive_end else None,
            "layer_sample_count": total_layer_samples,
            "truncated": truncated,
        }


def _num_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


ARCHIVE = StatusArchive()

__all__ = [
    "StatusArchive",
    "ARCHIVE",
    "parse_iso",
    "DEFAULT_RETENTION_DAYS",
    "DEFAULT_MAX_ROWS",
]
