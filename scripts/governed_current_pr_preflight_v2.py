#!/usr/bin/env python3
"""Governed current-PR preflight v2.

Closes #121 by classifying only an exact registry of inert Help Center evidence
transport as neutral while keeping every unknown or material data path fail-closed.
Every pull request must also carry exact-head originator readiness evidence. Legacy
SELF_CERTIFIED packets may be consumed only through the bounded bootstrap bridge
below, which validates them with the exact trusted base implementation and then
normalizes them to zero-authority same-lane readiness evidence. They never
substitute for provider gates, DAIL binding, CHLOM/CIE decisions, or independent
PentaCertifier authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
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
PREFLIGHT_VERSION = "2.2.0"
LEGACY_SEMANTIC_ERROR = "legacy evidence schema is not explicitly bound to originator readiness semantics"
LEGACY_EVIDENCE_SCHEMA = "ct.penta.pr.self-certification.v1"
LEGACY_RECEIPT_SCHEMA = "crownthrive.penta.serialized.git-receipt/v1"
LEGACY_PENDING_FINAL = "PENDING_REQUIRED_GATES_READBACK_AND_DAIL"
LEGACY_PENDING_DAIL = "REQUIRED_BEFORE_INSTITUTIONAL_CERTIFICATION"


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


def _legacy_projection_paths(number: int) -> tuple[Path, Path]:
    return (
        ROOT / f"penta/evidence/pr-self-cert/pr-{number}.json",
        ROOT / f"penta/continuity/receipts/pr-{number}-self-certification.json",
    )


def validate_legacy_readiness_payload(packet: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed semantic downgrade for the trusted-base legacy packet.

    Cryptographic/hash/diff validation is performed by the exact trusted-base
    generator/validator before this function is called. This function only
    establishes that the legacy packet is safe to interpret as zero-authority
    same-lane readiness evidence during the bootstrap transition.
    """
    if packet.get("schema") != LEGACY_EVIDENCE_SCHEMA:
        raise ValueError("legacy readiness evidence schema mismatch")
    if receipt.get("schema") != LEGACY_RECEIPT_SCHEMA:
        raise ValueError("legacy readiness receipt schema mismatch")
    if packet.get("canonical_semantics") not in (None, ""):
        raise ValueError("noncanonical legacy readiness packet cannot use compatibility downgrade")
    if receipt.get("canonical_semantics") not in (None, ""):
        raise ValueError("noncanonical legacy readiness receipt cannot use compatibility downgrade")
    if packet.get("self_certification_state") != "SELF_CERTIFIED":
        raise ValueError("legacy readiness packet state mismatch")
    if packet.get("final_institutional_certification_state") != LEGACY_PENDING_FINAL:
        raise ValueError("legacy readiness packet does not remain pending final institutional certification")
    if packet.get("dail_binding_state") != LEGACY_PENDING_DAIL:
        raise ValueError("legacy readiness packet does not remain pending DAIL binding")
    if packet.get("provider_results_manufactured") is not False:
        raise ValueError("legacy readiness packet attempted to manufacture provider truth")
    if packet.get("required_gate_bypass") is not False:
        raise ValueError("legacy readiness packet attempted to bypass a required gate")
    if packet.get("originator_identity") != packet.get("self_certifier_identity"):
        raise ValueError("legacy readiness packet is not same-lane originator evidence")
    for field in ("independent_certification", "authority_created", "merge_authority", "release_authority"):
        if packet.get(field) not in (None, False):
            raise ValueError(f"legacy readiness packet attempted to claim {field}")

    legacy_self = receipt.get("self_certification")
    if not isinstance(legacy_self, dict):
        raise ValueError("legacy readiness receipt self-certification envelope missing")
    if legacy_self.get("state") != "SELF_CERTIFIED":
        raise ValueError("legacy readiness receipt state mismatch")
    if legacy_self.get("provider_results_manufactured") is not False:
        raise ValueError("legacy readiness receipt attempted to manufacture provider truth")
    if legacy_self.get("final_gate_bypassed") is not False:
        raise ValueError("legacy readiness receipt attempted to bypass final gate")
    if legacy_self.get("originator") not in (None, packet.get("originator_identity")):
        raise ValueError("legacy readiness receipt originator mismatch")

    return {
        "state": "PASS",
        "canonical_semantics": "originator_readiness_evidence",
        "compatibility_input": "legacy_SELF_CERTIFIED_same_lane_packet",
        "actor_class": "originator_same_lane",
        "originator": packet.get("originator_identity"),
        "independent_certification": False,
        "authority_created": False,
        "merge_authority": False,
        "release_authority": False,
        "provider_results_manufactured": False,
        "required_gate_bypass": False,
        "requires_pentacertifier": True,
        "final_institutional_certification": "NOT_GRANTED_REQUIRES_INDEPENDENT_PENTACERTIFIER_AND_DAIL",
    }


