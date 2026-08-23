#!/usr/bin/env python3
"""Classify CrownThrive governance CI failures without inventing policy dispositions.

The classifier deliberately separates CI/evidence transport failures from institutional
HOLD/DENY decisions. A workflow failure is never promoted to POLICY_DENY or POLICY_HOLD
unless an authoritative validator explicitly emits a policy disposition marker.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

POLICY_MARKER = re.compile(r"CT_POLICY_DISPOSITION\s*[:=]\s*(ECAC|ALLOW|HOLD|DENY)\b", re.I)


def norm(value: str | None) -> str:
    return (value or "unknown").strip().lower()


def read_log(path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")[-20000:]


def classify(env: dict[str, str], logs: str = "") -> dict[str, object]:
    steps = {
        "hydrate_exact_git": norm(env.get("CT_STEP_HYDRATE")),
        "trusted_diff": norm(env.get("CT_STEP_TRUSTED_DIFF")),
        "documentation": norm(env.get("CT_STEP_DOCS")),
        "security": norm(env.get("CT_STEP_SECURITY")),
        "dependency_review": norm(env.get("CT_STEP_DEPENDENCY")),
    }

    marker = POLICY_MARKER.search(logs)
    explicit_policy = marker.group(1).upper() if marker else None

    failed = [name for name, outcome in steps.items() if outcome not in {"success", "skipped", "unknown"}]
    classification = "PASS"
    domain = "NONE"
    reason = "all_observed_governance_steps_passed_or_not_applicable"

    if explicit_policy == "DENY":
        classification, domain, reason = "POLICY_DENY", "POLICY", "authoritative_validator_emitted_deny"
    elif explicit_policy == "HOLD":
        classification, domain, reason = "POLICY_HOLD", "POLICY", "authoritative_validator_emitted_hold"
    elif steps["hydrate_exact_git"] not in {"success", "skipped", "unknown"}:
        classification, domain, reason = "CI_EVIDENCE_HYDRATION_FAILURE", "CI_EVIDENCE", "exact_git_objects_not_hydrated"
    elif steps["trusted_diff"] not in {"success", "skipped", "unknown"}:
        low = logs.lower()
        if "bad object" in low or "not a valid object" in low:
            classification, domain, reason = "CI_EVIDENCE_HYDRATION_FAILURE", "CI_EVIDENCE", "trusted_diff_missing_git_object"
        elif "stale" in low or "head mismatch" in low or "base mismatch" in low or "exact_head" in low:
            classification, domain, reason = "STALE_EXACT_HEAD", "SOURCE_IDENTITY", "trusted_diff_exact_head_mismatch"
        else:
            classification, domain, reason = "CONTRACT_ASSERTION_FAILURE", "GOVERNANCE_CONTRACT", "trusted_diff_contract_rejected"
    elif steps["dependency_review"] not in {"success", "skipped", "unknown"}:
        classification, domain, reason = "SUPPLY_CHAIN_DENY", "SUPPLY_CHAIN", "dependency_review_rejected_change"
    elif steps["security"] not in {"success", "skipped", "unknown"}:
        classification, domain, reason = "CONTRACT_ASSERTION_FAILURE", "SECURITY_POLICY", "deterministic_security_contract_failed"
    elif steps["documentation"] not in {"success", "skipped", "unknown"}:
        classification, domain, reason = "CONTRACT_ASSERTION_FAILURE", "DOCUMENTATION_POLICY", "documentation_contract_failed"
    elif failed:
        classification, domain, reason = "RUNTIME_UNAVAILABLE", "CI_RUNTIME", "unclassified_required_step_failed"

    return {
        "schema": "ct.schema.governance-run-classification.v1",
        "classification": classification,
        "domain": domain,
        "reason": reason,
        "steps": steps,
        "explicit_policy_disposition": explicit_policy,
        "policy_disposition_inferred": False,
        "institutional_state_inferred_from_ci": False,
        "rules": {
            "ci_failure_is_not_policy_deny": True,
            "ci_failure_is_not_policy_hold": True,
            "hold_and_deny_require_authoritative_evidence": True,
            "exact_head_identity_required": True,
        },
    }


def self_test() -> None:
    cases = [
        ({"CT_STEP_HYDRATE": "failure"}, "", "CI_EVIDENCE_HYDRATION_FAILURE"),
        ({"CT_STEP_HYDRATE": "success", "CT_STEP_TRUSTED_DIFF": "failure"}, "fatal: bad object abc", "CI_EVIDENCE_HYDRATION_FAILURE"),
        ({"CT_STEP_HYDRATE": "success", "CT_STEP_TRUSTED_DIFF": "failure"}, "head mismatch", "STALE_EXACT_HEAD"),
        ({"CT_STEP_SECURITY": "failure"}, "", "CONTRACT_ASSERTION_FAILURE"),
        ({"CT_STEP_DEPENDENCY": "failure"}, "", "SUPPLY_CHAIN_DENY"),
        ({"CT_STEP_SECURITY": "failure"}, "CT_POLICY_DISPOSITION=DENY", "POLICY_DENY"),
        ({"CT_STEP_DOCS": "success", "CT_STEP_SECURITY": "success"}, "", "PASS"),
    ]
    for env, logs, expected in cases:
        actual = classify(env, logs)["classification"]
        assert actual == expected, (env, expected, actual)
    print("Governance run classifier self-test: PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    result = classify(dict(os.environ), read_log(args.log))
    payload = json.dumps(result, sort_keys=True)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n## Governance classification\n\n")
            handle.write(f"- Classification: `{result['classification']}`\n")
            handle.write(f"- Domain: `{result['domain']}`\n")
            handle.write(f"- Reason: `{result['reason']}`\n")
            handle.write("- CI failure is not automatically an institutional HOLD or DENY.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
