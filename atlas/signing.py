"""Ed25519 (+ optional ML-DSA-65 hybrid) signing for ATLAS Hub federation.

Canonical form matches ``aimarket_hub.signing.Signer.manifest_canonical`` so Hub
crawls verify. Seed via ``ATLAS_SIGNING_SEED_B64`` (preferred in prod) or a key
file at ``ATLAS_SIGNING_KEY_PATH`` (default ``data/atlas_signing_key``).

Hybrid post-quantum: set ``ORACLE_PQC=1`` or ``ATLAS_PQC=1`` and install
``dilithium-py``. The ML-DSA key is persisted beside the classical key as
``{key_path}_mldsa`` (seed env does not cover PQ — same rule as oracle_core).

The two classical sources are not interchangeable once a Hub has pinned us: the env seed
wins over the file, so adding one to a deployment that already had a key file
silently republishes ATLAS under a new identity. Every Hub that pinned the old
key then fail-closed rejects our manifest and freezes its ATLAS catalogue at
whatever it last indexed — for five days, across two Hubs, before anyone noticed.
So a disagreement between the two sources now refuses to start unless the
operator says the rotation is deliberate via
``ATLAS_SIGNING_ALLOW_KEY_ROTATION=1``, and a deliberate rotation rewrites the
file so the sources converge and removing the env var cannot swap us back.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from dilithium_py.ml_dsa import ML_DSA_65 as _MLDSA
    _PQ_LIB = True
except ImportError:  # pragma: no cover
    _MLDSA = None  # type: ignore[misc, assignment]
    _PQ_LIB = False


def _truthy(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in ("1", "true", "yes")


def _pqc_requested() -> bool:
    return _truthy(os.environ.get("ATLAS_PQC")) or _truthy(os.environ.get("ORACLE_PQC"))


def _pqc_required() -> bool:
    return _truthy(os.environ.get("ATLAS_PQC_REQUIRE")) or _truthy(
        os.environ.get("ORACLE_PQC_REQUIRE")
    )


def _read_pq_keypair(path: Path) -> tuple[bytes, bytes]:
    try:
        lines = path.read_text().splitlines()
        if len(lines) != 2 or not all(lines):
            raise ValueError("expected exactly two non-empty hex lines")
        pair = (bytes.fromhex(lines[0]), bytes.fromhex(lines[1]))
        if not all(pair):
            raise ValueError("empty key")
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"ML-DSA key file {path} is corrupted: {exc}") from exc
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return pair


def _load_or_make_pq(path: Path) -> tuple[bytes, bytes]:
    if path.exists():
        return _read_pq_keypair(path)
    if not _PQ_LIB:
        raise RuntimeError("ATLAS_PQC/ORACLE_PQC is on but dilithium-py is missing")
    pk, sk = _MLDSA.keygen()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = f"{pk.hex()}\n{sk.hex()}\n"
    # Mode 0600 applies from the first byte. O_EXCL also prevents two workers
    # starting together from publishing different PQ identities.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _read_pq_keypair(path)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(payload)
    except Exception:
        with contextlib.suppress(OSError):
            path.unlink()
        raise
    return pk, sk


def _ensure_keypair(path: Path) -> tuple[bytes, bytes]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if path.exists():
        raw = path.read_bytes()
        if len(raw) == 64:
            return raw[:32], raw[32:]
        raise RuntimeError(f"Ed25519 key file {path} is corrupted (size={len(raw)})")
    path.parent.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    pub = priv.public_key().public_bytes_raw()
    # 0600 from the first byte (no world-readable window), and O_EXCL so two
    # workers generating concurrently converge on one identity.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raw = path.read_bytes()
        if len(raw) == 64:
            return raw[:32], raw[32:]
        raise RuntimeError(f"Ed25519 key file {path} is corrupted (size={len(raw)})")
    try:
        os.write(fd, seed + pub)
    finally:
        os.close(fd)
    return seed, pub


def _seed_from_env() -> bytes | None:
    raw = os.environ.get("ATLAS_SIGNING_SEED_B64", "").strip()
    if not raw:
        return None
    seed = base64.b64decode(raw)
    if len(seed) != 32:
        raise RuntimeError("ATLAS_SIGNING_SEED_B64 must decode to a 32-byte seed")
    return seed


def _pub_from_seed(seed: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()


def _write_keypair(path: Path, seed: bytes, pub: bytes) -> None:
    """Record ``seed``/``pub`` at ``path`` with no world-readable window."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".new")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, seed + pub)
    finally:
        os.close(fd)
    os.replace(tmp, path)


