#!/usr/bin/env python3
"""Executable policy helpers for PentaAlumni, PentaHybrid, PentaInstitute,
PentaSignal, and PentaAssure.

This module is deliberately deterministic and dependency-free. It converts the
institutional contracts into machine-evaluable dispositions without creating
legal or governance authority. Callers must provide CHLOM-recognized charters,
identity/role evidence, and source/evidence records from the appropriate
systems.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from typing import Any, Mapping, Sequence

RISK_RANK = {"D0": 0, "D1": 1, "D2": 2, "D3": 3}
ACTIVE_CHARTER_STATES = {"active"}
APPROVAL_STATES = {"approved", "approved_exact", "approved_with_conditions"}
ASSURANCE_SUCCESS_STATES = {"pass", "not_applicable"}


class InstitutionalRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class GovernanceDisposition:
    allowed: bool
    state: str
    reasons: tuple[str, ...]
    evidence_required: tuple[str, ...] = ()


@dataclass(frozen=True)
class SignalDisposition:
    disposition: str
    priority: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AssuranceDisposition:
    certified: bool
    disposition: str
    reasons: tuple[str, ...]


def _require_nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InstitutionalRuntimeError(f"{label} must be non-empty")
    return value


def evaluate_alumni_charter(
    charter: Mapping[str, Any],
    requested_scope: str,
    requested_risk: str,
    participant_roles: Sequence[str],
    participant_count: int,
    conflict_free_count: int,
) -> GovernanceDisposition:
    """Evaluate whether a PentaAlumni body can act inside a supplied charter.

    This checks the machine contract only. It assumes upstream identity and role
    evidence has already been resolved by CrownThrive ID/CHLOM and does not
    independently verify a person's identity.
    """
    reasons: list[str] = []
    evidence: list[str] = []

    _require_nonempty(charter.get("charter_id"), "charter_id")
    _require_nonempty(charter.get("body_id"), "body_id")

    state = charter.get("state")
    if state not in ACTIVE_CHARTER_STATES:
        reasons.append(f"charter state is not active: {state}")

    authority_class = charter.get("authority_class")
    if authority_class not in {"advisory", "delegated", "binding"}:
        reasons.append(f"invalid authority_class: {authority_class}")
    elif authority_class == "advisory":
        reasons.append("charter is advisory and cannot authorize binding execution")

    scopes = charter.get("scope")
    if not isinstance(scopes, list) or requested_scope not in scopes:
        reasons.append(f"requested scope is outside charter: {requested_scope}")

    ceiling = charter.get("risk_ceiling")
    if ceiling not in RISK_RANK or requested_risk not in RISK_RANK:
        reasons.append("invalid risk class")
    elif RISK_RANK[requested_risk] > RISK_RANK[ceiling]:
        reasons.append(f"requested risk {requested_risk} exceeds charter ceiling {ceiling}")

    allowed_roles = set(charter.get("member_roles") or [])
    roles = set(participant_roles)
    if not roles:
        reasons.append("no participant roles supplied")
    elif not roles <= allowed_roles:
        reasons.append(f"participant role outside charter: {sorted(roles - allowed_roles)}")

    quorum = charter.get("quorum")
    if not isinstance(quorum, int) or quorum < 1:
        reasons.append("invalid charter quorum")
    else:
        if participant_count < quorum:
            reasons.append(f"participant count {participant_count} is below quorum {quorum}")
        if conflict_free_count < quorum:
            reasons.append(f"conflict-free count {conflict_free_count} is below quorum {quorum}")

    if not reasons:
        evidence.extend(["identity_and_role_evidence", "current_term_evidence", "conflict_and_recusal_evidence", "quorum_record"])
        return GovernanceDisposition(True, "charter_authority_resolved", (), tuple(evidence))
    return GovernanceDisposition(False, "hold_fail_closed", tuple(reasons), tuple(evidence))


def evaluate_hybrid_decision(
    decision: Mapping[str, Any],
    charter_result: GovernanceDisposition | None,
    required_quorum: int | None = None,
) -> GovernanceDisposition:
    """Resolve a PentaHybrid human decision into an executable gate state."""
    reasons: list[str] = []
    disposition = decision.get("disposition")
    conflict = decision.get("conflict_check")
    participants = decision.get("participants") or []
    evidence_refs = decision.get("evidence_refs") or []

    _require_nonempty(decision.get("decision_id"), "decision_id")
    _require_nonempty(decision.get("authority_ref"), "authority_ref")
    _require_nonempty(decision.get("required_human_role"), "required_human_role")

    if conflict != "pass":
        reasons.append(f"conflict check not passed: {conflict}")
    if not evidence_refs:
        reasons.append("decision has no evidence references")
    if disposition not in APPROVAL_STATES:
        reasons.append(f"decision is not approved: {disposition}")
    if required_quorum is not None and len(set(participants)) < required_quorum:
        reasons.append(f"participant count is below required quorum {required_quorum}")
    if charter_result is not None and not charter_result.allowed:
        reasons.append("underlying PentaAlumni charter did not resolve authority")

    override_reason = decision.get("override_reason")
    recommendation = str(decision.get("machine_recommendation", ""))
    if "reject" in recommendation.casefold() and disposition in APPROVAL_STATES and not str(override_reason or "").strip():
        reasons.append("human approval overrides a negative machine recommendation without an override reason")

    if reasons:
        return GovernanceDisposition(False, "hold_fail_closed", tuple(reasons))
    return GovernanceDisposition(True, "human_approval_resolved", (), ("human_decision_receipt",))


def triage_signal(signal: Mapping[str, Any]) -> SignalDisposition:
    """Convert a PentaSignal observation into a bounded next action."""
    confidence = signal.get("confidence")
    corroboration = signal.get("corroboration_state")
    risk = signal.get("risk_class")
    existing = signal.get("disposition")
    reasons: list[str] = []

    if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
        raise InstitutionalRuntimeError("signal confidence must be between 0 and 1")
    if risk not in RISK_RANK:
        raise InstitutionalRuntimeError("signal risk_class is invalid")
    if corroboration not in {"uncorroborated", "partially_corroborated", "corroborated", "contradicted"}:
        raise InstitutionalRuntimeError("signal corroboration_state is invalid")

    if corroboration == "contradicted":
        return SignalDisposition("research_candidate", "normal", ("signal is contradicted and requires analytical reconciliation",))

    if RISK_RANK[risk] >= RISK_RANK["D2"] and confidence >= 0.70:
        reasons.append("high-consequence signal with material confidence")
        return SignalDisposition("escalate", "urgent", tuple(reasons))

    if corroboration == "corroborated" and confidence >= 0.75:
        reasons.append("corroborated signal exceeds research threshold")
        return SignalDisposition("research_candidate", "high", tuple(reasons))

    if confidence < 0.40 or corroboration == "uncorroborated":
        reasons.append("weak or uncorroborated signal remains under observation")
        return SignalDisposition("observe", "low", tuple(reasons))

    reasons.append(f"retain bounded disposition: {existing or 'research_candidate'}")
    return SignalDisposition(str(existing or "research_candidate"), "normal", tuple(reasons))


def validate_research_record(record: Mapping[str, Any]) -> GovernanceDisposition:
    """Validate minimum PentaInstitute evidence discipline before a recommendation can be promoted."""
    reasons: list[str] = []
    required_lists = ["sources", "methods", "findings", "recommendations", "known_unknowns"]
    _require_nonempty(record.get("research_id"), "research_id")
    _require_nonempty(record.get("question"), "question")
    _require_nonempty(record.get("sponsor_role"), "sponsor_role")

    if record.get("confidence") not in {"low", "medium", "high"}:
        reasons.append("research confidence is invalid")
    for field in required_lists:
        value = record.get(field)
        if not isinstance(value, list):
            reasons.append(f"{field} must be a list")
    if not record.get("sources"):
        reasons.append("research record has no sources")
    if not record.get("methods"):
        reasons.append("research record has no methods")
    if record.get("recommendations") and not record.get("findings"):
        reasons.append("recommendations exist without findings")
    if record.get("chlom_disposition") not in {"pending", "accepted", "rejected", "modified", "hold", "archived"}:
        reasons.append("invalid CHLOM disposition")

    if reasons:
        return GovernanceDisposition(False, "research_not_promotable", tuple(reasons))
    return GovernanceDisposition(True, "research_record_valid", (), ("source_register", "methods", "confidence", "known_unknowns"))


def evaluate_assurance(certification: Mapping[str, Any]) -> AssuranceDisposition:
    """Evaluate whether an explicit PentaAssure certification contract passes."""
    reasons: list[str] = []
    _require_nonempty(certification.get("certification_id"), "certification_id")
    _require_nonempty(certification.get("subject_ref"), "subject_ref")
    _require_nonempty(certification.get("standard_ref"), "standard_ref")

    independence = certification.get("independence_state")
    if independence == "not_satisfied" or independence not in {
        "independent",
        "human_independent",
        "separation_of_duties_satisfied",
        "not_satisfied",
    }:
        reasons.append(f"independence not satisfied: {independence}")

    evidence_refs = certification.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        reasons.append("no evidence references")

    checks = certification.get("checks")
    if not isinstance(checks, list) or not checks:
        reasons.append("no assurance checks")
    else:
        for check in checks:
            status = check.get("status") if isinstance(check, Mapping) else None
            if status not in ASSURANCE_SUCCESS_STATES:
                name = check.get("name", "unnamed") if isinstance(check, Mapping) else "invalid"
                reasons.append(f"assurance check not passing: {name}={status}")

    declared = certification.get("disposition")
    if reasons:
        return AssuranceDisposition(False, "not_certified", tuple(reasons))
    if declared not in {"certified", "hold"}:
        reasons.append(f"declared disposition is not promotable: {declared}")
        return AssuranceDisposition(False, "not_certified", tuple(reasons))
    if declared == "hold":
        return AssuranceDisposition(False, "hold", ("certification is explicitly held",))
    return AssuranceDisposition(True, "certified", ())


def _self_test() -> dict[str, Any]:
    charter = {
        "charter_id": "chlom.charter.release-council",
        "body_id": "penta.alumni.release-council",
        "purpose": "D2 release review",
        "authority_class": "delegated",
        "scope": ["release.approve"],
        "risk_ceiling": "D2",
        "member_roles": ["release-steward"],
        "eligibility_rules": ["active_term"],
        "term_rules": "active",
        "quorum": 2,
        "recusal_rules": ["originator_must_recuse"],
        "conflict_rules": ["no_material_conflict"],
        "revocation_authority": "CHLOM",
        "state": "active"
    }
    charter_result = evaluate_alumni_charter(charter, "release.approve", "D2", ["release-steward"], 2, 2)
    assert charter_result.allowed

    decision = {
        "decision_id": "penta.hybrid.release-1",
        "workflow_ref": "penta.mation.release-1",
        "risk_class": "D2",
        "requested_action": "promote release",
        "machine_recommendation": "approve after assurance",
        "confidence": 0.93,
        "evidence_refs": ["dail:evidence-1"],
        "required_human_role": "release-steward",
        "authority_ref": "chlom.charter.release-council",
        "conflict_check": "pass",
        "quorum_required": 2,
        "participants": ["ctid:a", "ctid:b"],
        "disposition": "approved",
        "override_reason": null,
        "receipts": ["dail:decision-1"]
    }
    decision_result = evaluate_hybrid_decision(decision, charter_result, 2)
    assert decision_result.allowed

    signal = {
        "signal_id": "penta.signal.provider-drift",
        "observed_at": "2026-08-26T00:00:00Z",
        "source_refs": ["provider:heartbeat"],
        "claim": "provider contract drift detected",
        "confidence": 0.85,
        "corroboration_state": "corroborated",
        "risk_class": "D2",
        "disposition": "research_candidate"
    }
    signal_result = triage_signal(signal)
    assert signal_result.disposition == "escalate"

    research = {
        "research_id": "penta.institute.provider-drift",
        "version": 1,
        "research_class": "rapid_brief",
        "question": "What changed and what is the blast radius?",
        "sponsor_role": "Penta Control",
        "sources": ["provider:heartbeat", "registry:binding"],
        "assumptions": ["heartbeat is current"],
        "competing_hypotheses": ["provider drift", "local stale cache"],
        "methods": ["cross-readback", "registry comparison"],
        "findings": ["provider drift confirmed"],
        "confidence": "high",
        "recommendations": ["hold mutations until recertification"],
        "known_unknowns": ["provider remediation ETA"],
        "chlom_disposition": "pending",
        "preservation_targets": ["PentaDocs", "DAIL"]
    }
    research_result = validate_research_record(research)
    assert research_result.allowed

    assurance = {
        "certification_id": "penta.assure.release-1",
        "subject_ref": "release:1",
        "standard_ref": "chlom.standard.release-d2",
        "risk_class": "D2",
        "evidence_refs": ["dail:test-1", "dail:review-1"],
        "independence_state": "separation_of_duties_satisfied",
        "checks": [
            {"name": "tests", "status": "pass", "evidence_ref": "dail:test-1"},
            {"name": "human gate", "status": "pass", "evidence_ref": "dail:review-1"}
        ],
        "disposition": "certified",
        "preserve": ["PentaDocs", "DAIL"]
    }
    assurance_result = evaluate_assurance(assurance)
    assert assurance_result.certified

    return {
        "pass": True,
        "charter": asdict(charter_result),
        "hybrid": asdict(decision_result),
        "signal": asdict(signal_result),
        "research": asdict(research_result),
        "assurance": asdict(assurance_result),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PENTA institutional policy runtime")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        parser.print_help()
        return 0
    try:
        result = _self_test()
    except Exception as exc:
        print(json.dumps({"pass": False, "error": repr(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
