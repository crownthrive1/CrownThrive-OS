#!/usr/bin/env python3
"""Deterministic admission controller for Penta-created pull requests.

This module intentionally does not create or merge PRs. It decides CREATE, REUSE,
SUPERSEDE, or HOLD from explicit candidate, current-topology, and provider inputs.
Provider adapters must perform the resulting mutation only after this decision passes.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")
PASS = "PASS"


def fail(reason: str, **extra):
    return {"decision": "HOLD", "reason": reason, "authority_created": False, **extra}


def _valid_sha(value: object) -> bool:
    return bool(SHA40.fullmatch(str(value)))


def _reconciliation_hold(candidate: dict, open_prs: list[dict]) -> dict | None:
    reconciliation = candidate.get("reconciliation")
    if not isinstance(reconciliation, dict):
        return fail("missing_current_reconciliation")

    required = (
        "current_main_sha",
        "checked_at",
        "topology_snapshot_ref",
        "current_changes_checked",
        "open_prs_checked",
        "active_owners_checked",
        "production_truth_checked",
        "founder_intent_checked",
        "behavior_change_review_complete",
        "affected_surfaces",
        "current_change_refs",
        "production_truth_refs",
        "active_owner_refs",
        "behavior_changes",
    )
    missing = [key for key in required if key not in reconciliation]
    if missing:
        return fail("missing_reconciliation_fields", missing=missing)

    if not _valid_sha(reconciliation["current_main_sha"]):
        return fail("invalid_current_main_sha")

    boolean_gates = (
        "current_changes_checked",
        "open_prs_checked",
        "active_owners_checked",
        "production_truth_checked",
        "founder_intent_checked",
        "behavior_change_review_complete",
    )
    incomplete = [gate for gate in boolean_gates if reconciliation.get(gate) is not True]
    if incomplete:
        return fail("current_reconciliation_incomplete", incomplete=incomplete)

    if not reconciliation.get("topology_snapshot_ref"):
        return fail("missing_topology_snapshot_ref")
    if not reconciliation.get("affected_surfaces"):
        return fail("missing_affected_surface_census")
    if not reconciliation.get("current_change_refs"):
        return fail("missing_current_change_refs")
    if not reconciliation.get("production_truth_refs"):
        return fail("missing_production_truth_refs")

    relationship = candidate.get("base_relationship", "current_main")
    if relationship == "current_main":
        if candidate.get("base_sha") != reconciliation["current_main_sha"]:
            return fail(
                "stale_base_requires_reconcile",
                candidate_base=candidate.get("base_sha"),
                current_main_sha=reconciliation["current_main_sha"],
            )
    elif relationship == "stacked_owner":
        stacked_on_pr = candidate.get("stacked_on_pr")
        if not isinstance(stacked_on_pr, int) or stacked_on_pr < 1:
            return fail("stacked_owner_missing_pr")
        owner = next((p for p in open_prs if p.get("repo") == candidate.get("repo") and p.get("number") == stacked_on_pr), None)
        if owner is None:
            return fail("stacked_owner_not_open", stacked_on_pr=stacked_on_pr)
        if owner.get("head_sha") and candidate.get("base_sha") != owner.get("head_sha"):
            return fail("stacked_base_not_owner_head", stacked_on_pr=stacked_on_pr)
    else:
        return fail("invalid_base_relationship", base_relationship=relationship)

    # Current behavior is not a defect merely because it looks unusual. Any proposed
    # behavioral change must be explicitly enumerated and carry an authority reference.
    behavior_changes = reconciliation.get("behavior_changes")
    if not isinstance(behavior_changes, list):
        return fail("behavior_changes_not_list")
    for change in behavior_changes:
        if not isinstance(change, dict):
            return fail("invalid_behavior_change_record")
        for key in ("behavior_key", "observed_state", "desired_state"):
            if key not in change:
                return fail("incomplete_behavior_change_record", missing=key)
        if change.get("observed_state") != change.get("desired_state") and not change.get("authority_ref"):
            return fail("behavior_change_without_authority", behavior_key=change.get("behavior_key"))

    return None


def decide(candidate: dict, open_prs: list[dict]) -> dict:
    required = (
        "repo",
        "subject_key",
        "owner_lane",
        "base_sha",
        "head_sha",
        "authority_class",
        "changed_files",
        "tests",
        "rollback",
        "evidence",
        "post_open_obligations",
        "reconciliation",
    )
    missing = [k for k in required if k not in candidate]
    if missing:
        return fail("missing_candidate_fields", missing=missing)
    if not _valid_sha(candidate["base_sha"]) or not _valid_sha(candidate["head_sha"]):
        return fail("invalid_exact_sha")
    if candidate.get("authority_created", False):
        return fail("admission_cannot_create_authority")
    if not candidate.get("changed_files"):
        return fail("empty_candidate_diff")
    if not candidate.get("rollback", {}).get("defined"):
        return fail("rollback_not_defined")

    reconciliation_hold = _reconciliation_hold(candidate, open_prs)
    if reconciliation_hold:
        return reconciliation_hold

    # A PR body may claim PASS only when exact-head/provider evidence supports it.
    for claim in candidate.get("evidence", {}).get("claims", []):
        if claim.get("state") == PASS:
            if not claim.get("exact_head") or not claim.get("provider_receipt"):
                return fail("unproven_pass_claim", claim=claim.get("name"))

    same_subject = [p for p in open_prs if p.get("repo") == candidate["repo"] and p.get("subject_key") == candidate["subject_key"]]
    if len(same_subject) > 1:
        return fail("multiple_open_owner_prs", prs=sorted(p.get("number") for p in same_subject if p.get("number")))
    if same_subject:
        owner = same_subject[0]
        return {"decision": "REUSE", "pr_number": owner.get("number"), "reason": "canonical_subject_already_open", "authority_created": False}

    rck = candidate.get("release_candidate_key")
    if rck:
        same_release = [p for p in open_prs if p.get("repo") == candidate["repo"] and p.get("release_candidate_key") == rck]
        if same_release:
            owner = sorted(same_release, key=lambda p: p.get("number", 0))[0]
            return {"decision": "REUSE", "pr_number": owner.get("number"), "reason": "release_candidate_already_owned", "authority_created": False}

    supersedes = candidate.get("supersedes_pr")
    if supersedes:
        return {"decision": "SUPERSEDE", "supersedes_pr": supersedes, "reason": "explicit_collision_safe_successor", "authority_created": False}

    return {"decision": "CREATE", "reason": "complete_current_reconciled_unowned_merge_candidate", "authority_created": False}


def self_test() -> None:
    base = {
        "repo": "crownthrive1/CrownThrive-OS",
        "subject_key": "release:3.69.1.0",
        "owner_lane": "penta.release",
        "release_candidate_key": "crownthrive1/CrownThrive-OS:3.69.1.0:gen1",
        "base_sha": "0" * 40,
        "head_sha": "1" * 40,
        "base_relationship": "current_main",
        "authority_class": "D2",
        "changed_files": ["x"],
        "tests": {"status": "PASS"},
        "rollback": {"defined": True, "procedure": "abandon branch"},
        "evidence": {"claims": [{"name": "gate", "state": "PASS", "exact_head": True, "provider_receipt": "run:1"}]},
        "post_open_obligations": ["independent certification"],
        "authority_created": False,
        "reconciliation": {
            "current_main_sha": "0" * 40,
            "checked_at": "2026-08-31T18:40:00Z",
            "topology_snapshot_ref": "census:current",
            "current_changes_checked": True,
            "open_prs_checked": True,
            "active_owners_checked": True,
            "production_truth_checked": True,
            "founder_intent_checked": True,
            "behavior_change_review_complete": True,
            "affected_surfaces": ["release"],
            "current_change_refs": ["git:main"],
            "production_truth_refs": ["provider:readback"],
            "active_owner_refs": [],
            "behavior_changes": [],
        },
    }
    assert decide(base, [])["decision"] == "CREATE"
    assert decide(base, [{"repo": base["repo"], "subject_key": base["subject_key"], "number": 7}])["decision"] == "REUSE"
    bad = json.loads(json.dumps(base)); bad["evidence"]["claims"][0]["provider_receipt"] = None
    assert decide(bad, [])["reason"] == "unproven_pass_claim"
    assert decide(base, [{"repo": base["repo"], "release_candidate_key": base["release_candidate_key"], "number": 8}])["decision"] == "REUSE"
    stale = json.loads(json.dumps(base)); stale["reconciliation"]["current_main_sha"] = "2" * 40
    assert decide(stale, [])["reason"] == "stale_base_requires_reconcile"
    inferred = json.loads(json.dumps(base)); inferred["reconciliation"]["behavior_changes"] = [{"behavior_key": "tracking_cc", "observed_state": "enabled", "desired_state": "disabled"}]
    assert decide(inferred, [])["reason"] == "behavior_change_without_authority"
    print("penta_pr_admission self-test: PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--open-prs", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ns = ap.parse_args()
    if ns.self_test:
        self_test()
        return 0
    if not ns.candidate or not ns.open_prs:
        ap.error("--candidate and --open-prs are required unless --self-test")
    result = decide(json.loads(ns.candidate.read_text()), json.loads(ns.open_prs.read_text()))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] != "HOLD" else 2


if __name__ == "__main__":
    sys.exit(main())
