"""Geographic watchboxes over free-to-commercialize ATLAS layers.

A watchbox is a bbox + layer filter. ``check`` returns stations currently
inside the box whose layer is allowlisted (never NC-only commercial feeds —
those are not in ATLAS at all).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import uuid
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .fleet import EVENT_LAYERS
from .geo import utc_now
from .stations import LAYER_META, STATION_CATALOG

# Layers we may sell / alert on. Matches free-to-commercialize GAIA relays + SIM.
ALLOWED_WATCHBOX_LAYERS = frozenset(LAYER_META.keys())

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{4,64}$")

# Never leaves the process through an HTTP read. `webhook_secret` must be stored in the
# clear (the delivery loop HMACs with it); the owner token must NOT be, so only its
# digest is persisted and the plaintext exists exactly once, in the create response.
SECRET_FIELDS = frozenset({"webhook_secret", "owner_token", "owner_token_sha256"})


def _default_path() -> Path:
    """Registry location, env-overridable so prod can point at mounted storage.

    The repo-relative default resolves to /app/data inside the container, which
    `docker compose up -d --build` wipes — so a subscription (and its HMAC secret) did
    not survive a redeploy. The only mounted volume is atlas_data:/data, and compose now
    sets ATLAS_WATCHBOX_PATH there. Kept repo-relative as the fallback so local dev and
    the test suite behave as before.
    """
    env = os.environ.get("ATLAS_WATCHBOX_PATH", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "data" / "watchboxes.json"


class WatchboxStore:
    """JSON-backed watchbox registry (single-process)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_path()
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

    def list(self, *, include_inactive: bool = True) -> list[dict[str, Any]]:
        """Full rows, INCLUDING webhook_secret — for the delivery loop, not for the API.

        Callers that serve this over HTTP must use `public_row`. Kept as one method
        rather than two stores because the loop genuinely needs the secret and a second
        copy of the registry would be a second thing to keep in sync.

        `include_inactive=False` is the delivery loop's view: an unsubscribed watchbox
        stops being checked, but its row (and therefore its evidence log) stays.
        """
        with self._lock:
            rows = [dict(v) for v in self._items.values()]
        if include_inactive:
            return rows
        return [r for r in rows if is_active(r)]

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
        """Create a watchbox and mint its owner token.

        The returned dict carries the plaintext `owner_token`; the stored row carries
        only its SHA-256. That asymmetry is the point — the registry file, a backup of
        it, or any future read endpoint cannot hand out ownership of a subscription.
        """
        wid = watchbox_id or f"wb-{uuid.uuid4().hex[:12]}"
        if not _ID_RE.match(wid):
            raise ValueError("invalid watchbox id")
        cleaned_layers = _normalize_layers(layers)
        if not cleaned_layers:
            raise ValueError("layers must include at least one allowed layer")
        _validate_bbox(west, south, east, north)
        if webhook_url:
            webhook_url = _validate_webhook(webhook_url)
        owner_token = secrets.token_urlsafe(32)
        row = {
            "id": wid,
            "label": (label or wid)[:120],
            "west": float(west),
            "south": float(south),
            "east": float(east),
            "north": float(north),
            "layers": cleaned_layers,
            "webhook_url": webhook_url,
            # Per-watchbox HMAC secret so the receiver can distinguish our POST from
            # anyone who learned the URL. Generated here, returned once by the create
            # endpoint, and never echoed by list/get — a secret that every reader of the
            # registry can fetch is not a secret.
            "webhook_secret": (secrets.token_urlsafe(32) if webhook_url else None),
            # Ownership. Only the digest is persisted: the token proves who may read the
            # box and its evidence log, and nothing that can be read back out of the
            # registry may be sufficient to impersonate the owner.
            "owner_token_sha256": hash_owner_token(owner_token),
            "active": True,
            "unsubscribed_at": None,
            "created_at": utc_now(),
            "sku": "atlas.watchbox.subscribe@v1",
        }
        with self._lock:
            if wid in self._items:
                raise KeyError(f"watchbox already exists: {wid}")
            self._items[wid] = row
            self._save()
            # The ONLY time the plaintext exists outside the caller's hands.
            return {**row, "owner_token": owner_token}

    def unsubscribe(self, watchbox_id: str) -> dict[str, Any] | None:
        """Stop monitoring, keep the evidence. Idempotent.

        Deletion used to drop the registry row, which orphaned the monitor-log rows: the
        signed checks still existed in SQLite but `GET /watchboxes/{id}/log` resolves the
        registry first, so cancelling a subscription silently made its own evidence
        unreachable. For a product whose value is "prove you were monitoring", that is
        the worst possible failure mode — worse than refusing to delete at all. So the
        default is an unsubscribe: the loop skips the row, the owner keeps their log.
        """
        with self._lock:
            row = self._items.get(watchbox_id)
            if row is None:
                return None
            if row.get("active", True):
                row["active"] = False
                row["unsubscribed_at"] = utc_now()
                self._save()
            return dict(row)

    def purge(self, watchbox_id: str) -> bool:
        """Hard-remove the registry row — this DOES orphan the monitor log.

        Deliberately separate from `unsubscribe` and operator-only at the HTTP layer:
        destroying the path to someone's evidence must be an explicit act, not the
        default meaning of DELETE.
        """
        with self._lock:
            if watchbox_id not in self._items:
                return False
            del self._items[watchbox_id]
            self._save()
            return True


def public_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """A watchbox row safe to serve over HTTP: every secret is stripped.

    The HMAC secret and the owner token are each shown exactly once, in the create
    response. Anything that lists or fetches a watchbox goes through here, so adding a
    new read endpoint cannot leak either of them by omission — the filter is a denylist
    of secret fields rather than a single hard-coded key, so a future secret is covered
    by adding it to `SECRET_FIELDS`.
    """
    if row is None:
        return None
    out = {k: v for k, v in row.items() if k not in SECRET_FIELDS}
    out["webhook_configured"] = bool(row.get("webhook_url"))
    out["active"] = is_active(row)
    return out


def is_active(row: dict[str, Any] | None) -> bool:
    """Rows written before unsubscribe existed have no `active` key and are live."""
    return bool((row or {}).get("active", True))


def hash_owner_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def owns(row: dict[str, Any] | None, supplied: str) -> bool:
    """Constant-time owner-token check.

    Fails closed on rows minted before owner tokens existed: they carry no digest, so
    no token can claim them and they stay operator-only.
    """
    stored = str((row or {}).get("owner_token_sha256") or "")
    if not stored or not supplied:
        return False
    return secrets.compare_digest(stored, hash_owner_token(supplied))


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
    # Block obvious SSRF targets. Slicing the authority by hand kept the port and any
    # userinfo attached, so "localhost:8080" and "user@localhost" both walked straight
    # past the name checks; urlsplit gives the bare host instead.
    try:
        host = (urlsplit(u).hostname or "").lower()
    except ValueError as exc:  # malformed authority / bad IPv6 literal
        raise ValueError("webhook_url host not allowed") from exc
    if not host or host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        raise ValueError("webhook_url host not allowed")
    try:
        ip = ip_address(host)
    except ValueError:
        return u  # a name — resolution is the delivery layer's problem
    # Literal IPs: loopback, RFC1918, and link-local (169.254.169.254 is the cloud
    # metadata endpoint) are the targets an SSRF is actually aimed at.
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_unspecified:
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
    "SECRET_FIELDS",
    "WatchboxStore",
    "STORE",
    "evaluate_watchbox",
    "hash_owner_token",
    "is_active",
    "owns",
    "point_in_bbox",
    "public_row",
    "catalog_layers_for_docs",
]
