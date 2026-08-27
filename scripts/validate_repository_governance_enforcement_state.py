#!/usr/bin/env python3
"""Validate CrownThrive-OS repository governance state."""

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
        "manifest_version": "1.3.0",
        "manifest_id": "ct.manifest.repository-governance-enforcement.v1",
        "source_id": "S106",
        "phase": "3",
        "historical_origin_phase": "2.99",
        "repository": "crownthrive1/CrownThrive-OS",
        "branch": "main",
        "canonical_main_sha": "1a07a8755e3b18d01ec6720ec2522b1727780c01",
        "bootstrap_pr": 64,
        "current_state": "ruleset_enforcement_behavior_verified_machine_reconciled",
        "merge_gate_enforced": True,
        "github_merge_gate_enforced": True,
        "agent_merge_policy": "fail_closed_quorum_and_validation",
        "github_branch_protection_required_for_phase_3": True,
        "policy_transition_enforcement": "agent_sovereign_plus_required_provider_merge_perimeter",
        "docs_impact": "docs_updated",
        "phase_3_execution_effect": "github_main_perimeter_verified_and_active; component_and_provider_gates_remain_independently_binding",
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
    if observed.get("branch_protected") is not True:
        fail("Current branch observation must remain protected=true while the verified ruleset is active")
    if observed.get("classic_branch_protection_enabled") is not False:
        fail("Classic branch protection observation must remain false and distinct from ruleset enforcement")
    if observed.get("classic_required_status_checks_enforcement") != "off":
        fail("Classic required-status API view must remain explicitly off unless separately observed otherwise")
    if observed.get("classic_required_contexts") != [] or observed.get("classic_required_checks") != []:
        fail("Classic branch-protection view must not fabricate required contexts/checks")
    if observed.get("ruleset_inventory") != "not_directly_enumerated_by_current_connector":
        fail("Ruleset inventory uncertainty must remain explicit")
    ruleset_config = observed.get("ruleset_configuration_evidence", {})
    for key in (
        "pull_request_required",
        "strict_up_to_date_with_main",
    ):
        if ruleset_config.get(key) is not True:
            fail(f"Ruleset configuration evidence missing required true predicate: {key}")
    if ruleset_config.get("required_status_context") != "CrownThrive governed merge gate":
        fail("Ruleset required status context drifted")
    if ruleset_config.get("force_pushes_allowed") is not False or ruleset_config.get("branch_deletion_allowed") is not False:
        fail("Ruleset evidence must preserve force-push and deletion blocking")
    if ruleset_config.get("routine_bypass_disabled") is not True:
        fail("Routine ruleset bypass must remain disabled")
    if ruleset_config.get("bypass_authority") != "explicit_D3_break_glass_only":
        fail("Ruleset bypass authority must remain D3 break-glass only")

    behavioral = observed.get("ruleset_behavioral_evidence", {})
    if behavioral.get("evidence_state") != "passed":
        fail("Ruleset behavioral proof must be passed")
    if behavioral.get("disposable_pr") != 93:
        fail("Ruleset behavioral proof PR drifted")
    if behavioral.get("required_job") != "CrownThrive governed merge gate":
        fail("Behavioral proof required job drifted")
    if behavioral.get("required_job_conclusion") != "failure":
        fail("Behavioral proof must demonstrate a deliberately failing required job")
    if behavioral.get("provider_mergeable_state") != "blocked":
        fail("Behavioral proof must preserve provider mergeable_state=blocked")
    if behavioral.get("git_graph_mergeable") is not True:
        fail("Behavioral proof must distinguish Git graph mergeability from provider gate blocking")
    if behavioral.get("closed_without_merge") is not True:
        fail("Behavioral test PR must be closed without merge")

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

    if target.get("manifest_version") != "1.1.0":
        fail("GitHub main target manifest version drifted")
    if target.get("manifest_id") != "ct.manifest.github-main-enforcement-target.v1":
        fail("Missing or invalid GitHub main enforcement target manifest")
    if target.get("activation_state") != "ruleset_enforced_behavior_verified":
        fail("Provider activation must remain ruleset_enforced_behavior_verified")
    if target.get("bootstrap_pr") != 64 or target.get("bootstrap_merge_sha") != "1a07a8755e3b18d01ec6720ec2522b1727780c01":
        fail("Bootstrap PR/merge evidence drifted")
    if target.get("phase") != "3" or target.get("historical_origin_phase") != "2.99":
        fail("GitHub main target must remain Phase 3 with explicit historical origin")
    if target.get("historical_entry_result") != "github_main_perimeter_predicate_passed":
        fail("GitHub perimeter historical entry result drifted")
    if target.get("phase_3_execution") != "repository_merge_perimeter_active_and_continuously_revalidated":
        fail("GitHub main target must remain an active Phase 3 merge perimeter")
    target_required = target.get("required_target", {})
    if target_required.get("required_status_check", {}).get("job") != "CrownThrive governed merge gate":
        fail("GitHub target required job drifted")
    if target_required.get("required_status_check", {}).get("must_emit_on_every_pull_request") is not True:
        fail("Required GitHub check must emit on every PR")
    if target_required.get("required_status_check", {}).get("strict_up_to_date_with_main") is not True:
        fail("Required GitHub check must remain strict/current-with-main")
    if target_required.get("force_pushes_allowed") is not False or target_required.get("branch_deletion_allowed") is not False:
        fail("GitHub target must block force pushes and deletion")
    if target_required.get("administrative_routine_bypass") is not False or target_required.get("bypass_mode") != "explicit_d3_break_glass_only":
        fail("GitHub target routine bypass must remain disabled with D3 break-glass only")

    provider = target.get("provider_evidence", {})
    test = provider.get("behavioral_negative_test", {})
    if test.get("state") != "passed" or test.get("provider_mergeable_state") != "blocked":
        fail("GitHub target behavioral negative proof must remain passed/blocked")
    if test.get("required_job") != "CrownThrive governed merge gate" or test.get("required_job_conclusion") != "failure":
        fail("GitHub target behavioral proof must preserve exact failing required job")
    if test.get("test_branch_closed_without_merge") is not True:
        fail("GitHub target behavioral test PR must remain closed without merge")
    predicates = target.get("required_provider_evidence", {})
    required_predicates = {
        "branch_protected_true",
        "pull_request_required",
        "governed_merge_gate_context_required",
        "strict_branch_update_required",
        "force_push_blocked",
        "branch_deletion_blocked",
        "routine_bypass_disabled",
        "d3_break_glass_only",
        "blocked_failing_check_test_or_equivalent_provider_evidence",
    }
    if set(predicates) != required_predicates or any(value != "passed" for value in predicates.values()):
        fail("All GitHub main-perimeter provider predicates must be explicitly passed")

    forbidden = set(data.get("forbidden_promotions", []))
    for item in {
        "github_ci_success_to_sovereign_authority",
        "github_branch_protection_to_sovereign_authority",
        "agent_quorum_to_D3_authority_without_authorized_human",
        "security_failure_to_pass_by_disabling_or_weakening_the_check",
    }:
        if item not in forbidden:
            fail(f"Missing forbidden promotion: {item}")

    limitations = set(data.get("known_provider_visibility_limitations", []))
    for item in {
        "classic_branch_protection_subobject_reports_off_no_contexts_while_ruleset_based_protection_is_active",
        "ruleset_inventory_not_directly_enumerated_by_current_connector",
        "codeql_alert_inventory_unavailable_to_current_audit_surface",
        "secret_scanning_push_protection_inventory_unavailable_to_current_audit_surface",
    }:
        if item not in limitations:
            fail(f"Missing provider visibility limitation: {item}")

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
        "python scripts/penta_gap_closure.py . --json",
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
        "python scripts/penta_gap_closure.py . --json",
        "python scripts/validate_security_governance.py",
        "python scripts/validate_repository_governance_enforcement_state.py",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0",
    ):
        require(MERGE_WORKFLOW, fragment)

    require(ADR, "# CT-ADR-GOV-011")
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
    print("GitHub main: protected by ruleset evidence; classic branch-protection API remains separately observed as off/no contexts.")
    print("Behavioral negative proof: exact CrownThrive governed merge gate failure produced provider mergeable_state=blocked.")
    print("Sovereign merge policy: CrownThrive agent fail-closed quorum + validation + reserved D3 human authority.")
    print("Phase 3: GitHub main perimeter is active; component and provider gates remain independently binding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
