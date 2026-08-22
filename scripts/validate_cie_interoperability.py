#!/usr/bin/env python3
"""Validate the public-safe CIE interoperability parent packet.

This validator is evidence only. It cannot certify a framework, activate a runtime,
create a sovereign vote, mutate providers/databases, or advance Phase 3.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"
CHILD_HEAD = "439b3a51f9979be2b8227e3ad553f83b297b3bd2"
PARENT_MAIN_AT_BUILD = "c7f14b73cff09f00a8f94f15a8587289de18ff7b"

FILES = {
    "cie": ROOT / "developers/manifests/cie-interoperability.v1.json",
    "handoff": ROOT / "developers/manifests/cie-convergent-handoff.v1.json",
    "chlom": ROOT / "developers/manifests/cie-chlom-pallet-interface.v1.json",
    "commercial": ROOT / "developers/manifests/cie-commercialization-candidates.v1.json",
}

CREDENTIAL_PATTERNS = (
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
    r"\bsk-[A-Za-z0-9]{20,}\b",
)
FORBIDDEN_TEXT = (
    '"framework_agent_vote_eligible": true',
    '"subagents_vote_eligible": true',
    '"transport_identities_vote_eligible": true',
    '"operationally_enabled": true',
    '"protected_runtime_dispatch_enabled": true',
    '"database_mutation_enabled": true',
    '"provider_mutation_enabled": true',
    '"checkout_enabled": true',
    '"exact_price_authorized": true',
    '"certification_status_active": true',
    '"customer_entitlement_active": true',
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"object required: {path}")
    return value


def expect(obj: dict, expected: dict, label: str) -> None:
    for key, value in expected.items():
        if obj.get(key) != value:
            fail(f"{label}.{key}: expected {value!r}, got {obj.get(key)!r}")


def require_false(obj: dict, keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if obj.get(key) is not False:
            fail(f"{label}.{key} must remain false")


def main() -> int:
    for path in FILES.values():
        if not path.is_file():
            fail(f"missing packet file: {path.relative_to(ROOT)}")

    cie = load(FILES["cie"])
    expect(
        cie,
        {
            "framework_id": "ct.framework.cultural-imprint-engine",
            "package_id": "ct.framework-package.cie",
            "framework_agent_id": "ct.framework-agent.cie",
            "factory_order": 1,
            "factory_lifecycle_state": "CONTROLLED_TEST_PROVISIONED_UNLINKED",
            "proposal_state": "DRAFT_NOT_ACCEPTED",
        },
        "cie",
    )
    parent = cie.get("canonical_parent", {})
    expect(
        parent,
        {
            "main_sha_at_build": PARENT_MAIN_AT_BUILD,
            "main_sha_is_authorization": False,
            "branch_protection_observed": False,
            "reconcile_again_before_promotion": True,
        },
        "canonical_parent",
    )
    child = cie.get("child_repository", {})
    expect(
        child,
        {
            "repository": "crownthrive1/CrownThrive-CIE",
            "repository_id": 1341314455,
            "proposal_pr": 2,
            "proposal_head_sha": CHILD_HEAD,
            "governance_state": "PROVISIONED_UNLINKED",
            "operationally_enabled": False,
            "vote_eligible": False,
            "parent_certification_state": "pending",
            "current_head_oidc_bootstrap_state": "pending",
            "current_head_backlink_ack_state": "pending",
        },
        "child_repository",
    )
    authority = cie.get("authority", {})
    expect(
        authority,
        {
            "required_approvals": 4,
            "agent_d_mandatory": True,
            "no_deny_or_block": True,
            "d3_human_reserved": True,
            "builder_may_self_verify": False,
            "builder_may_self_approve": False,
        },
        "authority",
    )
    require_false(
        authority,
        (
            "framework_agent_vote_eligible",
            "subagents_vote_eligible",
            "transport_identities_vote_eligible",
            "builder_may_self_verify",
            "builder_may_self_approve",
        ),
        "authority",
    )
    interop = cie.get("interoperability", {})
    expect(interop, {"state": "CONTRACT_VALIDATION_ONLY"}, "interoperability")
    require_false(
        interop,
        (
            "protected_runtime_dispatch_enabled",
            "provider_mutation_enabled",
            "database_mutation_enabled",
            "customer_mutation_enabled",
        ),
        "interoperability",
    )
    protected = cie.get("protected_algorithm", {})
    expect(
        protected,
        {
            "algorithm_id": "ct.algorithm.cie.v1",
            "algorithm_version": "1.0.1",
            "public_contract_digest": DIGEST,
            "public_implementation_reachable": False,
            "public_repository_contains_calibration": False,
            "public_repository_contains_private_evals": False,
            "missing_runtime_or_digest": "HOLD",
        },
        "protected_algorithm",
    )

    handoff = load(FILES["handoff"])
    expect(
        handoff,
        {
            "source_framework_id": "ct.framework.cultural-imprint-engine",
            "source_lifecycle_state": "CONTROLLED_TEST_PROVISIONED_UNLINKED",
            "target_framework_id": "ct.framework.convergent-ecosystem",
            "target_lifecycle_state": "RESEARCH_CANDIDATE_SOURCE_DISCOVERY",
            "handoff_state": "PREPARED_FAIL_CLOSED_NOT_EXECUTABLE",
            "handoff_execution_enabled": False,
            "target_operationally_enabled": False,
            "target_vote_eligible": False,
            "target_repository_provisioned": False,
            "target_parent_agent_activated": False,
            "runtime_effect": "NONE",
            "provider_effect": "NONE",
            "database_effect": "NONE",
            "sovereign_vote_effect": False,
            "current_result": "HOLD_TARGET_FRAMEWORK_NOT_ACCEPTED",
        },
        "handoff",
    )

    chlom = load(FILES["chlom"])
    expect(
        chlom,
        {
            "pallet_id": "ct.chlom.pallet.cie-cultural-governance",
            "lifecycle_state": "CONTRACT_VALIDATION_ONLY",
            "security_state": "HOLD_PENDING_INDEPENDENT_REVIEW",
            "private_runtime_material_in_public_manifest": False,
            "credentials_in_public_manifest": False,
            "private_fingerprints_in_public_manifest": False,
            "sovereign_vote_effect": False,
        },
        "chlom",
    )
    write_state = chlom.get("write_state", {})
    require_false(
        write_state,
        (
            "database_write_enabled",
            "provider_write_enabled",
            "customer_write_enabled",
            "public_or_generic_client_write_authority",
        ),
        "chlom.write_state",
    )
    if write_state.get("service_only_authority_required") is not True:
        fail("CHLOM service-only authority must remain required")
    if write_state.get("current_result") != "HOLD_CHLOM_WRITE_NOT_AUTHORIZED":
        fail("CHLOM write must remain HOLD")

    commercial = load(FILES["commercial"])
    expect(commercial, {"commercial_lifecycle_state": "CANDIDATE_ONLY"}, "commercial")
    require_false(
        commercial.get("activation_state", {}),
        (
            "exact_price_authorized",
            "stripe_product_created",
            "stripe_price_created",
            "checkout_enabled",
            "license_grant_active",
            "certification_status_active",
            "customer_entitlement_active",
            "customer_fulfillment_active",
        ),
        "commercial.activation_state",
    )

    combined = "\n".join(path.read_text(encoding="utf-8") for path in FILES.values())
    for text in FORBIDDEN_TEXT:
        if text in combined:
            fail(f"forbidden activation fragment: {text}")
    for pattern in CREDENTIAL_PATTERNS:
        if re.search(pattern, combined):
            fail("credential-shaped value detected")

    doctrine = (ROOT / "doctrine/cultural-imprint-engine.mdx").read_text(encoding="utf-8")
    convergent = (ROOT / "doctrine/convergent-ecosystem.mdx").read_text(encoding="utf-8")
    changelog = (ROOT / "changelog/phase-2-99-cie-interoperability-precert.mdx").read_text(encoding="utf-8")
    required_docs = (
        (doctrine, "PROVISIONED_UNLINKED"),
        (doctrine, "HOLD_PROTECTED_RUNTIME_UNAVAILABLE"),
        (convergent, "RESEARCH_CANDIDATE_SOURCE_DISCOVERY"),
        (convergent, "HOLD_TARGET_FRAMEWORK_NOT_ACCEPTED"),
        (changelog, CHILD_HEAD),
        (changelog, PARENT_MAIN_AT_BUILD),
    )
    for text, marker in required_docs:
        if marker not in text:
            fail(f"documentation marker missing: {marker}")

    print(
        "CIE interoperability parent packet PASS: public-safe contract validation only; "
        "CIE non-operational/non-voting; Convergent research-only; CHLOM writes HOLD; commerce candidate-only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
