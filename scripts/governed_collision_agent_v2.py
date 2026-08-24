#!/usr/bin/env python3
"""GitHub observer/preflight/reaction adapter for collision RTC v2.

The adapter is read-only.  It creates a main/head-bound evidence report and
bounded repair *proposals*; it never mutates a pull request or repository.  A
non-zero exit on material overlap is the prevention mechanism when wired to a
required check.
"""

from __future__ import annotations

import argparse
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
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from collision_rtc_v2 import (
    COLLISION_CLASSES,
    SCHEMA_VERSION,
    Claim,
    Collision,
    ContractError,
    Intent,
    RepairPlan,
    canonical_json,
    classify_collision,
    disposition_for,
    sha256_json,
)


SEMANTIC_JSON_PREFIXES = (
    "developers/manifests/",
    "contracts/",
    "reference/",
    "standards/",
)
SEMANTIC_JSON_FILES = {"docs.json"}
WORKFLOW_SUFFIXES = (".yml", ".yaml")
SQL_SUFFIXES = (".sql",)
MAX_OPEN_PRS = 300
MAX_FILES_PER_PR = 500
MAX_INSPECT_BYTES = 512_000
MAX_SEMANTIC_INSPECTIONS = 1_200
INTENT_COMMENT = re.compile(
    r"<!--\s*crownthrive-collision-intent:v2\s*(\{.*?\})\s*-->", re.DOTALL | re.IGNORECASE
)
CRON = re.compile(r"\bcron\s*:\s*['\"]([^'\"]+)['\"]")
SQL_OBJECT = re.compile(
    r"\b(?:create|alter|drop)\s+(?:or\s+replace\s+)?(?:table|function|view|sequence|policy|trigger)\s+"
    r"(?:if\s+(?:not\s+)?exists\s+)?([A-Za-z_][A-Za-z0-9_.]*)",
    re.IGNORECASE,
)
MDX_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
FRONTMATTER_FIELD = re.compile(r"^(id|slug|route|document_id)\s*:\s*['\"]?([^'\"\n]+)", re.MULTILINE)

SEMANTIC_KEYS = {
    "agent_id": "stable_id",
    "manifest_id": "stable_id",
    "framework_id": "stable_id",
    "stable_id": "stable_id",
    "document_id": "stable_id",
    "policy_id": "stable_id",
    "schedule_id": "schedule_slot",
    "runtime_resource": "runtime_resource",
    "function_id": "runtime_resource",
    "provider_reference": "provider_reference",
    "route": "route",
    "slug": "route",
    "source_id": "source_generation",
}
SEMANTIC_MDX_PREFIXES = ("automation/", "standards/", "developers/", "contracts/", "reference/")


class GitHubReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangedFile:
    path: str
    access: str
    value_digest: str | None
    previous_path: str | None = None


