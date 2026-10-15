"""Event pins must be re-fetched before they expire, or a still map drains itself.

A user left the globe open and reported "no fires, and a lot else missing". The
feed was healthy — the viewport endpoint was returning 2000 fire detections for
that exact bbox — but every ``kind: "event"`` pin (fire, quake, lightning,
alerts) had aged past ``EVENT_PIN_TTL_MS`` and been filtered out of both the map
and the per-layer "N here" counters, while station pins (no TTL) stayed put. The
header still read "fires: 115683" from the snapshot, so it looked like a
rendering bug rather than an expiry.

Nothing refetched them: ``refreshViewport()`` early-returns while the bbox key is
unchanged, and the only interval refreshed the snapshot.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
STATIC = ROOT / "atlas" / "_static"


def _atlas_js() -> str:
    return (PUBLIC / "assets" / "atlas.js").read_text(encoding="utf-8")


def _const_ms(source: str, name: str) -> int:
    m = re.search(rf"const {name} = ([^;]+);", source)
    assert m, f"{name} not found"
    return int(eval(m.group(1), {"__builtins__": {}}))  # noqa: S307 - literal arithmetic


def test_event_pins_are_refreshed_well_before_they_expire():
    source = _atlas_js()
    ttl = _const_ms(source, "EVENT_PIN_TTL_MS")
    refresh = _const_ms(source, "EVENT_PIN_REFRESH_MS")
    assert refresh < ttl, "pins would expire before anything refetched them"
    # Two full refresh attempts must fit inside the TTL, so one failed request
    # does not drain the event layers.
    assert refresh * 2 <= ttl


def test_the_refresh_timer_exists_and_clears_the_bbox_key():
    """refreshViewport() returns immediately while the bbox key is unchanged."""
    source = _atlas_js()
    m = re.search(
        r"setInterval\(\(\) => \{(.*?)\}, EVENT_PIN_REFRESH_MS\);",
        source,
        flags=re.S,
    )
    assert m, "no interval driving the event-pin refresh"
    body = m.group(1)
    assert 'lastBboxKey = ""' in body, "a stationary map would early-return forever"
    assert "refreshViewport(" in body


def test_refresh_skips_hidden_tabs():
    source = _atlas_js()
    m = re.search(r"setInterval\(\(\) => \{(.*?)\}, EVENT_PIN_REFRESH_MS\);", source, flags=re.S)
    assert "document.hidden" in m.group(1)


def test_region_cache_expires_before_event_pins():
    """The refresh must be able to produce a real request, not a cache hit forever."""
    source = _atlas_js()
    assert _const_ms(source, "REGION_TTL_MS") < _const_ms(source, "EVENT_PIN_TTL_MS")


def test_served_bundle_matches_the_source_bundle():
    """atlas/_static is what production serves; a stale copy ships the old bug."""
    assert (STATIC / "assets" / "atlas.js").read_text(encoding="utf-8") == _atlas_js()
