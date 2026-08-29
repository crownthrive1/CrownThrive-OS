#!/usr/bin/env python3
"""PentaPM/PentaIssues/PentaDevelopment native GitHub metadata convergence.

This reconciler closes the gap between CrownThrive's Penta governance metadata
and GitHub-native planning surfaces:

- PentaPM/PentaProjects: project membership and fields are handled by the
  existing penta_pm_reconcile.py engine after this script runs.
- PentaMilestone: release-train milestone is handled by the existing engine.
- PentaIssues: parent/sub-issue and blocked-by relationships are materialized
  through GitHub's issue relationship APIs.
- PentaDevelopment: every governed PR gets a native Development link. Terminal
  work links directly with a closing keyword. Partial multi-PR work receives an
  idempotent PR-scoped child issue, preserving the umbrella issue with Refs.

The script is idempotent and may be run for one PR or across all open governed
PRs. It never merges or closes work itself; GitHub closing keywords become
effective only when the governed PR reaches the default branch.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

API = "https://api.github.com"
API_VERSION = "2026-03-10"
PENTASELF_MARKER = "<!-- penta-self-remediation:"
SELF_ROOT_MARKER = "<!-- penta-relationship-root:self-remediation -->"
CHILD_MARKER = "<!-- penta-development-child:pr-{pr_number} -->"

TERMINAL_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)\b",
    re.IGNORECASE,
)
TRACKING_RE = re.compile(r"\b(?:refs?|references?)\s*:?\s*#(\d+)\b", re.IGNORECASE)
PARENT_RE = re.compile(r"(?im)^\s*(?:parent|parent issue)\s*:?\s*#(\d+)\s*$")
BLOCKED_BY_RE = re.compile(r"(?im)^\s*blocked\s+by\s*:?\s*#(\d+)\s*$")
BLOCKS_RE = re.compile(r"(?im)^\s*blocks\s*:?\s*#(\d+)\s*$")


class GH:
    def __init__(self, repo: str, token: str | None = None) -> None:
        self.repo = repo
        self.token = token or os.environ.get("PENTA_PM_GITHUB_TOKEN") or os.environ["GITHUB_TOKEN"]

    def req(self, method: str, path: str, body: Any | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "CrownThrive-PentaPM-PR-Convergence/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"GitHub {method} {path} -> {exc.code}: {detail[:900]}") from exc

    def get(self, path: str) -> Any:
        return self.req("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def paginate(self, path: str, max_pages: int = 10) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        sep = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            batch = self.get(f"{path}{sep}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError(f"pagination_expected_list:{path}")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items


def issue_numbers(pattern: re.Pattern[str], body: str) -> list[int]:
    return list(dict.fromkeys(int(value) for value in pattern.findall(body or "")))


def label_names(item: dict[str, Any]) -> set[str]:
    labels = item.get("labels") or []
    return {
        str(label.get("name") if isinstance(label, dict) else label).strip().lower()
        for label in labels
        if str(label.get("name") if isinstance(label, dict) else label).strip()
    }


def governed(labels: set[str]) -> bool:
    return any(name.startswith(("penta:", "penta-")) for name in labels)


def replace_tracking_with_terminal(body: str, issue_number: int) -> str:
    pattern = re.compile(
        rf"\b(?:refs?|references?)\s*:?\s*#{issue_number}\b",
        re.IGNORECASE,
    )
    if pattern.search(body):
        return pattern.sub(f"Closes #{issue_number}", body, count=1)
    if TERMINAL_RE.search(body):
        return body
    return body.rstrip() + f"\n\nCloses #{issue_number}\n"


def ensure_labels(gh: GH, number: int, labels: set[str]) -> None:
    if labels:
        gh.post(f"/repos/{gh.repo}/issues/{number}/labels", {"labels": sorted(labels)})


def get_issue(gh: GH, number: int) -> dict[str, Any]:
    return gh.get(f"/repos/{gh.repo}/issues/{number}")


def get_pr_issue(gh: GH, number: int) -> dict[str, Any]:
    return gh.get(f"/repos/{gh.repo}/issues/{number}")


def current_parent(gh: GH, child_number: int) -> dict[str, Any] | None:
    try:
        return gh.get(f"/repos/{gh.repo}/issues/{child_number}/parent")
    except RuntimeError as exc:
        if "404" in str(exc):
            return None
        raise


def ensure_sub_issue(gh: GH, parent_number: int, child: dict[str, Any]) -> bool:
    child_number = int(child["number"])
    if parent_number == child_number:
        return False
    parent = current_parent(gh, child_number)
    if parent and int(parent.get("number") or 0) == parent_number:
        return False
    gh.post(
        f"/repos/{gh.repo}/issues/{parent_number}/sub_issues",
        {"sub_issue_id": int(child["id"]), "replace_parent": bool(parent)},
    )
    return True


def ensure_blocked_by(gh: GH, issue_number: int, blocker: dict[str, Any]) -> bool:
    existing = gh.get(f"/repos/{gh.repo}/issues/{issue_number}/dependencies/blocked_by?per_page=100")
    existing_ids = {int(item["id"]) for item in existing}
    blocker_id = int(blocker["id"])
    if blocker_id in existing_ids:
        return False
    gh.post(
        f"/repos/{gh.repo}/issues/{issue_number}/dependencies/blocked_by",
        {"issue_id": blocker_id},
    )
    return True


def ensure_self_root(gh: GH) -> dict[str, Any]:
    for issue in gh.paginate(f"/repos/{gh.repo}/issues?state=open"):
        if "pull_request" in issue:
            continue
        if SELF_ROOT_MARKER in str(issue.get("body") or ""):
            return issue
    body = (
        f"{SELF_ROOT_MARKER}\n\n"
        "Operational parent for live PentaSELF remediation findings. "
        "PentaSELF creates durable findings, PentaPR creates repair PRs, "
        "PentaPM owns assignment/reassignment and metadata convergence, and "
        "PentaSELF/PentaCertify evidence gates remain authoritative before merge.\n\n"
        "This issue is an organizational relationship root; it does not assert "
        "that any child finding is resolved."
    )
    issue = gh.post(
        f"/repos/{gh.repo}/issues",
        {
            "title": "[PentaPM] PentaSELF production remediation queue",
            "body": body,
        },
    )
    ensure_labels(
        gh,
        int(issue["number"]),
        {
            "penta:pm",
            "penta:self",
            "penta:relationship-root",
            "penta:continuity",
            "penta:entity:issue",
        },
    )
    return issue


def find_child_for_pr(gh: GH, pr_number: int) -> dict[str, Any] | None:
    marker = CHILD_MARKER.format(pr_number=pr_number)
    for issue in gh.paginate(f"/repos/{gh.repo}/issues?state=all"):
        if "pull_request" in issue:
            continue
        if marker in str(issue.get("body") or ""):
            return issue
    return None


def ensure_pr_child(
    gh: GH,
    pr: dict[str, Any],
    parent_issue: dict[str, Any],
    pr_labels: set[str],
) -> dict[str, Any]:
    pr_number = int(pr["number"])
    child = find_child_for_pr(gh, pr_number)
    marker = CHILD_MARKER.format(pr_number=pr_number)
    title = f"[PentaDevelopment] PR #{pr_number}: {str(pr.get('title') or '')[:105]}"
    body = (
        f"{marker}\n\n"
        f"Parent work: #{parent_issue['number']}\n"
        f"Development PR: #{pr_number}\n\n"
        "This child issue is the terminal unit for this PR. PentaDevelopment "
        "may close this child when the governed PR merges; the umbrella parent "
        "remains referenced for multi-PR completion tracking."
    )
    if child is None:
        child = gh.post(f"/repos/{gh.repo}/issues", {"title": title, "body": body})
    else:
        child = gh.patch(
            f"/repos/{gh.repo}/issues/{child['number']}",
            {"title": title, "body": body},
        )
    inherited = {
        name
        for name in pr_labels
        if name.startswith(("penta:lane:", "penta:risk:", "penta:authority:", "penta:stage:"))
    }
    ensure_labels(
        gh,
        int(child["number"]),
        inherited
        | {
            "penta:development",
            "penta:issues",
            "penta:pm",
            "penta:entity:issue",
        },
    )
    ensure_sub_issue(gh, int(parent_issue["number"]), child)
    return child


def apply_explicit_relationships(gh: GH, issue: dict[str, Any]) -> int:
    body = str(issue.get("body") or "")
    changed = 0
    for parent_number in issue_numbers(PARENT_RE, body):
        changed += int(ensure_sub_issue(gh, parent_number, issue))
    for blocker_number in issue_numbers(BLOCKED_BY_RE, body):
        changed += int(ensure_blocked_by(gh, int(issue["number"]), get_issue(gh, blocker_number)))
    for blocked_number in issue_numbers(BLOCKS_RE, body):
        changed += int(ensure_blocked_by(gh, blocked_number, issue))
    return changed


def converge_pr(gh: GH, pr_number: int, *, apply: bool) -> dict[str, Any]:
    pr = gh.get(f"/repos/{gh.repo}/pulls/{pr_number}")
    pr_issue = get_pr_issue(gh, pr_number)
    labels = label_names(pr_issue)
    body = str(pr.get("body") or "")
    result: dict[str, Any] = {
        "pr": pr_number,
        "governed": governed(labels),
        "mode": "apply" if apply else "audit",
        "development_action": "none",
        "relationship_changes": 0,
    }
    if not result["governed"]:
        return result

    terminal = issue_numbers(TERMINAL_RE, body)
    tracking = issue_numbers(TRACKING_RE, body)
    refs = list(dict.fromkeys(terminal + tracking))
    if not refs:
        result["development_action"] = "missing-reference"
        return result

    source = get_issue(gh, refs[0])
    result["relationship_changes"] += apply_explicit_relationships(gh, source) if apply else 0

    if PENTASELF_MARKER in body:
        result["relationship_kind"] = "pentaself-root"
        if apply:
            root = ensure_self_root(gh)
            result["relationship_changes"] += int(ensure_sub_issue(gh, int(root["number"]), source))
            result["relationship_root"] = int(root["number"])
        if not terminal:
            result["development_action"] = f"promote-to-closes:{source['number']}"
            if apply:
                new_body = replace_tracking_with_terminal(body, int(source["number"]))
                gh.patch(f"/repos/{gh.repo}/pulls/{pr_number}", {"body": new_body})
        else:
            result["development_action"] = "terminal-link-present"
        return result

    if terminal:
        result["development_action"] = "terminal-link-present"
        return result

    # Tracking-only references mean the PR is not allowed to close the umbrella
    # issue. Create a PR-scoped child issue and close that child instead.
    result["development_action"] = f"create-or-reuse-child-under:{source['number']}"
    if apply:
        child = ensure_pr_child(gh, pr, source, labels)
        result["child_issue"] = int(child["number"])
        new_body = body.rstrip() + f"\n\nCloses #{child['number']}\n"
        gh.patch(f"/repos/{gh.repo}/pulls/{pr_number}", {"body": new_body})
    return result


def open_governed_pr_numbers(gh: GH) -> list[int]:
    pulls = gh.paginate(f"/repos/{gh.repo}/pulls?state=open")
    numbers: list[int] = []
    for pr in pulls:
        issue = get_pr_issue(gh, int(pr["number"]))
        if governed(label_names(issue)):
            numbers.append(int(pr["number"]))
    return numbers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--all-open", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")
    if not args.pr and not args.all_open:
        raise SystemExit("one of --pr or --all-open is required")

    gh = GH(args.repo)
    numbers = [args.pr] if args.pr else open_governed_pr_numbers(gh)
    results = [converge_pr(gh, int(number), apply=args.apply) for number in numbers if number]
    print(json.dumps({"schema": "ct.penta.pm.pr-convergence.v1", "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
