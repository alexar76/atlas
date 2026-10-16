"""Receipts and evidence: signed product receipts and their cache, evidence records, the GNSS
envelope and citations.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

from .. import __version__
from ..config import get_settings
from ..formatters import headline
from ..geo import utc_now


def make_receipt(payload: dict[str, Any], *, capability_id: str) -> dict[str, Any]:
    """Tamper-evident content receipt.

    sha256 alone is forgeable by anyone who edits the payload and recomputes;
    the Ed25519 signature over the canonical body (same key as the manifest)
    is what makes the receipt attributable to this ATLAS instance. When PQC is
    enabled the exact same canonical bytes also carry an ML-DSA-65 signature.
    """
    body = {k: v for k, v in payload.items() if k not in ("receipt", "receipt_url", "verifier_url")}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    receipt = {
        "algorithm": "sha256",
        "digest": digest,
        "service": "atlas",
        "version": __version__,
        "ts": utc_now(),
        "capability_id": capability_id,
    }
    try:
        from ..signing import get_signer

        signer = get_signer()
        signature = signer.sign_payload(canonical)
        receipt["signature_alg"] = signature["algorithm"]
        receipt["signature_b64"] = signature["value"]
        receipt["public_key_b64"] = signature["public_key"]
        if signature.get("pq_value"):
            receipt["pq_signature_alg"] = signature["pq_algorithm"]
            receipt["pq_signature_b64"] = signature["pq_value"]
            receipt["pq_public_key_b64"] = signature["pq_public_key"]
        receipt["signature_status"] = "signed"
    except ModuleNotFoundError:
        # Developer environments created before cryptography became a required
        # runtime dependency may still exercise deterministic product logic.
        # Never disguise that digest as an attributable signature. In the Docker
        # build cryptography is mandatory; key/configuration errors fail closed.
        receipt["signature_status"] = "unavailable_missing_runtime_dependency"
    return receipt


VERIFIER_ORIGIN = "https://verify.modelmarket.dev"


_RECEIPT_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()


_RECEIPT_CACHE_MAX = 64


_STATE_RANK = {
    "severe_degradation": 5,
    "degraded": 4,
    "mild_degradation": 3,
    "normal": 2,
    "unknown": 1,
}


_CLAIM_RANK = {
    "spoofing_reported": 5,
    "jamming_reported": 4,
    "derived_degradation": 3,
    "observed_metric": 2,
    "historical_proxy": 1,
}


def remember_receipt(receipt: dict[str, Any]) -> None:
    digest = str(receipt.get("digest") or "")
    if not digest:
        return
    products._RECEIPT_CACHE[digest] = dict(receipt)
    products._RECEIPT_CACHE.move_to_end(digest)
    while len(products._RECEIPT_CACHE) > products._RECEIPT_CACHE_MAX:
        products._RECEIPT_CACHE.popitem(last=False)


def lookup_receipt(digest: str) -> dict[str, Any] | None:
    row = products._RECEIPT_CACHE.get(digest)
    return dict(row) if isinstance(row, dict) else None


def _receipt_links(receipt: dict[str, Any]) -> tuple[str, str]:
    digest = str(receipt.get("digest") or "")
    settings = get_settings()
    base = (settings.public_url or "https://atlas.modelmarket.dev").rstrip("/")
    receipt_url = f"{base}/api/v1/receipts/{digest}" if digest else f"{base}/api/v1/receipts"
    verifier_url = f"{products.VERIFIER_ORIGIN}/?receipt_url={quote(receipt_url, safe='')}"
    return receipt_url, verifier_url


def _worst_state(states: list[str]) -> str:
    return max(states, key=lambda s: products._STATE_RANK.get(s, 0), default="unknown")


def _strongest_claim(levels: list[str]) -> str | None:
    ranked = [level for level in levels if level in products._CLAIM_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda level: products._CLAIM_RANK[level])


def _evidence_records(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Spec §8 evidence rows derived from the observations already in the envelope."""
    out: list[dict[str, Any]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        values = obs.get("values") if isinstance(obs.get("values"), dict) else {}
        out.append({
            "evidence_id": obs.get("id") or obs.get("point_id"),
            "point_id": obs.get("id") or obs.get("point_id"),
            "source_id": obs.get("parent_id") or obs.get("source"),
            "evidence_class": "ground_gnss_station",
            "claim_level": obs.get("claim_level") or "observed_metric",
            "claim_class": obs.get("claim_class"),
            "state": obs.get("state"),
            "degradation_score": obs.get("degradation_score"),
            "source": obs.get("source"),
            "lat": obs.get("lat") if obs.get("lat") is not None else values.get("latitude"),
            "lon": obs.get("lon") if obs.get("lon") is not None else values.get("longitude"),
        })
        for event in obs.get("interference_events") or []:
            if not isinstance(event, dict):
                continue
            out.append({
                "evidence_id": event.get("id") or event.get("point_id"),
                "point_id": event.get("id") or event.get("point_id"),
                "source_id": event.get("parent_id") or event.get("source"),
                "evidence_class": "curated_interference_event",
                "claim_level": event.get("claim_level") or "jamming_reported",
                "claim_class": event.get("claim_class") or "reported_interference",
                "source": event.get("source"),
                "distance_km": event.get("distance_km"),
            })
    return out


def _attach_gnss_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    """Fill spec §7.3 fields: summary, evidence, receipt_url, verifier_url."""
    cells = [c for c in (payload.get("cells") or []) if isinstance(c, dict)]
    observations = [o for o in (payload.get("observations") or []) if isinstance(o, dict)]
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    states = [str(c.get("state") or "unknown") for c in cells] or [
        str(o.get("state") or "unknown") for o in observations
    ]
    scores = [
        float(c["degradation_score"])
        for c in cells
        if isinstance(c.get("degradation_score"), (int, float))
    ]
    claims = [str(o.get("claim_level")) for o in observations if o.get("claim_level")]
    unknown = int(coverage.get("unknown_integrity") or 0)
    station_n = int(coverage.get("stations") or 0)
    if payload.get("ok") and station_n and unknown == 0:
        coverage_label = "full"
    elif payload.get("ok") and station_n:
        coverage_label = "partial"
    else:
        coverage_label = "none"
    payload["summary"] = {
        "state": products._worst_state(states) if payload.get("ok") else "unknown",
        "score": round(max(scores), 2) if scores and payload.get("ok") else None,
        "confidence": payload.get("confidence") if payload.get("ok") else 0.0,
        "coverage": coverage_label,
        "claim_level": products._strongest_claim(claims) if payload.get("ok") else None,
    }
    payload["evidence"] = products._evidence_records(observations) if payload.get("ok") else []
    if payload.get("ok"):
        payload["receipt"] = products.make_receipt(payload, capability_id="atlas.gnss.degradation.read@v1")
        products.remember_receipt(payload["receipt"])
        payload["receipt_url"], payload["verifier_url"] = products._receipt_links(payload["receipt"])
    else:
        payload.setdefault("receipt_url", None)
        payload.setdefault("verifier_url", None)
    return payload


def _citation(s: dict[str, Any]) -> dict[str, Any]:
    values = s.get("values") if isinstance(s.get("values"), dict) else {}
    layer = str(s.get("layer") or "")
    citation = {
        "id": s.get("id"),
        "parent_id": s.get("parent_id"),
        "layer": layer,
        "place": s.get("place"),
        "lat": s.get("lat"),
        "lon": s.get("lon"),
        "live": bool(s.get("live")),
        "mode": s.get("mode"),
        "source": s.get("source"),
        "headline": s.get("headline") or headline(layer, values),
        "values": values,
    }
    for key in (
        "observed_at", "acq_date", "acq_time_utc", "satellite", "instrument",
        "daynight", "version", "frp_mw", "scan_km", "track_km", "event_id",
        "type", "region", "status", "start_date", "end_date", "severity",
        "confidence_pct", "attribution", "url", "area_ha", "firedate",
        "energy_fj", "name", "alert", "color",
        "wmo", "profile_url", "source_url", "directory_url", "profile_path",
        "dac", "doi", "profile_quality", "fetched_at", "reading_age_ms",
        "station_id", "network", "country", "source_status", "state",
        "claim_class", "claim_level", "cause", "source_url", "license", "license_url",
        "attribution", "modified", "measurement_basis", "evidence_boundary",
    ):
        if s.get(key) is not None:
            citation[key] = s[key]
    return citation


# Imported last on purpose: this code reads products's state, settings and helpers at
# call time (where tests patch them), and either module may load first.
from .. import products as products  # noqa: E402
