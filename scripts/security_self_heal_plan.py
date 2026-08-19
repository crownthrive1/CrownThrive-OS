#!/usr/bin/env python3
"""Normalize security findings into a fail-closed CrownThrive healing plan.

This script never performs production mutation, credential rotation, privilege
change, or merge. It classifies repair work for a governed executor.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "developers/manifests/security-self-healing-policy.v1.json"
RANK = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def plan(findings: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    normalized = []
    block = False
    needs_human = False
    for finding in findings:
        sev = str(finding.get("severity", "informational")).lower()
        if sev not in RANK:
            sev = "high"
        rule_id = str(finding.get("rule_id", "unknown"))
        path = str(finding.get("path", "unknown"))
        autofix_safe = finding.get("autofix_safe") is True
        authority = str(finding.get("authority_class", "D1")).upper()
        action = "record"
        if sev in {"critical", "high"}:
            block = True
            action = "bounded_patch_then_full_revalidation" if autofix_safe and authority in {"D0", "D1"} else "block_and_escalate"
        elif sev == "medium":
            action = "bounded_patch_or_governed_delta"
        elif sev == "low":
            action = "queue_or_d1_fix"
        if authority == "D3":
            needs_human = True
            action = "human_reserved_remediation"
        normalized.append({
            "severity": sev, "rule_id": rule_id, "path": path,
            "authority_class": authority, "autofix_safe": autofix_safe,
            "action": action,
        })
    normalized.sort(key=lambda x: (-RANK[x["severity"]], x["path"], x["rule_id"]))
    return {
        "merge_blocked": block or needs_human,
        "human_authority_required": needs_human,
        "findings": normalized,
        "post_heal_requirements": policy["self_heal"]["post_heal_requirements"],
        "prohibited_shortcuts": [
            "weaken_or_disable_the_failing_check",
            "suppress_a_high_or_critical_finding_without_evidence",
            "expose_or_reconstruct_secrets",
            "self_approve_the_originating_material_change",
        ],
    }


def self_test(policy: dict[str, Any]) -> None:
    result = plan([
        {"severity": "high", "rule_id": "x", "path": "a.py", "autofix_safe": True, "authority_class": "D1"},
        {"severity": "low", "rule_id": "y", "path": "b.md", "autofix_safe": True, "authority_class": "D1"},
    ], policy)
    assert result["merge_blocked"] is True
    assert result["findings"][0]["action"] == "bounded_patch_then_full_revalidation"
    d3 = plan([{"severity": "medium", "rule_id": "cred", "path": "runtime", "authority_class": "D3"}], policy)
    assert d3["human_authority_required"] is True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings-json", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    policy = load(POLICY)
    if args.self_test:
        self_test(policy)
        print("Security self-heal planner self-test passed; high/critical and D3 remain fail-closed.")
        return 0
    if not args.findings_json:
        parser.error("--findings-json is required unless --self-test is used")
    raw = load(args.findings_json)
    findings = raw if isinstance(raw, list) else raw.get("findings", [])
    print(json.dumps(plan(findings, policy), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
