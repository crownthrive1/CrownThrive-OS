#!/usr/bin/env python3
"""Validate CrownThrive's agent-sovereign governance control plane."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "developers/manifests/agent-sovereign-governance.v1.json"
NOTIFY = ROOT / "developers/manifests/pm-notification-routing.v1.json"
SECURITY = ROOT / "developers/manifests/security-self-healing-policy.v1.json"
ACTIONS = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
REPO_STATE = ROOT / "developers/manifests/repository-governance-enforcement-state.v1.json"
GITHUB_TARGET = ROOT / "developers/manifests/github-main-enforcement-target.v1.json"
DOCS_WORKFLOW = ROOT / ".github/workflows/docs-governance.yml"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"
MERGE_WORKFLOW = ROOT / ".github/workflows/governed-merge-gate.yml"
MERGE_DECISION = ROOT / "scripts/governed_merge_decision.py"
RELAY = ROOT / "automation/institutional-hourly-agent-relay.mdx"
PERMISSIONS = ROOT / "automation/permissions-and-approval-gates.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def data(path: Path) -> dict:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(path: Path, fragment: str) -> None:
    if fragment not in path.read_text(encoding="utf-8"):
        fail(f"Required fragment {fragment!r} missing from {path.relative_to(ROOT)}")


def main() -> int:
    agent = data(AGENT)
    notify = data(NOTIFY)
    security = data(SECURITY)
    actions = data(ACTIONS)
    repo = data(REPO_STATE)
    github_target = data(GITHUB_TARGET)

    if agent.get("decision_id") != "CT-ADR-GOV-011" or agent.get("phase") != "2.99":
        fail("CT-ADR-GOV-011 / Phase 2.99 identity drifted")
    if agent.get("authority_model") != "agent_sovereign_fail_closed_with_provider_merge_perimeter":
        fail("Agent authority model must remain fail-closed with provider merge perimeter")
    if agent.get("repository_provider_role") != "required_technical_enforcement_evidence_ci_scan_and_transport_not_sovereign_authority":
        fail("GitHub role drifted from required technical perimeter/evidence/transport")
    if agent.get("github_branch_protection_dependency") is not True:
        fail("GitHub main enforcement is now required defense-in-depth for Phase 3")
    if agent.get("canonical_roadmap_generation") != "ten_phase_v1":
        fail("Canonical roadmap must remain ten_phase_v1")

    voters = [item for item in agent.get("voter_pool", []) if item.get("vote_eligible") is True]
    if len(voters) != 5:
        fail(f"Expected five eligible voters, found {len(voters)}")
    expected_voters = {
        "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
        "ct.relay.agent-d", "ct.relay.agent-s",
    }
    if {item.get("agent_id") for item in voters} != expected_voters:
        fail("Eligible voter identities drifted")

    quorum = agent.get("quorum", {})
    if float(quorum.get("approval_ratio", 0)) != 0.75 or quorum.get("rounding") != "ceil":
        fail("Quorum must remain ceil(75%)")
    if math.ceil(len(voters) * 0.75) != 4 or quorum.get("current_minimum_approvals") != 4:
        fail("Five-agent 75% quorum must require four approvals")
    if quorum.get("abstention_counts_as_approval") is not False:
        fail("Abstentions cannot count as approvals")
    if quorum.get("missing_vote_counts_as_approval") is not False:
        fail("Missing votes cannot count as approvals")
    if quorum.get("deny_or_block_vote_prevents_automatic_merge") is not True:
        fail("Deny/block must prevent automatic merge")
    if quorum.get("quorum_cannot_override_d3") is not True:
        fail("Agent quorum cannot override D3")

    merge_policy = agent.get("merge_policy", {})
    merge_required = set(merge_policy.get("required", []))
    for gate in {
        "institutional_documentation_validation_passed",
        "security_governance_validation_passed",
        "github_actions_runtime_policy_passed",
        "always_run_governed_merge_gate_passed",
        "trusted_changed_files_bound_to_provider_or_git_diff",
        "changed_domain_classification_complete_and_provenanced",
        "quorum_met",
        "independent_gatekeeper_approval_present",
    }:
        if gate not in merge_required:
            fail(f"Required merge gate missing: {gate}")
    if merge_policy.get("github_required_check_context") != "CrownThrive governed merge gate":
        fail("Stable GitHub required-check context drifted")
    if merge_policy.get("phase_3_requires_provider_enforcement") is not True:
        fail("Phase 3 must require provider main enforcement")

    changed_contract = agent.get("changed_domain_contract", {})
    if changed_contract.get("classification_source") != "trusted_git_diff_exact_set_plus_per_file_domain_classification":
        fail("Changed-domain classification must be rooted in trusted Git diff exact-set binding")
    if changed_contract.get("trusted_changed_files_source") != "exact_git_base_head_diff":
        fail("Material changed-file source must be exact Git base/head diff")
    if changed_contract.get("trusted_changed_files_required_for_material_risk_classes") is not True:
        fail("Material D1/D2/D3 packets must require trusted changed files")
    if changed_contract.get("packet_changed_files_must_exactly_match_trusted_diff") is not True:
        fail("Packet changed_files must exactly match trusted Git diff")
    if changed_contract.get("git_diff_rename_handling") != "no_renames_delete_plus_add":
        fail("Git diff binding must preserve renamed-away sensitive paths as delete + add")
    if changed_contract.get("changed_domains_are_derived_not_authoritative") is not True:
        fail("Caller changed_domains must not be authoritative")
    if changed_contract.get("asserted_changed_domains_must_match_derived") is not True:
        fail("Caller changed_domains assertion must match derived domains")
    if changed_contract.get("unclassified_material_file_fails_closed") is not True:
        fail("Unclassified material files must fail closed")

    rating = agent.get("risk_rating", {})
    if rating.get("minimum_automatic_merge_score") != 85:
        fail("Automatic merge score threshold must remain 85")
    if round(sum(float(v) for v in rating.get("dimensions", {}).values()), 8) != 1.0:
        fail("Risk-rating weights must sum to 1.0")
    if rating.get("weighted_votes") is not False:
        fail("Votes must remain one-agent/one-vote")

    recipients = notify.get("recipient_policy", {})
    if set(recipients) != {
        "founder_tracking", "institutional_tracking", "collab_portal_fallback_tracking"
    }:
        fail("PM recipient references drifted")
    if notify.get("privacy", {}).get("public_repository_stores_recipient_refs_not_addresses") is not True:
        fail("Public repository must store PM recipient references, not private addresses")
    for item in recipients.values():
        if "@" in str(item.get("runtime_ref", "")):
            fail("Runtime recipient ref contains an email address")

    required_collab_gates = {
        "credential_exact_match=passed",
        "project_meta_authenticated=passed",
        "institutional_project_uid=pinned",
        "approved_field_map=approved",
        "authenticated_project_read=passed",
        "bounded_write_readback=passed",
        "webhook_sender_delivery_integrity=passed",
    }
    if set(notify.get("collab_portal_fallback", {}).get("disable_only_when_all", [])) != required_collab_gates:
        fail("Collab fallback disable gates drifted")

    github_security = security.get("github_security_evidence", {})
    if security.get("crypto_blockchain_guardrails", {}).get("production_token_or_currency_status") != "research_target_not_activated":
        fail("CHLOM crypto/token status must remain research_target_not_activated")
    if security.get("crypto_blockchain_guardrails", {}).get("phase_9_dependency") is not True:
        fail("Advanced blockchain/crypto activation must remain Phase 9-gated")
    if github_security.get("github_blocking") != "not_relied_upon_as_sovereign_merge_authority":
        fail("GitHub security evidence must not become sovereign merge authority")
    if github_security.get("codeql_execution_mode") != "github_default_setup_provider_managed":
        fail("CodeQL provider execution mode drifted")

    runtime_gate = agent.get("github_actions_runtime_gate", {})
    if runtime_gate.get("target_runtime") != "node24" or runtime_gate.get("node20") != "prohibited":
        fail("Agent runtime gate must require Node 24 and prohibit Node 20")
    if runtime_gate.get("remote_action_refs") != "full_commit_sha_only":
        fail("Agent runtime gate must require full commit SHA action references")
    if runtime_gate.get("direct_to_main_dependency_repair") is not False:
        fail("Agents must not direct-write dependency self-heals to main")
    if actions.get("status") != "active_fail_closed" or actions.get("target_runtime") != "node24":
        fail("Machine GitHub Actions runtime policy drifted")

    github_gate = agent.get("github_main_enforcement_gate", {})
    if github_gate.get("target_manifest") != "developers/manifests/github-main-enforcement-target.v1.json":
        fail("GitHub main enforcement target manifest drifted")
    if github_gate.get("required_for_phase_3") is not True:
        fail("GitHub main enforcement must be a Phase 3 hard dependency")
    if github_gate.get("required_status_context") != "CrownThrive governed merge gate":
        fail("Required GitHub merge-gate context drifted")
    if github_gate.get("sovereign_authority") is not False:
        fail("GitHub enforcement must not become sovereign authority")

    target = github_target.get("required_target", {})
    if github_target.get("phase_3_entry") != "github_main_perimeter_passed_but_phase3_still_blocked_pending_all_phase_2_99_hard_exit":
        fail("GitHub main target must record perimeter passed while preserving the overall Phase 2.99 hard gate")
    if github_target.get("activation_state") != "ruleset_enforced_behavior_verified":
        fail("GitHub ruleset enforcement must be behaviorally verified before this state can pass")
    if target.get("pull_request_required") is not True:
        fail("Main target must require pull requests")
    if target.get("required_status_check", {}).get("job") != "CrownThrive governed merge gate":
        fail("Main target required check job drifted")
    if target.get("required_status_check", {}).get("must_emit_on_every_pull_request") is not True:
        fail("Required check must emit on every pull request")
    if target.get("force_pushes_allowed") is not False or target.get("branch_deletion_allowed") is not False:
        fail("Main target must block force pushes and deletion")
    behavioral = github_target.get("provider_evidence", {}).get("behavioral_negative_test", {})
    if behavioral.get("state") != "passed" or behavioral.get("provider_mergeable_state") != "blocked":
        fail("GitHub main perimeter requires a passed behavioral negative proof with provider mergeable_state=blocked")
    if behavioral.get("required_job") != "CrownThrive governed merge gate" or behavioral.get("required_job_conclusion") != "failure":
        fail("Behavioral proof must demonstrate the exact required governed-merge job failed")
    if behavioral.get("test_branch_closed_without_merge") is not True:
        fail("Behavioral test PR must remain closed without merge")

    never = set(agent.get("self_healing", {}).get("never", []))
    for item in {
        "force_node24_for_an_unupgraded_action",
        "allow_insecure_node_runtime_escape_hatch",
        "auto_merge_dependency_update_without_governed_validation",
        "treat_provider_branch_protection_as_sovereign_authority",
        "trust_caller_declared_changed_files_without_git_diff_binding",
    }:
        if item not in never:
            fail(f"Missing self-healing prohibition: {item}")

    if repo.get("agent_merge_policy") != "fail_closed_quorum_and_validation":
        fail("Repository state must register the agent fail-closed merge policy")
    if repo.get("github_merge_gate_enforced") is not True:
        fail("Ruleset-based GitHub merge gate must remain enforced after behavioral verification")
    if repo.get("github_branch_protection_required_for_phase_3") is not True:
        fail("GitHub branch protection must now remain a Phase 3 dependency")
    observed = repo.get("observed_enforcement", {})
    if observed.get("branch_protected") is not True:
        fail("Current branch read must remain protected=true while the verified ruleset is active")
    if observed.get("classic_branch_protection_enabled") is not False:
        fail("Classic branch protection observation must remain explicit and distinct from ruleset enforcement")
    if observed.get("ruleset_behavioral_evidence", {}).get("evidence_state") != "passed":
        fail("Repository state must preserve passed ruleset behavioral evidence")

    for fragment in (
        "python scripts/validate_github_actions_runtime_policy.py",
        "python scripts/validate_agent_sovereign_governance.py",
        "python scripts/governed_merge_decision.py --self-test",
        "python scripts/resolve_pm_notification_recipients.py --self-test",
        "python scripts/security_self_heal_plan.py --self-test",
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7",
    ):
        require(DOCS_WORKFLOW, fragment)

    for fragment in (
        "name: Security Governance",
        "name: Validate provider-managed CodeQL compatibility",
        "CodeQL default setup is provider-managed",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0",
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7",
        "python scripts/validate_github_actions_runtime_policy.py",
        "python scripts/validate_security_governance.py",
    ):
        require(SECURITY_WORKFLOW, fragment)
    if re.search(r"^\s*uses:\s*github/codeql-action/", SECURITY_WORKFLOW.read_text(encoding="utf-8"), flags=re.MULTILINE):
        fail("Advanced CodeQL configuration conflicts with registered GitHub default setup")

    for fragment in (
        "name: Governed Merge Gate",
        "name: CrownThrive governed merge gate",
        "fetch-depth: 0",
        "persist-credentials: false",
        "name: Bind governed changed files to trusted Git diff",
        "--verify-git-diff",
        "CT_GIT_BASE_SHA",
        "CT_GIT_HEAD_SHA",
        "python scripts/validate_docs.py",
        "python scripts/validate_security_governance.py",
        "python scripts/validate_repository_governance_enforcement_state.py",
        "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294 # v5.0.0",
    ):
        require(MERGE_WORKFLOW, fragment)

    for fragment in (
        "trusted_changed_files_from_git",
        "changed_files_trusted_diff_mismatch",
        "trusted_changed_files_missing",
        "--verify-git-diff",
        "--git-base",
        "--git-head",
    ):
        require(MERGE_DECISION, fragment)

    require(RELAY, "Agent S — Security & Resilience Sentinel")
    require(RELAY, "75% quorum")
    require(RELAY, "Collab Portal fallback tracking mailbox")
    require(PERMISSIONS, "## Agent-sovereign quorum and specialist gates")

    print("Agent-sovereign governance validation passed.")
    print("Eligible voters: 5; 75% quorum: 4 approvals; Agent D remains independent gatekeeper.")
    print("Material D1/D2/D3 changed files: exact trusted Git base/head diff binding required before specialist classification.")
    print("GitHub: ruleset-based main perimeter behaviorally verified; exact required gate remains defense-in-depth, not sovereign authority.")
    print("GitHub Actions: Node 24 fail-closed runtime gate; full-SHA action refs; governed dependency repair.")
    print("GitHub CodeQL: provider-managed default setup; duplicate advanced workflow prohibited.")
    print("D3: reserved human/specialist authority; no agent quorum substitution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
