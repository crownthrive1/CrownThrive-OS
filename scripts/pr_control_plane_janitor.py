#!/usr/bin/env python3
"""Evidence-preserving cleanup for generated GitHub branch namespaces.

Generated refs are retired only when the underlying history is already durable:
- merged tips may be deleted because they are reachable from protected main;
- unique generated tips may be deleted only after an archive anchor is created
  with the exact tip commits as parents and the archive ref is read back;
- protected, preserved, active-PR, current-execution, unmanaged, and young refs
  are never deleted.

Archive anchors use the protected-main tree and add history reachability only.
They never merge archived source into main, never rewrite PR/commit history, and
remain under the preserved ``archive/*`` namespace. Default mode is audit;
apply mode is bounded by ``--max-delete``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import fnmatch
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
from typing import Any, Iterable, Iterator
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config/pr_control_plane_janitor.json"
API_VERSION = "2022-11-28"
USER_AGENT = "CrownThrive-PR-Control-Plane-Janitor/1.3"
MAX_PAGINATION_PAGES = 100
ARCHIVE_PARENT_CHUNK = 24
MAX_API_ATTEMPTS = 3
MAX_RETRY_DELAY_SECONDS = 60.0


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
        "archive_eligible": False,
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

    minimum = float(rule.get("min_age_hours", 0))
    row["min_age_hours"] = minimum
    if age_hours < minimum:
        row["reason"] = "retention_window_active"
        return row

    if merged_into_main:
        row["eligible"] = True
        row["reason"] = "safe_generated_ref_already_preserved_on_main"
        return row

    # A managed, aged, inactive unique tip is a cleanup candidate only after an
    # archive anchor makes the exact commit graph durably reachable.
    row["archive_eligible"] = True
    row["reason"] = "safe_archive_required_for_unique_generated_tip"
    return row


def retry_delay_seconds(
    headers: dict[str, str],
    *,
    now_epoch: float | None = None,
    jitter_seconds: float = 0.0,
) -> float:
    """Resolve a bounded provider-requested rate-limit delay."""
    normalized = {str(key).lower(): str(value) for key, value in headers.items()}
    now = time.time() if now_epoch is None else now_epoch
    candidates: list[float] = []

    retry_after = normalized.get("retry-after", "").strip()
    if retry_after:
        try:
            candidates.append(float(retry_after))
        except ValueError:
            parsed = email.utils.parsedate_to_datetime(retry_after)
            if parsed is not None:
                candidates.append(parsed.timestamp() - now)

    reset = normalized.get("x-ratelimit-reset", "").strip()
    if reset:
        try:
            candidates.append(float(reset) - now)
        except ValueError:
            pass

    requested = max([1.0, *candidates]) + max(0.0, jitter_seconds)
    return min(MAX_RETRY_DELAY_SECONDS, requested)


def api_request(
    *,
    repo_full_name: str,
    token: str,
    path: str,
    method: str = "GET",
    payload: MappingLike | None = None,
) -> tuple[Any | None, dict[str, str], int]:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        data = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo_full_name}{path}",
            method=method,
            headers=headers,
            data=data,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                body = json.loads(raw.decode("utf-8")) if raw else None
                return body, dict(response.headers.items()), response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            response_headers = dict(exc.headers.items()) if exc.headers else {}
            normalized = {str(key).lower(): str(value) for key, value in response_headers.items()}
            rate_limited = (
                exc.code == 429
                or (
                    exc.code == 403
                    and (
                        normalized.get("x-ratelimit-remaining") == "0"
                        or "rate limit" in detail.lower()
                    )
                )
            )
            if rate_limited and attempt < MAX_API_ATTEMPTS:
                time.sleep(retry_delay_seconds(
                    response_headers,
                    jitter_seconds=random.uniform(0.0, 0.5),
                ))
                continue
            raise JanitorError(
                f"GitHub API {method} {path} failed {exc.code}: {detail[:800]}"
            ) from exc

    raise JanitorError(f"GitHub API {method} {path} exhausted bounded retries")


# Python 3.12-friendly structural alias without importing typing.Mapping twice.
MappingLike = dict[str, Any]


def pagination_request_paths(path: str) -> tuple[str, list[tuple[str, str]], int, int]:
    """Normalize a repository-relative list endpoint for deterministic paging."""
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


def chunks(values: list[dict[str, Any]], size: int = ARCHIVE_PARENT_CHUNK) -> Iterator[list[dict[str, Any]]]:
    if size < 1:
        raise JanitorError("archive parent chunk must be positive")
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def create_archive_anchor(
    *,
    repo: Path,
    repo_full_name: str,
    token: str,
    main_ref: str,
    candidates: list[dict[str, Any]],
    now: dt.datetime,
) -> dict[str, Any] | None:
    """Create a preserved reachability anchor for unique generated tips.

    Each anchor commit uses the exact protected-main tree. Candidate tip SHAs are
    parents only; therefore source files are not merged or projected into main.
    Chained anchor commits bound parent fan-out while retaining every candidate.
    The final archive branch is created only after every commit response matches
    the requested parent set, then read back exactly before deletion can begin.
    """
    if not candidates:
        return None

    main_sha = git(repo, "rev-parse", f"{main_ref}^{{commit}}")
    main_tree = git(repo, "rev-parse", f"{main_ref}^{{tree}}")
    current_parent = main_sha
    anchor_commits: list[str] = []
    anchored_tips: list[str] = []

    for index, group in enumerate(chunks(candidates), 1):
        tip_shas = [str(row.get("tip_sha") or "").strip() for row in group]
        if any(len(sha) != 40 for sha in tip_shas):
            raise JanitorError("archive candidate has malformed tip SHA")
        requested_parents = [current_parent, *tip_shas]
        body, _, status = api_request(
            repo_full_name=repo_full_name,
            token=token,
            path="/git/commits",
            method="POST",
            payload={
                "message": (
                    f"archive(generated-branches): preserve batch {index} before ref retirement\n\n"
                    "History-reachability anchor only. Tree is protected main; candidate tips are parents."
                ),
                "tree": main_tree,
                "parents": requested_parents,
            },
        )
        if status not in {200, 201} or not isinstance(body, dict):
            raise JanitorError(f"archive commit creation returned unexpected status {status}")
        created_sha = str(body.get("sha") or "").strip()
        observed_parents = [str((item or {}).get("sha") or "") for item in body.get("parents", [])]
        if len(created_sha) != 40 or observed_parents != requested_parents:
            raise JanitorError("archive commit readback did not preserve exact requested parents")
        if str((body.get("tree") or {}).get("sha") or "") != main_tree:
            raise JanitorError("archive commit tree drifted from protected main")
        anchor_commits.append(created_sha)
        anchored_tips.extend(tip_shas)
        current_parent = created_sha

    run_id = str(os.environ.get("GITHUB_RUN_ID") or int(now.timestamp()))
    attempt = str(os.environ.get("GITHUB_RUN_ATTEMPT") or "1")
    archive_branch = f"archive/generated-branches/{now:%Y%m%d}-{run_id}-{attempt}"
    body, _, status = api_request(
        repo_full_name=repo_full_name,
        token=token,
        path="/git/refs",
        method="POST",
        payload={"ref": f"refs/heads/{archive_branch}", "sha": current_parent},
    )
    if status not in {200, 201} or not isinstance(body, dict):
        raise JanitorError(f"archive ref creation returned unexpected status {status}")

    encoded = urllib.parse.quote(archive_branch, safe="/")
    readback, _, _ = api_request(
        repo_full_name=repo_full_name,
        token=token,
        path=f"/git/ref/heads/{encoded}",
    )
    observed = str(((readback or {}).get("object") or {}).get("sha") or "")
    if observed != current_parent:
        raise JanitorError("archive ref exact readback mismatch")

    return {
        "archive_branch": archive_branch,
        "archive_anchor_sha": current_parent,
        "archive_tree_sha": main_tree,
        "archive_commits": anchor_commits,
        "archived_tip_shas": anchored_tips,
        "archived_count": len(candidates),
        "exact_ref_readback": True,
        "source_tree_changed": False,
    }


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
                "archive_eligible": False,
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

    direct = [row for row in rows if row.get("eligible")]
    archive_required = [row for row in rows if row.get("archive_eligible")]
    deletion_candidates = sorted(
        [*direct, *archive_required],
        key=lambda row: (-float(row.get("age_hours", 0)), str(row.get("name"))),
    )
    attempted = deletion_candidates[:max_delete] if mode == "apply" else []
    attempted_archive = [row for row in attempted if row.get("archive_eligible")]
    attempted_direct = [row for row in attempted if row.get("eligible")]

    archive = None
    deleted: list[str] = []
    failures: list[dict[str, str]] = []
    if mode == "apply" and attempted_archive:
        # Archive all unique tips before deleting any ref in this wave. A HOLD
        # here means zero deletions have happened in this run.
        archive = create_archive_anchor(
            repo=repo,
            repo_full_name=repo_full_name,
            token=token,
            main_ref=main_ref,
            candidates=attempted_archive,
            now=now,
        )
        if archive is None or archive.get("exact_ref_readback") is not True:
            raise JanitorError("unique-tip archive did not complete exact readback")
        for row in attempted_archive:
            row["archive_branch"] = archive["archive_branch"]
            row["archive_anchor_sha"] = archive["archive_anchor_sha"]
            row["archived_before_delete"] = True

    if mode == "apply":
        for row in attempted:
            name = str(row["name"])
            if row.get("archive_eligible") and not row.get("archived_before_delete"):
                failures.append({"name": name, "error": "archive_readback_missing"})
                row["action"] = "delete_blocked_missing_archive"
                continue
            try:
                delete_branch(repo_full_name, token, name)
                deleted.append(name)
                row["action"] = "deleted_ref"
            except JanitorError as exc:
                row["action"] = "delete_failed"
                failures.append({"name": name, "error": str(exc)})
        for row in deletion_candidates[max_delete:]:
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
        "eligible": len(deletion_candidates),
        "direct_main_eligible": len(direct),
        "archive_required_eligible": len(archive_required),
        "attempted": len(attempted),
        "attempted_direct": len(attempted_direct),
        "attempted_archive": len(attempted_archive),
        "archive": archive,
        "deleted": len(deleted),
        "deleted_refs": deleted,
        "failures": failures,
        "reason_counts": dict(sorted(counts.items())),
        "rows": rows,
        "history_rewritten": False,
        "unique_unmerged_work_deleted": False,
        "archived_history_remains_reachable": bool(archive) if attempted_archive else True,
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
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
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
        hold = {
            "schema": "ct.github.pr-control-plane-janitor-report/v1",
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "repository": args.repository,
            "mode": args.mode,
            "state": "HOLD",
            "hold_reason": str(exc),
            "history_rewritten": False,
            "unique_unmerged_work_deleted": False,
            "authority_expansion": False,
        }
        report.write_text(json.dumps(hold, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"PR_CONTROL_PLANE_JANITOR_HOLD: {exc}", file=sys.stderr)
        return 2

    report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        key: result[key]
        for key in (
            "schema", "repository", "mode", "branches_scanned", "eligible",
            "direct_main_eligible", "archive_required_eligible", "attempted",
            "attempted_archive", "deleted", "open_pr_refs_preserved", "reason_counts"
        )
    }, indent=2, sort_keys=True))
    if result["failures"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
