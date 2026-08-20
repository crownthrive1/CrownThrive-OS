#!/usr/bin/env python3
"""Fail-closed validation for Founder Strategy & Audit capability under one canonical master."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/founder-strategy-orchestrator.v1.json"
SCHEMA = ROOT / "developers/schemas/founder-audit-report.v1.schema.json"
DOC = ROOT / "automation/founder-strategy-orchestrator.mdx"
WORKFLOW = ROOT / ".github/workflows/founder-strategy-orchestrator-candidate.yml"

VOTERS = {
    "ct.relay.agent-a", "ct.relay.agent-b", "ct.relay.agent-c", "ct.relay.agent-d", "ct.relay.agent-s"
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_json(path: Path) -> dict:
    require(path.is_file(), f"Missing required file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def activation_allowed(votes: dict[str, str]) -> bool:
    if set(votes) != VOTERS:
        return False
    normalized = {agent: decision.upper() for agent, decision in votes.items()}
    if any(decision in {"DENY", "BLOCK"} for decision in normalized.values()):
        return False
    if normalized["ct.relay.agent-d"] != "APPROVE":
        return False
    return sum(decision == "APPROVE" for decision in normalized.values()) >= 4


def main() -> int:
    manifest = read_json(MANIFEST)
    schema = read_json(SCHEMA)
    doc = DOC.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    require(manifest["manifest_id"] == "ct.manifest.founder-strategy-orchestrator.v1", "manifest identity drift")
    require(manifest["manifest_version"] == "0.2.0", "reconciled manifest version drift")
    require(manifest["phase"] == "2.99" and manifest["phase_3_advancement"] is False, "packet cannot advance Phase 3")
    require(manifest["status"] == "PREPARED_NOT_ACTIVATED", "capability must remain prepared, not activated")

    recon = manifest["identity_reconciliation"]
    require(recon["legacy_candidate_agent_id"] == "ct.agent.founder-strategy-orchestrator", "legacy candidate id must remain preserved")
    require(recon["legacy_disposition"] == "preserved_predecessor_candidate_identity_not_active_master", "legacy disposition drift")
    require(recon["canonical_master_agent_id"] == "ct.agent.founder-orchestrator", "canonical master drift")
    require(recon["capability_id"] == "ct.capability.founder-strategy-audit", "strategy capability id drift")
    require(recon["silent_deletion"] is False and recon["history_preserved"] is True, "lineage preservation required")
    require(recon["second_master_prohibited"] is True, "second master must remain prohibited")

    master = manifest["master"]
    require(master["agent_id"] == "ct.agent.founder-orchestrator", "master agent reference drift")
    require(master["vote_eligible"] is False, "master remains non-voting")
    require(master["operational_parent"] == "ct.relay.agent-a", "operational parent drift")

    capability = manifest["capability"]
    require(capability["capability_id"] == "ct.capability.founder-strategy-audit", "capability identity drift")
    require(capability["kind"] == "subordinate_capability_family", "strategy packet must remain subordinate capability")
    require(capability["vote_eligible"] is False, "capability cannot vote")
    identity = capability["identity_boundary"]
    require(identity["impersonates_human"] is False, "human impersonation prohibited")
    require(identity["may_claim_founder_approval"] is False, "founder approval cannot be inferred")
    require(identity["signature_authority"] == "none", "signature authority must remain none")

    authority = manifest["authority"]
    for key in (
        "direct_main_write", "merge", "deploy_or_publish", "send_external_message",
        "create_or_change_privileged_access", "production_credentials", "legal_financial_rights_decisions",
        "money_movement", "destructive_or_irreversible_action", "d3_execution", "self_approval",
        "privilege_escalation", "missing_evidence_means_permission", "may_register_second_master_agent",
    ):
        require(authority[key] is False, f"authority prohibition drifted: {key}")
    require(authority["maximum_risk_class"] == "D2", "maximum risk class must remain D2")

    activation = manifest["activation"]
    require(activation["parent_master_must_be_governed_first"] is True, "master packet must be governed first")
    require(set(activation["eligible_parent_voters"]) == VOTERS, "voter pool drift")
    require(activation["approvals_required"] == 4 and activation["agent_d_approval_required"] is True, "quorum drift")
    require(activation["deny_or_block_fails_closed"] is True, "deny/block must fail closed")
    require(activation["founder_ratification_required_for_first_activation"] is True, "first activation needs founder ratification")
    require("PR-158" in activation["collision_reconciliation_required"], "parent packet dependency missing")

    orchestration = manifest["orchestration"]
    require(orchestration["canonical_parent_agent_id"] == "ct.agent.founder-orchestrator", "child parent binding drift")
    require(orchestration["capability_id"] == "ct.capability.founder-strategy-audit", "child capability binding drift")
    require(orchestration["max_concurrent_subagents"] == 3 and orchestration["max_spawn_depth"] == 1, "delegation bounds drift")
    children = orchestration["children"]
    require(len(children) == 7, "expected seven strategy/audit subagents")
    require(len({item["agent_id"] for item in children}) == 7, "subagent IDs must remain unique")

    runtime = manifest["runtime_profile"]
    require(runtime["preferred_model"] == "gpt-5.6-sol", "preferred model drift")
    require(runtime["work_mode_reasoning"] == "Ultra", "reasoning target drift")
    require(runtime["api_fallback"]["reasoning_effort"] == "max", "API reasoning effort drift")
    require(runtime["schedule_runtime_binding"] == "DECLARED_TARGET_UNVERIFIED", "runtime binding cannot be falsely certified")

    report = manifest["report_contract"]
    require(set(report["recipients"]) == VOTERS, "report recipients must remain A/B/C/D/S")
    require(report["provider_receipt_required_before_marking_delivered"] is True, "delivery requires provider receipt")

    require(schema.get("title") == "CrownThrive Founder Audit Report Manifest v1", "report schema identity drift")
    require(schema.get("additionalProperties") is False, "report schema must fail closed")

    for phrase in (
        "CANONICAL MASTER: `ct.agent.founder-orchestrator`",
        "CAPABILITY: `ct.capability.founder-strategy-audit`",
        "LEGACY CANDIDATE ID PRESERVED",
        "does not impersonate",
        "Agent D approval",
        "No additional automation slot is created",
        "Kill switch",
    ):
        require(phrase in doc, f"documentation missing reconciliation phrase: {phrase}")

    require("name: Founder Strategy Orchestrator Candidate" in workflow, "existing candidate workflow lineage must remain preserved")
    require("python scripts/validate_founder_strategy_orchestrator.py" in workflow, "validator workflow integration missing")

    votes = {agent: "APPROVE" for agent in VOTERS}
    require(activation_allowed(votes), "positive quorum fixture failed")
    votes["ct.relay.agent-s"] = "BLOCK"
    require(not activation_allowed(votes), "block fixture must fail closed")

    public_text = MANIFEST.read_text(encoding="utf-8") + doc
    require("jones.usmc.kj" not in public_text.lower(), "private address must not enter public repository")

    print("PASS: Founder Strategy candidate reconciled to Strategy & Audit capability")
    print("PASS: canonical master is ct.agent.founder-orchestrator; legacy candidate ID preserved as lineage")
    print("PASS: no second master, no additional vote, no founder impersonation, D3 remains reserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
