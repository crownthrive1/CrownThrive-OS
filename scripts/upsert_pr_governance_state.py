#!/usr/bin/env python3
"""Upsert a machine-owned exact-head governance readback on a pull request.

Phase 3.5 ownership: PentaNurture/PentaStatus observation capability. This
script never converts CI transport state into CHLOM authority, D3 authority,
merge authority, or a manufactured PASS. Provider-read restrictions become an
explicit, receipted evidence hold while trusted workflow event data remains
available for bounded observability.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKER = "<!-- ct-governance-observability-v2 -->"
TRACKED = (
    "Governed Merge Gate",
    "Security Governance",
    "Documentation Governance",
    "Documentation Reconciliation Continuity",
    "PENTA Gap Closure",
)
OBSERVABILITY_RECEIPT = Path("github-observability.json")
PR_STATE_RECEIPT = Path("pr-governance-state.json")


def api(method: str, path: str, data: dict[str, Any] | None = None) -> Any:
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://api.github.com{path}"
    body = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def _restricted_warning(
    *,
    capability: str,
    exc: urllib.error.HTTPError,
    fallback: str,
) -> dict[str, Any]:
    payload = {
        "warning": "PROVIDER_READBACK_RESTRICTED",
        "capability": capability,
        "http_status": exc.code,
        "fallback": fallback,
    }
    print(json.dumps(payload, sort_keys=True))
    return payload


def _workflow_event_snapshot(event: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    run = event.get("workflow_run")
    if not isinstance(run, dict):
        return {}
    workflow_name = run.get("name")
    if workflow_name not in TRACKED:
        return {}
    return {
        str(workflow_name): {
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "run_id": str(run.get("id")) if run.get("id") is not None else None,
            "source": "trusted_workflow_run_event",
        }
    }


def resolve_pr(event: dict[str, Any], repo: str) -> tuple[int, dict[str, Any]] | None:
    pr = event.get("pull_request")
    if isinstance(pr, dict):
        return int(pr["number"]), pr

    run = event.get("workflow_run")
    if isinstance(run, dict):
        prs = run.get("pull_requests") or []
        if prs:
            candidate = prs[0]
            return int(candidate["number"]), candidate

        head_sha = run.get("head_sha")
        if head_sha:
            owner, name = repo.split("/", 1)
            try:
                candidates = api(
                    "GET",
                    f"/repos/{owner}/{name}/commits/{head_sha}/pulls?per_page=10",
                )
            except urllib.error.HTTPError as exc:
                if exc.code not in {403, 404}:
                    raise
                _restricted_warning(
                    capability="commit_to_pull_request_association",
                    exc=exc,
                    fallback="no_mutation_receipt",
                )
                return None
            open_prs = [item for item in candidates if item.get("state") == "open"]
            if open_prs:
                candidate = open_prs[0]
                return int(candidate["number"]), candidate
    return None


def enrich_pr(
    repo: str,
    pr_number: int,
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], str, int | None]:
    """Prefer the full PR object and retain the trusted snapshot on 403/404."""

    owner, name = repo.split("/", 1)
    try:
        return api("GET", f"/repos/{owner}/{name}/pulls/{pr_number}"), "VERIFIED", None
    except urllib.error.HTTPError as exc:
        if exc.code not in {403, 404}:
            raise
        _restricted_warning(
            capability="pull_request_detail",
            exc=exc,
            fallback="trusted_event_snapshot",
        )
        return snapshot, "DEGRADED", exc.code


def latest_workflows(
    repo: str,
    head_sha: str,
    event: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, str | None]], str, str | None, int | None]:
    """Read exact-head Actions state, falling back to the trusted event on 403/404."""

    owner, name = repo.split("/", 1)
    q = urllib.parse.urlencode({"head_sha": head_sha, "per_page": 100})
    try:
        payload = api("GET", f"/repos/{owner}/{name}/actions/runs?{q}")
    except urllib.error.HTTPError as exc:
        if exc.code not in {403, 404}:
            raise
        fallback = _workflow_event_snapshot(event or {})
        reason = (
            "ACTIONS_READ_FORBIDDEN"
            if exc.code == 403
            else "ACTIONS_READ_NOT_FOUND"
        )
        _restricted_warning(
            capability="actions_exact_head_enrichment",
            exc=exc,
            fallback=(
                "trusted_workflow_run_event"
                if fallback
                else "degraded_receipt_without_enrichment"
            ),
        )
        return fallback, "DEGRADED", reason, exc.code

    result: dict[str, dict[str, str | None]] = {}
    for run in payload.get("workflow_runs", []):
        workflow_name = run.get("name")
        if workflow_name not in TRACKED or workflow_name in result:
            continue
        result[str(workflow_name)] = {
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "run_id": str(run.get("id")) if run.get("id") is not None else None,
            "source": "github_actions_api",
        }
    return result, "VERIFIED", None, None


def evidence_state(
    runs: dict[str, dict[str, str | None]],
    provider_enrichment_state: str = "VERIFIED",
) -> str:
    if provider_enrichment_state != "VERIFIED":
        return "DEGRADED_PROVIDER_ENRICHMENT"
    if any(item.get("conclusion") == "failure" for item in runs.values()):
        return "CI_RED_REQUIRES_CLASSIFIER_READBACK"
    if runs and all(
        item.get("status") == "completed" and item.get("conclusion") == "success"
        for item in runs.values()
    ):
        return "GREEN_FOR_OBSERVED_WORKFLOWS"
    if any(
        item.get("status") in {"queued", "in_progress", "pending"}
        for item in runs.values()
    ):
        return "PENDING"
    return "PARTIAL_OR_NOT_YET_OBSERVED"


def _ref_line(pr: dict[str, Any], side: str) -> tuple[str, str]:
    obj = pr.get(side) or {}
    sha = str(obj.get("sha") or "unknown")
    ref = str(obj.get("ref") or "unknown")
    return sha, ref


def _apply_event_identity(pr: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Fill only identity fields supplied by the trusted workflow event."""

    snapshot = dict(pr)
    run = event.get("workflow_run")
    if not isinstance(run, dict):
        return snapshot

    head = dict(snapshot.get("head") or {})
    if not head.get("sha") and run.get("head_sha"):
        head["sha"] = run["head_sha"]
    if not head.get("ref") and run.get("head_branch"):
        head["ref"] = run["head_branch"]
    snapshot["head"] = head
    return snapshot


