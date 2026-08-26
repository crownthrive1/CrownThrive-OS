#!/usr/bin/env python3
"""GitHub-native PentaTagger.

PentaTagger owns semantic labels and readback receipts. It never merges or closes.
PentaPR owns lifecycle classification; PentaMerge and PentaCloser own terminal writes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from penta_github_labels import (
    DISPOSITION_LABELS,
    DISPOSITION_STAGE,
    ENTITY_PREFIXES,
    LANE_PREFIXES,
    RISK_PREFIXES,
    STAGE_PREFIXES,
    TERMINAL_PREFIXES,
    add_labels,
    ensure_labels,
    read_labels,
    reconcile_group,
)

API = "https://api.github.com"
COMMENT_MARKER = "<!-- penta-github-tagger:"
MAX_PAGES = 10

LANE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "docs": (
        "docs", "documentation", "mintlify", "pentadocs", "readme", "guide",
        "handbook", "sop", "policy", "constitution", "registry",
    ),
    "workflow": (
        "workflow", "github actions", "runner", "ci", "automation", "cron",
        "pipeline", "pull request", "issue", "label", "tagger", "closer",
    ),
    "database": (
        "database", "supabase", "postgres", "sql", "migration", "schema",
        "table", "rls", "row level security", "function", "trigger",
    ),
    "provider": (
        "provider", "adapter", "integration", "api", "webhook", "oauth",
        "mailgun", "resend", "stripe", "vercel", "cloudflare", "mintlify",
    ),
    "security": (
        "security", "credential", "secret", "token", "auth", "oauth", "rls",
        "policy", "incident", "vulnerability", "attestation", "provenance",
    ),
    "commerce": (
        "commerce", "checkout", "payment", "stripe", "price", "product",
        "license", "economic", "money", "subscription", "invoice", "wallet",
    ),
    "media": (
        "media", "music", "video", "television", "tv", "radio", "audio",
        "publishing", "book", "sermon", "kjv", "stream", "riverside",
    ),
    "observability": (
        "observability", "logger", "logging", "error", "report", "alert",
        "notification", "metric", "trace", "telemetry", "status", "monitor",
    ),
}

HIGH_RISK_TERMS = (
    "production", "deploy", "release", "security", "credential", "secret",
    "token", "auth", "oauth", "rls", "payment", "checkout", "stripe",
    "money", "delete", "close", "merge", "migration", "schema", "database",
    "governance", "rights", "license", "webhook", "provider",
)


class GH:
    def __init__(self, repo: str, token: str | None = None) -> None:
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            raise RuntimeError("github_token_required")

    def req(self, method: str, path: str, body: Any | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "PentaTagger/2.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} -> {exc.code}: {raw[:500]}") from exc

    def get(self, path: str) -> Any:
        return self.req("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def delete(self, path: str) -> Any:
        return self.req("DELETE", path)

    def paginate(
        self,
        path: str,
        *,
        list_key: str | None = None,
        max_pages: int = MAX_PAGES,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            payload = self.get(f"{path}{separator}page={page}")
            batch = payload.get(list_key, []) if list_key else payload
            if not isinstance(batch, list):
                raise RuntimeError(f"pagination_expected_list:{path}")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items


@dataclass(frozen=True)
class Entity:
    number: int
    kind: str
    title: str
    body: str
    state: str
    merged: bool
    draft: bool
    labels: set[str]
    files: tuple[str, ...]
    html_url: str


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _contains_keyword(text: str, keyword: str) -> bool:
    if len(keyword) <= 3 and keyword.isalnum():
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def classify_lanes(title: str, body: str, files: tuple[str, ...]) -> list[str]:
    text = f"{title}\n{body}".lower()
    scores = {lane: 0 for lane in LANE_KEYWORDS}

    for lane, keywords in LANE_KEYWORDS.items():
        for keyword in keywords:
            if _contains_keyword(text, keyword):
                scores[lane] += 1

    for raw_path in files:
        path = raw_path.lower()
        suffix = Path(path).suffix
        if path.startswith(("docs/", "documentation/")) or suffix in {".md", ".mdx", ".rst"}:
            scores["docs"] += 3
        if path.startswith(".github/workflows/") or "workflow" in path or "actions" in path:
            scores["workflow"] += 4
        if path.startswith("supabase/") or "migration" in path or suffix == ".sql":
            scores["database"] += 4
        if any(part in path for part in ("provider", "adapter", "integration", "webhook", "oauth")):
            scores["provider"] += 3
        if any(part in path for part in ("security", "credential", "secret", "auth", "rls", "policy")):
            scores["security"] += 3
        if any(part in path for part in ("commerce", "checkout", "payment", "stripe", "product", "license", "wallet")):
            scores["commerce"] += 3
        if any(part in path for part in ("media", "music", "video", "radio", "television", "publishing", "book", "sermon")):
            scores["media"] += 3
        if any(part in path for part in ("observability", "logger", "error", "report", "alert", "metric", "trace")):
            scores["observability"] += 3

    selected = [
        lane
        for lane, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if score >= 2
    ][:4]
    return selected or ["general"]


def classify_risk(title: str, body: str, files: tuple[str, ...], lanes: list[str]) -> str:
    text = f"{title}\n{body}\n{' '.join(files)}".lower()
    if any(_contains_keyword(text, term) for term in HIGH_RISK_TERMS):
        return "d2"
    if {"security", "database", "provider", "commerce"}.intersection(lanes):
        return "d2"
    non_docs = [path for path in files if Path(path.lower()).suffix not in {".md", ".mdx", ".rst"}]
    if files and not non_docs and set(lanes).issubset({"docs", "general"}):
        return "d0"
    if {"workflow", "media", "observability"}.intersection(lanes) or non_docs:
        return "d1"
    return "d0"


def lifecycle_projection(entity: Entity) -> tuple[list[str], list[str]]:
    if entity.state == "closed":
        terminal = "penta:terminal:merged" if entity.merged else "penta:terminal:closed"
        return [], [terminal]
    if entity.kind == "issue":
        return ["penta:stage:open"], []
    for disposition, label in DISPOSITION_LABELS.items():
        if label in entity.labels:
            return [DISPOSITION_STAGE[disposition]], []
    if entity.draft:
        return ["penta:stage:nurture"], []
    return ["penta:stage:review"], []


def fetch_entity(gh: GH, number: int) -> Entity:
    issue = gh.get(f"/repos/{gh.repo}/issues/{number}")
    labels = {item["name"] for item in issue.get("labels", [])}
    if "pull_request" not in issue:
        return Entity(
            number=number,
            kind="issue",
            title=issue.get("title") or "",
            body=issue.get("body") or "",
            state=issue.get("state") or "open",
            merged=False,
            draft=False,
            labels=labels,
            files=(),
            html_url=issue.get("html_url") or "",
        )

    pr = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    files = tuple(
        item.get("filename", "")
        for item in gh.paginate(f"/repos/{gh.repo}/pulls/{number}/files?per_page=100")
        if item.get("filename")
    )
    return Entity(
        number=number,
        kind="pr",
        title=pr.get("title") or issue.get("title") or "",
        body=pr.get("body") or issue.get("body") or "",
        state=pr.get("state") or issue.get("state") or "open",
        merged=bool(pr.get("merged")),
        draft=bool(pr.get("draft")),
        labels=labels,
        files=files,
        html_url=pr.get("html_url") or issue.get("html_url") or "",
    )


def receipt_digest(material: dict[str, Any]) -> str:
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def find_receipt_comment(gh: GH, number: int) -> tuple[dict[str, Any] | None, str | None]:
    comments = gh.paginate(f"/repos/{gh.repo}/issues/{number}/comments?per_page=100")
    for comment in comments:
        body = comment.get("body") or ""
        if COMMENT_MARKER not in body:
            continue
        match = re.search(r"<!-- penta-github-tagger:(\{.*?\}) -->", body, re.S)
        if not match:
            return comment, None
        try:
            marker = json.loads(match.group(1))
            return comment, marker.get("digest")
        except json.JSONDecodeError:
            return comment, None
    return None, None


def save_receipt_comment(gh: GH, receipt: dict[str, Any]) -> str:
    number = int(receipt["number"])
    existing, old_digest = find_receipt_comment(gh, number)
    if old_digest == receipt["digest"]:
        return "unchanged"

    lanes = ", ".join(receipt["lanes"])
    stage = receipt["stage"] or receipt["terminal"] or "none"
    marker = json.dumps(
        {
            "digest": receipt["digest"],
            "number": number,
            "kind": receipt["kind"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    body = (
        f"{COMMENT_MARKER}{marker} -->\n\n"
        "**PentaTagger GitHub-native receipt**\n\n"
        f"- Entity: `{receipt['kind'].upper()} #{number}`\n"
        f"- Lanes: `{lanes}`\n"
        f"- Risk: `{receipt['risk'].upper()}`\n"
        f"- Lifecycle projection: `{stage}`\n"
        f"- Label readback: `PASS` ({len(receipt['readback_labels'])} labels visible)\n"
        f"- Receipt digest: `{receipt['digest']}`\n\n"
        "Authority boundary: PentaTagger classifies and verifies labels; "
        "PentaPR classifies lifecycle; PentaMerge and PentaCloser execute terminal actions."
    )
    if existing:
        gh.patch(f"/repos/{gh.repo}/issues/comments/{existing['id']}", {"body": body})
        return "updated"
    gh.post(f"/repos/{gh.repo}/issues/{number}/comments", {"body": body})
    return "created"


def tag_entity(gh: GH, number: int, *, dry_run: bool = False, comment: bool = True) -> dict[str, Any]:
    entity = fetch_entity(gh, number)
    lanes = classify_lanes(entity.title, entity.body, entity.files)
    risk = classify_risk(entity.title, entity.body, entity.files, lanes)
    stage_labels, terminal_labels = lifecycle_projection(entity)
    entity_labels = [f"penta:entity:{entity.kind}"]
    lane_labels = [f"penta:lane:{lane}" for lane in lanes]
    risk_labels = [f"penta:risk:{risk}"]
    core_labels = {"penta:tagged", "penta:authority:tagger"}

    expected = core_labels.union(entity_labels, lane_labels, risk_labels, stage_labels, terminal_labels)
    current = set(entity.labels)

    if not dry_run:
        ensure_labels(gh)
        current = reconcile_group(gh, number, current, entity_labels, ENTITY_PREFIXES)
        current = reconcile_group(gh, number, current, lane_labels, LANE_PREFIXES)
        current = reconcile_group(gh, number, current, risk_labels, RISK_PREFIXES)
        current = reconcile_group(gh, number, current, stage_labels, STAGE_PREFIXES)
        current = reconcile_group(gh, number, current, terminal_labels, TERMINAL_PREFIXES)
        missing_core = core_labels.difference(current)
        if missing_core:
            add_labels(gh, number, missing_core)
        current = read_labels(gh, number)
        missing = expected.difference(current)
        if missing:
            raise RuntimeError(f"label_readback_failed:{number}:{','.join(sorted(missing))}")
    else:
        current = current.union(expected)

    material = {
        "repo": gh.repo,
        "number": number,
        "kind": entity.kind,
        "state": entity.state,
        "merged": entity.merged,
        "lanes": lanes,
        "risk": risk,
        "stage": stage_labels[0] if stage_labels else None,
        "terminal": terminal_labels[0] if terminal_labels else None,
        "expected_labels": sorted(expected),
    }
    receipt = {
        **material,
        "observed_at": utc_now(),
        "readback_labels": sorted(current),
        "status": "DRY_RUN" if dry_run else "PASS",
        "digest": receipt_digest(material),
        "url": entity.html_url,
    }
    if comment and not dry_run:
        receipt["comment_state"] = save_receipt_comment(gh, receipt)
    else:
        receipt["comment_state"] = "disabled"
    return receipt


def target_from_event(event_path: str | None) -> int | None:
    if not event_path:
        return None
    path = Path(event_path)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("pull_request"), dict):
        return int(payload["pull_request"]["number"])
    if isinstance(payload.get("issue"), dict):
        return int(payload["issue"]["number"])
    return None


def sweep_numbers(gh: GH, kind: str, max_items: int) -> list[int]:
    issues = gh.paginate(f"/repos/{gh.repo}/issues?state=open&per_page=100&sort=updated&direction=desc")
    numbers: list[int] = []
    for issue in issues:
        is_pr = "pull_request" in issue
        if kind == "pr" and not is_pr:
            continue
        if kind == "issue" and is_pr:
            continue
        numbers.append(int(issue["number"]))
        if len(numbers) >= max_items:
            break
    return numbers


def write_outputs(receipts: list[dict[str, Any]], receipt_path: str | None, summary_path: str | None) -> None:
    payload = {
        "generated_at": utc_now(),
        "status": "PASS" if all(item["status"] in {"PASS", "DRY_RUN"} for item in receipts) else "FAIL",
        "count": len(receipts),
        "receipts": receipts,
    }
    if receipt_path:
        Path(receipt_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if summary_path:
        lines = [
            "## PentaTagger GitHub Native",
            "",
            f"- Entities processed: **{len(receipts)}**",
            f"- Readback status: **{payload['status']}**",
            "- Authority: classification/readback only; no merge or close authority",
            "",
            "| Entity | Risk | Lanes | Lifecycle | Digest |",
            "|---|---|---|---|---|",
        ]
        for receipt in receipts[:50]:
            lifecycle = receipt["stage"] or receipt["terminal"] or "none"
            lines.append(
                f"| {receipt['kind'].upper()} #{receipt['number']} | {receipt['risk'].upper()} | "
                f"{', '.join(receipt['lanes'])} | {lifecycle} | `{receipt['digest'][:12]}` |"
            )
        Path(summary_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["event", "sweep", "verify"])
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH"))
    parser.add_argument("--number", type=int)
    parser.add_argument("--kind", choices=["all", "pr", "issue"], default="all")
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-comment", action="store_true")
    parser.add_argument("--receipt-path")
    parser.add_argument("--summary-path")
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("repo_required")
    gh = GH(args.repo)

    if args.number:
        numbers = [args.number]
    elif args.mode == "event":
        target = target_from_event(args.event_path)
        numbers = [target] if target is not None else []
    elif args.mode in {"sweep", "verify"}:
        numbers = sweep_numbers(gh, args.kind, args.max_items)
    else:
        numbers = []

    receipts = [
        tag_entity(gh, number, dry_run=args.dry_run, comment=not args.no_comment)
        for number in numbers
    ]
    write_outputs(receipts, args.receipt_path, args.summary_path)
    print(json.dumps({"count": len(receipts), "receipts": receipts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
