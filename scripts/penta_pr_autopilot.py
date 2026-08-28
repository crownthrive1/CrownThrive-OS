#!/usr/bin/env python3
"""Event-driven autonomous PentaPR convergence authority.

This wrapper preserves the existing PentaPR/PentaMerge/PentaCloser contracts while
closing the execution gap between classification and terminal action. It never
removes HOLDs, promotes drafts, bypasses failed/pending checks, manufactures
provider evidence, or expands D3 authority.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import penta_pr_lifecycle as lifecycle


AUTOPILOT_SELF_CHECK = "pentapr autopilot"


def configure_self_check_exclusion() -> None:
    lifecycle.SELF_LIFECYCLE_CHECK_NAMES = frozenset(
        set(lifecycle.SELF_LIFECYCLE_CHECK_NAMES) | {AUTOPILOT_SELF_CHECK}
    )


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


def drive_one(gh: lifecycle.GH, number: int, *, allow_deadline_close: bool) -> None:
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

    if disposition == "MERGE":
        merged, message = lifecycle.attempt_merge(gh, number)
        print(f"PentaAutopilot #{number} merged={merged} {message}")
        return

    if allow_deadline_close:
        lifecycle.pentacloser(gh, number)
        return

    print(
        f"PentaAutopilot #{number} terminal=DEFERRED "
        f"disposition={disposition or 'unknown'} reason={reason or 'unknown'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--number", type=int)
    parser.add_argument("--allow-deadline-close", action="store_true")
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("repo_required")

    configure_self_check_exclusion()
    gh = lifecycle.GH(args.repo)
    lifecycle.ensure_labels(gh)

    pulls = lifecycle.open_pull_requests(gh, args.number)
    for pull in pulls:
        drive_one(
            gh,
            int(pull["number"]),
            allow_deadline_close=args.allow_deadline_close,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
