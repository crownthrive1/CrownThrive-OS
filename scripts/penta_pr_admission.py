#!/usr/bin/env python3
"""Deterministic admission controller for Penta-created pull requests.

This module intentionally does not create or merge PRs. It decides CREATE, REUSE,
SUPERSEDE, or HOLD from explicit candidate and provider inputs. Provider adapters
must perform the resulting mutation only after this decision passes.
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


def decide(candidate: dict, open_prs: list[dict]) -> dict:
    required = ("repo", "subject_key", "owner_lane", "base_sha", "head_sha", "authority_class", "changed_files", "tests", "rollback", "evidence", "post_open_obligations")
    missing = [k for k in required if k not in candidate]
    if missing:
        return fail("missing_candidate_fields", missing=missing)
    if not SHA40.fullmatch(str(candidate["base_sha"])) or not SHA40.fullmatch(str(candidate["head_sha"])):
        return fail("invalid_exact_sha")
    if candidate.get("authority_created", False):
        return fail("admission_cannot_create_authority")
    if not candidate.get("changed_files"):
        return fail("empty_candidate_diff")
    if not candidate.get("rollback", {}).get("defined"):
        return fail("rollback_not_defined")

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

    return {"decision": "CREATE", "reason": "complete_unowned_merge_candidate", "authority_created": False}


def self_test() -> None:
    base = {
        "repo":"crownthrive1/CrownThrive-OS", "subject_key":"release:3.69.1.0", "owner_lane":"penta.release",
        "release_candidate_key":"crownthrive1/CrownThrive-OS:3.69.1.0:gen1",
        "base_sha":"0"*40, "head_sha":"1"*40, "authority_class":"D2", "changed_files":["x"],
        "tests":{"status":"PASS"}, "rollback":{"defined":True,"procedure":"abandon branch"},
        "evidence":{"claims":[{"name":"gate","state":"PASS","exact_head":True,"provider_receipt":"run:1"}]},
        "post_open_obligations":["independent certification"], "authority_created":False,
    }
    assert decide(base, [])["decision"] == "CREATE"
    assert decide(base, [{"repo":base["repo"],"subject_key":base["subject_key"],"number":7}])["decision"] == "REUSE"
    bad = json.loads(json.dumps(base)); bad["evidence"]["claims"][0]["provider_receipt"] = None
    assert decide(bad, [])["reason"] == "unproven_pass_claim"
    assert decide(base, [{"repo":base["repo"],"release_candidate_key":base["release_candidate_key"],"number":8}])["decision"] == "REUSE"
    print("penta_pr_admission self-test: PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--open-prs", type=Path)
    ap.add_argument("--self-test", action="store_true")
    ns = ap.parse_args()
    if ns.self_test:
        self_test(); return 0
    if not ns.candidate or not ns.open_prs:
        ap.error("--candidate and --open-prs are required unless --self-test")
    result = decide(json.loads(ns.candidate.read_text()), json.loads(ns.open_prs.read_text()))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["decision"] != "HOLD" else 2

if __name__ == "__main__":
    sys.exit(main())
