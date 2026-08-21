"""ATLAS shell translations stay complete and load before UI modules."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"


def _locale_keys(source: str, locale: str, next_locale: str | None) -> set[str]:
    start = source.index(f"    {locale}: {{")
    end = source.index(f"    {next_locale}: {{", start) if next_locale else source.index("\n  };", start)
    return set(re.findall(r'^\s+"([^"]+)":', source[start:end], flags=re.MULTILINE))


def test_every_locale_has_the_complete_interface_dictionary():
    source = (PUBLIC / "assets" / "i18n.js").read_text(encoding="utf-8")
    locales = ("en", "ru", "es", "fr", "zh")
    keys = {
        locale: _locale_keys(source, locale, locales[i + 1] if i + 1 < len(locales) else None)
        for i, locale in enumerate(locales)
    }
    assert len(keys["en"]) >= 60
    assert all(value == keys["en"] for value in keys.values())


def test_i18n_loads_before_theme_map_and_analyst():
    for name in ("index.html", "embed.html"):
        html = (PUBLIC / name).read_text(encoding="utf-8")
        assert html.index("/assets/i18n.js") < html.index("/assets/theme.js")
        assert html.index("/assets/i18n.js") < html.index("/assets/atlas.js")
        assert "data-i18n" in html


def test_dynamic_shell_copy_uses_dictionary_keys():
    atlas = (PUBLIC / "assets" / "atlas.js").read_text(encoding="utf-8")
    analyst = (PUBLIC / "assets" / "assistant.js").read_text(encoding="utf-8")
    for stale_literal in (
        'hint.textContent = "loading…"',
        'hint.textContent = "viewport error"',
        'el("detail-sub").textContent = "Fetching live reading…"',
        'el("detail-summary").textContent = "Could not load this sensor. Try again."',
    ):
        assert stale_literal not in atlas
    assert '"Analyzing live sensors…"' not in analyst
    assert '"Request failed: "' not in analyst


def test_layer_switcher_exposes_actionable_in_view_counts():
    atlas = (PUBLIC / "assets" / "atlas.js").read_text(encoding="utf-8")
    assert 'tr("layer.inView"' in atlas
    assert "actionableLayerCountsInView" in atlas
    assert "expandedParentIds" in atlas
    assert "item.cluster_parent" in atlas
