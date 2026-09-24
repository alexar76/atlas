"""Persistent per-station USGS registry, observation history, and feed uptime.

Uptime here is deliberately named ``observation_uptime``: it measures whether a
station that ATLAS previously discovered in a queried bbox appeared with a usable
latest observation on subsequent fresh registry polls. It is not a claim about
power, telemetry hardware, or USGS infrastructure outside those polls.
"""

from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

from .geo import utc_now

_VALUE_FIELDS = (
    "water_temperature_c", "ph", "dissolved_oxygen_mg_l",
    "specific_conductance_us_cm",
)


def _in_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> bool:
    west, south, east, north = bbox
    if not (south <= lat <= north):
        return False
    return west <= lon <= east if west <= east else lon >= west or lon <= east


class WaterQualityHistoryStore:
    def __init__(self, path: str, *, history_limit: int = 96) -> None:
        self.path = Path(path) if str(path or "").strip() else None
        self.history_limit = max(4, min(int(history_limit), 2_000))
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {"version": 1, "stations": {}}
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(loaded, dict) and isinstance(loaded.get("stations"), dict):
            self._data = loaded

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self._data, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    @staticmethod
    def _station_id(row: dict[str, Any]) -> str:
        return str(row.get("station_id") or "").strip()

    @staticmethod
    def _usable(row: dict[str, Any]) -> bool:
        return any(
            not isinstance(row.get(field), bool)
            and isinstance(row.get(field), (int, float))
            and math.isfinite(float(row[field]))
            for field in _VALUE_FIELDS
        )

    @staticmethod
    def _snapshot(row: dict[str, Any], recorded_at: str) -> dict[str, Any]:
        values = {
            field: float(row[field])
            for field in _VALUE_FIELDS
            if not isinstance(row.get(field), bool)
            and isinstance(row.get(field), (int, float))
            and math.isfinite(float(row[field]))
        }
        return {
            "recorded_at": recorded_at,
            "observed_at": row.get("observed_at"),
            "values": values,
            "approval_status": row.get("approval_status") or "Unknown",
            "qualifiers": list(row.get("qualifiers") or []),
            "observation_metadata": dict(row.get("observation_metadata") or {}),
        }

    def observe(
        self,
        bbox: tuple[float, float, float, float],
        rows: list[dict[str, Any]],
        *,
        polled_at: str | None = None,
    ) -> None:
        """Import registry rows and record one availability check per fresh poll."""
        at = polled_at or utc_now()
        with self._lock:
            stations = self._data.setdefault("stations", {})
            expected: set[str] = set()
            for station_id, state in stations.items():
                try:
                    lat, lon = float(state["lat"]), float(state["lon"])
                except (KeyError, TypeError, ValueError):
                    continue
                if math.isfinite(lat) and math.isfinite(lon) and _in_bbox(lat, lon, bbox):
                    expected.add(str(station_id))

            by_id = {
                self._station_id(row): row
                for row in rows if isinstance(row, dict) and self._station_id(row)
            }
            expected.update(by_id)
            for station_id in expected:
                row = by_id.get(station_id)
                state = stations.setdefault(station_id, {
                    "station_id": station_id,
                    "first_seen_at": at,
                    "checks": 0,
                    "successful_checks": 0,
                    "history": [],
                })
                state["checks"] = int(state.get("checks") or 0) + 1
                if row is None or not self._usable(row):
                    state["last_checked_at"] = at
                    continue
                state["successful_checks"] = int(state.get("successful_checks") or 0) + 1
                state.update({
                    "name": row.get("name") or station_id,
                    "lat": row.get("latitude"),
                    "lon": row.get("longitude"),
                    "site_type": row.get("site_type"),
                    "state_name": row.get("state_name"),
                    "county_name": row.get("county_name"),
                    "country_name": row.get("country_name"),
                    "agency_code": row.get("agency_code"),
                    "registry_id": row.get("registry_id"),
                    "hydrologic_unit_code": row.get("hydrologic_unit_code"),
                    "available_parameters": list(row.get("available_parameters") or []),
                    "last_seen_at": at,
                    "last_checked_at": at,
                })
                sample = self._snapshot(row, at)
                history = state.setdefault("history", [])
                previous = history[-1] if history else None
                fingerprint = {k: v for k, v in sample.items() if k != "recorded_at"}
                previous_fingerprint = (
                    {k: v for k, v in previous.items() if k != "recorded_at"}
                    if isinstance(previous, dict) else None
                )
                if fingerprint != previous_fingerprint:
                    history.append(sample)
                    del history[:-self.history_limit]
            self._data["updated_at"] = at
            self._save()

    def summary(self, station_id: str) -> dict[str, Any]:
        with self._lock:
            state = (self._data.get("stations") or {}).get(str(station_id))
            if not isinstance(state, dict):
                return {}
            checks = int(state.get("checks") or 0)
            successes = int(state.get("successful_checks") or 0)
            return {
                "observation_uptime_pct": round(100.0 * successes / checks, 2) if checks else None,
                "uptime_successful_checks": successes,
                "uptime_checks": checks,
                "history_count": len(state.get("history") or []),
                "first_seen_at": state.get("first_seen_at"),
                "last_seen_at": state.get("last_seen_at"),
                "last_checked_at": state.get("last_checked_at"),
                "uptime_basis": "successful latest-observation responses / fresh ATLAS polls in station bbox",
            }

    def detail(self, station_id: str) -> dict[str, Any]:
        with self._lock:
            state = (self._data.get("stations") or {}).get(str(station_id))
            if not isinstance(state, dict):
                return {}
            return {**self.summary(station_id), "history": list(state.get("history") or [])}
