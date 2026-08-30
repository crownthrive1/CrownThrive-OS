#!/usr/bin/env python3
"""PentaPR workflow compatibility v4.

GitHub Actions may classify, label and project lifecycle state. It may not merge
or close a pull request. Exact-head terminal provider writes are exclusively
owned by the native PentaPR terminal provider after the CrownThrive assignment
institutionalization gate returns PASS.
"""
from __future__ import annotations

import argparse
import os
import sys

import penta_pr_lifecycle as legacy
from penta_github_labels import ensure_labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["pr", "merge", "closer"])
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--number", type=int)
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("repo_required")

    gh = legacy.GH(args.repo)
    ensure_labels(gh)
    legacy.pentapr(gh, args.number)

    if args.mode in {"merge", "closer"}:
        print(
            "PentaPR v4 classification complete. Terminal provider mutation is "
            "deferred to ct.penta.pr-terminalization.v4 and requires exact-head "
            "assignment completion, three-DAIL readback, PentaDocs, Drive Human/"
            "Hybrid/Machine readback, independent certification, OS projection, "
            "and a current DAIL chain PASS."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
