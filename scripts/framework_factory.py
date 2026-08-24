#!/usr/bin/env python3
"""CrownThrive Framework Factory deterministic planner and validator.

The Factory prepares one bounded framework execution package at a time. A framework
child is a package, not a required standalone repository. The Factory cannot create
sovereign authority, bypass Agent D, expose protected algorithms, invent commercial
terms or infer missing evidence.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/framework-factory.v1.json"
FLEET = ROOT / "developers/manifests/framework-child-fleet.v1.json"
FEDERATION = ROOT / "developers/manifests/repository-federation.v1.json"
AGENT_BINDINGS = ROOT / "developers/manifests/agent-federation-bindings.v1.json"
FRAMEWORK_REGISTRY = ROOT / "doctrine/framework-engine-registry.mdx"
LIFECYCLE = [
    "SOURCE_DISCOVERY",
    "PACKAGE_SCAFFOLD",
    "DOCTRINE_AND_MACHINE_CONTRACT",
    "ENGINE_AND_DECISION_INTERFACE",
    "SKILLS_AND_TOOLS",
    "ETHICS_BOUNDARY",
    "CHLOM_MAPPING",
    "EVALS_TEVV",
    "API_MCP_CONTRACT",
    "PRIVATE_RUNTIME_BINDING",
    "CONTROLLED_TEST",
    "SOVEREIGN_SPECIALIST_REVIEW",
    "PARENT_CERTIFICATION_PENDING",
    "GOVERNED_FRAMEWORK_ACCEPTANCE",
    "RETROACTIVE_SCAN",
    "PUBLIC_PACKAGE_CANDIDATE",
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


def participation_contract() -> dict[str, Any]:
    bindings = load(AGENT_BINDINGS)
    rules = bindings.get("rules", {})
    if rules.get("framework_factory_participation_required") is not True:
        fail("all-agent Framework Factory participation contract missing")
    if rules.get("sync_agents_callers_must_be_non_voting") is not True:
        fail("sync_agents caller non-voting invariant missing")
    sync_callers = set(rules.get("non_voting_inventory_sync_agents", []))
    sovereign = {x.get("agent_id") for x in bindings.get("parent_sovereign_bindings", [])}
    if sync_callers != {"ct.subagent.governance-marshal"} or sync_callers & sovereign:
        fail("sync_agents must be owned only by governed non-voting D0-D2 transport")
    contract = bindings.get("factory_participation_contract", {})
    if contract.get("framework_identity_default_vote_state") != "non_voting":
        fail("framework default vote state drift")
    if contract.get("delegated_builder_children") != "non_voting_and_cannot_independently_verify_c_originated_work":
        fail("builder-child verification boundary drift")
    return contract


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("manifest_id") != "ct.manifest.framework-factory.v1" or data.get("manifest_version") != "2.0.0":
        fail("framework factory package-model manifest drift")
    if data.get("program_authority_issue") != 148:
        fail("founder program authority must remain issue #148")
    if data.get("canonical_parent_repository") != "crownthrive1/CrownThrive-Support":
        fail("canonical parent repository drift")
    inv = data.get("constitutional_invariants", {})
    if inv.get("current_sovereign_voters") != 5 or inv.get("current_minimum_approvals") != 4:
        fail("current constitution must remain five voters / four approvals")
    for key in (
        "agent_d_mandatory",
        "deny_or_block_prevents_automatic_merge",
        "missing_or_abstain_never_approves",
        "d3_human_reserved",
        "framework_identity_acceptance_does_not_create_vote",
        "framework_package_acceptance_does_not_create_vote",
        "framework_sovereign_vote_requires_separate_constitutional_acceptance",
        "framework_subagents_non_voting",
        "transport_messages_non_voting",
        "repository_identity_non_voting",
        "package_identity_non_voting",
        "child_self_activation_prohibited",
        "child_self_certification_prohibited",
        "factory_cannot_change_approval_ratio",
        "factory_cannot_remove_agent_d",
        "factory_cannot_self_authorize_unenumerated_constitutional_framework",
    ):
        if inv.get(key) is not True:
            fail(f"constitutional invariant missing: {key}")

    pkg = data.get("package_baseline", {})
    required_true = (
        "framework_package_is_child_identity",
        "optional_standalone_repository_projection_allowed",
        "workflow_ref_environment_agent_capability_binding_required",
        "parent_certification_required",
        "heartbeat_required_for_operational_transport",
        "hash_chained_events_required",
        "inherited_governance_required",
        "inherited_security_required",
        "restricted_algorithm_material_in_public_package_prohibited",
        "approved_private_runtime_required_for_proprietary_calibration",
    )
    for key in required_true:
        if pkg.get(key) is not True:
            fail(f"package baseline missing: {key}")
    for key in ("physical_repository_required", "pull_request_validation_oidc", "package_operational_before_parent_certification_and_acceptance", "package_vote_before_separate_constitutional_acceptance"):
        if pkg.get(key) is not False:
            fail(f"package fail-closed invariant drift: {key}")
    if pkg.get("parent_certification_agent") != "ct.relay.agent-d":
        fail("Agent D must remain package certifier")

    baseline = data.get("framework_agent_baseline", {})
    if baseline.get("minimum_institutionalization_score") != 85:
        fail("framework institutionalization score drift")
    if baseline.get("algorithm_public_contract_private_calibration_split") is not True:
        fail("protected algorithm split missing")
    if baseline.get("framework_override_is_permission_escalation") is not False:
        fail("framework override permission boundary drift")

    sequence = data.get("authorized_framework_sequence", [])
    if len(sequence) != 8:
        fail("authorized framework sequence must contain eight frameworks")
    expected = [
        "ct.framework.cultural-imprint-engine",
        "ct.framework.convergent-ecosystem",
        "ct.framework.thrive-flywheel",
        "ct.framework.chlom",
        "ct.framework.corridor-architecture",
        "ct.framework.hybrid-incubator",
        "ct.framework.mm-suites",
        "ct.framework.one-seat-multiple-industries",
    ]
    if [x.get("framework_id") for x in sequence] != expected:
        fail("framework sequence drift")
    for idx, item in enumerate(sequence, 1):
        if item.get("order") != idx or item.get("current_vote_state") != "non_voting":
            fail(f"framework order/vote drift at {idx}")
        if item.get("physical_repository_required") is not False:
            fail(f"physical repository cannot be required: {item.get('framework_id')}")
        if not str(item.get("package_id", "")).startswith("ct.framework-package."):
            fail(f"package identity missing: {item.get('framework_id')}")

    fleet = load(FLEET)
    if fleet.get("child_definition") != "independently_executable_framework_package_not_physical_repository":
        fail("fleet/factory child semantics mismatch")
    if not FEDERATION.is_file() or not FRAMEWORK_REGISTRY.is_file() or not AGENT_BINDINGS.is_file():
        fail("federation, bindings or framework registry missing")
    text = FRAMEWORK_REGISTRY.read_text(encoding="utf-8")
    for fid in expected:
        if fid not in text:
            fail(f"framework not present in registry: {fid}")
    participation_contract()


def implementation_backed_research_candidates() -> list[dict[str, Any]]:
    rows = participation_contract().get("implementation_backed_research_candidates", [])
    if not isinstance(rows, list):
        fail("implementation-backed research candidates must be a list")
    for row in rows:
        if not isinstance(row, dict) or row.get("candidate_state") != "RESEARCH_CANDIDATE" or row.get("vote_state") != "non_voting" or row.get("framework_implementation_allowed_now") is not False:
            fail("research candidate promotion boundary drift")
    return rows


def next_candidate(data: dict[str, Any]) -> dict[str, Any]:
    sequence = data["authorized_framework_sequence"]
    cie = sequence[0]
    research = implementation_backed_research_candidates()
    if cie.get("parent_certification_state") != "certified" or cie.get("current_state") != "GOVERNED_FRAMEWORK_ACCEPTANCE":
        return {
            "framework_id": cie["framework_id"],
            "package_id": cie["package_id"],
            "next_safe_packet": "complete_CIE_package_authority_binding_parent_certification_and_governed_framework_acceptance",
            "physical_repository_required": False,
            "public_activation_allowed": False,
            "parallel_research_allowed_for_next": True,
            "parallel_research_framework_id": sequence[1]["framework_id"],
            "implementation_backed_research_candidates": [x["framework_id"] for x in research],
            "implementation_of_next_allowed": False,
            "blocking_reason": "CIE package parent certification and governed framework acceptance remain pending",
        }
    return {
        "framework_id": sequence[1]["framework_id"],
        "package_id": sequence[1]["package_id"],
        "next_safe_packet": "build_convergent_ecosystem_package_source_and_doctrine_reconciliation_packet",
        "physical_repository_required": False,
        "public_activation_allowed": False,
        "implementation_backed_research_candidates": [x["framework_id"] for x in research],
        "implementation_of_next_allowed": True,
        "blocking_reason": "candidate must progress through package lifecycle and governed acceptance",
    }


def plan_for(data: dict[str, Any], framework_id: str) -> dict[str, Any]:
    item = next((x for x in data["authorized_framework_sequence"] if x["framework_id"] == framework_id), None)
    if item is not None:
        return {
            "framework_id": item["framework_id"],
            "package_id": item["package_id"],
            "canonical_name": item["canonical_name"],
            "framework_agent_id": item["framework_agent_id"],
            "canonical_host_repository": item.get("canonical_host_repository", "crownthrive1/CrownThrive-Support"),
            "optional_repository_projection": item.get("optional_repository_projection"),
            "physical_repository_required": False,
            "current_state": item["current_state"],
            "current_vote_state": "non_voting",
            "sovereign_vote_activation": "separate_constitutional_packet_required",
            "agent_d_mandatory": True,
            "d3_human_reserved": True,
            "child_self_activation": False,
            "required_artifacts": data["framework_agent_baseline"]["required_artifacts"],
            "lifecycle": LIFECYCLE,
            "promotion_semantics": "package_acceptance_and_parent_certification_do_not_by_themselves_create_sovereign_vote",
        }
    research = next((x for x in implementation_backed_research_candidates() if x.get("framework_id") == framework_id), None)
    if research is None:
        fail("framework is not in authorized sequence or implementation-backed research candidates")
    return {
        "framework_id": framework_id,
        "current_state": research["candidate_state"],
        "evidence_maturity": research["evidence_maturity"],
        "existing_agent_id": research["existing_agent_id"],
        "current_vote_state": "non_voting",
        "research_preparation_allowed_now": True,
        "framework_implementation_allowed_now": False,
        "implementation_gate": research["implementation_gate"],
        "sovereign_vote_activation": "separate_constitutional_packet_required",
        "agent_d_mandatory": True,
        "d3_human_reserved": True,
    }


def self_test(data: dict[str, Any]) -> None:
    validate_manifest(data)
    assert quorum_required(5) == 4
    nxt = next_candidate(data)
    assert nxt["framework_id"] == "ct.framework.cultural-imprint-engine"
    assert nxt["physical_repository_required"] is False
    assert nxt["implementation_of_next_allowed"] is False
    convergent = plan_for(data, "ct.framework.convergent-ecosystem")
    assert convergent["current_vote_state"] == "non_voting" and convergent["physical_repository_required"] is False
    cii = plan_for(data, "ct.framework.cii-thrivefund")
    assert cii["current_state"] == "RESEARCH_CANDIDATE" and cii["framework_implementation_allowed_now"] is False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--plan")
    args = ap.parse_args()
    data = load(MANIFEST)
    if args.self_test:
        self_test(data)
        print("Framework Factory self-test PASS: eight sequential framework packages; physical repo optional; A/B/C/D/S preserved; Agent D mandatory; protected runtime/IP/commercial gates fail closed.")
        return 0
    validate_manifest(data)
    if args.next:
        print(json.dumps(next_candidate(data), indent=2, sort_keys=True))
        return 0
    if args.plan:
        print(json.dumps(plan_for(data, args.plan), indent=2, sort_keys=True))
        return 0
    print("Framework Factory package-model manifest validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
