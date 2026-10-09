"""atlas/_static is what production serves, so it must equal frontend/public.

The two trees drifted for six days: the P4 layer toggles were committed into the
packaged copy only, and the existing parity check covered a single file
(``assets/atlas.js``) — so ``map-lib.js`` diverged unnoticed, and a
``sync_package_assets.sh`` run would have deleted the newer layers. This test
compares the whole tree, in both directions; the sync script's own guard refuses
to clobber a package-side edit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
STATIC = ROOT / "atlas" / "_static"
SYNC = ROOT / "scripts" / "sync_package_assets.sh"


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.name.startswith(".")
    }


def test_the_packaged_spa_is_byte_identical_to_the_source_of_truth():
    source = _tree(PUBLIC)
    packaged = _tree(STATIC)
    assert source, "frontend/public is the source of truth and must not be empty"

    missing = sorted(set(source) - set(packaged))
    extra = sorted(set(packaged) - set(source))
    differing = sorted(
        name for name in set(source) & set(packaged) if source[name] != packaged[name]
    )
    assert not missing, f"never synced into the package: {missing}"
    assert not extra, f"only in the package (a sync would delete these): {extra}"
    assert not differing, (
        "packaged copy differs — run scripts/sync_package_assets.sh "
        f"(or --adopt if the edit was made in the package): {differing}"
    )


def test_the_sync_script_refuses_to_clobber_a_package_side_edit(tmp_path):
    """The guard, exercised on a throwaway copy of both trees."""
    fake_root = tmp_path / "atlas"
    (fake_root / "frontend").mkdir(parents=True)
    (fake_root / "atlas").mkdir(parents=True)
    (fake_root / "config").mkdir(parents=True)
    (fake_root / "scripts").mkdir(parents=True)
    (fake_root / "config" / "model_providers.example.yaml").write_text("providers: []\n")
    (fake_root / "scripts" / "sync_package_assets.sh").write_bytes(SYNC.read_bytes())

    src = fake_root / "frontend" / "public"
    pkg = fake_root / "atlas" / "_static"
    src.mkdir()
    pkg.mkdir()
    (src / "app.js").write_text("const a = 1;\n")
    (pkg / "app.js").write_text("const a = 1;\n")
    # A layer toggle added straight into the packaged copy, as actually happened.
    (pkg / "app.js").write_text("const a = 1;\nconst b = 2;\n")
    (pkg / "only-here.js").write_text("orphan\n")

    def run(*args):
        return subprocess.run(
            ["bash", str(fake_root / "scripts" / "sync_package_assets.sh"), *args],
            capture_output=True, text=True, timeout=60,
        )

    blocked = run()
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr
    assert "app.js" in blocked.stderr and "only-here.js" in blocked.stderr
    assert (pkg / "only-here.js").exists(), "a refusal must not delete anything"

    adopted = run("--adopt")
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    assert (src / "app.js").read_text() == "const a = 1;\nconst b = 2;\n"
    assert (src / "only-here.js").read_text() == "orphan\n"

    # With the trees equal again the sync is a no-op that succeeds.
    assert run().returncode == 0

    # And the ordinary workflow is never blocked: edit the source of truth, sync.
    import os, time
    (src / "app.js").write_text("const a = 1;\nconst b = 3;\n")
    os.utime(src / "app.js", (time.time() + 5, time.time() + 5))
    assert run().returncode == 0
    assert (pkg / "app.js").read_text() == "const a = 1;\nconst b = 3;\n"
