#!/usr/bin/env python3
"""Validate the Cultural Imprint Engine framework-agent contract."""
from __future__ import annotations
import json
from pathlib import Path
from cie_scan import DIMENSIONS, HARD_BLOCK_CODES, PASS_THRESHOLD, PUBLIC_CONTRACT_DIGEST, self_test as scan_self_test

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/cie-framework-agent.v1.json"
ALGORITHM_REGISTRY = ROOT / "developers/manifests/framework-algorithm-registry.v1.json"
FEDERATION = ROOT / "developers/manifests/repository-federation.v1.json"
DOCTRINE = ROOT / "doctrine/cultural-imprint-engine.mdx"
PALLET = ROOT / "chlom/cie-cultural-governance-pallet.mdx"
AGENT_DOC = ROOT / "automation/cie-framework-agent.mdx"
FEDERATION_DOC = ROOT / "technology/repository-federation-control-plane.mdx"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("framework_id") != "ct.framework.cultural-imprint-engine": fail("framework id drift")
    agent = data.get("agent", {})
    if agent.get("agent_id") != "ct.framework-agent.cie" or agent.get("permanent") is not True: fail("CIE permanent agent identity drift")
    if agent.get("operational_parent") != "ct.relay.agent-a": fail("CIE operational parent must remain Agent A")
    if agent.get("vote_eligible") is not True or agent.get("vote_independence_required") is not True: fail("CIE sovereign voter independence required")
    if agent.get("may_self_approve_originating_material_change") is not False: fail("CIE cannot self-approve originating material")

    subagents = data.get("subagents", [])
    ids = {item.get("agent_id") for item in subagents}
    expected = {
        "ct.subagent.cie.identity-fit", "ct.subagent.cie.community-value",
        "ct.subagent.cie.story-alignment", "ct.subagent.cie.brand-safety",
        "ct.subagent.cie.legacy-impact", "ct.subagent.cie.remediation-escalation",
    }
    if ids != expected: fail("CIE subagent topology drift")
    if any(item.get("vote_eligible") is not False for item in subagents): fail("CIE subagents must remain non-voting")

    scoring = data.get("scoring", {})
    if scoring.get("pass_threshold") != PASS_THRESHOLD: fail("CIE pass threshold drift")
    dims = scoring.get("dimensions", {})
    if set(dims) != set(DIMENSIONS): fail("CIE canonical five dimensions drift")
    if sum(int(v.get("max_points", 0)) for v in dims.values()) != 100: fail("CIE scoring must total 100")
    if set(data.get("hard_blocks", [])) != HARD_BLOCK_CODES: fail("CIE hard-block set drift")
    if scoring.get("hard_blocks_override_score") is not True: fail("CIE hard blocks must override score")
    if scoring.get("calibration_state") != "restricted_vault_runtime" or scoring.get("public_repository_contains_calibration") is not False: fail("CIE calibration must remain restricted to Vault runtime")
    if scoring.get("runtime_algorithm_id") != "ct.algorithm.cie.v1" or scoring.get("runtime_service_id") != "repository_federation_bus": fail("CIE runtime binding drift")
    if scoring.get("public_contract_digest") != PUBLIC_CONTRACT_DIGEST: fail("CIE public contract digest drift")

    ethics = data.get("ethics_and_boundaries", {})
    for key in (
        "artifact_not_person_scoring", "sensitive_trait_inference_prohibited",
        "race_ethnicity_religion_or_other_sensitive_profile_scoring_prohibited",
        "community_authenticity_policing_of_people_prohibited",
        "evidence_and_reason_required_for_every_material_finding",
        "correction_and_appeal_path_required",
    ):
        if ethics.get(key) is not True: fail(f"CIE ethics invariant missing: {key}")

    sync = data.get("ecosystem_sync", {})
    if sync.get("applies_to_all_registered_agents") is not True or sync.get("retroactive_scan_required") is not True: fail("CIE ecosystem sync/retroactive scan required")
    if sync.get("transport") != "OIDC_authenticated_repository_federation_bus" or sync.get("subagent_messages_create_votes") is not False: fail("CIE federation transport/vote boundary drift")

    chlom = data.get("chlom", {})
    if chlom.get("pallet_id") != "ct.chlom.pallet.cie-cultural-governance": fail("CIE CHLOM pallet id drift")

    commercial = data.get("commercialization", {})
    if commercial.get("offer_state") != "candidate" or commercial.get("checkout_enabled") is not False or commercial.get("exact_price_authorized") is not False: fail("CIE commercialization must remain candidate/no checkout/no exact price")

    repo = data.get("repository_custody", {})
    if repo.get("target_repository") != "crownthrive1/CrownThrive-CIE": fail("CIE target repo drift")
    if repo.get("target_state") != "target_not_connected_not_provisioned": fail("CIE target repo must remain explicit until provisioned")
    if repo.get("parent_repository") != "crownthrive1/CrownThrive-Support" or repo.get("parent_certification_required") is not True or repo.get("child_self_activation") is not False: fail("CIE parent-child repository governance drift")

    ml = data.get("ml_and_ai", {})
    if ml.get("ml_training_state") != "not_started" or ml.get("ml_may_not_determine_personal_cultural_authenticity") is not True: fail("CIE ML boundary drift")

    readiness = data.get("implementation_readiness", {})
    if readiness.get("score") != 92 or readiness.get("pass_threshold") != 85 or readiness.get("verdict") != "PASS_PHASE_2_99_INSTITUTIONALIZATION": fail("CIE readiness score/state drift")
    if sum(int(v) for v in readiness.get("dimensions", {}).values()) != 92: fail("CIE readiness dimension arithmetic drift")

    algorithm_registry = json.loads(ALGORITHM_REGISTRY.read_text(encoding="utf-8"))
    algorithms = algorithm_registry.get("algorithms", [])
    if len(algorithms) != 1 or algorithms[0].get("algorithm_id") != "ct.algorithm.cie.v1": fail("CIE algorithm registry drift")
    if algorithms[0].get("public_contract_digest") != PUBLIC_CONTRACT_DIGEST: fail("CIE algorithm/public contract mismatch")
    if algorithms[0].get("vault_policy_ref") != "vault:ct.algorithm.cie.v1.policy_bundle": fail("CIE Vault policy reference drift")

    federation = json.loads(FEDERATION.read_text(encoding="utf-8"))
    child = next((item for item in federation.get("repositories", []) if item.get("repo_id") == "ct.repo.cie"), None)
    if not child or child.get("governance_state") != "pending_provisioning" or child.get("operationally_enabled") is not False: fail("CIE child must remain disabled until repository provisioning and parent certification")

    for path in (DOCTRINE, PALLET, AGENT_DOC, FEDERATION_DOC):
        if not path.is_file(): fail(f"missing CIE documentation: {path.relative_to(ROOT)}")
    scan_self_test()
    print("CIE framework-agent validation PASS: 92/100 institutionalization score, six-agent topology, five canonical dimensions, ethics boundaries, CHLOM pallet, OIDC federation and Vault-backed protected runtime verified; child repo remains pending/disabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
