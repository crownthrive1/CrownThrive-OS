#!/usr/bin/env python3
"""Validate CrownThrive-Support repository governance state.

S106 records GitHub's observed control plane. CT-ADR-GOV-011 supersedes the
assumption that GitHub branch protection is CrownThrive's sovereign governance
gate: governed agents now enforce fail-closed merge authority while GitHub CI,
security scans and post-merge revalidation remain independent evidence and
defense-in-depth.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/repository-governance-enforcement-state.v1.json"
DOCS_WORKFLOW = ROOT / ".github/workflows/docs-governance.yml"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"
STANDARD = ROOT / "standards/documentation-source-of-truth-and-autonomous-governance.mdx"
PLAN = ROOT / "changelog/phase-2-99-plan.mdx"
GATE = ROOT / "technology/phase-3-readiness-gate.mdx"
CHARTER = ROOT / "standards/ten-phase-institutional-program-charter.mdx"
RELAY = ROOT / "automation/institutional-hourly-agent-relay.mdx"
PERMISSIONS = ROOT / "automation/permissions-and-approval-gates.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def text(path: Path) -> str:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(path: Path, fragment: str) -> None:
    if fragment not in text(path):
        fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")


def main() -> int:
    data = json.loads(text(MANIFEST))
    expected = {
        "manifest_version": "1.1.0",
        "manifest_id": "ct.manifest.repository-governance-enforcement.v1",
        "source_id": "S106",
        "phase": "2.99",
        "repository": "crownthrive1/CrownThrive-Support",
        "branch": "main",
        "current_state": "agent_sovereign_policy_with_github_monitoring_scanning_and_post_merge_defense_in_depth",
        "merge_gate_enforced": False,
        "github_merge_gate_enforced": False,
        "agent_merge_policy": "fail_closed_quorum_and_validation",
        "github_branch_protection_required_for_phase_3": False,
        "policy_transition_enforcement": "agent_sovereign_with_independent_ci_and_security_evidence",
        "docs_impact": "docs_updated",
        "phase_3_entry_effect": "github_branch_protection_nonblocking; other_phase_2_99_hard_exit_requirements_remain_binding",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            fail(f"{key} drifted: {data.get(key)!r} != {value!r}")

    workflow = data.get("workflow", {})
    for key in (
        "pull_request_validation", "push_to_main_revalidation",
        "scheduled_security_revalidation",
    ):
        if workflow.get(key) is not True:
            fail(f"Workflow invariant {key} must be true")

    observed = data.get("observed_enforcement", {})
    if observed.get("branch_protected") is not False:
        fail("S106 currently requires branch_protected=false")
    if observed.get("classic_branch_protection_enabled") is not False:
        fail("S106 currently requires classic_branch_protection_enabled=false")
    if observed.get("required_status_checks_enforcement") != "off":
        fail("S106 currently requires required_status_checks_enforcement=off")
    if observed.get("required_contexts") != [] or observed.get("required_checks") != []:
        fail("S106 current observation must not fabricate required contexts/checks")
    if observed.get("ruleset_inventory") != "not_directly_enumerated_by_current_connector":
        fail("Ruleset inventory uncertainty must remain explicit")

    agent = data.get("agent_policy", {})
    if agent.get("decision_id") != "CT-ADR-GOV-011":
        fail("Agent decision ID drifted")
    if agent.get("eligible_voters") != 5 or agent.get("minimum_approvals") != 4:
        fail("Five-agent 75% quorum must require four approvals")
    if float(agent.get("approval_ratio", 0)) != 0.75:
        fail("Approval ratio must remain 75%")
    if agent.get("independent_gatekeeper_required") is not True:
        fail("Independent gatekeeper approval is required")
    if agent.get("minimum_automatic_merge_score") != 85:
        fail("Automatic merge risk threshold drifted")
    if agent.get("deny_or_block_prevents_automatic_merge") is not True:
        fail("Deny/block must stop automated merge")
    if agent.get("d3_quorum_substitution") is not False:
        fail("Agent quorum cannot substitute for D3 authority")

    github = data.get("github_role", {})
    if github.get("sovereign_merge_authority") is not False:
        fail("GitHub cannot be promoted to sovereign merge authority")
    if github.get("branch_protection") != "optional_defense_in_depth_not_trust_anchor":
        fail("GitHub branch-protection role drifted")
    for key in ("repository_transport", "ci_evidence", "codeql_evidence", "dependency_review_evidence", "post_merge_revalidation"):
        if github.get(key) is not True:
            fail(f"GitHub defense-in-depth invariant {key} must remain true")

    target = data.get("target", {})
    if target.get("sovereign_merge_authority") != "governed_agents_plus_reserved_human_authority":
        fail("Sovereign merge authority drifted")
    if target.get("agent_failed_validation_mergeability") != "blocked":
        fail("Failed agent validation must remain blocked")
    if target.get("github_branch_protection") != "optional_defense_in_depth":
        fail("GitHub branch protection must remain optional defense-in-depth")
    if target.get("bypass_authority") != "explicit_D3_decision":
        fail("Bypass authority must remain D3")

    forbidden = set(data.get("forbidden_promotions", []))
    for item in {
        "github_ci_success_to_sovereign_authority",
        "agent_quorum_to_D3_authority_without_authorized_human",
        "security_failure_to_pass_by_disabling_or_weakening_the_check",
    }:
        if item not in forbidden:
            fail(f"Missing forbidden promotion: {item}")

    for fragment in (
        "name: Documentation Governance",
        "name: Validate institutional documentation",
        "python scripts/validate_docs.py",
        "python scripts/validate_agent_sovereign_governance.py",
    ):
        require(DOCS_WORKFLOW, fragment)
    for fragment in (
        "name: Security Governance",
        "github/codeql-action/init@v4",
        "actions/dependency-review-action@v4",
    ):
        require(SECURITY_WORKFLOW, fragment)

    require(RELAY, "GitHub is not the sovereign merge authority")
    require(RELAY, "75% quorum")
    require(PERMISSIONS, "## Agent-sovereign quorum and specialist gates")
    require(PLAN, "CT-ADR-GOV-011")
    require(GATE, "CT-ADR-GOV-011")
    require(CHARTER, "CT-ADR-GOV-011")
    require(STANDARD, "CT-ADR-GOV-011")

    print("Repository governance state validation passed.")
    print("GitHub observed branch protection: false; GitHub merge gate enforced: false.")
    print("Sovereign merge policy: CrownThrive agent fail-closed quorum + validation + reserved D3 human authority.")
    print("Phase 3: GitHub branch protection is nonblocking; all other Phase 2.99 hard-exit requirements remain binding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
