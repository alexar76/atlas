"""The five documented legends must match the map's runtime layer metadata."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ATLAS_DIR = Path(__file__).resolve().parents[1]
_SCRIPT_DIRS = (
    ATLAS_DIR / "scripts",
    ATLAS_DIR.parent / "scripts",
)
for _scripts in _SCRIPT_DIRS:
    if (_scripts / "atlas_legend.py").is_file():
        sys.path.insert(0, str(_scripts))
        break
else:
    pytest.skip("atlas_legend.py not available in this checkout", allow_module_level=True)

from atlas_legend import TARGETS, render_legend  # noqa: E402


@pytest.mark.parametrize("target", TARGETS, ids=lambda target: target.lang)
def test_localized_legend_is_generated_from_runtime_catalog(target):
    assert target.full.read_text(encoding="utf-8") == render_legend(target.lang)


@pytest.mark.parametrize(
    "path",
    [
        ATLAS_DIR / "docs" / "GUIDE.md",
        ATLAS_DIR / "docs" / "i18n" / "GUIDE.ru.md",
        ATLAS_DIR / "docs" / "i18n" / "GUIDE.es.md",
        ATLAS_DIR / "docs" / "i18n" / "GUIDE.fr.md",
        ATLAS_DIR / "docs" / "i18n" / "GUIDE.zh.md",
    ],
)
def test_every_operator_guide_links_the_current_legend(path):
    text = path.read_text(encoding="utf-8")
    assert "LEGEND" in text
    assert "24 layers" not in text
    assert "24 слоя" not in text
    assert "24 capas" not in text
    assert "24 couches" not in text
    assert "24 个图层" not in text


@pytest.mark.parametrize(
    "path",
    [
        ATLAS_DIR / "docs" / "OPERATOR-USE-CASES.md",
        ATLAS_DIR / "docs" / "i18n" / "OPERATOR-USE-CASES.ru.md",
        ATLAS_DIR / "docs" / "i18n" / "OPERATOR-USE-CASES.es.md",
        ATLAS_DIR / "docs" / "i18n" / "OPERATOR-USE-CASES.fr.md",
        ATLAS_DIR / "docs" / "i18n" / "OPERATOR-USE-CASES.zh.md",
    ],
)
def test_p12_pins_and_field_skus_are_documented_in_every_locale(path):
    text = path.read_text(encoding="utf-8")
    for marker in (
        "at-wx-", "lt-wx-", "lt-hydro-", "lv-wx-", "lv-hydro-", "vic-",
        "rte-grid-01", "ie-river-", "jp-wx-", "jma-quake-01", "jma-typhoon-01",
        "cz-wx-", "kr-wx-", "gfm-flood-01", "atlas.mesh.sample@v1",
        "atlas.field.consensus@v1", "atlas.field.posterior@v1", "atlas.field.shape@v1",
    ):
        assert marker in text, f"{path.name}: {marker}"


@pytest.mark.parametrize("target", TARGETS, ids=lambda target: target.lang)
def test_every_localized_legend_samples_each_p12_layer_family(target):
    text = target.full.read_text(encoding="utf-8")
    for marker in (
        "at-wx-", "lt-wx-", "lv-wx-", "jp-wx-", "cz-wx-", "kr-wx-",
        "lt-hydro-", "lv-hydro-", "ie-river-", "vic-", "gfm-flood-",
        "rte-grid-", "jma-quake-", "jma-typhoon-",
    ):
        assert marker in text, f"{target.path}: {marker}"
