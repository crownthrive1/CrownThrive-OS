#!/usr/bin/env python3
"""PentaVergence repository worker.

The worker is intentionally preservation-first. It only mutates a PR when the
current repository evidence makes the action reversible and unambiguous:

* close when the PR contributes zero unique commits relative to main;
* merge only when exact-head checks are green, the Governed Merge Gate passed,
  the PR is current with main, mergeable, non-draft and contains no HOLD marker;
* otherwise emit repair/restack/preserve dispositions.

GitHub provider throttling is evidence unavailability, not repository failure.
A provider rate limit therefore produces an OBSERVE_RATE_LIMIT disposition and
never authorizes merge/close mutation. Missing evidence is never treated as PASS.

It never force-pushes, deletes branches, manufactures reviews, bypasses a gate,
or treats missing evidence as PASS.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

API = "https://api.github.com"
HOLD_MARKERS = (
    "draft/hold",
    "draft / hold",
    "hold —",
    "hold -",
    "merge_authorized: false",
    "merge authorized: false",
    "not approved",
    "must not merge",
    "independent review",
)
PASS_CONCLUSIONS = {"success", "neutral", "skipped"}


class GitHubRateLimit(RuntimeError):
    """GitHub provider quota prevented an authoritative read."""

    def __init__(self, method: str, path: str, status: int, detail: str, reset_epoch: int | None = None) -> None:
        self.method = method
        self.path = path
        self.status = status
        self.detail = detail
        self.reset_epoch = reset_epoch
        reset_text = f"; reset_epoch={reset_epoch}" if reset_epoch is not None else ""
        super().__init__(f"GitHub {method} {path} -> {status}: provider rate limit{reset_text}")

    def evidence(self) -> dict[str, Any]:
        now = int(time.time())
        retry_after = max(0, self.reset_epoch - now) if self.reset_epoch is not None else None
        return {
            "provider": "github",
            "state": "RATE_LIMITED",
            "http_status": self.status,
            "method": self.method,
            "path": self.path,
            "reset_epoch": self.reset_epoch,
            "retry_after_seconds": retry_after,
            "authority_effect": "none",
            "mutation_allowed": False,
        }


class GitHub:
    def __init__(self, repo: str, token: str) -> None:
        self.repo = repo
        self.token = token
        self._compare_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._checks_cache: dict[str, list[dict[str, Any]]] = {}
        self._pr_cache: dict[int, dict[str, Any]] = {}

    @staticmethod
    def _reset_epoch(headers: Any) -> int | None:
        try:
            value = headers.get("X-RateLimit-Reset") if headers is not None else None
            return int(value) if value else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_rate_limit(exc: urllib.error.HTTPError, detail: str) -> bool:
        lower = detail.lower()
        headers = exc.headers
        remaining = headers.get("X-RateLimit-Remaining") if headers is not None else None
        retry_after = headers.get("Retry-After") if headers is not None else None
        return (
            exc.code == 429
            or remaining == "0"
            or retry_after is not None
            or "rate limit exceeded" in lower
            or "secondary rate limit" in lower
            or "abuse detection mechanism" in lower
        )

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        url = f"{API}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            if self._is_rate_limit(exc, detail):
                raise GitHubRateLimit(method, path, exc.code, detail[:800], self._reset_epoch(exc.headers)) from exc
            raise RuntimeError(f"GitHub {method} {path} -> {exc.code}: {detail[:800]}") from exc

    def open_prs(self) -> list[dict[str, Any]]:
        return self.request("GET", f"/repos/{self.repo}/pulls?state=open&per_page=100&sort=updated&direction=asc")

    def compare(self, base: str, head: str) -> dict[str, Any]:
        cache_key = (base, head)
        if cache_key not in self._compare_cache:
            base_q = urllib.parse.quote(base, safe="")
            head_q = urllib.parse.quote(head, safe="")
            self._compare_cache[cache_key] = self.request("GET", f"/repos/{self.repo}/compare/{base_q}...{head_q}")
        return self._compare_cache[cache_key]

    def checks(self, sha: str) -> list[dict[str, Any]]:
        if sha not in self._checks_cache:
            payload = self.request("GET", f"/repos/{self.repo}/commits/{sha}/check-runs?per_page=100")
            self._checks_cache[sha] = payload.get("check_runs", []) if isinstance(payload, dict) else []
        return self._checks_cache[sha]

    def pr_detail(self, number: int) -> dict[str, Any]:
        if number not in self._pr_cache:
            self._pr_cache[number] = self.request("GET", f"/repos/{self.repo}/pulls/{number}")
        return self._pr_cache[number]

    def close_pr(self, number: int) -> None:
        self.request("PATCH", f"/repos/{self.repo}/pulls/{number}", {"state": "closed"})

    def merge_pr(self, number: int, sha: str) -> dict[str, Any]:
        return self.request(
            "PUT",
            f"/repos/{self.repo}/pulls/{number}/merge",
            {"sha": sha, "merge_method": "merge", "commit_title": f"PentaVergence: merge PR #{number}"},
        )


@dataclass
class Decision:
    number: int
    title: str
    head_sha: str
    disposition: str
    reasons: list[str]
    mutation: str | None = None
    mutation_result: str | None = None
    provider_evidence: dict[str, Any] | None = None


def is_hold(pr: dict[str, Any]) -> bool:
    text = f"{pr.get('title', '')}\n{pr.get('body') or ''}".lower()
    return bool(pr.get("draft")) or any(marker in text for marker in HOLD_MARKERS)


def rate_limited_decision(number: int, title: str, head_sha: str, exc: GitHubRateLimit) -> Decision:
    return Decision(
        number,
        title,
        head_sha,
        "OBSERVE_RATE_LIMIT",
        ["GitHub provider rate limit prevented authoritative readback; no mutation authorized"],
        provider_evidence=exc.evidence(),
    )


def classify(gh: GitHub, pr: dict[str, Any]) -> Decision:
    number = int(pr["number"])
    title = str(pr.get("title") or "")
    head_sha = str(pr["head"]["sha"])

    if is_hold(pr):
        return Decision(number, title, head_sha, "PRESERVE_HOLD", ["draft or explicit governance/HOLD marker"])

    try:
        cmp = gh.compare(pr["base"]["sha"], head_sha)
    except GitHubRateLimit as exc:
        return rate_limited_decision(number, title, head_sha, exc)

    ahead = int(cmp.get("ahead_by", 0))
    behind = int(cmp.get("behind_by", 0))

    if ahead == 0:
        return Decision(number, title, head_sha, "CLOSE_REPRESENTED", ["head has zero unique commits relative to base/main"])

    try:
        checks = gh.checks(head_sha)
    except GitHubRateLimit as exc:
        return rate_limited_decision(number, title, head_sha, exc)

    completed = [c for c in checks if c.get("status") == "completed"]
    failed = [c for c in completed if str(c.get("conclusion") or "").lower() not in PASS_CONCLUSIONS]
    governed = [c for c in completed if "governed merge gate" in str(c.get("name") or "").lower()]

    if failed:
        return Decision(number, title, head_sha, "REPAIR_REQUIRED", [f"{len(failed)} exact-head check(s) are not passing"])

    if behind > 0:
        return Decision(number, title, head_sha, "RESTACK_REQUIRED", [f"branch is {behind} commit(s) behind base"])

    mergeable = pr.get("mergeable")
    # List-pulls may omit mergeability; fetch exact PR if needed.
    if mergeable is None:
        try:
            detail = gh.pr_detail(number)
        except GitHubRateLimit as exc:
            return rate_limited_decision(number, title, head_sha, exc)
        mergeable = detail.get("mergeable")

    governed_pass = any(str(c.get("conclusion") or "").lower() in PASS_CONCLUSIONS for c in governed)
    pending = [c for c in checks if c.get("status") != "completed"]

    if mergeable is True and governed_pass and not pending:
        return Decision(number, title, head_sha, "MERGE_CANDIDATE", ["mergeable", "current with base", "Governed Merge Gate passed", "all observed checks completed"])

    reasons = []
    if not governed_pass:
        reasons.append("no exact-head successful Governed Merge Gate")
    if pending:
        reasons.append(f"{len(pending)} check(s) still pending")
    if mergeable is not True:
        reasons.append("mergeability not proven true")
    return Decision(number, title, head_sha, "OBSERVE", reasons or ["insufficient mutation evidence"])


def reconcile(repo: str, token: str, apply: bool, max_mutations: int) -> dict[str, Any]:
    gh = GitHub(repo, token)
    decisions: list[Decision] = []
    mutations = 0
    worker_state = "COMPLETE"
    provider_evidence: dict[str, Any] | None = None

    try:
        prs = gh.open_prs()
    except GitHubRateLimit as exc:
        worker_state = "OBSERVE_RATE_LIMIT"
        provider_evidence = exc.evidence()
        prs = []

    for pr in prs:
        d = classify(gh, pr)
        if d.disposition == "OBSERVE_RATE_LIMIT":
            worker_state = "OBSERVE_RATE_LIMIT"
            provider_evidence = provider_evidence or d.provider_evidence
        if apply and mutations < max_mutations:
            if d.disposition == "CLOSE_REPRESENTED":
                gh.close_pr(d.number)
                d.mutation = "close"
                d.mutation_result = "closed"
                mutations += 1
            elif d.disposition == "MERGE_CANDIDATE":
                result = gh.merge_pr(d.number, d.head_sha)
                d.mutation = "merge"
                d.mutation_result = "merged" if result.get("merged") else str(result.get("message") or "merge_not_completed")
                if result.get("merged"):
                    mutations += 1
        decisions.append(d)

    summary: dict[str, int] = {}
    for d in decisions:
        summary[d.disposition] = summary.get(d.disposition, 0) + 1
    if worker_state == "OBSERVE_RATE_LIMIT":
        summary["OBSERVE_RATE_LIMIT"] = max(1, summary.get("OBSERVE_RATE_LIMIT", 0))
    return {
        "contract": "ct.penta.vergence.repository-report.v2",
        "repository": repo,
        "apply": apply,
        "worker_state": worker_state,
        "mutations": mutations,
        "summary": summary,
        "provider_evidence": provider_evidence,
        "decisions": [asdict(d) for d in decisions],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-mutations", type=int, default=10)
    parser.add_argument("--output", default="penta-vergence-report.json")
    args = parser.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not args.repo or not token:
        raise SystemExit("repository and GH_TOKEN/GITHUB_TOKEN are required")

    report = reconcile(args.repo, token, args.apply, max(0, args.max_mutations))
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"repository": report["repository"], "worker_state": report["worker_state"], "summary": report["summary"], "mutations": report["mutations"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
