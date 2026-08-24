#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260824011626_cie_production_certification_bridge_v1.sql"
MANIFEST = ROOT / "developers/manifests/cie-production-certification-bridge.v1.json"
DOC = ROOT / "standards/cie-production-certification-bridge.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def require(text: str, values: tuple[str, ...], label: str) -> None:
    missing = [value for value in values if value not in text]
    if missing:
        fail(f"{label} missing invariants: {missing}")


def main() -> int:
    for path in (MIGRATION, MANIFEST, DOC):
        if not path.is_file():
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    migration = MIGRATION.read_text(encoding="utf-8")
    lower = migration.lower()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
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

    # The bridge may translate independent receipts into certification state, but it may not activate production.
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

    # Privileged bridge functions must be service-only and fixed-search-path.
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

    joined = "\n".join((migration, json.dumps(manifest, sort_keys=True), doc))
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
        "service-only reconciliation; no production activation, provider/economic/rights/D3/vote effect."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
