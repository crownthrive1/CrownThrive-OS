#!/usr/bin/env python3
"""CrownThrive Framework Factory deterministic planner and validator.

The factory prepares the next bounded framework packet. It does not create
sovereign authority, create repositories, bypass parent certification, or infer
missing evidence. Provider writes remain separate governed actions.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/framework-factory.v1.json"
FEDERATION = ROOT / "developers/manifests/repository-federation.v1.json"
FRAMEWORK_REGISTRY = ROOT / "doctrine/framework-engine-registry.mdx"

LIFECYCLE = [
    "SOURCE_DISCOVERY",
    "IDENTITY_RECONCILIATION",
    "DOCTRINE_NORMALIZATION",
    "AGENT_SCAFFOLD",
    "ALGORITHM_CONTRACT",
    "ETHICS_BOUNDARY",
    "CHLOM_MAPPING",
    "EVALS_TEVV",
    "REPOSITORY_PLAN",
    "FEDERATION_BOOTSTRAP",
    "CONTROLLED_TEST",
    "SOVEREIGN_SPECIALIST_REVIEW",
    "GOVERNED_ACCEPTANCE",
    "CHILD_CERTIFICATION",
    "RETROACTIVE_SCAN",
    "PRODUCTION_LIMITED",
    "MAINTAINED",
]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"{path.name}: object required")
    return value


def quorum_required(voters: int, ratio: float = 0.75) -> int:
    if voters < 1:
        fail("eligible voter count must be positive")
    return math.ceil(voters * ratio)


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("manifest_id") != "ct.manifest.framework-factory.v1":
        fail("framework factory manifest identity drift")
    if data.get("program_authority_issue") != 148:
        fail("founder program authority must remain issue #148")
    if data.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support":
        fail("canonical parent repository drift")

    invariants = data.get("constitutional_invariants", {})
    if float(invariants.get("approval_ratio", 0)) != 0.75:
        fail("approval ratio must remain 75%")
    for key in (
        "agent_d_mandatory",
        "deny_or_block_prevents_automatic_merge",
        "missing_or_abstain_never_approves",
        "d3_human_reserved",
        "one_accepted_framework_agent_one_vote",
        "framework_subagents_non_voting",
        "transport_messages_non_voting",
        "repository_identity_non_voting",
        "child_self_activation_prohibited",
        "child_self_certification_prohibited",
        "factory_cannot_change_approval_ratio",
        "factory_cannot_remove_agent_d",
        "factory_cannot_self_authorize_unenumerated_constitutional_framework",
    ):
        if invariants.get(key) is not True:
            fail(f"constitutional invariant missing: {key}")

    repo = data.get("repository_baseline", {})
    required_repo_truths = (
        "parent_certification_required",
        "bidirectional_reference_required",
        "message_ack_lifecycle_required",
        "heartbeat_required",
        "hash_chained_events_required",
        "inherited_governance_required",
        "inherited_security_required",
        "restricted_algorithm_material_in_public_repo_prohibited",
        "vault_or_approved_private_runtime_required_for_proprietary_calibration",
    )
    for key in required_repo_truths:
        if repo.get(key) is not True:
            fail(f"repository baseline missing: {key}")
    if repo.get("child_operational_before_linked_governed") is not False:
        fail("child repositories must remain non-operational before linked_governed")

    baseline = data.get("framework_agent_baseline", {})
    if int(baseline.get("minimum_institutionalization_score", 0)) != 85:
        fail("minimum framework institutionalization score must remain 85")
    if baseline.get("algorithm_public_contract_private_calibration_split") is not True:
        fail("framework algorithm public/private split is mandatory")
    if baseline.get("framework_override_is_permission_escalation") is not False:
        fail("framework override must never become permission escalation")
    required_artifacts = set(baseline.get("required_artifacts", []))
    for item in {
        "canonical_doctrine",
        "machine_contract",
        "parent_agent",
        "non_voting_subagent_topology",
        "score_or_decision_contract",
        "ethics_and_boundaries",
        "hard_blocks_or_non_negotiables",
        "human_escalation_triggers",
        "chlom_pallet_or_mapping",
        "independent_eval_suite",
        "repository_federation_contract",
        "retroactive_scan_contract",
        "api_mcp_contract",
        "documentation_projection",
        "rollback_recovery_contract",
    }:
        if item not in required_artifacts:
            fail(f"required framework artifact missing: {item}")

    sequence = data.get("authorized_sovereign_sequence", [])
    if not isinstance(sequence, list) or len(sequence) != 8:
        fail("authorized sovereign sequence must contain eight initial frameworks")
    initial = int(data.get("initial_sovereign_voters", 0))
    if initial != 5:
        fail("initial sovereign voter baseline must remain five for this factory version")

    seen_ids: set[str] = set()
    seen_agents: set[str] = set()
    seen_repos: set[str] = set()
    for idx, item in enumerate(sequence, start=1):
        if item.get("order") != idx:
            fail(f"framework order drift at position {idx}")
        fid = str(item.get("framework_id", ""))
        aid = str(item.get("framework_agent_id", ""))
        repo_name = str(item.get("child_repo_candidate", ""))
        if not fid.startswith("ct.framework.") or not aid.startswith("ct.framework-agent."):
            fail(f"invalid framework identity at order {idx}")
        if fid in seen_ids or aid in seen_agents or repo_name in seen_repos:
            fail("duplicate framework/agent/repository identity in authorized sequence")
        seen_ids.add(fid)
        seen_agents.add(aid)
        seen_repos.add(repo_name)
        voters = initial + idx
        required = quorum_required(voters)
        if item.get("prospective_total_voters") != voters:
            fail(f"prospective voter arithmetic drift for {fid}")
        if item.get("prospective_required_approvals") != required:
            fail(f"prospective quorum arithmetic drift for {fid}")

    if sequence[0].get("framework_id") != "ct.framework.cultural-imprint-engine":
        fail("CIE must remain the first framework-factory constitutional migration")
    if sequence[1].get("framework_id") != "ct.framework.convergent-ecosystem":
        fail("Convergent Ecosystem must remain next after CIE in factory v1")

    if not FEDERATION.is_file() or not FRAMEWORK_REGISTRY.is_file():
        fail("repository federation or framework source registry missing")
    source_text = FRAMEWORK_REGISTRY.read_text(encoding="utf-8")
    for fid in seen_ids:
        if fid not in source_text:
            fail(f"authorized framework not present in canonical Framework Registry: {fid}")


def next_candidate(data: dict[str, Any]) -> dict[str, Any]:
    """Return the next bounded factory target without inventing completion.

    The factory may prepare research/scaffolding for later candidates while the
    prior framework is not yet linked-governed, but constitutional activation is
    sequential and fail-closed.
    """
    sequence = data["authorized_sovereign_sequence"]
    first = sequence[0]
    if first.get("physical_child_repository_state") != "linked_governed":
        return {
            "framework_id": first["framework_id"],
            "next_safe_packet": "complete_CIE_governed_acceptance_then_provision_backlink_oidc_and_parent_certify_child",
            "activation_allowed": False,
            "parallel_research_allowed_for_next": True,
            "parallel_research_framework_id": sequence[1]["framework_id"],
            "blocking_reason": "CIE child repository is not yet linked_governed",
        }
    return {
        "framework_id": sequence[1]["framework_id"],
        "next_safe_packet": "build_convergent_ecosystem_source_and_doctrine_reconciliation_packet",
        "activation_allowed": False,
        "parallel_research_allowed_for_next": True,
        "blocking_reason": "candidate must progress through factory lifecycle and governed acceptance",
    }


def plan_for(data: dict[str, Any], framework_id: str) -> dict[str, Any]:
    sequence = data["authorized_sovereign_sequence"]
    item = next((row for row in sequence if row["framework_id"] == framework_id), None)
    if item is None:
        fail("framework is not in the program-authorized sovereign sequence")
    return {
        "framework_id": item["framework_id"],
        "canonical_name": item["canonical_name"],
        "framework_agent_id": item["framework_agent_id"],
        "child_repo_candidate": item["child_repo_candidate"],
        "current_state": item["current_state"],
        "prospective_total_voters": item["prospective_total_voters"],
        "prospective_required_approvals": item["prospective_required_approvals"],
        "agent_d_mandatory": True,
        "d3_human_reserved": True,
        "child_self_activation": False,
        "required_artifacts": data["framework_agent_baseline"]["required_artifacts"],
        "lifecycle": LIFECYCLE,
        "repository_contract": {
            "parent": data["canonical_parent_repository"],
            "backlink_path": data["repository_baseline"]["child_backlink_path"],
            "auth": data["repository_baseline"]["authentication"],
            "parent_certification_required": True,
        },
        "promotion_semantics": "prepare_and_validate_automatically; activate_or_vote_only_after_governed_acceptance_and_linked_governed_child_certification",
    }


def self_test(data: dict[str, Any]) -> None:
    validate_manifest(data)
    assert quorum_required(5) == 4
    assert quorum_required(6) == 5
    assert quorum_required(7) == 6
    assert quorum_required(8) == 6
    assert quorum_required(9) == 7
    assert quorum_required(13) == 10
    nxt = next_candidate(data)
    assert nxt["framework_id"] == "ct.framework.cultural-imprint-engine"
    assert nxt["parallel_research_framework_id"] == "ct.framework.convergent-ecosystem"
    assert nxt["activation_allowed"] is False
    plan = plan_for(data, "ct.framework.convergent-ecosystem")
    assert plan["prospective_total_voters"] == 7
    assert plan["prospective_required_approvals"] == 6
    assert plan["child_self_activation"] is False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--plan")
    args = parser.parse_args()
    data = load(MANIFEST)

    if args.self_test:
        self_test(data)
        print("Framework Factory self-test PASS: eight founder-authorized sequential framework candidates, 75%-ceil quorum growth, parent-certified child repos, non-voting subagents and D3 boundary verified.")
        return 0
    validate_manifest(data)
    if args.next:
        print(json.dumps(next_candidate(data), indent=2, sort_keys=True))
        return 0
    if args.plan:
        print(json.dumps(plan_for(data, args.plan), indent=2, sort_keys=True))
        return 0
    print("Framework Factory manifest validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
