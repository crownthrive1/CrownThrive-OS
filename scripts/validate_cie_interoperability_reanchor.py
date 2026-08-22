#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

EXPECTED_CHILD = "ce2344a72fb0c4ca699c538b9c10593007c65517"
EXPECTED_CORE = "e337defbe44d74f6c050528cb4fc21c0f20b577f8ceb2480e501479ffca990a3"
EXPECTED_TRANSPORT_BLOB = "d74aa7791d9d4062a45b0ca6214ff0d43a8c537e"
EXPECTED_MAIN = "c7f14b73cff09f00a8f94f15a8587289de18ff7b"

def req(cond: bool, msg: str):
    if not cond:
        raise SystemExit(f"ERROR: {msg}")

def main() -> int:
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "developers/manifests/cie-interoperability-reanchor.v2.json").read_text())
    req(data["canonical_parent"]["base_main_sha"] == EXPECTED_MAIN, "parent main drift")
    child = data["child"]
    req(child["current_candidate_head"] == EXPECTED_CHILD, "child head drift")
    req(child["repository_state"] == "PROVISIONED_UNLINKED", "repository state drift")
    req(child["operationally_enabled"] is False and child["vote_eligible"] is False, "child activation/vote drift")
    req(child["exact_head_child_governance"] == "PASS", "child exact-head governance not passed")
    contracts = data["contracts"]
    req(contracts["core_semantic_digest_sha256"] == EXPECTED_CORE, "core digest drift")
    req(contracts["transport_blob_sha"] == EXPECTED_TRANSPORT_BLOB, "transport artifact drift")
    req(contracts["transport_deployment_state"] == "NOT_DEPLOYED", "transport deployment drift")
    req(contracts["protected_runtime_invoked_by_preflight"] is False, "protected runtime invocation drift")
    inv = data["transport_invariants"]
    for key in ("provider_write_allowed","database_write_allowed","credential_operation_allowed","rights_legal_financial_decision_allowed","money_movement_allowed"):
        req(inv[key] is False, f"transport authority drift: {key}")
    req(inv["person_scoring_disposition"] == "BLOCK", "person scoring must block")
    req(inv["sensitive_trait_inference_disposition"] == "BLOCK", "sensitive trait inference must block")
    life = data["factory_lifecycle"]
    req(life["package_state"] == "CONTROLLED_TEST", "package state drift")
    req(life["parent_agent_state"] == "PREPARED_NOT_ACTIVATED", "agent state drift")
    req(life["mandatory_parent_certifier"] == "ct.relay.agent-d", "Agent D gate drift")
    req(life["parent_certification_state"] == "PENDING", "certification inferred")
    req(life["verified_oidc_authority_receipts_observed"] == 0, "OIDC authority inferred")
    req(data["chlom"]["registration_state"] == "CANDIDATE_UNREGISTERED", "CHLOM premature registration")
    req(data["chlom"]["database_mutation_in_this_packet"] is False, "CHLOM database mutation drift")
    req(data["convergent"]["state"] == "RESEARCH_CANDIDATE", "Convergent state drift")
    req(data["convergent"]["implementation_allowed"] is False and data["convergent"]["operationally_enabled"] is False, "Convergent premature activation")
    req(data["ip_publication"]["publication_state"] == "HOLD_PENDING_ISSUE_131", "IP gate drift")
    for key in ("exact_price_authorized","stripe_product_created","stripe_price_created","checkout_enabled","license_grant_active","certification_status_active","customer_entitlement_active"):
        req(data["commercialization"][key] is False, f"commercial activation drift: {key}")
    print("CIE re-anchor validation PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