class GitHubClient:
    def __init__(self, repository: str, token: str | None) -> None:
        self.repository = repository
        self.token = token
        self.base = f"https://api.github.com/repos/{repository}"
        self._content_cache: dict[tuple[str, str], str] = {}
        self._semantic_inspections = 0

    def _request(self, url: str) -> tuple[Any, Mapping[str, str]]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "crownthrive-collision-agent-v2",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    return body, response.headers
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 502, 503, 504}:
                    break
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
            except json.JSONDecodeError as exc:
                raise GitHubReadError(f"github_invalid_json:{url}:{exc}") from exc
            if attempt < 2:
                time.sleep(2**attempt)
        raise GitHubReadError(f"github_read_failed:{url}:{last_error}") from last_error

    def get(self, path: str) -> Any:
        data, _ = self._request(self.base + path)
        return data

    def paged(self, path: str, *, maximum: int) -> list[dict[str, Any]]:
        separator = "&" if "?" in path else "?"
        page = 1
        items: list[dict[str, Any]] = []
        last_page_count = 0
        while len(items) < maximum:
            url = self.base + path + f"{separator}per_page=100&page={page}"
            data, _ = self._request(url)
            if not isinstance(data, list):
                raise GitHubReadError("github_list_response_required")
            last_page_count = len(data)
            items.extend(item for item in data if isinstance(item, dict))
            if len(data) < 100:
                break
            page += 1
        if len(items) > maximum or (len(items) >= maximum and last_page_count == 100):
            raise GitHubReadError(f"bounded_snapshot_may_be_truncated:{maximum}")
        return items

    def main_sha(self, branch: str) -> str:
        data = self.get("/commits/" + urllib.parse.quote(branch, safe=""))
        return str(data["sha"])

    def open_pulls(self) -> list[dict[str, Any]]:
        return self.paged("/pulls?state=open&sort=updated&direction=desc", maximum=MAX_OPEN_PRS)

    def pull(self, number: int) -> dict[str, Any]:
        data = self.get(f"/pulls/{number}")
        if not isinstance(data, dict):
            raise GitHubReadError("github_pull_response_required")
        return data

    def files(self, number: int) -> list[ChangedFile]:
        data = self.paged(f"/pulls/{number}/files", maximum=MAX_FILES_PER_PR)
        files: list[ChangedFile] = []
        for item in data:
            if not item.get("filename"):
                continue
            status = str(item.get("status", "modified"))
            access = {"added": "create", "removed": "retire", "renamed": "create"}.get(status, "mutate")
            blob_sha = str(item.get("sha", ""))
            digest = hashlib.sha256(("git-blob-sha1:" + blob_sha).encode("utf-8")).hexdigest() if blob_sha else None
            files.append(
                ChangedFile(
                    path=str(item["filename"]),
                    access=access,
                    value_digest=digest,
                    previous_path=str(item["previous_filename"]) if item.get("previous_filename") else None,
                )
            )
        if not files:
            raise GitHubReadError(f"pull_request_{number}_has_no_readable_files")
        return sorted(set(files), key=lambda item: (item.path, item.access, item.previous_path or ""))

    def content(self, path: str, ref: str) -> str:
        key = (ref, path)
        if key in self._content_cache:
            return self._content_cache[key]
        self._semantic_inspections += 1
        if self._semantic_inspections > MAX_SEMANTIC_INSPECTIONS:
            raise GitHubReadError(f"semantic_inspection_bound_exceeded:{MAX_SEMANTIC_INSPECTIONS}")
        encoded_path = urllib.parse.quote(path, safe="/")
        data = self.get(f"/contents/{encoded_path}?ref={urllib.parse.quote(ref, safe='')}")
        if not isinstance(data, dict) or data.get("encoding") != "base64":
            raise GitHubReadError(f"unsupported_content_response:{path}")
        size = int(data.get("size", 0))
        if size > MAX_INSPECT_BYTES:
            raise GitHubReadError(f"semantic_file_too_large:{path}:{size}")
        try:
            raw = base64.b64decode(str(data.get("content", "")), validate=False).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise GitHubReadError(f"semantic_file_not_utf8:{path}") from exc
        self._content_cache[key] = raw
        return raw


def executable_sha() -> str:
    digest = hashlib.sha256()
    for name in ("collision_rtc_v2.py", "governed_collision_agent_v2.py"):
        digest.update((Path(__file__).resolve().parent / name).read_bytes())
    return digest.hexdigest()


def manifest_sha() -> str:
    manifest = Path(__file__).resolve().parents[1] / "developers/manifests/collision-governance-rtc.v2.json"
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


def needs_semantic_inspection(path: str) -> bool:
    return (
        (path.endswith(".json") and (path in SEMANTIC_JSON_FILES or path.startswith(SEMANTIC_JSON_PREFIXES)))
        or (path.startswith(".github/workflows/") and path.endswith(WORKFLOW_SUFFIXES))
        or path.endswith(SQL_SUFFIXES)
        or (path.endswith(".mdx") and path.startswith(SEMANTIC_MDX_PREFIXES))
    )


