#!/usr/bin/env python3
"""Governed current-PR preflight v2.

Classifies the exact trusted Git diff, requires non-certifying originator
readiness, and keeps deletes, renames, and protected modifications fail-closed
unless committed continuity receipts cover the exact before/after blobs.
Originator readiness never substitutes for provider gates, DAIL binding,
independent security/governance review, certification, or human-reserved
authority.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping

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
from penta_pr_gate_awareness import evidence_path, receipt_path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_CONTRACT = ROOT / "developers/manifests/governed-evidence-data-classification.v1.json"
SERIALIZED_POLICY = ROOT / "penta/registry/serialized-suite.json"
CONTINUITY_ROOT = ROOT / "penta/continuity/receipts"
PREFLIGHT_VERSION = "2.3.0"


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


def classifications_for(trusted_files: set[str], policy: dict[str, Any],
                        contract: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
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


def _git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise SystemExit(f"ERROR: git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _ensure_commit(ref: str) -> None:
    _git(ROOT, "cat-file", "-e", f"{ref}^{{commit}}")


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=ROOT,
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def _blob_sha(ref: str, path: str) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", f"{ref}:{path}"], cwd=ROOT, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _contains_self_certification(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "self_cert" in str(key).lower() or _contains_self_certification(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_self_certification(item) for item in value)
    return isinstance(value, str) and "SELF_CERT" in value.upper()


def _legacy_self_certification_paths(trusted_files: set[str]) -> list[str]:
    prohibited: list[str] = []
    for path in trusted_files:
        if path.startswith("penta/evidence/pr-self-cert/"):
            prohibited.append(path)
        elif path.startswith("penta/continuity/receipts/pr-") and path.endswith("-self-certification.json"):
            prohibited.append(path)
    return sorted(prohibited)


def _controlled_changes(git_base: str, git_head: str) -> list[dict[str, Any]]:
    serialized = load_json(SERIALIZED_POLICY)
    protected = [str(value) for value in serialized.get("protected_patterns", [])]
    proc = subprocess.run(
        ["git", "diff", "--name-status", "--find-renames", f"{git_base}...{git_head}"],
        cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"ERROR: trusted Git diff unavailable: {proc.stderr.strip()}")
    controlled: list[dict[str, Any]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0][0]
        if code == "R":
            old_path, path = parts[1], parts[2]
            controlled.append({
                "operation": "rename", "old_path": old_path, "path": path,
                "previous_blob_sha": _blob_sha(git_base, old_path),
                "new_blob_sha": _blob_sha(git_head, path),
            })
            continue
        path = parts[1]
        if code == "D":
            controlled.append({
                "operation": "delete", "path": path,
                "previous_blob_sha": _blob_sha(git_base, path), "new_blob_sha": None,
            })
        elif code == "M" and any(fnmatch.fnmatch(path, pattern) for pattern in protected):
            if not path.startswith(".github/workflows/"):
                controlled.append({
                    "operation": "modify", "path": path,
                    "previous_blob_sha": _blob_sha(git_base, path),
                    "new_blob_sha": _blob_sha(git_head, path),
                })
    return controlled


def _load_continuity_receipts(git_head: str) -> list[tuple[str, dict[str, Any]]]:
    receipts: list[tuple[str, dict[str, Any]]] = []
    if not CONTINUITY_ROOT.exists():
        return receipts
    for path in sorted(CONTINUITY_ROOT.glob("*.json")):
        relative = path.relative_to(ROOT).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("schema") != "crownthrive.penta.serialized.git-receipt/v1":
            continue
        if _contains_self_certification(payload):
            continue
        if _blob_sha(git_head, relative) is None:
            continue
        receipts.append((relative, payload))
    return receipts


def _receipt_change_matches(expected: Mapping[str, Any], item: Mapping[str, Any],
                            receipt: Mapping[str, Any], git_head: str) -> bool:
    if item.get("operation") != expected.get("operation") or item.get("path") != expected.get("path"):
        return False
    if expected.get("operation") == "rename" and item.get("old_path") != expected.get("old_path"):
        return False
    if expected.get("previous_blob_sha") and item.get("previous_blob_sha") != expected.get("previous_blob_sha"):
        return False
    if expected.get("new_blob_sha") and item.get("new_blob_sha") != expected.get("new_blob_sha"):
        return False
    if expected.get("operation") == "delete":
        continuity = receipt.get("continuity", {})
        if item.get("tombstone") is not True or continuity.get("silent_delete") is not False:
            return False
        if expected["path"] not in continuity.get("tombstones", []):
            return False
    rollback_ref = str(item.get("rollback_ref") or "")
    if len(rollback_ref) != 40:
        return False
    try:
        _ensure_commit(rollback_ref)
    except SystemExit:
        return False
    return _is_ancestor(rollback_ref, git_head)


def validate_committed_continuity(git_base: str, git_head: str) -> dict[str, Any]:
    controlled = _controlled_changes(git_base, git_head)
    if not controlled:
        return {"state": "NOT_REQUIRED", "controlled_changes": 0, "receipts": [], "authority_created": False}
    receipts = _load_continuity_receipts(git_head)
    coverage: list[dict[str, Any]] = []
    missing: list[str] = []
    for expected in controlled:
        matched_path: str | None = None
        for relative, receipt in receipts:
            if any(
                isinstance(item, dict) and _receipt_change_matches(expected, item, receipt, git_head)
                for item in receipt.get("changes", [])
            ):
                matched_path = relative
                break
        if not matched_path:
            missing.append(f"{expected['operation']}:{expected.get('old_path') or expected['path']}")
        else:
            coverage.append({"operation": expected["operation"], "path": expected["path"], "receipt": matched_path})
    if missing:
        raise SystemExit(
            "ERROR: committed non-certifying continuity receipt required for controlled changes: "
            + ", ".join(sorted(missing))
        )
    return {
        "state": "PASS", "controlled_changes": len(controlled), "covered_changes": coverage,
        "receipts": sorted({item["receipt"] for item in coverage}), "authority_created": False,
    }


def validate_originator_readiness(git_base: str, git_head: str) -> dict[str, Any]:
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return {"state": "NOT_APPLICABLE", "reason": "non_pull_request_execution", "authority_created": False}
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise SystemExit("ERROR: GITHUB_EVENT_PATH missing for pull_request originator-readiness gate")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        number = int(event["pull_request"]["number"])
        originator = str(event["pull_request"].get("user", {}).get("login") or os.environ.get("GITHUB_ACTOR") or "unknown-originator")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("ERROR: unable to resolve pull request identity for originator-readiness gate") from exc

    legacy_paths = _legacy_self_certification_paths(trusted_changed_files_from_git(git_base, git_head))
    if legacy_paths:
        raise SystemExit(
            "ERROR: originator certification artifacts are prohibited on the current exact subject: "
            + ", ".join(legacy_paths)
        )
    continuity = validate_committed_continuity(git_base, git_head)
    evidence_file = ROOT / evidence_path(number)
    receipt_file = ROOT / receipt_path(number)
    if evidence_file.exists() != receipt_file.exists():
        raise SystemExit("ERROR: partial originator-readiness projection found; evidence and receipt must be paired")

    ephemeral = False
    if not evidence_file.exists():
        prepared = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "penta_pr_gate_awareness.py"), "prepare",
            "--repo", str(ROOT), "--repository", os.environ.get("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS"),
            "--base", git_base, "--head", git_head, "--pr-number", str(number), "--originator", originator,
        ], cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if prepared.returncode != 0:
            detail = (prepared.stderr or prepared.stdout).strip()
            raise SystemExit(f"ERROR: ephemeral originator-readiness projection failed: {detail[:1500]}")
        if not evidence_file.exists() or not receipt_file.exists():
            raise SystemExit("ERROR: originator-readiness projection emitted no paired evidence")
        ephemeral = True

    try:
        proc = subprocess.run([
            sys.executable, str(ROOT / "scripts" / "penta_pr_gate_awareness.py"), "validate",
            "--repo", str(ROOT), "--repository", os.environ.get("GITHUB_REPOSITORY", "crownthrive1/CrownThrive-OS"),
            "--base", git_base, "--head", git_head, "--pr-number", str(number),
        ], cwd=ROOT, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise SystemExit(f"ERROR: Penta originator-readiness HOLD: {detail[:1500]}")
        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise SystemExit("ERROR: originator-readiness validator emitted invalid JSON") from exc
        if result.get("state") != "PASS" or result.get("authority_created") is not False:
            raise SystemExit("ERROR: originator-readiness did not return non-authoritative PASS")
        if result.get("independent_certification_required") is not True:
            raise SystemExit("ERROR: originator-readiness removed independent certification")
        result["ephemeral_projection"] = ephemeral
        result["candidate_branch_mutated"] = False
        result["committed_continuity"] = continuity
        return result
    finally:
        if ephemeral:
            evidence_file.unlink(missing_ok=True)
            receipt_file.unlink(missing_ok=True)


def self_test(policy: dict[str, Any], contract: dict[str, Any]) -> None:
    expected_neutral = {"institutional_general"}
    for path in contract["registered_neutral_paths"]:
        got = deterministic_domains(path, policy, contract)
        if got != expected_neutral:
            raise SystemExit(f"ERROR: registered evidence path not neutral: {path} -> {sorted(got)}")
    material_vectors = {
        "data/payments-ledger.json": {"finance"}, "data/royalty-rates.json": {"finance"},
        "data/token-registry.json": {"blockchain"}, "data/wallet-state.json": {"blockchain"},
        "data/license-grants.json": {"rights"}, "data/rights-chain.json": {"rights"},
        "data/customer-records.json": {"privacy"}, "data/privacy-export.json": {"privacy"},
        "data/localization-map.json": {"localization"}, "data/country-routing.json": {"localization"},
    }
    for path, minimum in material_vectors.items():
        got = deterministic_domains(path, policy, contract)
        if not minimum.issubset(got):
            raise SystemExit(f"ERROR: material data path under-classified: {path} -> {sorted(got)}")
    if deterministic_domains("data/unregistered-evidence-looking.json", policy, contract) != set(CONSERVATIVE_FALLBACK_DOMAINS):
        raise SystemExit("ERROR: unknown data path did not retain conservative fallback")
    if deterministic_domains("data/help_center_article_manifest.v1.bundle.json.backup", policy, contract) != set(CONSERVATIVE_FALLBACK_DOMAINS):
        raise SystemExit("ERROR: path extension/name spoof incorrectly inherited neutrality")
    if not _contains_self_certification({"self_certification_state": "SELF_CERTIFIED"}):
        raise SystemExit("ERROR: originator-certification negative vector was not detected")
    if _contains_self_certification({
        "readiness_state": "READY_FOR_INDEPENDENT_REVIEW", "authority_created": False,
        "independent_certification_required": True,
    }):
        raise SystemExit("ERROR: non-certifying readiness was incorrectly rejected")
    print(json.dumps({
        "preflight_version": PREFLIGHT_VERSION, "contract": contract["contract_id"],
        "registered_neutral_paths": len(contract["registered_neutral_paths"]),
        "material_negative_vectors": len(material_vectors), "unknown_data_fail_closed": True,
        "extension_only_neutrality": False, "originator_readiness_gate": True,
        "originator_certification_prohibited": True, "source_pure_ephemeral_originator_projection": True,
        "controlled_change_requires_committed_non_certifying_continuity": True,
        "independent_certification_required": True, "self_test": "PASS",
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

    readiness = validate_originator_readiness(args.git_base, args.git_head)
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
        "preflight_version": PREFLIGHT_VERSION, "evidence_contract": contract["contract_id"],
        "originator_readiness": readiness, "originator_is_not_certifier": True,
        "sovereign_authority": False, "trusted_changed_files_count": len(trusted_files),
        "trusted_changed_files_digest": changed_file_digest(trusted_files),
        "trusted_changed_files_redacted": True, "derived_changed_domains": sorted(domains),
        "neutral_only": neutral_only, "required_specialists": sorted(required_specialists),
        "decision_engine_executed": True, "positive_preflight_classification_clean": True,
        "positive_preflight_specialists_complete": True, "positive_preflight_auto_merge_authorized": False,
        "negative_missing_specialist_vectors": missing_vectors,
        "negative_omitted_file_proved": bool(omitted),
        "negative_unclassified_file_proved": bool(unclassified),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
