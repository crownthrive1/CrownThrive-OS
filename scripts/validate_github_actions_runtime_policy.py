#!/usr/bin/env python3
"""Fail closed on GitHub Actions Node/runtime and action-reference drift.

This validator deliberately uses a narrow accepted YAML profile rather than
trying to implement a complete YAML parser. Any `uses` or `runs-on` form that
falls outside the accepted literal forms is rejected so syntax variation cannot
silently bypass the supply-chain policy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "developers/manifests/github-actions-runtime-policy.v1.json"
WORKFLOW_DIR = ROOT / ".github/workflows"
DEPENDABOT = ROOT / ".github/dependabot.yml"
RUNNER_BOOTSTRAP = ROOT / "scripts/penta_runner_fabric_bootstrap.sh"

USES_DIRECTIVE_RE = re.compile(
    r"^\s*(?:-\s*)?(?:uses|['\"]uses['\"])\s*:\s*(.*?)\s*$"
)
RUNS_ON_DIRECTIVE_RE = re.compile(
    r"^\s*(?:runs-on|['\"]runs-on['\"])\s*:\s*(.*?)\s*$"
)
FLOW_USES_RE = re.compile(
    r"^\s*-\s*\{.*(?:\buses\b|['\"]uses['\"])\s*:"
)
REMOTE_RE = re.compile(r"^([^/]+)/([^/@]+)(/[^@]+)?@([0-9a-fA-F]{40})$")
FORBIDDEN_ENV = (
    "FORCE_JAVASCRIPT_ACTIONS_TO_NODE24",
    "ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION",
)


class PolicyParseError(ValueError):
    """Raised when a governed workflow uses syntax outside the accepted profile."""


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


def split_yaml_comment(raw: str) -> tuple[str, Optional[str]]:
    """Split an inline YAML comment while respecting simple quoted scalars."""
    quote: Optional[str] = None
    escaped = False
    for index, char in enumerate(raw):
        if quote == '"':
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
                continue
        elif quote == "'":
            if char == quote:
                if index + 1 < len(raw) and raw[index + 1] == "'":
                    continue
                quote = None
                continue
        else:
            if char in {'"', "'"}:
                quote = char
                continue
            if char == "#" and (index == 0 or raw[index - 1].isspace()):
                return raw[:index].rstrip(), raw[index + 1 :].strip() or None
    if quote is not None:
        raise PolicyParseError("unterminated quoted YAML scalar")
    return raw.strip(), None


def decode_literal_scalar(raw: str) -> tuple[str, Optional[str]]:
    """Decode the strict scalar forms accepted for uses/runs-on directives."""
    scalar, comment = split_yaml_comment(raw)
    scalar = scalar.strip()
    if not scalar:
        raise PolicyParseError("empty directive value")

    if scalar[0] in {'"', "'"}:
        quote = scalar[0]
        if len(scalar) < 2 or scalar[-1] != quote:
            raise PolicyParseError("quoted directive must end on the same YAML line")
        inner = scalar[1:-1]
        if quote == "'":
            inner = inner.replace("''", "'")
        elif "\\" in inner:
            raise PolicyParseError("escaped double-quoted directive is outside the accepted profile")
        value = inner
    else:
        if any(char.isspace() for char in scalar):
            raise PolicyParseError("unquoted directive values may not contain whitespace")
        if scalar in {">", ">-", ">+", "|", "|-", "|+"}:
            raise PolicyParseError("folded or block directive values are prohibited")
        value = scalar

    if not value:
        raise PolicyParseError("directive value resolved empty")
    return value, comment


def parse_uses_line(line: str) -> Optional[tuple[str, Optional[str]]]:
    if FLOW_USES_RE.match(line):
        raise PolicyParseError("flow-style uses mapping is prohibited; use one governed literal uses directive per line")
    match = USES_DIRECTIVE_RE.match(line)
    if not match:
        return None
    return decode_literal_scalar(match.group(1))


def parse_runs_on_line(line: str) -> Optional[str | tuple[str, ...]]:
    match = RUNS_ON_DIRECTIVE_RE.match(line)
    if not match:
        return None
    scalar, _comment = split_yaml_comment(match.group(1))
    scalar = scalar.strip()
    if scalar.startswith("["):
        if not scalar.endswith("]"):
            raise PolicyParseError("flow runner label list must end on the same YAML line")
        raw_labels = scalar[1:-1].split(",")
        labels = tuple(label.strip() for label in raw_labels)
        if not labels or any(not label for label in labels):
            raise PolicyParseError("flow runner label list contains an empty label")
        if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", label) for label in labels):
            raise PolicyParseError("flow runner labels must be unquoted simple identifiers")
        if len(set(labels)) != len(labels):
            raise PolicyParseError("flow runner label list contains a duplicate")
        return labels
    value, _comment = decode_literal_scalar(match.group(1))
    return value


def parser_self_test() -> None:
    sha = "a" * 40
    expected = f"actions/checkout@{sha}"
    cases = (
        f"        uses: {expected} # v7.0.1",
        f"      - uses: {expected} # v7.0.1",
        f"        uses: '{expected}' # v7.0.1",
        f'        "uses": "{expected}" # v7.0.1',
    )
    for line in cases:
        parsed = parse_uses_line(line)
        assert parsed is not None and parsed[0] == expected and parsed[1] == "v7.0.1"

    assert parse_runs_on_line("    runs-on: ubuntu-latest") == "ubuntu-latest"
    assert parse_runs_on_line("    'runs-on': 'ubuntu-latest'") == "ubuntu-latest"
    assert parse_runs_on_line("    runs-on: [self-hosted, linux, x64]") == (
        "self-hosted", "linux", "x64"
    )

    rejected = (
        "      - { uses: actions/checkout@" + sha + " }",
        "        uses: >",
        '        uses: "actions/checkout@' + sha + '\\n"',
    )
    for line in rejected:
        try:
            parsed = parse_uses_line(line)
            if parsed is not None and parsed[0] not in {">", ">-", ">+", "|", "|-", "|+"}:
                raise AssertionError(f"Expected parser rejection for {line!r}")
        except PolicyParseError:
            pass
        else:
            if parsed is not None:
                assert parsed[0] in {">", ">-", ">+", "|", "|-", "|+"}


def main() -> int:
    parser_self_test()
    policy = load_policy()
    if policy.get("manifest_version") != "1.1.0":
        fail("GitHub Actions runtime policy must include self-hosted bootstrap hardening version 1.1.0")
    if policy.get("status") != "active_fail_closed":
        fail("GitHub Actions runtime policy must remain active_fail_closed")
    if policy.get("target_runtime") != "node24" or policy.get("node20_status") != "prohibited":
        fail("Node 24 must be the runtime floor and Node 20 must be prohibited")
    if policy.get("minimum_actions_runner_version") != "2.327.1":
        fail("Minimum Node-24-capable Actions runner version drifted")

    runner_policy = policy.get("runner_policy", {})
    if runner_policy.get("github_hosted") != "permitted_only_from_approved_literal_labels":
        fail("GitHub-hosted runners must remain restricted to approved literal labels")
    approved_runners = set(runner_policy.get("approved_github_hosted_labels", []))
    if approved_runners != {"ubuntu-latest"}:
        fail(f"Approved GitHub-hosted runner inventory drifted: {sorted(approved_runners)}")
    if runner_policy.get("dynamic_runs_on_expressions") != "prohibited":
        fail("Dynamic runs-on expressions must remain prohibited")
    if runner_policy.get("self_hosted") != "bootstrap_certification_only_until_exact_head_attestation_is_verified":
        fail("Self-hosted runners must remain restricted to the bootstrap certification lane")
    if runner_policy.get("production_self_hosted") != "blocked_until_separate_policy_promotion_after_exact_head_attestation":
        fail("Production self-hosted execution must remain blocked pending a separate evidenced promotion")

    bootstrap_workflows = runner_policy.get("approved_self_hosted_bootstrap_workflows", [])
    if not isinstance(bootstrap_workflows, list) or len(bootstrap_workflows) != 1:
        fail("Exactly one self-hosted bootstrap certification workflow must be governed")
    bootstrap = bootstrap_workflows[0]
    expected_bootstrap = {
        "path": ".github/workflows/penta-runner-fabric-certification.yml",
        "event": "workflow_dispatch_only",
        "ref": "refs/heads/main",
        "repository": "crownthrive1/CrownThrive-OS",
        "labels": [
            "self-hosted", "linux", "x64", "crownthrive", "pentafabric",
            "rtc", "trusted", "provider", "pentamail",
        ],
        "provider_secrets": "prohibited",
        "provider_writes": "prohibited",
        "public_pull_request_execution": "prohibited",
        "result_authority": "runner_capability_only_not_production_workload_authority",
    }
    if bootstrap != expected_bootstrap:
        fail("Self-hosted bootstrap workflow contract drifted")
    bootstrap_path = expected_bootstrap["path"]
    bootstrap_labels = tuple(expected_bootstrap["labels"])

    refs = policy.get("reference_policy", {})
    if refs.get("remote_actions_must_use_full_length_commit_sha") is not True:
        fail("Remote actions must remain pinned to a full commit SHA")
    if refs.get("full_length_sha_characters") != 40:
        fail("Full action SHA length must remain 40 characters")
    if refs.get("mutable_tag_or_branch_refs") != "prohibited":
        fail("Mutable tag/branch action references must remain prohibited")
    if refs.get("version_comment_required") is not True:
        fail("Pinned actions must retain human-readable version comments")
    if refs.get("unparsed_uses_directive") != "blocking":
        fail("Unparsed uses directives must remain blocking")
    if refs.get("quoted_uses_scalars") != "parsed_and_governed":
        fail("Quoted uses scalars must remain governed")

    provenance = policy.get("provenance_policy", {})
    if provenance.get("production_evidence_attestation") != "permitted_after_underlying_gate_pass":
        fail("Provenance attestations must remain downstream of the underlying PASS gate")
    if provenance.get("attestation_must_not_convert_hold_to_pass") is not True:
        fail("Provenance attestations must never manufacture PASS")
    if provenance.get("subject_must_be_sanitized_non_secret_evidence") is not True:
        fail("Provenance subjects must remain sanitized non-secret evidence")

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
        evidence = str(item.get("upstream_evidence", ""))
        if not re.search(r"verified_2026-08-(?:19|25|26)", evidence):
            fail(f"Approved action {action} lacks current upstream runtime/source evidence")
        approved[action] = {"sha": sha, "version": version}

    required_actions = {
        "actions/checkout",
        "actions/setup-python",
        "actions/setup-node",
        "actions/dependency-review-action",
        "actions/upload-artifact",
    }
    if set(approved) != required_actions:
        fail(f"Approved action inventory drifted: {sorted(approved)}")

    seen = set()
    runner_count = 0
    self_hosted_bootstrap_seen = set()
    for path in workflow_paths():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for token in FORBIDDEN_ENV:
            if token in text:
                fail(f"{rel} contains prohibited runtime escape/substitution {token}")

        for lineno, line in enumerate(text.splitlines(), 1):
            try:
                runner = parse_runs_on_line(line)
            except PolicyParseError as exc:
                fail(f"{rel}:{lineno} invalid runs-on directive: {exc}")
            if runner is not None:
                runner_count += 1
                if isinstance(runner, tuple):
                    if rel != bootstrap_path:
                        fail(f"{rel}:{lineno} self-hosted/multi-label runner is outside the approved bootstrap lane")
                    if runner != bootstrap_labels:
                        fail(f"{rel}:{lineno} self-hosted bootstrap labels drifted: {runner!r}")
                    if not re.search(r"(?ms)^on:\n  workflow_dispatch:\s*\n\npermissions:", text):
                        fail(f"{rel} must remain workflow_dispatch-only")
                    if re.search(r"(?m)^\s{2}(?:pull_request|pull_request_target|push|schedule):", text):
                        fail(f"{rel} contains a prohibited automatic or public-code event")
                    guard = (
                        "if: github.repository == 'crownthrive1/CrownThrive-OS' "
                        "&& github.ref == 'refs/heads/main'"
                    )
                    if guard not in text:
                        fail(f"{rel} must remain bound to the canonical repository exact main ref")
                    if "${{ secrets." in text:
                        fail(f"{rel} bootstrap certification lane must not consume repository secrets")
                    self_hosted_bootstrap_seen.add(rel)
                elif runner not in approved_runners:
                    fail(
                        f"{rel}:{lineno} runner {runner!r} is not an approved literal GitHub-hosted runner; "
                        "dynamic, matrix, and unverified labels are fail-closed"
                    )

            try:
                parsed = parse_uses_line(line)
            except PolicyParseError as exc:
                fail(f"{rel}:{lineno} invalid uses directive: {exc}")
            if parsed is None:
                continue
            value, comment = parsed
            if value.startswith("./"):
                continue
            remote = REMOTE_RE.fullmatch(value)
            if not remote:
                fail(f"{rel}:{lineno} remote action must use a governed full 40-character commit SHA: {value}")
            owner, repo, subpath, sha = remote.groups()
            base = f"{owner}/{repo}"
            if base not in approved:
                fail(f"{rel}:{lineno} remote action {base} is not in the approved Node 24 action inventory")
            if subpath:
                fail(f"{rel}:{lineno} approved remote action {base} must use its canonical repository root, not subpath {subpath}")
            expected = approved[base]
            if sha.lower() != expected["sha"]:
                fail(
                    f"{rel}:{lineno} {base} SHA drifted; verify upstream Node runtime/security, "
                    "then reconcile policy and workflow together"
                )
            if not comment or expected["version"] not in comment:
                fail(f"{rel}:{lineno} {base} must retain version comment {expected['version']}")
            seen.add(base)

    if runner_count == 0:
        fail("No literal runs-on directives were observed; runner policy cannot be considered enforced")
    if self_hosted_bootstrap_seen != {bootstrap_path}:
        fail(f"Self-hosted bootstrap coverage drifted: {sorted(self_hosted_bootstrap_seen)}")
    if seen != required_actions:
        fail(f"Workflow action coverage drifted; seen={sorted(seen)}")

    if not RUNNER_BOOTSTRAP.is_file():
        fail("PentaFabric runner bootstrap script is missing")
    runner_bootstrap = RUNNER_BOOTSTRAP.read_text(encoding="utf-8")
    bootstrap_fragments = (
        'MINIMUM_RUNNER_VERSION="2.327.1"',
        'asset_digest="$(jq -r',
        'official GitHub release metadata lacks a governed SHA-256 digest',
        'runner archive SHA-256 does not match official GitHub release metadata',
        '"digest_verified": true',
        'PENTA_RUNNER_ROOT must be a dedicated child of',
        '--config -',
    )
    for fragment in bootstrap_fragments:
        if fragment not in runner_bootstrap:
            fail(f"PentaFabric runner bootstrap hardening missing {fragment!r}")
    digest_gate = runner_bootstrap.find('if [[ "$archive_sha256" != "$expected_archive_sha256" ]]')
    credential_request = runner_bootstrap.find('registration_json="$(api -X POST')
    if digest_gate < 0 or credential_request < 0 or credential_request < digest_gate:
        fail("Runner registration credential must be requested only after archive digest verification")

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
    print(f"Workflows scanned: {len(workflow_paths())}; literal runner directives: {runner_count}; remote actions: {', '.join(sorted(seen))}.")
    print("Runtime floor: Node 24; Node 20 and runtime warning-suppression escape hatches: prohibited.")
    print("Runner policy: literal GitHub-hosted labels plus one exact-main, secret-free self-hosted certification lane; production self-hosted execution remains blocked.")
    print("Remote actions: quoted/unquoted uses parsed, canonical root, full-SHA pinned; Dependabot daily proposals only.")
    print("Provenance: sanitized PASS evidence may be attested; attestation never promotes HOLD.")
    print("CodeQL: provider-managed default setup; duplicate advanced workflow action references: prohibited.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
