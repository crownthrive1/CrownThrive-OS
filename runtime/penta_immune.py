"""PentaImmune: bounded autonomic weakness hunting and repair planning.

The hunter operates only on supplied CrownThrive-local signals. It does not scan
external targets, execute arbitrary commands, self-certify, or self-promote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping, Sequence

SAFE_KINDS = frozenset(
    {
        "ci_failure",
        "test_failure",
        "evidence_gap",
        "stale_automation",
        "known_governance_defect",
        "docs_drift",
        "registry_drift",
    }
)
SAFE_HANDLERS = frozenset(
    {
        "patch_known_code",
        "add_negative_test",
        "repair_workflow",
        "regenerate_manifest",
        "reconcile_docs",
        "reconcile_registry",
    }
)
AUTONOMOUS_AUTHORITIES = frozenset({"D0", "D1", "D2"})


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WeaknessCandidate:
    id: str
    kind: str
    source_ref: str
    authority_level: str
    handler: str
    severity: int
    recurrence: int
    confidence: int
    reversibility: int
    testability: int
    blast_radius: int
    rollback: Mapping[str, Any]
    fallback: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.id or not self.source_ref:
            raise ValueError("candidate id and source_ref are required")
        if self.kind not in SAFE_KINDS:
            raise ValueError("candidate kind is outside the repo-local hunting scope")
        if self.handler not in SAFE_HANDLERS:
            raise ValueError("candidate handler is not allowlisted")
        if self.authority_level not in {"D0", "D1", "D2", "D3"}:
            raise ValueError("unsupported decision authority")
        for name in ("severity", "recurrence", "confidence", "reversibility", "testability", "blast_radius"):
            value = getattr(self, name)
            if not isinstance(value, int) or not 0 <= value <= 5:
                raise ValueError(f"{name} must be an integer from 0 through 5")
        if not self.rollback or not self.fallback:
            raise ValueError("every candidate requires rollback and fallback/redundancy")

    @property
    def score(self) -> int:
        self.validate()
        return (
            self.severity * 3
            + self.recurrence * 2
            + self.confidence * 2
            + self.reversibility * 2
            + self.testability * 2
            - self.blast_radius * 3
        )

    @property
    def fingerprint(self) -> str:
        stable = {
            "kind": self.kind,
            "handler": self.handler,
            "source_ref": self.source_ref,
            "metadata": dict(self.metadata),
        }
        return hashlib.sha256(canonical_json(stable).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AutonomyPolicy:
    max_repairs_per_cycle: int = 1
    max_attempts_per_candidate: int = 2
    cooldown_seconds: int = 3600
    kill_switch_state: str = "armed"
    allowed_authority: frozenset[str] = AUTONOMOUS_AUTHORITIES
    allow_production_promotion: bool = False
    allow_self_certification: bool = False
    allow_authority_expansion: bool = False

    def validate(self) -> None:
        if self.max_repairs_per_cycle < 0:
            raise ValueError("max_repairs_per_cycle cannot be negative")
        if self.max_attempts_per_candidate < 1:
            raise ValueError("max_attempts_per_candidate must be positive")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        if self.kill_switch_state not in {"armed", "tripped"}:
            raise ValueError("kill switch must be armed or tripped")
        if self.allowed_authority - AUTONOMOUS_AUTHORITIES:
            raise ValueError("autonomous policy cannot include D3")
        if self.allow_production_promotion or self.allow_self_certification or self.allow_authority_expansion:
            raise ValueError("autonomous policy cannot grant promotion, self-certification, or authority expansion")


def rank_candidates(candidates: Sequence[WeaknessCandidate]) -> list[WeaknessCandidate]:
    validated = []
    for candidate in candidates:
        candidate.validate()
        validated.append(candidate)
    return sorted(validated, key=lambda c: (-c.score, c.id))


def build_repair_plan(candidate: WeaknessCandidate, policy: AutonomyPolicy | None = None) -> dict[str, Any]:
    policy = policy or AutonomyPolicy()
    policy.validate()
    candidate.validate()
    reasons: list[str] = []
    if policy.kill_switch_state == "tripped":
        reasons.append("kill switch is tripped")
    if candidate.authority_level not in policy.allowed_authority:
        reasons.append("candidate exceeds autonomous authority")
    if policy.max_repairs_per_cycle == 0:
        reasons.append("repair throttle is exhausted")
    status = "READY" if not reasons else "HOLD"
    plan = {
        "schema": "ct.penta.immune-repair-plan.v1",
        "candidate_id": candidate.id,
        "candidate_fingerprint": candidate.fingerprint,
        "source_ref": candidate.source_ref,
        "kind": candidate.kind,
        "authority_level": candidate.authority_level,
        "handler": candidate.handler,
        "priority_score": candidate.score,
        "status": status,
        "reasons": reasons,
        "rollback": dict(candidate.rollback),
        "fallback": dict(candidate.fallback),
        "redundancy_required": True,
        "max_attempts": policy.max_attempts_per_candidate,
        "cooldown_seconds": policy.cooldown_seconds,
        "requires_exact_head_test": True,
        "requires_independent_certification": True,
        "production_promotion_authorized": False,
        "arbitrary_command_execution_authorized": False,
    }
    plan["plan_sha256"] = sha256_json(plan)
    return plan


def select_candidate(
    candidates: Sequence[WeaknessCandidate],
    *,
    attempt_counts: Mapping[str, int] | None = None,
    policy: AutonomyPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or AutonomyPolicy()
    policy.validate()
    attempts = dict(attempt_counts or {})
    considered: list[dict[str, Any]] = []
    for candidate in rank_candidates(candidates):
        plan = build_repair_plan(candidate, policy)
        current_attempts = int(attempts.get(candidate.id, 0))
        if current_attempts >= policy.max_attempts_per_candidate:
            plan = dict(plan)
            plan["status"] = "HOLD"
            plan["reasons"] = list(plan["reasons"]) + ["candidate retry cap reached"]
            plan["plan_sha256"] = sha256_json({k: v for k, v in plan.items() if k != "plan_sha256"})
        considered.append(plan)
        if plan["status"] == "READY":
            return {"selected": plan, "considered": considered}
    return {"selected": None, "considered": considered}


def verify_repair_result(
    plan: Mapping[str, Any],
    *,
    tested_head_sha: str,
    current_head_sha: str,
    test_receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    if plan.get("status") != "READY":
        reasons.append("repair plan was not executable")
    if tested_head_sha != current_head_sha:
        reasons.append("tested head does not match current head")
    if not test_receipts:
        reasons.append("test receipts are required")
    elif any(str(receipt.get("status", "")).upper() != "PASS" for receipt in test_receipts):
        reasons.append("one or more repair tests failed")
    if not plan.get("rollback"):
        reasons.append("rollback is missing")
    if not plan.get("fallback"):
        reasons.append("fallback/redundancy is missing")
    result = {
        "schema": "ct.penta.immune-repair-result.v1",
        "candidate_id": plan.get("candidate_id"),
        "status": "PASS" if not reasons else "HOLD",
        "tested_head_sha": tested_head_sha,
        "current_head_sha": current_head_sha,
        "test_receipts": [dict(x) for x in test_receipts],
        "rollback": plan.get("rollback"),
        "fallback": plan.get("fallback"),
        "reasons": reasons,
        "eligible_for_evidence_build": not reasons,
        "eligible_for_production_promotion": False,
    }
    result["result_sha256"] = sha256_json(result)
    return result


def remember_repair(
    candidate: WeaknessCandidate,
    *,
    plan: Mapping[str, Any],
    repair_result: Mapping[str, Any],
    evidence_receipt_sha256: str,
) -> dict[str, Any]:
    if repair_result.get("status") != "PASS":
        raise ValueError("failed or held repair cannot enter successful repair memory")
    memory = {
        "schema": "ct.penta.immune-memory.v1",
        "candidate_fingerprint": candidate.fingerprint,
        "candidate_kind": candidate.kind,
        "handler": candidate.handler,
        "recipe": {
            "plan_sha256": plan.get("plan_sha256"),
            "rollback": plan.get("rollback"),
            "fallback": plan.get("fallback"),
        },
        "evidence_receipt_sha256": evidence_receipt_sha256,
        "advisory_only": True,
        "requires_prerequisite_match": True,
        "requires_retest": True,
        "grants_authority": False,
        "grants_certification": False,
    }
    memory["memory_sha256"] = sha256_json(memory)
    return memory


def propose_penta(*, name: str, purpose: str, evidence_refs: Sequence[str]) -> dict[str, Any]:
    """Generate a candidate subsystem proposal without institutionalizing it."""
    if not name.startswith("Penta") or not purpose or not evidence_refs:
        raise ValueError("Penta proposal requires a canonical name, purpose and evidence")
    proposal = {
        "schema": "ct.penta.subsystem-proposal.v1",
        "name": name,
        "purpose": purpose,
        "evidence_refs": list(evidence_refs),
        "state": "CANDIDATE",
        "requires_external_governance": True,
        "self_registration_authorized": False,
        "self_activation_authorized": False,
        "authority_expansion_authorized": False,
    }
    proposal["proposal_sha256"] = sha256_json(proposal)
    return proposal
