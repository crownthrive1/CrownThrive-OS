#!/usr/bin/env python3
"""Read-only PentaImmune repo-local hunter.

The hunter consumes GitHub metadata and emits ranked work candidates. It never
scans external targets and never mutates GitHub. Repair execution remains a
separate governed PentaFactory/PentaPR responsibility.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.penta_immune import WeaknessCandidate, rank_candidates  # noqa: E402


def _get_json(url: str, token: str) -> dict[str, Any] | list[Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CrownThrive-PentaImmune/1.0",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def candidates_from_snapshot(snapshot: dict[str, Any]) -> list[WeaknessCandidate]:
    candidates: list[WeaknessCandidate] = []
    for run in snapshot.get("failed_workflow_runs", []):
        run_id = str(run.get("id", "")).strip()
        if not run_id:
            continue
        candidates.append(
            WeaknessCandidate(
                id=f"ci-{run_id}",
                kind="ci_failure",
                source_ref=f"workflow-run:{run_id}",
                authority_level="D1",
                handler="repair_workflow",
                severity=4,
                recurrence=2,
                confidence=5,
                reversibility=4,
                testability=5,
                blast_radius=2,
                rollback={"method": "git_revert", "scope": "repair commit"},
                fallback={"method": "hold", "redundancy": "known-good-main"},
                metadata={
                    "workflow": str(run.get("name", "")),
                    "head_branch": str(run.get("head_branch", "")),
                    "head_sha": str(run.get("head_sha", "")),
                    "html_url": str(run.get("html_url", "")),
                },
            )
        )

    for issue in snapshot.get("open_issues", []):
        labels = {
            str(item.get("name", "")).strip().lower()
            for item in issue.get("labels", [])
            if isinstance(item, dict)
        }
        if "penta-immune-ready" not in labels:
            continue
        number = str(issue.get("number", "")).strip()
        if not number:
            continue
        candidates.append(
            WeaknessCandidate(
                id=f"issue-{number}",
                kind="known_governance_defect",
                source_ref=f"issue:{number}",
                authority_level="D2",
                handler="patch_known_code",
                severity=3,
                recurrence=2,
                confidence=4,
                reversibility=4,
                testability=4,
                blast_radius=2,
                rollback={"method": "git_revert", "scope": "repair commit"},
                fallback={"method": "hold", "redundancy": "known-good-main"},
                metadata={"title": str(issue.get("title", "")), "html_url": str(issue.get("html_url", ""))},
            )
        )
    return candidates


def live_snapshot(repo: str, token: str, api_url: str) -> dict[str, Any]:
    runs = _get_json(f"{api_url}/repos/{repo}/actions/runs?status=failure&per_page=20", token)
    issues = _get_json(f"{api_url}/repos/{repo}/issues?state=open&per_page=100", token)
    return {
        "repo": repo,
        "failed_workflow_runs": list((runs or {}).get("workflow_runs", [])),
        "open_issues": [
            item for item in (issues or []) if isinstance(item, dict) and "pull_request" not in item
        ],
    }


def report(snapshot: dict[str, Any]) -> dict[str, Any]:
    ranked = rank_candidates(candidates_from_snapshot(snapshot))
    output = {
        "schema": "ct.penta.immune-hunt.v1",
        "scope": "authorized_repo_local_only",
        "repo": snapshot.get("repo"),
        "candidate_count": len(ranked),
        "selected": None,
        "ranked": [],
        "mutation_performed": False,
        "production_promotion_authorized": False,
    }
    for candidate in ranked[:20]:
        item = {
            "id": candidate.id,
            "kind": candidate.kind,
            "source_ref": candidate.source_ref,
            "authority_level": candidate.authority_level,
            "handler": candidate.handler,
            "score": candidate.score,
            "fingerprint": candidate.fingerprint,
            "rollback": dict(candidate.rollback),
            "fallback": dict(candidate.fallback),
            "metadata": dict(candidate.metadata),
        }
        output["ranked"].append(item)
    if output["ranked"]:
        output["selected"] = output["ranked"][0]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.snapshot:
        snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    else:
        repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        if not repo or not token:
            print(json.dumps({"status": "HOLD", "reason": "missing GitHub repo/token for live read-only hunt"}))
            return 0
        snapshot = live_snapshot(repo, token, api_url)

    output = report(snapshot)
    rendered = json.dumps(output, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
