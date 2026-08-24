#!/usr/bin/env python3
"""Fail-closed validator for the additive current-head CIE re-anchor."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "developers/manifests/cie-interoperability-reanchor.v2.json"
EXPECTED_PARENT_BASE = "c7f14b73cff09f00a8f94f15a8587289de18ff7b"
EXPECTED_PARENT_PR = 246
EXPECTED_CHILD = "33a218b6ea05feed1c9a22dd5d3f07c36407fec4"
EXPECTED_PREVIOUS_CHILD = "ce2344a72fb0c4ca699c538b9c10593007c65517"
EXPECTED_CHILD_BASE = "073da74bb6eb1fde31b9a6d0321bb85baf5ac8fd"
EXPECTED_CORE = "e337defbe44d74f6c050528cb4fc21c0f20b577f8ceb2480e501479ffca990a3"
EXPECTED_TRANSPORT_BLOB = "d74aa7791d9d4062a45b0ca6214ff0d43a8c537e"
EXPECTED_PROTECTED = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"
EXPECTED_CHILD_RUN = 32594128955
EXPECTED_UNIT_TESTS = 16


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    parent = data["canonical_parent"]
    child = data["child"]
    evidence = data["validation_evidence"]
    binding = data["parent_child_binding"]
    contracts = data["contracts"]
    lifecycle = data["factory_lifecycle"]
    transport = data["transport_invariants"]
    chlom = data["chlom"]
    convergent = data["convergent"]
    ip = data["ip_publication"]
    commercial = data["commercialization"]

    if data.get("manifest_version") != "2.1.0":
        fail("reanchor manifest version drift")
    if data.get("state") != "CURRENT_HEAD_RECONCILIATION_CANDIDATE":
        fail("reanchor state drift")
    if parent.get("base_main_sha") != EXPECTED_PARENT_BASE or parent.get("pr") != EXPECTED_PARENT_PR:
        fail("parent base or PR drift")
    if parent.get("branch") != "agent-c/cie-interoperability-current-main-20260822":
        fail("parent branch drift")
    if parent.get("operational_authority") is not False or parent.get("merge_authority") is not False:
        fail("parent authority must remain false")

    if child.get("current_candidate_head") != EXPECTED_CHILD:
        fail("current child head drift")
    if child.get("previous_candidate_head") != EXPECTED_PREVIOUS_CHILD:
        fail("previous child head lineage drift")
    if child.get("predecessor_candidate_heads") != [
        "4f34f9c2987da347823d06e30d1b142a383973c5",
        EXPECTED_PREVIOUS_CHILD,
    ]:
        fail("child predecessor lineage drift")
    if child.get("base_sha") != EXPECTED_CHILD_BASE or child.get("pr") != 6:
        fail("child base or PR drift")
    if child.get("head_delta_commits") != 9:
        fail("child head delta evidence drift")
    if child.get("repository_state") != "PROVISIONED_UNLINKED":
        fail("child repository state drift")
    if child.get("parent_link_state") != "CANDIDATE_RECONCILED_PENDING_OIDC_ACK_AGENT_D":
        fail("child parent-link state drift")
    if child.get("binding_mode") != "asymmetric_child_parent_identity_parent_exact_child_head":
        fail("child binding mode drift")
    if child.get("operationally_enabled") is not False or child.get("vote_eligible") is not False:
        fail("child authority drift")
    if child.get("ready_for_review") is not False:
        fail("child must remain draft before independent evidence")
    if child.get("exact_head_child_governance") != "PASS_VALIDATION_ONLY":
        fail("child exact-head validation state drift")

    if evidence.get("child_governance_run_id") != EXPECTED_CHILD_RUN:
        fail("child governance run evidence drift")
    if evidence.get("validate_job_conclusion") != "success":
        fail("child validation job is not green")
    if evidence.get("executable_unit_tests_observed") != EXPECTED_UNIT_TESTS:
        fail("child unit-test count drift")
    if evidence.get("unit_test_conclusion") != "success":
        fail("child unit-test gate is not green")
    if evidence.get("pull_request_oidc_authority_received") is not False:
        fail("pull-request validation may not claim OIDC authority")
    if evidence.get("trusted_federation_runtime_job") != "SKIPPED_ON_PULL_REQUEST":
        fail("trusted runtime job boundary drift")
    if evidence.get("certification_effect") is not False or evidence.get("sovereign_vote_effect") is not False:
        fail("validation evidence may not certify or vote")

    expected_binding = {
        "child_records_parent_pr": EXPECTED_PARENT_PR,
        "child_records_parent_branch": "agent-c/cie-interoperability-current-main-20260822",
        "child_records_parent_main_sha": EXPECTED_PARENT_BASE,
        "child_exact_parent_proposal_head_required": False,
        "parent_exact_child_head_required": True,
        "parent_exact_child_head": EXPECTED_CHILD,
        "current_head_oidc_ack_state": "PENDING",
        "agent_d_parent_certification_state": "PENDING",
        "authorization_effect": False,
    }
    for key, value in expected_binding.items():
        if binding.get(key) != value:
            fail(f"parent-child binding drift: {key}")

    if contracts.get("core_semantic_digest_sha256") != EXPECTED_CORE:
        fail("core semantic digest drift")
    if contracts.get("transport_blob_sha") != EXPECTED_TRANSPORT_BLOB:
        fail("transport contract blob drift")
    if contracts.get("protected_public_contract_digest") != EXPECTED_PROTECTED:
        fail("protected digest drift")
    if contracts.get("transport_deployment_state") != "NOT_DEPLOYED":
        fail("transport may not claim deployment")
    if contracts.get("public_safe_preflight_success_disposition") != "HOLD_PRIVATE_RUNTIME_NOT_INVOKED":
        fail("public preflight must remain HOLD")
    if contracts.get("protected_runtime_invoked_by_preflight") is not False:
        fail("public preflight may not invoke protected runtime")

    for key in ("provider_write_allowed", "database_write_allowed", "credential_operation_allowed", "rights_legal_financial_decision_allowed", "money_movement_allowed"):
        if transport.get(key) is not False:
            fail(f"transport authority drift: {key}")

    if lifecycle.get("package_state") != "CONTROLLED_TEST":
        fail("factory lifecycle drift")
    if lifecycle.get("parent_agent_state") != "PREPARED_NOT_ACTIVATED":
        fail("parent agent state drift")
    if lifecycle.get("vote_eligible") is not False or lifecycle.get("d3_human_reserved") is not True:
        fail("framework authority drift")
    if lifecycle.get("mandatory_parent_certifier") != "ct.relay.agent-d":
        fail("Agent D is no longer mandatory")
    if lifecycle.get("parent_certification_state") != "PENDING":
        fail("parent certification may not be inferred")
    if lifecycle.get("verified_oidc_authority_receipts_observed") != 0:
        fail("OIDC authority receipt count drift")
    if lifecycle.get("next_framework_state") != "RESEARCH_CANDIDATE":
        fail("Convergent may not be promoted")

    if chlom.get("registration_state") != "CANDIDATE_UNREGISTERED" or chlom.get("operationally_enabled") is not False or chlom.get("database_mutation_in_this_packet") is not False:
        fail("CHLOM boundary drift")
    if convergent.get("state") != "RESEARCH_CANDIDATE" or convergent.get("implementation_allowed") is not False or convergent.get("operationally_enabled") is not False:
        fail("Convergent boundary drift")
    if ip.get("publication_state") != "HOLD_PENDING_ISSUE_131" or ip.get("customer_output_ready") is not False:
        fail("IP/publication boundary drift")
    for key in ("exact_price_authorized", "stripe_product_created", "stripe_price_created", "checkout_enabled", "license_grant_active", "certification_status_active", "customer_entitlement_active"):
        if commercial.get(key) is not False:
            fail(f"commercial activation drift: {key}")

    text = PATH.read_text(encoding="utf-8")
    for pattern in (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", r"\bsb_secret_[A-Za-z0-9_-]{16,}\b", r"\bsk-[A-Za-z0-9]{20,}\b"):
        if re.search(pattern, text):
            fail("credential-shaped value detected")

    print(
        "CIE current-head reanchor validation PASS: "
        f"parent={EXPECTED_PARENT_BASE}; child={EXPECTED_CHILD}; "
        f"child-tests={EXPECTED_UNIT_TESTS}; non-operational; non-voting; "
        "Agent-D pending; OIDC=0; CHLOM unregistered; Convergent research-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
