"""Live AIMarket Hub federation slice for ATLAS Analyst.

Sensor numbers stay on the ATLAS snapshot. This module supplies a compact,
read-only view of what the Hub currently indexes (peers + capability ids) so
the Analyst can answer federation / "what exists to invoke" questions without
inventing SKUs.

Failures are soft: unreachable Hub → ``ok: false`` payload; Analyst must say so.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger("atlas.federation")

_DEFAULT_HUB = "https://modelmarket.dev"
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}


def hub_base_url() -> str:
    settings = get_settings()
    raw = (getattr(settings, "hub_url", None) or _DEFAULT_HUB).strip().rstrip("/")
    return raw or _DEFAULT_HUB


def _compact_tool(row: dict[str, Any]) -> dict[str, Any] | None:
    cap = str(row.get("capability_id") or "").strip()
    if not cap:
        return None
    desc = str(row.get("description") or "").strip()
    if len(desc) > 160:
        desc = desc[:157] + "…"
    out: dict[str, Any] = {
        "capability_id": cap,
        "description": desc,
        "source_hub": row.get("source_hub"),
        "source_hub_name": row.get("source_hub_name"),
        "product_id": row.get("product_id"),
    }
    price = row.get("price_per_call_usd")
    if isinstance(price, (int, float)):
        out["price_per_call_usd"] = float(price)
    trust = row.get("trust_score")
    if isinstance(trust, (int, float)):
        out["trust_score"] = round(float(trust), 4)
    return out


def _fetch_federation_slice(*, timeout_s: float = 6.0) -> dict[str, Any]:
    root = hub_base_url()
    well_known_url = f"{root}/.well-known/ai-market.json"
    manifest_url = f"{root}/ai-market/v2/manifest"
    peers_url = f"{root}/ai-market/v2/federation/peers"

    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        wk: dict[str, Any] = {}
        try:
            r = client.get(well_known_url)
            if r.status_code == 200:
                body = r.json()
                if isinstance(body, dict):
                    wk = body
        except (httpx.HTTPError, ValueError) as exc:
            log.debug("hub well-known fetch failed: %s", exc)

        manifest: dict[str, Any] = {}
        try:
            r = client.get(manifest_url)
            if r.status_code == 200:
                body = r.json()
                if isinstance(body, dict):
                    manifest = body
        except (httpx.HTTPError, ValueError) as exc:
            log.debug("hub manifest fetch failed: %s", exc)

        peers_raw: list[Any] = []
        try:
            r = client.get(peers_url)
            if r.status_code == 200:
                body = r.json()
                if isinstance(body, dict) and isinstance(body.get("peers"), list):
                    peers_raw = body["peers"]
                elif isinstance(body, list):
                    peers_raw = body
        except (httpx.HTTPError, ValueError) as exc:
            log.debug("hub peers fetch failed: %s", exc)

    if not peers_raw and isinstance(wk.get("peers"), list):
        peers_raw = wk["peers"]

    peers: list[dict[str, Any]] = []
    for p in peers_raw:
        if not isinstance(p, dict):
            continue
        cats = p.get("categories")
        if isinstance(cats, list):
            cats = [str(c) for c in cats[:16]]
        else:
            cats = []
        peers.append(
            {
                "url": p.get("url") or p.get("well_known_url"),
                "name": p.get("name"),
                "capabilities_count": p.get("capabilities_count"),
                "trust_score": p.get("trust_score"),
                "categories": cats,
                "last_crawl": p.get("last_crawl"),
            }
        )

    tools_in = manifest.get("tools") if isinstance(manifest.get("tools"), list) else []
    capabilities: list[dict[str, Any]] = []
    for row in tools_in:
        if not isinstance(row, dict):
            continue
        compact = _compact_tool(row)
        if compact:
            capabilities.append(compact)

    # Prefer GAIA / physical + atlas-relevant first, then oracles — keeps prompt useful
    # when the federated catalog is large.
    def _cap_rank(c: dict[str, Any]) -> tuple[int, str]:
        hub = str(c.get("source_hub") or "").lower()
        cid = str(c.get("capability_id") or "").lower()
        if "iot.modelmarket" in hub or cid.startswith("gaia."):
            return (0, cid)
        if "oracle" in hub or any(
            cid.startswith(p)
            for p in ("platon.", "chronos.", "lumen.", "lattice.", "turing.")
        ):
            return (1, cid)
        return (2, cid)

    capabilities.sort(key=_cap_rank)
    max_caps = int(getattr(get_settings(), "federation_capability_limit", 80) or 80)
    max_caps = max(20, min(max_caps, 120))
    capabilities = capabilities[:max_caps]

    by_hub = manifest.get("by_hub") if isinstance(manifest.get("by_hub"), dict) else {}
    hubs_indexed: list[dict[str, Any]] = []
    for url, meta in by_hub.items():
        if url == "local":
            continue
        if isinstance(meta, dict):
            hubs_indexed.append(
                {
                    "url": url,
                    "name": meta.get("name") or url,
                    "capabilities": meta.get("capabilities") or meta.get("count"),
                }
            )
        elif isinstance(meta, int):
            hubs_indexed.append({"url": url, "capabilities": meta})

    ok = bool(capabilities or peers or wk)
    return {
        "ok": ok,
        "hub_url": root,
        "well_known_url": well_known_url,
        "manifest_url": manifest_url,
        "hub_version": wk.get("hub_version"),
        "products_count": wk.get("products_count"),
        "capabilities_count": wk.get("capabilities_count"),
        "federated_capabilities_count": wk.get("federated_capabilities_count")
        or manifest.get("federated_capabilities")
        or len(capabilities),
        "total_capabilities": manifest.get("total_capabilities") or len(capabilities),
        "peers": peers,
        "hubs_indexed": hubs_indexed,
        "capabilities": capabilities,
        "note": (
            "Live Hub index (read-only). Capability ids here are invocable via Hub; "
            "ATLAS sensor numbers still come only from SNAPSHOT stations."
            if ok
            else "Hub federation unreachable — do not invent federation SKUs."
        ),
    }


def _refresh_sync() -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = _fetch_federation_slice(
            timeout_s=float(getattr(settings, "federation_timeout_s", 6.0) or 6.0)
        )
    except Exception as exc:  # noqa: BLE001 — soft fail for Analyst
        log.warning("federation slice failed: %s", exc)
        payload = {
            "ok": False,
            "hub_url": hub_base_url(),
            "peers": [],
            "capabilities": [],
            "error": type(exc).__name__,
            "note": "Hub federation unreachable — do not invent federation SKUs.",
        }

    with _CACHE_LOCK:
        _CACHE["at"] = time.monotonic()
        _CACHE["payload"] = payload
        _CACHE["refreshing"] = False
    return dict(payload)


def federation_slice(*, force: bool = False) -> dict[str, Any]:
    """TTL-cached Hub federation summary for Analyst prompts.

    The no-force path never blocks: it is called from the async ``/api/ai/ask``
    handler on the event loop, and the underlying fetch is up to 3 sequential
    HTTP GETs. On a stale/cold cache it kicks a daemon-thread refresh and
    serves the stale copy (or a "warming" placeholder) immediately.
    """
    ttl = float(getattr(get_settings(), "federation_cache_ttl_s", 120.0) or 120.0)
    ttl = max(30.0, min(ttl, 900.0))
    now = time.monotonic()
    if force:
        return _refresh_sync()
    with _CACHE_LOCK:
        cached = _CACHE.get("payload")
        at = float(_CACHE.get("at") or 0.0)
        # A failed fetch only earns a short retry window — a single DNS blip
        # must not poison the Analyst's federation view for the full TTL.
        eff_ttl = ttl if (isinstance(cached, dict) and cached.get("ok")) else min(ttl, 15.0)
        if cached is not None and (now - at) < eff_ttl:
            return dict(cached)
        if not _CACHE.get("refreshing"):
            _CACHE["refreshing"] = True
            threading.Thread(
                target=_refresh_sync, daemon=True, name="atlas-federation-refresh"
            ).start()
        if cached is not None:
            return dict(cached)
    return {
        "ok": False,
        "hub_url": hub_base_url(),
        "peers": [],
        "capabilities": [],
        "note": "Hub federation warming up — do not invent federation SKUs.",
    }


def clear_federation_cache() -> None:
    with _CACHE_LOCK:
        _CACHE["at"] = 0.0
        _CACHE["payload"] = None
        _CACHE["refreshing"] = False


__all__ = [
    "federation_slice",
    "clear_federation_cache",
    "hub_base_url",
]
