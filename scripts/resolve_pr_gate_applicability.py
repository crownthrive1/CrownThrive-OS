#!/usr/bin/env python3
"""Resolve CrownThrive PR gate applicability from a trusted exact Git diff.

This resolver does not grant merge/release authority. It classifies which merge
validation groups are relevant to the exact changed paths and emits a
machine-readable submission contract. Unrelated controls are NOT_APPLICABLE,
not PASS and not FAILURE.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "config/penta_pr_gate_applicability.json"


class ApplicabilityError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_policy(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApplicabilityError(f"invalid applicability policy: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != "ct.penta.pr-gate-applicability.v1":
        raise ApplicabilityError("unsupported applicability policy schema")
    groups = value.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ApplicabilityError("applicability policy has no groups")
    return value


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise ApplicabilityError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def ensure_commit(repo: Path, ref: str) -> None:
    git(repo, "cat-file", "-e", f"{ref}^{{commit}}")


def changed_paths(repo: Path, base: str, head: str) -> list[str]:
    ensure_commit(repo, base)
    ensure_commit(repo, head)
    raw = git(repo, "diff", "--name-only", "--find-renames", f"{base}...{head}")
    return sorted({line.strip().replace("\\", "/") for line in raw.splitlines() if line.strip()})


def _matches(path: str, rule: Mapping[str, Any]) -> bool:
    normalized = path.replace("\\", "/").lower()
    suffix = Path(normalized).suffix
    extensions = {str(item).lower() for item in rule.get("extensions", [])}
    if suffix and suffix in extensions:
        return True
    for pattern in rule.get("patterns", []):
        candidate = str(pattern).replace("\\", "/").lower()
        if fnmatch.fnmatchcase(normalized, candidate):
            return True
        if candidate.startswith("**/") and fnmatch.fnmatchcase(normalized, candidate[3:]):
            return True
    return False


def infer_change_class(required: Sequence[str]) -> str:
    required_set = set(required)
    if "workflow_policy" in required_set or "phase_control" in required_set or "phase3_state" in required_set:
        return "governance_control"
    if "security" in required_set:
        return "security_or_runtime"
    if "namespace_api" in required_set:
        return "api_or_provider_runtime"
    if "agent_governance" in required_set or "penta_control" in required_set:
        return "penta_or_agent_runtime"
    if required_set and required_set <= {"documentation", "homepage"}:
        return "documentation_or_projection"
    if required_set:
        return "bounded_source_change"
    return "unclassified_source_change"


def infer_risk(required: Sequence[str]) -> str:
    elevated = {
        "workflow_policy",
        "phase_control",
        "phase3_state",
        "security",
        "namespace_api",
        "agent_governance",
        "penta_control",
        "security_self_heal",
    }
    return "D2" if set(required).intersection(elevated) else "D1"


def resolve_paths(paths: Sequence[str], policy: Mapping[str, Any]) -> dict[str, Any]:
    groups = policy["groups"]
    required: list[str] = []
    not_applicable: list[str] = []
    details: dict[str, Any] = {}
    for group_name, rule in groups.items():
        matched = sorted(path for path in paths if _matches(path, rule))
        applicable = bool(matched)
        if applicable:
            required.append(group_name)
            state = "REQUIRED"
        else:
            not_applicable.append(group_name)
            state = "NOT_APPLICABLE"
        details[group_name] = {
            "state": state,
            "owner": rule.get("owner"),
            "matched_paths": matched,
            "evidence_required": rule.get("evidence", []),
            "repair_action": rule.get("repair_action"),
        }

    required.sort()
    not_applicable.sort()
    contract: dict[str, Any] = {
        "schema": "ct.penta.pr-submission.v1",
        "policy_schema": policy.get("schema"),
        "policy_version": policy.get("version"),
        "required_status_context": policy.get("required_status_context"),
        "change_class": infer_change_class(required),
        "risk_class": infer_risk(required),
        "changed_files": sorted(paths),
        "required_merge_groups": required,
        "not_applicable_groups": not_applicable,
        "groups": details,
        "universal_merge_controls": policy.get("universal_merge_controls", []),
        "release_gates": policy.get("release_gates", {}),
        "authority_created": False,
    }
    contract["contract_sha256"] = sha256_json(contract)
    return contract


def resolve(repo: Path, base: str, head: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    contract = resolve_paths(changed_paths(repo, base, head), policy)
    contract["base_sha"] = base
    contract["head_sha"] = head
    contract.pop("contract_sha256", None)
    contract["contract_sha256"] = sha256_json(contract)
    return contract


def write_github_output(path: Path, contract: Mapping[str, Any], policy: Mapping[str, Any]) -> None:
    lines = [
        f"change_class={contract['change_class']}",
        f"risk_class={contract['risk_class']}",
        f"contract_sha256={contract['contract_sha256']}",
        "required_groups=" + ",".join(contract["required_merge_groups"]),
    ]
    required = set(contract["required_merge_groups"])
    for group_name in policy["groups"]:
        lines.append(f"{group_name}={'true' if group_name in required else 'false'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="strict")


def self_test(policy: Mapping[str, Any]) -> dict[str, Any]:
    vectors = [
        ("docs_only", ["README.md"], {"documentation"}, {"security", "phase_control", "phase3_state"}),
        ("migration", ["supabase/migrations/20260831_example.sql"], {"security"}, {"documentation", "homepage", "phase3_state"}),
        ("homepage", ["scripts/render_homepage_projection.py"], {"homepage"}, {"collab_portal", "phase3_state"}),
        ("workflow", [".github/workflows/example.yml"], {"workflow_policy", "security"}, {"homepage", "phase3_state"}),
        ("penta_pr", ["scripts/penta_pr_lifecycle.py"], {"penta_control", "pm_routing"}, {"homepage", "phase3_state"}),
        ("collab_doc", ["docs/collab-portal-runbook.mdx"], {"documentation", "collab_portal"}, {"homepage", "phase3_state"}),
        ("phase3_state", ["docs/phase3/CURRENT_STATE.md"], {"documentation", "phase3_state"}, {"homepage"}),
        ("asset", ["assets/logo.png"], set(), {"security", "documentation", "phase_control", "phase3_state"}),
    ]
    results: list[dict[str, Any]] = []
    for name, paths, expected, forbidden in vectors:
        contract = resolve_paths(paths, policy)
        required = set(contract["required_merge_groups"])
        missing = sorted(expected - required)
        unexpected = sorted(forbidden.intersection(required))
        if missing or unexpected:
            raise ApplicabilityError(
                f"self-test {name} failed missing={missing} unexpected={unexpected} required={sorted(required)}"
            )
        results.append({"name": name, "required": sorted(required)})
    return {
        "schema": "ct.penta.pr-gate-applicability.self-test.v1",
        "state": "PASS",
        "vectors": results,
        "authority_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY.relative_to(ROOT)))
    parser.add_argument("--json-output")
    parser.add_argument("--github-output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    policy_path = Path(args.policy)
    if not policy_path.is_absolute():
        policy_path = repo / policy_path
    policy = load_policy(policy_path)

    if args.self_test:
        print(json.dumps(self_test(policy), sort_keys=True))
        return 0
    if not args.base or not args.head:
        raise SystemExit("--base and --head are required unless --self-test is used")

    contract = resolve(repo, args.base, args.head, policy)
    rendered = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        Path(args.json_output).write_text(rendered, encoding="utf-8")
    if args.github_output:
        write_github_output(Path(args.github_output), contract, policy)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApplicabilityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
