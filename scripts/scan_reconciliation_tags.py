#!/usr/bin/env python3
"""Validate CrownThrive reconciliation tags, subagent contracts, and draft index.

Standard-library only. Offline validation is always available. With
--github-open-prs and GITHUB_TOKEN/GITHUB_REPOSITORY, the scanner also compares
the committed draft index to current open pull-request metadata using read-only
GitHub API access.

The draft index may designate exactly one ``self_pr`` whose head is ``SELF``.
That avoids the impossible self-reference of committing a manifest that embeds
its own final commit SHA. Live GitHub metadata remains authoritative for that
single dynamic head.

A moving open draft head is itself reconciliation evidence, not necessarily a
CI defect. Head drift is reported and requires Agent O reconciliation; it only
fails this scanner when the stale indexed row still claims ``CT:CI-PASS``,
because exact-head technical proof must never silently follow a changed head.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TAG_MANIFEST = ROOT / "developers/manifests/reconciliation-tag-system.v1.json"
DRAFT_INDEX = ROOT / "developers/manifests/draft-reconciliation-index.v1.json"
AGENT_FILES = {
    "ct.subagent.reconciliation-tag-sentinel": ROOT / "developers/agents/reconciliation/agent-l-tag-sentinel.v1.yaml",
    "ct.subagent.permissioned-source-reconciler": ROOT / "developers/agents/reconciliation/agent-m-permissioned-source-reconciler.v1.yaml",
    "ct.subagent.reconciliation-proof-verifier": ROOT / "developers/agents/reconciliation/agent-n-proof-drift-verifier.v1.yaml",
    "ct.subagent.draft-reconciliation-integrator": ROOT / "developers/agents/reconciliation/agent-o-draft-reconciliation-integrator.v1.yaml",
}
TAG_BLOCK = re.compile(r"<!--\s*ct-reconciliation-tags:v1(?P<body>.*?)-->", re.DOTALL | re.IGNORECASE)
TAG_TOKEN = re.compile(r"\bCT:[A-Z][A-Z0-9-]*\b")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Missing required JSON: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail(f"Expected object in {path.relative_to(ROOT)}")
    return data


def validate_tag_set(tags: list[str], allowed: set[str], context: str) -> None:
    if len(tags) != len(set(tags)):
        fail(f"Duplicate reconciliation tag in {context}")
    unknown = sorted(set(tags) - allowed)
    if unknown:
        fail(f"Unknown reconciliation tag(s) in {context}: {unknown}")
    s = set(tags)
    if "CT:PASS" in s:
        required = {"CT:RECONCILE", "CT:SOURCE-SCAN", "CT:DRIFT-WATCH"}
        if not required.issubset(s):
            fail(f"CT:PASS missing required drift/source tags in {context}")
        if s & {"CT:OPEN", "CT:BLOCKED", "CT:DEFERRAL", "CT:NOT-PASS"}:
            fail(f"CT:PASS conflicts with unresolved state in {context}")
    if "CT:DEFERRAL" in s:
        required = {"CT:NOT-PASS", "CT:RECONCILE", "CT:SOURCE-SCAN", "CT:REOPEN-WATCH"}
        if not required.issubset(s):
            fail(f"CT:DEFERRAL missing required non-pass/reopen tags in {context}")
        if "CT:PASS" in s:
            fail(f"Deferral cannot be PASS in {context}")
    if "CT:STALE-BASE" in s and not {"CT:DRAFT", "CT:RECONCILE"}.issubset(s):
        fail(f"CT:STALE-BASE must be a reconciled draft in {context}")
    if "CT:CI-PASS" in s and "CT:CI-FAIL" in s:
        fail(f"CI cannot be both PASS and FAIL in {context}")
    if "CT:SUPERSEDED" in s and "CT:RECONCILE" not in s:
        fail(f"Superseded record must remain reconciliation-addressable in {context}")


def parse_tag_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    for match in TAG_BLOCK.finditer(text or ""):
        blocks.append(TAG_TOKEN.findall(match.group("body")))
    return blocks


def github_get(url: str, token: str) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "crownthrive-reconciliation-tag-scanner/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as response:  # noqa: S310 - validated fixed GitHub host
        return json.loads(response.read().decode("utf-8"))


def fetch_open_prs(repository: str, token: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        fail("Invalid GITHUB_REPOSITORY")
    url = f"https://api.github.com/repos/{repository}/pulls?state=open&per_page=100"
    try:
        data = github_get(url, token)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        fail(f"Read-only GitHub draft scan failed: {exc}")
    if not isinstance(data, list):
        fail("Unexpected GitHub pull-request response")
    return [x for x in data if isinstance(x, dict)]


def validate_agent_contracts(manifest: dict[str, Any]) -> None:
    declared = {x.get("agent_id") for x in manifest.get("subagents", []) if isinstance(x, dict)}
    if declared != set(AGENT_FILES):
        fail(f"Reconciliation subagent set drifted: {sorted(str(x) for x in declared)}")
    required_fragments = (
        "vote_eligible: false",
        "may_advance_phase: false",
        "self_state_awareness: true",
        "self_audit: true",
        "self_reconciliation: true",
        "self_limiting_least_privilege: true",
        "self_escalation: true",
        "self_documentation: true",
        "self_recovery: true",
    )
    for agent_id, path in AGENT_FILES.items():
        if not path.is_file():
            fail(f"Missing reconciliation subagent contract: {path.relative_to(ROOT)}")
        text = path.read_text(encoding="utf-8")
        if f"agent_id: {agent_id}" not in text:
            fail(f"Agent identity mismatch in {path.relative_to(ROOT)}")
        for fragment in required_fragments:
            if fragment not in text:
                fail(f"Missing {fragment!r} in {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-open-prs", action="store_true", help="Compare draft index to current open GitHub PRs")
    parser.add_argument("--event", type=Path, default=Path(os.environ["GITHUB_EVENT_PATH"]) if os.environ.get("GITHUB_EVENT_PATH") else None)
    args = parser.parse_args()

    tag_manifest = load_json(TAG_MANIFEST)
    draft_index = load_json(DRAFT_INDEX)

    if tag_manifest.get("manifest_id") != "ct.manifest.reconciliation-tag-system.v1":
        fail("Reconciliation tag manifest identity drifted")
    if tag_manifest.get("phase") != "2.99" or tag_manifest.get("roadmap_generation") != "ten_phase_v1":
        fail("Reconciliation tag system must remain Phase 2.99 / ten_phase_v1")
    if tag_manifest.get("governance_decision") != "CT-ADR-GOV-011":
        fail("Reconciliation tag system must inherit CT-ADR-GOV-011")
    if tag_manifest.get("vote_eligible") is not False or tag_manifest.get("may_advance_phase") is not False:
        fail("Reconciliation tag system cannot vote or advance phases")
    if tag_manifest.get("tag_authority") != "routing_and_evidence_discovery_only":
        fail("Tags must remain routing/evidence metadata only")

    tag_defs = tag_manifest.get("tags")
    if not isinstance(tag_defs, dict) or not tag_defs:
        fail("Missing tag definitions")
    allowed = set(tag_defs)
    required_allowed = {
        "CT:PASS", "CT:OPEN", "CT:BLOCKED", "CT:CLOSED", "CT:DEFERRAL", "CT:NOT-PASS",
        "CT:RECONCILE", "CT:SOURCE-SCAN", "CT:DRIFT-WATCH", "CT:REOPEN-WATCH",
        "CT:DRAFT", "CT:STALE-BASE", "CT:CI-PASS", "CT:CI-FAIL", "CT:QUORUM-PENDING",
        "CT:SPECIALIST-PENDING", "CT:DEPENDENCY-PENDING", "CT:SUPERSEDED",
    }
    if not required_allowed.issubset(allowed):
        fail(f"Required reconciliation tags missing: {sorted(required_allowed - allowed)}")

    validate_agent_contracts(tag_manifest)

    if draft_index.get("manifest_id") != "ct.manifest.draft-reconciliation-index.v1":
        fail("Draft reconciliation index identity drifted")
    observed_main = draft_index.get("observed_main_sha")
    if not isinstance(observed_main, str) or not SHA40.fullmatch(observed_main):
        fail("Draft index observed_main_sha must be an exact commit SHA")
    self_pr = draft_index.get("self_pr")
    if not isinstance(self_pr, int) or self_pr <= 0:
        fail("Draft index must declare positive integer self_pr")
    if draft_index.get("self_head_semantics") != "dynamic_live_head_not_self_committed_sha":
        fail("Draft index self-head semantics drifted")
    drafts = draft_index.get("drafts")
    if not isinstance(drafts, list):
        fail("Draft index drafts must be an array")

    seen_prs: set[int] = set()
    self_rows = 0
    for row in drafts:
        if not isinstance(row, dict):
            fail("Draft index row must be an object")
        pr = row.get("pr")
        if not isinstance(pr, int) or pr <= 0 or pr in seen_prs:
            fail(f"Invalid/duplicate PR in draft index: {pr!r}")
        seen_prs.add(pr)
        head, base = row.get("head"), row.get("base")
        if pr == self_pr:
            self_rows += 1
            if head != "SELF":
                fail(f"Self PR #{pr} must use head='SELF'")
        elif not isinstance(head, str) or not SHA40.fullmatch(head):
            fail(f"PR #{pr} head must be exact SHA")
        if not isinstance(base, str) or not SHA40.fullmatch(base):
            fail(f"PR #{pr} base must be exact SHA")
        tags = row.get("tags")
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            fail(f"PR #{pr} tags must be strings")
        validate_tag_set(tags, allowed, f"PR #{pr}")
        s = set(tags)
        if "CT:DRAFT" not in s:
            fail(f"Open draft index entry #{pr} lacks CT:DRAFT")
        if base != observed_main and "CT:STALE-BASE" not in s:
            fail(f"PR #{pr} base differs from observed main but lacks CT:STALE-BASE")
        if "CT:CI-PASS" in s and not row.get("evidence_refs"):
            fail(f"PR #{pr} claims CT:CI-PASS without evidence reference")
        if "CT:PASS" in s:
            fail(f"Draft PR #{pr} must not use sovereign-looking CT:PASS")
    if self_rows != 1:
        fail("Draft index must contain exactly one SELF row")

    closed_rows = draft_index.get("closed_superseded_drafts", [])
    if not isinstance(closed_rows, list):
        fail("closed_superseded_drafts must be an array")
    for row in closed_rows:
        if not isinstance(row, dict) or not isinstance(row.get("pr"), int):
            fail("Invalid closed superseded draft row")
        tags = row.get("tags")
        if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
            fail(f"Closed PR #{row.get('pr')} tags must be strings")
        validate_tag_set(tags, allowed, f"closed PR #{row.get('pr')}")
        if "CT:SUPERSEDED" not in tags:
            fail(f"Closed superseded PR #{row.get('pr')} lacks CT:SUPERSEDED")
        if row.get("disposition") != "closed_unmerged_history_preserved":
            fail(f"Closed PR #{row.get('pr')} must preserve history")

    if args.event and args.event.is_file():
        event = load_json(args.event)
        texts: list[tuple[str, str]] = []
        pr = event.get("pull_request")
        issue = event.get("issue")
        comment = event.get("comment")
        if isinstance(pr, dict):
            texts.append(("pull_request.body", str(pr.get("body") or "")))
        if isinstance(issue, dict):
            texts.append(("issue.body", str(issue.get("body") or "")))
        if isinstance(comment, dict):
            texts.append(("comment.body", str(comment.get("body") or "")))
        for context, text in texts:
            for block in parse_tag_blocks(text):
                validate_tag_set(block, allowed, context)

    drift_messages: list[str] = []
    if args.github_open_prs:
        token = os.environ.get("GITHUB_TOKEN", "")
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if not token or not repository:
            fail("--github-open-prs requires GITHUB_TOKEN and GITHUB_REPOSITORY")
        live = fetch_open_prs(repository, token)
        live_numbers = {int(x["number"]) for x in live if isinstance(x.get("number"), int)}
        if live_numbers != seen_prs:
            missing = sorted(live_numbers - seen_prs)
            stale = sorted(seen_prs - live_numbers)
            fail(f"Draft index drift: missing live PRs={missing}; indexed-but-not-open={stale}")
        by_number = {int(x["number"]): x for x in live if isinstance(x.get("number"), int)}
        for row in drafts:
            pr = int(row["pr"])
            live_row = by_number[pr]
            live_head = str((live_row.get("head") or {}).get("sha") or "")
            live_base = str((live_row.get("base") or {}).get("sha") or "")
            tags = set(row.get("tags") or [])
            if pr == self_pr:
                if not SHA40.fullmatch(live_head):
                    fail(f"Self PR #{pr} live head is not a valid exact SHA")
            elif live_head and live_head != row["head"]:
                message = f"PR #{pr} head drift: index={row['head']} live={live_head}"
                if "CT:CI-PASS" in tags:
                    fail(message + "; stale CT:CI-PASS must be re-proven on the new exact head")
                drift_messages.append(message)
            if live_base and live_base != row["base"]:
                drift_messages.append(f"PR #{pr} base drift: index={row['base']} live={live_base}")

    print("Reconciliation tag validation passed.")
    print(f"Allowed tags: {len(allowed)}")
    print(f"Indexed open drafts: {len(drafts)}")
    print(f"Closed superseded drafts preserved: {len(closed_rows)}")
    if drift_messages:
        print(f"Live moving-draft reconciliation signals: {len(drift_messages)}")
        for message in drift_messages:
            print(f"DRIFT: {message}")
    print("Agents L/M/N/O are non-voting, least-privilege, self-auditing and phase-gated.")
    print("PASS remains drift-watched; DEFERRAL remains explicitly NOT-PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
