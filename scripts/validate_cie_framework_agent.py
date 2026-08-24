#!/usr/bin/env python3
"""Validate the Cultural Imprint Engine non-voting controlled-test package."""
from __future__ import annotations

import json
from pathlib import Path
from cie_scan import DIMENSIONS, HARD_BLOCK_CODES, PASS_THRESHOLD, PUBLIC_CONTRACT_DIGEST, self_test as scan_self_test

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cie-framework-agent.v1.json"
ALGORITHMS = ROOT / "developers/manifests/framework-algorithm-registry.v1.json"
FEDERATION = ROOT / "developers/manifests/repository-federation.v1.json"
FLEET = ROOT / "developers/manifests/framework-child-fleet.v1.json"
DOCS = [
    ROOT / "doctrine/cultural-imprint-engine.mdx",
    ROOT / "chlom/cie-cultural-governance-pallet.mdx",
    ROOT / "automation/cie-framework-agent.mdx",
    ROOT / "technology/repository-federation-control-plane.mdx",
]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    agent = data.get("agent", {})
    if data.get("manifest_version") != "2.0.0" or data.get("framework_id") != "ct.framework.cultural-imprint-engine" or data.get("package_id") != "ct.framework-package.cie":
        fail("CIE package identity drift")
    if data.get("status") != "controlled_test_non_voting":
        fail("CIE framework state drift")
    if agent.get("agent_id") != "ct.framework-agent.cie" or agent.get("operational_parent") != "ct.relay.agent-a":
        fail("CIE identity/parent drift")
    if agent.get("vote_eligible") is not False or agent.get("may_create_sovereign_vote") is not False or agent.get("sovereign_vote_state") != "not_accepted":
        fail("CIE must remain non-voting")
    if agent.get("may_self_approve_originating_material_change") is not False:
        fail("CIE self-approval prohibited")
    if any(item.get("vote_eligible") is not False for item in data.get("subagents", [])):
        fail("CIE subagents must remain non-voting")

    scoring = data.get("scoring", {})
    dims = scoring.get("dimensions", {})
    if scoring.get("pass_threshold") != PASS_THRESHOLD or set(dims) != set(DIMENSIONS) or sum(int(v.get("max_points", 0)) for v in dims.values()) != 100:
        fail("CIE public scoring contract drift")
    if set(data.get("hard_blocks", [])) != HARD_BLOCK_CODES or scoring.get("hard_blocks_override_score") is not True:
        fail("CIE hard-block drift")
    if scoring.get("calibration_state") != "restricted_private_runtime_registered" or scoring.get("public_repository_contains_calibration") is not False:
        fail("protected calibration boundary drift")
    if scoring.get("public_contract_digest") != PUBLIC_CONTRACT_DIGEST:
        fail("public contract digest drift")

    ethics = data.get("ethics_and_boundaries", {})
    for key in (
        "artifact_not_person_scoring",
        "sensitive_trait_inference_prohibited",
        "race_ethnicity_religion_or_other_sensitive_profile_scoring_prohibited",
        "community_authenticity_policing_of_people_prohibited",
        "evidence_and_reason_required_for_every_material_finding",
        "correction_and_appeal_path_required",
    ):
        if ethics.get(key) is not True:
            fail(f"ethics invariant missing: {key}")

    sync = data.get("ecosystem_sync", {})
    if sync.get("retroactive_scan_required") is not True or sync.get("subagent_messages_create_votes") is not False or sync.get("sync_agents_creates_votes") is not False:
        fail("sync/vote boundary drift")

    commercial = data.get("commercialization", {})
    if commercial.get("offer_state") != "candidate" or commercial.get("checkout_enabled") is not False or commercial.get("exact_price_authorized") is not False:
        fail("commercialization boundary drift")

    package = data.get("package_execution", {})
    expected_package = {
        "package_id": "ct.framework-package.cie",
        "physical_repository_required": False,
        "package_state": "controlled_test",
        "parent_certification_required": True,
        "parent_certification_agent": "ct.relay.agent-d",
        "parent_certification_state": "pending",
        "parent_certification_detail": "pending_pre_cert_evidence_and_governed_acceptance",
        "optional_repository_projection_state": "physical_provisioned_pre_cert",
        "optional_repository_projection_repo_id": "ct.repo.cie",
        "optional_repository_projection_github_repository_id": 1341314455,
        "optional_repository_projection_governance_state": "provisioned_unlinked",
        "optional_repository_projection_head_sha": "073da74bb6eb1fde31b9a6d0321bb85baf5ac8fd",
        "optional_repository_projection_contract_sha256": "2c88d166607f0f280a6024c31720b14767896ef8f7a67109eb9863943490630a",
        "optional_repository_projection_operationally_enabled": False,
        "optional_repository_projection_vote_eligible": False,
        "public_activation_allowed": False,
        "operationally_enabled": False,
        "can_vote": False,
        "pull_request_validation_oidc": False,
        "workflow_ref_environment_agent_capability_binding_required": True,
    }
    for key, value in expected_package.items():
        if package.get(key) != value:
            fail(f"CIE package execution drift: {key}")

    ready = data.get("implementation_readiness", {})
    if ready.get("score") != 92 or ready.get("verdict") != "PASS_PHASE_2_99_CONTROLLED_TEST":
        fail("CIE readiness state drift")

    algorithms = json.loads(ALGORITHMS.read_text(encoding="utf-8"))
    rows = algorithms.get("algorithms", [])
    if len(rows) != 1:
        fail("expected one registered CIE algorithm")
    algo = rows[0]
    if algo.get("algorithm_id") != "ct.algorithm.cie.v1" or algo.get("implementation_package_id") != "ct.framework-package.cie" or algo.get("public_contract_digest") != PUBLIC_CONTRACT_DIGEST:
        fail("algorithm registry mismatch")
    if algo.get("physical_repository_required") is not False:
        fail("CIE algorithm cannot require a standalone repository")
    if "vault_policy_ref" in algo or algo.get("private_runtime_reference_state") != "registered_not_public":
        fail("public algorithm registry must not expose private runtime locator")
    if algo.get("mcp_enabled") is not False:
        fail("CIE MCP must remain disabled before governed promotion")

    fed = json.loads(FEDERATION.read_text(encoding="utf-8"))
    fpkg = next((x for x in fed.get("framework_packages", []) if x.get("package_id") == "ct.framework-package.cie"), None)
    if not fpkg:
        fail("CIE federation package missing")
    if fpkg.get("package_state") != "controlled_test" or fpkg.get("operationally_enabled") is not False or fpkg.get("public_activation_allowed") is not False or fpkg.get("can_vote") is not False or fpkg.get("parent_certification_state") != "pending":
        fail("CIE federation package state drift")
    if fed.get("authority", {}).get("physical_child_repository_required") is not False:
        fail("federation cannot require physical child repository")

    fleet = json.loads(FLEET.read_text(encoding="utf-8"))
    cie = next((x for x in fleet.get("framework_children", []) if x.get("framework_id") == "ct.framework.cultural-imprint-engine"), None)
    if not cie or cie.get("package_id") != "ct.framework-package.cie" or cie.get("current_state") != "CONTROLLED_TEST" or cie.get("package_materialization_allowed") is not True:
        fail("CIE fleet package state drift")

    for path in DOCS:
        if not path.is_file():
            fail(f"missing CIE documentation: {path.relative_to(ROOT)}")
    scan_self_test()
    print("CIE validation PASS: controlled-test framework package, non-voting parent/subagents, executable package identity, public scoring contract, protected private calibration and Agent-D certification gate verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