def walk_semantic_json(value: Any) -> Iterable[Claim]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            domain_type = SEMANTIC_KEYS.get(str(key))
            if domain_type and isinstance(child, (str, int)):
                yield Claim.from_mapping(
                    {"domain_type": domain_type, "key": str(child), "access": "mutate"}
                )
            yield from walk_semantic_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_semantic_json(child)


def claims_from_content(path: str, content: str) -> set[Claim]:
    claims: set[Claim] = set()
    if path.endswith(".json"):
        try:
            claims.update(walk_semantic_json(json.loads(content)))
        except json.JSONDecodeError as exc:
            raise ContractError(f"semantic_json_invalid:{path}:{exc.lineno}") from exc
    if path.startswith(".github/workflows/") and path.endswith(WORKFLOW_SUFFIXES):
        for schedule in CRON.findall(content):
            claims.add(
                Claim.from_mapping(
                    {"domain_type": "schedule_slot", "key": schedule, "access": "mutate"}
                )
            )
    if path.endswith(SQL_SUFFIXES):
        for object_name in SQL_OBJECT.findall(content):
            claims.add(
                Claim.from_mapping(
                    {"domain_type": "runtime_resource", "key": object_name, "access": "mutate"}
                )
            )
    if path.endswith(".mdx"):
        frontmatter = MDX_FRONTMATTER.search(content)
        if frontmatter:
            for field, value in FRONTMATTER_FIELD.findall(frontmatter.group(1)):
                domain = "stable_id" if field in {"id", "document_id"} else "route"
                claims.add(Claim.from_mapping({"domain_type": domain, "key": value, "access": "mutate"}))
    return claims


def claims_from_body(body: str | None) -> set[Claim]:
    if not body:
        return set()
    match = INTENT_COMMENT.search(body)
    if not match:
        return set()
    try:
        declaration = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ContractError("invalid_pr_body_collision_intent_json") from exc
    if declaration.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("invalid_pr_body_collision_intent_version")
    raw_claims = declaration.get("claims")
    if not isinstance(raw_claims, list):
        raise ContractError("invalid_pr_body_collision_claims")
    return {Claim.from_mapping(item) for item in raw_claims}


def build_pr_intent(
    client: GitHubClient,
    pull: Mapping[str, Any],
    files: Sequence[ChangedFile],
    *,
    main_sha: str,
    executable_digest: str,
    policy_digest: str,
) -> tuple[Intent, list[str]]:
    number = int(pull["number"])
    head_sha = str(pull["head"]["sha"])
    base_sha = str(pull["base"]["sha"])
    claims: set[Claim] = set()
    for changed in files:
        claim = {"domain_type": "path", "key": changed.path, "access": changed.access}
        if changed.value_digest:
            claim["value_digest"] = changed.value_digest
        claims.add(Claim.from_mapping(claim))
        if changed.previous_path:
            claims.add(
                Claim.from_mapping(
                    {"domain_type": "path", "key": changed.previous_path, "access": "retire"}
                )
            )
    errors: list[str] = []
    for changed in files:
        path = changed.path
        if not needs_semantic_inspection(path):
            continue
        try:
            content_ref = base_sha if changed.access == "retire" else head_sha
            claims.update(claims_from_content(path, client.content(path, content_ref)))
        except (GitHubReadError, ContractError) as exc:
            errors.append(str(exc))
    try:
        claims.update(claims_from_body(pull.get("body")))
    except ContractError as exc:
        errors.append(str(exc))
    correlation = uuid.uuid5(uuid.NAMESPACE_URL, f"{client.repository}:pr:{number}:{head_sha}:{main_sha}")
    instance = uuid.uuid5(uuid.NAMESPACE_URL, f"{client.repository}:collision-agent:{main_sha}")
    intent = Intent.from_mapping(
        {
            "schema_version": SCHEMA_VERSION,
            "intent_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{client.repository}:pr:{number}:{head_sha}")),
            "repository": client.repository,
            "target": {"kind": "pull_request", "id": str(number)},
            "agent": {
                "agent_id": "ct.subagent.collision.preflight-sentinel",
                "instance_id": str(instance),
            },
            "versions": {
                "base_sha": base_sha,
                "head_sha": head_sha,
                "executable_sha256": executable_digest,
                "config_sha256": policy_digest,
                "policy_sha256": policy_digest,
            },
            "authority_class": "D1",
            "correlation_id": str(correlation),
            "claims": [claim.as_dict() for claim in sorted(claims)],
        }
    )
    return intent, sorted(set(errors))


