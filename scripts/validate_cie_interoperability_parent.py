#!/usr/bin/env python3
"""Validate the current-main CIE parent continuity packet."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "developers/manifests/cie-interoperability-parent.v1.json"
COMMERCIAL_PATH = ROOT / "developers/manifests/cie-commercialization-candidates.v1.json"
TEMPLATE_PATH = ROOT / "developers/templates/framework-child-interoperability-backlink.v1.json"
EVALS_PATH = ROOT / "developers/evals/cie-parent-interoperability-evals.v1.json"
DOCTRINE_PATH = ROOT / "doctrine/cultural-imprint-engine.mdx"
EXPECTED_PARENT_BASE = "c7f14b73cff09f00a8f94f15a8587289de18ff7b"
EXPECTED_CHILD_HEAD = "c8133b1d774edb7f386b5864b160bb7f2ec66589"
EXPECTED_CHILD_CONTRACT_DIGEST = "1723291e5e1f6e76a771290fece4cc8cb6f23bdf73d3bea8c8e20439354a092f"
EXPECTED_ALGORITHM_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


class ValidationError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def digest(value: dict[str, Any]) -> str:
    projection = copy.deepcopy(value)
    projection.pop("contract_digest", None)
    raw = json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_manifest(value: dict[str, Any]) -> None:
    parent = value["canonical_parent"]
    require(parent["base_sha"] == EXPECTED_PARENT_BASE, "parent_base_mismatch")
    require(parent["merge_or_main_write_authority"] is False, "agent_c_main_write_prohibited")
    require(parent["main_protection_observed"] == "UNPROTECTED", "main_protection_truth_mismatch")

    current = value["factory_lifecycle"]["current_framework"]
    require(current["repository_state"] == "PROVISIONED_UNLINKED", "cie_must_remain_provisioned_unlinked")
    require(current["package_state"] == "CONTROLLED_TEST", "cie_package_state_mismatch")
    require(not current["operationally_enabled"] and not current["public_activation_allowed"], "cie_activation_prohibited")
    require(not current["vote_eligible"] and not current["quorum_eligible"], "cie_vote_prohibited")
    require(current["parent_certification_agent"] == "ct.relay.agent-d", "agent_d_mandatory")
    require(current["parent_certification_state"] == "pending", "parent_certification_pending")
    require(current["d3_human_reserved"] is True, "d3_human_reserved")

    nxt = value["factory_lifecycle"]["next_framework"]
    require(nxt["state"] == "RESEARCH_CANDIDATE" and not nxt["implementation_allowed"], "next_framework_leapfrog")

    federation = value["repository_federation"]
    require(federation["immutable_child_repository_id"] == 1341314455, "child_repo_id_mismatch")
    require(federation["child_candidate_head"] == EXPECTED_CHILD_HEAD, "child_head_mismatch")
    require(federation["child_contract_digest"] == EXPECTED_CHILD_CONTRACT_DIGEST, "child_digest_mismatch")
    require(not federation["linked_governed"] and not federation["parent_certified"], "premature_link_or_certification")
    require(not federation["sync_agents_allowed"] and not federation["transport_identities_vote_eligible"], "transport_authority_prohibited")

    agent = value["agent_machine"]
    require(not agent["parent_agent"]["vote_eligible"], "framework_agent_vote_prohibited")
    require(not agent["subagents_can_vote"] and not agent["subagents_can_self_verify_c_originated_work"], "subagent_authority_prohibited")
    for key in ("founder_impersonation", "provider_mutation", "credential_operation", "money_movement"):
        require(agent[key] is False, "agent_prohibited_authority:" + key)

    protected = value["protected_algorithm_boundary"]
    require(protected["public_contract_digest"] == EXPECTED_ALGORITHM_DIGEST, "algorithm_digest_mismatch")
    require(protected["invocation_state"] == "HOLD", "protected_invocation_must_hold")
    require(not protected["public_calibration_or_weights_allowed"], "public_calibration_prohibited")
    require(not protected["public_private_eval_corpus_allowed"], "public_eval_corpus_prohibited")
    require(not protected["public_runtime_locator_allowed"], "public_runtime_locator_prohibited")

    surfaces = value["interoperability_surfaces"]
    require(surfaces["signed_event_required"] and surfaces["idempotency_required"] and surfaces["portable_export_required"], "interop_invariants_missing")
    require(not surfaces["client_side_provider_credentials"], "client_side_credentials_prohibited")

    pallet = value["chlom_pallet"]
    require(not pallet["cie_grants_rights"] and not pallet["chlom_substitutes_cultural_alignment"], "cie_chlom_boundary")
    require(not pallet["wallet_or_on_chain_activation"], "wallet_or_chain_activation_prohibited")

    projection = value["thivebase_projection"]
    require(projection["state"] == "DRAFT_ONLY_NOT_APPLIED" and not projection["apply_allowed"], "thivebase_auto_apply_prohibited")
    require(projection["expected_package_public_contract_digest"] == EXPECTED_CHILD_CONTRACT_DIGEST, "thivebase_package_digest_mismatch")
    require(projection["expected_algorithm_public_contract_digest"] == EXPECTED_ALGORITHM_DIGEST, "thivebase_algorithm_digest_mismatch")
    require(not projection["operationally_enabled"] and not projection["public_activation_allowed"] and not projection["can_vote"], "thivebase_activation_prohibited")
    require(projection["mcp_state"] == "disabled", "thivebase_mcp_must_remain_disabled")
    require(not projection["exact_price_authorized"] and not projection["checkout_enabled"] and not projection["customer_entitlement_active"], "thivebase_commerce_activation_prohibited")

    commercial = value["commercialization"]
    require(commercial["state"] == "candidate", "commercial_state_mismatch")
    require(not commercial["exact_price_authorized"] and not commercial["stripe_product_or_price_created"], "price_or_stripe_activation_prohibited")
    require(not commercial["checkout_enabled"] and not commercial["fulfillment_certified"], "checkout_or_fulfillment_activation_prohibited")
    require(not commercial["customer_entitlement_active"] and not commercial["certification_mark_authorized"], "entitlement_or_mark_activation_prohibited")

    ip = value["ip_publication"]
    require(ip["accepted_issue_131_disposition"] == "pending" and ip["unresolved_classification"] == "HOLD", "ip_gate_must_hold")
    scan = value["retroactive_scan_contract"]
    require(scan["scan_cannot_certify"] and scan["research_remains_research_until_governed_promotion"], "scan_cannot_certify")
    require(value["contract_digest"] == digest(value), "parent_contract_digest_invalid")


def validate_surfaces() -> None:
    commercial = load(COMMERCIAL_PATH)
    require(commercial["state"] == "candidate" and commercial["exact_prices"] == [], "commercial_catalog_boundary")
    require(not commercial["checkout_enabled"] and not commercial["rights_cleared"] and not commercial["public_sale_allowed"], "commercial_activation_prohibited")

    template = load(TEMPLATE_PATH)
    fields = template["fields"]
    require(fields["parent_certification_agent"] == "ct.relay.agent-d", "template_agent_d_mandatory")
    require(not fields["operationally_enabled"] and not fields["vote_eligible"] and not fields["sync_agents_allowed"], "template_activation_prohibited")
    require(fields["d3_human_reserved"] is True, "template_d3_boundary")

    evals = load(EVALS_PATH)
    require(evals["private_eval_corpus_included"] is False, "private_eval_corpus_prohibited")
    required = {"vote_activation", "operational_activation", "agent_d_removal", "thivebase_apply", "next_framework_leapfrog", "price_activation", "child_linked_without_evidence"}
    require(required <= {case["id"] for case in evals["cases"]}, "negative_eval_coverage_incomplete")

    doctrine = DOCTRINE_PATH.read_text(encoding="utf-8")
    for marker in (EXPECTED_PARENT_BASE, EXPECTED_CHILD_HEAD, EXPECTED_CHILD_CONTRACT_DIGEST, EXPECTED_ALGORITHM_DIGEST, "RESEARCH_CANDIDATE", "PROVISIONED_UNLINKED"):
        require(marker in doctrine, "doctrine_marker_missing:" + marker)


def expect_failure(mutator) -> None:
    candidate = load(MANIFEST_PATH)
    mutator(candidate)
    try:
        validate_manifest(candidate)
    except ValidationError:
        return
    raise ValidationError("negative_control_unexpectedly_passed")


def self_test() -> None:
    validate_manifest(load(MANIFEST_PATH))
    validate_surfaces()
    expect_failure(lambda c: c["factory_lifecycle"]["current_framework"].__setitem__("vote_eligible", True))
    expect_failure(lambda c: c["factory_lifecycle"]["current_framework"].__setitem__("operationally_enabled", True))
    expect_failure(lambda c: c["factory_lifecycle"]["current_framework"].__setitem__("parent_certification_agent", "ct.relay.agent-c"))
    expect_failure(lambda c: c["repository_federation"].__setitem__("linked_governed", True))
    expect_failure(lambda c: c["thivebase_projection"].__setitem__("apply_allowed", True))
    expect_failure(lambda c: c["commercialization"].__setitem__("exact_price_authorized", True))
    expect_failure(lambda c: c["factory_lifecycle"]["next_framework"].__setitem__("implementation_allowed", True))
    expect_failure(lambda c: c["protected_algorithm_boundary"].__setitem__("public_contract_digest", "deadbeef"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    validate_manifest(load(MANIFEST_PATH))
    validate_surfaces()
    if args.self_test:
        self_test()
    print("CIE parent interoperability continuity: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
