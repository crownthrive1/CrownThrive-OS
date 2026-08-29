#!/usr/bin/env python3
"""PentaPM remediation assignment and reassignment controller.

Consumes a PentaSELF finding plus its GitHub issue/PR numbers. PentaPM computes
the full required Penta worker set, reconciles assignment labels, and writes a
stable assignment packet to both artifacts. Re-running with changed conditions
replaces stale assignments rather than accumulating them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.github.com"
ASSIGN_PREFIX = "penta:assigned:"
MARKER_PREFIX = "<!-- penta-pm-assignment:"
DEFAULT_OWNER = "PentaBuild"


class GH:
    def __init__(self, repo: str, token: str | None = None) -> None:
        self.repo = repo
        self.token = token or os.environ["GITHUB_TOKEN"]

    def req(self, method: str, path: str, body: Any | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "CrownThrive-PentaPM-Remediation/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"GitHub {method} {path} -> {exc.code}: {detail[:700]}") from exc

    def get(self, path: str) -> Any:
        return self.req("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def delete(self, path: str) -> Any:
        return self.req("DELETE", path)

    def paginate(self, path: str, max_pages: int = 10) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            batch = self.get(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError(f"pagination_expected_list:{path}")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items


def owner_slug(owner: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", owner.strip()).strip("-").lower()
    if not value:
        raise ValueError("empty_penta_owner")
    return value[:48]


def load_policy(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        policy = json.load(handle)
    remediation = policy.get("remediation_assignment")
    if not isinstance(remediation, dict):
        raise ValueError("missing_remediation_assignment_policy")
    return policy


def normalize_explicit_owners(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("required_pentas") or []
    if not isinstance(raw, list):
        raise ValueError("required_pentas_must_be_array")
    owners = {str(item).strip()[:80] for item in raw if str(item).strip()}
    return owners


def desired_owners(payload: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    remediation = policy["remediation_assignment"]
    lane = str(payload.get("lane") or "general").strip().lower()
    state = str(payload.get("state") or "open").strip().lower()
    defaults = set(remediation.get("always_required") or [DEFAULT_OWNER])
    defaults.update((remediation.get("lane_owners") or {}).get(lane) or (remediation.get("lane_owners") or {}).get("general") or [])
    defaults.update(normalize_explicit_owners(payload))
    if state in set(remediation.get("reassignment_states") or []):
        defaults.update(remediation.get("blocked_state_owners") or [])
    risk = str(payload.get("risk") or "").upper()
    if risk in {"D2", "D3"}:
        defaults.update(remediation.get("high_risk_owners") or [])
    return sorted({str(owner).strip() for owner in defaults if str(owner).strip()})[:32]


def _assignment_label(owner: str) -> str:
    return ASSIGN_PREFIX + owner_slug(owner)


def _ensure_dynamic_label(gh: GH, label: str, owner: str) -> None:
    try:
        gh.post(
            f"/repos/{gh.repo}/labels",
            {
                "name": label,
                "color": "006b75",
                "description": f"PentaPM assigned remediation worker: {owner}"[:100],
            },
        )
    except RuntimeError as exc:
        if "422" not in str(exc):
            raise


def _read_labels(gh: GH, number: int) -> set[str]:
    issue = gh.get(f"/repos/{gh.repo}/issues/{number}")
    return {item["name"] for item in issue.get("labels", [])}


def reconcile_assignments(gh: GH, number: int, owners: list[str]) -> dict[str, list[str]]:
    current = _read_labels(gh, number)
    desired = {_assignment_label(owner) for owner in owners}
    managed = {name for name in current if name.startswith(ASSIGN_PREFIX)}
    removed: list[str] = []
    added: list[str] = []
    for label in sorted(managed.difference(desired)):
        encoded = urllib.parse.quote(label, safe="")
        try:
            gh.delete(f"/repos/{gh.repo}/issues/{number}/labels/{encoded}")
        except RuntimeError as exc:
            if "404" not in str(exc):
                raise
        removed.append(label)
    for owner in owners:
        label = _assignment_label(owner)
        if label in current:
            continue
        _ensure_dynamic_label(gh, label, owner)
        gh.post(f"/repos/{gh.repo}/issues/{number}/labels", {"labels": [label]})
        added.append(label)
    for fixed, color, description in (
        ("penta:authority:pm", "006b75", "PentaPM owns remediation assignment and reassignment"),
        ("penta:remediation", "b60205", "PentaSELF remediation work item"),
    ):
        if fixed not in current:
            try:
                gh.post(f"/repos/{gh.repo}/labels", {"name": fixed, "color": color, "description": description})
            except RuntimeError as exc:
                if "422" not in str(exc):
                    raise
            gh.post(f"/repos/{gh.repo}/issues/{number}/labels", {"labels": [fixed]})
    return {"added": added, "removed": removed}


def assignment_marker(finding_id: str) -> str:
    return f"{MARKER_PREFIX}{finding_id} -->"


def _find_assignment_comment(gh: GH, number: int, finding_id: str) -> dict[str, Any] | None:
    wanted = assignment_marker(finding_id)
    for comment in gh.paginate(f"/repos/{gh.repo}/issues/{number}/comments?"):
        if wanted in str(comment.get("body") or ""):
            return comment
    return None


def _assignment_body(payload: dict[str, Any], owners: list[str], issue_number: int, pr_number: int) -> str:
    finding_id = str(payload.get("finding_id") or "unknown")
    revision_material = json.dumps(
        {
            "finding_id": finding_id,
            "state": payload.get("state"),
            "lane": payload.get("lane"),
            "risk": payload.get("risk"),
            "owners": owners,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    revision = hashlib.sha256(revision_material.encode("utf-8")).hexdigest()[:16]
    owner_lines = "\n".join(f"- `{owner}`" for owner in owners)
    return (
        f"{assignment_marker(finding_id)}\n\n"
        "## PentaPM remediation assignment\n"
        f"Assignment revision: `{revision}`\n"
        f"Finding: `{finding_id}`\n"
        f"Issue: `#{issue_number}`\n"
        f"PR: `#{pr_number}`\n"
        f"Lane: `{payload.get('lane') or 'general'}`\n"
        f"Risk: `{payload.get('risk') or 'D1'}`\n"
        f"State: `{payload.get('state') or 'open'}`\n\n"
        "### Required Penta workers\n"
        f"{owner_lines}\n\n"
        "PentaPM owns this worker set. Re-running this controller replaces stale `penta:assigned:*` labels with the current required set. "
        "The bootstrap `penta:hold` remains until the actual repair, tests, evidence, and existing governed release gates are satisfied."
    )


def upsert_assignment_comment(gh: GH, number: int, payload: dict[str, Any], owners: list[str], issue_number: int, pr_number: int) -> None:
    finding_id = str(payload.get("finding_id") or "unknown")
    body = _assignment_body(payload, owners, issue_number, pr_number)
    existing = _find_assignment_comment(gh, number, finding_id)
    if existing:
        gh.patch(f"/repos/{gh.repo}/issues/comments/{existing['id']}", {"body": body})
    else:
        gh.post(f"/repos/{gh.repo}/issues/{number}/comments", {"body": body})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--finding-file", required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--policy", default="config/penta_pm_policy.json")
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")
    with open(args.finding_file, encoding="utf-8") as handle:
        payload = json.load(handle)
    policy = load_policy(args.policy)
    owners = desired_owners(payload, policy)
    if not owners:
        raise SystemExit("PentaPM resolved zero remediation owners; fail closed")
    gh = GH(args.repo)
    issue_delta = reconcile_assignments(gh, args.issue, owners)
    pr_delta = reconcile_assignments(gh, args.pr, owners)
    upsert_assignment_comment(gh, args.issue, payload, owners, args.issue, args.pr)
    upsert_assignment_comment(gh, args.pr, payload, owners, args.issue, args.pr)
    print(
        json.dumps(
            {
                "state": "ASSIGNED",
                "authority": "PentaPM",
                "finding_id": payload.get("finding_id"),
                "issue_number": args.issue,
                "pr_number": args.pr,
                "owners": owners,
                "issue_delta": issue_delta,
                "pr_delta": pr_delta,
                "bootstrap_hold_preserved": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
