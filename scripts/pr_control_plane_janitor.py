#!/usr/bin/env python3
"""Evidence-preserving cleanup for generated GitHub branch namespaces.

The janitor deletes a branch ref only when all of the following are true:
- the branch matches an explicitly managed generated namespace;
- it is not protected and is not covered by a preserve pattern;
- it is not the head or base of any open pull request;
- its tip is already an ancestor of protected main, so deleting the ref cannot
  remove unique source work from repository history;
- its namespace-specific retention window has elapsed.

Closed-but-unmerged branches are intentionally retained because their tips may
contain unique engineering work. Deleting a ref never rewrites commits or PR
history. The default mode is audit; apply mode is bounded by --max-delete.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config/pr_control_plane_janitor.json"
API_VERSION = "2022-11-28"
USER_AGENT = "CrownThrive-PR-Control-Plane-Janitor/1.0"
MAX_PAGINATION_PAGES = 100


class JanitorError(RuntimeError):
    pass


def load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JanitorError(f"invalid janitor policy: {path}") from exc
    if value.get("schema") != "ct.github.pr-control-plane-janitor/v1":
        raise JanitorError("unsupported janitor policy schema")
    managed = value.get("managed_patterns")
    if not isinstance(managed, list) or not managed:
        raise JanitorError("managed_patterns must be a non-empty list")
    for item in managed:
        if not isinstance(item, dict) or not str(item.get("pattern", "")).strip():
            raise JanitorError("every managed pattern requires a pattern")
        if float(item.get("min_age_hours", -1)) < 0:
            raise JanitorError("min_age_hours cannot be negative")
    return value


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise JanitorError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def is_ancestor(repo: Path, ancestor_ref: str, descendant_ref: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor_ref, descendant_ref],
        cwd=repo,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def matching_rule(name: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    matches = [
        item for item in policy.get("managed_patterns", [])
        if fnmatch.fnmatch(name, str(item.get("pattern")))
    ]
    if not matches:
        return None
    # Prefer the most specific rule if policy patterns overlap.
    return max(matches, key=lambda item: len(str(item.get("pattern", ""))))


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(name, str(pattern)) for pattern in patterns)


def classify_branch(
    *,
    name: str,
    protected: bool,
    active_pr_refs: set[str],
    merged_into_main: bool,
    age_hours: float,
    policy: dict[str, Any],
    execution_branch: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "eligible": False,
        "reason": "unclassified",
        "age_hours": round(age_hours, 2),
    }
    if protected:
        row["reason"] = "protected_branch"
        return row
    if execution_branch and name == execution_branch:
        row["reason"] = "current_execution_branch"
        return row
    if matches_any(name, policy.get("preserve_patterns", [])):
        row["reason"] = "preserve_pattern"
        return row
    rule = matching_rule(name, policy)
    if rule is None:
        row["reason"] = "outside_managed_generated_namespaces"
        return row
    row["managed_pattern"] = rule["pattern"]
    row["managed_reason"] = rule.get("reason")
    if name in active_pr_refs:
        row["reason"] = "open_pr_head_or_base"
        return row
    if not merged_into_main:
        row["reason"] = "unique_tip_not_merged_into_main"
        return row
    minimum = float(rule.get("min_age_hours", 0))
    row["min_age_hours"] = minimum
    if age_hours < minimum:
        row["reason"] = "retention_window_active"
        return row
    row["eligible"] = True
    row["reason"] = "safe_generated_ref_already_preserved_on_main"
    return row


def api_request(
    *,
    repo_full_name: str,
    token: str,
    path: str,
    method: str = "GET",
) -> tuple[Any | None, dict[str, str], int]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo_full_name}{path}",
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            body = json.loads(raw.decode("utf-8")) if raw else None
            return body, dict(response.headers.items()), response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise JanitorError(f"GitHub API {method} {path} failed {exc.code}: {detail[:800]}") from exc


def pagination_request_paths(path: str) -> tuple[str, list[tuple[str, str]], int, int]:
    """Normalize a repository-relative list endpoint for deterministic paging.

    GitHub may emit absolute Link targets using its numeric ``/repositories/{id}``
    canonical form even when the request entered through ``/repos/{owner}/{repo}``.
    Those provider-generated URLs are valid but are intentionally not trusted as
    future request authority. We instead retain the caller's already-bounded
    repository-relative endpoint and advance only the integer ``page`` parameter.
    """
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        raise JanitorError("pagination path must remain repository-relative")
    if parsed.fragment:
        raise JanitorError("pagination path fragments are not supported")

    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    base_pairs: list[tuple[str, str]] = []
    page = 1
    per_page = 100
    seen_page = False
    seen_per_page = False
    for key, value in pairs:
        if key == "page":
            if seen_page:
                raise JanitorError("duplicate pagination page parameter")
            seen_page = True
            try:
                page = int(value)
            except ValueError as exc:
                raise JanitorError("pagination page must be an integer") from exc
            continue
        if key == "per_page":
            if seen_per_page:
                raise JanitorError("duplicate pagination per_page parameter")
            seen_per_page = True
            try:
                per_page = int(value)
            except ValueError as exc:
                raise JanitorError("pagination per_page must be an integer") from exc
            continue
        base_pairs.append((key, value))

    if page < 1:
        raise JanitorError("pagination page must be positive")
    if per_page < 1 or per_page > 100:
        raise JanitorError("pagination per_page must be between 1 and 100")
    return parsed.path, base_pairs, page, per_page


def paged_path(
    endpoint: str,
    base_pairs: list[tuple[str, str]],
    page: int,
    per_page: int,
) -> str:
    query = urllib.parse.urlencode([
        *base_pairs,
        ("per_page", str(per_page)),
        ("page", str(page)),
    ])
    return f"{endpoint}?{query}" if query else endpoint


def paginate(repo_full_name: str, token: str, path: str) -> list[dict[str, Any]]:
    """Read every list page without following provider-supplied absolute URLs."""
    endpoint, base_pairs, page, per_page = pagination_request_paths(path)
    rows: list[dict[str, Any]] = []
    pages_read = 0
    while True:
        if pages_read >= MAX_PAGINATION_PAGES:
            raise JanitorError(
                f"pagination exceeded bounded page cap ({MAX_PAGINATION_PAGES}) for {endpoint}"
            )
        request_path = paged_path(endpoint, base_pairs, page, per_page)
        body, _, _ = api_request(
            repo_full_name=repo_full_name,
            token=token,
            path=request_path,
        )
        if not isinstance(body, list):
            raise JanitorError(f"expected list response from {request_path}")
        rows.extend(item for item in body if isinstance(item, dict))
        pages_read += 1
        if len(body) < per_page:
            break
        page += 1
    return rows


def open_pr_refs(repo_full_name: str, token: str) -> set[str]:
    pulls = paginate(repo_full_name, token, "/pulls?state=open&per_page=100")
    refs: set[str] = set()
    for pull in pulls:
        base = pull.get("base") or {}
        head = pull.get("head") or {}
        base_ref = str(base.get("ref") or "").strip()
        if base_ref:
            refs.add(base_ref)
        head_repo = (head.get("repo") or {}).get("full_name")
        head_ref = str(head.get("ref") or "").strip()
        if head_ref and head_repo == repo_full_name:
            refs.add(head_ref)
    return refs


def branch_rows(repo_full_name: str, token: str) -> list[dict[str, Any]]:
    return paginate(repo_full_name, token, "/branches?per_page=100")


def remote_ref(name: str) -> str:
    return f"refs/remotes/origin/{name}"


def tip_age_hours(repo: Path, ref: str, now_epoch: float) -> float:
    raw = git(repo, "show", "-s", "--format=%ct", ref)
    try:
        timestamp = float(raw)
    except ValueError as exc:
        raise JanitorError(f"invalid commit timestamp for {ref}: {raw}") from exc
    return max(0.0, (now_epoch - timestamp) / 3600.0)


def delete_branch(repo_full_name: str, token: str, name: str) -> None:
    encoded = urllib.parse.quote(name, safe="/")
    _, _, status = api_request(
        repo_full_name=repo_full_name,
        token=token,
        path=f"/git/refs/heads/{encoded}",
        method="DELETE",
    )
    if status not in {200, 204}:
        raise JanitorError(f"unexpected delete status {status} for {name}")


def run(
    *,
    repo: Path,
    repo_full_name: str,
    token: str,
    policy: dict[str, Any],
    mode: str,
    max_delete: int,
    execution_branch: str | None,
) -> dict[str, Any]:
    if mode not in {"audit", "apply"}:
        raise JanitorError("mode must be audit or apply")
    if max_delete < 0:
        raise JanitorError("max_delete cannot be negative")

    main_branch = str(policy.get("main_branch", "main"))
    main_ref = remote_ref(main_branch)
    git(repo, "cat-file", "-e", f"{main_ref}^{{commit}}")
    active_refs = open_pr_refs(repo_full_name, token)
    branches = branch_rows(repo_full_name, token)
    now = dt.datetime.now(dt.timezone.utc)
    now_epoch = now.timestamp()
    rows: list[dict[str, Any]] = []

    for branch in branches:
        name = str(branch.get("name") or "").strip()
        if not name:
            continue
        ref = remote_ref(name)
        ref_exists = subprocess.run(
            ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
            cwd=repo,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if not ref_exists:
            rows.append({
                "name": name,
                "eligible": False,
                "reason": "remote_ref_missing_from_checkout",
                "protected": bool(branch.get("protected", False)),
            })
            continue
        row = classify_branch(
            name=name,
            protected=bool(branch.get("protected", False)),
            active_pr_refs=active_refs,
            merged_into_main=is_ancestor(repo, ref, main_ref),
            age_hours=tip_age_hours(repo, ref, now_epoch),
            policy=policy,
            execution_branch=execution_branch,
        )
        row["protected"] = bool(branch.get("protected", False))
        row["tip_sha"] = str((branch.get("commit") or {}).get("sha") or "")
        rows.append(row)

    eligible = sorted(
        (row for row in rows if row.get("eligible")),
        key=lambda row: (-float(row.get("age_hours", 0)), str(row.get("name"))),
    )
    attempted = eligible[:max_delete] if mode == "apply" else []
    deleted: list[str] = []
    failures: list[dict[str, str]] = []
    if mode == "apply":
        for row in attempted:
            name = str(row["name"])
            try:
                delete_branch(repo_full_name, token, name)
                deleted.append(name)
                row["action"] = "deleted_ref"
            except JanitorError as exc:
                row["action"] = "delete_failed"
                failures.append({"name": name, "error": str(exc)})
        for row in eligible[max_delete:]:
            row["action"] = "eligible_over_run_cap"

    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1

    return {
        "schema": "ct.github.pr-control-plane-janitor-report/v1",
        "policy_version": policy.get("version"),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "repository": repo_full_name,
        "main_branch": main_branch,
        "mode": mode,
        "max_delete": max_delete,
        "branches_scanned": len(rows),
        "open_pr_refs_preserved": len(active_refs),
        "eligible": len(eligible),
        "attempted": len(attempted),
        "deleted": len(deleted),
        "deleted_refs": deleted,
        "failures": failures,
        "reason_counts": dict(sorted(counts.items())),
        "rows": rows,
        "history_rewritten": False,
        "unique_unmerged_work_deleted": False,
        "authority_expansion": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS"))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--mode", choices=("audit", "apply"), default="audit")
    parser.add_argument("--max-delete", type=int)
    parser.add_argument("--report", default="/tmp/pr-control-plane-janitor-report.json")
    parser.add_argument("--execution-branch", default=os.environ.get("GITHUB_REF_NAME"))
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise SystemExit("PR_CONTROL_PLANE_JANITOR_HOLD: GITHUB_TOKEN is required")
    try:
        policy = load_policy(Path(args.policy).resolve())
        max_delete = args.max_delete
        if max_delete is None:
            max_delete = int(policy.get("default_max_delete", 75))
        result = run(
            repo=Path(args.repo_root).resolve(),
            repo_full_name=args.repository,
            token=token,
            policy=policy,
            mode=args.mode,
            max_delete=max_delete,
            execution_branch=args.execution_branch,
        )
    except JanitorError as exc:
        print(f"PR_CONTROL_PLANE_JANITOR_HOLD: {exc}", file=sys.stderr)
        return 2

    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        key: result[key]
        for key in (
            "schema", "repository", "mode", "branches_scanned", "eligible",
            "attempted", "deleted", "open_pr_refs_preserved", "reason_counts"
        )
    }, indent=2, sort_keys=True))
    if result["failures"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
