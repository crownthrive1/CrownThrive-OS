#!/usr/bin/env python3
"""Trusted provider transport for PentaRelease PentaDocs metadata reconciliation.

This program is intended to execute only from protected-main source in a
``workflow_run`` context. It never checks out or executes candidate code. It
reads the exact candidate head through the GitHub API, applies the bounded
metadata transform from ``reconcile_pentadocs_metadata``, creates one commit,
and advances the candidate ref only when the provider head is still the exact
observed SHA. A concurrent head move therefore fails closed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import reconcile_pentadocs_metadata as core

API = "https://api.github.com"


class GitHub:
    def __init__(self, repo: str, token: str) -> None:
        self.repo = repo
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CrownThrive-PentaRelease-PentaDocs-Metadata/1.0",
        }

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers=self.headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return json.loads(raw or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:700]}") from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("POST", path, body)

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PATCH", path, body)


def verify_candidate(gh: GitHub, number: int, expected_head: str) -> tuple[dict[str, Any], str]:
    pull = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    if pull.get("state") != "open":
        raise RuntimeError("candidate_not_open")
    head = pull.get("head") or {}
    head_repo = (head.get("repo") or {}).get("full_name")
    head_ref = str(head.get("ref") or "")
    head_sha = str(head.get("sha") or "")
    if head_repo != gh.repo:
        raise RuntimeError("candidate_external_repo")
    if not head_ref.startswith("pentarelease/surface-"):
        raise RuntimeError(f"candidate_branch_out_of_scope:{head_ref}")
    if head_sha != expected_head:
        raise RuntimeError(f"candidate_head_moved:expected={expected_head}:observed={head_sha}")
    return pull, head_ref


def read_text_at_head(gh: GitHub, path: str, head_sha: str) -> tuple[str, str]:
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
    payload = gh.get(
        f"/repos/{gh.repo}/contents/{encoded_path}?ref={urllib.parse.quote(head_sha, safe='')}"
    )
    if payload.get("encoding") != "base64" or not payload.get("content"):
        raise RuntimeError(f"content_unavailable:{path}")
    raw = base64.b64decode(payload["content"].replace("\n", ""))
    return raw.decode("utf-8"), str(payload.get("sha") or "")


def create_reconciled_commit(
    gh: GitHub,
    *,
    number: int,
    expected_head: str,
) -> dict[str, Any]:
    _, head_ref = verify_candidate(gh, number, expected_head)
    tree_entries: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []

    for path in core.TARGET_PATHS:
        original, _ = read_text_at_head(gh, path, expected_head)
        reconciled, changed, reason = core.reconcile_text(original)
        if reason in {"frontmatter_missing", "title_missing"}:
            raise RuntimeError(f"metadata_hold:{path}:{reason}")
        if changed:
            blob = gh.post(
                f"/repos/{gh.repo}/git/blobs",
                {"content": reconciled, "encoding": "utf-8"},
            )
            tree_entries.append(
                {"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]}
            )
        rows.append({"path": path, "changed": changed, "reason": reason})

    if not tree_entries:
        return {
            "schema": "ct.pentarelease.pentadocs-metadata-provider.v1",
            "state": "PASS_NO_DELTA",
            "pr_number": number,
            "head_sha": expected_head,
            "head_ref": head_ref,
            "changed": 0,
            "rows": rows,
            "provider_mutation": False,
            "authority_expansion": False,
        }

    parent = gh.get(f"/repos/{gh.repo}/git/commits/{expected_head}")
    base_tree_sha = (parent.get("tree") or {}).get("sha")
    if not base_tree_sha:
        raise RuntimeError("candidate_base_tree_missing")

    tree = gh.post(
        f"/repos/{gh.repo}/git/trees",
        {"base_tree": base_tree_sha, "tree": tree_entries},
    )
    commit = gh.post(
        f"/repos/{gh.repo}/git/commits",
        {
            "message": "fix(pentarelease): reconcile PentaDocs structured metadata",
            "tree": tree["sha"],
            "parents": [expected_head],
        },
    )
    new_sha = str(commit.get("sha") or "")
    if not new_sha:
        raise RuntimeError("provider_commit_sha_missing")

    # Exact-head fence immediately before the only ref mutation. If the branch
    # moved concurrently, force=false also prevents replacing a non-ancestor.
    verify_candidate(gh, number, expected_head)
    encoded_ref = urllib.parse.quote(head_ref, safe="")
    gh.patch(
        f"/repos/{gh.repo}/git/refs/heads/{encoded_ref}",
        {"sha": new_sha, "force": False},
    )

    readback = gh.get(f"/repos/{gh.repo}/pulls/{number}")
    observed = str(((readback.get("head") or {}).get("sha")) or "")
    if observed != new_sha:
        raise RuntimeError(f"provider_readback_mismatch:expected={new_sha}:observed={observed}")

    return {
        "schema": "ct.pentarelease.pentadocs-metadata-provider.v1",
        "state": "RECONCILED",
        "pr_number": number,
        "previous_head_sha": expected_head,
        "head_sha": new_sha,
        "head_ref": head_ref,
        "changed": len(tree_entries),
        "rows": rows,
        "provider_mutation": True,
        "authority_expansion": False,
        "release_state_manufactured": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print(json.dumps({"state": "HOLD", "reason": "github_token_missing"}))
        return 78

    try:
        result = create_reconciled_commit(
            GitHub(args.repo, token),
            number=args.number,
            expected_head=args.expected_head,
        )
    except Exception as exc:  # fail closed with a bounded public error string
        print(json.dumps({"state": "HOLD", "reason": str(exc)[:1000]}, sort_keys=True))
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
