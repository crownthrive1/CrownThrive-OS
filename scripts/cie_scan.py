#!/usr/bin/env python3
"""Public-safe Cultural Imprint Engine (CIE) contract and runtime client.

The public repository intentionally does not contain proprietary deduction,
confidence, recurrence, or detection calibration. Those controls are resolved by
the parent-governed repository federation runtime from the approved Vault bundle.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from repository_federation_sync import federation_call

DIMENSIONS = ("identity_fit", "community_value", "story_alignment", "brand_safety", "legacy_impact")
PASS_THRESHOLD = 85
PUBLIC_CONTRACT_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"
HARD_BLOCK_CODES = {
    "fabricated_community_endorsement",
    "identity_impersonation_or_deliberate_erasure",
    "dehumanizing_or_discriminatory_representation",
    "knowingly_false_cultural_or_canon_claim",
    "unauthorized_rewrite_of_protected_canon_or_identity",
    "exploitative_use_of_sacred_restricted_or_private_material",
    "material_source_community_attribution_fraud",
    "retaliatory_suppression_of_documented_correction",
    "cie_score_or_evidence_manipulation",
    "bypass_of_required_cie_review",
}
REJECTED_SUBJECT_TYPES = {
    "person", "individual", "individual_sensitive_profile", "user_profile",
    "employee_profile", "customer_profile",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("cie_input_must_be_object")
    return value


def validate_subject(packet: dict[str, Any]) -> dict[str, Any]:
    subject_id = str(packet.get("subject_id", "")).strip()
    subject_type = str(packet.get("subject_type", "")).strip().lower()
    declared_context = packet.get("declared_context")
    if not subject_id or not subject_type or declared_context in (None, "", {}):
        raise ValueError("subject_id_subject_type_and_declared_context_required")
    if subject_type in REJECTED_SUBJECT_TYPES:
        raise ValueError("cie_scores_artifacts_and_uses_not_people")

    evidence = packet.get("dimension_evidence")
    if not isinstance(evidence, dict) or set(evidence) != set(DIMENSIONS):
        raise ValueError("all_five_canonical_dimensions_required")
    normalized_evidence: dict[str, list[str]] = {}
    for dimension in DIMENSIONS:
        values = evidence[dimension]
        if not isinstance(values, list):
            raise ValueError(f"dimension_evidence_must_be_list:{dimension}")
        normalized_evidence[dimension] = [str(item).strip() for item in values if str(item).strip()]

    findings = packet.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings_must_be_list")
    normalized_findings: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("finding_must_be_object")
        dimension = str(finding.get("dimension", "")).strip()
        code = str(finding.get("code", "")).strip()
        severity = str(finding.get("severity", "")).strip().lower()
        confidence = str(finding.get("confidence", "")).strip().lower()
        recurrence = str(finding.get("recurrence", "first")).strip().lower()
        reason = str(finding.get("reason", "")).strip()
        if dimension not in DIMENSIONS or not code or not severity or not confidence or not reason:
            raise ValueError(f"invalid_finding:{code or '<missing>'}")
        normalized_findings.append({
            "dimension": dimension,
            "code": code,
            "severity": severity,
            "confidence": confidence,
            "recurrence": recurrence,
            "reason": reason,
        })

    return {
        "subject_id": subject_id,
        "subject_type": subject_type,
        "declared_context": declared_context,
        "dimension_evidence": normalized_evidence,
        "findings": normalized_findings,
    }


def evaluate(packet: dict[str, Any], *, agent_id: str = "ct.framework-agent.cie") -> dict[str, Any]:
    subject = validate_subject(packet)
    response = federation_call("algorithm.cie.score", {"agent_id": agent_id, "subject": subject})
    result = response.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("cie_runtime_result_missing")
    if result.get("policy_contract_digest") != PUBLIC_CONTRACT_DIGEST and result.get("verdict") not in {"REJECTED", "HOLD_INSUFFICIENT_EVIDENCE"}:
        raise RuntimeError("cie_runtime_contract_digest_mismatch")
    return result


def self_test() -> None:
    evidence = {name: [f"evidence:{name}"] for name in DIMENSIONS}
    valid = validate_subject({
        "subject_id": "asset:test",
        "subject_type": "digital_asset",
        "declared_context": {"audience": "declared"},
        "dimension_evidence": evidence,
        "findings": [{
            "dimension": "brand_safety",
            "code": "context_gap",
            "severity": "medium",
            "confidence": "primary_verified",
            "recurrence": "first",
            "reason": "Synthetic public-contract validation finding.",
        }],
    })
    assert set(valid["dimension_evidence"]) == set(DIMENSIONS)
    assert len(HARD_BLOCK_CODES) == 10
    assert PASS_THRESHOLD == 85
    try:
        validate_subject({
            "subject_id": "person:1",
            "subject_type": "person",
            "declared_context": {"purpose": "invalid"},
            "dimension_evidence": evidence,
            "findings": [],
        })
    except ValueError as exc:
        assert str(exc) == "cie_scores_artifacts_and_uses_not_people"
    else:
        raise AssertionError("person scoring must be rejected")
    text = Path(__file__).read_text(encoding="utf-8")
    for protected in ("SEVERITY_" + "DEDUCTIONS", "confidence_" + "multipliers", "recurrence_" + "multipliers"):
        assert protected not in text
    print("CIE public-client self-test PASS: public contract preserved, person scoring rejected, protected calibration absent; runtime scoring requires governed OIDC federation + Vault.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--agent-id", default="ct.framework-agent.cie")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.input:
        parser.error("--input required unless --self-test")
    result = evaluate(load(args.input), agent_id=args.agent_id)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
