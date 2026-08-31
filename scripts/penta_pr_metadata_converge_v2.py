#!/usr/bin/env python3
"""Canonical PR Development metadata convergence.

v2 rules:
- one PR-scoped Development issue maximum for each PR;
- never invent a parent/child pair for metadata-only work;
- adopt legacy Gate Awareness/PentaPM metadata issues instead of multiplying them;
- close recognized metadata-only duplicates only after a canonical issue is selected;
- when the referenced PR is terminal, close all recognized metadata-only units;
- never merge/close a PR and never manufacture governance evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

API = "https://api.github.com"
API_VERSION = "2022-11-28"
MARKER_TEMPLATE = "<!-- penta-development:pr-{number}:v2 -->"
OLD_CHILD_TEMPLATE = "<!-- penta-development-child:pr-{number} -->"

TERMINAL_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)\b",
    re.IGNORECASE,
)
DEV_PR_RE = re.compile(r"(?im)^\s*Development PR:\s*#(\d+)\s*$")

LEGACY_METADATA_PHRASES = (
    "Automatically created by Penta PR Gate Awareness",
    "PentaPM created this bounded metadata/evidence unit",
    "This child issue is the terminal unit for this PR",
)


class GH:
    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.token = (
            os.environ.get("PENTA_PM_GITHUB_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
            or ""
        )
        if not self.token:
            raise SystemExit("github_token_required")

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
                "User-Agent": "CrownThrive-PentaPR-Metadata-Convergence/2.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:700]}") from exc

    def get(self, path: str) -> Any:
        return self.req("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def paginate(self, path: str, max_pages: int = 20) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        sep = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            payload = self.get(f"{path}{sep}per_page=100&page={page}")
            if not isinstance(payload, list):
                raise RuntimeError(f"pagination_expected_list:{path}")
            items.extend(payload)
            if len(payload) < 100:
                break
        return items


def issue_labels(item: dict[str, Any]) -> set[str]:
    return {
        str(label.get("name") if isinstance(label, dict) else label).strip().lower()
        for label in (item.get("labels") or [])
        if str(label.get("name") if isinstance(label, dict) else label).strip()
    }


def governed_pr(issue_projection: dict[str, Any]) -> bool:
    return any(name.startswith(("penta:", "penta-")) for name in issue_labels(issue_projection))


def metadata_pr_number(issue: dict[str, Any]) -> int | None:
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    match = DEV_PR_RE.search(body)
    if not match or not title.startswith("[PentaDevelopment] PR #"):
        return None
    return int(match.group(1))


def recognized_metadata_only(issue: dict[str, Any], pr_number: int) -> bool:
    if metadata_pr_number(issue) != pr_number:
        return False
    body = str(issue.get("body") or "")
    marker = MARKER_TEMPLATE.format(number=pr_number)
    old_marker = OLD_CHILD_TEMPLATE.format(number=pr_number)
    return marker in body or old_marker in body or any(
        phrase in body for phrase in LEGACY_METADATA_PHRASES
    )


def referenced_numbers(body: str, pattern: re.Pattern[str]) -> list[int]:
    return list(dict.fromkeys(int(value) for value in pattern.findall(body or "")))


def choose_canonical(pr: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    number = int(pr["number"])
    body = str(pr.get("body") or "")
    terminal = set(referenced_numbers(body, TERMINAL_RE))
    marker = MARKER_TEMPLATE.format(number=number)
    old_marker = OLD_CHILD_TEMPLATE.format(number=number)

    terminal_matches = [item for item in candidates if int(item["number"]) in terminal]
    if len(terminal_matches) == 1:
        return terminal_matches[0]
    v2 = [item for item in candidates if marker in str(item.get("body") or "")]
    if v2:
        return sorted(v2, key=lambda item: int(item["number"]))[0]
    old = [item for item in candidates if old_marker in str(item.get("body") or "")]
    if old:
        return sorted(old, key=lambda item: int(item["number"]))[0]
    penta_pm = [
        item
        for item in candidates
        if "PentaPM created this bounded metadata/evidence unit" in str(item.get("body") or "")
    ]
    if penta_pm:
        return sorted(penta_pm, key=lambda item: int(item["number"]))[0]
    return sorted(candidates, key=lambda item: int(item["number"]))[0]


def canonical_body(pr: dict[str, Any], issue: dict[str, Any]) -> str:
    number = int(pr["number"])
    return (
        f"{MARKER_TEMPLATE.format(number=number)}\n\n"
        f"Development PR: #{number}\n"
        "Relationship: canonical PR-scoped Development metadata unit\n\n"
        "This issue is the single GitHub Development/metadata unit for the PR. "
        "It does not represent independent engineering scope and creates no merge, "
        "release, provider, financial, rights, credential, certification, or D3 authority. "
        "Historical duplicate metadata issues may be closed as duplicates while their history remains preserved.\n\n"
        f"Canonicalized from issue #{int(issue['number'])}."
    )


def create_canonical(gh: GH, pr: dict[str, Any]) -> dict[str, Any]:
    number = int(pr["number"])
    title = f"[PentaDevelopment] PR #{number}: {str(pr.get('title') or '')[:105]}"
    return gh.post(
        f"/repos/{gh.repo}/issues",
        {
            "title": title,
            "body": (
                f"{MARKER_TEMPLATE.format(number=number)}\n\n"
                f"Development PR: #{number}\n"
                "Relationship: canonical PR-scoped Development metadata unit\n\n"
                "This issue is the single GitHub Development/metadata unit for the PR and is metadata/evidence routing only."
            ),
        },
    )


def ensure_pr_terminal_link(gh: GH, pr: dict[str, Any], canonical_number: int) -> bool:
    body = str(pr.get("body") or "")
    terminal = set(referenced_numbers(body, TERMINAL_RE))
    if canonical_number in terminal:
        return False
    if terminal:
        return False
    new_body = body.rstrip() + f"\n\nCloses #{canonical_number}\n"
    gh.patch(f"/repos/{gh.repo}/pulls/{int(pr['number'])}", {"body": new_body})
    pr["body"] = new_body
    return True


def close_issue(gh: GH, number: int, *, duplicate: bool) -> None:
    gh.patch(
        f"/repos/{gh.repo}/issues/{number}",
        {"state": "closed", "state_reason": "duplicate" if duplicate else "completed"},
    )


@dataclass
class Result:
    pr: int
    state: str
    canonical_issue: int | None
    created: bool = False
    canonicalized: bool = False
    pr_body_linked: bool = False
    duplicates_closed: int = 0
    terminal_metadata_closed: int = 0
    skipped_reason: str | None = None

    def asdict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def converge_one(gh: GH, pr_number: int, *, all_issues: list[dict[str, Any]], apply: bool) -> Result:
    pr = gh.get(f"/repos/{gh.repo}/pulls/{pr_number}")
    pr_issue = gh.get(f"/repos/{gh.repo}/issues/{pr_number}")
    state = str(pr.get("state") or "unknown")
    result = Result(pr=pr_number, state=state, canonical_issue=None)

    if state == "open" and not governed_pr(pr_issue):
        result.skipped_reason = "not_governed"
        return result

    candidates = [issue for issue in all_issues if recognized_metadata_only(issue, pr_number)]
    canonical = choose_canonical(pr, candidates)

    if state != "open":
        if apply:
            for issue in candidates:
                if str(issue.get("state") or "").lower() == "open":
                    close_issue(
                        gh,
                        int(issue["number"]),
                        duplicate=canonical is not None and int(issue["number"]) != int(canonical["number"]),
                    )
                    result.terminal_metadata_closed += 1
        result.canonical_issue = int(canonical["number"]) if canonical else None
        return result

    if canonical is None:
        if not apply:
            result.skipped_reason = "would_create_canonical"
            return result
        canonical = create_canonical(gh, pr)
        all_issues.append(canonical)
        candidates.append(canonical)
        result.created = True

    canonical_number = int(canonical["number"])
    result.canonical_issue = canonical_number

    if apply:
        desired_body = canonical_body(pr, canonical)
        if str(canonical.get("body") or "") != desired_body:
            gh.patch(f"/repos/{gh.repo}/issues/{canonical_number}", {"body": desired_body})
            result.canonicalized = True
        result.pr_body_linked = ensure_pr_terminal_link(gh, pr, canonical_number)
        for issue in candidates:
            issue_number = int(issue["number"])
            if issue_number == canonical_number or str(issue.get("state") or "").lower() != "open":
                continue
            close_issue(gh, issue_number, duplicate=True)
            result.duplicates_closed += 1

    return result


def open_pr_numbers(gh: GH) -> list[int]:
    pulls = gh.paginate(f"/repos/{gh.repo}/pulls?state=open")
    return [int(item["number"]) for item in pulls]


def referenced_metadata_pr_numbers(all_issues: list[dict[str, Any]]) -> set[int]:
    result: set[int] = set()
    for issue in all_issues:
        number = metadata_pr_number(issue)
        if number is not None and recognized_metadata_only(issue, number):
            result.add(number)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("repo_required")
    if not args.pr and not args.all:
        raise SystemExit("one_of_pr_or_all_required")

    gh = GH(args.repo)
    all_issues = [
        item
        for item in gh.paginate(f"/repos/{gh.repo}/issues?state=all", max_pages=25)
        if "pull_request" not in item
    ]
    numbers = [args.pr] if args.pr else sorted(set(open_pr_numbers(gh)) | referenced_metadata_pr_numbers(all_issues))

    results: list[dict[str, Any]] = []
    for number in numbers:
        try:
            results.append(converge_one(gh, number, all_issues=all_issues, apply=args.apply).asdict())
        except RuntimeError as exc:
            results.append(Result(pr=number, state="ERROR", canonical_issue=None, skipped_reason=str(exc)).asdict())

    payload = {
        "schema": "ct.penta.pr-metadata-convergence.v2",
        "mode": "apply" if args.apply else "audit",
        "results": results,
        "summary": {
            "prs": len(results),
            "created": sum(int(item["created"]) for item in results),
            "canonicalized": sum(int(item["canonicalized"]) for item in results),
            "duplicates_closed": sum(int(item["duplicates_closed"]) for item in results),
            "terminal_metadata_closed": sum(int(item["terminal_metadata_closed"]) for item in results),
            "errors": sum(int(item["state"] == "ERROR") for item in results),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
