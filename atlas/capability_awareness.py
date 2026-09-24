"""Auto-discover ATLAS map capabilities for Analyst prompts and UI i18n.

New GAIA devices / layers become Analyst-visible when they appear in
``STATION_CATALOG`` + ``LAYER_META`` (+ optional ``LAYER_HINTS`` aliases).
No per-SKU prompt edits required.
"""

from __future__ import annotations

from typing import Any

from .ai_map_actions import LAYER_HINTS
from .products import PRODUCT_CAPS, SITUATION_BRIEF_DEFAULT_LAYERS
from .stations import LAYER_META, STATION_CATALOG
from .watchboxes import ALLOWED_WATCHBOX_LAYERS


# Extra multilingual tokens for topic_scope (beyond LAYER_HINTS).
_BASE_SCOPE = (
    "sensor", "station", "atlas", "gaia", "live", "sim", "snapshot", "bbox", "map",
    "reading", "report", "briefing", "anomaly", "watchbox", "layer", "capability",
    "датчик", "станц", "карта", "показан", "отчёт", "отчет", "ситуац", "сводк",
    "анализ", "аномал", "слой",
    "sensor", "estación", "informe", "capteur", "rapport",
    "传感器", "地图", "读数", "报告",
    "aicom", "aimarket", "ecosystem", "экосистем", "hub", "factory", "argus",
    "metis", "skopos", "oracle", "mcp", "warden", "dioscuri", "helios", "theoros",
    "acex", "lottery", "mesh", "protocol", "monitor", "bridges", "provenance",
    "escrow", "channel", "фабрик", "оракул", "протокол", "монитор",
    "fábrica", "oráculo", "usine", "工厂", "预言机", "协议",
)


def layer_label(layer_key: str, locale: str = "en") -> str:
    meta = LAYER_META.get(layer_key) or {}
    labels = meta.get("labels") if isinstance(meta.get("labels"), dict) else {}
    loc = (locale or "en").lower()[:2]
    if loc in labels and labels[loc]:
        return str(labels[loc])
    return str(meta.get("label") or layer_key)


def layers_payload(*, locale: str | None = None) -> dict[str, dict[str, Any]]:
    """Snapshot/API layers block — optional localized ``label``."""
    out: dict[str, dict[str, Any]] = {}
    for key, meta in LAYER_META.items():
        row = dict(meta)
        if locale:
            row["label"] = layer_label(key, locale)
        out[key] = row
    return out


def catalog_capabilities() -> list[dict[str, str]]:
    """Unique Hub SKUs currently wired into ATLAS pins (auto from catalog)."""
    seen: dict[str, dict[str, str]] = {}
    for sid, meta in STATION_CATALOG.items():
        cap = str(meta.get("capability") or "").strip()
        if not cap or cap in seen:
            continue
        layer = str(meta.get("layer") or "")
        seen[cap] = {
            "capability": cap,
            "layer": layer,
            "example_device": sid,
            "label": layer_label(layer) if layer else "",
        }
    return sorted(seen.values(), key=lambda r: r["capability"])


def dynamic_scope_markers() -> tuple[str, ...]:
    """Topic-scope tokens derived from layers + hints + capability ids."""
    tokens: set[str] = set(_BASE_SCOPE)
    for key, meta in LAYER_META.items():
        tokens.add(key.lower())
        label = str(meta.get("label") or "")
        for part in label.lower().replace("/", " ").split():
            if len(part) >= 3:
                tokens.add(part)
        labels = meta.get("labels") if isinstance(meta.get("labels"), dict) else {}
        for loc_label in labels.values():
            for part in str(loc_label).lower().replace("/", " ").split():
                if len(part) >= 3:
                    tokens.add(part)
    for hints in LAYER_HINTS.values():
        for h in hints:
            h = (h or "").lower().strip()
            if len(h) >= 3:
                tokens.add(h)
    for row in catalog_capabilities():
        cap = row["capability"].lower()
        tokens.add(cap)
        # gaia.fire.read@v1 → fire
        for part in cap.replace("@", ".").split("."):
            if len(part) >= 3 and part not in {"gaia", "read", "v1", "atlas"}:
                tokens.add(part)
    tokens.add("watchbox")
    tokens.add("firms")
    tokens.add("safecast")
    tokens.add("cybernews")
    tokens.add("federation")
    tokens.add("federated")
    tokens.add("capability_id")
    tokens.update(GENERIC_SCOPE_MARKERS)
    return tuple(sorted(tokens, key=lambda s: (-len(s), s)))


