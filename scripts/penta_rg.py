#!/usr/bin/env python3
"""PentaRG™: CrownThrive Release Governance & Recovery.

Audits repository, release, provider, archive/restore, topology and Vercel
contracts. Mutations are policy-enumerated, reversible and receipt-producing.
PentaRG never manufactures PASS, weakens protection, rewrites history or reads
secret values.
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
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA = "ct.penta.rg.receipt.20260827.v1"
POLICY_SCHEMA = "ct.penta.rg.policy.20260827.v1"
TOPOLOGY_SCHEMA = "ct.penta.rg.topology.20260827.v1"
API = "https://api.github.com"
BAD = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)")
MARKER = "<!-- pentarg-control:"


class PentaRGError(RuntimeError):
    pass


class ProviderDeferred(PentaRGError):
    def __init__(self, message: str, reset_at: str | None = None):
        super().__init__(message)
        self.reset_at = reset_at


class RequestBudget:
    def __init__(self, maximum: int):
        if maximum < 1:
            raise ValueError("request budget must be positive")
        self.maximum, self.used = maximum, 0

    def consume(self):
        if self.used >= self.maximum:
            raise ProviderDeferred("provider_request_budget_exhausted")
        self.used += 1


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    scope: str
    detail: str
    authority: str = "D1"
    repair: str = "hold"
    reversible: bool = True


@dataclass(frozen=True)
class Action:
    action: str
    target: str
    authority: str
    reason: str
    apply_allowed: bool
    rollback: str
    metadata: Mapping[str, Any] | None = None


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def iso(value=None):
    return (value or utc_now()).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value):
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or dt.timezone.utc).astimezone(dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PentaRGError(f"json_object_required:{path}")
    return value


def founder_lease_active(policy, now=None):
    now = now or utc_now()
    lease = ((policy.get("authority") or {}).get("d3") or {}).get("founder_lease") or {}
    start, end = parse_time(lease.get("starts_at")), parse_time(lease.get("expires_at"))
    return bool(lease.get("enabled") is True and start and end and start <= now <= end)


def authority_allowed(policy, authority, now=None):
    authority = authority.upper()
    if authority in {"D0", "D1"}:
        return True
    if authority == "D2":
        return ((policy.get("authority") or {}).get("d2") or {}).get("mode") == "bounded_autonomous"
    return authority == "D3" and founder_lease_active(policy, now)


def action_pin(value):
    if value.startswith("./") or value.startswith("docker://"):
        return "local", None
    if "@" not in value:
        return "missing_ref", None
    ref = value.rsplit("@", 1)[1]
    return ("full_sha", ref) if FULL_SHA.fullmatch(ref) else ("floating_ref", ref)


def scan_workflow_text(path, text):
    findings = []
    for value in USES.findall(text):
        if action_pin(value)[0] in {"missing_ref", "floating_ref"}:
            findings.append(Finding("workflow_action_not_full_sha_pinned", "BLOCK", path, f"{value} is not full-SHA pinned", repair="pin_action"))
    if re.search(r"(?m)^\s*permissions:\s*write-all\s*$", text):
        findings.append(Finding("workflow_write_all_permissions", "BLOCK", path, "write-all violates least privilege", "D2", "reduce_permissions"))
    if "pull_request_target:" in text and "github.event.pull_request.head.sha" in text and any(v in text for v in ("contents: write", "actions: write", "pull-requests: write", "issues: write")):
        findings.append(Finding("untrusted_pr_target_checkout_with_write_authority", "BLOCK", path, "untrusted PR head cannot execute with write authority", "D3", "split_trusted_transport"))
    if "schedule:" in text and "concurrency:" not in text:
        findings.append(Finding("scheduled_workflow_without_concurrency", "WARN", path, "scheduled workflow lacks concurrency fencing", repair="add_concurrency"))
    return findings


def local_audit(root, policy, topology):
    root = Path(root).resolve()
    findings = []
    if policy.get("schema") != POLICY_SCHEMA:
        findings.append(Finding("policy_schema_drift", "BLOCK", "config/penta_rg_policy.json", "unexpected schema"))
    if topology.get("schema") != TOPOLOGY_SCHEMA:
        findings.append(Finding("topology_schema_drift", "BLOCK", "config/penta_rg_topology.json", "unexpected schema"))
    for rel in policy.get("required_paths", []):
        if not (root / str(rel)).exists():
            findings.append(Finding("required_path_missing", "BLOCK", str(rel), "required control-plane asset absent", repair="restore_from_canonical_history"))
    workflows = root / ".github/workflows"
    if workflows.exists():
        for path in sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")]):
            findings += scan_workflow_text(path.relative_to(root).as_posix(), path.read_text(encoding="utf-8", errors="replace"))
    generic = set((policy.get("archive") or {}).get("generic_workflow_paths") or [])
    for rel in sorted(generic):
        if (root / rel).exists():
            findings.append(Finding("unbound_generic_workflow_present", "BLOCK", rel, "generic workflow conflicts with registered topology", repair="archive_with_tombstone"))
    nodes = {str(n.get("id")) for n in topology.get("nodes", []) if isinstance(n, dict)}
    for item in sorted(set(policy.get("required_topology_nodes", [])) - nodes):
        findings.append(Finding("topology_node_missing", "BLOCK", item, "required interoperability node absent", repair="register_topology_node"))
    edges = {(str(e.get("from")), str(e.get("to"))) for e in topology.get("edges", []) if isinstance(e, dict)}
    for edge in policy.get("required_topology_edges", []):
        if isinstance(edge, list) and len(edge) == 2 and tuple(map(str, edge)) not in edges:
            findings.append(Finding("topology_edge_missing", "BLOCK", f"{edge[0]}->{edge[1]}", "required interoperability edge absent", repair="register_topology_edge"))
    for rel in (policy.get("vercel") or {}).get("required_files", []):
        if not (root / str(rel)).exists():
            findings.append(Finding("vercel_control_plane_file_missing", "BLOCK", str(rel), "Vercel source contract incomplete", repair="restore_vercel_control_plane"))
    blocks = sum(f.severity == "BLOCK" for f in findings)
    report = {"schema": SCHEMA, "kind": "local_audit", "observed_at": iso(), "status": "PASS" if not blocks else "HOLD", "mode": policy.get("mode"), "founder_d3_lease_active": founder_lease_active(policy), "findings": [asdict(f) for f in findings], "counts": {"block": blocks, "warn": sum(f.severity == "WARN" for f in findings), "total": len(findings)}, "mutation_performed": False, "pass_manufactured": False}
    report["receipt_sha256"] = digest(report)
    return report


def starter_pr_match(title, files, policy):
    allowed = set((policy.get("archive") or {}).get("generic_workflow_paths") or [])
    prefixes = tuple(str(v).casefold() for v in (policy.get("archive") or {}).get("generic_title_prefixes", []))
    return bool(files and len(set(files)) == len(files) and set(files) <= allowed and title.casefold().startswith(prefixes))


def file_fingerprint(files):
    return digest(sorted(set(map(str, files))))


def duplicate_groups(pulls):
    groups = {}
    for pull in pulls:
        if pull.get("files"):
            groups.setdefault(file_fingerprint(pull["files"]), []).append(int(pull["number"]))
    return [sorted(v) for v in groups.values() if len(v) > 1]


def classify_run_conclusion(value):
    value = str(value or "").casefold()
    if value in {"success", "neutral", "skipped"}:
        return "PASS", "none"
    if value == "action_required":
        return "HOLD", "provider_approval_or_actor_policy"
    if value in BAD:
        return "HOLD", "bounded_rerun_then_remediation"
    return ("PENDING", "await_provider_completion") if not value else ("HOLD", "unclassified_provider_conclusion")


def provider_rerun_not_retriable(exc):
    """Return true only for an explicit provider rejection of a rerun attempt.

    Permission failures and generic 403 responses remain fatal. This classification
    only converts GitHub's immutable/non-rerunnable historical-run response into a
    receipt-producing HOLD disposition.
    """
    value = str(exc or "").casefold()
    return "rerun-failed-jobs_" in value and any(
        marker in value
        for marker in (
            "this workflow run cannot be retried",
            "workflow run cannot be retried",
            "workflow run is not rerunnable",
            "workflow run cannot be re-run",
        )
    )


class GitHubClient:
    def __init__(self, repo, token, budget):
        self.repo, self.token, self.budget = repo, token, budget

    def request(self, method, path, body=None):
        self.budget.consume()
        req = urllib.request.Request(API + path, data=None if body is None else json.dumps(body).encode(), method=method, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CrownThrive-PentaRG/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            if exc.code in {403, 429} and exc.headers.get("x-ratelimit-remaining") == "0":
                reset = exc.headers.get("x-ratelimit-reset")
                reset_at = iso(dt.datetime.fromtimestamp(int(reset), tz=dt.timezone.utc)) if reset and reset.isdigit() else None
                raise ProviderDeferred(f"github_quota_exhausted:{raw[:400]}", reset_at) from exc
            raise PentaRGError(f"github_{method}_{path}_{exc.code}:{raw[:800]}") from exc

    def get(self, path): return self.request("GET", path)
    def post(self, path, body): return self.request("POST", path, body)
    def patch(self, path, body): return self.request("PATCH", path, body)

    def paginate(self, path, pages=3):
        values, sep = [], "&" if "?" in path else "?"
        for page in range(1, pages + 1):
            batch = self.get(f"{path}{sep}page={page}")
            if not isinstance(batch, list):
                raise PentaRGError(f"pagination_expected_list:{path}")
            values += batch
            if len(batch) < 100:
                break
        return values


def _pull_files(gh, number):
    return [str(v.get("filename")) for v in gh.paginate(f"/repos/{gh.repo}/pulls/{number}/files?per_page=100")]


def _workflow_runs(gh, sha):
    payload = gh.get(f"/repos/{gh.repo}/actions/runs?head_sha={urllib.parse.quote(sha, safe='')}&per_page=100")
    latest = {}
    for run in payload.get("workflow_runs", []):
        key = str(run.get("name") or run.get("workflow_id"))
        if key not in latest or int(run.get("id") or 0) > int(latest[key].get("id") or 0):
            latest[key] = run
    return list(latest.values())


def _comments(gh, number):
    return gh.paginate(f"/repos/{gh.repo}/issues/{number}/comments?per_page=100")


def _marked(gh, number, key):
    return any(f"{MARKER}{key} -->" in str(v.get("body") or "") for v in _comments(gh, number))


def _comment(gh, number, key, text):
    if not _marked(gh, number, key):
        gh.post(f"/repos/{gh.repo}/issues/{number}/comments", {"body": f"{MARKER}{key} -->\n{text}"})


def remote_audit(repo, token, policy, apply=False):
    provider = policy.get("provider") or {}
    budget, observations, actions, executed, deferred = RequestBudget(int(provider.get("request_budget", 240))), [], [], [], None
    gh = GitHubClient(repo, token, budget)
    try:
        pulls = gh.paginate(f"/repos/{repo}/pulls?state=open&sort=updated&direction=asc&per_page=100", 2)[: int(provider.get("max_open_pulls_per_sweep", 75))]
        for raw in pulls:
            number, sha = int(raw["number"]), str((raw.get("head") or {}).get("sha") or "")
            files, states = _pull_files(gh, number), []
            for run in _workflow_runs(gh, sha) if sha else []:
                state, route = classify_run_conclusion(run.get("conclusion"))
                states.append({"id": run.get("id"), "name": run.get("name"), "status": run.get("status"), "conclusion": run.get("conclusion"), "gate_state": state, "route": route})
                if route == "bounded_rerun_then_remediation" and run.get("id"):
                    actions.append(Action("rerun_failed_workflow", str(run["id"]), "D1", f"PR #{number} exact-head provider run failed", True, "new attempt; prior attempt immutable", {"pr": number, "head_sha": sha}))
                elif route == "provider_approval_or_actor_policy":
                    actions.append(Action("reissue_pr_from_trusted_actor_or_approve_provider_run", f"pr:{number}", "D2", "provider returned action_required before jobs", False, "no mutation", {"head_sha": sha, "workflow": run.get("name")}))
            starter = starter_pr_match(str(raw.get("title") or ""), files, policy)
            if starter:
                actions.append(Action("archive_generic_workflow_pr", f"pr:{number}", "D1", "unbound provider starter conflicts with canonical topology", True, "reopen PR; history retained", {"files": files, "head_sha": sha}))
            observations.append({"number": number, "title": raw.get("title"), "draft": raw.get("draft"), "head_sha": sha, "files": files, "starter_template": starter, "runs": states})
        for group in duplicate_groups(observations):
            actions.append(Action("deduplicate_pr_group", ",".join(map(str, group)), "D2", "same changed-file fingerprint", False, "no mutation without supersession evidence", {"prs": group}))
        if apply:
            for action in actions:
                if not action.apply_allowed or not authority_allowed(policy, action.authority):
                    continue
                if action.action == "archive_generic_workflow_pr":
                    number = int(action.target.split(":")[1]); key = f"archive-pr-{number}-v1"
                    _comment(gh, number, key, "### PentaRG autonomous archive\n\nUnbound generic workflow archived without deleting branch or history. Any successor must be topology-bound, full-SHA pinned, least-privilege, tested and receipt-producing.")
                    gh.patch(f"/repos/{repo}/pulls/{number}", {"state": "closed"})
                    executed.append({"action": action.action, "pr": number, "status": "APPLIED"})
                elif action.action == "rerun_failed_workflow":
                    run, pr = int(action.target), int((action.metadata or {}).get("pr") or 0); key = f"rerun-{run}-v1"
                    if pr and _marked(gh, pr, key):
                        executed.append({"action": action.action, "run_id": run, "status": "NOOP_ALREADY_REQUESTED"}); continue
                    try:
                        gh.post(f"/repos/{repo}/actions/runs/{run}/rerun-failed-jobs", {})
                    except ProviderDeferred:
                        raise
                    except PentaRGError as exc:
                        if not provider_rerun_not_retriable(exc):
                            raise
                        hold_key = f"rerun-{run}-provider-nonretriable-v1"
                        if pr:
                            _comment(
                                gh,
                                pr,
                                hold_key,
                                f"### PentaRG non-retriable provider HOLD\n\nGitHub refused a failed-job rerun for historical run `{run}` on exact head `{(action.metadata or {}).get('head_sha')}` because the workflow run is no longer retriable. No PASS was manufactured and no history was rewritten. The failed provider evidence remains immutable and requires current-head remediation or supersession rather than another retry.",
                            )
                        executed.append({
                            "action": action.action,
                            "run_id": run,
                            "status": "SKIPPED_PROVIDER_NOT_RETRIABLE",
                            "provider_reason": "workflow_run_cannot_be_retried",
                            "head_sha": (action.metadata or {}).get("head_sha"),
                            "pr": pr or None,
                        })
                        continue
                    if pr: _comment(gh, pr, key, f"### PentaRG bounded retry\n\nRequested one failed-job rerun for `{run}` on exact head `{(action.metadata or {}).get('head_sha')}`. A rerun is not PASS; readback remains required.")
                    executed.append({"action": action.action, "run_id": run, "status": "DISPATCHED"})
    except ProviderDeferred as exc:
        deferred = {"reason": str(exc), "provider_reset_at": exc.reset_at, "retry_after_seconds": int(provider.get("deferred_retry_seconds", 1800))}
    receipt = {"schema": SCHEMA, "kind": "remote_audit_and_recovery", "observed_at": iso(), "repository": repo, "mode": policy.get("mode"), "apply_requested": apply, "founder_d3_lease_active": founder_lease_active(policy), "request_budget": {"maximum": budget.maximum, "used": budget.used}, "observations": observations, "planned_actions": [asdict(a) for a in actions], "executed_actions": executed, "deferred": deferred, "pass_manufactured": False, "branch_protection_modified": False, "history_rewritten": False, "secret_values_read": False}
    receipt["status"] = "DEFERRED" if deferred else "HOLD" if any(r.get("gate_state") == "HOLD" for p in observations for r in p.get("runs", [])) else "PASS"
    previous, events = "GENESIS", []
    for i, payload in enumerate([{"kind": "AUDIT", "observations": len(observations)}, {"kind": "PLAN", "actions": len(actions)}, {"kind": "APPLY", "executed": len(executed), "requested": apply}, {"kind": "DEFER", "value": deferred}], 1):
        event = {"sequence": i, "previous_hash": previous, "at": receipt["observed_at"], "payload": payload}; event["event_hash"] = digest(event); previous = event["event_hash"]; events.append(event)
    receipt["dail_event_chain"], receipt["receipt_sha256"] = events, digest({**receipt, "dail_event_chain": events})
    return receipt


def write_output(report, output=None):
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if output:
        path = Path(output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
    print(text, end="")


def main(argv: Sequence[str] | None = None):
    parser = argparse.ArgumentParser(description="PentaRG Release Governance & Recovery"); sub = parser.add_subparsers(dest="command", required=True)
    local = sub.add_parser("audit"); local.add_argument("--root", default=str(Path(__file__).resolve().parents[1])); local.add_argument("--policy", default="config/penta_rg_policy.json"); local.add_argument("--topology", default="config/penta_rg_topology.json"); local.add_argument("--output")
    remote = sub.add_parser("remote"); remote.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY")); remote.add_argument("--token", default=os.environ.get("PENTA_RG_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")); remote.add_argument("--policy", default="config/penta_rg_policy.json"); remote.add_argument("--apply", action="store_true"); remote.add_argument("--output")
    args = parser.parse_args(argv)
    if args.command == "audit":
        root = Path(args.root).resolve(); policy = Path(args.policy); topology = Path(args.topology)
        report = local_audit(root, load_json(policy if policy.is_absolute() else root / policy), load_json(topology if topology.is_absolute() else root / topology)); write_output(report, args.output); return 0 if report["status"] == "PASS" else 1
    if not args.repo or not args.token: raise SystemExit("remote requires repository and token")
    report = remote_audit(args.repo, args.token, load_json(args.policy), args.apply); write_output(report, args.output); return 0


if __name__ == "__main__":
    raise SystemExit(main())
