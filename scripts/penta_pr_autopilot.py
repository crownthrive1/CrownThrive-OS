#!/usr/bin/env python3
"""Event-driven autonomous PentaPR convergence authority.

v2.3 keeps the single provider-required Governed Merge Gate as the GitHub merge
perimeter while preserving the separate release topology for elevated-risk work.
Other workflows remain valuable evidence but do not independently veto merge
unless their control is aggregated as applicable inside that required context.

Important authority boundary:
- D0/D1 may use the bounded GitHub-native autonomous merge path after the exact
  required gate passes and all ordinary mergeability/hold predicates pass.
- D2 is never merged by PentaPR Autopilot. It may be moved from draft to ready
  after the exact merge gate passes, then must continue through the independent
  PentaSecurity -> CHLOM -> applicable CIE -> PentaCertifier -> PentaMerge/
  PentaRelease topology.
- D3 is human-reserved and is never autonomously merged.
- Missing risk classification fails closed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import penta_pr_lifecycle as lifecycle

AUTOPILOT_SELF_CHECK = "pentapr autopilot"
REQUIRED_MERGE_CONTEXT = "crownthrive governed merge gate"
BAD_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}
RISK_LABELS = (
    ("D3", "penta:risk:d3"),
    ("D2", "penta:risk:d2"),
    ("D1", "penta:risk:d1"),
    ("D0", "penta:risk:d0"),
)


def configure_self_check_exclusion() -> None:
    lifecycle.SELF_LIFECYCLE_CHECK_NAMES = frozenset(
        set(lifecycle.SELF_LIFECYCLE_CHECK_NAMES) | {AUTOPILOT_SELF_CHECK}
    )


def classified_risk(labels: set[str]) -> str | None:
    observed = [risk for risk, label in RISK_LABELS if label in labels]
    if len(observed) != 1:
        return None
    return observed[0]


def autonomous_merge_allowed(labels: set[str]) -> tuple[bool, str]:
    risk = classified_risk(labels)
    if risk is None:
        return False, "risk_unclassified_or_ambiguous"
    if risk == "D3":
        return False, "d3_human_reserved"
    if risk == "D2":
        return False, "d2_independent_release_topology_required"
    return True, f"{risk.lower()}_github_native_merge_eligible"


def self_test() -> dict[str, Any]:
    vectors = [
        ({"penta:risk:d0"}, True, "d0_github_native_merge_eligible"),
        ({"penta:risk:d1"}, True, "d1_github_native_merge_eligible"),
        ({"penta:risk:d2"}, False, "d2_independent_release_topology_required"),
        ({"penta:risk:d3"}, False, "d3_human_reserved"),
        (set(), False, "risk_unclassified_or_ambiguous"),
        ({"penta:risk:d1", "penta:risk:d2"}, False, "risk_unclassified_or_ambiguous"),
    ]
    receipts: list[dict[str, Any]] = []
    for labels, expected_allowed, expected_reason in vectors:
        allowed, reason = autonomous_merge_allowed(labels)
        if allowed != expected_allowed or reason != expected_reason:
            raise RuntimeError(
                f"autopilot self-test failed labels={sorted(labels)} allowed={allowed} reason={reason}"
            )
        receipts.append({"labels": sorted(labels), "allowed": allowed, "reason": reason})
    return {
        "schema": "ct.penta.pr-autopilot.release-topology-self-test.v1",
        "state": "PASS",
        "vectors": receipts,
        "d2_requires_independent_release_topology": True,
        "d3_human_reserved": True,
        "unknown_risk_fail_closed": True,
        "authority_created": False,
    }


def required_gate_state(gh: lifecycle.GH, sha: str) -> tuple[str, dict[str, Any] | None]:
    observed = gh.get(f"/repos/{gh.repo}/commits/{sha}/check-runs?per_page=100").get("check_runs", [])
    matching = [
        item for item in observed
        if REQUIRED_MERGE_CONTEXT in str(item.get("name") or "").strip().casefold()
    ]
    if not matching:
        return "MISSING", None
    latest = max(
        matching,
        key=lambda item: (
            int(item.get("id") or 0),
            str(item.get("completed_at") or ""),
            str(item.get("started_at") or ""),
        ),
    )
    if latest.get("status") != "completed":
        return "PENDING", latest
    conclusion = str(latest.get("conclusion") or "").casefold()
    if conclusion == "success":
        return "PASS", latest
    if conclusion in BAD_CONCLUSIONS:
        return "FAIL", latest
    return "PENDING", latest


def advisory_check_summary(gh: lifecycle.GH, sha: str) -> dict[str, int]:
    observed = gh.get(f"/repos/{gh.repo}/commits/{sha}/check-runs?per_page=100").get("check_runs", [])
    current = lifecycle._latest_check_runs(observed)
    advisory = [
        item for item in current
        if REQUIRED_MERGE_CONTEXT not in str(item.get("name") or "").strip().casefold()
        and not lifecycle._is_self_lifecycle_check(item)
    ]
    return {
        "failed": sum(str(item.get("conclusion") or "").casefold() in BAD_CONCLUSIONS for item in advisory),
        "pending": sum(item.get("status") != "completed" for item in advisory),
        "observed": len(advisory),
    }


def mark_ready_for_review(gh: lifecycle.GH, pull: dict[str, Any]) -> tuple[bool, str]:
    if not pull.get("draft"):
        return False, "already_ready"
    node_id = str(pull.get("node_id") or "")
    if not node_id:
        return False, "pull_request_node_id_missing"
    payload = gh.post(
        "/graphql",
        {
            "query": (
                "mutation($id:ID!){markPullRequestReadyForReview(input:{pullRequestId:$id})"
                "{pullRequest{isDraft}}}"
            ),
            "variables": {"id": node_id},
        },
    )
    errors = payload.get("errors") if isinstance(payload, dict) else None
    if errors:
        return False, "ready_transition_failed"
    is_draft = (((payload.get("data") or {}).get("markPullRequestReadyForReview") or {}).get("pullRequest") or {}).get("isDraft")
    return is_draft is False, "marked_ready" if is_draft is False else "ready_transition_unconfirmed"


def attempt_restack(gh: lifecycle.GH, number: int) -> tuple[bool, str]:
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    labels = lifecycle.read_labels(gh, number)
    if "penta:hold" in labels:
        return False, "operator_hold"
    if pull.get("mergeable_state") != "behind":
        return False, f"restack_not_required:{pull.get('mergeable_state') or 'unknown'}"

    head_sha = ((pull.get("head") or {}).get("sha"))
    if not head_sha:
        return False, "head_sha_missing"

    result: dict[str, Any] = gh.put(
        f"/repos/{gh.repo}/pulls/{number}/update-branch",
        {"expected_head_sha": head_sha},
    )
    return True, str(result.get("message") or "update_branch_requested")


def attempt_required_merge(gh: lifecycle.GH, number: int) -> tuple[bool, str]:
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    labels = lifecycle.read_labels(gh, number)
    if "penta:hold" in labels:
        return False, "operator_hold"
    allowed, risk_reason = autonomous_merge_allowed(labels)
    if not allowed:
        return False, risk_reason
    head_sha = ((pull.get("head") or {}).get("sha"))
    if not head_sha:
        return False, "head_sha_missing"
    gate_state, _ = required_gate_state(gh, head_sha)
    if gate_state != "PASS":
        return False, f"required_gate_{gate_state.lower()}"
    if pull.get("draft"):
        changed, reason = mark_ready_for_review(gh, pull)
        if not changed:
            return False, reason
        pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
        head_sha = ((pull.get("head") or {}).get("sha"))
        if not head_sha:
            return False, "head_sha_missing_after_ready"
        gate_state, _ = required_gate_state(gh, head_sha)
        if gate_state != "PASS":
            return False, f"required_gate_{gate_state.lower()}_after_ready"
    if pull.get("mergeable") is not True:
        return False, f"not_mergeable:{pull.get('mergeable_state') or 'unknown'}"

    result = gh.put(
        f"/repos/{gh.repo}/pulls/{number}/merge",
        {
            "merge_method": "squash",
            "sha": head_sha,
            "commit_title": f"PentaMerge: {pull['title']}",
        },
    )
    merged = bool(result.get("merged"))
    if merged:
        lifecycle.mark_terminal(gh, number, "penta:terminal:merged", "penta:authority:merge")
    return merged, result.get("message", "merge_attempted")


def drive_one(gh: lifecycle.GH, number: int) -> None:
    lifecycle.pentapr(gh, number)
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    if pull.get("state") != "open":
        print(f"PentaAutopilot #{number} terminal=ALREADY_CLOSED")
        return

    labels = lifecycle.read_labels(gh, number)
    if "penta:hold" in labels:
        print(f"PentaAutopilot #{number} terminal=DEFERRED reason=operator_hold")
        return

    text = ((pull.get("title") or "") + "\n" + (pull.get("body") or "")).lower()
    if "superseded by" in text or "represented-zero-delta" in text:
        lifecycle.pentacloser(gh, number)
        print(f"PentaAutopilot #{number} close_candidate=true reason=superseded_or_represented")
        return

    if pull.get("mergeable_state") == "behind":
        changed, message = attempt_restack(gh, number)
        print(f"PentaAutopilot #{number} restack={changed} {message}")
        return
    if pull.get("mergeable") is False or pull.get("mergeable_state") == "dirty":
        print(f"PentaAutopilot #{number} terminal=DEFERRED reason={pull.get('mergeable_state') or 'not_mergeable'}")
        return

    head_sha = ((pull.get("head") or {}).get("sha"))
    if not head_sha:
        print(f"PentaAutopilot #{number} terminal=DEFERRED reason=head_sha_missing")
        return
    gate_state, _ = required_gate_state(gh, head_sha)
    advisory = advisory_check_summary(gh, head_sha)
    if gate_state != "PASS":
        print(
            f"PentaAutopilot #{number} terminal=DEFERRED required_gate={gate_state} "
            f"advisory_failed={advisory['failed']} advisory_pending={advisory['pending']}"
        )
        return

    allowed, risk_reason = autonomous_merge_allowed(labels)
    if not allowed:
        if pull.get("draft") and risk_reason == "d2_independent_release_topology_required":
            changed, ready_reason = mark_ready_for_review(gh, pull)
            print(
                f"PentaAutopilot #{number} ready={changed} {ready_reason} terminal=DEFERRED "
                f"reason={risk_reason} advisory_failed={advisory['failed']} advisory_pending={advisory['pending']}"
            )
            return
        print(
            f"PentaAutopilot #{number} terminal=DEFERRED reason={risk_reason} "
            f"advisory_failed={advisory['failed']} advisory_pending={advisory['pending']}"
        )
        return

    merged, message = attempt_required_merge(gh, number)
    print(
        f"PentaAutopilot #{number} merged={merged} {message} "
        f"advisory_failed={advisory['failed']} advisory_pending={advisory['pending']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--number", type=int)
    parser.add_argument("--allow-deadline-close", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    if not args.repo:
        raise SystemExit("repo_required")

    configure_self_check_exclusion()
    gh = lifecycle.GH(args.repo)
    lifecycle.ensure_labels(gh)

    pulls = lifecycle.open_pull_requests(gh, args.number)
    for pull in pulls:
        drive_one(gh, int(pull["number"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