def build_comment(
    pr: dict[str, Any],
    runs: dict[str, dict[str, str | None]],
    *,
    provider_enrichment_state: str = "VERIFIED",
    degraded_reason: str | None = None,
    provider_http_status: int | None = None,
) -> str:
    head_sha, head_ref = _ref_line(pr, "head")
    base_sha, base_ref = _ref_line(pr, "base")
    evidence = evidence_state(runs, provider_enrichment_state)
    evidence_disposition = (
        "HOLD_EVIDENCE"
        if provider_enrichment_state != "VERIFIED"
        else "NOT_DERIVED_FROM_CI"
    )
    lines = [
        MARKER,
        "## Penta governance observability readback",
        "",
        f"- Updated UTC: `{datetime.now(timezone.utc).isoformat()}`",
        f"- PR transport state: `{'DRAFT' if pr.get('draft') else pr.get('state', 'unknown').upper()}`",
        f"- Exact head: `{head_sha}` (`{head_ref}`)",
        f"- Exact base: `{base_sha}` (`{base_ref}`)",
        f"- Mergeable readback: `{pr.get('mergeable')}`",
        f"- CI evidence state: `{evidence}`",
        f"- Provider enrichment: `{provider_enrichment_state}`",
        f"- Evidence disposition: `{evidence_disposition}`",
        "- CHLOM/D3 disposition created by this readback: `NONE`",
        "- Capability owner: `PentaNurture / PentaStatus`",
        "- Authority created by this readback: `NONE`",
    ]
    if degraded_reason:
        lines.append(f"- Degraded reason: `{degraded_reason}`")
    if provider_http_status is not None:
        lines.append(f"- Provider HTTP status: `{provider_http_status}`")

    lines += ["", "### Observed governance workflows", ""]
    if not runs:
        lines.append(
            "No tracked workflow run could be enriched for this exact head. "
            "The evidence projection remains fail-closed."
        )
    else:
        for name in TRACKED:
            item = runs.get(name)
            if not item:
                lines.append(f"- {name}: `NOT_OBSERVED`")
            else:
                lines.append(
                    f"- {name}: `{item.get('status')}` / "
                    f"`{item.get('conclusion')}` / run `{item.get('run_id')}` / "
                    f"source `{item.get('source', 'unknown')}`"
                )
    lines += [
        "",
        "### Interpretation firewall",
        "",
        "A CI failure is not automatically a CHLOM/Penta `HOLD` or `DENY`. "
        "A provider-read restriction creates only an evidence hold and never "
        "a governance PASS. Authoritative dispositions require current policy "
        "and evidence output. Exact-head/base identity is machine-read from "
        "GitHub or the trusted workflow event and supersedes stale prose only "
        "for transport/source identity. PentaMerge and PentaCloser must apply "
        "their own current authority and gates.",
    ]
    return "\n".join(lines)


