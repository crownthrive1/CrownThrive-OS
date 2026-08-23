#!/usr/bin/env python3
"""Operationally bind the current PR Git diff to CHLOM/CrownThrive governance logic.

This is a provider-side CI preflight, not a sovereign vote or merge authorization.
It derives the exact changed-file set from Git, deterministically classifies each
file, executes the real governed ``decide()`` path with a permanent CI-only hard
block, and proves negative vectors for omitted files and missing specialists.

The sovereign decision still comes from exact-head A/B/C/D/S evidence under
CT-ADR-GOV-011. This preflight only proves that the provider-required workflow
cannot pass by printing a Git diff while skipping the classification/specialist
code path.
"""

from __future__ import annotations

import argparse
import json
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

# Conservative fallback used only when a changed path has no explicit manifest
# path rule. Unknown code/config surfaces therefore expand scrutiny rather than
# reducing it. Documentation gets the neutral documentation domain.
CONSERVATIVE_FALLBACK_DOMAINS = {
    "security",
    "legal",
    "deployment",
    "blockchain",
    "llm",
    "rights",
    "finance",
    "accessibility",
    "localization",
}
DOCUMENTATION_PREFIXES = (
    "changelog/",
    "docs/",
    "technology/",
    "standards/",
    "automation/",
)
DOCUMENTATION_SUFFIXES = (".md", ".mdx")


def deterministic_domains(path: str, policy: dict[str, Any]) -> set[str]:
    """Return a fail-closed deterministic domain set for one trusted path."""
    contract = policy.get("changed_domain_contract", {})
    rules = contract.get("path_domain_rules", []) if isinstance(contract, dict) else []
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

    # Governance/code/config paths without an explicit minimum-domain rule are
    # deliberately over-classified. This cannot reduce the specialist set.
    if path.startswith(("scripts/", "developers/manifests/", ".github/")):
        return {"security", "agent", "deployment"}

    return set(CONSERVATIVE_FALLBACK_DOMAINS)


def classifications_for(
    trusted_files: set[str], policy: dict[str, Any]
) -> tuple[list[dict[str, Any]], set[str]]:
    classifications: list[dict[str, Any]] = []
    domains: set[str] = set()
    for path in sorted(trusted_files):
        item_domains = deterministic_domains(path, policy)
        if not item_domains:
            raise SystemExit(f"ERROR: deterministic classification empty for {path}")
        domains.update(item_domains)
        classifications.append(
            {
                "path": path,
                "domains": sorted(item_domains),
                "provenance": "deterministic_path_rule",
            }
        )
    return classifications, domains


def neutral_domains_for(policy: dict[str, Any]) -> set[str]:
    """Return only manifest-declared neutral domains.

    Neutrality is policy-owned, not inferred by the preflight. An empty
    specialist set is valid only when every derived changed domain is explicitly
    present in this governed neutral-domain registry.
    """
    contract = policy.get("changed_domain_contract", {})
    if not isinstance(contract, dict):
        return set()
    return {
        normalize_domain(value)
        for value in contract.get("neutral_domains", [])
        if normalize_domain(value)
    }


def fixture_scores() -> dict[str, int]:
    return {
        "evidence_quality": 100,
        "validation_strength": 100,
        "security_posture": 100,
        "reversibility": 100,
        "authority_fit": 100,
    }


def fixture_votes() -> list[dict[str, str]]:
    # These are CI fixtures only. The permanent hard block below prevents this
    # packet from ever being interpreted as sovereign merge authorization.
    return [
        {"agent_id": "ct.relay.agent-a", "vote": "approve"},
        {"agent_id": "ct.relay.agent-b", "vote": "approve"},
        {"agent_id": "ct.relay.agent-c", "vote": "approve"},
        {"agent_id": "ct.relay.agent-d", "vote": "approve"},
    ]


def build_packet(
    trusted_files: set[str],
    classifications: list[dict[str, Any]],
    domains: set[str],
    specialists: set[str],
) -> dict[str, Any]:
    return {
        "risk_class": "D2",
        "scores": fixture_scores(),
        "votes": fixture_votes(),
        "changed_files": sorted(trusted_files),
        "domain_classifications": classifications,
        "changed_domains": sorted(domains),
        "specialist_endorsements": sorted(specialists),
        "hard_blocks": ["ci_operational_preflight_non_sovereign_authority"],
    }


def assert_positive_preflight(result: dict[str, Any]) -> None:
    if result.get("trusted_changed_files_bound") is not True:
        raise SystemExit("ERROR: current-PR decision path did not bind trusted changed files")
    if result.get("domain_classification_errors"):
        raise SystemExit(
            "ERROR: current-PR domain classification failed: "
            + json.dumps(result["domain_classification_errors"], sort_keys=True)
        )
    if result.get("specialist_endorsement_errors"):
        raise SystemExit(
            "ERROR: current-PR specialist normalization failed: "
            + json.dumps(result["specialist_endorsement_errors"], sort_keys=True)
        )
    if result.get("missing_specialists"):
        raise SystemExit(
            "ERROR: current-PR deterministic specialist set incomplete: "
            + json.dumps(result["missing_specialists"], sort_keys=True)
        )
    if result.get("agent_auto_merge_authorized") is not False:
        raise SystemExit("ERROR: CI preflight must never create sovereign merge authority")
    if "ci_operational_preflight_non_sovereign_authority" not in result.get("hard_blocks", []):
        raise SystemExit("ERROR: permanent non-sovereign CI preflight hard block missing")


