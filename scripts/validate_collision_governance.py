#!/usr/bin/env python3
"""Validate CrownThrive collision-governance and Founder Orchestrator boundaries."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers" / "manifests" / "collision-governance-founder-orchestration.v1.json"
DOC = ROOT / "automation" / "collision-avoidance-founder-orchestration.mdx"
WORKFLOW = ROOT / ".github" / "workflows" / "collision-governance.yml"
CHANGELOG = ROOT / "changelog" / "phase-2-99-collision-governance-founder-orchestration.mdx"

sys.path.insert(0, str(ROOT / "scripts"))
import governed_collision_control as gcc  # noqa: E402

EXPECTED_VOTERS = {
    "ct.relay.agent-a",
    "ct.relay.agent-b",
    "ct.relay.agent-c",
    "ct.relay.agent-d",
    "ct.relay.agent-s",
}
EXPECTED_AGENT_IDS = {
    "ct.subagent.collision.preflight-sentinel",
    "ct.subagent.collision.adjudicator",
    "ct.subagent.collision.postmerge-reconciler",
    "ct.subagent.queue.priority-throttle",
    "ct.subagent.quorum.session-router",
}
FORBIDDEN_PRIVILEGE_FRAGMENTS = (
    "cast_sovereign_vote",
    "waive_agent_d",
    "waive_specialist",
    "merge_blocked",
    "override_d3",
    "self_approve",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(MANIFEST.exists(), f"missing {MANIFEST.relative_to(ROOT)}")
    require(DOC.exists(), f"missing {DOC.relative_to(ROOT)}")
    require(WORKFLOW.exists(), f"missing {WORKFLOW.relative_to(ROOT)}")
    require(CHANGELOG.exists(), f"missing {CHANGELOG.relative_to(ROOT)}")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(data["manifest_id"] == "ct.manifest.collision-governance-founder-orchestration.v1", "manifest id drift")
    require(data["phase"] == "2.99", "phase must remain 2.99")
    require(data["state"] == "controlled_test_pending_governed_acceptance", "packet must remain controlled-test before adoption")
    require(data["founder_reconciliation_issue"] == 157, "founder reconciliation issue binding drift")

    boundary = data["authority_boundary"]
    require(set(boundary["sovereign_voters"]) == EXPECTED_VOTERS, "collision control may not change sovereign voter pool")
    require(boundary["ordinary_automatic_promotion"] == "4_of_5_including_agent_d_no_deny_or_block", "quorum contract drift")
    require(boundary["special_quorum_changes_vote_math"] is False, "special quorum cannot change vote math")
    require(boundary["special_quorum_can_waive_specialists"] is False, "special quorum cannot waive specialists")
    require(boundary["special_quorum_can_override_d3"] is False, "special quorum cannot override D3")
    require(boundary["originating_agent_self_vote_allowed"] is False, "originating agent self-vote must remain prohibited")
    require(boundary["d3_remains_human_reserved"] is True, "D3 human boundary drift")

    parent = data["candidate_parent_binding"]
    require(parent["agent_id"] == "ct.agent.founder-orchestrator", "candidate Founder Orchestrator id drift")
    require(parent["binding_state"] == "pending_identity_and_runtime_reconciliation", "Founder Orchestrator must reconcile identity/runtime before activation")
    require(parent["vote_eligible"] is False, "Founder Orchestrator queue privileges may not create a sixth vote")
    privileges = "\n".join(parent["bounded_privileges"]).lower()
    for fragment in FORBIDDEN_PRIVILEGE_FRAGMENTS:
        require(fragment not in privileges, f"forbidden privilege leaked into bounded privileges: {fragment}")
    forbidden = "\n".join(parent["forbidden"]).lower()
    for fragment in FORBIDDEN_PRIVILEGE_FRAGMENTS:
        require(fragment in forbidden or fragment == "waive_specialist", f"forbidden authority list missing guard: {fragment}")
    require("waive_applicable_specialist" in forbidden, "specialist non-waiver guard missing")

    agents = data["agents"]
    agent_ids = {item["agent_id"] for item in agents}
    require(agent_ids == EXPECTED_AGENT_IDS, "collision subagent set drift")
    require(all(item["vote_eligible"] is False for item in agents), "collision subagents must remain non-voting")

    classes = data["collision_classes"]
    require([item["id"] for item in classes] == [f"CT-COLL-{n}" for n in range(6)], "collision class sequence must remain 0..5")
    require(classes[-1]["default_disposition"] == "founder_or_authorized_human_adjudication", "constitutional/D3 collision must escalate")

    preflight = data["preflight_contract"]
    require(preflight["required_before_material_branch_or_pr"] is True, "material preflight must remain required")
    require(preflight["unknown_collision_evidence"] == "hold_or_escalate_not_clear", "unknown collision evidence must fail closed")
    require(preflight["force_push_as_collision_resolution"] is False, "force-push collision resolution prohibited")

    postmerge = data["postmerge_contract"]
    require(postmerge["required_after_material_main_merge"] is True, "post-merge reconciliation must remain required")
    require("invalidate_stale_exact_head_or_base_bound_review_evidence" in postmerge["steps"], "stale review invalidation missing")

    throttle = data["throttle_policy"]
    require(throttle["max_concurrent_final_quorum_d2"] == 2, "D2 final-quorum WIP limit drift")
    require(throttle["max_concurrent_same_collision_domain"] == 1, "same-domain serialization must remain one-at-a-time")
    require(throttle["max_concurrent_d3"] == 1, "D3 must remain serialized")
    require(throttle["temporary_d2_quorum_window_increase"]["does_not_change_vote_threshold"] is True, "temporary queue widening cannot change quorum threshold")

    sq = data["special_quorum"]
    require(sq["vote_pool_changes"] is False, "special quorum cannot alter voter pool")
    require(sq["threshold_changes"] is False, "special quorum cannot alter threshold")
    require(sq["agent_d_remains_mandatory"] is True, "Agent D must remain mandatory")
    require(sq["specialists_remain_mandatory"] is True, "specialists must remain mandatory")
    require(sq["head_or_base_change_expires_session"] is True, "special quorum must be exact-head/base bound")

    experiment = data["experimental_secondary_institutional_model"]
    require(experiment["state"] == "secondary_experimental_not_governing_authority", "separation-of-powers analogue must remain secondary/experimental")
    require(len(experiment["lanes"]) == 3, "experimental institutional model must contain three CrownThrive lanes")

    schedule = data["schedule_contract"]
    existing = set(schedule["known_existing_minute_slots_to_avoid"])
    chosen = schedule["chosen_slots"]
    require(chosen == [40, 50], "collision schedule slots drift")
    require(not (existing & set(chosen)), "collision schedules overlap known existing hourly lanes")
    require(schedule["hourly_queue_review_cron"] == "40 * * * *", "queue cron drift")
    require(schedule["hourly_postmerge_reconciliation_cron"] == "50 * * * *", "postmerge cron drift")

    integration = data["integration_state"]
    require(integration["governed_merge_gate_integration"] == "pending_shared_surface_reconciliation", "shared merge-gate file must not be overwritten before reconciliation")
    require(integration["supabase_runtime_binding"] == "not_mutated_by_this_public_packet", "public packet must not fabricate live Supabase agent binding")
    require(integration["phase_3_advancement"] is False, "packet may not advance Phase 3")

    tests = gcc.self_test()
    require(tests["status"] == "PASS", "collision controller self-test failed")

    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    require("40 * * * *" in workflow_text and "50 * * * *" in workflow_text, "workflow schedule mismatch")
    require("pull_request:" in workflow_text, "preflight PR trigger missing")
    require("push:" in workflow_text and "main" in workflow_text, "post-merge main trigger missing")
    require("contents: read" in workflow_text and "pull-requests: read" in workflow_text, "workflow must remain read-only")
    require("contents: write" not in workflow_text and "pull-requests: write" not in workflow_text, "workflow may not gain write authority")

    doc_text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "Collision Preflight Sentinel",
        "Post-Merge Reconciler",
        "Special Quorum",
        "Executive Coordination",
        "Policy Assembly",
        "Adjudication and Precedent",
        "Issue #157",
    ):
        require(phrase in doc_text, f"documentation missing required concept: {phrase}")

    print("PASS: collision governance / founder orchestration controls validated")
    print(f"PASS: {len(agents)} non-voting collision/queue subagents")
    print("PASS: special quorum preserves A/B/C/D/S 4-of-5 + Agent D and D3 human boundary")
    print("PASS: queue throttle 2 D2 / 1 same-domain / 1 D3")
    print("PASS: scheduled lanes :40 and :50 avoid current known relay minutes")
    print(f"PASS: controller deterministic self-tests={tests['tests']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
