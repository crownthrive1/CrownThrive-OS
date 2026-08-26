"""PentaEVIBuilder: deterministic evidence construction and independent certification gates.

This module constructs evidence. It never grants authority, promotes production,
or certifies its own output. The exact source SHA is part of the evidence identity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA_ID = "ct.penta.evidence-bundle.v1"
CERT_SCHEMA_ID = "ct.penta.evidence-certification.v1"
MEMORY_SCHEMA_ID = "ct.penta.repair-memory.v1"
PRODUCER_ID = "penta.evi-builder"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_exact_sha(value: str, field_name: str = "head_sha") -> None:
    if not _SHA_RE.fullmatch(value or ""):
        raise ValueError(f"{field_name} must be a lowercase 40-character Git SHA")


@dataclass(frozen=True)
class TestReceipt:
    name: str
    status: str
    source: str
    details: str = ""

    def normalized(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status.upper(),
            "source": self.source,
            "details": self.details,
        }


@dataclass(frozen=True)
class AutonomyEnvelope:
    authority_level: str = "A2"
    kill_switch_state: str = "armed"
    max_repairs_per_cycle: int = 1
    max_attempts_per_candidate: int = 2
    permit_self_certification: bool = False
    permit_production_promotion: bool = False
    permit_authority_expansion: bool = False

    def validate(self) -> None:
        if self.authority_level not in {"A0", "A1", "A2", "A3", "A4"}:
            raise ValueError("unsupported authority level")
        if self.kill_switch_state not in {"armed", "tripped"}:
            raise ValueError("kill_switch_state must be armed or tripped")
        if self.max_repairs_per_cycle < 0 or self.max_attempts_per_candidate < 1:
            raise ValueError("invalid autonomy throttle")
        if (
            self.permit_self_certification
            or self.permit_production_promotion
            or self.permit_authority_expansion
        ):
            raise ValueError("PentaEVIBuilder cannot grant certification, promotion, or authority expansion")


@dataclass(frozen=True)
class EvidenceBundle:
    work_order_id: str
    subject: str
    source_ref: str
    repo: str
    head_sha: str
    target_state: str
    authority_level: str
    observations: Sequence[Mapping[str, Any]]
    claims: Sequence[Mapping[str, Any]]
    evidence_refs: Sequence[str]
    test_receipts: Sequence[TestReceipt]
    rollback: Mapping[str, Any]
    fallback: Mapping[str, Any]
    provenance: Mapping[str, Any]
    autonomy: AutonomyEnvelope = field(default_factory=AutonomyEnvelope)
    producer: str = PRODUCER_ID
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_exact_sha(self.head_sha)
        self.autonomy.validate()
        if not self.work_order_id or not self.subject or not self.source_ref or not self.repo:
            raise ValueError("work order, subject, source_ref and repo are required")
        if self.authority_level not in {"D0", "D1", "D2", "D3"}:
            raise ValueError("unsupported decision authority")
        if self.producer != PRODUCER_ID:
            raise ValueError("unexpected evidence producer")
        if not self.rollback:
            raise ValueError("rollback is required")
        if not self.fallback:
            raise ValueError("fallback/redundancy is required")
        if self.provenance.get("exact_git_binding") is not True:
            raise ValueError("exact_git_binding=true is required")
        if self.provenance.get("head_sha") != self.head_sha:
            raise ValueError("provenance head_sha must equal evidence head_sha")

    def payload(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_ID,
            "work_order_id": self.work_order_id,
            "subject": self.subject,
            "source_ref": self.source_ref,
            "repo": self.repo,
            "head_sha": self.head_sha,
            "target_state": self.target_state,
            "authority_level": self.authority_level,
            "observations": [dict(x) for x in self.observations],
            "claims": [dict(x) for x in self.claims],
            "evidence_refs": list(self.evidence_refs),
            "test_receipts": [x.normalized() for x in self.test_receipts],
            "rollback": dict(self.rollback),
            "fallback": dict(self.fallback),
            "provenance": dict(self.provenance),
            "autonomy": asdict(self.autonomy),
            "producer": self.producer,
            "created_at": self.created_at,
            "certification_state": "UNVERIFIED",
            "production_promotion": False,
        }

    def to_dict(self) -> dict[str, Any]:
        body = self.payload()
        body["receipt_sha256"] = sha256_json(body)
        return body


def build_bundle(
    *,
    work_order_id: str,
    subject: str,
    source_ref: str,
    repo: str,
    head_sha: str,
    target_state: str,
    authority_level: str,
    observations: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    evidence_refs: Sequence[str],
    test_receipts: Sequence[TestReceipt],
    rollback: Mapping[str, Any],
    fallback: Mapping[str, Any],
    autonomy: AutonomyEnvelope | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    bundle = EvidenceBundle(
        work_order_id=work_order_id,
        subject=subject,
        source_ref=source_ref,
        repo=repo,
        head_sha=head_sha,
        target_state=target_state,
        authority_level=authority_level,
        observations=observations,
        claims=claims,
        evidence_refs=evidence_refs,
        test_receipts=test_receipts,
        rollback=rollback,
        fallback=fallback,
        provenance={"exact_git_binding": True, "head_sha": head_sha},
        autonomy=autonomy or AutonomyEnvelope(),
        created_at=created_at or utc_now(),
    )
    return bundle.to_dict()


def certify_bundle(
    bundle: Mapping[str, Any],
    *,
    verifier: str,
    current_head_sha: str,
    human_gate: bool = False,
) -> dict[str, Any]:
    """Return a fail-closed independent certification decision."""
    reasons: list[str] = []
    _require_exact_sha(current_head_sha, "current_head_sha")
    body = dict(bundle)
    supplied_digest = body.pop("receipt_sha256", None)
    if body.get("schema") != SCHEMA_ID:
        reasons.append("unsupported evidence schema")
    if supplied_digest != sha256_json(body):
        reasons.append("evidence receipt digest mismatch")
    if verifier == body.get("producer"):
        reasons.append("producer cannot independently certify its own evidence")
    if body.get("head_sha") != current_head_sha:
        reasons.append("certified head does not match current head")
    if not body.get("evidence_refs"):
        reasons.append("evidence references are required")
    if not body.get("rollback"):
        reasons.append("rollback evidence is required")
    if not body.get("fallback"):
        reasons.append("fallback/redundancy evidence is required")
    provenance = body.get("provenance") or {}
    if provenance.get("exact_git_binding") is not True or provenance.get("head_sha") != current_head_sha:
        reasons.append("exact Git provenance binding is invalid")
    autonomy = body.get("autonomy") or {}
    if any(
        autonomy.get(flag) is not False
        for flag in (
            "permit_self_certification",
            "permit_production_promotion",
            "permit_authority_expansion",
        )
    ):
        reasons.append("autonomy envelope attempts forbidden authority")
    receipts = body.get("test_receipts") or []
    if not receipts:
        reasons.append("test receipts are required")
    elif any(str(receipt.get("status", "")).upper() != "PASS" for receipt in receipts):
        reasons.append("one or more required tests did not pass")
    if body.get("authority_level") == "D3" and not human_gate:
        reasons.append("D3 requires a human gate")
    status = "PASS" if not reasons else "HOLD"
    decision = {
        "schema": CERT_SCHEMA_ID,
        "status": status,
        "verifier": verifier,
        "independent_verifier": verifier != body.get("producer"),
        "evidence_receipt_sha256": supplied_digest,
        "certified_head_sha": current_head_sha,
        "human_gate": bool(human_gate),
        "reasons": reasons,
        "production_promotion_authorized": False,
    }
    decision["decision_sha256"] = sha256_json(decision)
    return decision


def build_repair_memory(
    *,
    weakness_fingerprint: str,
    recipe: Mapping[str, Any],
    evidence_receipt_sha256: str,
    successful_head_sha: str,
) -> dict[str, Any]:
    """Create advisory memory. Memory is never authority or a substitute for retesting."""
    _require_exact_sha(successful_head_sha, "successful_head_sha")
    if not weakness_fingerprint or not recipe or not evidence_receipt_sha256:
        raise ValueError("complete repair memory inputs are required")
    memory = {
        "schema": MEMORY_SCHEMA_ID,
        "weakness_fingerprint": weakness_fingerprint,
        "recipe": dict(recipe),
        "evidence_receipt_sha256": evidence_receipt_sha256,
        "successful_head_sha": successful_head_sha,
        "advisory_only": True,
        "requires_retest": True,
        "grants_authority": False,
        "grants_certification": False,
    }
    memory["memory_sha256"] = sha256_json(memory)
    return memory