def assert_missing_specialists_fail_closed(
    base_packet: dict[str, Any],
    trusted_files: set[str],
    policy: dict[str, Any],
    required_specialists: set[str],
) -> list[str]:
    verified: list[str] = []
    for specialist in sorted(required_specialists):
        packet = json.loads(json.dumps(base_packet))
        packet["specialist_endorsements"] = sorted(required_specialists - {specialist})
        result = decide(packet, policy, trusted_files)
        if specialist not in result.get("missing_specialists", []):
            raise SystemExit(
                f"ERROR: missing specialist {specialist} did not fail closed on current PR"
            )
        if result.get("agent_auto_merge_authorized") is not False:
            raise SystemExit(
                f"ERROR: missing specialist {specialist} unexpectedly authorized merge"
            )
        verified.append(specialist)
    return verified


def assert_omitted_file_fails_closed(
    base_packet: dict[str, Any], trusted_files: set[str], policy: dict[str, Any]
) -> str:
    if not trusted_files:
        raise SystemExit("ERROR: pull request trusted changed-file set is empty")

    def sensitivity(path: str) -> tuple[int, str]:
        if path.startswith(".github/workflows/"):
            return (0, path)
        if path.startswith("scripts/"):
            return (1, path)
        if path.startswith("developers/manifests/"):
            return (2, path)
        return (3, path)

    omitted = sorted(trusted_files, key=sensitivity)[0]
    packet = json.loads(json.dumps(base_packet))
    packet["changed_files"] = [path for path in packet["changed_files"] if path != omitted]
    packet["domain_classifications"] = [
        item for item in packet["domain_classifications"] if item.get("path") != omitted
    ]
    reduced_domains: set[str] = set()
    for item in packet["domain_classifications"]:
        reduced_domains.update(normalize_domain(value) for value in item.get("domains", []))
    packet["changed_domains"] = sorted(reduced_domains)
    packet["specialist_endorsements"] = sorted(required_specialists_for(reduced_domains, policy))

    result = decide(packet, policy, trusted_files)
    errors = result.get("domain_classification_errors", [])
    if not any(error.startswith("changed_files_trusted_diff_mismatch:") for error in errors):
        raise SystemExit(
            f"ERROR: omitting trusted file {omitted} did not produce trusted-diff mismatch"
        )
    if result.get("agent_auto_merge_authorized") is not False:
        raise SystemExit(f"ERROR: omitted trusted file {omitted} unexpectedly authorized merge")
    return omitted


def assert_unclassified_file_fails_closed(
    base_packet: dict[str, Any], trusted_files: set[str], policy: dict[str, Any]
) -> str:
    path = sorted(trusted_files)[0]
    packet = json.loads(json.dumps(base_packet))
    packet["domain_classifications"] = [
        item for item in packet["domain_classifications"] if item.get("path") != path
    ]
    result = decide(packet, policy, trusted_files)
    if f"unclassified_changed_file:{path}" not in result.get("domain_classification_errors", []):
        raise SystemExit(f"ERROR: unclassified trusted file {path} did not fail closed")
    if result.get("agent_auto_merge_authorized") is not False:
        raise SystemExit(f"ERROR: unclassified trusted file {path} unexpectedly authorized merge")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-base", required=True)
    parser.add_argument("--git-head", required=True)
    args = parser.parse_args()

    policy = load_json(MANIFEST)
    trusted_files = trusted_changed_files_from_git(args.git_base, args.git_head)
    classifications, domains = classifications_for(trusted_files, policy)
    required_specialists = required_specialists_for(domains, policy)
    neutral_domains = neutral_domains_for(policy)
    neutral_only = bool(domains) and domains.issubset(neutral_domains)

    # A D2 packet must resolve specialist coverage unless its entire derived
    # domain set is explicitly neutral in the governed manifest. This preserves
    # fail-closed behavior for any unknown/non-neutral domain while allowing
    # documentation-only changes to remain genuinely neutral.
    if not required_specialists and not neutral_only:
        raise SystemExit(
            "ERROR: D2 current-PR preflight resolved no specialist requirements "
            "for non-neutral domains"
        )

    packet = build_packet(trusted_files, classifications, domains, required_specialists)
    result = decide(packet, policy, trusted_files)
    assert_positive_preflight(result)
    missing_specialist_vectors = assert_missing_specialists_fail_closed(
        packet, trusted_files, policy, required_specialists
    )
    omitted_file = assert_omitted_file_fails_closed(packet, trusted_files, policy)
    unclassified_file = assert_unclassified_file_fails_closed(packet, trusted_files, policy)

    print(
        json.dumps(
            {
                "mode": "ci_operational_preflight_non_sovereign_authority",
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
                "negative_missing_specialist_vectors": missing_specialist_vectors,
                "negative_omitted_file_proved": bool(omitted_file),
                "negative_unclassified_file_proved": bool(unclassified_file),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
