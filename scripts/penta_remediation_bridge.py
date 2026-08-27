#!/usr/bin/env python3
"""PentaCrawler/PentaFlows/PentaHelper durable PR remediation bridge.

The bridge observes the exact PR head, classifies every failed check into one or
more bounded remediation domains, persists a causal state record on the PR, and
executes only two explicitly safe provider actions:

1. GitHub update-branch source convergence for a same-repository PR whose base
   has advanced. This never force-pushes, rewrites history, or bypasses checks.
2. Provider-control-plane workflow dispatch when authoritative provider custody
   evidence must be refreshed. The provider workflow retains its own credentials,
   policy, and certification gates.

All other repair classes remain HOLD with an explicit owner/action. The bridge
never marks a check successful, never removes HOLD, never makes a draft ready,
never merges, and never grants D3 or provider authority.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from runtime.penta_hold_remediation import CheckFailure, DEFAULT_ROUTES

API = "https://api.github.com"
MARKER = "<!-- penta-remediation-bridge:"
SCHEMA = "ct.penta.remediation-bridge.20260827.v1"
BAD = {"failure", "cancelled", "timed_out", "action_required", "stale", "startup_failure"}
PROVIDER_WORKFLOW = "penta-provider-control-plane.yml"
MAX_ROUTE_ATTEMPTS_PER_HEAD = 3


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


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
                "Authorization": "Bearer " + self.token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "PentaRemediationBridge/1.0.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} {path} -> {exc.code}: {raw[:1000]}") from exc

    def get(self, path: str) -> Any:
        return self.req("GET", path)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def put(self, path: str, body: Any) -> Any:
        return self.req("PUT", path, body)

    def paginate(self, path: str, *, max_pages: int = 10) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            batch = self.get(f"{path}{separator}page={page}")
            if not isinstance(batch, list):
                raise RuntimeError(f"pagination_expected_list:{path}")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items


@dataclass(frozen=True)
class RoutePlan:
    fingerprint: str
    check_name: str
    route_id: str
    owner_penta: str
    disposition: str
    helper_action: str
    attempt: int


class PentaCrawler:
    def __init__(self, gh: GH) -> None:
        self.gh = gh

    @staticmethod
    def _context(item: dict[str, Any]) -> tuple[str, str]:
        app = item.get("app") or {}
        return (
            str(app.get("slug") or app.get("name") or "unknown-app").casefold(),
            str(item.get("name") or "").strip().casefold(),
        )

    @staticmethod
    def _recency(item: dict[str, Any]) -> tuple[int, str, str]:
        try:
            run_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            run_id = 0
        return run_id, str(item.get("completed_at") or ""), str(item.get("started_at") or "")

    def latest_checks(self, sha: str) -> list[dict[str, Any]]:
        payload = self.gh.get(f"/repos/{self.gh.repo}/commits/{sha}/check-runs?per_page=100")
        observed = payload.get("check_runs", [])
        latest: dict[tuple[str, str], dict[str, Any]] = {}
        for item in observed:
            key = self._context(item)
            current = latest.get(key)
            if current is None or self._recency(item) > self._recency(current):
                latest[key] = item
        return list(latest.values())

    def crawl(self, number: int) -> tuple[dict[str, Any], list[CheckFailure]]:
        pull = self.gh.get(f"/repos/{self.gh.repo}/pulls/{number}")
        if pull.get("state") != "open":
            raise RuntimeError(f"pr_not_open:{number}")
        head_sha = str((pull.get("head") or {}).get("sha") or "")
        if not head_sha:
            raise RuntimeError(f"pr_head_missing:{number}")
        failures: list[CheckFailure] = []
        for item in self.latest_checks(head_sha):
            if item.get("status") != "completed" or item.get("conclusion") not in BAD:
                continue
            output = item.get("output") or {}
            summary = "\n".join(
                str(value or "")
                for value in (output.get("title"), output.get("summary"), output.get("text"))
                if value
            )
            failures.append(
                CheckFailure(
                    name=str(item.get("name") or "unknown-check"),
                    conclusion=str(item.get("conclusion") or "failure"),
                    summary=summary[:12000],
                )
            )
        return pull, failures


class PentaFlows:
    @staticmethod
    def _base_fingerprint(repo: str, number: int, head_sha: str, failure: CheckFailure) -> str:
        material = f"{repo.casefold()}|{number}|{head_sha}|{failure.name.casefold()}|{failure.normalized_signature()}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def route(
        self,
        *,
        repo: str,
        number: int,
        head_sha: str,
        failures: list[CheckFailure],
        attempts: dict[str, int],
    ) -> tuple[list[RoutePlan], list[dict[str, Any]]]:
        plans: list[RoutePlan] = []
        escalations: list[dict[str, Any]] = []
        for failure in failures:
            matched = [route for route in DEFAULT_ROUTES if route.matches(failure)]
            if not matched:
                escalations.append({"check": failure.name, "reason": "unclassified", "owner": "PentaTriage"})
                continue
            base = self._base_fingerprint(repo, number, head_sha, failure)
            for route in matched:
                fingerprint = hashlib.sha256(f"{base}|{route.route_id}".encode("utf-8")).hexdigest()
                attempt = int(attempts.get(fingerprint, 0)) + 1
                if attempt > MAX_ROUTE_ATTEMPTS_PER_HEAD:
                    escalations.append(
                        {
                            "check": failure.name,
                            "route_id": route.route_id,
                            "owner": "PentaTriage",
                            "reason": "attempt_cap",
                            "fingerprint": fingerprint,
                        }
                    )
                    continue
                attempts[fingerprint] = attempt
                plans.append(
                    RoutePlan(
                        fingerprint=fingerprint,
                        check_name=failure.name,
                        route_id=route.route_id,
                        owner_penta=route.owner_penta,
                        disposition="AUTO_REMEDIATE" if route.safe_to_autoremediate else "EVIDENCE_REQUIRED",
                        helper_action=route.helper_action,
                        attempt=attempt,
                    )
                )
        return plans, escalations


class PentaHelper:
    def __init__(self, gh: GH) -> None:
        self.gh = gh

    def current_base_sha(self, pull: dict[str, Any]) -> str:
        base = pull.get("base") or {}
        ref = urllib.parse.quote(str(base.get("ref") or "main"), safe="")
        branch = self.gh.get(f"/repos/{self.gh.repo}/branches/{ref}")
        return str((branch.get("commit") or {}).get("sha") or "")

    def converge_source(self, pull: dict[str, Any], *, current_base_sha: str) -> dict[str, Any]:
        number = int(pull["number"])
        head = pull.get("head") or {}
        base = pull.get("base") or {}
        head_repo = (head.get("repo") or {}).get("full_name")
        base_repo = (base.get("repo") or {}).get("full_name")
        head_sha = str(head.get("sha") or "")
        recorded_base_sha = str(base.get("sha") or "")
        if head_repo != base_repo or base_repo != self.gh.repo:
            return {"action": "source_convergence", "status": "HOLD", "reason": "fork_or_cross_repo"}
        if not current_base_sha or current_base_sha == recorded_base_sha:
            return {"action": "source_convergence", "status": "NOOP", "reason": "base_not_advanced"}
        try:
            result = self.gh.put(
                f"/repos/{self.gh.repo}/pulls/{number}/update-branch",
                {"expected_head_sha": head_sha},
            )
            return {
                "action": "source_convergence",
                "status": "DISPATCHED",
                "old_head_sha": head_sha,
                "old_base_sha": recorded_base_sha,
                "current_base_sha": current_base_sha,
                "message": result.get("message"),
            }
        except RuntimeError as exc:
            return {
                "action": "source_convergence",
                "status": "HOLD",
                "reason": "update_branch_rejected",
                "error": str(exc)[:1000],
            }

    def refresh_provider_evidence(self, pull: dict[str, Any], *, already_dispatched: bool) -> dict[str, Any]:
        if already_dispatched:
            return {"action": "provider_evidence_refresh", "status": "NOOP", "reason": "already_dispatched_for_head"}
        ref = str((pull.get("base") or {}).get("ref") or "main")
        self.gh.post(
            f"/repos/{self.gh.repo}/actions/workflows/{PROVIDER_WORKFLOW}/dispatches",
            {"ref": ref},
        )
        return {"action": "provider_evidence_refresh", "status": "DISPATCHED", "workflow": PROVIDER_WORKFLOW, "ref": ref}


class DurableState:
    def __init__(self, gh: GH, number: int) -> None:
        self.gh = gh
        self.number = number
        self.comment: dict[str, Any] | None = None
        self.state: dict[str, Any] = {
            "schema": SCHEMA,
            "attempts": {},
            "events": [],
            "provider_dispatch_heads": [],
        }
        self._load()

    def _load(self) -> None:
        comments = self.gh.paginate(f"/repos/{self.gh.repo}/issues/{self.number}/comments?per_page=100")
        for comment in comments:
            body = str(comment.get("body") or "")
            if MARKER not in body:
                continue
            match = re.search(r"<!-- penta-remediation-bridge:(\{.*?\}) -->", body, re.S)
            if not match:
                continue
            try:
                loaded = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if loaded.get("schema") == SCHEMA:
                self.comment = comment
                self.state = loaded
                self.state.setdefault("attempts", {})
                self.state.setdefault("events", [])
                self.state.setdefault("provider_dispatch_heads", [])
                return

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        previous_hash = self.state["events"][-1]["event_hash"] if self.state["events"] else "GENESIS"
        event = {
            "sequence": len(self.state["events"]) + 1,
            "kind": kind,
            "at": utc_now(),
            "previous_hash": previous_hash,
            "payload": payload,
        }
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
        event["event_hash"] = hashlib.sha256(encoded).hexdigest()
        self.state["events"].append(event)
        self.state["events"] = self.state["events"][-200:]

    def save(self, *, head_sha: str, plans: list[RoutePlan], escalations: list[dict[str, Any]], actions: list[dict[str, Any]]) -> None:
        self.state.update(
            {
                "head_sha": head_sha,
                "updated_at": utc_now(),
                "plans": [asdict(plan) for plan in plans],
                "escalations": escalations,
                "last_actions": actions,
                "merge_authority_granted": False,
                "draft_state_changed": False,
                "check_conclusions_mutated": False,
            }
        )
        marker = f"{MARKER}{json.dumps(self.state, separators=(',', ':'))} -->"
        summary = (
            f"{marker}\n\n"
            "### Penta self-remediation control\n\n"
            f"Exact head: `{head_sha}`  \n"
            f"Routed remediation domains: **{len(plans)}**  \n"
            f"Escalations: **{len(escalations)}**  \n"
            "Authority boundary: **HOLD remains authoritative until exact-head checks independently pass.** "
            "This control cannot mark checks green, remove governance, make a draft ready, or merge the PR."
        )
        if self.comment:
            self.gh.patch(f"/repos/{self.gh.repo}/issues/comments/{self.comment['id']}", {"body": summary})
        else:
            created = self.gh.post(f"/repos/{self.gh.repo}/issues/{self.number}/comments", {"body": summary})
            self.comment = created


def remediate(gh: GH, number: int) -> dict[str, Any]:
    crawler = PentaCrawler(gh)
    flows = PentaFlows()
    helper = PentaHelper(gh)
    durable = DurableState(gh, number)
    pull, failures = crawler.crawl(number)
    head_sha = str((pull.get("head") or {}).get("sha") or "")
    durable.event("HOLD_SCAN", {"head_sha": head_sha, "failure_count": len(failures)})

    if not failures:
        durable.event("HOLD_CLEAR_CANDIDATE", {"head_sha": head_sha, "penta_pr_handoff": True})
        durable.save(head_sha=head_sha, plans=[], escalations=[], actions=[])
        return {"status": "NO_FAILED_CHECKS", "head_sha": head_sha, "merge_authority_granted": False}

    plans, escalations = flows.route(
        repo=gh.repo,
        number=number,
        head_sha=head_sha,
        failures=failures,
        attempts=durable.state["attempts"],
    )
    for plan in plans:
        durable.event("REMEDIATION_ROUTED", asdict(plan))
    for escalation in escalations:
        durable.event("REMEDIATION_ESCALATED", escalation)

    actions: list[dict[str, Any]] = []
    current_base_sha = helper.current_base_sha(pull)
    if any(plan.route_id == "family-interoperability" and plan.disposition == "AUTO_REMEDIATE" for plan in plans):
        action = helper.converge_source(pull, current_base_sha=current_base_sha)
        actions.append(action)
        durable.event("SOURCE_CONVERGENCE", action)

    if any(plan.route_id == "provider-convergence" for plan in plans):
        already = head_sha in set(durable.state.get("provider_dispatch_heads", []))
        action = helper.refresh_provider_evidence(pull, already_dispatched=already)
        actions.append(action)
        durable.event("PROVIDER_EVIDENCE_REFRESH", action)
        if action.get("status") == "DISPATCHED":
            durable.state.setdefault("provider_dispatch_heads", []).append(head_sha)

    for plan in plans:
        if plan.route_id not in {"family-interoperability", "provider-convergence"}:
            action = {
                "action": "bounded_owner_handoff",
                "status": "HOLD",
                "route_id": plan.route_id,
                "owner_penta": plan.owner_penta,
                "instruction": plan.helper_action,
            }
            actions.append(action)
            durable.event("BOUNDED_OWNER_HANDOFF", action)

    durable.save(head_sha=head_sha, plans=plans, escalations=escalations, actions=actions)
    return {
        "status": "REMEDIATION_ROUTED",
        "head_sha": head_sha,
        "failure_count": len(failures),
        "route_count": len(plans),
        "actions": actions,
        "escalations": escalations,
        "merge_authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded Penta PR self-remediation")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")
    result = remediate(GH(args.repo), args.number)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
