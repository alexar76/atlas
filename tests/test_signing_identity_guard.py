"""The env seed must not silently replace a pinned federation identity.

ATLAS advertises its Ed25519 public key in ``.well-known/ai-market.json`` and Hubs
pin it on first contact. ``ATLAS_SIGNING_SEED_B64`` overrides the key file, so
adding one to a deployment that already had a file republishes ATLAS under a new
identity: every Hub that pinned the old key fail-closed rejects the manifest and
freezes its ATLAS catalogue. That happened for five days across two Hubs, with the
only symptom a red bar on an analytics dashboard.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from atlas.signing import Signer


def _seed_b64(seed: bytes) -> str:
    return base64.b64encode(seed).decode()


def _pub_b64(seed: bytes) -> str:
    return base64.b64encode(
        Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
    ).decode()


def _write_key_file(path, seed: bytes) -> None:
    pub = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
    path.write_bytes(seed + pub)


def test_env_seed_conflicting_with_key_file_refuses_to_start(monkeypatch, tmp_path):
    key = tmp_path / "atlas_signing_key"
    pinned = Ed25519PrivateKey.generate().private_bytes_raw()
    _write_key_file(key, pinned)
    intruder = Ed25519PrivateKey.generate().private_bytes_raw()
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", _seed_b64(intruder))
    monkeypatch.delenv("ATLAS_SIGNING_ALLOW_KEY_ROTATION", raising=False)

    with pytest.raises(RuntimeError) as exc:
        Signer(key_path=key, pqc=False)

    msg = str(exc.value)
    # The operator has to be told both keys and both exits, or the report is a
    # dead end — diagnosing the real incident meant deriving keys by hand.
    assert _pub_b64(pinned) in msg
    assert _pub_b64(intruder) in msg
    assert "ATLAS_SIGNING_ALLOW_KEY_ROTATION" in msg
    # The refusal must not have already overwritten the pinned identity.
    assert key.read_bytes()[:32] == pinned


def test_matching_env_seed_and_key_file_start_normally(monkeypatch, tmp_path):
    key = tmp_path / "atlas_signing_key"
    seed = Ed25519PrivateKey.generate().private_bytes_raw()
    _write_key_file(key, seed)
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", _seed_b64(seed))
    monkeypatch.delenv("ATLAS_SIGNING_ALLOW_KEY_ROTATION", raising=False)

    assert Signer(key_path=key, pqc=False).public_key_b64 == _pub_b64(seed)


def test_opted_in_rotation_converges_the_key_file(monkeypatch, tmp_path):
    key = tmp_path / "atlas_signing_key"
    old = Ed25519PrivateKey.generate().private_bytes_raw()
    _write_key_file(key, old)
    new = Ed25519PrivateKey.generate().private_bytes_raw()
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", _seed_b64(new))
    monkeypatch.setenv("ATLAS_SIGNING_ALLOW_KEY_ROTATION", "1")

    assert Signer(key_path=key, pqc=False).public_key_b64 == _pub_b64(new)
    # Converged: dropping the env var later must not swap the identity back to a
    # key no Hub pins any more.
    assert key.read_bytes()[:32] == new
    monkeypatch.delenv("ATLAS_SIGNING_SEED_B64")
    assert Signer(key_path=key, pqc=False).public_key_b64 == _pub_b64(new)


def test_env_seed_without_key_file_records_the_identity(monkeypatch, tmp_path):
    key = tmp_path / "nested" / "atlas_signing_key"
    seed = Ed25519PrivateKey.generate().private_bytes_raw()
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", _seed_b64(seed))
    monkeypatch.delenv("ATLAS_SIGNING_ALLOW_KEY_ROTATION", raising=False)

    assert Signer(key_path=key, pqc=False).public_key_b64 == _pub_b64(seed)
    assert key.exists() and key.read_bytes()[:32] == seed


def test_unwritable_key_path_still_signs_from_the_env_seed(monkeypatch, tmp_path):
    # A read-only data directory is a weaker guarantee, not a reason to refuse
    # to serve: signing needs only the seed.
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    seed = Ed25519PrivateKey.generate().private_bytes_raw()
    monkeypatch.setenv("ATLAS_SIGNING_SEED_B64", _seed_b64(seed))
    try:
        assert Signer(key_path=ro / "atlas_signing_key", pqc=False).public_key_b64 == _pub_b64(seed)
    finally:
        ro.chmod(0o700)


def test_key_file_alone_is_stable_across_restarts(monkeypatch, tmp_path):
    monkeypatch.delenv("ATLAS_SIGNING_SEED_B64", raising=False)
    key = tmp_path / "atlas_signing_key"
    first = Signer(key_path=key, pqc=False).public_key_b64
    assert Signer(key_path=key, pqc=False).public_key_b64 == first
