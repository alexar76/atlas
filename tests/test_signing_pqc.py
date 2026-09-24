"""ATLAS hybrid Ed25519 + ML-DSA-65 when ORACLE_PQC/ATLAS_PQC is on."""

from __future__ import annotations

import json
import stat

import pytest

import atlas.signing as signing_mod
from atlas.products import make_receipt
from atlas.signing import Signer

try:
    from dilithium_py.ml_dsa import ML_DSA_65  # noqa: F401

    _PQ = True
except ImportError:
    _PQ = False

pytestmark = pytest.mark.skipif(not _PQ, reason="dilithium-py not installed")


@pytest.fixture(autouse=True)
def _clean_pqc_env(monkeypatch):
    for var in ("ORACLE_PQC", "ATLAS_PQC", "ATLAS_SIGNING_SEED_B64", "ATLAS_SIGNING_ALLOW_KEY_ROTATION"):
        monkeypatch.delenv(var, raising=False)


def test_hybrid_manifest_signature_includes_pq(tmp_path):
    signer = Signer(key_path=tmp_path / "atlas_signing_key", pqc=True)
    manifest = {
        "capabilities_count": 1,
        "generated_at": "2026-01-01T00:00:00Z",
        "protocol_version": "v2",
        "tools": [{"id": "atlas.demo@v1"}],
        "by_hub": {},
    }
    sig = signer.sign_manifest(manifest)
    assert sig["algorithm"] == "ed25519"
    assert sig["pq_algorithm"] == "ml-dsa-65"
    assert sig["pq_value"] and sig["pq_public_key"]
    assert (tmp_path / "atlas_signing_key_mldsa").is_file()
    assert stat.S_IMODE((tmp_path / "atlas_signing_key_mldsa").stat().st_mode) == 0o600
    canonical = signer.manifest_canonical(manifest)
    assert Signer.verify_signature_object(
        canonical,
        sig,
        signer.public_key_b64,
        require_pq=True,
        pq_public_key_b64=sig["pq_public_key"],
    )


def test_tampering_breaks_both_manifest_layers(tmp_path):
    signer = Signer(key_path=tmp_path / "atlas_signing_key", pqc=True)
    manifest = {
        "capabilities_count": 1,
        "generated_at": "2026-01-01T00:00:00Z",
        "protocol_version": "v2",
        "tools": [{"id": "atlas.demo@v1"}],
        "by_hub": {},
    }
    signature = signer.sign_manifest(manifest)
    manifest["capabilities_count"] = 2
    assert not Signer.verify_signature_object(
        signer.manifest_canonical(manifest), signature, require_pq=True
    )


def test_hybrid_content_receipt_signs_the_same_canonical_bytes(monkeypatch, tmp_path):
    signer = Signer(key_path=tmp_path / "atlas_signing_key", pqc=True)
    monkeypatch.setattr(signing_mod, "_signer", signer)
    payload = {"ok": True, "evidence": [{"id": "sensor-1"}]}
    receipt = make_receipt(payload, capability_id="atlas.demo@v1")

    assert receipt["pq_signature_alg"] == "ml-dsa-65"
    signature = {
        "algorithm": receipt["signature_alg"],
        "public_key": receipt["public_key_b64"],
        "value": receipt["signature_b64"],
        "pq_algorithm": receipt["pq_signature_alg"],
        "pq_public_key": receipt["pq_public_key_b64"],
        "pq_value": receipt["pq_signature_b64"],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert Signer.verify_signature_object(
        canonical,
        signature,
        signer.public_key_b64,
        require_pq=True,
        pq_public_key_b64=receipt["pq_public_key_b64"],
    )
    assert not Signer.verify_signature_object(
        canonical + "tampered", signature, require_pq=True
    )


def test_pq_key_stable_across_restarts(tmp_path):
    key = tmp_path / "atlas_signing_key"
    first = Signer(key_path=key, pqc=True).sign_manifest(
        {"capabilities_count": 0, "generated_at": "t", "protocol_version": "v2", "tools": [], "by_hub": {}}
    )["pq_public_key"]
    second = Signer(key_path=key, pqc=True).sign_manifest(
        {"capabilities_count": 0, "generated_at": "t", "protocol_version": "v2", "tools": [], "by_hub": {}}
    )["pq_public_key"]
    assert first == second


def test_pqc_off_stays_classical(tmp_path):
    sig = Signer(key_path=tmp_path / "k", pqc=False).sign_manifest(
        {"capabilities_count": 0, "generated_at": "t", "protocol_version": "v2", "tools": [], "by_hub": {}}
    )
    assert "pq_value" not in sig


def test_malformed_pq_key_refuses_to_start(tmp_path):
    key = tmp_path / "atlas_signing_key"
    (tmp_path / "atlas_signing_key_mldsa").write_text("not-a-key\n")
    with pytest.raises(RuntimeError, match="corrupted"):
        Signer(key_path=key, pqc=True)