def collision_matrix(intents: Sequence[Intent]) -> list[Collision]:
    output: list[Collision] = []
    for index, left in enumerate(intents):
        for right in intents[index + 1 :]:
            collision = classify_collision(left, right)
            if collision.severity:
                output.append(collision)
    return sorted(output, key=lambda item: (-item.severity, item.fingerprint))


def pull_snapshot_record(pull: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "head_sha": str(pull["head"]["sha"]),
        "base_sha": str(pull["base"]["sha"]),
        "updated_at": pull.get("updated_at"),
        "draft": bool(pull.get("draft", False)),
        "body_sha256": hashlib.sha256(str(pull.get("body") or "").encode("utf-8")).hexdigest(),
    }


def analyze_snapshot(
    client: GitHubClient,
    *,
    branch: str,
    candidate: int | None,
    event_action: str | None,
) -> dict[str, Any]:
    main_start = client.main_sha(branch)
    if candidate is not None and event_action == "closed":
        pull = client.pull(candidate)
        head_sha = str(pull["head"]["sha"])
        main_end = client.main_sha(branch)
        return {
            "schema_version": SCHEMA_VERSION,
            "mode": "reaction",
            "reaction": "RELEASE_OWNERSHIP_AND_RECONCILE",
            "target_pr": candidate,
            "head_sha": head_sha,
            "main_sha_start": main_start,
            "main_sha_end": main_end,
            "snapshot_stable": main_start == main_end,
            "merge_authority": False,
            "D3_auto": False,
        }

    pulls = client.open_pulls()
    if candidate is not None and not any(int(pr["number"]) == candidate for pr in pulls):
        pulls.append(client.pull(candidate))
    pulls = sorted(pulls, key=lambda item: int(item["number"]))
    executable_digest = executable_sha()
    policy_digest = manifest_sha()
    intents: list[Intent] = []
    errors: dict[int, list[str]] = {}
    head_snapshot: dict[int, str] = {}
    pull_snapshot: dict[int, dict[str, Any]] = {}
    for pull in pulls:
        number = int(pull["number"])
        head_snapshot[number] = str(pull["head"]["sha"])
        pull_snapshot[number] = pull_snapshot_record(pull)
        intent, inspection_errors = build_pr_intent(
            client,
            pull,
            client.files(number),
            main_sha=main_start,
            executable_digest=executable_digest,
            policy_digest=policy_digest,
        )
        intents.append(intent)
        if inspection_errors:
            errors[number] = inspection_errors

    all_collisions = collision_matrix(intents)
    if candidate is None:
        selected = all_collisions
    else:
        candidate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{client.repository}:pr:{candidate}:{head_snapshot[candidate]}"))
        selected = [
            collision
            for collision in all_collisions
            if candidate_id in {collision.left_intent_id, collision.right_intent_id}
        ]
    decision = disposition_for(selected)
    if errors:
        decision = {
            **decision,
            "disposition": "HOLD",
            "max_severity": max(2, int(decision["max_severity"])),
            "reason_codes": sorted(set(decision["reason_codes"]) | {"semantic_inspection_incomplete"}),
        }
    plans: list[dict[str, Any]] = []
    by_id = {intent.intent_id: intent for intent in intents}
    for collision in selected:
        primary = by_id[collision.left_intent_id]
        plans.append(RepairPlan.compile(collision, primary, current_main_sha=main_start).as_dict())

    pulls_end = client.open_pulls()
    head_snapshot_end = {int(pull["number"]): str(pull["head"]["sha"]) for pull in pulls_end}
    pull_snapshot_end = {int(pull["number"]): pull_snapshot_record(pull) for pull in pulls_end}
    main_end = client.main_sha(branch)
    candidate_end: str | None = None
    if candidate is not None:
        candidate_end = head_snapshot_end.get(candidate)
        if candidate_end is None:
            candidate_end = str(client.pull(candidate)["head"]["sha"])
    snapshot_stable = main_start == main_end and pull_snapshot == pull_snapshot_end
    if not snapshot_stable:
        decision = {
            **decision,
            "disposition": "HOLD",
            "max_severity": max(2, int(decision["max_severity"])),
            "reason_codes": sorted(set(decision["reason_codes"]) | {"snapshot_changed_during_evaluation"}),
        }
    epoch = sha256_json(
        {
            "repository": client.repository,
            "main_sha": main_start,
            "pull_snapshot": pull_snapshot,
            "executable_sha256": executable_digest,
            "policy_sha256": policy_digest,
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "preflight" if candidate is not None else "reconcile",
        "repository": client.repository,
        "target_pr": candidate,
        "snapshot_epoch_sha256": epoch,
        "main_sha_start": main_start,
        "main_sha_end": main_end,
        "candidate_head_start": head_snapshot.get(candidate) if candidate is not None else None,
        "candidate_head_end": candidate_end,
        "open_pr_snapshot_start_sha256": sha256_json(pull_snapshot),
        "open_pr_snapshot_end_sha256": sha256_json(pull_snapshot_end),
        "snapshot_stable": snapshot_stable,
        "open_pull_request_count": len(pulls),
        "intent_count": len(intents),
        "inspection_errors": errors,
        "decision": decision,
        "collisions": [item.as_dict() for item in selected],
        "repair_proposals": plans,
        "reaction_policy": {
            "pr_opened_or_updated": "detect_then_prevent_before_promotion",
            "pr_closed_or_main_advanced": "release_recompute_rebind_or_hold",
            "expired_lease": "release_with_new_fence_epoch",
            "repair_failure": "bounded_retry_then_dead_letter",
        },
        "merge_authority": False,
        "force_push_authority": False,
        "provider_write_authority": False,
        "D3_auto": False,
    }


def write_report(report: Mapping[str, Any], output: str | None) -> None:
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        decision = report.get("decision", {})
        lines = [
            "## Collision governance v2",
            "",
            f"- Mode: `{report.get('mode')}`",
            f"- Disposition: `{decision.get('disposition', report.get('reaction'))}`",
            f"- Maximum severity: `{decision.get('max_severity', 0)}`",
            f"- Snapshot stable: `{report.get('snapshot_stable')}`",
            f"- Main start: `{report.get('main_sha_start')}`",
            f"- Main end: `{report.get('main_sha_end')}`",
            f"- Collisions: `{len(report.get('collisions', []))}`",
            "- Auto-merge: `false`",
            "- D3 auto: `false`",
            "",
        ]
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--candidate", type=int)
    parser.add_argument("--event-action", default=os.environ.get("GITHUB_EVENT_ACTION"))
    parser.add_argument("--output", default="collision-governance-v2-report.json")
    parser.add_argument("--fail-on-severity", type=int, default=2)
    args = parser.parse_args(argv)
    if not args.repository:
        parser.error("--repository or GITHUB_REPOSITORY is required")
    try:
        report = analyze_snapshot(
            GitHubClient(args.repository, args.token),
            branch=args.branch,
            candidate=args.candidate,
            event_action=args.event_action,
        )
        write_report(report, args.output)
        decision = report.get("decision")
        if isinstance(decision, Mapping) and int(decision.get("max_severity", 0)) >= args.fail_on_severity:
            return 2
        return 0
    except (ContractError, GitHubReadError, KeyError, TypeError, ValueError, OSError) as exc:
        failure = {
            "schema_version": SCHEMA_VERSION,
            "disposition": "HOLD",
            "reason_code": "COLLISION_OBSERVER_FAILED_CLOSED",
            "error": str(exc),
            "merge_authority": False,
            "D3_auto": False,
        }
        write_report(failure, args.output)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
