#!/usr/bin/env python3
"""Bounded, fail-closed CHLOM data-less replay custody loop.

The loop never mutates production. For each validation branch it:
1. resolves the exact Supabase preview and terminal migration state;
2. on MIGRATIONS_FAILED, extracts one concrete missing dependency;
3. finds exactly one earlier provider-applied migration that created/seeded it;
4. requires that Git currently represents that version only as a no-op marker;
5. verifies the provider body, scans for credential-like literals, restores it to Git;
6. creates a new immutable validation branch/PR and explicitly dispatches this workflow;
7. on MIGRATIONS_PASSED, performs an independent topology readback and advances the
   dependent Penta wave only to dependent validation.

Any ambiguity, unsupported failure class, source mismatch, write race, data-bearing
preview, or topology drift produces HOLD evidence and exits non-zero.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO = os.environ.get("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS")
PARENT_PROJECT = os.environ.get("PARENT_PROJECT_REF", "tzajnzshmtzjenqulehq")
REPAIR_BRANCH = os.environ.get(
    "REPAIR_BRANCH", "repair/chlom-framework-package-custody-v8-20260904"
)
VALIDATION_BRANCH = os.environ.get("GITHUB_REF_NAME", "")
SOURCE_HEAD = os.environ.get("GITHUB_SHA", "")
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
SUPABASE_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
WORKFLOW_FILE = ".github/workflows/chlom-replay-autoloop.yml"
RESULT_PATH = Path("/tmp/chlom_replay_autoloop_result.json")
MAX_CYCLES = 12

PROHIBITED = (
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"\bsk_(?:live|test)_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bsbp_[A-Za-z0-9_-]{12,}\b"),
    re.compile(rb"\bgh[opusr]_[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        rb"(?i)(?:password|api[_-]?key|access[_-]?token)\s*[:=]\s*'[^']{8,}'"
    ),
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hold(reason: str, **evidence: Any) -> None:
    payload = {
        "schema": "crownthrive.supabase.chlom-replay-autoloop/v1",
        "state": "HOLD",
        "reason": reason,
        "repository": REPO,
        "repair_branch": REPAIR_BRANCH,
        "validation_branch": VALIDATION_BRANCH,
        "validated_source_head_sha": SOURCE_HEAD,
        "production_history_mutated": False,
        "production_schema_mutated": False,
        "production_data_copied": False,
        "production_mutated": False,
        "dependent_penta_wave": "HOLD",
        "commercial_activation_authorized": False,
        "production_deployment_authorized": False,
        "stable_products_only": True,
        "observed_at_utc": now(),
        **evidence,
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    raise SystemExit(1)


def request_json(
    url: str,
    *,
    token: str,
    method: str = "GET",
    body: Any | None = None,
    accept: str = "application/json",
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "User-Agent": "CrownThrive-CHLOM-Replay-Autoloop/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read(1200).decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"request failed {method} {url}: {exc}") from exc


def gh(path: str, *, method: str = "GET", body: Any | None = None) -> Any:
    if not GH_TOKEN:
        hold("GITHUB_TOKEN_UNAVAILABLE")
    return request_json(
        f"https://api.github.com/repos/{REPO}/{path}",
        token=GH_TOKEN,
        method=method,
        body=body,
        accept="application/vnd.github+json",
    )


def supabase(path: str, *, method: str = "GET", body: Any | None = None) -> Any:
    if not SUPABASE_TOKEN:
        hold("SUPABASE_ACCESS_TOKEN_UNAVAILABLE")
    return request_json(
        f"https://api.supabase.com/v1/{path}",
        token=SUPABASE_TOKEN,
        method=method,
        body=body,
    )


def sql(project_ref: str, query: str) -> list[dict[str, Any]]:
    payload = supabase(
        f"projects/{project_ref}/database/query",
        method="POST",
        body={"query": query},
    )
    rows = payload if isinstance(payload, list) else payload.get("data", payload.get("result", []))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        hold("UNEXPECTED_DATABASE_QUERY_RESPONSE", project_ref=project_ref, response=payload)
    return rows


def flatten_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from flatten_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from flatten_strings(child)


def recursive_values(value: Any, names: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in names and child is not None:
                found.append(str(child))
            found.extend(recursive_values(child, names))
    elif isinstance(value, list):
        for child in value:
            found.extend(recursive_values(child, names))
    return found


def branch_rows() -> list[dict[str, Any]]:
    payload = supabase(f"projects/{PARENT_PROJECT}/branches")
    rows = payload if isinstance(payload, list) else payload.get("branches", payload.get("data", []))
    if not isinstance(rows, list):
        hold("UNEXPECTED_BRANCH_LIST_RESPONSE", response=payload)
    return [row for row in rows if isinstance(row, dict)]


def resolve_preview() -> dict[str, Any]:
    last: list[dict[str, Any]] = []
    for _ in range(150):
        candidates: list[dict[str, Any]] = []
        for row in branch_rows():
            git_branch = str(
                row.get("git_branch")
                or row.get("git_branch_name")
                or row.get("branch_name")
                or ""
            )
            name = str(row.get("name") or "")
            if (
                git_branch == VALIDATION_BRANCH
                or name == VALIDATION_BRANCH
                or VALIDATION_BRANCH.endswith("/" + name)
                or VALIDATION_BRANCH.endswith(name)
            ):
                candidates.append(row)
        candidates.sort(
            key=lambda row: str(row.get("created_at") or row.get("updated_at") or ""),
            reverse=True,
        )
        last = candidates[:5]
        for row in candidates:
            with_data = row.get("with_data")
            if with_data is True:
                hold("PREVIEW_WITH_DATA_TRUE", preview=row)
            row_head = str(
                row.get("head_sha")
                or row.get("git_sha")
                or row.get("commit_sha")
                or ""
            )
            if row_head and SOURCE_HEAD and row_head != SOURCE_HEAD:
                continue
            state = str(
                row.get("status")
                or row.get("migration_status")
                or row.get("state")
                or ""
            )
            if state in {"MIGRATIONS_FAILED", "MIGRATIONS_PASSED"}:
                return row
        time.sleep(12)
    hold("TERMINAL_PREVIEW_STATE_NOT_OBSERVED", observed_candidates=last)
    return {}


def verify_supabase_check(expected_pass: bool) -> list[dict[str, Any]]:
    if not SOURCE_HEAD:
        hold("GITHUB_SOURCE_HEAD_UNAVAILABLE")
    payload = gh(f"commits/{SOURCE_HEAD}/check-runs?per_page=100")
    runs = payload.get("check_runs", []) if isinstance(payload, dict) else []
    supabase_runs = [
        run
        for run in runs
        if isinstance(run, dict)
        and "supabase" in str(run.get("name", "")).lower()
    ]
    if not supabase_runs:
        hold("SUPABASE_CHECK_RUN_NOT_BOUND_TO_SOURCE_HEAD", check_runs=runs)
    if expected_pass and not any(
        str(run.get("conclusion")) == "success" for run in supabase_runs
    ):
        hold("SUPABASE_CHECK_NOT_SUCCESSFUL", supabase_check_runs=supabase_runs)
    return supabase_runs


def preview_ref(row: dict[str, Any]) -> str:
    value = str(
        row.get("project_ref")
        or row.get("project_id")
        or row.get("preview_project_ref")
        or row.get("ref")
        or ""
    )
    if not value or value == PARENT_PROJECT:
        hold("INVALID_PREVIEW_PROJECT_REF", preview=row)
    return value


def cycle_number() -> int:
    match = re.search(r"-c(\d+)-", VALIDATION_BRANCH)
    return int(match.group(1)) if match else 0


def parse_failure(row: dict[str, Any]) -> dict[str, str]:
    strings = list(flatten_strings(row))
    joined = "\n".join(strings)

    version_values = recursive_values(
        row,
        {
            "failed_version",
            "migration_version",
            "failed_migration_version",
            "version",
        },
    )
    versions = [value for value in version_values if re.fullmatch(r"20\d{12}", value)]
    if not versions:
        versions = re.findall(r"\b20\d{12}\b", joined)
    if not versions:
        hold("FAILED_MIGRATION_VERSION_NOT_EXTRACTABLE", preview=row)
    failed_version = versions[-1]

    name_values = recursive_values(
        row,
        {"failed_name", "migration_name", "failed_migration_name", "name"},
    )
    failed_name = next(
        (value for value in name_values if value and value != VALIDATION_BRANCH),
        "unknown",
    )

    relation = re.search(
        r"relation\s+[\"']?([a-zA-Z_][\w]*[.][a-zA-Z_][\w]*)[\"']?\s+does not exist",
        joined,
        re.I,
    )
    schema = re.search(
        r"schema\s+[\"']?([a-zA-Z_][\w]*)[\"']?\s+does not exist",
        joined,
        re.I,
    )
    function = re.search(
        r"function\s+([a-zA-Z_][\w]*[.][a-zA-Z_][\w]*)\s*\([^\n]*?\)\s+does not exist",
        joined,
        re.I,
    )
    column = re.search(
        r"column\s+[\"']?([a-zA-Z_][\w]*)[\"']?\s+(?:of relation\s+[\"']?([a-zA-Z_][\w]*(?:[.][a-zA-Z_][\w]*)?)[\"']?\s+)?does not exist",
        joined,
        re.I,
    )
    foreign_key = re.search(
        r"Key\s*\(([^)]+)\)=\(([^)]+)\)\s+is not present in table\s+[\"']?([a-zA-Z_][\w]*(?:[.][a-zA-Z_][\w]*)?)[\"']?",
        joined,
        re.I,
    )

    result = {
        "failed_version": failed_version,
        "failed_name": failed_name,
        "error_excerpt": joined[-4000:],
    }
    if relation:
        result.update({"kind": "relation", "target": relation.group(1)})
    elif schema:
        result.update({"kind": "schema", "target": schema.group(1)})
    elif function:
        result.update({"kind": "function", "target": function.group(1)})
    elif column:
        target = column.group(1)
        if column.group(2):
            target = f"{column.group(2)}.{target}"
        result.update({"kind": "column", "target": target})
    elif foreign_key:
        result.update(
            {
                "kind": "foreign_key_seed",
                "target": foreign_key.group(3),
                "key_column": foreign_key.group(1),
                "key_value": foreign_key.group(2),
            }
        )
    else:
        hold("UNSUPPORTED_REPLAY_FAILURE_CLASS", preview=row, error_excerpt=joined[-6000:])
    return result


def sql_literal(value: str) -> str:
    return value.replace("'", "''")


def provider_candidates(failure: dict[str, str]) -> list[dict[str, Any]]:
    token = failure["target"].split(".")[-1]
    failed_version = failure["failed_version"]
    query = f"""
    select version,name,array_to_string(statements,E'\\n') as sql_text
    from supabase_migrations.schema_migrations
    where version < '{sql_literal(failed_version)}'
      and array_to_string(statements,E'\\n') ilike '%{sql_literal(token)}%'
    order by version
    """
    rows = sql(PARENT_PROJECT, query)
    target = re.escape(failure["target"])
    kind = failure["kind"]
    filtered: list[dict[str, Any]] = []
    for row in rows:
        body = str(row.get("sql_text") or "")
        lowered = body.lower()
        matched = False
        if kind == "relation":
            matched = bool(
                re.search(
                    rf"create\s+(?:unlogged\s+)?(?:table|view|materialized\s+view)\s+(?:if\s+not\s+exists\s+)?{target}\b",
                    body,
                    re.I,
                )
            )
        elif kind == "schema":
            matched = bool(
                re.search(
                    rf"create\s+schema\s+(?:if\s+not\s+exists\s+)?{target}\b",
                    body,
                    re.I,
                )
            )
        elif kind == "function":
            matched = bool(
                re.search(
                    rf"create\s+(?:or\s+replace\s+)?function\s+{target}\s*\(",
                    body,
                    re.I,
                )
            )
        elif kind == "column":
            parts = failure["target"].split(".")
            column_name = re.escape(parts[-1])
            relation_name = re.escape(".".join(parts[:-1])) if len(parts) > 1 else r"[a-zA-Z_][\w.]*"
            matched = bool(
                re.search(
                    rf"alter\s+table\s+(?:if\s+exists\s+)?{relation_name}.*?add\s+column\s+(?:if\s+not\s+exists\s+)?{column_name}\b",
                    body,
                    re.I | re.S,
                )
            )
        elif kind == "foreign_key_seed":
            value = failure.get("key_value", "")
            table = failure["target"].split(".")[-1]
            matched = table.lower() in lowered and value in body and "insert into" in lowered
        if matched:
            filtered.append(row)
    return filtered


def repair_ref() -> tuple[str, str, list[dict[str, Any]]]:
    ref = gh(f"git/ref/heads/{urllib.parse.quote(REPAIR_BRANCH, safe='')}")
    sha = str(ref.get("object", {}).get("sha") or "")
    if not sha:
        hold("REPAIR_BRANCH_REF_UNAVAILABLE", response=ref)
    commit = gh(f"git/commits/{sha}")
    tree_sha = str(commit.get("tree", {}).get("sha") or "")
    if not tree_sha:
        hold("REPAIR_BRANCH_TREE_UNAVAILABLE", commit=commit)
    tree = gh(f"git/trees/{tree_sha}?recursive=1")
    entries = tree.get("tree", []) if isinstance(tree, dict) else []
    if not isinstance(entries, list):
        hold("REPAIR_TREE_RESPONSE_INVALID", response=tree)
    return sha, tree_sha, [entry for entry in entries if isinstance(entry, dict)]


def choose_candidate(
    rows: list[dict[str, Any]], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    paths = [str(entry.get("path") or "") for entry in entries]
    eligible: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for row in rows:
        version = str(row.get("version") or "")
        migration_paths = sorted(
            path
            for path in paths
            if path.startswith(f"supabase/migrations/{version}_") and path.endswith(".sql")
        )
        markers = [path for path in migration_paths if path.endswith("_remote_applied_lineage.sql")]
        canonical = [path for path in migration_paths if not path.endswith("_remote_applied_lineage.sql")]
        evidence.append(
            {
                "version": version,
                "name": row.get("name"),
                "migration_paths": migration_paths,
            }
        )
        if len(markers) == 1 and not canonical:
            copy = dict(row)
            copy["marker_path"] = markers[0]
            eligible.append(copy)
    if len(eligible) != 1:
        hold(
            "PROVIDER_CUSTODY_CANDIDATE_AMBIGUOUS",
            provider_candidates=evidence,
            eligible_count=len(eligible),
        )
    return eligible[0]


def sanitize_name(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not value:
        hold("PROVIDER_MIGRATION_NAME_UNUSABLE", provider_name=name)
    return value


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def create_blob(raw: bytes) -> str:
    response = gh(
        "git/blobs",
        method="POST",
        body={"content": base64.b64encode(raw).decode("ascii"), "encoding": "base64"},
    )
    sha = str(response.get("sha") or "")
    expected = git_blob_sha(raw)
    if sha != expected:
        hold("GITHUB_BLOB_IDENTITY_MISMATCH", expected=expected, actual=sha)
    return sha


def commit_tree(
    *, parent_sha: str, base_tree_sha: str, message: str, elements: list[dict[str, Any]]
) -> str:
    tree = gh(
        "git/trees",
        method="POST",
        body={"base_tree": base_tree_sha, "tree": elements},
    )
    tree_sha = str(tree.get("sha") or "")
    if not tree_sha:
        hold("GITHUB_TREE_CREATION_FAILED", response=tree)
    commit = gh(
        "git/commits",
        method="POST",
        body={"message": message, "tree": tree_sha, "parents": [parent_sha]},
    )
    commit_sha = str(commit.get("sha") or "")
    if not commit_sha:
        hold("GITHUB_COMMIT_CREATION_FAILED", response=commit)
    return commit_sha


def update_branch(branch: str, sha: str) -> None:
    gh(
        f"git/refs/heads/{urllib.parse.quote(branch, safe='')}",
        method="PATCH",
        body={"sha": sha, "force": False},
    )


def restore_provider(failure: dict[str, str], preview: dict[str, Any]) -> dict[str, Any]:
    parent_sha, tree_sha, entries = repair_ref()
    rows = provider_candidates(failure)
    candidate = choose_candidate(rows, entries)
    version = str(candidate["version"])
    name = str(candidate["name"])
    body_text = candidate.get("sql_text")
    if not isinstance(body_text, str):
        hold("PROVIDER_SQL_BODY_MISSING", candidate={k: v for k, v in candidate.items() if k != "sql_text"})
    raw = body_text.encode("utf-8")
    if not raw or len(raw) > 300_000:
        hold("PROVIDER_SQL_BODY_SIZE_OUT_OF_BOUNDS", version=version, bytes=len(raw))
    for pattern in PROHIBITED:
        if pattern.search(raw):
            hold("PROVIDER_SQL_BODY_SECRET_SCAN_FAILED", version=version, pattern=repr(pattern.pattern))

    body_sha = hashlib.sha256(raw).hexdigest()
    blob_sha = create_blob(raw)
    canonical_path = f"supabase/migrations/{version}_{sanitize_name(name)}.sql"
    marker_path = str(candidate["marker_path"])
    cycle = cycle_number() + 1
    if cycle > MAX_CYCLES:
        hold("MAX_REPLAY_REPAIR_CYCLES_EXCEEDED", cycle=cycle, max_cycles=MAX_CYCLES)

    receipt = {
        "schema": "crownthrive.supabase.chlom-replay-auto-custody/v1",
        "receipt_id": f"ct.supabase.chlom-replay-auto-custody.{version}.c{cycle:02d}",
        "cycle": cycle,
        "failure": failure,
        "failed_preview": preview,
        "provider_project_ref": PARENT_PROJECT,
        "provider_version": version,
        "provider_name": name,
        "canonical_path": canonical_path,
        "retired_marker_path": marker_path,
        "bytes": len(raw),
        "sha256": body_sha,
        "git_blob_sha": blob_sha,
        "credential_literal_scan": "PASS",
        "production_history_mutated": False,
        "production_schema_mutated": False,
        "production_data_copied": False,
        "production_mutated": False,
        "dependent_penta_wave": "HOLD_PENDING_TERMINAL_MIGRATIONS_PASSED",
        "commercial_activation_authorized": False,
        "production_deployment_authorized": False,
        "stable_products_only": True,
        "created_at_utc": now(),
    }
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    receipt_blob = create_blob(receipt_raw)
    receipt_path = f"supabase/migration_lineage/replay_diagnostics/autoloop/c{cycle:02d}_{version}_{sanitize_name(name)}.json"

    repair_commit = commit_tree(
        parent_sha=parent_sha,
        base_tree_sha=tree_sha,
        message=f"fix(supabase): restore provider custody {version} {name}",
        elements=[
            {"path": canonical_path, "mode": "100644", "type": "blob", "sha": blob_sha},
            {"path": marker_path, "mode": "100644", "type": "blob", "sha": None},
            {"path": receipt_path, "mode": "100644", "type": "blob", "sha": receipt_blob},
        ],
    )
    update_branch(REPAIR_BRANCH, repair_commit)

    branch = f"validation/chlom-replay-auto-c{cycle:02d}-{version}-{repair_commit[:7]}"
    try:
        gh(
            "git/refs",
            method="POST",
            body={"ref": f"refs/heads/{branch}", "sha": repair_commit},
        )
    except RuntimeError as exc:
        hold("VALIDATION_BRANCH_CREATION_FAILED", error=str(exc), repair_commit=repair_commit)

    repair_commit_obj = gh(f"git/commits/{repair_commit}")
    repair_tree = str(repair_commit_obj.get("tree", {}).get("sha") or "")
    request_receipt = {
        "schema": "crownthrive.supabase.chlom-replay-validation-request/v1",
        "request_id": f"ct.supabase.chlom-replay-validation.c{cycle:02d}.{version}",
        "cycle": cycle,
        "validation_branch": branch,
        "repair_commit_sha": repair_commit,
        "restored_provider_version": version,
        "restored_provider_name": name,
        "restored_provider_sha256": body_sha,
        "with_data": False,
        "required_terminal_state": "MIGRATIONS_PASSED",
        "required_topology_readback": "PASS",
        "production_mutated": False,
        "dependent_penta_wave": "HOLD",
        "created_at_utc": now(),
    }
    request_raw = (json.dumps(request_receipt, indent=2, sort_keys=True) + "\n").encode()
    request_blob = create_blob(request_raw)
    validation_commit = commit_tree(
        parent_sha=repair_commit,
        base_tree_sha=repair_tree,
        message=f"test(supabase): request CHLOM replay cycle {cycle:02d}",
        elements=[
            {
                "path": f"supabase/migration_lineage/replay_diagnostics/autoloop/c{cycle:02d}_{version}_validation_request.json",
                "mode": "100644",
                "type": "blob",
                "sha": request_blob,
            }
        ],
    )
    update_branch(branch, validation_commit)

    pr = gh(
        "pulls",
        method="POST",
        body={
            "title": f"test(supabase): CHLOM replay cycle {cycle:02d} after {version}",
            "head": branch,
            "base": "main",
            "body": (
                "Validation-only, data-less replay. Do not merge or advance production. "
                f"Restored exact provider custody `{version}_{name}` at `{repair_commit}`. "
                "The dependent Penta wave remains HOLD unless this exact PR reaches literal "
                "MIGRATIONS_PASSED and independent topology readback PASS."
            ),
            "draft": False,
            "maintainer_can_modify": True,
        },
    )
    pr_number = pr.get("number")
    time.sleep(3)
    gh(
        f"actions/workflows/{urllib.parse.quote(WORKFLOW_FILE, safe='')}/dispatches",
        method="POST",
        body={"ref": branch},
    )
    return {
        "state": "EXACT_PROVIDER_CUSTODY_RESTORED_NEXT_PREVIEW_DISPATCHED",
        "cycle": cycle,
        "failure": failure,
        "provider_version": version,
        "provider_name": name,
        "provider_bytes": len(raw),
        "provider_sha256": body_sha,
        "provider_git_blob_sha": blob_sha,
        "repair_commit_sha": repair_commit,
        "validation_branch": branch,
        "validation_commit_sha": validation_commit,
        "validation_pr_number": pr_number,
        "production_mutated": False,
        "dependent_penta_wave": "HOLD",
        "created_at_utc": now(),
    }


def topology_pass(project_ref: str) -> dict[str, Any]:
    query = r"""
    with relations as (
      select n.nspname schema_name,c.relname object_name,c.relkind,c.relrowsecurity,c.relforcerowsecurity
      from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where (n.nspname,c.relname) in (
        ('integration_control','creative_asset_routes'),
        ('institutional_federation','repository_registry'),
        ('institutional_federation','algorithm_registry'),
        ('institutional_federation','repository_agent_bindings'),
        ('institutional_federation','framework_package_registry'),
        ('institutional_federation','continuity_compiler_runs'),
        ('institutional_federation','capability_execution_queue'),
        ('chlom_secrets','trade_secret_assets'),
        ('chlom_runtime','vaulted_capability_registry'),
        ('chlom_runtime','capability_contracts'),
        ('chlom_runtime','agent_templates'),
        ('chlom_runtime','agent_health'),
        ('chlom_runtime','agent_suite_registry'),
        ('chlom_runtime','agent_skill_packages'),
        ('chlom_runtime','construction_work_queue'),
        ('chlom_runtime','construction_gate_definitions'),
        ('chlom_runtime','construction_gate_assignments'),
        ('chlom_runtime','dail_events'),
        ('chlom_runtime','replay_topology_receipts')
      )
    )
    select jsonb_build_object(
      'migration_count',(select count(*) from supabase_migrations.schema_migrations),
      'migration_head',(select max(version) from supabase_migrations.schema_migrations),
      'wrong_execution_builder_version_count',(select count(*) from supabase_migrations.schema_migrations where version='20260823203100'),
      'relations',(select jsonb_agg(to_jsonb(r) order by schema_name,object_name) from relations r),
      'relay_agents',(
        select jsonb_agg(jsonb_build_object('agent_id',agent_id,'canonical_name',canonical_name,'agent_class',agent_class,'authority_ceiling',authority_ceiling,'lifecycle_state',lifecycle_state) order by agent_id)
        from chlom_runtime.agent_templates where agent_id in ('ct.relay.agent-c','ct.relay.agent-d')
      ),
      'append_dail_function_count',(
        select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='chlom_runtime' and p.proname='append_dail_event'
      ),
      'public_write_grants',(
        select coalesce(jsonb_agg(jsonb_build_object('schema',table_schema,'table',table_name,'grantee',grantee,'privilege',privilege_type)), '[]'::jsonb)
        from information_schema.role_table_grants
        where grantee in ('anon','authenticated','PUBLIC')
          and privilege_type in ('INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER')
          and table_schema in ('chlom_runtime','chlom_secrets','institutional_federation','integration_control')
      ),
      'topology_receipt',(
        select to_jsonb(r) from chlom_runtime.replay_topology_receipts r
        where status='PASS' order by observed_at desc limit 1
      )
    ) evidence
    """
    rows = sql(project_ref, query)
    if len(rows) != 1:
        hold("TOPOLOGY_QUERY_ROW_COUNT_INVALID", rows=rows)
    evidence = rows[0].get("evidence")
    if isinstance(evidence, str):
        evidence = json.loads(evidence)
    if not isinstance(evidence, dict):
        hold("TOPOLOGY_EVIDENCE_NOT_OBJECT", row=rows[0])
    errors: list[str] = []
    relations = evidence.get("relations") or []
    if len(relations) != 19:
        errors.append(f"required relations expected=19 actual={len(relations)}")
    for row in relations:
        if row.get("relkind") != "v" and not row.get("relrowsecurity"):
            errors.append(f"RLS disabled {row.get('schema_name')}.{row.get('object_name')}")
    agents = sorted(row.get("agent_id") for row in (evidence.get("relay_agents") or []))
    if agents != ["ct.relay.agent-c", "ct.relay.agent-d"]:
        errors.append(f"relay agents={agents}")
    if int(evidence.get("append_dail_function_count") or 0) < 1:
        errors.append("DAIL append function missing")
    if evidence.get("wrong_execution_builder_version_count") != 0:
        errors.append("non-provider Execution Builder version remains")
    if evidence.get("public_write_grants"):
        errors.append("public/authenticated write grants present")
    topology = evidence.get("topology_receipt")
    if not isinstance(topology, dict) or topology.get("status") != "PASS":
        errors.append("terminal topology receipt missing or not PASS")
    if str(evidence.get("migration_head") or "") < "20260904150000":
        errors.append("migration head below terminal topology migration")
    if errors:
        hold("TOPOLOGY_READBACK_FAILED", errors=errors, topology_evidence=evidence)
    return evidence


def finalize_pass(preview: dict[str, Any], project_ref: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = topology_pass(project_ref)
    receipt = {
        "schema": "crownthrive.supabase.chlom-replay-certification/v1",
        "receipt_id": "ct.supabase.chlom-replay-certification.20260904.terminal",
        "state": "PASS",
        "reason": "DATA_LESS_PREVIEW_MIGRATIONS_PASSED_AND_INDEPENDENT_TOPOLOGY_PASS",
        "validation_branch": VALIDATION_BRANCH,
        "validated_source_head_sha": SOURCE_HEAD,
        "preview_project_ref": project_ref,
        "preview_branch_id": str(preview.get("id") or preview.get("branch_id") or ""),
        "with_data": False,
        "migration_state": "MIGRATIONS_PASSED",
        "topology_readback": evidence,
        "supabase_check_runs": checks,
        "dependent_penta_wave": "ADVANCED_TO_DEPENDENT_VALIDATION",
        "production_history_mutated": False,
        "production_schema_mutated": False,
        "production_data_copied": False,
        "production_mutated": False,
        "production_deployment_authorized": False,
        "commercial_activation_authorized": False,
        "stable_products_only": True,
        "certified_at_utc": now(),
    }
    RESULT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    if not VALIDATION_BRANCH.startswith("validation/chlom-replay-"):
        hold("WORKFLOW_REF_IS_NOT_VALIDATION_BRANCH")
    preview = resolve_preview()
    state = str(
        preview.get("status")
        or preview.get("migration_status")
        or preview.get("state")
        or ""
    )
    project_ref = preview_ref(preview)
    if state == "MIGRATIONS_PASSED":
        checks = verify_supabase_check(expected_pass=True)
        result = finalize_pass(preview, project_ref, checks)
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if state != "MIGRATIONS_FAILED":
        hold("UNEXPECTED_TERMINAL_MIGRATION_STATE", preview=preview)
    checks = verify_supabase_check(expected_pass=False)
    failure = parse_failure(preview)
    result = restore_provider(failure, preview)
    result["supabase_check_runs"] = checks
    RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        hold("AUTLOOP_HTTP_OR_GIT_FAILURE", error=str(exc))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        hold("AUTLOOP_RUNTIME_FAILURE", error=str(exc))
