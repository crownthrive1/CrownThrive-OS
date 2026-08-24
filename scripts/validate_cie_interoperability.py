#!/usr/bin/env python3
"""Fail-closed validator for the current-main CIE interoperability parent anchor."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from typing import Any

EXPECTED_PARENT = "c7f14b73cff09f00a8f94f15a8587289de18ff7b"
EXPECTED_CHILD = "4f34f9c2987da347823d06e30d1b142a383973c5"
EXPECTED_DIGEST = "e337defbe44d74f6c050528cb4fc21c0f20b577f8ceb2480e501479ffca990a3"
EXPECTED_ALGORITHM_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"

class ValidationError(ValueError):
    pass

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)

def validate(data: dict[str, Any]) -> None:
    require(data.get("packet_id") == "ct.packet.cie-interoperability-current-main.v1", "packet identity drift")
    parent = data.get("canonical_parent", {})
    require(parent.get("observed_main_sha") == EXPECTED_PARENT, "parent main drift")
    require(parent.get("write_authority_in_this_packet") is False, "parent write authority prohibited")
    child = data.get("child_package", {})
    require(child.get("candidate_head_sha") == EXPECTED_CHILD, "child head drift")
    require(child.get("candidate_contract_digest_sha256") == EXPECTED_DIGEST, "contract digest drift")
    require(child.get("contract_digest_scheme") == "sha256-canonical-json-sortkeys-v1", "digest scheme drift")
    require(child.get("repository_state") == "PROVISIONED_UNLINKED", "child lifecycle drift")
    for key in ("operationally_enabled", "vote_eligible", "exact_head_independently_verified"):
        require(child.get(key) is False, f"child fail-closed drift: {key}")

    life = data.get("factory_lifecycle", {})
    require(life.get("factory_state") == "CONTROLLED_TEST", "factory state drift")
    require(life.get("parent_certification_agent") == "ct.relay.agent-d", "Agent D mandatory")
    require(life.get("parent_certification_state") == "PENDING", "certification cannot be inferred")
    require(life.get("next_framework_state") == "RESEARCH_CANDIDATE", "Convergent must remain research-only")
    require(life.get("phase_3_advancement_allowed") is False, "Phase 3 advancement prohibited")

    auth = data.get("authority", {})
    require(auth.get("framework_agent_id") == "ct.framework-agent.cie", "framework agent drift")
    require(auth.get("authority_ceiling") == "D2", "authority ceiling drift")
    require(auth.get("d3_human_reserved") is True, "D3 must remain human-reserved")
    require(auth.get("mandatory_parent_certifier") == "ct.relay.agent-d", "mandatory D drift")
    for key in ("vote_eligible", "sovereign_vote_created", "sync_agents_allowed", "self_approval_allowed",
                "merge_or_main_write_allowed", "provider_or_database_mutation_allowed",
                "credential_operation_allowed", "rights_legal_financial_decision_allowed",
                "money_movement_allowed"):
        require(auth.get(key) is False, f"authority lock drift: {key}")

    machine = data.get("agent_machine", {})
    require(machine.get("parent_agent_state") == "PREPARED_NOT_ACTIVATED", "agent activation drift")
    require(machine.get("delegated_subagents_non_voting") is True, "subagents must be non-voting")
    require(machine.get("delegated_subagents_may_independently_verify_c_work") is False, "child verification conflict")
    require(machine.get("protected_runtime_direct_access") is False, "direct protected-runtime access prohibited")

    decision = data.get("decision_interface", {})
    require(decision.get("dispositions") == ["PASS_CANDIDATE", "HOLD", "BLOCK"], "disposition drift")
    require(decision.get("numeric_weights_public") is False, "weights must remain private")
    require(decision.get("numeric_calibration_public") is False, "calibration must remain private")
    require(decision.get("final_authority") is False, "CIE decision cannot be final authority")

    runtime = data.get("protected_runtime", {})
    require(runtime.get("public_contract_digest") == EXPECTED_ALGORITHM_DIGEST, "algorithm digest drift")
    require(runtime.get("classification") == "RESTRICTED_INSTITUTIONAL", "protected classification drift")
    require(runtime.get("runtime_verified_for_candidate_head") is False, "runtime verification cannot be inferred")
    for key in ("implementation_body_public", "weights_or_calibration_public",
                "private_eval_corpora_public", "defensive_rules_public"):
        require(runtime.get(key) is False, f"protected publication drift: {key}")
    require(runtime.get("missing_runtime_or_digest_disposition") == "HOLD", "missing runtime must HOLD")
    require(runtime.get("digest_mismatch_disposition") == "HOLD", "digest mismatch must HOLD")

    api = data.get("api_mcp", {})
    require(api.get("api_state") == "CANDIDATE_NOT_DEPLOYED", "API deployment drift")
    require(api.get("mcp_state") == "DISABLED", "MCP state drift")
    for key in ("evaluate_enabled", "explain_enabled", "chlom_packaging_enabled",
                "convergent_preflight_enabled", "provider_writes", "database_writes", "customer_writes"):
        require(api.get(key) is False, f"API/MCP fail-closed drift: {key}")

    chlom = data.get("chlom", {})
    require(chlom.get("registration_state") == "CANDIDATE_UNREGISTERED", "CHLOM registration drift")
    require(chlom.get("supabase_registration_state") == "PLANNED_D1_NOT_APPLIED", "Supabase state drift")
    for key in ("operationally_enabled", "api_enabled", "mcp_enabled", "database_mutation_in_this_packet",
                "raw_private_evidence_body_allowed", "protected_runtime_direct_access"):
        require(chlom.get(key) is False, f"CHLOM fail-closed drift: {key}")
    require("agent_d_parent_certification" in chlom.get("registration_requires", []), "Agent D CHLOM gate missing")

    bridge = data.get("convergent_bridge", {})
    require(bridge.get("state") == "RESEARCH_CANDIDATE", "Convergent state drift")
    for key in ("operationally_enabled", "repository_provisioned", "agent_vote_eligible",
                "protected_runtime_direct_access"):
        require(bridge.get(key) is False, f"Convergent early activation: {key}")
    require("cie_linked_governed" in bridge.get("promotion_requires", []), "CIE predecessor gate missing")

    ip = data.get("ip_publication", {})
    require(ip.get("public_projection_class") == "PUBLIC_STANDARD_CANDIDATE", "IP projection drift")
    require(ip.get("publication_state") == "HOLD_PENDING_ISSUE_131", "IP gate must remain HOLD")
    for key in ("copyright_licensed_material_included", "trade_secret_or_controlled_body_included",
                "patent_candidate_body_included", "restricted_evidence_body_included",
                "credentials_or_fingerprints_included", "customer_output_ready"):
        require(ip.get(key) is False, f"IP publication drift: {key}")

    commercial = data.get("commercialization", {})
    require(commercial.get("commercial_state") == "CANDIDATE", "commercial state drift")
    for key in ("exact_price_authorized", "stripe_product_created", "stripe_price_created",
                "checkout_enabled", "license_grant_active", "certification_status_active",
                "customer_entitlement_active"):
        require(commercial.get(key) is False, f"commercial activation drift: {key}")

    security = data.get("security_operations", {})
    require(security.get("verified_oidc_authority_receipt_count_observed") == 0, "OIDC receipts cannot be inferred")
    require(security.get("this_packet_changes_rls_or_grants") is False, "RLS/grant mutation prohibited")
    require(security.get("this_packet_changes_security_definer_rpc_permissions") is False, "RPC permission mutation prohibited")

    nav = data.get("navigation", {})
    require(nav.get("state") == "CANDIDATE_PATCH_MANIFEST", "navigation state drift")
    require(nav.get("direct_mintlify_dashboard_write") is False, "dashboard write prohibited")
    require(nav.get("docs_json_updated_in_this_packet") is False, "docs navigation cannot be falsely claimed")

def reject(base: dict[str, Any], mutate, label: str) -> None:
    candidate = copy.deepcopy(base)
    mutate(candidate)
    try:
        validate(candidate)
    except ValidationError:
        return
    raise ValidationError(f"negative case unexpectedly accepted: {label}")

def self_test(data: dict[str, Any]) -> None:
    validate(data)
    cases = [
        (lambda d: d["authority"].__setitem__("vote_eligible", True), "vote_enablement"),
        (lambda d: d["authority"].__setitem__("d3_human_reserved", False), "d3_delegation"),
        (lambda d: d["protected_runtime"].__setitem__("implementation_body_public", True), "protected_publication"),
        (lambda d: d["protected_runtime"].__setitem__("missing_runtime_or_digest_disposition", "PASS_CANDIDATE"), "runtime_missing_without_hold"),
        (lambda d: d["chlom"].__setitem__("operationally_enabled", True), "chlom_activation"),
        (lambda d: d["convergent_bridge"].__setitem__("operationally_enabled", True), "convergent_activation"),
        (lambda d: d["api_mcp"].__setitem__("database_writes", True), "database_write"),
        (lambda d: d["commercialization"].__setitem__("checkout_enabled", True), "checkout_activation"),
        (lambda d: d["child_package"].__setitem__("candidate_head_sha", "0"*40), "child_head_drift"),
    ]
    for mutate, label in cases:
        reject(data, mutate, label)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = json.loads((args.root / "developers/manifests/cie-interoperability.v1.json").read_text(encoding="utf-8"))
    self_test(data) if args.self_test else validate(data)
    output = {
        "ok": True,
        "packet_id": data["packet_id"],
        "parent_main": EXPECTED_PARENT,
        "child_head": EXPECTED_CHILD,
        "contract_digest": EXPECTED_DIGEST,
        "factory_state": "CONTROLLED_TEST",
        "repository_state": "PROVISIONED_UNLINKED",
        "operationally_enabled": False,
        "vote_eligible": False,
        "convergent_state": "RESEARCH_CANDIDATE"
    }
    print(json.dumps(output, sort_keys=True) if args.json else "CIE parent interoperability validation PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
