#!/usr/bin/env python3
"""PentaPM GitHub-native reconciliation engine.

Creates/locates governed milestones and a Projects v2 control board, adds repository
issues/PRs to that project, applies deterministic milestone routing, validates
Development linkage, and emits a machine-readable receipt. It is intentionally
idempotent and never merges, releases, or self-certifies D2/D3 authority.
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
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "penta_pm_policy.json"
RECEIPT_DIR = ROOT / "artifacts" / "penta-pm"
LINK_RE = re.compile(r"(?im)^\s*(closes|fixes|resolves|refs|references)\s+#(\d+)\b")


def request(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CrownThrive-PentaPM/1.0",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub {method} {url} -> {exc.code}: {detail}") from exc


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
    q = """query($owner:String!,$repo:String!){repository(owner:$owner,name:$repo){id owner{__typename login ... on User{id projectsV2(first:100){nodes{id title number}}} ... on Organization{id projectsV2(first:100){nodes{id title number}}}}}}}"""
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
    if artifact.get("milestone", {}).get("title") == milestone:
        return []
    spec = current.get(milestone)
    if not spec:
        return [{"action": "hold_missing_milestone", "number": artifact["number"], "milestone": milestone}]
    action = {"action": "assign_milestone", "number": artifact["number"], "milestone": milestone}
    if apply:
        request("PATCH", f"{api}/issues/{artifact['number']}", token, {"milestone": spec["number"]})
    return [action]


def receipt(repo, mode, actions, holds):
    payload = {
        "schema": "ct.penta.pm.receipt.v1",
        "repo": repo,
        "mode": mode,
        "generated_at_epoch": int(time.time()),
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

    milestones, a = ensure_milestones(api, token, policy, args.apply)
    actions += a
    project, a = ensure_project(token, owner, repo, policy["canonical_project"], args.apply)
    actions += a
    if project:
        actions += ensure_project_fields(token, project["id"], policy["project_fields"], args.apply)
        pstate = project_items_and_fields(token, project["id"])
        existing = {n["content"]["number"] for n in pstate["items"]["nodes"] if n.get("content") and n["content"].get("number")}
    else:
        existing = set()

    for artifact in get_open_artifacts(api, token):
        labels = artifact.get("labels", [])
        governed = any((x.get("name", "") if isinstance(x, dict) else str(x)).startswith("penta:") for x in labels)
        if not governed:
            continue
        c = classify(labels, policy)
        if project:
            actions += ensure_project_item(token, project["id"], artifact["node_id"], existing, artifact["number"], args.apply)
        actions += ensure_milestone(api, token, artifact, c["milestone"], milestones, args.apply)
        if "pull_request" in artifact and not LINK_RE.search(artifact.get("body") or ""):
            holds.append({"type": "missing_development_link", "number": artifact["number"]})
        if c["owner"] == "unassigned" or not c["lanes"] or c["risk"] == "unclassified" or c["stage"] == "unclassified":
            holds.append({"type": "incomplete_classification", "number": artifact["number"], "classification": c})

    out = receipt(args.repo, "apply" if args.apply else "check", actions, holds)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPT_DIR / "latest.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    if args.check and (actions or holds):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