def _validate_with_trusted_base_legacy_generator(
    *,
    git_base: str,
    git_head: str,
    number: int,
    repository: str,
) -> dict[str, Any]:
    show = subprocess.run(
        ["git", "show", f"{git_base}:scripts/penta_pr_gate_awareness.py"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if show.returncode != 0 or not show.stdout.startswith("#!/usr/bin/env python3"):
        raise SystemExit("ERROR: exact trusted-base legacy gate-awareness validator unavailable")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".py", delete=False) as fh:
        fh.write(show.stdout)
        legacy_script = Path(fh.name)
    try:
        command = [
            sys.executable,
            str(legacy_script),
            "validate",
            "--repo",
            str(ROOT),
            "--repository",
            repository,
            "--base",
            git_base,
            "--head",
            git_head,
            "--pr-number",
            str(number),
        ]
        proc = subprocess.run(command, cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        legacy_script.unlink(missing_ok=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise SystemExit(f"ERROR: trusted-base legacy readiness validation failed: {detail[:1500]}")
    try:
        legacy_result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("ERROR: trusted-base legacy readiness validator emitted invalid JSON") from exc
    if legacy_result.get("state") != "PASS":
        raise SystemExit("ERROR: trusted-base legacy readiness validator did not return PASS")

    evidence_path, receipt_path = _legacy_projection_paths(number)
    try:
        packet = json.loads(evidence_path.read_text(encoding="utf-8"))
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        normalized = validate_legacy_readiness_payload(packet, receipt)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"ERROR: unsafe legacy readiness compatibility packet: {exc}") from exc
    normalized["trusted_base_validator"] = git_base
    normalized["legacy_validation_state"] = legacy_result.get("state")
    normalized["legacy_subject_head_sha"] = legacy_result.get("subject_head_sha")
    return normalized


def validate_originator_readiness(git_base: str, git_head: str) -> dict[str, Any]:
    """Require current same-lane readiness evidence on GitHub PR executions."""
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return {"state": "NOT_APPLICABLE", "reason": "non_pull_request_execution"}
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("ERROR: GITHUB_EVENT_PATH missing for pull_request readiness gate")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        number = int(event["pull_request"]["number"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("ERROR: unable to resolve pull request number for readiness gate") from exc

    repository = os.environ.get("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS")
    command = [
        sys.executable,
        str(ROOT / "scripts" / "penta_pr_gate_awareness.py"),
        "validate",
        "--repo",
        str(ROOT),
        "--repository",
        repository,
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
        if LEGACY_SEMANTIC_ERROR in detail:
            return _validate_with_trusted_base_legacy_generator(
                git_base=git_base,
                git_head=git_head,
                number=number,
                repository=repository,
            )
        raise SystemExit(f"ERROR: Penta originator readiness HOLD: {detail[:1500]}")
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("ERROR: readiness validator emitted invalid JSON") from exc
    if result.get("state") != "PASS":
        raise SystemExit("ERROR: originator readiness did not return PASS")
    if result.get("independent_certification") is not False:
        raise SystemExit("ERROR: originator readiness attempted to claim independent certification")
    if result.get("merge_authority") is not False or result.get("release_authority") is not False:
        raise SystemExit("ERROR: originator readiness attempted to claim merge/release authority")
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
        "originator_readiness_gate": True,
        "legacy_self_certification_bootstrap_is_zero_authority": True,
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

    originator_readiness = validate_originator_readiness(args.git_base, args.git_head)
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
        "originator_readiness": originator_readiness,
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
