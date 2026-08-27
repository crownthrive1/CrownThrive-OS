#!/usr/bin/env python3
"""PentaPM GitHub-native reconciliation engine.

Creates/locates governed milestones and a Projects v2 control board, adds repository
issues/PRs to that project, applies deterministic milestone routing, validates
Development linkage, and emits a machine-readable receipt. It is intentionally
idempotent and never merges, releases, or self-certifies D2/D3 authority.

Public repository REST GETs may retry without Authorization when a GitHub App
installation has exhausted its read quota. GraphQL/Projects v2 and every mutation
remain authenticated. On pull-request read-only runs only, a rate-limited Projects
v2 read is recorded as deferred/non-authoritative rather than misreported as PM
drift; scheduled/apply runs continue to fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "penta_pm_policy.json"
RECEIPT_DIR = ROOT / "artifacts" / "penta-pm"
LINK_RE = re.compile(r"(?im)^\s*(closes|fixes|resolves|refs|references)\s+#(\d+)\b")
RATE_LIMIT_RE = re.compile(r"rate limit exceeded for installation|api rate limit exceeded", re.I)


def _decode_response(r):
    raw = r.read().decode() or "{}"
    return json.loads(raw)


def _runtime_error(method, url, exc):
    detail = exc.read().decode(errors="replace")
    return RuntimeError(f"GitHub {method} {url} -> {exc.code}: {detail}")


def is_rate_limit_error(exc: BaseException | str) -> bool:
    return bool(RATE_LIMIT_RE.search(str(exc)))


def request(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CrownThrive-PentaPM/1.1",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return _decode_response(r)
    except urllib.error.HTTPError as exc:
        err = _runtime_error(method, url, exc)
        # Public CrownThrive repository GETs have an independent unauthenticated
        # read surface. Never use this path for GraphQL, private content, or writes.
        if method == "GET" and url.startswith("https://api.github.com/repos/") and is_rate_limit_error(err):
            public_headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "CrownThrive-PentaPM-PublicRead/1.1",
            }
            public_req = urllib.request.Request(url, headers=public_headers, method="GET")
            try:
                with urllib.request.urlopen(public_req, timeout=30) as r:
                    return _decode_response(r)
            except urllib.error.HTTPError as public_exc:
                raise _runtime_error(method, url, public_exc) from public_exc
        raise err from exc


def graphql(token, query, variables=None):
    out = request("POST", "https://api.github.com/graphql", token, {"query": query, "variables": variables or {}})
    if out.get("errors"):
        raise RuntimeError(f"GitHub GraphQL errors: {out['errors']}")
    return out["data"]


def paginate(url, token):
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        batch = request("GET", f"{url}{sep}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise RuntimeError(f"Expected list from {url}")
        yield from batch
        if len(batch) < 100:
            return
        page += 1


def ensure_milestones(api, token, policy, apply):
    current = {m["title"]: m for m in paginate(f"{api}/milestones?state=all", token)}
    actions = []
    for spec in policy["milestones"]:
        title = spec["title"]
        if title in current:
            continue
        actions.append({"action": "create_milestone", "title": title})
        if apply:
            current[title] = request("POST", f"{api}/milestones", token, {"title": title, "description": spec["description"]})
    return current, actions


def owner_project_context(token, owner, repo):
    q = """
    query($owner:String!,$repo:String!){
      repository(owner:$owner,name:$repo){
        id
        owner{
          __typename
          login
          ... on User{
            id
            projectsV2(first:100){nodes{id title number}}
          }
          ... on Organization{
            id
            projectsV2(first:100){nodes{id title number}}
          }
        }
      }
    }
    """
    return graphql(token, q, {"owner": owner, "repo": repo})["repository"]


def ensure_project(token, owner, repo, title, apply):
    ctx = owner_project_context(token, owner, repo)
    host = ctx["owner"]
    for p in host.get("projectsV2", {}).get("nodes", []):
        if p["title"] == title:
            return p, []
    action = {"action": "create_project", "title": title}
    if not apply:
        return None, [action]
    q = """mutation($owner:ID!,$title:String!){createProjectV2(input:{ownerId:$owner,title:$title}){projectV2{id title number}}}"""
    p = graphql(token, q, {"owner": host["id"], "title": title})["createProjectV2"]["projectV2"]
    return p, [action]


def project_items_and_fields(token, project_id):
    q = """query($id:ID!){node(id:$id){... on ProjectV2{fields(first:100){nodes{... on ProjectV2FieldCommon{id name dataType}}} items(first:100){nodes{id content{... on Issue{id number} ... on PullRequest{id number}}}}}}}}"""
    return graphql(token, q, {"id": project_id})["node"]


def ensure_project_fields(token, project_id, required, apply):
    state = project_items_and_fields(token, project_id)
    names = {f["name"] for f in state["fields"]["nodes"] if f}
    actions = []
    for name in required:
        if name in names:
            continue
        actions.append({"action": "create_project_field", "name": name})
        if apply:
            q = """mutation($project:ID!,$name:String!){createProjectV2Field(input:{projectId:$project,dataType:TEXT,name:$name}){projectV2Field{... on ProjectV2Field{id name}}}}"""
            graphql(token, q, {"project": project_id, "name": name})
    return actions


def get_open_artifacts(api, token):
    return list(paginate(f"{api}/issues?state=open", token))


def classify(labels, policy):
    names = [x["name"] if isinstance(x, dict) else x for x in labels]
    lanes = [x for x in names if x.startswith("penta:lane:")]
    owner = next((x.split("penta:authority:", 1)[1] for x in names if x.startswith("penta:authority:")), "unassigned")
    risk = next((x.split("penta:risk:", 1)[1] for x in names if x.startswith("penta:risk:")), "unclassified")
    stage = next((x.split("penta:stage:", 1)[1] for x in names if x.startswith("penta:stage:")), "unclassified")
    milestone = None
    for lane in lanes:
        if lane in policy["milestone_routing"]:
            milestone = policy["milestone_routing"][lane]
            break
    milestone = milestone or "OS Production Convergence"
    return {"owner": owner, "lanes": lanes, "risk": risk, "stage": stage, "milestone": milestone}


def ensure_project_item(token, project_id, content_id, existing, number, apply):
    if number in existing:
        return []
    action = {"action": "add_project_item", "number": number}
    if apply:
        q = """mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id}}}"""
        graphql(token, q, {"project": project_id, "content": content_id})
    return [action]


def ensure_milestone(api, token, artifact, milestone, current, apply):
    existing = artifact.get("milestone") or {}
    if existing.get("title") == milestone:
        return []
    spec = current.get(milestone)
    if not spec:
        return [{"action": "hold_missing_milestone", "number": artifact["number"], "milestone": milestone}]
    action = {"action": "assign_milestone", "number": artifact["number"], "milestone": milestone}
    if apply:
        request("PATCH", f"{api}/issues/{artifact['number']}", token, {"milestone": spec["number"]})
    return [action]


def receipt(repo, mode, actions, holds, provider_readback_state="FULL"):
    payload = {
        "schema": "ct.penta.pm.receipt.v1",
        "repo": repo,
        "mode": mode,
        "generated_at_epoch": int(time.time()),
        "provider_readback_state": provider_readback_state,
        "actions": actions,
        "holds": holds,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.getenv("GITHUB_REPOSITORY"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not args.repo or "/" not in args.repo:
        raise SystemExit("--repo owner/name required")
    token = os.getenv("PENTA_PM_GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("PENTA_PM_GITHUB_TOKEN, GH_TOKEN, or GITHUB_TOKEN required")
    owner, repo = args.repo.split("/", 1)
    api = f"https://api.github.com/repos/{owner}/{repo}"
    policy = json.loads(POLICY.read_text())
    actions, holds = [], []
    provider_hold = False
    provider_readback_state = "FULL"

    try:
        milestones, a = ensure_milestones(api, token, policy, args.apply)
        actions += a
    except RuntimeError as exc:
        # REST GETs already attempt the independent public read surface. If both
        # fail, there is no trustworthy milestone view and this remains blocking.
        out = receipt(args.repo, "apply" if args.apply else "check", actions, [{"type": "milestones_provider_authority", "blocking": True, "message": str(exc)}], "UNAVAILABLE")
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        (RECEIPT_DIR / "latest.json").write_text(json.dumps(out, indent=2) + "\n")
        print(json.dumps(out, indent=2))
        return 3

    project = None
    existing = set()
    try:
        project, a = ensure_project(token, owner, repo, policy["canonical_project"], args.apply)
        actions += a
        if project:
            actions += ensure_project_fields(token, project["id"], policy["project_fields"], args.apply)
            pstate = project_items_and_fields(token, project["id"])
            existing = {n["content"]["number"] for n in pstate["items"]["nodes"] if n.get("content") and n["content"].get("number")}
    except RuntimeError as exc:
        deferred = (not args.apply) and is_rate_limit_error(exc)
        if deferred:
            provider_readback_state = "PROJECTS_V2_DEFERRED_RATE_LIMIT_READ_ONLY"
        else:
            provider_hold = True
        holds.append({
            "type": "projects_v2_provider_authority",
            "provider": "github",
            "required_secret": "PENTA_PM_GITHUB_TOKEN",
            "blocking": not deferred,
            "state": "DEFERRED_RATE_LIMIT_READ_ONLY" if deferred else "HOLD",
            "message": str(exc),
        })

    try:
        artifacts = get_open_artifacts(api, token)
    except RuntimeError as exc:
        holds.append({"type": "artifact_inventory_provider_authority", "blocking": True, "message": str(exc)})
        provider_hold = True
        artifacts = []

    for artifact in artifacts:
        labels = artifact.get("labels", [])
        governed = any((x.get("name", "") if isinstance(x, dict) else str(x)).startswith("penta:") for x in labels)
        if not governed:
            continue
        c = classify(labels, policy)
        if project:
            try:
                actions += ensure_project_item(token, project["id"], artifact["node_id"], existing, artifact["number"], args.apply)
            except RuntimeError as exc:
                provider_hold = True
                holds.append({"type": "project_item_provider_authority", "number": artifact["number"], "blocking": True, "message": str(exc)})
        actions += ensure_milestone(api, token, artifact, c["milestone"], milestones, args.apply)
        if "pull_request" in artifact and not LINK_RE.search(artifact.get("body") or ""):
            holds.append({"type": "missing_development_link", "number": artifact["number"], "blocking": True})
        if c["owner"] == "unassigned" or not c["lanes"] or c["risk"] == "unclassified" or c["stage"] == "unclassified":
            holds.append({"type": "incomplete_classification", "number": artifact["number"], "classification": c, "blocking": True})

    out = receipt(args.repo, "apply" if args.apply else "check", actions, holds, provider_readback_state)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPT_DIR / "latest.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))

    blocking_holds = [h for h in holds if h.get("blocking", True)]
    if provider_hold:
        return 3
    if args.check and (actions or blocking_holds):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
