#!/usr/bin/env python3
"""Event-driven autonomous PentaPR convergence coordinator.

v2.2 keeps reversible restack assistance in the autonomous lane but fails closed
for terminal provider mutations. MERGE and CLOSE dispositions are evidence that
native terminal owners have work to do; they are not sufficient authority for
this autopilot to merge or close a pull request.

Terminal mutation remains reserved for the governed PentaMerge/PentaCloser path
after exact-head semantic owner results, required security/CHLOM/CIE gates and
independent certification are current and provider-read back. A stale predecessor
must also have the required successor/handoff readback before terminal close.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import penta_pr_lifecycle as lifecycle

AUTOPILOT_SELF_CHECK = "pentapr autopilot"
AUTONOMOUS_TERMINAL_HOLDS = {
    "MERGE": "HOLD_INDEPENDENT_SEMANTIC_GATE_OWNER_RESULTS_REQUIRED",
    "CLOSE": "HOLD_SUCCESSOR_OR_TERMINAL_HANDOFF_PROVIDER_READBACK_REQUIRED",
}


def configure_self_check_exclusion() -> None:
    lifecycle.SELF_LIFECYCLE_CHECK_NAMES = frozenset(
        set(lifecycle.SELF_LIFECYCLE_CHECK_NAMES) | {AUTOPILOT_SELF_CHECK}
    )


def autonomous_terminal_mutation_guard(disposition: str | None) -> tuple[bool, str]:
    """Return a deterministic fail-closed decision for autonomous terminal work.

    The autonomous coordinator may classify and prepare work, but it must not
    convert GitHub mergeability/check labels into terminal authority. The native
    terminal owner can execute separately after governed semantic evidence is
    exact-head current and read back.
    """

    hold = AUTONOMOUS_TERMINAL_HOLDS.get(disposition or "")
    if hold:
        return False, hold
    return True, "PASS_NON_TERMINAL_AUTONOMOUS_ACTION"


def attempt_restack(gh: lifecycle.GH, number: int) -> tuple[bool, str]:
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    labels = lifecycle.read_labels(gh, number)
    if "penta:hold" in labels:
        return False, "operator_hold"
    if pull.get("draft"):
        return False, "draft"
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


def drive_one(gh: lifecycle.GH, number: int) -> None:
    lifecycle.pentapr(gh, number)
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    if pull.get("state") != "open":
        print(f"PentaAutopilot #{number} terminal=ALREADY_CLOSED")
        return

    _, state = lifecycle.lifecycle_comment(gh, number)
    disposition = (state or {}).get("disposition")
    reason = (state or {}).get("reason")

    if disposition == "RESTACK":
        changed, message = attempt_restack(gh, number)
        print(f"PentaAutopilot #{number} restack={changed} {message}")
        return

    terminal_allowed, terminal_reason = autonomous_terminal_mutation_guard(disposition)
    if not terminal_allowed:
        print(
            f"PentaAutopilot #{number} terminal=DEFERRED "
            f"disposition={disposition} hold={terminal_reason} "
            f"reason={reason or 'unknown'}"
        )
        return

    print(
        f"PentaAutopilot #{number} terminal=DEFERRED "
        f"disposition={disposition or 'unknown'} reason={reason or 'unknown'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--number", type=int)
    # Compatibility flag retained so old/manual callers do not crash. It does
    # not grant terminal provider-mutation authority.
    parser.add_argument("--allow-deadline-close", action="store_true")
    args = parser.parse_args()
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
