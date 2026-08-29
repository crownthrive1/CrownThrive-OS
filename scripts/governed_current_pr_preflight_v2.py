#!/usr/bin/env python3
"""Governed current-PR preflight v2.

Closes #121 by classifying only an exact registry of inert Help Center evidence
transport as neutral while keeping every unknown or material data path fail-closed.
Every pull request must also carry an exact-head originator self-certification
projection; that self-certification is candidate evidence and never substitutes
for provider gates, DAIL binding, or human-reserved authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from governed_merge_decision import (
    MANIFEST,
    changed_file_digest,
    decide,
    load_json,
    normalize_domain,
    required_specialists_for,
    trusted_changed_files_from_git,
)
from governed_current_pr_preflight import (
    CONSERVATIVE_FALLBACK_DOMAINS,
    DOCUMENTATION_PREFIXES,
    DOCUMENTATION_SUFFIXES,
    assert_missing_specialists_fail_closed,
    assert_omitted_file_fails_closed,
    assert_positive_preflight,
    assert_unclassified_file_fails_closed,
    build_packet,
    neutral_domains_for,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_CONTRACT = ROOT / "developers/manifests/governed-evidence-data-classification.v1.json"
PREFLIGHT_VERSION = "2.1.0"


def evidence_contract() -> dict[str, Any]:
    contract = load_json(EVIDENCE_CONTRACT)
    if contract.get("schema_version") != "1.0.0":
        raise SystemExit("ERROR: unsupported evidence-data classification contract")
    if contract.get("extension_never_proves_neutrality") is not True:
        raise SystemExit("ERROR: evidence contract must prohibit extension-only neutrality")
    return contract


def evidence_data_domains(path: str, contract: dict[str, Any]) -> set[str] | None:
    registered = {str(value) for value in contract.get("registered_neutral_paths", [])}
    if path in registered:
        return {
            normalize_domain(value)
            for value in contract.get("neutral_domains", ["institutional_general"])
            if normalize_domain(value)
        }

    vectors = contract.get("material_data_path_vectors", {})
    if path.startswith("data/") and isinstance(vectors, dict):
        matched: set[str] = set()
        for domain, prefixes in vectors.items():
            if any(path.startswith(str(prefix)) for prefix in prefixes):
                matched.add(normalize_domain(domain))
        if matched:
            return matched
        return set(CONSERVATIVE_FALLBACK_DOMAINS)
    return None


def deterministic_domains(path: str, policy: dict[str, Any], contract: dict[str, Any]) -> set[str]:
    data_domains = evidence_data_domains(path, contract)
    if data_domains is not None:
        return data_domains

    changed = policy.get("changed_domain_contract", {})
    rules = changed.get("path_domain_rules", []) if isinstance(changed, dict) else []
    domains: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        exact = str(rule.get("path", "")).strip()
        prefix = str(rule.get("prefix", "")).strip()
        if (exact and path == exact) or (prefix and path.startswith(prefix)):
            domains.update(
                normalize_domain(value)
                for value in rule.get("required_domains", [])
                if normalize_domain(value)
            )
    if domains:
        return domains
    if path.startswith(DOCUMENTATION_PREFIXES) or path.endswith(DOCUMENTATION_SUFFIXES):
        return {"documentation"}
    if path.startswith(("scripts/", "developers/manifests/", ".github/")):
        return {"security", "agent", "deployment"}
    return set(CONSERVATIVE_FALLBACK_DOMAINS)


def classifications_for(trusted_files: set[str], policy: dict[str, Any], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    classifications: list[dict[str, Any]] = []
    domains: set[str] = set()
    for path in sorted(trusted_files):
        item_domains = deterministic_domains(path, policy, contract)
        if not item_domains:
            raise SystemExit(f"ERROR: deterministic classification empty for {path}")
        domains.update(item_domains)
        classifications.append({
            "path": path,
            "domains": sorted(item_domains),
            "provenance": "deterministic_path_rule",
        })
    return classifications, domains


def validate_originator_self_certification(git_base: str, git_head: str) -> dict[str, Any]:
    """Require a current self-cert packet on GitHub pull_request executions."""
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return {"state": "NOT_APPLICABLE", "reason": "non_pull_request_execution"}
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("ERROR: GITHUB_EVENT_PATH missing for pull_request self-certification gate")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        number = int(event["pull_request"]["number"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("ERROR: unable to resolve pull request number for self-certification gate") from exc

    command = [
        sys.executable,
        str(ROOT / "scripts" / "penta_pr_gate_awareness.py"),
        "validate",
        "--repo",
        str(ROOT),
        "--repository",
        os.environ.get("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS"),
        "--base",
        git_base,
        "--head",
        git_head,
        "--pr-number",
        str(number),
    ]
    proc = subprocess.run(command, cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise SystemExit(f"ERROR: Penta originator self-certification HOLD: {detail[:1500]}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("ERROR: self-certification validator emitted invalid JSON") from exc
    if result.get("state") != "PASS":
        raise SystemExit("ERROR: originator self-certification did not return PASS")
    return result


def self_test(policy: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_neutral = {"institutional_general"}
    for path in contract["registered_neutral_paths"]:
        got = deterministic_domains(path, policy, contract)
        if got != expected_neutral:
            raise SystemExit(f"ERROR: registered evidence path not neutral: {path} -> {sorted(got)}")

    material_vectors = {
        "data/payments-ledger.json": {"finance"},
        "data/royalty-rates.json": {"finance"},
        "data/token-registry.json": {"blockchain"},
        "data/wallet-state.json": {"blockchain"},
        "data/license-grants.json": {"rights"},
        "data/rights-chain.json": {"rights"},
        "data/customer-records.json": {"privacy"},
        "data/privacy-export.json": {"privacy"},
        "data/localization-map.json": {"localization"},
        "data/country-routing.json": {"localization"},
    }
    for path, minimum in material_vectors.items():
        got = deterministic_domains(path, policy, contract)
        if not minimum.issubset(got):
            raise SystemExit(f"ERROR: material data path under-classified: {path} -> {sorted(got)}")

    unknown = deterministic_domains("data/unregistered-evidence-looking.json", policy, contract)
    if unknown != set(CONSERVATIVE_FALLBACK_DOMAINS):
        raise SystemExit("ERROR: unknown data path did not retain conservative fallback")

    spoof = deterministic_domains("data/help_center_article_manifest.v1.bundle.json.backup", policy, contract)
    if spoof != set(CONSERVATIVE_FALLBACK_DOMAINS):
        raise SystemExit("ERROR: path extension/name spoof incorrectly inherited neutrality")

    print(json.dumps({
        "preflight_version": PREFLIGHT_VERSION,
        "contract": contract["contract_id"],
        "registered_neutral_paths": len(contract["registered_neutral_paths"]),
        "material_negative_vectors": len(material_vectors),
        "unknown_data_fail_closed": True,
        "extension_only_neutrality": False,
        "originator_self_certification_gate": True,
        "self_test": "PASS",
    }, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-base")
    parser.add_argument("--git-head")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    policy = load_json(MANIFEST)
    contract = evidence_contract()
    if args.self_test:
        self_test(policy, contract)
        return 0
    if not args.git_base or not args.git_head:
        raise SystemExit("ERROR: --git-base and --git-head are required unless --self-test is used")

    self_certification = validate_originator_self_certification(args.git_base, args.git_head)
    trusted_files = trusted_changed_files_from_git(args.git_base, args.git_head)
    classifications, domains = classifications_for(trusted_files, policy, contract)
    required_specialists = required_specialists_for(domains, policy)
    neutral_domains = neutral_domains_for(policy) | set(contract.get("neutral_domains", []))
    neutral_only = bool(domains) and domains.issubset(neutral_domains)
    if not required_specialists and not neutral_only:
        raise SystemExit("ERROR: D2 current-PR preflight resolved no specialist requirements for non-neutral domains")

    packet = build_packet(trusted_files, classifications, domains, required_specialists)
    result = decide(packet, policy, trusted_files)
    assert_positive_preflight(result)
    missing_vectors = assert_missing_specialists_fail_closed(packet, trusted_files, policy, required_specialists)
    omitted = assert_omitted_file_fails_closed(packet, trusted_files, policy)
    unclassified = assert_unclassified_file_fails_closed(packet, trusted_files, policy)

    print(json.dumps({
        "mode": "ci_operational_preflight_non_sovereign_authority",
        "preflight_version": PREFLIGHT_VERSION,
        "evidence_contract": contract["contract_id"],
        "originator_self_certification": self_certification,
        "sovereign_authority": False,
        "trusted_changed_files_count": len(trusted_files),
        "trusted_changed_files_digest": changed_file_digest(trusted_files),
        "trusted_changed_files_redacted": True,
        "derived_changed_domains": sorted(domains),
        "neutral_only": neutral_only,
        "required_specialists": sorted(required_specialists),
        "decision_engine_executed": True,
        "positive_preflight_classification_clean": True,
        "positive_preflight_specialists_complete": True,
        "positive_preflight_auto_merge_authorized": False,
        "negative_missing_specialist_vectors": missing_vectors,
        "negative_omitted_file_proved": bool(omitted),
        "negative_unclassified_file_proved": bool(unclassified),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
