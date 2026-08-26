#!/usr/bin/env python3
"""Validate CrownThrive governed-deferral contract and fixtures.

Repository validation only. This script does not mutate Supabase, provider gates,
phase state, or sovereign authority.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "developers/manifests/governed-deferral-standard.v1.json"
FIXTURE_PATH = ROOT / "tests/fixtures/governed-deferral-cases.v1.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_ts(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: timestamp required")
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid timestamp") from exc


def validate_record(record: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = contract["required_fields"]
    for field in required:
        if field not in record or record[field] in (None, "", [], {}):
            errors.append(f"missing_required:{field}")

    deferral_id = str(record.get("deferral_id", ""))
    if not deferral_id.startswith("CT-DEF-"):
        errors.append("invalid_deferral_id")

    status = str(record.get("status", "")).lower()
    allowed = set(contract["status_lifecycle"])
    forbidden = set(contract["forbidden_statuses"])
    if status not in allowed:
        errors.append("invalid_status")
    if status in forbidden:
        errors.append("pass_semantics_forbidden")

    if record.get("risk_class") not in contract["risk_classes"]:
        errors.append("invalid_risk_class")

    if not isinstance(record.get("external_dependency"), bool):
        errors.append("external_dependency_must_be_boolean")

    for field in ("compensating_controls", "evidence_refs"):
        value = record.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field}_must_be_nonempty_list")

    if record.get("underlying_gate_mutated_by_deferral") is True:
        errors.append("underlying_gate_mutation_forbidden")

    if record.get("technical_pass") is True:
        errors.append("technical_pass_cannot_be_created_by_deferral")

    try:
        review_due = parse_ts(record.get("review_due_at"), "review_due_at")
    except ValueError as exc:
        errors.append(str(exc))
        review_due = None

    approved_at = None
    try:
        approved_at = parse_ts(record.get("approved_at"), "approved_at")
    except ValueError as exc:
        errors.append(str(exc))

    expiry = record.get("expires_at")
    exception = record.get("expiry_exception_reason")
    if status in {"candidate", "approved"} and not expiry and not exception:
        errors.append("active_deferral_requires_expiry_or_exception")
    if exception is not None and (not isinstance(exception, str) or not exception.strip()):
        errors.append("expiry_exception_reason_invalid")
    if expiry:
        try:
            expiry_ts = parse_ts(expiry, "expires_at")
            if approved_at and expiry_ts <= approved_at:
                errors.append("expiry_must_follow_approval")
            if review_due and expiry_ts < review_due:
                errors.append("expiry_must_not_precede_review")
        except ValueError as exc:
            errors.append(str(exc))

    resolved_at = record.get("resolved_at")
    if status == "resolved" and not resolved_at:
        errors.append("resolved_requires_resolved_at")
    if status != "resolved" and resolved_at:
        errors.append("resolved_at_only_for_resolved")

    if status in {"expired", "revoked", "resolved"} and record.get("active") is True:
        errors.append("terminal_status_cannot_be_active")

    if record.get("risk_class") == "D3" and record.get("approved_by_kind") not in {"human", "qualified_human"}:
        errors.append("d3_requires_human_approval")

    return sorted(set(errors))


def main() -> int:
    contract = load(CONTRACT_PATH)
    fixtures = load(FIXTURE_PATH)

    if contract.get("schema_version") != "1.0.0":
        raise SystemExit("unsupported contract schema")
    rules = contract.get("rules", {})
    required_true = [
        "approval_never_means_pass",
        "underlying_gate_state_must_not_be_mutated_by_deferral",
        "unknown_evidence_must_remain_unknown",
        "reopening_trigger_required",
        "compensating_controls_required",
        "evidence_refs_required",
        "accountable_owner_required",
        "review_due_required_while_candidate_or_approved",
        "d3_remains_human_reserved",
    ]
    for key in required_true:
        if rules.get(key) is not True:
            raise SystemExit(f"contract invariant missing: {key}")

    failures: list[str] = []
    results: list[dict[str, Any]] = []
    for case in fixtures["cases"]:
        errors = validate_record(case["record"], contract)
        valid = not errors
        expected = bool(case["expect_valid"])
        if valid != expected:
            failures.append(f"{case['case_id']}: expected valid={expected}, got errors={errors}")
        expected_errors = set(case.get("expected_errors", []))
        if expected_errors and not expected_errors.issubset(set(errors)):
            failures.append(f"{case['case_id']}: missing expected errors {sorted(expected_errors - set(errors))}")
        results.append({"case_id": case["case_id"], "valid": valid, "errors": errors})

    output = {
        "contract_id": contract["contract_id"],
        "cases": results,
        "failures": failures,
        "pass_semantics_forbidden": True,
        "underlying_gate_mutation_forbidden": True,
        "repository_validator_is_non_authoritative": True,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
