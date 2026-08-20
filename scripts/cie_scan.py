#!/usr/bin/env python3
"""Deterministic Cultural Imprint Engine (CIE) scoring and explanation engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DIMENSIONS = ("identity_fit", "community_value", "story_alignment", "brand_safety", "legacy_impact")
SEVERITY_DEDUCTIONS = {"info": 0, "low": 2, "medium": 5, "high": 10, "critical": 20}
PASS_THRESHOLD = 85
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
REJECTED_SUBJECT_TYPES = {"person", "individual_sensitive_profile"}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def score_dimension(payload: dict[str, Any]) -> tuple[int, list[dict[str, Any]], list[str]]:
    evidence = [str(x).strip() for x in payload.get("evidence_refs", []) if str(x).strip()]
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings_must_be_list")
    deductions = 0
    normalized: list[dict[str, Any]] = []
    hard_blocks: list[str] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("finding_must_be_object")
        code = str(finding.get("code", "")).strip()
        severity = str(finding.get("severity", "")).strip().lower()
        reason = str(finding.get("reason", "")).strip()
        refs = [str(x).strip() for x in finding.get("evidence_refs", []) if str(x).strip()]
        if not code or severity not in SEVERITY_DEDUCTIONS or not reason or not refs:
            raise ValueError(f"invalid_finding:{code or '<missing>'}")
        deductions += SEVERITY_DEDUCTIONS[severity]
        if code in HARD_BLOCK_CODES:
            hard_blocks.append(code)
        normalized.append({"code": code, "severity": severity, "reason": reason, "evidence_refs": refs})
    score = max(0, 20 - deductions)
    if not evidence:
        score = 0
    return score, normalized, hard_blocks


def verdict_for(total: int, missing_evidence: bool, hard_blocks: list[str]) -> str:
    if hard_blocks:
        return "FAIL_HARD_BLOCK"
    if missing_evidence:
        return "HOLD_INSUFFICIENT_EVIDENCE"
    if total >= PASS_THRESHOLD:
        return "PASS"
    if total >= 70:
        return "REVIEW"
    if total >= 50:
        return "HOLD"
    return "FAIL"


def evaluate(packet: dict[str, Any]) -> dict[str, Any]:
    subject_type = str(packet.get("subject_type", "")).strip()
    subject_id = str(packet.get("subject_id", "")).strip()
    declared_context = packet.get("declared_context")
    if not subject_id or not subject_type or declared_context in (None, "", {}):
        raise ValueError("subject_id_subject_type_and_declared_context_required")
    if subject_type in REJECTED_SUBJECT_TYPES:
        raise ValueError("cie_scores_artifacts_and_uses_not_people")
    dims = packet.get("dimension_evidence")
    if not isinstance(dims, dict) or set(dims) != set(DIMENSIONS):
        raise ValueError("all_five_canonical_dimensions_required")

    dimension_scores: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    hard_blocks: list[str] = []
    missing: list[str] = []
    reasons: list[str] = []

    for name in DIMENSIONS:
        item = dims[name]
        if not isinstance(item, dict):
            raise ValueError(f"dimension_must_be_object:{name}")
        score, normalized, blocks = score_dimension(item)
        dimension_scores[name] = score
        if not item.get("evidence_refs"):
            missing.append(name)
        for finding in normalized:
            findings.append({"dimension": name, **finding})
        hard_blocks.extend(blocks)
        reasons.append(f"{name}={score}/20")

    total = sum(dimension_scores.values())
    verdict = verdict_for(total, bool(missing), sorted(set(hard_blocks)))
    corrections = [
        {
            "code": item["code"],
            "dimension": item["dimension"],
            "priority": item["severity"],
            "required_action": f"Correct and re-evidence: {item['reason']}",
        }
        for item in findings
        if item["severity"] in {"medium", "high", "critical"}
    ]
    assigned_agents = sorted(set(str(x).strip() for x in packet.get("assigned_agents", []) if str(x).strip()))
    human_escalations = sorted(set(str(x).strip() for x in packet.get("human_escalations", []) if str(x).strip()))
    if hard_blocks and "ct.relay.agent-d" not in assigned_agents:
        assigned_agents.append("ct.relay.agent-d")

    return {
        "cie_contract_version": "1.0.0",
        "subject_id": subject_id,
        "subject_type": subject_type,
        "cie_score": total,
        "score_max": 100,
        "pass_threshold": PASS_THRESHOLD,
        "verdict": verdict,
        "dimension_scores": dimension_scores,
        "findings": findings,
        "hard_blocks": sorted(set(hard_blocks)),
        "missing_dimension_evidence": missing,
        "corrections": corrections,
        "assigned_agents": assigned_agents,
        "human_escalations": human_escalations,
        "reasons": reasons,
        "disclaimer": "CIE evaluates the artifact/use/context. It does not score a person's cultural authenticity and does not substitute for legal, rights, security or professional determinations.",
    }


def self_test() -> None:
    evidence = {name: {"evidence_refs": [f"evidence:{name}"], "findings": []} for name in DIMENSIONS}
    good = evaluate({"subject_id": "asset:good", "subject_type": "digital_asset", "declared_context": {"audience": "declared"}, "dimension_evidence": evidence})
    assert good["cie_score"] == 100 and good["verdict"] == "PASS"

    medium = json.loads(json.dumps(evidence))
    medium["brand_safety"]["findings"] = [{"code": "context_gap", "severity": "medium", "reason": "Material context is incomplete.", "evidence_refs": ["evidence:gap"]}]
    result = evaluate({"subject_id": "asset:review", "subject_type": "page", "declared_context": {"audience": "declared"}, "dimension_evidence": medium})
    assert result["cie_score"] == 95 and result["verdict"] == "PASS"

    hard = json.loads(json.dumps(evidence))
    hard["community_value"]["findings"] = [{"code": "fabricated_community_endorsement", "severity": "critical", "reason": "An endorsement is represented without evidence.", "evidence_refs": ["evidence:endorsement"]}]
    result = evaluate({"subject_id": "asset:block", "subject_type": "campaign", "declared_context": {"audience": "declared"}, "dimension_evidence": hard})
    assert result["verdict"] == "FAIL_HARD_BLOCK" and result["cie_score"] == 80

    missing = json.loads(json.dumps(evidence))
    missing["legacy_impact"]["evidence_refs"] = []
    result = evaluate({"subject_id": "asset:unknown", "subject_type": "document", "declared_context": {"audience": "declared"}, "dimension_evidence": missing})
    assert result["verdict"] == "HOLD_INSUFFICIENT_EVIDENCE"

    try:
        evaluate({"subject_id": "person:1", "subject_type": "person", "declared_context": {"purpose": "bad"}, "dimension_evidence": evidence})
    except ValueError as exc:
        assert str(exc) == "cie_scores_artifacts_and_uses_not_people"
    else:
        raise AssertionError("person scoring must be rejected")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("CIE scoring engine self-test PASS: five dimensions, 100-point scale, hard-block override, evidence HOLD and person-scoring prohibition verified.")
        return 0
    if not args.input:
        parser.error("--input required unless --self-test")
    result = evaluate(load(args.input))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
