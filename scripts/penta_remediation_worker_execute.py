#!/usr/bin/env python3
"""Trusted Penta remediation worker execution bridge."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

GITHUB_API = "https://api.github.com"
DEFAULT_OIDC_ENDPOINT = "https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-remediation-worker-oidc"
DEFAULT_OIDC_AUDIENCE = "crownthrive-penta-remediation"
MARKER_RE = re.compile(r"penta-self-remediation:([0-9a-fA-F-]{36})")
EXEC_MARKER = "<!-- penta-remediation-execution:{execution_id} -->"


class HTTPError(RuntimeError):
    pass


def request_json(method: str, url: str, headers: dict[str, str], body: Any | None = None, *, allow_404: bool = False) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            raw = response.read()
            return json.loads(raw or b"null")
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        detail = exc.read().decode(errors="replace")
        raise HTTPError(f"{method} {url} -> {exc.code}: {detail[:1000]}") from exc


def mint_github_oidc_token(audience: str = DEFAULT_OIDC_AUDIENCE) -> str:
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL") or ""
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN") or ""
    if not request_url or not request_token:
        raise RuntimeError("github_oidc_refresh_authority_unavailable")
    separator = "&" if "?" in request_url else "?"
    url = request_url + separator + "audience=" + urllib.parse.quote(audience, safe="")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + request_token,
            "Accept": "application/json",
            "User-Agent": "CrownThrive-PentaRemediationWorker/1.3",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            token = str((json.load(response) or {}).get("value") or "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"github_oidc_refresh_failed:{exc.code}:{detail[:200]}") from exc
    if not token:
        raise RuntimeError("github_oidc_refresh_token_missing")
    return token


class GH:
    def __init__(self, repo: str, token: str) -> None:
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "CrownThrive-PentaRemediationWorker/1.3",
        }

    def req(self, method: str, path: str, body: Any | None = None, *, allow_404: bool = False) -> Any:
        return request_json(method, f"{GITHUB_API}/repos/{self.repo}{path}", self.headers, body, allow_404=allow_404)

    def get(self, path: str, *, allow_404: bool = False) -> Any:
        return self.req("GET", path, allow_404=allow_404)

    def post(self, path: str, body: Any) -> Any:
        return self.req("POST", path, body)

    def patch(self, path: str, body: Any) -> Any:
        return self.req("PATCH", path, body)

    def put(self, path: str, body: Any) -> Any:
        return self.req("PUT", path, body)

    def delete(self, path: str) -> Any:
        return self.req("DELETE", path)

    def open_prs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for page in range(1, 6):
            batch = self.get(f"/pulls?state=open&base=main&per_page=100&page={page}")
            items.extend(batch)
            if len(batch) < 100:
                break
        return items


class Supabase:
    """OIDC-authenticated RPC facade. No Supabase service-role secret enters Actions."""

    def __init__(self, endpoint: str, oidc_token: str, audience: str = DEFAULT_OIDC_AUDIENCE) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.audience = audience
        self.headers = {
            "Authorization": f"Bearer {oidc_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "CrownThrive-PentaRemediationWorker/1.3",
        }
        self.refresh_count = 0

    @staticmethod
    def _is_expired_oidc_error(exc: HTTPError) -> bool:
        text = str(exc).lower().replace("\\\"", '"').replace("\\'", "'")
        return (
            '"exp" claim timestamp check failed' in text
            or "'exp' claim timestamp check failed" in text
            or "token expired" in text
            or "jwt expired" in text
        )

    def _refresh_oidc(self) -> None:
        token = mint_github_oidc_token(self.audience)
        self.headers["Authorization"] = f"Bearer {token}"
        self.refresh_count += 1

    def rpc(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        body = {"op": name, "args": payload or {}}
        try:
            envelope = request_json("POST", self.endpoint, self.headers, body)
        except HTTPError as exc:
            if not self._is_expired_oidc_error(exc):
                raise
            self._refresh_oidc()
            envelope = request_json("POST", self.endpoint, self.headers, body)
        if not isinstance(envelope, dict) or not envelope.get("ok"):
            raise RuntimeError(f"penta_remediation_oidc_rpc_rejected:{name}")
        return envelope.get("result")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def labels_for(gh: GH, number: int) -> set[str]:
    issue = gh.get(f"/issues/{number}")
    return {str(item.get("name")) for item in issue.get("labels", []) if item.get("name")}


def finding_id_from_pr(pr: dict[str, Any]) -> str | None:
    match = MARKER_RE.search(str(pr.get("body") or ""))
    return match.group(1).lower() if match else None


def read_manifest(gh: GH, pr: dict[str, Any], finding_id: str) -> dict[str, Any]:
    head = pr.get("head") or {}
    ref = str(head.get("ref") or "")
    path = f"penta/remediations/{finding_id}.json"
    encoded_ref = urllib.parse.quote(ref, safe="")
    payload = gh.get(f"/contents/{path}?ref={encoded_ref}")
    raw = base64.b64decode(payload["content"]).decode("utf-8")
    manifest = json.loads(raw)
    if str(manifest.get("finding_id") or "").lower() != finding_id:
        raise RuntimeError(f"manifest_finding_mismatch:{pr['number']}")
    return manifest


def assigned_pentas_from_labels(labels: set[str]) -> list[str]:
    return sorted(name.removeprefix("penta:assigned:") for name in labels if name.startswith("penta:assigned:"))


def adopt_pr(gh: GH, sb: Supabase, number: int) -> dict[str, Any] | None:
    pr = gh.get(f"/pulls/{number}")
    if pr.get("state") != "open":
        return None
    if ((pr.get("head") or {}).get("repo") or {}).get("full_name") != gh.repo:
        raise RuntimeError(f"external_fork_remediation_refused:{number}")
    labels = labels_for(gh, number)
    if "penta:remediation" not in labels:
        return None
    finding_id = finding_id_from_pr(pr)
    if not finding_id:
        raise RuntimeError(f"remediation_marker_missing:{number}")
    manifest = read_manifest(gh, pr, finding_id)
    issue_number = int(manifest.get("issue_number") or 0)
    if issue_number <= 0:
        raise RuntimeError(f"remediation_issue_missing:{number}")
    assigned = assigned_pentas_from_labels(labels)
    result = sb.rpc(
        "penta_pm_enqueue_remediation_execution_v1",
        {
            "p_finding_id": finding_id,
            "p_issue_number": issue_number,
            "p_pr_number": number,
            "p_head_sha": (pr.get("head") or {}).get("sha"),
            "p_target_ref": str(manifest.get("target_ref") or "unknown"),
            "p_lane": str(manifest.get("lane") or "general"),
            "p_risk": str(manifest.get("risk") or "D1"),
            "p_assigned_pentas": assigned,
        },
    )
    return {"pr": pr, "manifest": manifest, "enqueue": result, "labels": labels}


def upsert_execution_comment(gh: GH, number: int, execution: dict[str, Any]) -> None:
    execution_id = str(execution.get("execution_id") or "unknown")
    marker = EXEC_MARKER.format(execution_id=execution_id)
    state = str(execution.get("state") or "unknown")
    receipt = execution.get("receipt") or {}
    body = (
        f"{marker}\n\n"
        "## Penta execution readback\n"
        f"- Execution: `{execution_id}`\n"
        f"- State: `{state}`\n"
        f"- DAIL event: `{execution.get('dail_event_id') or 'pending'}`\n"
        f"- PentaOS task: `{execution.get('task_id') or 'pending'}`\n"
        f"- Updated: `{now_iso()}`\n\n"
        "```json\n"
        + json.dumps(receipt, sort_keys=True, indent=2)[:12000]
        + "\n```"
    )
    comments: list[dict[str, Any]] = []
    for page in range(1, 4):
        batch = gh.get(f"/issues/{number}/comments?per_page=100&page={page}")
        comments.extend(batch)
        if len(batch) < 100:
            break
    existing = next((item for item in comments if marker in str(item.get("body") or "")), None)
    if existing:
        gh.patch(f"/issues/comments/{existing['id']}", {"body": body})
    else:
        gh.post(f"/issues/{number}/comments", {"body": body})


def write_receipt_file(gh: GH, pr: dict[str, Any], execution: dict[str, Any]) -> str | None:
    finding_id = str(execution["finding_id"])
    branch = str((pr.get("head") or {}).get("ref") or "")
    path = f"penta/remediations/{finding_id}.execution.json"
    document = {
        "schema": "ct.penta.remediation.execution-receipt.v1",
        "finding_id": finding_id,
        "execution_id": execution.get("execution_id"),
        "pr_number": execution.get("pr_number"),
        "issue_number": execution.get("issue_number"),
        "state": execution.get("state"),
        "task_id": execution.get("task_id"),
        "dail_event_id": execution.get("dail_event_id"),
        "receipt": execution.get("receipt") or {},
        "generated_at": now_iso(),
        "authority_manufactured": False,
    }
    content = json.dumps(document, sort_keys=True, indent=2) + "\n"
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    encoded_ref = urllib.parse.quote(branch, safe="")
    current = gh.get(f"/contents/{encoded_path}?ref={encoded_ref}", allow_404=True)
    if current:
        old = base64.b64decode(current["content"]).decode("utf-8")
        try:
            old_doc = json.loads(old)
            old_doc.pop("generated_at", None)
            new_doc = dict(document)
            new_doc.pop("generated_at", None)
            if old_doc == new_doc:
                return None
        except json.JSONDecodeError:
            pass
    payload: dict[str, Any] = {
        "message": f"PentaExecution: record remediation {finding_id}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if current:
        payload["sha"] = current["sha"]
    result = gh.put(f"/contents/{encoded_path}", payload)
    return ((result.get("commit") or {}).get("sha"))


def mark_verified_pr(gh: GH, pr: dict[str, Any], execution: dict[str, Any]) -> None:
    number = int(pr["number"])
    receipt = execution.get("receipt") or {}
    no_code_delta = bool(receipt.get("no_code_delta"))
    write_receipt_file(gh, pr, execution)
    if no_code_delta:
        body = str(pr.get("body") or "")
        marker = "<!-- penta-remediation-verified-no-code-delta -->"
        if marker not in body:
            body = body.rstrip() + (
                "\n\n" + marker + "\n"
                "represented-zero-delta: PentaSELF independently verified the source problem resolved before corrective branch execution; "
                "the Penta execution receipt is authoritative evidence for terminal closure.\n"
            )
            gh.patch(f"/pulls/{number}", {"body": body})
    labels = labels_for(gh, number)
    if "penta:hold" in labels:
        encoded = urllib.parse.quote("penta:hold", safe="")
        try:
            gh.delete(f"/issues/{number}/labels/{encoded}")
        except HTTPError as exc:
            if "404" not in str(exc):
                raise
    upsert_execution_comment(gh, number, execution)


def finalize_pr(gh: GH, sb: Supabase, number: int) -> None:
    readback = sb.rpc("penta_remediation_execution_read_v1", {"p_pr_number": number})
    for execution in (readback or {}).get("items", []):
        pr = gh.get(f"/pulls/{number}")
        state = execution.get("state")
        if state == "verified":
            mark_verified_pr(gh, pr, execution)
        elif state in {"verification", "failed", "held"}:
            upsert_execution_comment(gh, number, execution)


def event_pr_number() -> int | None:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return None
    event = json.loads(open(path, encoding="utf-8").read())
    payload = event.get("client_payload") or {}
    value = payload.get("pr_number")
    return int(value) if value else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--pr", type=int)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("repo_required")
    token = os.environ.get("PENTA_PM_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    oidc_token = os.environ.get("PENTA_REMEDIATION_OIDC_TOKEN")
    oidc_endpoint = os.environ.get("PENTA_REMEDIATION_OIDC_ENDPOINT") or DEFAULT_OIDC_ENDPOINT
    audience = os.environ.get("PENTA_REMEDIATION_OIDC_AUDIENCE") or DEFAULT_OIDC_AUDIENCE
    if not token or not oidc_token:
        raise SystemExit("trusted_remediation_github_and_oidc_credentials_required")
    gh = GH(args.repo, token)
    sb = Supabase(oidc_endpoint, oidc_token, audience)

    requested = args.pr or event_pr_number()
    adopted: list[int] = []
    if requested:
        if adopt_pr(gh, sb, requested):
            adopted.append(requested)
    else:
        for pr in gh.open_prs():
            number = int(pr["number"])
            labels = labels_for(gh, number)
            if "penta:remediation" not in labels:
                continue
            if adopt_pr(gh, sb, number):
                adopted.append(number)
            if len(adopted) >= 50:
                break

    reconcile = sb.rpc("penta_remediation_execution_reconcile_v1", {}) or {}
    for number in adopted:
        finalize_pr(gh, sb, number)

    claim = sb.rpc("penta_remediation_execution_claim_v1", {"p_limit": max(1, min(args.limit, 10))}) or {}
    executed: list[dict[str, Any]] = []
    for item in claim.get("items", []):
        number = int(item["pr_number"])
        pr = gh.get(f"/pulls/{number}")
        current_head = str((pr.get("head") or {}).get("sha") or "")
        if current_head != item.get("head_sha"):
            adopt_pr(gh, sb, number)
            continue
        result = sb.rpc("penta_remediation_execute_known_v3", {"p_execution_id": item["execution_id"]}) or {}
        executed.append(result)
        finalize_pr(gh, sb, number)

    status = sb.rpc("penta_remediation_execution_status_v1", {}) or {}
    print(json.dumps({
        "state": "COMPLETE",
        "adopted_prs": adopted,
        "reconcile": reconcile,
        "claimed": claim.get("count", 0),
        "executed": executed,
        "status": status,
        "oidc_refresh_count": sb.refresh_count,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
