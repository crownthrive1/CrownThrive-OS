#!/usr/bin/env python3
"""Fail-closed static validator for the public collision v2 packet."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/collision-governance-rtc.v2.json"
CANDIDATE_WORKFLOW = ROOT / ".github/workflows/collision-governance-v2.yml"
TRUSTED_WORKFLOW = ROOT / ".github/workflows/collision-governance-trusted-v2.yml"
CORE = ROOT / "scripts/collision_rtc_v2.py"
ADAPTER = ROOT / "scripts/governed_collision_agent_v2.py"
TESTS = ROOT / "tests/test_collision_rtc_v2.py"
ADAPTER_TESTS = ROOT / "tests/test_collision_agent_v2.py"


def require(condition: bool, reason: str, failures: list[str]) -> None:
    if not condition:
        failures.append(reason)


def main() -> int:
    failures: list[str] = []
    for path in (MANIFEST, CANDIDATE_WORKFLOW, TRUSTED_WORKFLOW, CORE, ADAPTER, TESTS, ADAPTER_TESTS):
        require(path.is_file(), f"missing:{path.relative_to(ROOT)}", failures)
    if failures:
        print(json.dumps({"state": "HOLD", "failures": failures}, indent=2))
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    candidate_workflow = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
    trusted_workflow = TRUSTED_WORKFLOW.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")
    tests = TESTS.read_text(encoding="utf-8")
    adapter_tests = ADAPTER_TESTS.read_text(encoding="utf-8")

    require(manifest.get("schema_version") == "2.0.0", "manifest_schema_version", failures)
    require(manifest.get("status") == "DRAFT_CONTROLLED_TEST", "manifest_status_must_be_draft", failures)
    require(manifest["canonical_parent"]["agent_id"] == "ct.agent.architecture-refactor-optimizer", "wrong_parent", failures)
    require(manifest["rtc"]["new_scheduler_slot"] is False, "new_scheduler_forbidden", failures)
    require(manifest["rtc"]["public_realtime_channel"] is False, "public_rtc_forbidden", failures)
    require(manifest["repair"]["maximum_retries"] == 3, "retry_bound", failures)
    require("merge" in manifest["repair"]["prohibited_auto_actions"], "merge_must_be_prohibited", failures)
    require("D3_action" in manifest["repair"]["prohibited_auto_actions"], "d3_must_be_prohibited", failures)

    required_agents = {
        "ct.subagent.collision.preflight-sentinel",
        "ct.subagent.collision.adjudicator",
        "ct.subagent.collision.repair-planner",
        "ct.subagent.collision.postmerge-reconciler",
        "ct.subagent.queue.priority-throttle",
    }
    actual_agents = {item["agent_id"] for item in manifest["agents"]}
    require(actual_agents == required_agents, "agent_set_drift", failures)
    require(all(item.get("authority_ceiling") != "D3" for item in manifest["agents"]), "agent_d3_forbidden", failures)

    require("pull_request:" in candidate_workflow, "candidate_trigger_missing", failures)
    require("pull_request_target:" not in candidate_workflow, "trusted_trigger_in_candidate_workflow", failures)
    require("schedule:" not in candidate_workflow and "workflow_dispatch:" not in candidate_workflow, "privileged_trigger_in_candidate_workflow", failures)
    require("permissions: {}" in candidate_workflow, "candidate_workflow_permissions_not_empty", failures)
    require("GITHUB_TOKEN" not in candidate_workflow, "token_exposed_to_untrusted_head", failures)
    require("github.event.pull_request.head.sha" in candidate_workflow, "candidate_checkout_binding_missing", failures)
    require("pull_request_target:" in trusted_workflow, "trusted_base_trigger_missing", failures)
    require("merge_group:" in trusted_workflow, "merge_group_trigger_missing", failures)
    require("schedule:" in trusted_workflow and "workflow_dispatch:" in trusted_workflow, "trusted_recovery_trigger_missing", failures)
    require("github.event.pull_request.head.sha" not in trusted_workflow, "candidate_code_reference_in_trusted_workflow", failures)
    require("persist-credentials: false" in candidate_workflow and "persist-credentials: false" in trusted_workflow, "credential_persistence_not_disabled", failures)
    require("if: github.event_name == 'pull_request_target'" in trusted_workflow, "trusted_job_boundary_missing", failures)
    require("--fail-on-severity 2" in trusted_workflow, "material_preflight_not_blocking", failures)
    require("--fail-on-severity 6" in trusted_workflow, "awareness_sweep_should_not_claim_merge_gate", failures)

    for symbol in (
        "snapshot_changed_during_evaluation",
        "semantic_inspection_incomplete",
        "RepairPlan.compile",
        "main_sha_start",
        "main_sha_end",
    ):
        require(symbol in adapter, f"adapter_missing:{symbol}", failures)
    for symbol in (
        "collision_domain_already_leased",
        "fence_token_mismatch",
        "repair_plan_stale_version_binding",
        "DEAD_LETTER",
        "idempotency_key",
        "previous_event_hash",
    ):
        require(symbol in core, f"core_missing:{symbol}", failures)
    require(tests.count("def test_") + adapter_tests.count("def test_") >= 25, "insufficient_test_count", failures)
    require("concurrent_acquire" in tests, "concurrency_test_missing", failures)
    require("prohibited_repairs" in tests, "authority_boundary_test_missing", failures)
    require("same_agent_id_in_different_manifests" in adapter_tests, "semantic_collision_test_missing", failures)
    require("main_movement_forces_hold" in adapter_tests, "toctou_test_missing", failures)
    require("byte_identical_direct_stack" in adapter_tests, "inert_duplicate_test_missing", failures)

    prohibited_runtime_patterns = [
        r"SUPABASE_SERVICE_ROLE_KEY\s*=",
        r"postgres(?:ql)?://[^\s]+:[^\s]+@",
        r"fingerprint_salt",
        r"vault[_ -]?location",
    ]
    packet_text = "\n".join((candidate_workflow, trusted_workflow, core, adapter, json.dumps(manifest)))
    for pattern in prohibited_runtime_patterns:
        require(not re.search(pattern, packet_text, re.IGNORECASE), f"protected_material_pattern:{pattern}", failures)

    state = "PASS" if not failures else "HOLD"
    print(
        json.dumps(
            {
                "state": state,
                "schema_version": "2.0.0",
                "checks": 34,
                "failures": failures,
                "merge_authority": False,
                "D3_auto": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
