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
REPO_STATE = ROOT / "developers/manifests/repository-governance-enforcement-state.v1.json"
DOCS_WORKFLOW = ROOT / ".github/workflows/docs-governance.yml"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security-governance.yml"
RELAY = ROOT / "automation/institutional-hourly-agent-relay.mdx"
PERMISSIONS = ROOT / "automation/permissions-and-approval-gates.mdx"
ADVANCED_CODEQL_USE = re.compile(r"^\s*uses:\s*github/codeql-action/", re.MULTILINE)

EXPECTED_SPECIALIST_ENDORSEMENTS = {
    "security", "legal_regulatory", "operations_sre", "blockchain_protocol",
    "ai_ml_llm_tevv", "ip_rights_licensing", "finance_tax_treasury",
    "accessibility_consumer_protection", "regional_global_localization",
}

REQUIRED_SUBAGENTS = {
    "governance_marshal", "verification_tevv", "recovery_rollback",
    "legal_regulatory", "operations_sre", "blockchain_protocol",
    "ai_ml_llm_tevv", "ip_rights_licensing", "finance_tax_treasury",
    "accessibility_consumer_protection", "regional_global_localization",
    "evidence_provenance",
}


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
    repo = data(REPO_STATE)

    if agent.get("decision_id") != "CT-ADR-GOV-011" or agent.get("phase") != "2.99":
        fail("CT-ADR-GOV-011 / Phase 2.99 identity drifted")
    if agent.get("manifest_version") != "1.1.0":
        fail("Agent governance manifest must be unanimous-first version 1.1.0")
    if agent.get("authority_model") != "agent_sovereign_fail_closed_unanimous_first":
        fail("Agent authority model must remain fail-closed and unanimous-first")
    if agent.get("repository_provider_role") != "evidence_ci_scan_and_transport_not_sovereign_authority":
        fail("GitHub role drifted from evidence/CI/scan/transport")
    if agent.get("github_branch_protection_dependency") is not False:
        fail("GitHub branch protection must not be a sovereign dependency")
    if agent.get("canonical_roadmap_generation") != "ten_phase_v1":
        fail("Canonical roadmap must remain ten_phase_v1")

    voters = [item for item in agent.get("voter_pool", []) if item.get("vote_eligible") is True]
    expected_voters = {
        "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
        "ct.relay.agent-d", "ct.relay.agent-s",
    }
    if len(voters) != 5 or {item.get("agent_id") for item in voters} != expected_voters:
        fail("Exactly five canonical sovereign voters A/B/C/D/S must remain registered")

    quorum = agent.get("quorum", {})
    if quorum.get("normal_mode") != "unanimous" or float(quorum.get("normal_approval_ratio", 0)) != 1.0:
        fail("Normal sovereign decision mode must require unanimity")
    if quorum.get("current_normal_minimum_approvals") != 5:
        fail("Five-agent normal mode must require five approvals")
    if quorum.get("abstention_counts_as_approval") is not False or quorum.get("missing_vote_counts_as_approval") is not False:
        fail("Missing/abstain cannot count as approval")
    if quorum.get("deny_or_block_vote_prevents_normal_merge") is not True:
        fail("Any deny/block must prevent normal unanimous merge")
    if quorum.get("quorum_cannot_override_d3") is not True:
        fail("Sovereign votes cannot override D3")

    override = quorum.get("deadlock_override", {})
    special_ratio = float(override.get("special_vote_ratio", 0))
    special_required = math.ceil(len(voters) * special_ratio)
    if override.get("enabled") is not True:
        fail("Disciplined deadlock override must remain enabled")
    if override.get("minimum_elapsed_hours") != 6:
        fail("Deadlock override wait window must remain six hours")
    if override.get("minimum_reconciliation_attempts") != 2:
        fail("Deadlock override must require at least two reconciliation attempts")
    if special_ratio < (2 / 3) or special_required != 4 or override.get("current_special_vote_minimum_approvals") != 4:
        fail("Five-agent deadlock special vote must be at least 2/3 rounded up = four approvals")
    for flag in (
        "all_sovereign_votes_must_be_cast", "independent_gatekeeper_must_approve",
        "security_sentinel_must_approve_when_security_is_required", "cannot_override_hard_blocks",
        "cannot_override_missing_specialists", "cannot_override_failed_or_stale_required_ci",
        "cannot_override_d3_or_human_reserved_authority", "cannot_override_critical_or_high_security_finding",
        "cannot_override_secret_credential_or_privilege_failure",
        "cannot_override_legal_rights_or_irreversible_authority_block",
        "override_reason_and_evidence_required",
    ):
        if override.get(flag) is not True:
            fail(f"Deadlock override safety invariant drifted: {flag}")
    if override.get("initiator_agent_id") != "ct.subagent.governance-marshal":
        fail("Only Governance Marshal may initiate the deadlock override protocol")
    if override.get("initiator_is_non_voting") is not True:
        fail("Governance Marshal must remain non-voting")

    rating = agent.get("risk_rating", {})
    if rating.get("minimum_automatic_merge_score") != 85:
        fail("Automatic merge score threshold must remain 85")
    if round(sum(float(value) for value in rating.get("dimensions", {}).values()), 8) != 1.0:
        fail("Risk-rating weights must sum to 1.0")
    if rating.get("weighted_votes") is not False:
        fail("Votes must remain one-agent/one-vote")

    specialist_registry = agent.get("specialist_activation", {})
    if not isinstance(specialist_registry, dict) or len(specialist_registry) != 9:
        fail("Exactly nine rule-based specialist activation cells must be registered")
    endorsement_ids = {item.get("endorsement_id") for item in specialist_registry.values() if isinstance(item, dict)}
    if endorsement_ids != EXPECTED_SPECIALIST_ENDORSEMENTS:
        fail(f"Specialist endorsement registry drifted: {sorted(endorsement_ids)}")
    for key, item in specialist_registry.items():
        if not isinstance(item, dict) or not item.get("required_patterns"):
            fail(f"Specialist {key} must have rule-based activation patterns")
        if not item.get("authority") and not item.get("agent_id"):
            fail(f"Specialist {key} must declare authority or assigned agent")

    subagents = agent.get("subagent_registry", {})
    if not isinstance(subagents, dict) or set(subagents) != REQUIRED_SUBAGENTS:
        fail("Governed non-voting subagent registry drifted")
    for key, item in subagents.items():
        if not isinstance(item, dict) or item.get("vote_eligible") is not False:
            fail(f"Subagent {key} must remain non-voting")
        if not item.get("agent_id") or not item.get("role"):
            fail(f"Subagent {key} must declare stable id and role")

    healing = agent.get("self_healing", {})
    evolution = healing.get("evolution_policy", {})
    refractory = healing.get("refractory_policy", {})
    if healing.get("enabled") is not True:
        fail("Self-healing must remain enabled")
    for flag in (
        "same_failure_must_not_repeat_without_new_evidence",
        "failed_repair_requires_root_cause_reassessment",
        "validators_and_security_controls_cannot_be_weakened_to_self_heal",
        "repair_must_rerun_original_failed_control",
        "repair_must_rerun_full_applicable_control_family",
    ):
        if refractory.get(flag) is not True:
            fail(f"Refractory self-healing invariant drifted: {flag}")
    if evolution.get("governance_marshal_may_propose_new_subagents") is not True:
        fail("Governance Marshal must be able to propose bounded subagent evolution")
    if evolution.get("new_subagents_are_non_voting_by_default") is not True:
        fail("New subagents must default to non-voting")
    if evolution.get("changes_to_sovereign_voter_identity_unanimity_rule_deadlock_override_floor_or_d3_boundary_require_founder_authorization") is not True:
        fail("Core sovereign authority changes must remain founder-reserved")

    recipients = notify.get("recipient_policy", {})
    if set(recipients) != {"founder_tracking", "institutional_tracking", "collab_portal_fallback_tracking"}:
        fail("PM recipient references drifted")
    if notify.get("privacy", {}).get("public_repository_stores_recipient_refs_not_addresses") is not True:
        fail("Public repository must store PM recipient references, not private addresses")
    for item in recipients.values():
        if "@" in str(item.get("runtime_ref", "")):
            fail("Runtime recipient ref contains an email address")

    required_collab_gates = {
        "credential_exact_match=passed", "project_meta_authenticated=passed",
        "institutional_project_uid=pinned", "approved_field_map=approved",
        "authenticated_project_read=passed", "bounded_write_readback=passed",
        "webhook_sender_delivery_integrity=passed",
    }
    actual_gates = set(notify.get("collab_portal_fallback", {}).get("disable_only_when_all", []))
    if actual_gates != required_collab_gates:
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

    if repo.get("agent_merge_policy") != "fail_closed_quorum_and_validation":
        fail("Repository state must register the fail-closed agent merge policy")

    for fragment in (
        "python scripts/validate_agent_sovereign_governance.py",
        "python scripts/governed_merge_decision.py --self-test",
        "python scripts/resolve_pm_notification_recipients.py --self-test",
        "python scripts/security_self_heal_plan.py --self-test",
    ):
        require(DOCS_WORKFLOW, fragment)
    for fragment in (
        "name: Security Governance",
        "name: Validate provider-managed CodeQL compatibility",
        "CodeQL default setup is provider-managed",
        "python scripts/validate_security_governance.py",
    ):
        require(SECURITY_WORKFLOW, fragment)
    if ADVANCED_CODEQL_USE.search(SECURITY_WORKFLOW.read_text(encoding="utf-8")):
        fail("Advanced CodeQL configuration conflicts with registered GitHub default setup")

    require(RELAY, "Agent S — Security & Resilience Sentinel")
    require(RELAY, "Collab Portal fallback tracking mailbox")
    require(PERMISSIONS, "## Agent-sovereign quorum and specialist gates")

    print("Agent-sovereign governance validation passed.")
    print("Normal sovereign vote: 5/5 unanimous; Agent D remains mandatory independent gatekeeper.")
    print("Deadlock override: after 6 hours and >=2 reconciliation attempts, 2/3 rounded up = 4/5; all five votes must be cast; hard blocks/D3/specialist/security boundaries remain non-overridable.")
    print("Rule-based specialist cells: 9; governed non-voting subagents: 12.")
    print("Self-healing: refractory rerun/original-control/root-cause rules enforced; Governance Marshal may propose bounded evolution but cannot self-expand sovereign authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
