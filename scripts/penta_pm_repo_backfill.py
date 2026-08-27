#!/usr/bin/env python3
"""PentaPM repository-scoped retroactive metadata backfill.

Uses the repository GITHUB_TOKEN, not the Projects-v2 PAT, to repair GitHub-native
Development linkage on governed open pull requests. The canonical PentaPM umbrella
issue #584 explicitly governs retroactive metadata convergence, so an orphaned PR is
bound with `Refs #584` without asserting that the PR closes the umbrella issue.

This helper is idempotent and does not merge, approve, release, or change D2/D3
authority. It never handles secret values.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

LINK_RE = re.compile(r"(?im)^\s*(closes|fixes|resolves|refs|references)\s+#(\d+)\b")
MARKER = "<!-- penta-pm:development-backfill:v1 -->"
UMBRELLA = 584


def request(method: str, url: str, token: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "CrownThrive-PentaPM-RepoBackfill/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads((response.read().decode() or "{}"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub {method} {url} -> {exc.code}: {detail}") from exc


def paginate(url: str, token: str):
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


def governed(labels) -> bool:
    return any(
        (label.get("name", "") if isinstance(label, dict) else str(label)).startswith("penta:")
        for label in labels
    )


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    if not repo or "/" not in repo:
        raise SystemExit("GITHUB_REPOSITORY owner/name required")
    if not token:
        raise SystemExit("repository GITHUB_TOKEN required")

    api = f"https://api.github.com/repos/{repo}"
    repaired = []
    already_linked = []

    for artifact in paginate(f"{api}/issues?state=open", token):
        if "pull_request" not in artifact or not governed(artifact.get("labels", [])):
            continue
        number = artifact["number"]
        body = artifact.get("body") or ""
        if LINK_RE.search(body):
            already_linked.append(number)
            continue
        suffix = (
            f"\n\n{MARKER}\n"
            "## PentaPM Development linkage\n\n"
            f"Refs #{UMBRELLA}\n"
        )
        request("PATCH", f"{api}/pulls/{number}", token, {"body": body.rstrip() + suffix})
        repaired.append(number)

    result = {
        "schema": "ct.penta.pm.repo-backfill.v1",
        "repository": repo,
        "umbrella_issue": UMBRELLA,
        "repaired_prs": repaired,
        "already_linked_count": len(already_linked),
        "state": "pass",
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
