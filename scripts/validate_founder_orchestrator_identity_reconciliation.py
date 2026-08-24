#!/usr/bin/env python3
"""Validate one canonical Founder Orchestrator identity with preserved predecessor lineage."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "developers/manifests/founder-orchestrator-master.v1.json"
COLLISION = ROOT / "developers/manifests/collision-governance-founder-orchestration.v1.json"
CONVERGENCE = ROOT / "developers/manifests/convergence-refactor-policy.v1.json"

VOTERS = {
    "ct.relay.agent-a",
    "ct.relay.agent-b",
    "ct.relay.agent-c",
    "ct.relay.agent-d",
    "ct.relay.agent-s",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: Path) -> dict:
    require(path.is_file(), f"missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    master = load(MASTER)
    collision = load(COLLISION)
    convergence = load(CONVERGENCE)

    require(master["manifest_id"] == "ct.manifest.founder-orchestrator-master.v1", "master manifest id drift")
    require(master["canonical_agent_id"] == "ct.agent.founder-orchestrator", "canonical master id drift")
    require(master["vote_eligible"] is False, "master orchestrator must remain non-voting")
    require(master["operational_parent"] == "ct.relay.agent-a", "operational parent drift")
    require(master["phase"] == "2.99" and master["phase_3_advancement"] is False, "identity reconciliation cannot advance Phase 3")

    recon = master["identity_reconciliation"]
    require(recon["legacy_candidate_ids"] == ["ct.agent.founder-strategy-orchestrator"], "legacy candidate lineage drift")
    require(recon["legacy_disposition"] == "preserved_predecessor_candidate_identity_not_active_master", "legacy disposition drift")
    require(recon["silent_deletion"] is False and recon["predecessor_history_preserved"] is True, "predecessor history must be preserved")

    families = {item["capability_id"]: item for item in master["capability_families"]}
    require(set(families) == {"ct.capability.founder-strategy-audit", "ct.capability.founder-queue-convergence"}, "capability family set drift")
    require(families["ct.capability.founder-strategy-audit"]["legacy_candidate_agent_id"] == "ct.agent.founder-strategy-orchestrator", "strategy lineage missing")
    require(all(item["vote_eligible"] is False for item in families.values()), "capability families may not vote")

    authority = master["authority"]
    for key in (
        "sovereign_vote", "may_create_sovereign_vote", "may_impersonate_founder", "may_claim_founder_approval",
        "signature_authority", "merge_authority", "direct_main_write", "provider_write_default",
        "production_credential_authority", "money_movement", "legal_rights_financial_decision_authority",
        "d3_execution", "self_approval", "unknown_to_pass", "history_deletion", "force_push",
    ):
        require(authority[key] is False, f"forbidden master authority enabled: {key}")

    constitutional = master["constitutional_boundary"]
    require(set(constitutional["sovereign_voters"]) == VOTERS, "sovereign voter pool drift")
    require(constitutional["automatic_promotion"] == "4_of_5_including_agent_d_no_deny_or_block", "promotion rule drift")
    require(constitutional["agent_d_mandatory"] is True, "Agent D must remain mandatory")
    require(constitutional["d3_human_reserved"] is True, "D3 must remain human-reserved")
    require(constitutional["master_orchestrator_adds_vote"] is False, "master orchestrator cannot add a vote")
    require(constitutional["capability_children_add_votes"] is False, "children cannot add votes")

    parent = collision["candidate_parent_binding"]
    require(parent["agent_id"] == master["canonical_agent_id"], "collision governor parent must bind to canonical master")
    require("ct.agent.founder-orchestrator" in convergence["reuse_existing_roles"], "convergence policy must reuse canonical master")
    require("ct.agent.founder-strategy-orchestrator" not in convergence["reuse_existing_roles"], "legacy candidate may not remain a parallel master role")

    print("PASS: one canonical Founder Orchestrator master identity")
    print("PASS: former Founder Strategy Orchestrator preserved as predecessor lineage")
    print("PASS: Strategy/Audit and Queue/Convergence are non-voting capability families")
    print("PASS: A/B/C/D/S constitutional voter pool unchanged; D3 remains human-reserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
