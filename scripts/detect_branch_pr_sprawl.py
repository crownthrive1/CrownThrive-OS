#!/usr/bin/env python3
"""Read a public-safe audit snapshot and report branch/PR WIP budget state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--branch-budget", type=int, default=8)
    parser.add_argument("--pr-budget", type=int, default=7)
    parser.add_argument("--strict", action="store_true", help="exit nonzero when a budget is exceeded")
    args = parser.parse_args()

    data = json.loads(args.snapshot.read_text(encoding="utf-8"))
    github = data.get("github", {})
    branches = int(github.get("branches", -1))
    prs = int(github.get("open_pull_requests", -1))
    if branches < 0 or prs < 0:
        raise SystemExit("SPRAWL_SENTINEL: snapshot lacks non-negative branch/PR counts")

    findings = []
    if branches > args.branch_budget:
        findings.append(f"branches={branches} exceeds budget={args.branch_budget}")
    if prs > args.pr_budget:
        findings.append(f"open_prs={prs} exceeds budget={args.pr_budget}")

    state = "ACTION_NEEDED" if findings else "WITHIN_BUDGET"
    print(json.dumps({"state": state, "findings": findings, "mutation_performed": False}, sort_keys=True))
    if args.strict and findings:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
