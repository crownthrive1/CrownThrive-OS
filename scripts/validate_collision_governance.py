#!/usr/bin/env python3
"""Validate CrownThrive collision, convergence, refactor and Founder Orchestrator boundaries."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers" / "manifests" / "collision-governance-founder-orchestration.v1.json"
CONVERGENCE = ROOT / "developers" / "manifests" / "convergence-refactor-policy.v1.json"
DOC = ROOT / "automation" / "collision-avoidance-founder-orchestration.mdx"
WORKFLOW = ROOT / ".github" / "workflows" / "collision-governance.yml"
CHANGELOG = ROOT / "changelog" / "phase-2-99-collision-governance-founder-orchestration.mdx"
REFRACTOR = ROOT / "scripts" / "governed_convergence_refactor.py"

sys.path.insert(0, str(ROOT / "scripts"))
import governed_collision_control as gcc  # noqa: E402
import governed_convergence_refactor as gcr  # noqa: E402

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
EXPECTED_EXTENSION_AGENT_IDS = {
    "ct.subagent.convergence.rotor",
    "ct.subagent.refactor.steward",
}
FORBIDDEN_BOUNDED_PRIVILEGE_FRAGMENTS = (
    "cast_sovereign_vote",
    "waive_agent_d",
    "waive_specialist",
    "merge_blocked",
    "override_d3",
    "self_approve",
)
REQUIRED_FORBIDDEN_GUARDS = (
    "cast_sovereign_vote_by_orchestration_action",
    "waive_agent_d",
    "waive_applicable_specialist",
    "merge_blocked_pr",
    "change_d3_authority_without_explicit_human_authorization",
    "self_approve_originating_material_change",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    for path in (MANIFEST, CONVERGENCE, DOC, WORKFLOW, CHANGELOG, REFRACTOR):
        require(path.exists(), f"missing {path.relative_to(ROOT)}")

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
    for fragment in FORBIDDEN_BOUNDED_PRIVILEGE_FRAGMENTS:
        require(fragment not in privileges, f"forbidden privilege leaked into bounded privileges: {fragment}")
    forbidden = "\n".join(parent["forbidden"]).lower()
    for guard in REQUIRED_FORBIDDEN_GUARDS:
        require(guard in forbidden, f"forbidden authority list missing guard: {guard}")

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

    convergence = json.loads(CONVERGENCE.read_text(encoding="utf-8"))
    require(convergence["manifest_id"] == "ct.manifest.convergence-refactor-policy.v1", "convergence manifest id drift")
    require(convergence["phase"] == "2.99", "convergence policy must remain Phase 2.99")
    require(convergence["parent_packet"] == data["manifest_id"], "convergence policy must extend existing collision governor")
    extension_ids = {item["agent_id"] for item in convergence["extension_agents"]}
    require(extension_ids == EXPECTED_EXTENSION_AGENT_IDS, "convergence/refactor extension-agent set drift")
    require(all(item["vote_eligible"] is False for item in convergence["extension_agents"]), "convergence/refactor agents must remain non-voting")

    authority = convergence["authority"]
    for key in (
        "sovereign_voter_pool_changes",
        "provider_write_authority",
        "merge_authority",
        "branch_delete_authority",
        "file_delete_authority",
        "force_push_authority",
        "silent_pr_close_authority",
        "unknown_to_pass_authority",
    ):
        require(authority[key] is False, f"forbidden convergence authority enabled: {key}")
    require(authority["d3_remains_human_reserved"] is True, "convergence policy cannot alter D3")

    preservation = convergence["knowledge_preservation"]
    for key in (
        "never_silently_destroy_knowledge",
        "never_silently_overwrite_history",
        "no_automation_branch_deletion",
        "no_automation_file_deletion",
        "no_force_push",
        "no_silent_pr_closure",
        "supersession_requires_successor_or_reason",
        "supersession_requires_predecessor_reference",
        "material_current_page_change_requires_version_or_changelog",
        "historical_claims_remain_preserved_even_when_no_longer_current",
    ):
        require(preservation[key] is True, f"knowledge-preservation invariant disabled: {key}")

    modes = convergence["attention_modes"]
    require(set(modes) == {"EXPANSION", "BALANCED", "CONVERGENCE", "INCIDENT"}, "attention mode set drift")
    for mode, budget in modes.items():
        require(sum(int(v) for v in budget.values()) == 100, f"attention budget must equal 100 for {mode}")
    require(modes["CONVERGENCE"]["closure_percent"] >= 70, "convergence mode must devote at least 70% attention to closure")

    whole = convergence["whole_system_refactor_rule"]
    require(whole["prefer_update_existing_owner_over_create_parallel_owner"] is True, "must prefer existing owner update")
    require(whole["prefer_extract_unique_delta_over_wholesale_stale_pr_promotion"] is True, "must extract unique stale deltas")
    require(whole["registry_growth_alone_is_not_certification_debt"] is True, "registry growth must not become proof debt by count alone")

    tests = gcc.self_test()
    require(tests["status"] == "PASS", "collision controller self-test failed")

    fake = {
        "open_pr_count": 24,
        "collisions": [{"severity": 2}] * 9,
        "throttle": {
            "main_sha": "abc",
            "ranked": [
                {"number": 1, "title": "Phase 2.99 hard-exit reconciliation", "draft": True, "stale_base": True, "collision_severity": 2, "priority": {"score": 80, "band": "P1"}},
                {"number": 2, "title": "Future framework experiment", "draft": True, "stale_base": False, "collision_severity": 0, "priority": {"score": 20, "band": "P4"}},
            ],
        },
    }
    plan = gcr.build_plan(fake)
    require(plan["pressure"]["mode"] == "CONVERGENCE", "convergence rotor threshold test failed")
    require(all(item["automatic_delete"] is False for item in plan["all_open_pr_dispositions"]), "refactor plan may not auto-delete")
    require(all(item["force_push"] is False for item in plan["all_open_pr_dispositions"]), "refactor plan may not force-push")
    require(any(item["disposition"] == "continue_research_without_promotion" for item in plan["all_open_pr_dispositions"]), "attention rotation must preserve throttled research")

    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    require("40 * * * *" in workflow_text and "50 * * * *" in workflow_text, "workflow schedule mismatch")
    require("pull_request:" in workflow_text, "preflight PR trigger missing")
    require("push:" in workflow_text and "main" in workflow_text, "post-merge main trigger missing")
    require("contents: read" in workflow_text and "pull-requests: read" in workflow_text, "workflow must remain read-only")
    require("contents: write" not in workflow_text and "pull-requests: write" not in workflow_text, "workflow may not gain write authority")
    require("governed_convergence_refactor.py --self-test" in workflow_text, "convergence self-test missing")
    require("Rotate attention and emit whole-estate refactor plan" in workflow_text, "attention-rotation workflow step missing")
    require("Post-merge convergence/refactor refresh" in workflow_text, "post-merge refactor refresh missing")

    doc_text = DOC.read_text(encoding="utf-8")
    for phrase in (
        "Collision Preflight Sentinel",
        "Post-Merge Reconciler",
        "Special Quorum",
        "Executive Coordination",
        "Policy Assembly",
        "Adjudication and Precedent",
        "Issue #157",
        "Convergence Rotor",
        "Refactor Steward",
        "never silently deletes",
    ):
        require(phrase in doc_text, f"documentation missing required concept: {phrase}")

    print("PASS: collision/convergence/refactor founder-orchestration controls validated")
    print(f"PASS: {len(agents)} base non-voting collision/queue subagents + {len(extension_ids)} non-voting convergence/refactor extensions")
    print("PASS: special quorum preserves A/B/C/D/S 4-of-5 + Agent D and D3 human boundary")
    print("PASS: convergence mode rotates >=70% attention to closure without deleting work")
    print("PASS: no branch/file deletion, force push, silent PR closure, or UNKNOWN->PASS authority")
    print("PASS: scheduled lanes :40 and :50 reused; no new workflow family created")
    print(f"PASS: collision controller deterministic self-tests={tests['tests']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
