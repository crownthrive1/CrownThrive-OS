#!/usr/bin/env python3
"""Fail-closed CrownThrive collision preflight with intentional-stack awareness.

An intentional stacked dependency is not itself a destructive collision when the
parent and child have no exact changed-file overlap. Exact-file overlap, semantic
or higher collisions, and stale main-based state remain blocking.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

import governed_collision_control as gcc


def is_intentional_stack_only(item: dict) -> bool:
    reasons = set(item.get("reasons") or [])
    exact = item.get("exact_files") or []
    severity = int(item.get("severity") or 0)
    return (
        severity == 2
        and "stacked_dependency_detected" in reasons
        and not exact
        and not any(term in reasons for term in (
            "exact_changed_file_overlap",
            "constitutional_surface_parallel_change",
        ))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args()
    if not args.repo or not args.token:
        parser.error("--repo and --token/GITHUB_TOKEN are required")

    result = gcc.preflight(args.repo, args.token, args.pr)
    material = []
    awareness = []
    for item in result.get("collisions") or []:
        severity = int(item.get("severity") or 0)
        if severity < 2:
            awareness.append(item)
        elif is_intentional_stack_only(item):
            copy = dict(item)
            copy["promotion_dependency"] = "parent_must_be_accepted_before_child_promotion"
            awareness.append(copy)
        else:
            material.append(item)

    stale = bool(result.get("stale_main_base"))
    output = {
        "pr": args.pr,
        "current_main_sha": result.get("current_main_sha"),
        "target_head_sha": result.get("target_head_sha"),
        "target_base_ref": result.get("target_base_ref"),
        "stale_main_base": stale,
        "blocking_collisions": material,
        "awareness_collisions": awareness,
        "status": "HOLD" if stale or material else "PASS",
        "rule": "intentional stack without exact-file overlap is dependency awareness; exact overlap remains blocking",
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if stale or material:
        print("Collision preflight HOLD: material collision or stale main-based packet requires reconciliation.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
