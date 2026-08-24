#!/usr/bin/env python3
"""Validate Agent F's bounded post-PR-91 Help Center reconciliation packet."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "developers" / "manifests" / "help-center-795-post-merge-reconciliation.v1.json"
BUNDLE = ROOT / "data" / "help_center_article_manifest.v1.bundle.json"
MATERIALIZATION = ROOT / "developers" / "manifests" / "help-center-795-materialization-reconciliation.v1.json"
HARD_EXIT = ROOT / "developers" / "manifests" / "phase-2-99-hard-exit-ledger.v1.json"

EXPECTED_MAIN = "8fcb68bf209e32ba2cd265e1b6ca730cb8da64d7"
EXPECTED_SOURCE_SHA = "c7f16bd8b504431e71a4407728e22ab9a950ab9dcd891d831bd78f6802335b0f"


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> None:
    packet = load(PACKET)
    bundle = load(BUNDLE)
    materialization = load(MATERIALIZATION)
    hard_exit = load(HARD_EXIT)

    require(packet["authority"]["roadmap_decision_id"] == "CT-ADR-ROADMAP-010", "roadmap authority drift")
    require(packet["authority"]["roadmap_generation"] == "ten_phase_v1", "roadmap generation drift")
    require(packet["authority"]["current_phase"] == 2 and packet["authority"]["current_subphase"] == "2.99", "phase drift")
    require(packet["authority"]["phase_3_entry"] == "blocked_pending_phase_2_99_hard_exit", "premature Phase 3 promotion")
    require(packet["canonical_main"]["sha"] == EXPECTED_MAIN, "post-merge canonical main SHA drift")

    require(bundle["source"]["inventory_count"] == 795, "bundle source inventory must remain 795")
    require(bundle["source"]["source_sha256"] == EXPECTED_SOURCE_SHA, "S11 source hash drift")
    require(bundle["stable_identity"]["first_article_id"] == "ct.article.recovered.0001", "first stable article id drift")
    require(bundle["stable_identity"]["last_article_id"] == "ct.article.recovered.0795", "last stable article id drift")

    require(materialization["changed_records"]["record_count"] == 795, "materialization record count drift")
    require(materialization["closure_delta_if_merged"]["complete_machine_manifest_generated_in_repo"] is True, "PR91 permitted closure delta missing")
    require(materialization["closure_delta_if_merged"]["gate_002_pass"] is False, "PR91 must not close GATE-002")

    post = packet["post_merge_reconciliation"]
    require(post["complete_machine_manifest_generated_in_repo"] is True, "post-merge canonical materialization not recorded")
    require(post["hard_exit_ledger_current_main_value"] is False, "packet must preserve observed stale ledger value")
    require(post["hard_exit_ledger_reconciliation_required"] is True, "ledger reconciliation dependency must remain explicit")
    require(post["hard_exit_ledger_owner_collision"]["active_pr"] == 122, "active ledger owner drift")
    require(post["hard_exit_ledger_owner_collision"]["agent_f_action"] == "handoff_only_no_competing_ledger_edit", "Agent F must not collide with PR122 ledger ownership")

    tags = packet["reconciliation_tag_scan"]
    require(tags["policy"]["deferral_is_never_pass"] is True, "deferral semantics weakened")
    require(tags["policy"]["unknown_is_never_zero_or_pass"] is True, "UNKNOWN semantics weakened")
    require(tags["phase_gate_tags"]["CT-P299-GATE-002"]["state"] == "OPEN", "GATE-002 tag unexpectedly promoted")
    require(tags["phase_gate_tags"]["CT-P299-GATE-003"]["state"] == "OPEN", "GATE-003 tag unexpectedly promoted")
    gate2_policies = tags["governed_gate_002_policies"]
    require(gate2_policies["source_not_recovered_terminal_policy"]["state"] == "PASS", "source-not-recovered policy missing")
    require(gate2_policies["p0_p1_current_rebuild_policy"]["state"] == "PASS", "P0/P1 current rebuild policy missing")
    require(gate2_policies["p0_p1_current_rebuild_policy"]["autopublish_without_required_approval"] is False, "P0/P1 reconstruction cannot bypass approval")
    require(gate2_policies["governed_reconstruction_quorum"]["independent_quorum_required_for_material_acceptance"] is True, "material reconstruction quorum weakened")
    require(gate2_policies["full_documentation_hard_gate"]["non_deferrable"] is True, "full documentation hard gate cannot become deferrable")
    require(gate2_policies["full_documentation_hard_gate"]["phase3_entry_blocked_until_complete"] is True, "documentation gate cannot permit premature Phase 3")

    closure = packet["closure_state"]
    require(all(closure[key] is False for key in (
        "terminal_disposition_assigned_795",
        "section_and_category_mapping_795",
        "exposure_classified_795",
        "risk_classified_795",
        "owner_or_owner_queue_795",
        "canonical_route_or_explicit_nonpublic_state_795",
        "source_mapping_795",
        "navigation_or_intentionally_unlisted_795",
        "p0_p1_substantive_or_explicit_unresolved_closure",
        "s94_body_recovery_complete",
        "source_not_recovered_applied_to_all_eligible_records",
    )), "unresolved articleization state was falsely promoted")
    require(closure["body_records_recovered_this_pass"] == 0, "body recovery count must remain zero without source evidence")
    require(closure["source_not_recovered_policy_available"] is True, "governed source-not-recovered disposition path must be represented")
    require(packet["gate_scope"]["gate_002_pass"] is False, "GATE-002 must remain not passed")

    retired = packet["retired_provider_state"]["simplebase"]
    require(retired["state"] == "retired_historical_only", "SimpleBase must remain historical-only")
    require(retired["active_dependency"] is False and retired["restoration_target"] is False, "SimpleBase cannot be restored as an active dependency")
    require(retired["current_support_stack"] == ["GitHub", "Mintlify"], "current support stack drift")

    require(hard_exit["articleization"]["complete_machine_manifest_generated_in_repo"] is False, "main hard-exit ledger already reconciled; retire this handoff or update packet semantics")
    require(hard_exit["open_hard_gates"][1]["gate_id"] == "CT-P299-GATE-002", "GATE-002 position/identity drift")
    require(hard_exit["open_hard_gates"][1]["state"] == "not_met", "GATE-002 unexpectedly changed state")

    print("PASS: Agent F post-PR91 merge reconciliation packet is internally consistent, tag-aware and fail-closed.")


if __name__ == "__main__":
    main()