# Generic English words that legitimately signal federation questions ("who are
# your peers?", "invoke a capability") but are far too common as substrings —
# "Shakespeare" contains "peer", "manifesto" contains "manifest". topic_scope
# matches these on word boundaries only; everything else stays substring.
GENERIC_SCOPE_MARKERS = frozenset({"peer", "peers", "manifest", "catalog", "invoke"})


def analyst_surfaces_brief() -> str:
    """Auto-generated ATLAS surfaces block for the Analyst system prompt."""
    layer_lines = []
    for key in LAYER_META:
        label = layer_label(key)
        devices = [sid for sid, m in STATION_CATALOG.items() if m.get("layer") == key]
        sample = ", ".join(devices[:4])
        more = f" (+{len(devices) - 4})" if len(devices) > 4 else ""
        layer_lines.append(f"  - {key} ({label}): {sample}{more}" if devices else f"  - {key} ({label})")

    cap_lines = [
        f"  - {r['capability']} → layer `{r['layer']}` (e.g. {r['example_device']})"
        for r in catalog_capabilities()
    ]

    product_lines = []
    for spec in PRODUCT_CAPS:
        sku = str(spec.get("capability_id") or "")
        if not sku:
            continue
        desc = str(spec.get("description") or "").split(".")[0].strip()
        product_lines.append(f"  - {sku} — {desc}" if desc else f"  - {sku}")

    defaults = ", ".join(k for k in SITUATION_BRIEF_DEFAULT_LAYERS if k in LAYER_META)
    wb = ", ".join(sorted(ALLOWED_WATCHBOX_LAYERS))
    return (
        "ATLAS SURFACES (auto-discovered from STATION_CATALOG + LAYER_META — "
        "new GAIA devices appear here when mirrored into the catalog):\n"
        f"Layers ({len(LAYER_META)}):\n" + "\n".join(layer_lines) + "\n"
        f"Hub capabilities plotted on the map ({len(cap_lines)}):\n" + "\n".join(cap_lines) + "\n"
        "Composite ATLAS products (Hub-ready invoke, from PRODUCT_CAPS):\n"
        + "\n".join(product_lines) + "\n"
        f"atlas.situation.brief@v1 default layers: {defaults} "
        "(not spacewx/geomag/argo)\n"
        "  GET /.well-known/ai-market.json · POST /ai-market/v2/invoke\n"
        "Watchboxes (ATLAS REST, subscribe then check):\n"
        "  GET/POST /api/v1/watchboxes · POST /api/v1/watchboxes/{id}/check\n"
        f"  Allowed layers: {wb}\n"
        "Note: every clickable sensor/event/observation point is agent-addressable "
        "through atlas.point.read@v1; its parent GAIA rail remains explicit."
    )


def layer_names_csv(locale: str = "en") -> str:
    return ", ".join(layer_label(k, locale) for k in LAYER_META)


def report_section_names() -> str:
    """Situation-report section list derived from catalog layers."""
    # Keep a stable narrative order: core climate → hazards → edge.
    preferred = (
        "weather", "air", "tide", "river", "marine", "grid", "quake", "energy",
        "fire", "effis", "flood", "lightning", "volcano", "alerts", "events",
        "radiation", "jamming", "gnss", "traffic", "ais", "adsb", "tsunami",
        "cyclone",
        "spacewx", "geomag", "argo",
    )
    ordered = [k for k in preferred if k in LAYER_META]
    ordered.extend(k for k in LAYER_META if k not in ordered)
    titles = [layer_label(k) for k in ordered]
    return "Overview, " + ", ".join(titles) + ", Risks & anomalies, Recommended next checks."
