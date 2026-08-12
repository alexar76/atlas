"""ATLAS Analyst auto-discovers layers / Hub SKUs from the catalog."""

from __future__ import annotations

from atlas.capability_awareness import (
    analyst_surfaces_brief,
    catalog_capabilities,
    dynamic_scope_markers,
    layer_label,
    report_section_names,
)
from atlas.stations import LAYER_META, STATION_CATALOG
from atlas.topic_scope import out_of_scope_reason
from atlas import ai_assistant as ai


def test_layer_labels_five_locales():
    for key in ("fire", "radiation", "jamming", "traffic"):
        assert key in LAYER_META
        labels = LAYER_META[key]["labels"]
        for loc in ("en", "ru", "es", "fr", "zh"):
            assert labels.get(loc), f"{key}.{loc}"
            assert layer_label(key, loc) == labels[loc]


def test_catalog_capabilities_include_new_skus():
    caps = {r["capability"] for r in catalog_capabilities()}
    for needle in (
        "gaia.fire.read@v1",
        "gaia.radiation.read@v1",
        "gaia.jamming.read@v1",
        "gaia.adsb.read@v1",
        "gaia.ais.read@v1",
    ):
        assert needle in caps


def test_analyst_surfaces_brief_auto():
    brief = analyst_surfaces_brief()
    assert "firms-fire-01" in brief
    assert "gaia.fire.read@v1" in brief
    assert "atlas.watchbox.check@v1" in brief
    assert "atlas.situation.brief@v1" in brief
    assert str(len(LAYER_META)) in brief or f"Layers ({len(LAYER_META)})" in brief


def test_system_prompt_includes_auto_surfaces():
    prompt = ai.build_system_prompt(locale="en", live_json="{}", report=True)
    assert "ATLAS SURFACES" in prompt
    assert "firms-fire-01" in prompt or "gaia.fire.read@v1" in prompt
    assert "Wildfire" in prompt or "fire" in prompt
    assert "watchbox" in prompt.lower()
    # report sections derived from catalog
    assert "Radiation" in report_section_names() or "radiation" in report_section_names().lower()


def test_scope_accepts_wildfire_question():
    markers = dynamic_scope_markers()
    assert "fire" in markers or "wildfire" in markers
    assert "radiation" in markers
    assert "jamming" in markers or "gnss" in markers
    assert out_of_scope_reason("Show wildfire hotspots from FIRMS on the map please") is None
    assert out_of_scope_reason("What is Safecast radiation near Fukushima right now?") is None


def test_new_catalog_device_surfaces_without_prompt_edit():
    """Adding a catalog entry is enough — brief enumerates STATION_CATALOG."""
    assert "firms-fire-01" in STATION_CATALOG
    assert STATION_CATALOG["firms-fire-01"]["capability"] == "gaia.fire.read@v1"
    assert any(r["example_device"] == "firms-fire-01" for r in catalog_capabilities())
