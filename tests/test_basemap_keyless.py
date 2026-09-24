"""A keyed (paid) basemap is never attached without its key.

Keyless CARTO tiles come back with "API KEY REQUIRED — carto.com/basemaps?apikey"
burned into the image, so attaching that layer without a key stamps the
watermark across the whole map. ATLAS must fall back to a keyless provider and
say why in the panel instead.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
MAP_LIB = PUBLIC / "assets" / "map-lib.js"

NODE = shutil.which("node")

DRIVER = """
global.window = {};
global.document = { getElementById: () => (CFG_NODE) };
require(%(lib)s);
const lib = global.window.AtlasMapLib;
const out = {
  info: lib.basemapInfo(),
  dark: lib.styleForBasemap("dark", "mercator"),
  light: lib.styleForBasemap("light", "mercator"),
  globe: lib.styleForBasemap("dark", "globe"),
  physical: lib.styleForBasemap("dark", "globe", "physical"),
};
console.log(JSON.stringify(out));
"""


def _run(config: dict | None) -> dict:
    node_stub = "null" if config is None else f"{{ textContent: {json.dumps(json.dumps(config))} }}"
    script = DRIVER.replace("CFG_NODE", node_stub) % {"lib": json.dumps(str(MAP_LIB))}
    proc = subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, timeout=60, cwd=str(ROOT)
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


needs_node = pytest.mark.skipif(NODE is None, reason="node not available")


@needs_node
def test_no_config_uses_the_keyless_provider():
    out = _run(None)
    assert out["info"] == {
        "provider": "openfreemap",
        "label": "OpenFreeMap",
        "attribution": out["info"]["attribution"],
        "keyed": False,
        "keyMissing": False,
    }
    for key in ("dark", "light", "globe"):
        assert isinstance(out[key], str), key
        assert "cartocdn" not in out[key]
        assert out[key].startswith("https://tiles.openfreemap.org/styles/")


@needs_node
@pytest.mark.parametrize("provider", ["auto", "carto"])
def test_carto_requested_without_a_key_falls_back_and_reports_it(provider: str):
    out = _run({"provider": provider, "key": ""})
    assert out["info"]["provider"] == "openfreemap"
    assert out["info"]["keyed"] is False
    # "auto" never asked for CARTO, so only an explicit request is a miss.
    assert out["info"]["keyMissing"] is (provider == "carto")
    assert "cartocdn" not in json.dumps(out["dark"])


@needs_node
def test_carto_is_attached_only_with_a_key_and_the_key_reaches_the_tiles():
    out = _run({"provider": "carto", "key": "k3y"})
    assert out["info"] == {
        "provider": "carto",
        "label": "CARTO",
        "attribution": out["info"]["attribution"],
        "keyed": True,
        "keyMissing": False,
    }
    tiles = out["dark"]["sources"]["carto"]["tiles"]
    assert tiles and all(url.endswith("@2x.png?api_key=k3y") for url in tiles)


@needs_node
def test_provider_none_serves_no_tiles_at_all():
    out = _run({"provider": "none", "key": ""})
    assert out["dark"]["sources"] == {}
    assert [layer["type"] for layer in out["dark"]["layers"]] == ["background"]


@needs_node
def test_physical_globe_surface_stays_keyless_sentinel2():
    out = _run(None)
    sources = out["physical"]["sources"]
    assert list(sources) == ["earth"]
    assert "api_key" not in json.dumps(sources)
    assert "eox.at" in json.dumps(sources)


def test_map_lib_never_builds_carto_tiles_without_a_key():
    source = MAP_LIB.read_text(encoding="utf-8")
    # Every cartocdn URL is built in one place, and that place takes a key.
    hosts = re.findall(r"basemaps\.cartocdn\.com", source)
    assert len(hosts) == 1, "CARTO URLs must be built only by cartoTiles(kind, key)"
    assert "function cartoTiles(kind, key)" in source
    assert 'cfg.provider === "carto" && cfg.key' in source


def test_html_carries_a_keyless_basemap_config_placeholder():
    for name in ("index.html", "embed.html"):
        html = (PUBLIC / name).read_text(encoding="utf-8")
        match = re.search(
            r'<script id="atlas-basemap-config" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert match, name
        assert json.loads(match.group(1)) == {"provider": "auto", "key": ""}
        # The config must be parsed before map-lib.js reads it.
        assert html.index("atlas-basemap-config") < html.index("/assets/map-lib.js")


def test_server_substitutes_the_configured_provider(monkeypatch):
    from atlas import main as main_mod

    html = '<script id="atlas-basemap-config" type="application/json">{"provider":"auto","key":""}</script>'

    monkeypatch.setattr(main_mod.settings, "basemap_provider", "carto", raising=False)
    monkeypatch.setattr(main_mod.settings, "basemap_api_key", "  k3y  ", raising=False)
    assert json.loads(
        re.search(r">(.*?)</script>", main_mod._inject_basemap_config(html)).group(1)
    ) == {"provider": "carto", "key": "k3y"}

    # Keyed provider asked for, no key configured → the client gets keyless.
    monkeypatch.setattr(main_mod.settings, "basemap_api_key", "", raising=False)
    assert json.loads(
        re.search(r">(.*?)</script>", main_mod._inject_basemap_config(html)).group(1)
    ) == {"provider": "openfreemap", "key": ""}

    # Junk provider degrades to auto rather than to a broken map.
    monkeypatch.setattr(main_mod.settings, "basemap_provider", "wat", raising=False)
    assert main_mod._basemap_config()["provider"] == "auto"


def test_injected_payload_cannot_close_the_script_tag(monkeypatch):
    from atlas import main as main_mod

    html = '<script id="atlas-basemap-config" type="application/json">{}</script>'
    monkeypatch.setattr(main_mod.settings, "basemap_provider", "carto", raising=False)
    monkeypatch.setattr(main_mod.settings, "basemap_api_key", "a</script><script>x=1", raising=False)
    out = main_mod._inject_basemap_config(html)
    assert out.count("<script") == 1
    assert "\\u003c/script" in out


TUNE_DRIVER = """
global.window = {};
global.document = { getElementById: () => (null) };
require(%(lib)s);
const lib = global.window.AtlasMapLib;
const calls = { paint: [], sources: [], layers: [] };
const present = new Set(%(layers)s);
const map = {
  getLayer: (id) => (present.has(id) ? { id } : undefined),
  getSource: (id) => undefined,
  setPaintProperty: (id, prop, value) => calls.paint.push([id, prop, value]),
  addSource: (id, spec) => { calls.sources.push([id, spec]); },
  addLayer: (spec, before) => { present.add(spec.id); calls.layers.push([spec, before]); },
};
lib.tuneVectorBasemap(map, %(kind)s);
const again = calls.paint.length;
lib.tuneVectorBasemap(map, %(kind)s);
calls.reappliedPaints = calls.paint.length - again;
console.log(JSON.stringify(calls));
"""


def _tune(kind: str, layers: list[str]) -> dict:
    script = TUNE_DRIVER % {
        "lib": json.dumps(str(MAP_LIB)),
        "layers": json.dumps(layers),
        "kind": json.dumps(kind),
    }
    proc = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


@needs_node
def test_dark_vector_style_gets_relief_and_the_atlas_palette():
    out = _tune("dark", ["background", "water", "boundary_country_z0-4", "place_city"])

    # The keyless dark style ships the Natural Earth source but no layer for it,
    # which is what made the globe a black ball.
    (sid, spec), = out["sources"]
    assert sid == "atlas-relief"
    assert spec["maxzoom"] == 6, "uncapped relief would request tiles that do not exist"
    (layer, before), = out["layers"]
    assert layer["id"] == "atlas-relief"
    assert before == "water", "relief belongs under the ocean fill"

    painted = {(lid, prop) for lid, prop, _ in out["paint"]}
    assert ("background", "background-color") in painted
    assert ("water", "fill-color") in painted
    assert ("boundary_country_z0-4", "line-color") in painted
    assert ("place_city", "text-color") in painted
    # Layers this style does not have are skipped, not crashed on.
    assert all(lid in {"background", "water", "boundary_country_z0-4", "place_city"}
               for lid, _, _ in out["paint"])
    # Second pass must be a no-op: every write fires styledata, which re-invokes it.
    assert out["reappliedPaints"] == 0


@needs_node
def test_light_vector_style_only_gets_relief():
    out = _tune("light", ["background", "water", "place_city"])
    assert [sid for sid, _ in out["sources"]] == ["atlas-relief"]
    assert out["paint"] == [], "positron already reads — do not repaint it"


@needs_node
def test_raster_and_physical_styles_are_left_alone():
    # No `water` layer → nothing to sit under, so no relief and no retint.
    out = _tune("dark", ["carto"])
    assert out["layers"] == []
    assert out["paint"] == []
