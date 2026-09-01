#!/usr/bin/env python3
"""PentaOverlay: governed repository-resource reconciliation for CrownThrive OS.

The runtime is intentionally fail-closed. It can observe without provider-write
authority, but it will not claim a mutation or production PASS unless the
provider write/readback actually succeeds.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REGISTRY_PATH = Path(".crownthrive/resources/repository-resources.v1.json")
CONTRACT = "ct.penta.overlay.v1"
RECEIPT_SCHEMA = "ct.penta.overlay.receipt.v1"
SAFE_REFERENCE_POLICY = "PURE_REFERENCE_FAST_FORWARD"
MANAGED_OVERLAY_POLICY = "CROWNTHRIVE_OVERLAY_GOVERNED_MERGE"
REFERENCE_CLASS = "REFERENCE_FORK"
OVERLAY_CLASS = "MANAGED_OVERLAY_FORK"
FIRST_PARTY_CLASSES = {"FIRST_PARTY_SOURCE", "FIRST_PARTY_EMPTY_PLACEHOLDER"}

UPSTREAM_WORKFLOW_HINTS = (
    "upstream-auto-merge",
    "upstream-follow",
    "upstream-sync",
    "upstream-convergence",
    "sync-upstream",
)


class PentaOverlayError(RuntimeError):
    pass


class ProviderError(PentaOverlayError):
    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class CompareState:
    status: str
    ahead_by: int
    behind_by: int

    @property
    def reference_fast_forward_eligible(self) -> bool:
        # base=fork head, head=upstream head
        return self.behind_by == 0 and self.status in {"ahead", "identical"}


class GitHubClient:
    def __init__(self, token: str | None, api_url: str = "https://api.github.com"):
        self.token = token or ""
        self.api_url = api_url.rstrip("/")

    @property
    def authenticated(self) -> bool:
        return bool(self.token)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"{self.api_url}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CrownThrive-PentaOverlay/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body).get("message", body)
            except json.JSONDecodeError:
                detail = body
            raise ProviderError(exc.code, f"GitHub {method} {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(None, f"GitHub {method} {path}: {exc.reason}") from exc

    def get_repo(self, repo: str) -> dict[str, Any]:
        return self._request("GET", f"/repos/{repo}")

    def get_branch(self, repo: str, branch: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(branch, safe="")
        return self._request("GET", f"/repos/{repo}/branches/{quoted}")

    def get_head(self, repo: str, branch: str) -> str:
        return str(self.get_branch(repo, branch)["commit"]["sha"])

    def compare(self, repo: str, base: str, head: str) -> CompareState:
        b = urllib.parse.quote(base, safe=":")
        h = urllib.parse.quote(head, safe=":")
        data = self._request("GET", f"/repos/{repo}/compare/{b}...{h}")
        return CompareState(
            status=str(data.get("status", "unknown")),
            ahead_by=int(data.get("ahead_by", 0)),
            behind_by=int(data.get("behind_by", 0)),
        )

    def update_ref_fast_forward(self, repo: str, branch: str, sha: str) -> None:
        quoted = urllib.parse.quote(branch, safe="/")
        self._request(
            "PATCH",
            f"/repos/{repo}/git/refs/heads/{quoted}",
            {"sha": sha, "force": False},
        )

    def list_workflows(self, repo: str, branch: str) -> list[dict[str, Any]]:
        quoted_ref = urllib.parse.quote(branch, safe="")
        try:
            data = self._request("GET", f"/repos/{repo}/contents/.github/workflows?ref={quoted_ref}")
        except ProviderError as exc:
            if exc.status == 404:
                return []
            raise
        return data if isinstance(data, list) else []

    def dispatch_workflow(self, repo: str, workflow: str | int, ref: str) -> None:
        wid = urllib.parse.quote(str(workflow), safe="")
        self._request("POST", f"/repos/{repo}/actions/workflows/{wid}/dispatches", {"ref": ref})

    def get_ref(self, repo: str, branch: str) -> dict[str, Any] | None:
        quoted = urllib.parse.quote(branch, safe="/")
        try:
            return self._request("GET", f"/repos/{repo}/git/ref/heads/{quoted}")
        except ProviderError as exc:
            if exc.status == 404:
                return None
            raise

    def create_branch(self, repo: str, branch: str, sha: str) -> None:
        self._request("POST", f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})

    def merge_into_branch(self, repo: str, base_branch: str, head_sha: str, message: str) -> dict[str, Any] | None:
        return self._request(
            "POST",
            f"/repos/{repo}/merges",
            {"base": base_branch, "head": head_sha, "commit_message": message},
        )

    def list_open_pulls(self, repo: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/repos/{repo}/pulls?state=open&per_page=100") or []

    def create_pull(self, repo: str, title: str, head: str, base: str, body: str) -> dict[str, Any]:
        return self._request("POST", f"/repos/{repo}/pulls", {"title": title, "head": head, "base": base, "body": body})


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != "ct.repository-resource-registry.v1":
        raise PentaOverlayError("unexpected repository-resource registry contract")
    if not isinstance(data.get("resources"), list):
        raise PentaOverlayError("repository-resource registry resources must be a list")
    return data


def is_supabase_reference(resource: dict[str, Any]) -> bool:
    repo = str(resource.get("repository", "")).lower()
    return (
        repo in {"crownthrive1/supabase", "crownthrive1/thivebase-supabase-"}
        or resource.get("role") == "supabase_platform_reference"
    )


def enforce_static_authority_invariants(resource: dict[str, Any]) -> None:
    if resource.get("may_grant_provider_or_d3_authority") is not False:
        raise PentaOverlayError(f"{resource.get('repository')}: authority-expansion invariant violated")
    if resource.get("resource_class") in {REFERENCE_CLASS, OVERLAY_CLASS}:
        if resource.get("authority") not in {"reference_only", "managed_overlay"}:
            raise PentaOverlayError(f"{resource.get('repository')}: fork authority classification invalid")
    if is_supabase_reference(resource):
        if resource.get("resource_class") != REFERENCE_CLASS:
            raise PentaOverlayError("Supabase platform reference must remain REFERENCE_FORK")
        if resource.get("authority") != "reference_only":
            raise PentaOverlayError("Supabase platform reference must remain reference_only")
        if resource.get("role") != "supabase_platform_reference":
            raise PentaOverlayError("Supabase platform reference role must remain supabase_platform_reference")


def discover_upstream_workflow(files: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = []
    for item in files:
        name = str(item.get("name", "")).lower()
        if any(hint in name for hint in UPSTREAM_WORKFLOW_HINTS):
            candidates.append(item)
    return sorted(candidates, key=lambda x: str(x.get("name", "")))[0] if candidates else None


def sync_state_from_compare(compare: CompareState, same_head: bool) -> str:
    if same_head:
        return "IDENTICAL"
    if compare.behind_by == 0 and compare.ahead_by > 0:
        return "UPSTREAM_AHEAD"
    if compare.behind_by > 0 and compare.ahead_by == 0:
        return "CROWNTHRIVE_AHEAD"
    if compare.behind_by > 0 and compare.ahead_by > 0:
        return "DIVERGED"
    return "UNKNOWN"


def material_projection(resource: dict[str, Any]) -> tuple[Any, ...]:
    keys = (
        "repository",
        "default_branch",
        "exact_head",
        "resource_class",
        "role",
        "authority",
        "state",
        "upstream_repository",
        "upstream_branch",
        "upstream_head",
        "sync_policy",
        "sync_state",
    )
    return tuple(resource.get(k) for k in keys)


class Reconciler:
    def __init__(
        self,
        client: GitHubClient,
        *,
        apply_reference_sync: bool = False,
        dispatch_managed_overlay: bool = False,
        prepare_managed_overlay: bool = False,
    ):
        self.client = client
        self.apply_reference_sync = apply_reference_sync
        self.dispatch_managed_overlay = dispatch_managed_overlay
        self.prepare_managed_overlay = prepare_managed_overlay

    def _observe_repo(self, repo: str) -> tuple[str, str]:
        meta = self.client.get_repo(repo)
        branch = str(meta["default_branch"])
        head = self.client.get_head(repo, branch)
        return branch, head

    def _reference(self, resource: dict[str, Any]) -> dict[str, Any]:
        repo = str(resource["repository"])
        upstream_repo = str(resource["upstream_repository"])
        fork_branch, fork_head = self._observe_repo(repo)
        upstream_branch, upstream_head = self._observe_repo(upstream_repo)

        compare = self.client.compare(upstream_repo, fork_head, upstream_head)
        eligible = compare.reference_fast_forward_eligible and fork_head != upstream_head
        action = "NONE"

        if eligible:
            if self.apply_reference_sync:
                if not self.client.authenticated:
                    action = "HOLD_PROVIDER_WRITE"
                else:
                    self.client.update_ref_fast_forward(repo, fork_branch, upstream_head)
                    readback = self.client.get_head(repo, fork_branch)
                    if readback != upstream_head:
                        raise PentaOverlayError(
                            f"{repo}: fast-forward readback mismatch {readback} != {upstream_head}"
                        )
                    fork_head = readback
                    action = "FAST_FORWARDED"
            else:
                action = "FAST_FORWARD_AVAILABLE"
        elif fork_head != upstream_head:
            action = "HOLD_DIVERGENT_OR_AHEAD"

        out = copy.deepcopy(resource)
        out["default_branch"] = fork_branch
        out["exact_head"] = fork_head
        out["upstream_branch"] = upstream_branch
        out["upstream_head"] = upstream_head
        out["sync_policy"] = SAFE_REFERENCE_POLICY
        out["sync_state"] = (
            "FAST_FORWARD_SYNCED" if action == "FAST_FORWARDED"
            else sync_state_from_compare(compare, fork_head == upstream_head)
        )
        return {
            "resource": out,
            "event": {
                "repository": repo,
                "class": REFERENCE_CLASS,
                "fork_head_before": resource.get("exact_head"),
                "fork_head_after": fork_head,
                "upstream_head": upstream_head,
                "compare": {
                    "status": compare.status,
                    "ahead_by": compare.ahead_by,
                    "behind_by": compare.behind_by,
                },
                "zero_crownthrive_only_commits": compare.behind_by == 0,
                "fork_head_is_upstream_ancestor": compare.reference_fast_forward_eligible,
                "action": action,
            },
        }

    def _prepare_overlay_pr(
        self,
        repo: str,
        default_branch: str,
        fork_head: str,
        upstream_head: str,
    ) -> dict[str, Any]:
        owner = repo.split("/", 1)[0]
        branch = f"pentaoverlay/upstream-convergence-{upstream_head[:12]}"
        open_pulls = self.client.list_open_pulls(repo)
        for pr in open_pulls:
            head_ref = str(pr.get("head", {}).get("ref", ""))
            if head_ref.startswith("pentaoverlay/upstream-convergence-"):
                return {"action": "EXISTING_OVERLAY_PR", "pr_number": pr.get("number"), "branch": head_ref}

        if self.client.get_ref(repo, branch) is None:
            self.client.create_branch(repo, branch, fork_head)

        try:
            self.client.merge_into_branch(
                repo,
                branch,
                upstream_head,
                "PentaOverlay governed upstream convergence",
            )
        except ProviderError as exc:
            if exc.status == 409:
                return {"action": "HOLD_MERGE_CONFLICT", "branch": branch}
            raise

        pr = self.client.create_pull(
            repo,
            "PentaOverlay: governed upstream convergence",
            f"{owner}:{branch}",
            default_branch,
            (
                "Governed upstream convergence prepared by PentaOverlay. "
                "Preserve all CrownThrive commits and third-party provenance. "
                "No force-push, reset, rebase, provider authority, rights, certification, "
                "vote/quorum, money, credential, or D3 authority is created. "
                "Merge only after repository-local tests and exact-head readback."
            ),
        )
        return {"action": "PREPARED_OVERLAY_PR", "pr_number": pr.get("number"), "branch": branch}

    def _overlay(self, resource: dict[str, Any]) -> dict[str, Any]:
        repo = str(resource["repository"])
        upstream_repo = str(resource["upstream_repository"])
        fork_branch, fork_head = self._observe_repo(repo)
        upstream_branch, upstream_head = self._observe_repo(upstream_repo)

        compare = self.client.compare(upstream_repo, fork_head, upstream_head)
        upstream_changed = upstream_head != resource.get("upstream_head")
        action = "NONE"
        detail: dict[str, Any] = {}

        if upstream_changed:
            workflows = self.client.list_workflows(repo, fork_branch)
            workflow = discover_upstream_workflow(workflows)
            if workflow is not None:
                action = "UPSTREAM_WORKFLOW_PRESENT"
                detail["workflow"] = workflow.get("name")
                if self.dispatch_managed_overlay:
                    if not self.client.authenticated:
                        action = "HOLD_PROVIDER_WRITE"
                    else:
                        self.client.dispatch_workflow(repo, workflow.get("id") or workflow.get("name"), fork_branch)
                        action = "DISPATCHED_UPSTREAM_WORKFLOW"
            elif self.prepare_managed_overlay:
                if not self.client.authenticated:
                    action = "HOLD_PROVIDER_WRITE"
                else:
                    detail.update(self._prepare_overlay_pr(repo, fork_branch, fork_head, upstream_head))
                    action = str(detail.get("action"))
            else:
                action = "HOLD_NO_UPSTREAM_WORKFLOW"

        out = copy.deepcopy(resource)
        out["default_branch"] = fork_branch
        out["exact_head"] = fork_head
        out["upstream_branch"] = upstream_branch
        out["upstream_head"] = upstream_head
        out["sync_policy"] = MANAGED_OVERLAY_POLICY
        out["sync_state"] = sync_state_from_compare(compare, fork_head == upstream_head)

        return {
            "resource": out,
            "event": {
                "repository": repo,
                "class": OVERLAY_CLASS,
                "fork_head": fork_head,
                "upstream_head": upstream_head,
                "upstream_changed_since_registry": upstream_changed,
                "compare": {
                    "status": compare.status,
                    "ahead_by": compare.ahead_by,
                    "behind_by": compare.behind_by,
                },
                "action": action,
                **detail,
            },
        }

    def _first_party(self, resource: dict[str, Any]) -> dict[str, Any]:
        repo = str(resource["repository"])
        try:
            branch, head = self._observe_repo(repo)
            action = "OBSERVED"
        except ProviderError as exc:
            if resource.get("resource_class") == "FIRST_PARTY_EMPTY_PLACEHOLDER" and exc.status in {404, 409}:
                branch = str(resource.get("default_branch") or "main")
                head = resource.get("exact_head")
                action = "EMPTY_PLACEHOLDER"
            else:
                raise
        out = copy.deepcopy(resource)
        out["default_branch"] = branch
        out["exact_head"] = head
        return {
            "resource": out,
            "event": {
                "repository": repo,
                "class": resource.get("resource_class"),
                "head_before": resource.get("exact_head"),
                "head_after": head,
                "action": action,
            },
        }

    def reconcile(self, registry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        candidate = copy.deepcopy(registry)
        events: list[dict[str, Any]] = []
        projected: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for original in registry["resources"]:
            enforce_static_authority_invariants(original)
            try:
                klass = original.get("resource_class")
                if klass == REFERENCE_CLASS:
                    result = self._reference(original)
                elif klass == OVERLAY_CLASS:
                    result = self._overlay(original)
                elif klass in FIRST_PARTY_CLASSES:
                    result = self._first_party(original)
                else:
                    raise PentaOverlayError(f"{original.get('repository')}: unsupported resource class {klass}")
                projected.append(result["resource"])
                events.append(result["event"])
            except (ProviderError, PentaOverlayError) as exc:
                projected.append(copy.deepcopy(original))
                errors.append({
                    "repository": original.get("repository"),
                    "error": type(exc).__name__,
                    "detail": str(exc),
                })

        candidate["resources"] = projected
        candidate["repository_count"] = len(projected)
        candidate["fork_count"] = sum(
            1 for r in projected if r.get("resource_class") in {REFERENCE_CLASS, OVERLAY_CLASS}
        )
        candidate["observed_at"] = utc_now()

        changed = [
            r["repository"]
            for before, r in zip(registry["resources"], projected)
            if material_projection(before) != material_projection(r)
        ]

        meaningful = []
        for event in events:
            if event.get("action") in {
                "FAST_FORWARDED",
                "FAST_FORWARD_AVAILABLE",
                "HOLD_DIVERGENT_OR_AHEAD",
                "DISPATCHED_UPSTREAM_WORKFLOW",
                "PREPARED_OVERLAY_PR",
                "HOLD_MERGE_CONFLICT",
                "HOLD_NO_UPSTREAM_WORKFLOW",
                "HOLD_PROVIDER_WRITE",
            }:
                meaningful.append(event)
        if changed:
            meaningful.append({"action": "MATERIAL_REGISTRY_CHANGE", "repositories": changed})

        state = "PASS_OBSERVED"
        if errors:
            state = "HOLD"
        elif any(e.get("action", "").startswith("HOLD_") for e in events):
            state = "HOLD"
        elif any(e.get("action") in {"FAST_FORWARD_AVAILABLE"} for e in events):
            state = "HOLD_SYNC_AVAILABLE"

        receipt = {
            "schema": RECEIPT_SCHEMA,
            "contract": CONTRACT,
            "observed_at": candidate["observed_at"],
            "state": state,
            "provider_authenticated": self.client.authenticated,
            "material_registry_change": bool(changed),
            "changed_repositories": changed,
            "events": events,
            "meaningful_events": meaningful,
            "errors": errors,
            "authority_created": False,
            "third_party_authorship_promoted": False,
            "force_push_used": False,
            "reset_used": False,
            "rebase_used": False,
        }
        return candidate, receipt


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def self_test() -> dict[str, Any]:
    vectors = []

    safe = CompareState("ahead", ahead_by=3, behind_by=0)
    assert safe.reference_fast_forward_eligible
    vectors.append("safe_reference_fast_forward")

    divergent = CompareState("diverged", ahead_by=2, behind_by=1)
    assert not divergent.reference_fast_forward_eligible
    vectors.append("divergent_reference_blocks")

    ahead = CompareState("behind", ahead_by=0, behind_by=2)
    assert not ahead.reference_fast_forward_eligible
    vectors.append("crownthrive_ahead_reference_blocks")

    files = [{"name": "upstream-auto-merge.yml", "id": 1}, {"name": "ci.yml", "id": 2}]
    assert discover_upstream_workflow(files)["id"] == 1
    vectors.append("managed_overlay_prefers_repo_local_workflow")

    supabase = {
        "repository": "crownthrive1/Supabase",
        "resource_class": REFERENCE_CLASS,
        "role": "supabase_platform_reference",
        "authority": "reference_only",
        "may_grant_provider_or_d3_authority": False,
    }
    enforce_static_authority_invariants(supabase)
    vectors.append("supabase_reference_boundary")

    bad = dict(supabase)
    bad["authority"] = "canonical_source"
    try:
        enforce_static_authority_invariants(bad)
        raise AssertionError("bad Supabase authority should fail")
    except PentaOverlayError:
        pass
    vectors.append("supabase_authority_escalation_blocks")

    return {
        "schema": "ct.penta.overlay.self-test.v1",
        "state": "PASS",
        "vectors": vectors,
        "authority_created": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PentaOverlay repository-resource reconciler")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("self-test")

    rec = sub.add_parser("reconcile")
    rec.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    rec.add_argument("--registry-out", type=Path, required=True)
    rec.add_argument("--receipt-out", type=Path, required=True)
    rec.add_argument("--apply-reference-sync", action="store_true")
    rec.add_argument("--dispatch-managed-overlay", action="store_true")
    rec.add_argument("--prepare-managed-overlay", action="store_true")
    rec.add_argument("--token-env", default="PENTAOVERLAY_GITHUB_TOKEN")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "self-test":
        print(json.dumps(self_test(), sort_keys=True))
        return 0

    registry = load_registry(args.registry)
    token = os.environ.get(args.token_env) or None
    reconciler = Reconciler(
        GitHubClient(token),
        apply_reference_sync=args.apply_reference_sync,
        dispatch_managed_overlay=args.dispatch_managed_overlay,
        prepare_managed_overlay=args.prepare_managed_overlay,
    )
    candidate, receipt = reconciler.reconcile(registry)
    write_json(args.registry_out, candidate)
    write_json(args.receipt_out, receipt)
    print(json.dumps({
        "state": receipt["state"],
        "material_registry_change": receipt["material_registry_change"],
        "meaningful_events": len(receipt["meaningful_events"]),
        "errors": len(receipt["errors"]),
        "authority_created": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
