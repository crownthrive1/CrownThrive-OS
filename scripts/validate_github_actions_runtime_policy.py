#!/usr/bin/env python3
"""Fail closed on GitHub Actions Node/runtime and action-reference drift."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
WORKFLOW_DIR = ROOT / ".github/workflows"
DEPENDABOT = ROOT / ".github/dependabot.yml"

USES_RE = re.compile(r"^\s*uses:\s*([^\s#]+)(?:\s+#\s*(.+?))?\s*$")
REMOTE_RE = re.compile(r"^([^/]+)/([^/@]+)(/[^@]+)?@([0-9a-fA-F]{40})$")
FORBIDDEN_ENV = (
    "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24",
    "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION",
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_policy() -> dict:
    if not POLICY_PATH.is_file():
        fail(f"Missing runtime policy: {POLICY_PATH.relative_to(ROOT)}")
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def workflow_paths() -> list[Path]:
    paths = sorted(set(WORKFLOW_DIR.glob("*.yml")) | set(WORKFLOW_DIR.glob("*.yaml")))
    if not paths:
        fail("No GitHub Actions workflows found")
    return paths


def main() -> int:
    policy = load_policy()
    if policy.get("status") != "active_fail_closed":
        fail("GitHub Actions runtime policy must remain active_fail_closed")
    if policy.get("target_runtime") != "node24" or policy.get("node20_status") != "prohibited":
        fail("Node 24 must be the runtime floor and Node 20 must be prohibited")
    if policy.get("minimum_actions_runner_version") != "2.327.1":
        fail("Minimum Node-24-capable Actions runner version drifted")
    if policy.get("runner_policy", {}).get("self_hosted") != "blocked_until_node24_runner_attestation_is_machine_verified":
        fail("Self-hosted runners must remain blocked until Node 24 runner attestation is machine verified")

    refs = policy.get("reference_policy", {})
    if refs.get("remote_actions_must_use_full_length_commit_sha") is not True:
        fail("Remote actions must remain pinned to a full commit SHA")
    if refs.get("full_length_sha_characters") != 40:
        fail("Full action SHA length must remain 40 characters")
    if refs.get("mutable_tag_or_branch_refs") != "prohibited":
        fail("Mutable tag/branch action references must remain prohibited")
    if refs.get("version_comment_required") is not True:
        fail("Pinned actions must retain human-readable version comments")

    if policy.get("escape_hatches", {}).get("ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION") != "prohibited":
        fail("Insecure Node runtime escape hatch must remain prohibited")

    approved = {}
    for item in policy.get("approved_actions", []):
        action = item.get("uses")
        sha = item.get("sha")
        version = item.get("version")
        if not action or not re.fullmatch(r"[0-9a-f]{40}", str(sha)):
            fail(f"Approved action {action!r} lacks a full lowercase SHA")
        if item.get("runtime") != "node24" or item.get("compatibility") != "approved":
            fail(f"Approved action {action} is not explicitly Node 24 compatible")
        approved[action] = {"sha": sha, "version": version}

    required_actions = {
        "actions/checkout",
        "actions/setup-python",
        "actions/dependency-review-action",
    }
    if set(approved) != required_actions:
        fail(f"Approved action inventory drifted: {sorted(approved)}")

    seen = set()
    for path in workflow_paths():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for token in FORBIDDEN_ENV:
            if token in text:
                fail(f"{rel} contains prohibited runtime escape/substitution {token}")
        if re.search(r"runs-on:\s*(?:\[[^\]]*self-hosted|self-hosted)", text, flags=re.IGNORECASE):
            fail(f"{rel} uses self-hosted runner without machine-verified Node 24 runner attestation")

        for lineno, line in enumerate(text.splitlines(), 1):
            match = USES_RE.match(line)
            if not match:
                continue
            value, comment = match.groups()
            if value.startswith("./"):
                continue
            remote = REMOTE_RE.match(value)
            if not remote:
                fail(f"{rel}:{lineno} remote action must use a full 40-character commit SHA: {value}")
            owner, repo, _subpath, sha = remote.groups()
            base = f"{owner}/{repo}"
            if base not in approved:
                fail(f"{rel}:{lineno} remote action {base} is not in the approved Node 24 action inventory")
            expected = approved[base]
            if sha.lower() != expected["sha"]:
                fail(
                    f"{rel}:{lineno} {base} SHA drifted; verify upstream Node runtime/security, "
                    "then reconcile policy and workflow together"
                )
            if not comment or expected["version"] not in comment:
                fail(f"{rel}:{lineno} {base} must retain version comment {expected['version']}")
            seen.add(base)

    if seen != required_actions:
        fail(f"Workflow action coverage drifted; seen={sorted(seen)}")

    dependabot = DEPENDABOT.read_text(encoding="utf-8") if DEPENDABOT.is_file() else ""
    for fragment in (
        'package-ecosystem: "github-actions"',
        'directory: "/"',
        'interval: "daily"',
        'timezone: "America/New_York"',
    ):
        if fragment not in dependabot:
            fail(f"Dependabot GitHub Actions self-healing configuration missing {fragment!r}")

    self_heal = policy.get("self_healing", {})
    if self_heal.get("update_source") != "dependabot_github_actions":
        fail("GitHub Actions update source must remain Dependabot")
    if self_heal.get("direct_to_main_mutation") is not False:
        fail("Runtime self-healing must not mutate main directly")
    if self_heal.get("merge_authority") != "agent_sovereign_quorum":
        fail("Runtime update PRs must remain subject to agent-sovereign quorum")

    print("GitHub Actions runtime and supply-chain policy passed.")
    print(f"Workflows scanned: {len(workflow_paths())}; remote actions: {', '.join(sorted(seen))}.")
    print("Runtime floor: Node 24; Node 20 and runtime warning-suppression escape hatches: prohibited.")
    print("Remote actions: full-SHA pinned; Dependabot: daily bounded update proposals; direct-to-main repair: disabled.")
    print("CodeQL: provider-managed default setup; duplicate advanced workflow action references: prohibited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
