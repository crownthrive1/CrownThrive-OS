#!/usr/bin/env python3
"""Read-only convergence/refactor planner for CrownThrive Phase 2.99.

This module reuses the existing collision controller and produces an attention-rotation
and refactor plan. It never mutates GitHub, providers, runtime state, votes, or phase.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

import governed_collision_control as gcc


def classify_mode(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    throttle = snapshot["throttle"]
    ranked = throttle["ranked"]
    open_prs = int(snapshot["open_pr_count"])
    stale = sum(1 for item in ranked if item.get("stale_base"))
    material_collisions = sum(1 for item in snapshot["collisions"] if int(item.get("severity") or 0) >= 2)
    p0 = [item for item in ranked if item.get("priority", {}).get("band") == "P0"]

    reasons: List[str] = []
    if p0:
        mode = "INCIDENT"
        reasons.append("explicit_critical_security_or_founder_priority_signal")
    elif open_prs >= 20 or stale >= 8 or material_collisions >= 8:
        mode = "CONVERGENCE"
        if open_prs >= 20:
            reasons.append("open_pr_pressure")
        if stale >= 8:
            reasons.append("stale_main_pressure")
        if material_collisions >= 8:
            reasons.append("material_collision_pressure")
    elif open_prs >= 10 or stale >= 3:
        mode = "BALANCED"
        if open_prs >= 10:
            reasons.append("moderate_open_pr_pressure")
        if stale >= 3:
            reasons.append("moderate_stale_main_pressure")
    else:
        mode = "EXPANSION"
        reasons.append("convergence_pressure_below_threshold")

    budgets = {
        "EXPANSION": {"closure": 35, "current_build": 45, "research": 20},
        "BALANCED": {"closure": 50, "current_build": 35, "research": 15},
        "CONVERGENCE": {"closure": 70, "current_build": 20, "research": 10},
        "INCIDENT": {"closure": 80, "current_build": 15, "research": 5},
    }
    return {
        "mode": mode,
        "reasons": reasons,
        "open_pr_count": open_prs,
        "stale_main_pr_count": stale,
        "material_collision_count": material_collisions,
        "attention_budget_percent": budgets[mode],
    }


def lane_for(item: Dict[str, Any]) -> str:
    text = f"{item.get('title') or ''}".lower()
    if any(term in text for term in ("hard-exit", "hard exit", "help center", "795", "phase 2.99", "reconcile")):
        return "phase_2_99_closure"
    if any(term in text for term in ("security", "merge gate", "collision", "governance", "quorum")):
        return "canonical_governance"
    if any(term in text for term in ("docs", "documentation", "handbook", "source", "revival", "canon", "doctrine")):
        return "documentation_current_truth"
    if any(term in text for term in ("api", "mcp", "provider", "runtime", "webhook", "vault", "website")):
        return "runtime_api_provider"
    if any(term in text for term in ("framework", "cie", "agent", "federation", "orchestrator")):
        return "agent_framework_federation"
    if any(term in text for term in ("virality", "sermon", "storefront", "product", "commerce")):
        return "product_platform_vertical"
    return "future_or_other"


def refactor_disposition(item: Dict[str, Any], mode: str) -> Dict[str, Any]:
    stale = bool(item.get("stale_base"))
    severity = int(item.get("collision_severity") or 0)
    draft = bool(item.get("draft"))
    lane = lane_for(item)

    if severity >= 5:
        disposition = "hold_for_adjudication"
        reason = "constitutional_or_d3_collision"
    elif severity >= 2:
        disposition = "preserve_and_stack_on_current_owner"
        reason = "material_collision_requires_single_owner"
    elif stale:
        disposition = "preserve_and_rebase"
        reason = "current_main_advanced"
    elif mode in {"CONVERGENCE", "INCIDENT"} and lane in {"future_or_other", "agent_framework_federation"} and draft:
        disposition = "continue_research_without_promotion"
        reason = "attention_rotated_to_closure_without_discarding_work"
    else:
        disposition = "preserve_active"
        reason = "no_destructive_refactor_required"

    return {
        "number": item["number"],
        "title": item.get("title"),
        "lane": lane,
        "priority": item.get("priority"),
        "stale_base": stale,
        "collision_severity": severity,
        "disposition": disposition,
        "reason": reason,
        "knowledge_preserved": True,
        "automatic_close": False,
        "automatic_delete": False,
        "force_push": False,
    }


def build_plan(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    mode = classify_mode(snapshot)
    ranked = snapshot["throttle"]["ranked"]
    items = [refactor_disposition(item, mode["mode"]) for item in ranked]

    lane_order = {
        "canonical_governance": 0,
        "phase_2_99_closure": 1,
        "documentation_current_truth": 2,
        "runtime_api_provider": 3,
        "agent_framework_federation": 4,
        "product_platform_vertical": 5,
        "future_or_other": 6,
    }
    items.sort(
        key=lambda item: (
            lane_order[item["lane"]],
            -int((item.get("priority") or {}).get("score") or 0),
            int(item["number"]),
        )
    )

    closure_focus = [
        item for item in items
        if item["lane"] in {"canonical_governance", "phase_2_99_closure", "documentation_current_truth"}
    ][:8]

    return {
        "mode": "convergence_refactor_plan",
        "current_main_sha": snapshot["throttle"]["main_sha"],
        "pressure": mode,
        "closure_focus": closure_focus,
        "all_open_pr_dispositions": items,
        "refactor_sequence": [
            "canonical_main_and_merge_perimeter",
            "phase_2_99_hard_exit_and_full_documentation_gate",
            "current_truth_documentation_and_source_registry",
            "runtime_api_mcp_provider_state",
            "agent_framework_and_federation_state",
            "product_and_platform_verticals",
            "future_research_and_experimental_work",
        ],
        "preservation_invariants": {
            "never_silently_destroy_knowledge": True,
            "never_silently_overwrite_history": True,
            "no_automation_branch_deletion": True,
            "no_automation_file_deletion": True,
            "no_force_push": True,
            "no_silent_pr_closure": True,
            "supersession_requires_predecessor_and_successor_or_reason": True,
            "prefer_update_existing_owner_over_parallel_owner": True,
            "prefer_extract_unique_delta_over_wholesale_stale_packet_promotion": True,
        },
        "phase_3_advancement": False,
    }


def write_summary(plan: Dict[str, Any]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    pressure = plan["pressure"]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n## CrownThrive Convergence / Refactor Rotation\n\n")
        handle.write(f"- Mode: `{pressure['mode']}`\n")
        handle.write(f"- Open PRs: `{pressure['open_pr_count']}`\n")
        handle.write(f"- Stale main-based PRs: `{pressure['stale_main_pr_count']}`\n")
        handle.write(f"- Material collisions: `{pressure['material_collision_count']}`\n")
        handle.write(f"- Attention budget: `{pressure['attention_budget_percent']}`\n")
        handle.write("- Knowledge destruction: `PROHIBITED`\n")
        handle.write("- Silent overwrite: `PROHIBITED`\n")
        handle.write("- Automatic branch/file deletion: `PROHIBITED`\n")
        handle.write("\n### Closure focus\n")
        for item in plan["closure_focus"]:
            handle.write(f"- #{item['number']} `{item['lane']}` → `{item['disposition']}` — {item['title']}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        fake = {
            "open_pr_count": 24,
            "collisions": [{"severity": 2}] * 9,
            "throttle": {
                "main_sha": "abc",
                "ranked": [
                    {
                        "number": 1,
                        "title": "Phase 2.99 hard-exit reconciliation",
                        "draft": True,
                        "stale_base": True,
                        "collision_severity": 2,
                        "priority": {"score": 80, "band": "P1"},
                    },
                    {
                        "number": 2,
                        "title": "Future framework experiment",
                        "draft": True,
                        "stale_base": False,
                        "collision_severity": 0,
                        "priority": {"score": 20, "band": "P4"},
                    },
                ],
            },
        }
        plan = build_plan(fake)
        assert plan["pressure"]["mode"] == "CONVERGENCE"
        assert plan["all_open_pr_dispositions"][0]["automatic_delete"] is False
        assert all(item["force_push"] is False for item in plan["all_open_pr_dispositions"])
        assert any(item["disposition"] == "continue_research_without_promotion" for item in plan["all_open_pr_dispositions"])
        print(json.dumps({"status": "PASS", "tests": 4, "mode": plan["pressure"]["mode"]}, indent=2))
        return 0

    if not args.repo or not args.token:
        parser.error("--repo and --token/GITHUB_TOKEN are required")
    snapshot = gcc.queue_snapshot(args.repo, args.token)
    plan = build_plan(snapshot)
    print(json.dumps(plan, indent=2, sort_keys=True))
    write_summary(plan)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
