#!/usr/bin/env python3
"""Validate CrownThrive-Support repository governance state."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/repository-governance-enforcement-state.v1.json"
TARGET = ROOT / "developers/manifests/github-main-enforcement-target.v1.json"
ACTIONS_POLICY = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
DOCS_WORKFLOW = ROOT / ".github/workflows/docs-governance.yml"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"
MERGE_WORKFLOW = ROOT / ".github/workflows/governed-merge-gate.yml"
ADR = ROOT / "changelog/adr-agent-sovereign-governance-quorum-security.md"
STANDARD_AMENDMENT = ROOT / "standards/agent-sovereign-governance-amendment-ct-adr-gov-011.md"
RUNTIME_STANDARD = ROOT / "standards/github-actions-runtime-supply-chain-standard.md"
GATE_AMENDMENT = ROOT / "technology/phase-3-readiness-gate-amendment-ct-adr-gov-011.md"
RELAY = ROOT / "automation/institutional-hourly-agent-relay.mdx"
PERMISSIONS = ROOT / "automation/permissions-and-approval-gates.mdx"
CHLOM = ROOT / "chlom/overview.mdx"
DSCAAS = ROOT / "governance/ds-caas.mdx"
SECURITY = ROOT / "SECURITY.md"


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
    target = json.loads(text(TARGET))
    actions = json.loads(text(ACTIONS_POLICY))
    expected = {
        "manifest_version": "1.2.0",
        "manifest_id": "ct.manifest.repository-governance-enforcement.v1",
        "source_id": "S106",
        "phase": "2.99",
        "repository": "crownthrive1/CrownThrive-Support",
        "branch": "main",
        "current_state": "always_run_pr_gates_bootstrapped_provider_main_enforcement_pending",
        "merge_gate_enforced": False,
        "github_merge_gate_enforced": False,
        "agent_merge_policy": "fail_closed_quorum_and_validation",
        "github_branch_protection_required_for_phase_3": True,
        "policy_transition_enforcement": "agent_sovereign_plus_required_provider_merge_perimeter",
        "docs_impact": "docs_updated",
        "phase_3_entry_effect": "blocked_until_github_main_required_check_enforcement_is_enabled_and_provider_verified; all_other_phase_2_99_hard_exit_requirements_remain_binding",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            fail(f"{key} drifted: {data.get(key)!r} != {value!r}")

    workflow = data.get("workflow", {})
    for key in (
        "pull_request_validation",
        "pull_request_checks_always_emit",
        "push_to_main_revalidation",
        "scheduled_security_revalidation",
    ):
        if workflow.get(key) is not True:
            fail(f"Workflow invariant {key} must be true")
    if workflow.get("governed_merge_job") != "CrownThrive governed merge gate":
        fail("Stable governed merge job context drifted")

    observed = data.get("observed_enforcement", {})
    if observed.get("branch_protected") is not False:
        fail("Current S106 observation must remain branch_protected=false until provider activation is verified")
    if observed.get("classic_branch_protection_enabled") is not False:
        fail("Current S106 observation must remain classic_branch_protection_enabled=false")
    if observed.get("required_status_checks_enforcement") != "off":
        fail("Current S106 observation must remain required_status_checks_enforcement=off")
    if observed.get("required_contexts") != [] or observed.get("required_checks") != []:
        fail("Current observation must not fabricate required contexts/checks")
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
    if github.get("branch_protection") != "required_defense_in_depth_merge_perimeter_not_trust_anchor":
        fail("GitHub branch-protection role drifted")
    if github.get("required_check_target") != "CrownThrive governed merge gate":
        fail("GitHub required-check target drifted")
    for key in (
        "repository_transport", "ci_evidence", "codeql_evidence",
        "dependency_review_evidence", "post_merge_revalidation",
    ):
        if github.get(key) is not True:
            fail(f"GitHub defense-in-depth invariant {key} must remain true")

    destination = data.get("target", {})
    if destination.get("sovereign_merge_authority") != "governed_agents_plus_reserved_human_authority":
        fail("Sovereign merge authority drifted")
    if destination.get("agent_failed_validation_mergeability") != "blocked":
        fail("Failed agent validation must remain blocked")
    if destination.get("github_branch_protection") != "required_defense_in_depth":
        fail("GitHub branch protection must remain required defense-in-depth")
    if destination.get("pull_request_required") is not True:
        fail("Main target must require pull requests")
    if destination.get("strict_required_status_checks") is not True:
        fail("Main target must require strict up-to-date status checks")
    if destination.get("required_status_context") != "CrownThrive governed merge gate":
        fail("Required status context drifted")
    if destination.get("force_pushes_allowed") is not False or destination.get("branch_deletion_allowed") is not False:
        fail("Main target must block force pushes and branch deletion")
    if destination.get("bypass_authority") != "explicit_D3_break_glass_only":
        fail("Bypass authority must remain explicit D3 break-glass only")

    if target.get("manifest_id") != "ct.manifest.github-main-enforcement-target.v1":
        fail("Missing or invalid GitHub main enforcement target manifest")
    if target.get("activation_state") != "pending_provider_admin_configuration_after_bootstrap_merge":
        fail("Provider activation state drifted")
    if target.get("phase_2_99_exit") != "blocking_until_provider_enforcement_verified":
        fail("GitHub provider perimeter must block Phase 2.99 exit until verified")
    if target.get("phase_3_entry") != "blocked_until_provider_enforcement_verified":
        fail("GitHub provider perimeter must block Phase 3 entry until verified")
    target_required = target.get("required_target", {})
    if target_required.get("required_status_check", {}).get("job") != "CrownThrive governed merge gate":
        fail("GitHub target required job drifted")
    if target_required.get("required_status_check", {}).get("must_emit_on_every_pull_request") is not True:
        fail("Required GitHub check must emit on every PR")

    forbidden = set(data.get("forbidden_promotions", []))
    for item in {
        "github_ci_success_to_sovereign_authority",
        "github_branch_protection_to_sovereign_authority",
        "agent_quorum_to_D3_authority_without_authorized_human",
        "security_failure_to_pass_by_disabling_or_weakening_the_check",
    }:
        if item not in forbidden:
            fail(f"Missing forbidden promotion: {item}")

    if actions.get("status") != "active_fail_closed" or actions.get("target_runtime") != "node24":
        fail("Repository runtime gate must remain active and Node 24")
    if actions.get("node20_status") != "prohibited":
        fail("Node 20 action runtime must remain prohibited")
    if actions.get("self_healing", {}).get("direct_to_main_mutation") is not False:
        fail("GitHub Actions dependency repair must not bypass governed PR/quorum flow")

    for fragment in (
        "name: Documentation Governance",
        "name: Validate institutional documentation",
        "pull_request:",
        "python scripts/validate_docs.py",
        "python scripts/validate_github_actions_runtime_policy.py",
        "python scripts/validate_agent_sovereign_governance.py",
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7",
    ):
        require(DOCS_WORKFLOW, fragment)
    for fragment in (
        "name: Security Governance",
        "pull_request:",
        "name: Validate provider-managed CodeQL compatibility",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0",
        "python scripts/validate_github_actions_runtime_policy.py",
    ):
        require(SECURITY_WORKFLOW, fragment)
    if re.search(r"^\s*uses:\s*github/codeql-action/", text(SECURITY_WORKFLOW), flags=re.MULTILINE):
        fail("Advanced CodeQL workflow conflicts with provider-managed default setup")

    for fragment in (
        "name: Governed Merge Gate",
        "name: CrownThrive governed merge gate",
        "pull_request:",
        "python scripts/validate_docs.py",
        "python scripts/validate_security_governance.py",
        "python scripts/validate_repository_governance_enforcement_state.py",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0",
    ):
        require(MERGE_WORKFLOW, fragment)

    require(ADR, "# CT-ADR-GOV-011")
    require(ADR, "Phase 3 therefore remains `blocked_pending_phase_2_99_hard_exit`")
    require(STANDARD_AMENDMENT, "required defense-in-depth merge perimeter")
    require(GATE_AMENDMENT, "GitHub main merge perimeter is a Phase 3 hard-entry dependency")
    require(GATE_AMENDMENT, "GitHub Actions runtime gate")
    require(RELAY, "GitHub is not the sovereign merge authority")
    require(RELAY, "75% quorum")
    require(PERMISSIONS, "## Agent-sovereign quorum and specialist gates")
    require(CHLOM, "Target metaprotocol architecture")
    require(DSCAAS, "Agent-sovereign enforcement")
    require(SECURITY, "Continuous Security Governance")
    require(RUNTIME_STANDARD, "# GitHub Actions Runtime and Supply-Chain Standard")
    require(RUNTIME_STANDARD, "Node 24")
    require(RUNTIME_STANDARD, "Dependabot")

    print("Repository governance state validation passed.")
    print("GitHub observed branch protection: false; provider merge gate: pending activation after bootstrap merge.")
    print("Always-run governed merge status context: CrownThrive governed merge gate.")
    print("Sovereign merge policy: CrownThrive agent fail-closed quorum + validation + reserved D3 human authority.")
    print("Phase 3: blocked until GitHub main required-check enforcement is enabled and provider-verified, plus all other Phase 2.99 hard-exit gates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