def upsert(repo: str, pr_number: int, body: str) -> None:
    owner, name = repo.split("/", 1)
    comments = api(
        "GET",
        f"/repos/{owner}/{name}/issues/{pr_number}/comments?per_page=100",
    )
    for comment in comments:
        if MARKER in (comment.get("body") or ""):
            api(
                "PATCH",
                f"/repos/{owner}/{name}/issues/comments/{comment['id']}",
                {"body": body},
            )
            return
    api(
        "POST",
        f"/repos/{owner}/{name}/issues/{pr_number}/comments",
        {"body": body},
    )


def write_receipts(receipt: dict[str, Any]) -> None:
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    OBSERVABILITY_RECEIPT.write_text(serialized, encoding="utf-8")
    PR_STATE_RECEIPT.write_text(serialized, encoding="utf-8")


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    event = json.loads(
        Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8")
    )
    base_receipt: dict[str, Any] = {
        "schema": "ct.governance-observability-receipt.v3",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": repo,
        "workflow_execution": "SUCCESS",
        "authority_created": "NONE",
        "chlom_d3_disposition_created": "NONE",
    }

    resolved = resolve_pr(event, repo)
    if resolved is None:
        run = event.get("workflow_run") or {}
        receipt = {
            **base_receipt,
            "result": "DEGRADED_NO_PULL_REQUEST_RESOLVED",
            "institutional_state": "HOLD_EVIDENCE",
            "evidence_state": "DEGRADED",
            "reason": "PULL_REQUEST_ASSOCIATION_UNAVAILABLE",
            "run_id": run.get("id"),
            "head_sha": run.get("head_sha"),
            "projection_state": "NOT_WRITTEN",
        }
        write_receipts(receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0

    pr_number, raw_snapshot = resolved
    pr, pr_detail_state, pr_detail_http_status = enrich_pr(
        repo,
        pr_number,
        raw_snapshot,
    )
    pr = _apply_event_identity(pr, event)
    head_sha, _ = _ref_line(pr, "head")
    if head_sha == "unknown":
        receipt = {
            **base_receipt,
            "result": "DEGRADED_EXACT_HEAD_UNAVAILABLE",
            "institutional_state": "HOLD_EVIDENCE",
            "evidence_state": "DEGRADED",
            "reason": "EXACT_HEAD_SHA_UNAVAILABLE",
            "pr": pr_number,
            "projection_state": "NOT_WRITTEN",
        }
        write_receipts(receipt)
        print(json.dumps(receipt, sort_keys=True))
        return 0

    runs, actions_state, actions_reason, actions_http_status = latest_workflows(
        repo,
        head_sha,
        event,
    )
    degraded_reasons = [
        reason
        for reason in (
            "PR_DETAIL_READBACK_RESTRICTED"
            if pr_detail_state != "VERIFIED"
            else None,
            actions_reason,
        )
        if reason
    ]
    provider_enrichment_state = (
        "DEGRADED"
        if pr_detail_state != "VERIFIED" or actions_state != "VERIFIED"
        else "VERIFIED"
    )
    provider_http_status = actions_http_status or pr_detail_http_status
    degraded_reason = ",".join(degraded_reasons) if degraded_reasons else None

    comment = build_comment(
        pr,
        runs,
        provider_enrichment_state=provider_enrichment_state,
        degraded_reason=degraded_reason,
        provider_http_status=provider_http_status,
    )
    projection_state = "WRITTEN"
    projection_http_status: int | None = None
    try:
        upsert(repo, pr_number, comment)
    except urllib.error.HTTPError as exc:
        if exc.code not in {403, 404}:
            raise
        _restricted_warning(
            capability="pull_request_comment_projection",
            exc=exc,
            fallback="workflow_receipt_and_summary",
        )
        projection_state = "DEGRADED_NOT_WRITTEN"
        projection_http_status = exc.code
        provider_enrichment_state = "DEGRADED"
        degraded_reasons.append("PROJECTION_WRITE_FORBIDDEN")
        degraded_reason = ",".join(dict.fromkeys(degraded_reasons))

    receipt = {
        **base_receipt,
        "result": "PASS_PENTA_GOVERNANCE_PR_READBACK_UPSERT"
        if projection_state == "WRITTEN"
        else "DEGRADED_PENTA_GOVERNANCE_PR_READBACK",
        "institutional_state": (
            "HOLD_EVIDENCE"
            if provider_enrichment_state != "VERIFIED"
            else "NOT_DERIVED_FROM_CI"
        ),
        "evidence_state": evidence_state(runs, provider_enrichment_state),
        "provider_enrichment_state": provider_enrichment_state,
        "reason": degraded_reason,
        "provider_http_status": provider_http_status,
        "projection_http_status": projection_http_status,
        "projection_state": projection_state,
        "pr": pr_number,
        "head_sha": head_sha,
        "workflow_runs": runs,
    }
    write_receipts(receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
