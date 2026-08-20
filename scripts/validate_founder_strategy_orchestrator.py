#!/usr/bin/env python3
"""Fail-closed validation for the non-canonical Founder Strategy Orchestrator candidate."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/founder-strategy-orchestrator.v1.json"
SCHEMA = ROOT / "developers/schemas/founder-audit-report.v1.schema.json"
DOC = ROOT / "automation/founder-strategy-orchestrator.mdx"
WORKFLOW = ROOT / ".github/workflows/founder-strategy-orchestrator-candidate.yml"

VOTERS = {
    "ct.relay.agent-a",
    "ct.relay.agent-b",
    "ct.relay.agent-c",
    "ct.relay.agent-d",
    "ct.relay.agent-s",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read_json(path: Path) -> dict:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def activation_allowed(votes: dict[str, str]) -> bool:
    """Model the immutable fail-closed parent vote rule for self-tests."""
    if set(votes) != VOTERS:
        return False
    normalized = {agent: decision.upper() for agent, decision in votes.items()}
    if any(decision in {"DENY", "BLOCK"} for decision in normalized.values()):
        return False
    if normalized["ct.relay.agent-d"] != "APPROVE":
        return False
    return sum(decision == "APPROVE" for decision in normalized.values()) >= 4


def self_test_votes() -> None:
    approve = {agent: "APPROVE" for agent in VOTERS}
    require(activation_allowed(approve), "five approvals should satisfy the parent vote model")

    four = dict(approve)
    four["ct.relay.agent-c"] = "ABSTAIN"
    require(activation_allowed(four), "four approvals including Agent D should satisfy the parent vote model")

    missing = dict(approve)
    missing.pop("ct.relay.agent-b")
    require(not activation_allowed(missing), "missing vote must fail closed")

    d_abstains = dict(approve)
    d_abstains["ct.relay.agent-d"] = "ABSTAIN"
    require(not activation_allowed(d_abstains), "Agent D approval is mandatory")

    deny = dict(approve)
    deny["ct.relay.agent-s"] = "DENY"
    require(not activation_allowed(deny), "any deny must fail closed")


def main() -> int:
    manifest = read_json(MANIFEST)
    schema = read_json(SCHEMA)
    doc = DOC.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    require(manifest.get("manifest_id") == "ct.manifest.founder-strategy-orchestrator.v1", "manifest identity drifted")
    require(manifest.get("phase") == "2.99", "candidate must not imply Phase 3")
    require(manifest.get("canonicality") == "non_canonical_until_governed_merge_and_activation_receipt", "canonicality must remain non-canonical")
    require(manifest.get("status") == "PREPARED_NOT_ACTIVATED", "candidate must remain prepared, not activated")

    agent = manifest.get("agent", {})
    require(agent.get("agent_id") == "ct.agent.founder-strategy-orchestrator", "stable agent ID drifted")
    require(agent.get("vote_eligible") is False, "Founder Strategy Orchestrator must be non-voting")
    identity = agent.get("identity_boundary", {})
    require(identity.get("impersonates_human") is False, "human impersonation must remain prohibited")
    require(identity.get("may_claim_founder_approval") is False, "founder approval cannot be inferred")
    require(identity.get("signature_authority") == "none", "signature authority must remain none")
    require(identity.get("first_person_founder_statements") is False, "first-person founder statements must remain prohibited")

    runtime = manifest.get("runtime_profile", {})
    require(runtime.get("preferred_model") == "gpt-5.6-sol", "preferred model must be gpt-5.6-sol")
    require(runtime.get("work_mode_reasoning") == "Ultra", "Work-mode reasoning target must be Ultra")
    fallback = runtime.get("api_fallback", {})
    require(fallback.get("reasoning_effort") == "max", "API fallback must use max, not an invented ultra API effort")
    require(fallback.get("reasoning_effort") != "ultra", "ultra is not an API reasoning_effort value")
    require(fallback.get("max_concurrent_subagents") == 3, "API fallback concurrency must remain three")
    require(runtime.get("schedule_runtime_binding") == "DECLARED_TARGET_UNVERIFIED", "runtime binding cannot be falsely certified")

    authority = manifest.get("authority", {})
    for key in (
        "direct_main_write",
        "merge",
        "deploy_or_publish",
        "send_external_message",
        "create_or_change_privileged_access",
        "production_credentials",
        "legal_financial_rights_decisions",
        "money_movement",
        "destructive_or_irreversible_action",
        "d3_execution",
        "self_approval",
        "privilege_escalation",
        "missing_evidence_means_permission",
    ):
        require(authority.get(key) is False, f"authority prohibition drifted: {key}")
    require(authority.get("maximum_risk_class") == "D2", "maximum risk class must remain D2")

    activation = manifest.get("activation", {})
    require(activation.get("activation_state") == "PREPARED_NOT_ACTIVATED", "activation state drifted")
    require(set(activation.get("eligible_parent_voters", [])) == VOTERS, "eligible parent voter pool drifted")
    require(activation.get("approvals_required") == 4, "activation must require four approvals")
    require(activation.get("agent_d_approval_required") is True, "Agent D approval must remain mandatory")
    require(activation.get("deny_or_block_fails_closed") is True, "deny/block must fail closed")
    require(activation.get("missing_or_abstention_not_approval") is True, "missing/abstention cannot count")
    require(activation.get("descendant_votes_count") is False, "descendant votes cannot count")
    require(activation.get("self_vote_count") is False, "self vote cannot count")
    require(activation.get("risk_score_minimum") == 85, "risk score threshold must remain 85")
    require(activation.get("founder_ratification_required_for_first_activation") is True, "first activation needs founder ratification")
    require(activation.get("supervised_dry_runs_required", 0) >= 3, "three supervised dry runs are required")
    require(set(activation.get("collision_reconciliation_required", [])) == {"PR-101", "PR-102", "PR-125", "PR-145"}, "known topology collisions must remain explicit")
    require(activation.get("live_vote_receipt_ingestion_required") is True, "live vote receipt ingestion cannot be waived")

    orchestration = manifest.get("orchestration", {})
    require(orchestration.get("max_concurrent_subagents") == 3, "subagent concurrency must remain three")
    require(orchestration.get("max_spawn_depth") == 1, "spawn depth must remain one")
    require(orchestration.get("task_envelope_required") is True, "task envelope is mandatory")
    require(orchestration.get("sole_draft_writer") == "ct.subagent.founder-report-compiler", "sole draft writer drifted")
    children = orchestration.get("children", [])
    require(len(children) == 7, "expected seven bounded subagent roles")
    require(len({item.get("agent_id") for item in children}) == len(children), "subagent IDs must be unique")
    require(all("merge" not in str(item.get("authority", "")).lower() for item in children), "no subagent may have merge authority")

    schedule = manifest.get("schedule_contract", {})
    require(schedule.get("reuses_existing_task") is True, "candidate must reuse an existing dispatcher")
    require(schedule.get("creates_new_task") is False, "candidate must not consume a new task slot")
    require(schedule.get("candidate_mode") == "evaluate_and_report_only_no_delegation_or_mutation", "candidate schedule must remain report-only")
    require("YYYY-MM-DD" in schedule.get("once_per_local_day_lock", ""), "daily idempotency lock is required")

    report = manifest.get("report_contract", {})
    require(set(report.get("recipients", [])) == VOTERS, "report routing must cover exactly A/B/C/D/S")
    require(report.get("provider_receipt_required_before_marking_delivered") is True, "delivery needs provider receipt")
    require(set(report.get("response_states", [])) == {"ACCEPTED", "DISPUTED", "DEFERRED", "OUT_OF_SCOPE"}, "agent response states drifted")

    required_claim_fields = {
        "source_id", "authority_tier", "claim_kind", "confidence",
        "implementation_status", "classification", "snapshot_at",
    }
    require(set(manifest.get("evidence_contract", {}).get("required_claim_fields", [])) == required_claim_fields, "claim traceability fields drifted")

    require(schema.get("title") == "CrownThrive Founder Audit Report Manifest v1", "report schema identity drifted")
    require(schema.get("additionalProperties") is False, "report schema must fail closed on unknown root fields")
    require({"findings", "assignments", "verification", "delivery"}.issubset(set(schema.get("required", []))), "report schema is incomplete")

    for fragment in (
        "NON-CANONICAL CONTROLLED CANDIDATE",
        "PREPARED, NOT ACTIVATED",
        "does not impersonate",
        "Four approvals",
        "Agent D approval",
        "No additional automation slot is created",
        "ct.relay.agent-a",
        "ct.relay.agent-b",
        "ct.relay.agent-c",
        "ct.relay.agent-d",
        "ct.relay.agent-s",
        "DOC_CREATED",
        "EMAIL_SENT",
        "Current limitations",
        "Kill switch",
    ):
        require(fragment in doc, f"required documentation fragment missing: {fragment}")

    for fragment in (
        "name: Founder Strategy Orchestrator Candidate",
        "python -m py_compile scripts/validate_founder_strategy_orchestrator.py",
        "python scripts/validate_founder_strategy_orchestrator.py",
        "python scripts/validate_docs.py",
    ):
        require(fragment in workflow, f"workflow integration missing: {fragment}")

    public_text = MANIFEST.read_text(encoding="utf-8") + doc
    require("jones.usmc.kj" not in public_text.lower(), "private delivery address must not enter public repository")
    require("I am Kavonte" not in public_text, "impersonation phrase detected")
    require("Kavonte approved" not in public_text, "fabricated founder approval phrase detected")

    self_test_votes()

    print("Founder Strategy Orchestrator candidate validation passed.")
    print("State: PREPARED_NOT_ACTIVATED; non-canonical; non-voting; fail-closed.")
    print("Activation: 4-of-5 A/B/C/D/S, Agent D mandatory, no deny/block, founder ratification for first activation.")
    print("Authority: read-first; draft-branch ceiling; no main write, merge, deploy, external send, credentials, D3, or self-approval.")
    print("Scheduling: existing Agent A dispatcher only; once-per-day idempotency lock; candidate mode is report-only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