def _reconcile_env_seed(path: Path, env_seed: bytes) -> bytes:
    """Return the public key for ``env_seed``, refusing a silent identity swap.

    The env seed overrides the key file, so an env seed added to a deployment that
    already has a file is a federation-identity rotation — and an unannounced one
    locks us out of every Hub that pinned the old key. Fail closed on a mismatch
    and make the operator opt in; converge the file either way so the identity no
    longer depends on which source is present.
    """
    env_pub = _pub_from_seed(env_seed)
    file_seed: bytes | None = None
    if path.exists():
        raw = path.read_bytes()
        if len(raw) != 64:
            raise RuntimeError(f"Ed25519 key file {path} is corrupted (size={len(raw)})")
        file_seed = raw[:32]

    if file_seed is not None and file_seed != env_seed:
        file_pub_b64 = base64.b64encode(_pub_from_seed(file_seed)).decode()
        env_pub_b64 = base64.b64encode(env_pub).decode()
        if os.environ.get("ATLAS_SIGNING_ALLOW_KEY_ROTATION", "").strip() not in ("1", "true", "yes"):
            raise RuntimeError(
                "ATLAS_SIGNING_SEED_B64 does not match the existing key file "
                f"{path}: env advertises {env_pub_b64}, the file holds "
                f"{file_pub_b64}. The env seed wins, so starting would republish "
                "ATLAS under a new federation identity and every Hub that pinned "
                "the old key would reject our manifest. Either drop the env seed "
                "to keep the pinned identity, or set "
                "ATLAS_SIGNING_ALLOW_KEY_ROTATION=1 to rotate deliberately and "
                "re-pin the new key on each Hub "
                "(POST /ai-market/v2/federation/peers/repin)."
            )
        logger.warning(
            "Rotating ATLAS federation identity: %s -> %s (operator opt-in). "
            "Every Hub that pinned the old key must be re-pinned or it will "
            "reject our manifest.", file_pub_b64, env_pub_b64,
        )

    if file_seed != env_seed:
        # Converge the file on the env seed so a later env removal cannot swap
        # the identity back to a key no Hub pins any more. Best-effort: signing
        # works from the env seed alone, so a read-only data directory is a
        # weaker guarantee, not a reason to refuse to serve.
        try:
            _write_keypair(path, env_seed, env_pub)
        except OSError as exc:
            logger.warning(
                "Could not record the signing identity at %s (%s). Signing still "
                "works from ATLAS_SIGNING_SEED_B64, but dropping that env var "
                "would change the advertised key.", path, exc,
            )
    return env_pub


class Signer:
    def __init__(self, key_path: str | Path | None = None, *, pqc: bool | None = None) -> None:
        settings_path: str | None = None
        try:
            from .config import get_settings

            settings_path = getattr(get_settings(), "signing_key_path", None)
        except Exception:  # noqa: BLE001 — signing must not depend on config health
            settings_path = None
        path = Path(
            key_path
            or os.environ.get("ATLAS_SIGNING_KEY_PATH")
            or settings_path
            or "data/atlas_signing_key"
        )
        self.key_path = path
        env_seed = _seed_from_env()
        if env_seed is not None:
            self._seed = env_seed
            self._pub_bytes = _reconcile_env_seed(self.key_path, env_seed)
        else:
            self._seed, self._pub_bytes = _ensure_keypair(self.key_path)
        self._public_key_b64 = base64.b64encode(self._pub_bytes).decode()

        if pqc is None:
            pqc = _pqc_requested()
        self._pq: tuple[bytes, bytes] | None = None
        if pqc:
            if not _PQ_LIB:
                raise RuntimeError(
                    "ATLAS_PQC/ORACLE_PQC is on but dilithium-py is missing — "
                    "install dilithium-py in the ATLAS image"
                )
            self._pq = _load_or_make_pq(Path(f"{self.key_path}_mldsa"))

    @property
    def public_key_b64(self) -> str:
        return self._public_key_b64

    def sign_canonical(self, canonical: str) -> str:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        sig = Ed25519PrivateKey.from_private_bytes(self._seed).sign(canonical.encode())
        return base64.b64encode(sig).decode()

    def sign_payload(self, canonical: str) -> dict[str, str]:
        obj: dict[str, str] = {
            "algorithm": "ed25519",
            "public_key": self.public_key_b64,
            "value": self.sign_canonical(canonical),
        }
        if self._pq is not None:
            pk, sk = self._pq
            obj["pq_algorithm"] = "ml-dsa-65"
            obj["pq_public_key"] = base64.b64encode(pk).decode()
            obj["pq_value"] = base64.b64encode(_MLDSA.sign(sk, canonical.encode())).decode()
        return obj

    @staticmethod
    def verify_signature_object(
        canonical: str,
        signature: dict[str, Any],
        ed_public_key_b64: str | None = None,
        *,
        require_pq: bool | None = None,
        pq_public_key_b64: str | None = None,
    ) -> bool:
        """Verify both layers and optionally pin the PQ identity."""
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        if signature.get("algorithm") != "ed25519":
            return False
        ed_key = ed_public_key_b64 or signature.get("public_key")
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(ed_key or "")).verify(
                base64.b64decode(signature.get("value", "")), canonical.encode()
            )
        except (InvalidSignature, ValueError):
            return False

        must_pq = _pqc_required() if require_pq is None else bool(require_pq)
        if not signature.get("pq_value"):
            return not must_pq
        if signature.get("pq_algorithm") != "ml-dsa-65" or not _PQ_LIB:
            return False
        presented = signature.get("pq_public_key", "")
        if pq_public_key_b64 and presented != pq_public_key_b64:
            return False
        try:
            return bool(
                _MLDSA.verify(
                    base64.b64decode(presented),
                    canonical.encode(),
                    base64.b64decode(signature["pq_value"]),
                )
            )
        except Exception:
            return False

    def manifest_canonical(self, manifest: dict[str, Any]) -> str:
        tools = manifest.get("tools", [])
        tools_hash = hashlib.sha256(
            json.dumps(tools, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        by_hub_hash = hashlib.sha256(
            json.dumps(manifest.get("by_hub", {}), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        return (
            f"capabilities_count:{manifest.get('capabilities_count', 0)}"
            f"|generated_at:{manifest.get('generated_at', '')}"
            f"|protocol_version:{manifest.get('protocol_version', 'v1')}"
            f"|tools_hash:{tools_hash}"
            f"|by_hub_hash:{by_hub_hash}"
        )

    def sign_manifest(self, manifest: dict[str, Any]) -> dict[str, str]:
        return self.sign_payload(self.manifest_canonical(manifest))


_signer: Signer | None = None


def get_signer() -> Signer:
    global _signer
    if _signer is None:
        _signer = Signer()
    return _signer


__all__ = ["Signer", "get_signer"]
