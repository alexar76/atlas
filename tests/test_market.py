"""ATLAS AIMarket peer surface — signed well-known + manifest."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlas.market import manifest, well_known
from atlas.products import PRODUCT_CAPS
from atlas.signing import Signer


def test_well_known_advertises_signer_and_caps(monkeypatch, tmp_path):
    seed = Ed25519PrivateKey.generate().private_bytes_raw()
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", base64.b64encode(seed).decode())
    # Reset singleton between tests.
    import atlas.signing as signing_mod

    signing_mod._signer = None

    wk = well_known()
    assert wk["capabilities_count"] == len(PRODUCT_CAPS)
    assert wk["signer_public_key"]
    assert wk["manifest_url"].endswith("/ai-market/v2/manifest")
    assert wk["mcp_endpoint"].endswith("/ai-market/v2/invoke")


def test_manifest_signature_verifies(monkeypatch):
    seed = Ed25519PrivateKey.generate().private_bytes_raw()
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", base64.b64encode(seed).decode())
    import atlas.signing as signing_mod

    signing_mod._signer = None

    m = manifest()
    assert m["capabilities_count"] == len(PRODUCT_CAPS)
    assert {t["capability_id"] for t in m["tools"]} == {
        "atlas.situation.brief@v1",
        "atlas.fire.weather@v1",
        "atlas.watchbox.check@v1",
        "atlas.nearest.read@v1",
    }
    sig = m["signature"]
    signer = Signer()
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(sig["public_key"]))
    try:
        pub.verify(base64.b64decode(sig["value"]), signer.manifest_canonical(m).encode())
    except InvalidSignature as exc:  # pragma: no cover
        raise AssertionError("manifest signature failed") from exc
    assert sig["public_key"] == signer.public_key_b64
