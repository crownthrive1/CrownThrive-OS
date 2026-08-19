#!/usr/bin/env python3
"""Compute CrownThrive's agent-sovereign merge decision.

GitHub is required defense-in-depth, evidence, CI, scanning and transport. It is
not sovereign authority. The engine is fail-closed, retains CT-ADR-GOV-011's
4-of-5 + mandatory Agent D rule, derives specialist gates from the governed
registry, derives material changed domains from per-file classifications, and
requires material packet ``changed_files`` to exactly match a trusted Git diff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/agent-sovereign-governance.v1.json"
VALID_VOTES = {"approve", "deny", "block", "abstain"}
MATERIAL_RISK_CLASSES = {"D1", "D2", "D3"}
SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_domain(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_paths(values: Iterable[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def trusted_changed_files_from_git(base_sha: str, head_sha: str) -> set[str]:
    """Derive the authoritative changed-file set from exact Git commit SHAs.

    Rename detection is disabled so a rename is represented as deletion + add,
    preventing a sensitive deleted path from disappearing from classification.
    The function never accepts branch names, tags or caller-provided file lists.
    """
    if not SHA40.fullmatch(base_sha or "") or not SHA40.fullmatch(head_sha or ""):
        raise ValueError("git_base_and_head_must_be_exact_40_hex_commit_shas")
    completed = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", base_sha, head_sha, "--"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "git_diff_failed"
        raise ValueError(f"trusted_git_diff_failed:{detail}")
    paths = normalize_paths(completed.stdout.splitlines())
    if len(paths) != len(set(paths)):
        raise ValueError("trusted_git_diff_contains_duplicate_path")
    return set(paths)


def changed_file_digest(paths: Iterable[str]) -> str:
    payload = "\n".join(sorted(set(paths))).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def specialist_alias_map(policy: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    """Build governed endorsement alias -> canonical endorsement ID mapping."""
    aliases: dict[str, str] = {}
    errors: list[str] = []
    registry = policy.get("specialist_activation", {})
    if not isinstance(registry, dict):
        return aliases, ["specialist_registry_not_object"]

    for specialist_key, config in registry.items():
        if not isinstance(config, dict):
            errors.append(f"specialist_config_not_object:{normalize_domain(specialist_key)}")
            continue
        canonical = normalize_domain(config.get("endorsement_id", specialist_key))
        if not canonical:
            errors.append(f"specialist_endorsement_id_missing:{normalize_domain(specialist_key)}")
            continue
        candidates = [canonical, *config.get("endorsement_aliases", [])]
        for candidate in candidates:
            alias = normalize_domain(candidate)
            if not alias:
                errors.append(f"specialist_alias_empty:{canonical}")
                continue
            existing = aliases.get(alias)
            if existing and existing != canonical:
                errors.append(f"specialist_alias_collision:{alias}:{existing}:{canonical}")
                continue
            aliases[alias] = canonical
    return aliases, errors


def normalize_endorsements(
    values: Any, policy: dict[str, Any]
) -> tuple[set[str], list[str]]:
    """Canonicalize specialist endorsements and reject unknown IDs fail-closed."""
    alias_map, alias_errors = specialist_alias_map(policy)
    errors = list(alias_errors)
    if values is None:
        values = []
    if not isinstance(values, list):
        return set(), [*errors, "specialist_endorsements_not_list"]

    normalized: set[str] = set()
    for value in values:
        token = normalize_domain(value)
        canonical = alias_map.get(token)
        if not canonical:
            errors.append(f"unknown_specialist_endorsement:{token or '<empty>'}")
            continue
        normalized.add(canonical)
    return normalized, errors


def required_specialists_for(changed_domains: set[str], policy: dict[str, Any]) -> set[str]:
    """Resolve cumulative specialist endorsements from the machine registry."""
    normalized_domains = {
        normalize_domain(value) for value in changed_domains if normalize_domain(value)
    }
    required: set[str] = set()
    registry = policy.get("specialist_activation", {})
    if not isinstance(registry, dict):
        return required
    for specialist_key, config in registry.items():
        if not isinstance(config, dict):
            continue
        endorsement_id = normalize_domain(config.get("endorsement_id", specialist_key))
        patterns = {
            normalize_domain(value)
            for value in config.get("required_patterns", [])
            if normalize_domain(value)
        }
        patterns.add(normalize_domain(specialist_key))
        patterns.add(endorsement_id)
        if normalized_domains & patterns:
            required.add(endorsement_id)
    return required


def allowed_domain_tokens(policy: dict[str, Any]) -> set[str]:
    """Build the controlled changed-domain vocabulary from governed policy."""
    allowed: set[str] = set()
    contract = policy.get("changed_domain_contract", {})
    if isinstance(contract, dict):
        allowed.update(
            normalize_domain(value)
            for value in contract.get("neutral_domains", [])
            if normalize_domain(value)
        )
        for rule in contract.get("path_domain_rules", []):
            if isinstance(rule, dict):
                allowed.update(
                    normalize_domain(value)
                    for value in rule.get("required_domains", [])
                    if normalize_domain(value)
                )

    registry = policy.get("specialist_activation", {})
    if isinstance(registry, dict):
        for key, config in registry.items():
            if not isinstance(config, dict):
                continue
            allowed.add(normalize_domain(key))
            allowed.add(normalize_domain(config.get("endorsement_id", key)))
            allowed.update(
                normalize_domain(value)
                for value in config.get("required_patterns", [])
                if normalize_domain(value)
            )
    allowed.discard("")
    return allowed


def validate_changed_file_binding(
    declared_files: list[str],
    trusted_changed_files: set[str] | None,
    required: bool,
) -> list[str]:
    """Require exact set equality between packet files and trusted Git diff."""
    if not required:
        return []
    if trusted_changed_files is None:
        return ["trusted_changed_files_missing"]

    declared = set(declared_files)
    trusted = set(trusted_changed_files)
    if declared == trusted:
        return []

    omitted = sorted(trusted - declared)
    extra = sorted(declared - trusted)
    detail: list[str] = []
    if omitted:
        detail.append(f"omitted={','.join(omitted)}")
    if extra:
        detail.append(f"extra={','.join(extra)}")
    return ["changed_files_trusted_diff_mismatch:" + ":".join(detail)]


def classify_changed_domains(
    packet: dict[str, Any],
    policy: dict[str, Any],
    risk_class: str,
    trusted_changed_files: set[str] | None = None,
) -> tuple[set[str], list[str]]:
    """Derive changed domains from classified files and validate provenance.

    D1/D2/D3 packets fail closed if material files are omitted, unclassified,
    or do not exactly match the trusted Git diff. Caller ``changed_domains`` is
    only an assertion and never the authority source for specialist activation.
    """
    contract = policy.get("changed_domain_contract", {})
    if not isinstance(contract, dict):
        return set(), ["changed_domain_contract_missing"]

    required_risks = {
        str(value).upper() for value in contract.get("required_for_risk_classes", [])
    }
    required = risk_class in required_risks or risk_class == "D3"
    changed_files_raw = packet.get("changed_files", [])
    classifications_raw = packet.get("domain_classifications", [])

    if not required and not changed_files_raw and not classifications_raw:
        asserted = packet.get("changed_domains")
        if asserted:
            return set(), ["changed_domains_asserted_without_file_classification"]
        return set(), []

    errors: list[str] = []
    if not isinstance(changed_files_raw, list):
        return set(), ["changed_files_not_list"]
    changed_files = normalize_paths(changed_files_raw)
    if len(changed_files) != len(changed_files_raw):
        errors.append("changed_files_contains_empty_path")
    if len(changed_files) != len(set(changed_files)):
        errors.append("changed_files_contains_duplicate_path")
    if required and not changed_files:
        errors.append("material_changed_files_missing")

    errors.extend(validate_changed_file_binding(changed_files, trusted_changed_files, required))

    if not isinstance(classifications_raw, list):
        return set(), [*errors, "domain_classifications_not_list"]

    allowed = allowed_domain_tokens(policy)
    allowed_provenance = {
        normalize_domain(value)
        for value in contract.get("allowed_provenance", [])
        if normalize_domain(value)
    }
    reviewer_requires_evidence = bool(
        contract.get("reviewer_classification_requires_evidence_ref", True)
    )

    by_path: dict[str, dict[str, Any]] = {}
    derived: set[str] = set()
    for raw in classifications_raw:
        if not isinstance(raw, dict):
            errors.append("domain_classification_not_object")
            continue
        path = str(raw.get("path", "")).strip()
        if not path:
            errors.append("domain_classification_missing_path")
            continue
        if path in by_path:
            errors.append(f"duplicate_domain_classification:{path}")
            continue
        by_path[path] = raw
        if path not in changed_files:
            errors.append(f"domain_classification_unknown_path:{path}")

        domains_raw = raw.get("domains", [])
        if not isinstance(domains_raw, list) or not domains_raw:
            errors.append(f"domain_classification_missing_domains:{path}")
            domains: set[str] = set()
        else:
            domains = {
                normalize_domain(value) for value in domains_raw if normalize_domain(value)
            }
            if len(domains) != len(domains_raw):
                errors.append(f"domain_classification_empty_domain:{path}")
            unknown = sorted(domains - allowed)
            if unknown:
                errors.append(
                    f"domain_classification_unknown_domains:{path}:{','.join(unknown)}"
                )
        derived.update(domains)

        provenance = normalize_domain(raw.get("provenance", ""))
        if provenance not in allowed_provenance:
            errors.append(f"domain_classification_invalid_provenance:{path}:{provenance}")
        if (
            provenance == "reviewer_classification"
            and reviewer_requires_evidence
            and not str(raw.get("evidence_ref", "")).strip()
        ):
            errors.append(f"domain_classification_evidence_ref_missing:{path}")

        for rule in contract.get("path_domain_rules", []):
            if not isinstance(rule, dict):
                continue
            exact = str(rule.get("path", "")).strip()
            prefix = str(rule.get("prefix", "")).strip()
            matches = bool((exact and path == exact) or (prefix and path.startswith(prefix)))
            if not matches:
                continue
            required_domains = {
                normalize_domain(value)
                for value in rule.get("required_domains", [])
                if normalize_domain(value)
            }
            missing = sorted(required_domains - domains)
            if missing:
                errors.append(
                    f"domain_classification_missing_required:{path}:{','.join(missing)}"
                )

    missing_paths = sorted(set(changed_files) - set(by_path))
    for path in missing_paths:
        errors.append(f"unclassified_changed_file:{path}")

    if required and not derived:
        errors.append("material_changed_domains_empty")

    if "changed_domains" in packet:
        asserted_raw = packet.get("changed_domains", [])
        if not isinstance(asserted_raw, list):
            errors.append("changed_domains_assertion_not_list")
        else:
            asserted = {
                normalize_domain(value)
                for value in asserted_raw
                if normalize_domain(value)
            }
            if contract.get("asserted_changed_domains_must_match_derived", True):
                if asserted != derived:
                    errors.append(
                        "changed_domains_assertion_mismatch:"
                        f"asserted={','.join(sorted(asserted))}:"
                        f"derived={','.join(sorted(derived))}"
                    )

    return derived, errors


def decide(
    packet: dict[str, Any],
    policy: dict[str, Any],
    trusted_changed_files: set[str] | None = None,
) -> dict[str, Any]:
    pool = {
        item["agent_id"]: item
        for item in policy["voter_pool"]
        if item.get("vote_eligible") is True
    }
    q = policy["quorum"]
    required = math.ceil(len(pool) * float(q["approval_ratio"]))

    votes_by_agent: dict[str, str] = {}
    invalid_votes: list[str] = []
    for item in packet.get("votes", []):
        agent_id = str(item.get("agent_id", ""))
        vote = str(item.get("vote", "")).lower()
        if agent_id not in pool or vote not in VALID_VOTES:
            invalid_votes.append(agent_id or "<missing>")
            continue
        if agent_id in votes_by_agent:
            invalid_votes.append(f"duplicate:{agent_id}")
            continue
        votes_by_agent[agent_id] = vote

    approvals = sum(v == "approve" for v in votes_by_agent.values())
    denials = sorted(a for a, v in votes_by_agent.items() if v in {"deny", "block"})
    abstentions = sorted(a for a, v in votes_by_agent.items() if v == "abstain")
    missing = sorted(set(pool) - set(votes_by_agent))

    weights = policy["risk_rating"]["dimensions"]
    scores = packet.get("scores", {})
    score_errors: list[str] = []
    composite = 0.0
    for name, weight in weights.items():
        value = scores.get(name)
        if not isinstance(value, (int, float)) or not 0 <= float(value) <= 100:
            score_errors.append(name)
            continue
        composite += float(value) * float(weight)
    composite = round(composite, 2)

    risk_class = str(packet.get("risk_class", "")).upper()
    d3 = risk_class == "D3"
    hard_blocks = [str(x) for x in packet.get("hard_blocks", []) if str(x).strip()]

    changed_domains, classification_errors = classify_changed_domains(
        packet, policy, risk_class, trusted_changed_files
    )
    endorsements, endorsement_errors = normalize_endorsements(
        packet.get("specialist_endorsements", []), policy
    )
    required_specialists = required_specialists_for(changed_domains, policy)
    missing_endorsements = sorted(required_specialists - endorsements)

    gatekeeper_ok = votes_by_agent.get("ct.relay.agent-d") == "approve"
    score_ok = (
        not score_errors
        and composite >= float(policy["risk_rating"]["minimum_automatic_merge_score"])
    )
    quorum_ok = approvals >= required and not denials
    human_ok = (not d3) or packet.get("human_authorized") is True

    reasons: list[str] = []
    if invalid_votes:
        reasons.append(f"invalid_votes:{','.join(invalid_votes)}")
    if denials:
        reasons.append(f"deny_or_block:{','.join(denials)}")
    if approvals < required:
        reasons.append(f"quorum_not_met:{approvals}/{required}")
    if missing:
        reasons.append(f"missing_votes:{','.join(missing)}")
    if abstentions:
        reasons.append(f"abstentions:{','.join(abstentions)}")
    if not gatekeeper_ok:
        reasons.append("independent_gatekeeper_approval_missing")
    if score_errors:
        reasons.append(f"invalid_scores:{','.join(score_errors)}")
    if not score_ok and not score_errors:
        reasons.append(
            f"risk_score_below_threshold:{composite}/"
            f"{policy['risk_rating']['minimum_automatic_merge_score']}"
        )
    if classification_errors:
        reasons.append(f"invalid_domain_classification:{'|'.join(classification_errors)}")
    if endorsement_errors:
        reasons.append(f"invalid_specialist_endorsements:{'|'.join(endorsement_errors)}")
    if missing_endorsements:
        reasons.append(f"missing_specialists:{','.join(missing_endorsements)}")
    if hard_blocks:
        reasons.append(f"hard_blocks:{','.join(hard_blocks)}")
    if d3 and not human_ok:
        reasons.append("d3_human_authorization_required")
    if d3:
        reasons.append("d3_quorum_is_advisory_not_substitute_for_human_authority")

    auto_merge_authorized = bool(
        risk_class in {"D0", "D1", "D2"}
        and quorum_ok
        and gatekeeper_ok
        and score_ok
        and not hard_blocks
        and not missing_endorsements
        and not invalid_votes
        and not classification_errors
        and not endorsement_errors
    )

    decision = "approve_agent_merge" if auto_merge_authorized else "deny_or_escalate"
    if (
        d3
        and human_ok
        and quorum_ok
        and gatekeeper_ok
        and score_ok
        and not hard_blocks
        and not missing_endorsements
        and not invalid_votes
        and not classification_errors
        and not endorsement_errors
    ):
        decision = "human_authorized_execution_may_proceed_under_separate_d3_controls"

    return {
        "decision": decision,
        "agent_auto_merge_authorized": auto_merge_authorized,
        "risk_class": risk_class,
        "eligible_voters": len(pool),
        "quorum_ratio": q["approval_ratio"],
        "minimum_approvals": required,
        "approvals": approvals,
        "denials_or_blocks": denials,
        "abstentions": abstentions,
        "missing_votes": missing,
        "composite_risk_score": composite,
        "minimum_score": policy["risk_rating"]["minimum_automatic_merge_score"],
        "trusted_changed_files_bound": trusted_changed_files is not None,
        "trusted_changed_files_digest": (
            changed_file_digest(trusted_changed_files) if trusted_changed_files is not None else None
        ),
        "derived_changed_domains": sorted(changed_domains),
        "domain_classification_errors": classification_errors,
        "required_specialists": sorted(required_specialists),
        "normalized_specialist_endorsements": sorted(endorsements),
        "specialist_endorsement_errors": endorsement_errors,
        "missing_specialists": missing_endorsements,
        "hard_blocks": hard_blocks,
        "human_authorized": packet.get("human_authorized") is True,
        "reasons": reasons,
    }


def self_test(policy: dict[str, Any]) -> None:
    common_scores = {
        "evidence_quality": 100,
        "validation_strength": 100,
        "security_posture": 100,
        "reversibility": 100,
        "authority_fit": 100,
    }
    four_yes = [
        {"agent_id": "ct.relay.agent-a", "vote": "approve"},
        {"agent_id": "ct.relay.agent-b", "vote": "approve"},
        {"agent_id": "ct.relay.agent-c", "vote": "approve"},
        {"agent_id": "ct.relay.agent-d", "vote": "approve"},
    ]

    ok = decide({
        "risk_class": "D0", "scores": common_scores, "votes": four_yes,
        "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert ok["agent_auto_merge_authorized"] is True
    assert ok["minimum_approvals"] == 4

    three_yes = decide({
        "risk_class": "D0", "scores": common_scores, "votes": four_yes[:3],
        "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert three_yes["agent_auto_merge_authorized"] is False

    docs_files = {"changelog/example.md"}
    d1_docs = decide({
        "risk_class": "D1", "scores": common_scores, "votes": four_yes,
        "changed_files": ["changelog/example.md"],
        "domain_classifications": [{
            "path": "changelog/example.md", "domains": ["documentation"],
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.docs"
        }],
        "changed_domains": ["documentation"],
        "specialist_endorsements": [], "hard_blocks": []
    }, policy, docs_files)
    assert d1_docs["agent_auto_merge_authorized"] is True
    assert d1_docs["trusted_changed_files_bound"] is True

    d1_missing_trusted_diff = decide({
        "risk_class": "D1", "scores": common_scores, "votes": four_yes,
        "changed_files": ["changelog/example.md"],
        "domain_classifications": [{
            "path": "changelog/example.md", "domains": ["documentation"],
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.docs"
        }],
        "specialist_endorsements": [], "hard_blocks": []
    }, policy)
    assert d1_missing_trusted_diff["agent_auto_merge_authorized"] is False
    assert "trusted_changed_files_missing" in d1_missing_trusted_diff["domain_classification_errors"]

    d1_unclassified = decide({
        "risk_class": "D1", "scores": common_scores, "votes": four_yes,
        "changed_files": ["changelog/example.md"],
        "domain_classifications": [], "specialist_endorsements": [], "hard_blocks": []
    }, policy, docs_files)
    assert d1_unclassified["agent_auto_merge_authorized"] is False

    omitted_sensitive = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_files": ["changelog/example.md"],
        "domain_classifications": [{
            "path": "changelog/example.md", "domains": ["documentation"],
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.omission"
        }],
        "specialist_endorsements": [], "hard_blocks": []
    }, policy, {"changelog/example.md", "scripts/governed_merge_decision.py"})
    assert omitted_sensitive["agent_auto_merge_authorized"] is False
    assert any(
        error.startswith("changed_files_trusted_diff_mismatch:omitted=scripts/governed_merge_decision.py")
        for error in omitted_sensitive["domain_classification_errors"]
    )

    expected_ids = {
        "security", "legal_regulatory", "operations_sre", "blockchain_protocol",
        "ai_ml_llm_tevv", "ip_rights_licensing", "finance_tax_treasury",
        "accessibility_consumer_protection", "regional_global_localization",
    }
    registry_ids = {
        normalize_domain(config.get("endorsement_id", key))
        for key, config in policy.get("specialist_activation", {}).items()
    }
    assert registry_ids == expected_ids

    aliases, alias_errors = specialist_alias_map(policy)
    assert not alias_errors
    assert aliases["security_privacy"] == "security"

    single_domain_expectations = {
        "security": {"security"},
        "legal": {"legal_regulatory"},
        "deployment": {"operations_sre"},
        "llm": {"ai_ml_llm_tevv"},
        "copyright": {"ip_rights_licensing"},
        "tax": {"finance_tax_treasury"},
        "accessibility": {"accessibility_consumer_protection"},
        "localization": {"regional_global_localization"},
    }
    for domain, expected in single_domain_expectations.items():
        assert required_specialists_for({domain}, policy) == expected

    cumulative_expectations = {
        "rights": {"legal_regulatory", "ip_rights_licensing"},
        "blockchain": {"security", "blockchain_protocol"},
        "privacy": {"security", "legal_regulatory"},
        "royalty": {"legal_regulatory", "finance_tax_treasury"},
        "cross-border": {"legal_regulatory", "regional_global_localization"},
        "settlement": {"blockchain_protocol", "finance_tax_treasury"},
    }
    for domain, expected in cumulative_expectations.items():
        assert required_specialists_for({domain}, policy) == expected

    all_domains = [
        "security", "legal", "deployment", "blockchain", "llm",
        "copyright", "tax", "accessibility", "localization"
    ]
    all_files = {"tests/specialist-matrix.json"}
    all_specialists = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_files": ["tests/specialist-matrix.json"],
        "domain_classifications": [{
            "path": "tests/specialist-matrix.json", "domains": all_domains,
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.matrix"
        }],
        "changed_domains": all_domains,
        "specialist_endorsements": sorted(expected_ids), "hard_blocks": []
    }, policy, all_files)
    assert all_specialists["agent_auto_merge_authorized"] is True
    assert set(all_specialists["required_specialists"]) == expected_ids

    rights_files = {"contracts/example-rights.json"}
    missing_one = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_files": ["contracts/example-rights.json"],
        "domain_classifications": [{
            "path": "contracts/example-rights.json", "domains": ["rights"],
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.rights"
        }],
        "changed_domains": ["rights"],
        "specialist_endorsements": ["legal_regulatory"], "hard_blocks": []
    }, policy, rights_files)
    assert missing_one["agent_auto_merge_authorized"] is False
    assert missing_one["missing_specialists"] == ["ip_rights_licensing"]

    security_files = {"docs/security-change.md"}
    security_alias = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_files": ["docs/security-change.md"],
        "domain_classifications": [{
            "path": "docs/security-change.md", "domains": ["security"],
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.security"
        }],
        "changed_domains": ["security"],
        "specialist_endorsements": ["security_privacy"], "hard_blocks": []
    }, policy, security_files)
    assert security_alias["agent_auto_merge_authorized"] is True
    assert security_alias["normalized_specialist_endorsements"] == ["security"]

    merge_file = {"scripts/governed_merge_decision.py"}
    missing_required_domain = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_files": ["scripts/governed_merge_decision.py"],
        "domain_classifications": [{
            "path": "scripts/governed_merge_decision.py", "domains": ["agent"],
            "provenance": "deterministic_path_rule"
        }],
        "changed_domains": ["agent"],
        "specialist_endorsements": ["ai_ml_llm_tevv"], "hard_blocks": []
    }, policy, merge_file)
    assert missing_required_domain["agent_auto_merge_authorized"] is False
    assert any(
        "domain_classification_missing_required:scripts/governed_merge_decision.py:security" in error
        for error in missing_required_domain["domain_classification_errors"]
    )

    mismatch = decide({
        "risk_class": "D2", "scores": common_scores, "votes": four_yes,
        "changed_files": ["scripts/governed_merge_decision.py"],
        "domain_classifications": [{
            "path": "scripts/governed_merge_decision.py", "domains": ["security", "agent"],
            "provenance": "deterministic_path_rule"
        }],
        "changed_domains": ["agent"],
        "specialist_endorsements": ["security_privacy", "ai_ml_llm_tevv"],
        "hard_blocks": []
    }, policy, merge_file)
    assert mismatch["agent_auto_merge_authorized"] is False
    assert any(
        error.startswith("changed_domains_assertion_mismatch:")
        for error in mismatch["domain_classification_errors"]
    )

    legal_files = {"contracts/example-legal.json"}
    d3 = decide({
        "risk_class": "D3", "scores": common_scores, "votes": four_yes,
        "changed_files": ["contracts/example-legal.json"],
        "domain_classifications": [{
            "path": "contracts/example-legal.json", "domains": ["legal"],
            "provenance": "reviewer_classification", "evidence_ref": "ct.evidence.test.legal"
        }],
        "changed_domains": ["legal"],
        "specialist_endorsements": ["legal_regulatory"],
        "hard_blocks": [], "human_authorized": False
    }, policy, legal_files)
    assert d3["agent_auto_merge_authorized"] is False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verify-git-diff", action="store_true")
    parser.add_argument("--git-base")
    parser.add_argument("--git-head")
    args = parser.parse_args()
    policy = load_json(MANIFEST)

    if args.self_test:
        self_test(policy)
        print(
            "Agent-sovereign merge-decision self-test passed: 4/5 + Agent D preserved; "
            "material changed files require trusted Git-diff exact-set binding; "
            "per-file domain provenance and nine cumulative specialist gates enforced; "
            "D3 cannot auto-merge."
        )
        return 0

    trusted: set[str] | None = None
    if args.git_base or args.git_head or args.verify_git_diff:
        if not args.git_base or not args.git_head:
            parser.error("--git-base and --git-head are both required for trusted Git diff binding")
        try:
            trusted = trusted_changed_files_from_git(args.git_base, args.git_head)
        except ValueError as exc:
            raise SystemExit(f"ERROR: {exc}") from exc

    if args.verify_git_diff:
        print(json.dumps({
            "trusted_changed_files_count": len(trusted or set()),
            "trusted_changed_files_digest": changed_file_digest(trusted or set()),
            "trusted_changed_files_redacted": True,
        }, indent=2, sort_keys=True))
        if not args.packet:
            return 0

    if not args.packet:
        parser.error("--packet is required unless --self-test or --verify-git-diff is used")

    packet = load_json(args.packet)
    result = decide(packet, policy, trusted)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
