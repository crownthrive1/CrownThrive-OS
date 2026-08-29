#!/usr/bin/env python3
"""PentaSELF -> PentaPR remediation intake.

Turns a durable PentaSELF finding into one idempotent GitHub issue and one
remediation pull request. The bootstrap PR contains the immutable remediation
manifest and is held from terminal execution until assigned workers add the
actual repair and evidence. PentaPR does not manufacture merge authority here.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.github.com"
MARKER_PREFIX = "<!-- penta-self-remediation:"
LANES = {
    "docs",
    "workflow",
    "database",
    "provider",
    "security",
    "commerce",
    "media",
    "observability",
    "general",
}
RISKS = {"D0", "D1", "D2", "D3"}
SEVERITY_RISK = {"info": "D0", "watch": "D0", "degraded": "D1", "critical": "D2"}


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
                "User-Agent": "CrownThrive-PentaSELF-PentaPR/1.0",
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

    def put(self, path: str, body: Any) -> Any:
        return self.req("PUT", path, body)

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


def _text(value: Any, field: str, *, required: bool = False, limit: int = 4000) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"missing_required_field:{field}")
    return text[:limit]


def remediation_key(finding_id: str) -> str:
    raw = finding_id.strip()
    if not raw:
        raise ValueError("missing_required_field:finding_id")
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-._").lower()
    if safe:
        return safe[:56]
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def normalize_finding(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("finding_payload_must_be_object")
    finding_id = _text(payload.get("finding_id"), "finding_id", required=True, limit=160)
    symptom = _text(payload.get("symptom"), "symptom", required=True, limit=2000)
    severity = _text(payload.get("severity") or "degraded", "severity", limit=32).lower()
    lane = _text(payload.get("lane") or "general", "lane", limit=32).lower()
    if lane not in LANES:
        lane = "general"
    explicit_risk = _text(payload.get("risk"), "risk", limit=8).upper()
    risk = explicit_risk or SEVERITY_RISK.get(severity, "D1")
    if risk not in RISKS:
        raise ValueError(f"invalid_risk:{risk}")
    required_pentas = payload.get("required_pentas") or []
    if not isinstance(required_pentas, list):
        raise ValueError("required_pentas_must_be_array")
    required_pentas = [
        _text(item, "required_pentas", limit=80)
        for item in required_pentas
        if _text(item, "required_pentas", limit=80)
    ][:24]
    criteria = payload.get("acceptance_criteria") or []
    if isinstance(criteria, str):
        criteria = [criteria]
    if not isinstance(criteria, list):
        raise ValueError("acceptance_criteria_must_be_array_or_string")
    criteria = [_text(item, "acceptance_criteria", limit=700) for item in criteria if _text(item, "acceptance_criteria", limit=700)][:30]
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    return {
        "schema": "ct.penta.self.remediation-finding.v1",
        "finding_id": finding_id,
        "remediation_key": remediation_key(finding_id),
        "severity": severity,
        "risk": risk,
        "lane": lane,
        "state": _text(payload.get("state") or "open", "state", limit=32).lower(),
        "target_ref": _text(payload.get("target_ref"), "target_ref", limit=1000),
        "symptom": symptom,
        "required_pentas": sorted(set(required_pentas)),
        "acceptance_criteria": criteria,
        "evidence": evidence,
        "source": "PentaSELF",
        "pr_authority": "PentaPR",
        "pm_authority": "PentaPM",
    }


def marker(finding_id: str) -> str:
    return f"{MARKER_PREFIX}{finding_id} -->"


def _label_spec(name: str) -> tuple[str, str]:
    fixed = {
        "penta:source:self": ("5319e7", "Finding originated from PentaSELF"),
        "penta:remediation": ("b60205", "PentaSELF remediation work item"),
        "penta:authority:pm": ("006b75", "PentaPM owns worker assignment and reassignment"),
        "penta:risk:d3": ("000000", "D3 human-reserved or sovereign-risk action"),
    }
    if name in fixed:
        return fixed[name]
    return "ededed", "Penta remediation control label"


def ensure_labels(gh: GH, names: set[str]) -> None:
    existing = {item["name"] for item in gh.paginate(f"/repos/{gh.repo}/labels?")}
    for name in sorted(names.difference(existing)):
        color, description = _label_spec(name)
        try:
            gh.post(f"/repos/{gh.repo}/labels", {"name": name, "color": color, "description": description})
        except RuntimeError as exc:
            if "422" not in str(exc):
                raise


def add_labels(gh: GH, number: int, names: set[str]) -> None:
    ensure_labels(gh, names)
    gh.post(f"/repos/{gh.repo}/issues/{number}/labels", {"labels": sorted(names)})


def find_existing_issue(gh: GH, finding_id: str) -> dict[str, Any] | None:
    wanted = marker(finding_id)
    for issue in gh.paginate(f"/repos/{gh.repo}/issues?state=all&labels=penta%3Aremediation"):
        if "pull_request" in issue:
            continue
        if wanted in str(issue.get("body") or ""):
            return issue
    return None


def issue_body(finding: dict[str, Any]) -> str:
    criteria = "\n".join(f"- [ ] {item}" for item in finding["acceptance_criteria"]) or "- [ ] Repair the observed condition and attach independent verification evidence."
    owners = ", ".join(finding["required_pentas"]) or "PentaPM will compute the required owner set from lane/risk policy."
    evidence_json = json.dumps(finding["evidence"], sort_keys=True, indent=2)[:8000]
    return (
        f"{marker(finding['finding_id'])}\n\n"
        "## PentaSELF finding\n"
        f"- Finding: `{finding['finding_id']}`\n"
        f"- Severity: `{finding['severity']}`\n"
        f"- Risk: `{finding['risk']}`\n"
        f"- Lane: `{finding['lane']}`\n"
        f"- Target: `{finding['target_ref'] or 'unspecified'}`\n"
        f"- Symptom: {finding['symptom']}\n\n"
        "## Requested Penta owners\n"
        f"{owners}\n\n"
        "## Acceptance criteria\n"
        f"{criteria}\n\n"
        "## Evidence\n"
        f"```json\n{evidence_json}\n```\n\n"
        "PentaSELF is the source of the finding. PentaPR owns the remediation PR. "
        "PentaPM owns assignment/reassignment. Existing governance, certification, and terminal merge controls remain authoritative."
    )


def ensure_issue(gh: GH, finding: dict[str, Any]) -> dict[str, Any]:
    issue = find_existing_issue(gh, finding["finding_id"])
    title = f"[PentaSELF] {finding['symptom'][:110]}"
    if issue is None:
        issue = gh.post(f"/repos/{gh.repo}/issues", {"title": title, "body": issue_body(finding)})
    else:
        gh.patch(f"/repos/{gh.repo}/issues/{issue['number']}", {"title": title, "body": issue_body(finding)})
    labels = {
        "penta:source:self",
        "penta:remediation",
        "penta:entity:issue",
        "penta:authority:pm",
        "penta:stage:open",
        f"penta:lane:{finding['lane']}",
        f"penta:risk:{finding['risk'].lower()}",
    }
    if finding["risk"] == "D3":
        labels.add("penta:hold")
    add_labels(gh, int(issue["number"]), labels)
    return issue


def ensure_branch(gh: GH, branch: str, base_branch: str) -> None:
    encoded = urllib.parse.quote(branch, safe="")
    try:
        gh.get(f"/repos/{gh.repo}/git/ref/heads/{encoded}")
        return
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
    base = gh.get(f"/repos/{gh.repo}/git/ref/heads/{urllib.parse.quote(base_branch, safe='')}")
    sha = base["object"]["sha"]
    gh.post(f"/repos/{gh.repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})


def put_manifest(gh: GH, branch: str, finding: dict[str, Any], issue_number: int) -> str:
    path = f"penta/remediations/{finding['remediation_key']}.json"
    document = dict(finding)
    document.update(
        {
            "issue_number": issue_number,
            "bootstrap_hold": True,
            "terminal_authority": "PentaMerge/PentaCloser",
            "completion_contract": "repair + tests + independent evidence + governed merge gates",
        }
    )
    raw = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")
    payload: dict[str, Any] = {
        "message": f"chore(pentaself): bootstrap remediation {finding['remediation_key']}",
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": branch,
    }
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    try:
        existing = gh.get(f"/repos/{gh.repo}/contents/{encoded_path}?ref={urllib.parse.quote(branch, safe='')}")
        payload["sha"] = existing["sha"]
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
    gh.put(f"/repos/{gh.repo}/contents/{encoded_path}", payload)
    return path


def find_existing_pr(gh: GH, branch: str) -> dict[str, Any] | None:
    owner = gh.repo.split("/", 1)[0]
    head = urllib.parse.quote(f"{owner}:{branch}", safe="")
    pulls = gh.get(f"/repos/{gh.repo}/pulls?state=all&head={head}&per_page=20")
    return pulls[0] if pulls else None


def ensure_pr(gh: GH, finding: dict[str, Any], issue: dict[str, Any], base_branch: str) -> dict[str, Any]:
    branch = f"pentaself/remediation/{finding['remediation_key']}"
    ensure_branch(gh, branch, base_branch)
    manifest_path = put_manifest(gh, branch, finding, int(issue["number"]))
    pr = find_existing_pr(gh, branch)
    title = f"fix(pentaself): remediate {finding['remediation_key']}"
    body = (
        f"{marker(finding['finding_id'])}\n\n"
        f"Refs #{issue['number']}\n\n"
        "PentaPR remediation bootstrap created from a durable PentaSELF finding. "
        f"The authoritative handoff manifest is `{manifest_path}`.\n\n"
        "**Initial state:** `penta:hold`. PentaPM must assign/reassign all required Penta workers, "
        "the repair must be committed to this branch, and the existing exact-head governance/certification "
        "gates must pass before terminal authority can act."
    )
    if pr is None:
        pr = gh.post(
            f"/repos/{gh.repo}/pulls",
            {"title": title, "head": branch, "base": base_branch, "body": body, "maintainer_can_modify": True},
        )
    elif pr.get("state") == "open":
        pr = gh.patch(f"/repos/{gh.repo}/pulls/{pr['number']}", {"title": title, "body": body, "base": base_branch})
    labels = {
        "penta:source:self",
        "penta:remediation",
        "penta:entity:pr",
        "penta:authority:pr",
        "penta:authority:pm",
        "penta:stage:review",
        "penta:hold",
        f"penta:lane:{finding['lane']}",
        f"penta:risk:{finding['risk'].lower()}",
    }
    add_labels(gh, int(pr["number"]), labels)
    return pr


def write_outputs(issue_number: int, pr_number: int, finding_id: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with open(output, "a", encoding="utf-8") as handle:
        handle.write(f"issue_number={issue_number}\n")
        handle.write(f"pr_number={pr_number}\n")
        handle.write(f"finding_id={finding_id}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--finding-file", required=True)
    parser.add_argument("--base", default="main")
    args = parser.parse_args()
    if not args.repo:
        raise SystemExit("--repo or GITHUB_REPOSITORY is required")
    with open(args.finding_file, encoding="utf-8") as handle:
        finding = normalize_finding(json.load(handle))
    gh = GH(args.repo)
    issue = ensure_issue(gh, finding)
    pr = ensure_pr(gh, finding, issue, args.base)
    write_outputs(int(issue["number"]), int(pr["number"]), finding["finding_id"])
    print(
        json.dumps(
            {
                "state": "HANDED_OFF",
                "finding_id": finding["finding_id"],
                "issue_number": issue["number"],
                "pr_number": pr["number"],
                "pr_authority": "PentaPR",
                "next_authority": "PentaPM",
                "bootstrap_hold": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
