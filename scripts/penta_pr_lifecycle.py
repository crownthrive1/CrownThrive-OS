#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

from penta_github_labels import (
    DISPOSITION_LABELS,
    DISPOSITION_STAGE,
    STAGE_PREFIXES,
    TERMINAL_PREFIXES,
    add_labels,
    ensure_labels,
    read_labels,
    reconcile_group,
    remove_label,
)

API = "https://api.github.com"
MARKER = "<!-- penta-pr-lifecycle:"
SELF_LIFECYCLE_CHECK_NAMES = frozenset({"run / lifecycle"})
PRECLOSE_REQUIRED_LABELS = frozenset(
    {
        "penta:tagged",
        "penta:authority:tagger",
        "penta:entity:pr",
        "penta:authority:pr",
        "penta:close",
        "penta:stage:close-candidate",
    }
)


class GH:
    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.token = os.environ["GITHUB_TOKEN"]

    def req(self, method: str, path: str, body: Any | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "PentaPR/2.0.2",
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

    def put(self, path: str, body: Any) -> Any:
        return self.req("PUT", path, body)

    def delete(self, path: str) -> Any:
        return self.req("DELETE", path)

    def paginate(self, path: str, *, list_key: str | None = None, max_pages: int = 10) -> list[dict[str, Any]]:
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


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_self_lifecycle_check(item: dict[str, Any]) -> bool:
    name = str(item.get("name") or "").strip().casefold()
    return name in SELF_LIFECYCLE_CHECK_NAMES


def checks(gh: GH, sha: str) -> dict[str, Any]:
    observed = gh.get(f"/repos/{gh.repo}/commits/{sha}/check-runs?per_page=100").get("check_runs", [])
    statuses = gh.get(f"/repos/{gh.repo}/commits/{sha}/status")
    ignored = [item for item in observed if _is_self_lifecycle_check(item)]
    runs = [item for item in observed if not _is_self_lifecycle_check(item)]
    bad = {"failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}
    pending = any(item.get("status") != "completed" for item in runs) or statuses.get("state") == "pending"
    failed = any(item.get("conclusion") in bad for item in runs) or statuses.get("state") in {"failure", "error"}
    governed = [item for item in runs if "governed merge gate" in (item.get("name") or "").lower()]
    governed_ok = any(item.get("status") == "completed" and item.get("conclusion") == "success" for item in governed)
    return {
        "failed": failed,
        "pending": pending,
        "governed_ok": governed_ok,
        "count": len(runs),
        "observed_count": len(observed),
        "ignored_self_count": len(ignored),
    }


def lifecycle_comment(gh: GH, number: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    comments = gh.paginate(f"/repos/{gh.repo}/issues/{number}/comments?per_page=100")
    for comment in comments:
        body = comment.get("body") or ""
        if MARKER not in body:
            continue
        match = re.search(r"<!-- penta-pr-lifecycle:(\{.*?\}) -->", body, re.S)
        if match:
            try:
                return comment, json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return None, None


def save_state(gh: GH, number: int, state: dict[str, Any]) -> None:
    body = (
        f"{MARKER}{json.dumps(state, separators=(',', ':'))} -->\n\n"
        f"PentaPR lifecycle control. Hard terminal deadline: **{state['deadline_at']}**. "
        f"Current disposition: **{state['disposition']}**. "
        "PentaTagger supplies semantic labels; PentaMerge/PentaCloser retain terminal authority."
    )
    comment, _ = lifecycle_comment(gh, number)
    if comment:
        gh.patch(f"/repos/{gh.repo}/issues/comments/{comment['id']}", {"body": body})
    else:
        gh.post(f"/repos/{gh.repo}/issues/{number}/comments", {"body": body})


def set_labels(gh: GH, number: int, disposition: str) -> set[str]:
    current = read_labels(gh, number)
    desired_disposition = DISPOSITION_LABELS[disposition]
    for old in DISPOSITION_LABELS.values():
        if old in current and old != desired_disposition:
            remove_label(gh, number, old)
            current.discard(old)

    current = reconcile_group(
        gh,
        number,
        current,
        [DISPOSITION_STAGE[disposition]],
        STAGE_PREFIXES,
    )
    additive = {desired_disposition, "penta:deadline-12h", "penta:authority:pr"}
    missing = additive.difference(current)
    if missing:
        add_labels(gh, number, missing)
        current.update(missing)
    return current


def require_preclose_readback(
    gh: GH,
    number: int,
    *,
    lifecycle_head_sha: str | None,
    expected_head_sha: str | None,
) -> set[str]:
    if not lifecycle_head_sha or not expected_head_sha or lifecycle_head_sha != expected_head_sha:
        raise RuntimeError(
            f"preclose_lifecycle_head_stale:{number}:"
            f"lifecycle={lifecycle_head_sha or 'missing'}:expected={expected_head_sha or 'missing'}"
        )

    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    observed_head_sha = ((pull.get("head") or {}).get("sha"))
    if pull.get("state") != "open":
        raise RuntimeError(f"preclose_pr_not_open:{number}:{pull.get('state') or 'unknown'}")
    if observed_head_sha != expected_head_sha:
        raise RuntimeError(
            f"preclose_head_changed:{number}:expected={expected_head_sha}:observed={observed_head_sha or 'missing'}"
        )

    readback = read_labels(gh, number)
    if "penta:hold" in readback:
        raise RuntimeError(f"preclose_hold_detected:{number}")

    missing = PRECLOSE_REQUIRED_LABELS.difference(readback)
    if missing:
        raise RuntimeError(f"preclose_label_readback_failed:{number}:{','.join(sorted(missing))}")
    return readback


def mark_terminal(gh: GH, number: int, terminal: str, authority: str) -> None:
    current = read_labels(gh, number)
    current = reconcile_group(gh, number, current, [], STAGE_PREFIXES)
    current = reconcile_group(gh, number, current, [terminal], TERMINAL_PREFIXES)
    if authority not in current:
        add_labels(gh, number, [authority])
    readback = read_labels(gh, number)
    required = {terminal, authority}
    missing = required.difference(readback)
    if missing:
        raise RuntimeError(f"terminal_label_readback_failed:{number}:{','.join(sorted(missing))}")


def classify(gh: GH, pr: dict[str, Any]) -> tuple[str, str]:
    number = pr["number"]
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    labels = read_labels(gh, number)
    if "penta:hold" in labels:
        return "NURTURE", "operator_hold"
    text = ((pull.get("title") or "") + "\n" + (pull.get("body") or "")).lower()
    if "superseded by" in text or "represented-zero-delta" in text:
        return "CLOSE", "superseded_or_represented"
    if pull.get("draft"):
        return "NURTURE", "draft"
    if pull.get("mergeable") is False or pull.get("mergeable_state") in {"dirty", "behind"}:
        return "RESTACK", pull.get("mergeable_state") or "not_mergeable"
    check_state = checks(gh, pull["head"]["sha"])
    if check_state["failed"]:
        return "NURTURE", "checks_failed"
    if check_state["pending"]:
        return "NURTURE", "checks_pending"
    if pull.get("mergeable") is True and check_state["governed_ok"]:
        return "MERGE", "mergeable_governed_green"
    return "NURTURE", "awaiting_governed_merge_gate"


def open_pull_requests(gh: GH, number: int | None = None) -> list[dict[str, Any]]:
    if number is not None:
        pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
        return [pull] if pull.get("state") == "open" else []
    return gh.paginate(f"/repos/{gh.repo}/pulls?state=open&per_page=100&sort=created&direction=asc")


def pentapr(gh: GH, number: int | None = None) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    pull_requests = open_pull_requests(gh, number)
    for pr in pull_requests:
        _, state = lifecycle_comment(gh, pr["number"])
        if not state:
            state = {
                "first_seen_at": iso(now),
                "deadline_at": iso(now + dt.timedelta(hours=12)),
                "disposition": "NURTURE",
                "reason": "first_seen",
                "head_sha": pr["head"]["sha"],
            }
        disposition, reason = classify(gh, pr)
        state.update(
            {
                "disposition": disposition,
                "reason": reason,
                "head_sha": pr["head"]["sha"],
                "updated_at": iso(now),
            }
        )
        set_labels(gh, pr["number"], disposition)
        save_state(gh, pr["number"], state)
        print(f"PentaPR #{pr['number']} {disposition} {reason} deadline={state['deadline_at']}")


def attempt_merge(gh: GH, number: int) -> tuple[bool, str]:
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    labels = read_labels(gh, number)
    if "penta:hold" in labels:
        return False, "operator_hold"
    check_state = checks(gh, pull["head"]["sha"])
    if (
        pull.get("draft")
        or pull.get("mergeable") is not True
        or check_state["failed"]
        or check_state["pending"]
        or not check_state["governed_ok"]
    ):
        return False, "not_currently_merge_eligible"
    result = gh.put(
        f"/repos/{gh.repo}/pulls/{number}/merge",
        {
            "merge_method": "squash",
            "sha": pull["head"]["sha"],
            "commit_title": f"PentaMerge: {pull['title']}",
        },
    )
    merged = bool(result.get("merged"))
    if merged:
        mark_terminal(gh, number, "penta:terminal:merged", "penta:authority:merge")
    return merged, result.get("message", "merge_attempted")


def pentamerge(gh: GH, number: int | None = None) -> None:
    pull_requests = open_pull_requests(gh, number)
    for pr in pull_requests:
        labels = read_labels(gh, pr["number"])
        if "penta:merge" not in labels:
            continue
        merged, message = attempt_merge(gh, pr["number"])
        print(f"PentaMerge #{pr['number']} merged={merged} {message}")


def pentacloser(gh: GH, number: int | None = None) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    pull_requests = open_pull_requests(gh, number)
    for pr in pull_requests:
        number = pr["number"]
        labels = read_labels(gh, number)
        if "penta:hold" in labels:
            print(f"PentaCloser #{number} terminal=HELD")
            continue
        _, state = lifecycle_comment(gh, number)
        if not state or now < parse_iso(state["deadline_at"]):
            continue

        expected_head_sha = ((pr.get("head") or {}).get("sha"))
        lifecycle_head_sha = state.get("head_sha")
        if lifecycle_head_sha != expected_head_sha:
            raise RuntimeError(
                f"preclose_lifecycle_head_stale:{number}:"
                f"lifecycle={lifecycle_head_sha or 'missing'}:expected={expected_head_sha or 'missing'}"
            )

        merged, message = attempt_merge(gh, number)
        if merged:
            print(f"PentaCloser #{number} terminal=MERGED")
            continue

        state.update(
            {
                "disposition": "CLOSE",
                "reason": "hard_deadline_expired",
                "updated_at": iso(now),
            }
        )
        set_labels(gh, number, "CLOSE")
        save_state(gh, number, state)
        readback = require_preclose_readback(
            gh,
            number,
            lifecycle_head_sha=lifecycle_head_sha,
            expected_head_sha=expected_head_sha,
        )
        gh.post(
            f"/repos/{gh.repo}/issues/{number}/comments",
            {
                "body": (
                    "PentaCloser terminal disposition at the 12-hour hard limit. "
                    "This PR did not satisfy current exact-head merge requirements and is being closed, "
                    "not force-merged. Fresh GitHub provider readback confirmed "
                    "`penta:tagged`, `penta:close`, and `penta:stage:close-candidate` "
                    f"on exact head `{expected_head_sha}` before closure "
                    f"({len(readback)} total labels visible). Merge attempt: `{message}`. "
                    "History and branch provenance remain preserved."
                )
            },
        )
        gh.patch(f"/repos/{gh.repo}/pulls/{number}", {"state": "closed"})
        mark_terminal(gh, number, "penta:terminal:closed", "penta:authority:closer")
        print(f"PentaCloser #{number} terminal=CLOSED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["pr", "merge", "closer"])
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    parser.add_argument("--number", type=int)
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("repo_required")
    gh = GH(args.repo)
    ensure_labels(gh)
    {"pr": pentapr, "merge": pentamerge, "closer": pentacloser}[args.mode](gh, args.number)
    return 0


if __name__ == "__main__":
    sys.exit(main())
