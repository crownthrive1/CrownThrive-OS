#!/usr/bin/env python3
"""Validate CrownThrive's agent-sovereign governance control plane.

The invariant is explicit: GitHub supplies repository transport, CI and security
signals, while governed CrownThrive agents plus reserved human authority decide
whether a change may enter canonical institutional state.
"""

from __future__ import annotations

import json
import math
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
    if agent.get("authority_model") != "agent_sovereign_fail_closed":
        fail("Agent authority model must remain fail-closed")
    if agent.get("repository_provider_role") != "evidence_ci_scan_and_transport_not_sovereign_authority":
        fail("GitHub role drifted from evidence/CI/scan/transport")
    if agent.get("github_branch_protection_dependency") is not False:
        fail("GitHub branch protection must not be a sovereign dependency")
    if agent.get("canonical_roadmap_generation") != "ten_phase_v1":
        fail("Canonical roadmap must remain ten_phase_v1")

    voters = [item for item in agent.get("voter_pool", []) if item.get("vote_eligible") is True]
    if len(voters) != 5:
        fail(f"Expected five eligible voters, found {len(voters)}")
    voter_ids = {item.get("agent_id") for item in voters}
    expected_voters = {
        "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c",
        "ct.relay.agent-d", "ct.relay.agent-s",
    }
    if voter_ids != expected_voters:
        fail("Eligible voter identities drifted")

    quorum = agent.get("quorum", {})
    if float(quorum.get("approval_ratio", 0)) != 0.75 or quorum.get("rounding") != "ceil":
        fail("Quorum must remain ceil(75%)")
    required = math.ceil(len(voters) * 0.75)
    if required != 4 or quorum.get("current_minimum_approvals") != 4:
        fail("Five-agent 75% quorum must require four approvals")
    if quorum.get("abstention_counts_as_approval") is not False:
        fail("Abstentions cannot count as approvals")
    if quorum.get("missing_vote_counts_as_approval") is not False:
        fail("Missing votes cannot count as approvals")
    if quorum.get("deny_or_block_vote_prevents_automatic_merge") is not True:
        fail("Deny/block must prevent automatic merge")
    if quorum.get("quorum_cannot_override_d3") is not True:
        fail("Agent quorum cannot override D3")

    rating = agent.get("risk_rating", {})
    if rating.get("minimum_automatic_merge_score") != 85:
        fail("Automatic merge score threshold must remain 85")
    weights = rating.get("dimensions", {})
    if round(sum(float(value) for value in weights.values()), 8) != 1.0:
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
    actual_gates = set(notify.get("collab_portal_fallback", {}).get("disable_only_when_all", []))
    if actual_gates != required_collab_gates:
        fail("Collab fallback disable gates drifted")

    if security.get("crypto_blockchain_guardrails", {}).get("production_token_or_currency_status") != "research_target_not_activated":
        fail("CHLOM crypto/token status must remain research_target_not_activated")
    if security.get("crypto_blockchain_guardrails", {}).get("phase_9_dependency") is not True:
        fail("Advanced blockchain/crypto activation must remain Phase 9-gated")
    if security.get("github_security_evidence", {}).get("github_blocking") != "not_relied_upon_as_sovereign_merge_authority":
        fail("GitHub security evidence must not become sovereign merge authority")

    if repo.get("agent_merge_policy") != "fail_closed_quorum_and_validation":
        fail("Repository state must register the agent fail-closed merge policy")
    if repo.get("github_merge_gate_enforced") is not False:
        fail("Current GitHub merge gate must remain explicitly false")
    if repo.get("github_branch_protection_required_for_phase_3") is not False:
        fail("GitHub branch protection must not remain a Phase 3 dependency")

    for fragment in (
        "python scripts/validate_agent_sovereign_governance.py",
        "python scripts/governed_merge_decision.py --self-test",
        "python scripts/resolve_pm_notification_recipients.py --self-test",
        "python scripts/security_self_heal_plan.py --self-test",
    ):
        require(DOCS_WORKFLOW, fragment)
    for fragment in (
        "name: Security Governance",
        "github/codeql-action/init@v4",
        "github/codeql-action/analyze@v4",
        "actions/dependency-review-action@v4",
        "python scripts/validate_security_governance.py",
    ):
        require(SECURITY_WORKFLOW, fragment)

    require(RELAY, "Agent S — Security & Resilience Sentinel")
    require(RELAY, "75% quorum")
    require(RELAY, "Collab Portal fallback tracking mailbox")
    require(PERMISSIONS, "## Agent-sovereign quorum and specialist gates")

    print("Agent-sovereign governance validation passed.")
    print("Eligible voters: 5; 75% quorum: 4 approvals; Agent D remains independent gatekeeper.")
    print("GitHub branch protection: non-sovereign defense-in-depth, not a Phase 3 dependency.")
    print("D3: reserved human/specialist authority; no agent quorum substitution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
