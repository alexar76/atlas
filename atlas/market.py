"""AIMarket peer surface for ATLAS composite products.

ATLAS remains the map; these endpoints publish the three ship-first SKUs so Hub
federation can crawl them once seeded. Invoke is free on the public edge today
(same honesty as GAIA demo reads) — Hub escrow attaches when ATLAS is registered.
"""

from __future__ import annotations

from typing import Any

from . import __version__
from .config import get_settings
from .geo import utc_now
from .products import PRODUCT_CAPS
from .signing import get_signer


def well_known() -> dict[str, Any]:
    settings = get_settings()
    base = (settings.public_url or "https://atlas.modelmarket.dev").rstrip("/")
    signer = get_signer()
    return {
        "name": "ATLAS — planetary sensor map & composite briefs",
        "protocol_versions": ["v2"],
        "protocol_version": "v2",
        "hub_version": __version__,
        "hub_name": "ATLAS",
        "hub_url": base,
        "manifest_url": f"{base}/ai-market/v2/manifest",
        "mcp_endpoint": f"{base}/ai-market/v2/invoke",
        "capabilities_count": len(PRODUCT_CAPS),
        "signer_public_key": signer.public_key_b64,
        "description": (
            "Planetary MapLibre sensor map over GAIA relays, plus composite Hub SKUs: "
            "watchbox check, wildfire+weather desk note, cross-layer situation briefs, "
            "and nearest LIVE pin by lat/lon. LIVE only with provenance; refuse when coverage is empty."
        ),
        "categories": [
            "iot",
            "sensors",
            "physical-data",
            "geospatial",
            "risk-brief",
            "wildfire",
            "watchbox",
        ],
        "ecosystem": {
            "product": "atlas.map",
            "related": ["gaia.gateway", "aimarket-hub", "alien-monitor"],
        },
    }


def manifest() -> dict[str, Any]:
    settings = get_settings()
    base = (settings.public_url or "https://atlas.modelmarket.dev").rstrip("/")
    signer = get_signer()
    tools = []
    for cap in PRODUCT_CAPS:
        tools.append(
            {
                **cap,
                "source_hub": base,
                "source_hub_name": "ATLAS",
                "invoke_url": f"{base}/ai-market/v2/invoke",
                "trust_score": 0.5,
            }
        )
    body: dict[str, Any] = {
        "protocol_version": "v2",
        "release_version": __version__,
        "generated_at": utc_now(),
        "base_url": base,
        "products_count": 1,
        "capabilities_count": len(tools),
        "total_capabilities": len(tools),
        "local_capabilities": len(tools),
        "federated_capabilities": 0,
        "hubs_indexed": 1,
        "tools": tools,
        "by_hub": {base: {"name": "ATLAS", "capabilities": len(tools)}},
    }
    body["signature"] = signer.sign_manifest(body)
    return body


__all__ = ["well_known", "manifest"]
