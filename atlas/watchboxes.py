"""Geographic watchboxes over free-to-commercialize ATLAS layers.

A watchbox is a bbox + layer filter. ``check`` returns stations currently
inside the box whose layer is allowlisted (never NC-only commercial feeds —
those are not in ATLAS at all).
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from .fleet import EVENT_LAYERS
from .geo import utc_now
from .stations import LAYER_META, STATION_CATALOG

# Layers we may sell / alert on. Matches free-to-commercialize GAIA relays + SIM.
ALLOWED_WATCHBOX_LAYERS = frozenset(LAYER_META.keys())

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{4,64}$")
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "watchboxes.json"


class WatchboxStore:
    """JSON-backed watchbox registry (single-process)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _DEFAULT_PATH
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            self._items = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._items = {}
            return
        items = raw.get("watchboxes") if isinstance(raw, dict) else None
        out: dict[str, dict[str, Any]] = {}
        if isinstance(items, list):
            for row in items:
                if isinstance(row, dict) and row.get("id"):
                    out[str(row["id"])] = row
        self._items = out

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": utc_now(),
            "watchboxes": list(self._items.values()),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._items.values()]

    def get(self, watchbox_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._items.get(watchbox_id)
            return dict(row) if row else None

    def create(
        self,
        *,
        west: float,
        south: float,
        east: float,
        north: float,
        layers: list[str],
        label: str = "",
        webhook_url: str | None = None,
        watchbox_id: str | None = None,
    ) -> dict[str, Any]:
        wid = watchbox_id or f"wb-{uuid.uuid4().hex[:12]}"
        if not _ID_RE.match(wid):
            raise ValueError("invalid watchbox id")
        cleaned_layers = _normalize_layers(layers)
        if not cleaned_layers:
            raise ValueError("layers must include at least one allowed layer")
        _validate_bbox(west, south, east, north)
        if webhook_url:
            webhook_url = _validate_webhook(webhook_url)
        row = {
            "id": wid,
            "label": (label or wid)[:120],
            "west": float(west),
            "south": float(south),
            "east": float(east),
            "north": float(north),
            "layers": cleaned_layers,
            "webhook_url": webhook_url,
            "created_at": utc_now(),
            "sku": "atlas.watchbox.subscribe@v1",
        }
        with self._lock:
            if wid in self._items:
                raise KeyError(f"watchbox already exists: {wid}")
            self._items[wid] = row
            self._save()
            return dict(row)

    def delete(self, watchbox_id: str) -> bool:
        with self._lock:
            if watchbox_id not in self._items:
                return False
            del self._items[watchbox_id]
            self._save()
            return True


def _normalize_layers(layers: list[str]) -> list[str]:
    out: list[str] = []
    for raw in layers or []:
        layer = str(raw).strip().lower()
        if layer in ALLOWED_WATCHBOX_LAYERS and layer not in out:
            out.append(layer)
    return out


def _validate_bbox(west: float, south: float, east: float, north: float) -> None:
    if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0):
        raise ValueError("west/east out of range")
    if not (-90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
        raise ValueError("south/north out of range")
    if south > north:
        raise ValueError("south must be <= north")
    # Allow antimeridian wrap (west > east); reject degenerate zero-area.
    if abs(north - south) < 1e-9 and abs(east - west) < 1e-9:
        raise ValueError("bbox has zero area")


def _validate_webhook(url: str) -> str:
    u = url.strip()
    if not (u.startswith("https://") and len(u) < 500):
        raise ValueError("webhook_url must be https://…")
    # Block obvious SSRF targets
    host = u[8:].split("/", 1)[0].lower()
    if host.startswith("127.") or host in ("localhost", "::1") or host.endswith(".local"):
        raise ValueError("webhook_url host not allowed")
    return u


def point_in_bbox(
    lat: float,
    lon: float,
    *,
    west: float,
    south: float,
    east: float,
    north: float,
) -> bool:
    if not (south <= lat <= north):
        return False
    if west <= east:
        return west <= lon <= east
    # antimeridian wrap
    return lon >= west or lon <= east


def evaluate_watchbox(
    watchbox: dict[str, Any],
    stations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return matches for stations inside the box on allowed layers."""
    layers = set(watchbox.get("layers") or []) & ALLOWED_WATCHBOX_LAYERS
    matches: list[dict[str, Any]] = []
    for s in stations or []:
        layer = str(s.get("layer") or "")
        if layer not in layers:
            continue
        try:
            lat = float(s.get("lat"))
            lon = float(s.get("lon"))
        except (TypeError, ValueError):
            continue
        if layer in EVENT_LAYERS and abs(lat) < 1e-6 and abs(lon) < 1e-6:
            continue
        if not point_in_bbox(
            lat,
            lon,
            west=float(watchbox["west"]),
            south=float(watchbox["south"]),
            east=float(watchbox["east"]),
            north=float(watchbox["north"]),
        ):
            continue
        matches.append(
            {
                "id": s.get("id"),
                "layer": layer,
                "label": s.get("label"),
                "lat": lat,
                "lon": lon,
                "headline": s.get("headline"),
                "live": bool(s.get("live")),
                "source": s.get("source"),
                "values": s.get("values") or {},
            }
        )
    return {
        "watchbox_id": watchbox.get("id"),
        "sku": "atlas.watchbox.subscribe@v1",
        "evaluated_at": utc_now(),
        "match_count": len(matches),
        "matches": matches,
        "layers": sorted(layers),
        "bbox": {
            "west": watchbox.get("west"),
            "south": watchbox.get("south"),
            "east": watchbox.get("east"),
            "north": watchbox.get("north"),
        },
    }


# Process-wide store
STORE = WatchboxStore()


def catalog_layers_for_docs() -> list[str]:
    """Layers present in STATION_CATALOG ∩ allowlist (for docs / API)."""
    present = {str(m.get("layer")) for m in STATION_CATALOG.values()}
    return sorted(present & ALLOWED_WATCHBOX_LAYERS)


__all__ = [
    "ALLOWED_WATCHBOX_LAYERS",
    "WatchboxStore",
    "STORE",
    "evaluate_watchbox",
    "point_in_bbox",
    "catalog_layers_for_docs",
]
