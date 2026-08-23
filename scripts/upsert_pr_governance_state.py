#!/usr/bin/env python3
"""Upsert a machine-owned current-head governance comment on a pull request.

This script never edits the human-authored PR body and never interprets CI failure as
institutional HOLD/DENY. It reports source identity and observable workflow evidence only.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER = "<!-- ct-governance-observability-v1 -->"
TRACKED = (
    "Governed Merge Gate",
    "Security Governance",
    "Documentation Governance",
    "Documentation Reconciliation Continuity",
)


def api(method: str, path: str, data: dict[str, Any] | None = None) -> Any:
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://api.github.com{path}"
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def resolve_pr(event: dict[str, Any], repo: str) -> int | None:
    pr = event.get("pull_request")
    if isinstance(pr, dict):
        return int(pr["number"])

    run = event.get("workflow_run")
    if isinstance(run, dict):
        prs = run.get("pull_requests") or []
        if prs:
            return int(prs[0]["number"])
        head_sha = run.get("head_sha")
        if head_sha:
            owner, name = repo.split("/", 1)
            candidates = api("GET", f"/repos/{owner}/{name}/commits/{head_sha}/pulls?per_page=10")
            open_prs = [item for item in candidates if item.get("state") == "open"]
            if open_prs:
                return int(open_prs[0]["number"])
    return None


def latest_workflows(repo: str, head_sha: str) -> dict[str, dict[str, str | None]]:
    owner, name = repo.split("/", 1)
    q = urllib.parse.urlencode({"head_sha": head_sha, "per_page": 100})
    payload = api("GET", f"/repos/{owner}/{name}/actions/runs?{q}")
    result: dict[str, dict[str, str | None]] = {}
    for run in payload.get("workflow_runs", []):
        workflow_name = run.get("name")
        if workflow_name not in TRACKED or workflow_name in result:
            continue
        result[workflow_name] = {
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "run_id": str(run.get("id")) if run.get("id") is not None else None,
        }
    return result


def evidence_state(runs: dict[str, dict[str, str | None]]) -> str:
    if any(item.get("conclusion") == "failure" for item in runs.values()):
        return "CI_RED_REQUIRES_CLASSIFIER_READBACK"
    if runs and all(item.get("status") == "completed" and item.get("conclusion") == "success" for item in runs.values()):
        return "GREEN_FOR_OBSERVED_WORKFLOWS"
    if any(item.get("status") in {"queued", "in_progress", "pending"} for item in runs.values()):
        return "PENDING"
    return "PARTIAL_OR_NOT_YET_OBSERVED"


def build_comment(pr: dict[str, Any], runs: dict[str, dict[str, str | None]]) -> str:
    head = pr["head"]
    base = pr["base"]
    lines = [
        MARKER,
        "## Machine governance readback",
        "",
        f"- Updated UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"- PR transport state: `{'DRAFT' if pr.get('draft') else pr.get('state', 'unknown').upper()}`",
        f"- Exact head: `{head['sha']}` (`{head['ref']}`)",
        f"- Exact base: `{base['sha']}` (`{base['ref']}`)",
        f"- Mergeable readback: `{pr.get('mergeable')}`",
        f"- CI evidence state: `{evidence_state(runs)}`",
        "- Institutional disposition: `NOT_DERIVED_FROM_CI`",
        "",
        "### Observed governance workflows",
        "",
    ]
    if not runs:
        lines.append("No tracked workflow run has been observed for this exact head yet.")
    else:
        for name in TRACKED:
            item = runs.get(name)
            if not item:
                lines.append(f"- {name}: `NOT_OBSERVED`")
            else:
                lines.append(
                    f"- {name}: `{item.get('status')}` / `{item.get('conclusion')}` / run `{item.get('run_id')}`"
                )
    lines += [
        "",
        "### Interpretation firewall",
        "",
        "A CI failure is not automatically a CHLOM `HOLD` or `DENY`. `HOLD` and `DENY` require authoritative policy/evidence output. Exact-head/base identity is machine-read from GitHub and supersedes stale prose snapshots for transport/source identity only.",
    ]
    return "\n".join(lines)


def upsert(repo: str, pr_number: int, body: str) -> None:
    owner, name = repo.split("/", 1)
    comments = api("GET", f"/repos/{owner}/{name}/issues/{pr_number}/comments?per_page=100")
    for comment in comments:
        if MARKER in (comment.get("body") or ""):
            api("PATCH", f"/repos/{owner}/{name}/issues/comments/{comment['id']}", {"body": body})
            return
    api("POST", f"/repos/{owner}/{name}/issues/{pr_number}/comments", {"body": body})


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    pr_number = resolve_pr(event, repo)
    if pr_number is None:
        print("No open pull request resolved for governance readback; no mutation performed.")
        return 0
    owner, name = repo.split("/", 1)
    pr = api("GET", f"/repos/{owner}/{name}/pulls/{pr_number}")
    head_sha = pr["head"]["sha"]
    runs = latest_workflows(repo, head_sha)
    upsert(repo, pr_number, build_comment(pr, runs))
    print(json.dumps({"result": "PASS_GOVERNANCE_PR_READBACK_UPSERT", "pr": pr_number, "head_sha": head_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
