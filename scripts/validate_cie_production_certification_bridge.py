#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migration_lineage/legacy_local_timestamp_drift/local_only_versions/20260824011626_cie_production_certification_bridge_v1.sql"
MANIFEST = ROOT / "developers/manifests/cie-production-certification-bridge.v1.json"
LIVE_RECEIPT = ROOT / "developers/manifests/cie-production-certification-bridge-live-receipt-20260823.v1.json"
DOC = ROOT / "standards/cie-production-certification-bridge.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require(text: str, values: tuple[str, ...], label: str) -> None:
    missing = [value for value in values if value not in text]
    if missing:
        fail(f"{label} missing invariants: {missing}")


def main() -> int:
    for path in (MIGRATION, MANIFEST, LIVE_RECEIPT, DOC):
        if not path.is_file():
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    migration = MIGRATION.read_text(encoding="utf-8")
    lower = migration.lower()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    receipt = json.loads(LIVE_RECEIPT.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")

    if manifest.get("bridge_id") != "ct.bridge.cie.production-certification.v1":
        fail("bridge identity drift")
    if manifest.get("framework_id") != "ct.framework.cultural-imprint-engine":
        fail("framework identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine":
        fail("canonical engine name drift")
    if manifest.get("accepted_public_contract_digest") != EXPECTED_DIGEST:
        fail("accepted contract digest drift")

    authority = manifest.get("authority_model", {})
    required_false = (
        "originator_may_certify",
        "service_role_may_manufacture_verifier_disposition",
        "vote_effect",
        "provider_write_effect",
        "economic_effect",
        "rights_effect",
        "production_activation_effect",
    )
    for key in required_false:
        if authority.get(key) is not False:
            fail(f"authority expansion: {key}")
    if authority.get("agent_d_resolution_required") is not True:
        fail("Agent D resolution must be required")
    if authority.get("agent_d_certification_exact_snapshot_bound") is not True:
        fail("Agent D certification must be exact-snapshot bound")
    if authority.get("lifecycle_verifier") != "ct.gen7.agent-q":
        fail("lifecycle verifier drift")
    if authority.get("semantic_evidence_required") is not True or authority.get("security_evidence_required") is not True:
        fail("independent semantic/security evidence must remain required")
    if authority.get("d3_human_reserved") is not True:
        fail("D3 reservation drift")

    require(
        migration,
        (
            "create or replace function chlom_runtime.cie_parent_certification_reconcile_v1",
            "resolved_independent_agent_d_issue_required",
            "exact_agent_d_resolution_event_required",
            "agent_d_resolution_missing_exact_evidence",
            "actor_agent_id='ct.relay.agent-d'",
            "parent_certification_state='certified'",
            "parent_certification_child_head",
            "parent_certification_parent_head",
            "parent_certification_link_receipt_id",
            "parent_certification_event_id",
            "cie.parent_certification.reconciled",
            "create or replace function chlom_runtime.cie_wave4_activation_evidence_gate_v1",
            "parent_certified_exact_snapshot",
            "HOLD_PARENT_CERTIFICATION_PENDING_OR_STALE",
            "create or replace function chlom_runtime.cie_lifecycle_release_reconcile_v1",
            "resolved_independent_lifecycle_verifier_issue_required",
            "actor_agent_id='ct.gen7.agent-q'",
            "independent_semantic_and_security_evidence_required",
            "lifecycle_resolution_missing_exact_independent_evidence",
            "platform_key='cie' and dimension='lifecycle_release'",
            "cie.lifecycle_release.reconciled",
            "create or replace function chlom_runtime.cie_production_certification_bridge_status_v1",
            "CERTIFICATION_BRIDGE_READY_NON_ACTIVATING",
            "activation_authorized',false",
            "operational_activation',false",
            "vote_effect',false",
            "D3_auto',false",
            EXPECTED_DIGEST,
        ),
        "migration",
    )

    forbidden_activation_fragments = (
        "activate_cie_production_v1(",
        "package_state='maintained'",
        "operationally_enabled=true",
        "public_activation_allowed=true",
        "invocation_state='production_limited'",
        "checkout_enabled=true",
        "customer_entitlement_active=true",
        "can_vote=true",
        "d3_human_reserved=false",
    )
    for fragment in forbidden_activation_fragments:
        if fragment in lower:
            fail(f"bridge contains forbidden activation fragment: {fragment}")

    require(
        lower,
        (
            "security definer",
            "set search_path = pg_catalog",
            "revoke execute on function chlom_runtime.cie_parent_certification_reconcile_v1",
            "revoke execute on function chlom_runtime.cie_lifecycle_release_reconcile_v1",
            "revoke execute on function chlom_runtime.cie_production_certification_bridge_status_v1",
            "from public, anon, authenticated",
            "grant execute on function chlom_runtime.cie_parent_certification_reconcile_v1",
            "grant execute on function chlom_runtime.cie_lifecycle_release_reconcile_v1",
            "grant execute on function chlom_runtime.cie_production_certification_bridge_status_v1",
            "to service_role",
        ),
        "access control",
    )

    require(
        doc,
        (
            "Cultural Imprint Engine",
            "It is deliberately **not** an activation function.",
            "Stale certification is invalid",
            "semantic-evidence reference",
            "security-evidence reference",
            "Silence is never authority.",
        ),
        "documentation",
    )

    if receipt.get("receipt_class") != "LIVE_CONTROLLED_TEST_EVIDENCE_NOT_REUSABLE_AUTHORITY":
        fail("live receipt classification drift")
    if receipt.get("framework_id") != "ct.framework.cultural-imprint-engine" or receipt.get("canonical_engine_name") != "Cultural Imprint Engine":
        fail("live receipt CIE identity drift")
    if receipt.get("bridge_id") != "ct.bridge.cie.production-certification.v1":
        fail("live receipt bridge identity drift")
    source = receipt.get("source", {})
    if source.get("source_ci_head_before_live_apply") != "a693d15eec82c83b84aeffe501f4b733f190cf6b":
        fail("live receipt source CI head drift")
    if not source.get("source_ci") or any(value != "success" for value in source["source_ci"].values()):
        fail("live receipt source CI not all success")
    thrivebase = receipt.get("thrivebase", {})
    if thrivebase.get("migration_name") != "cie_production_certification_bridge_v1" or thrivebase.get("apply_state") != "success":
        fail("live migration receipt drift")
    if not re.fullmatch(r"\d{14}", str(thrivebase.get("migration_version", ""))):
        fail("live migration version shape invalid")
    acl = thrivebase.get("acl_readback", {})
    for key in ("security_definer", "pinned_search_path", "postgres_execute", "service_role_execute"):
        if acl.get(key) is not True:
            fail(f"live ACL expected true: {key}")
    for key in ("public_execute", "anon_execute", "authenticated_execute"):
        if acl.get(key) is not False:
            fail(f"live ACL exposure drift: {key}")
    snapshot = receipt.get("exact_test_snapshot", {})
    if snapshot.get("accepted_public_contract_digest") != EXPECTED_DIGEST:
        fail("live receipt contract digest drift")
    for key in ("guardian_verified", "family_verified", "interoperability_verified"):
        if snapshot.get(key) is not True:
            fail(f"live exact link verification missing: {key}")
    for key in ("technical_link_authority_effect", "technical_link_operational_activation", "technical_link_vote_effect"):
        if snapshot.get(key) is not False:
            fail(f"live link authority expansion: {key}")
    status = receipt.get("live_status_readback", {})
    if status.get("bridge_state") != "HOLD_AGENT_D_EXACT_CERTIFICATION":
        fail("live bridge must remain on Agent D HOLD")
    if status.get("source_integration_state") != "SOURCE_INTEGRATION_READY":
        fail("live source integration state drift")
    if status.get("parent_certification_state") != "pending" or status.get("parent_certified_exact_snapshot") is not False:
        fail("live parent certification must remain pending")
    if status.get("lifecycle_release_state") != "pending":
        fail("live lifecycle release must remain pending")
    for key in ("activation_authorized", "operational_activation", "provider_write_effect", "economic_effect", "rights_effect", "vote_effect", "D3_auto"):
        if status.get(key) is not False:
            fail(f"live receipt authority expansion: {key}")
    tests = {item.get("observed_error"): item for item in receipt.get("negative_tests", [])}
    for expected_error in ("resolved_independent_agent_d_issue_required", "exact_parent_certification_required_before_lifecycle_release"):
        item = tests.get(expected_error)
        if not item or item.get("result") != "PASS_FAIL_CLOSED" or item.get("state_mutation") is not False:
            fail(f"missing fail-closed live negative test: {expected_error}")
    package = receipt.get("post_test_package_state", {})
    if package.get("package_state") != "controlled_test" or package.get("parent_certification_state") != "pending":
        fail("post-test package state drift")
    for key in ("operationally_enabled", "public_activation_allowed", "can_vote", "exact_price_authorized", "checkout_enabled", "customer_entitlement_active"):
        if package.get(key) is not False:
            fail(f"post-test package authority expansion: {key}")
    if package.get("d3_human_reserved") is not True:
        fail("post-test D3 reservation drift")
    semantics = receipt.get("snapshot_semantics", {})
    if semantics.get("historical_evidence_only") is not True or semantics.get("not_reusable_authority") is not True:
        fail("live receipt must be historical non-reusable evidence")
    if semantics.get("repository_head_changes_require_new_exact_link_and_new_independent_resolution") is not True:
        fail("head-change recertification invariant missing")
    for key in ("founder_override_inferred", "founder_ratification_inferred", "silence_is_authority"):
        if semantics.get(key) is not False:
            fail(f"founder authority inference drift: {key}")

    joined = "\n".join((migration, json.dumps(manifest, sort_keys=True), json.dumps(receipt, sort_keys=True), doc))
    credential_patterns = (
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bsb_secret_[A-Za-z0-9_-]{16,}\b",
        r"\bsk-[A-Za-z0-9]{20,}\b",
        r"\bmint_[A-Za-z0-9_-]{16,}\b",
        r"BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY",
    )
    for pattern in credential_patterns:
        if re.search(pattern, joined):
            fail("credential-shaped value detected")

    print(
        "CIE production certification bridge PASS: exact-snapshot Agent D receipt translation; "
        "stale certification invalidation; independent lifecycle semantic/security evidence; "
        "live fail-closed receipt; service-only reconciliation; no production activation, "
        "provider/economic/rights/D3/vote effect."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
