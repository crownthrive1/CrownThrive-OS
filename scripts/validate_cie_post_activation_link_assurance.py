#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260824070356_cie_post_activation_link_assurance_v1.sql"
MANIFEST = ROOT / "developers/manifests/cie-post-activation-link-assurance.v1.json"
DOC = ROOT / "standards/cie-post-activation-link-assurance.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def require(text: str, values: tuple[str, ...], label: str) -> None:
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"{label} missing invariants: {missing}")


def main() -> int:
    for path in (MIGRATION, MANIFEST, DOC):
        if not path.is_file():
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    sql = MIGRATION.read_text(encoding="utf-8")
    lower = sql.lower()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    doc = DOC.read_text(encoding="utf-8")

    if manifest.get("assurance_id") != "ct.assurance.cie.post-activation-link.v1":
        fail("assurance identity drift")
    if manifest.get("canonical_engine_name") != "Cultural Imprint Engine":
        fail("canonical engine name drift")
    if manifest.get("accepted_public_contract_digest") != EXPECTED_DIGEST:
        fail("CIE public contract digest drift")

    prod = manifest.get("production_authority", {})
    if prod.get("required_mode") != "founder_direct":
        fail("post-activation assurance must bind founder_direct production")
    for key in (
        "rewrite_original_authority_snapshot",
        "rewrite_founder_request",
        "rewrite_production_exact_version_ref",
        "rewrite_production_content_sha256",
    ):
        if prod.get(key) is not False:
            fail(f"production authority rewrite prohibited: {key}")

    boundaries = manifest.get("hard_boundaries", {})
    for key, value in boundaries.items():
        if value is not False:
            fail(f"hard boundary expanded: {key}")

    require(sql, (
        "create or replace function chlom_runtime.refresh_cie_parent_child_production_assurance_v1",
        "create or replace function chlom_runtime.cie_post_activation_link_assurance_status_v1",
        "valid_founder_direct_production_receipt_required",
        "production_authority_snapshot_integrity_failure",
        "github_descendant_evidence_required",
        "fresh_exact_repository_observations_required",
        "guardian_binding_not_fail_closed",
        "family_relationship_evidence_missing",
        "interop_parent_child_link_contract_not_registered",
        "'linked_governed'",
        "'production_authority_rewritten',false",
        "'operational_activation',false",
        "'authority_effect',false",
        "'vote_effect',false",
        "'D3_auto',false",
        "PRODUCTION_ACTIVE_CURRENT_LINK_ASSURED",
        EXPECTED_DIGEST,
    ), "migration")

    # This is assurance-only. It must never reactivate, rewrite Founder authority, or enable public/economic state.
    forbidden = (
        "activate_cie_production_v1(",
        "production_authority_request_id'=",
        "production_exact_version_ref'=",
        "production_content_sha256'=",
        "public_activation_allowed=true",
        "commercial_state='active'",
        "checkout_enabled=true",
        "customer_entitlement_active=true",
        "can_vote=true",
        "d3_human_reserved=false",
        "invocation_state='production'",
    )
    for fragment in forbidden:
        if fragment in lower:
            fail(f"forbidden assurance mutation: {fragment}")

    require(lower, (
        "security definer",
        "set search_path = pg_catalog",
        "revoke all on function chlom_runtime.refresh_cie_parent_child_production_assurance_v1",
        "revoke all on function chlom_runtime.cie_post_activation_link_assurance_status_v1",
        "from public,anon,authenticated",
        "grant execute on function chlom_runtime.refresh_cie_parent_child_production_assurance_v1",
        "grant execute on function chlom_runtime.cie_post_activation_link_assurance_status_v1",
        "to service_role",
    ), "access control")

    require(doc, (
        "Cultural Imprint Engine (CIE)",
        "does **not** reactivate CIE",
        "newer Support Git SHA is **not** a new Founder production authorization",
        "PRODUCTION_ACTIVE_CURRENT_LINK_ASSURED",
    ), "documentation")

    joined = "\n".join((sql, json.dumps(manifest, sort_keys=True), doc))
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
        "CIE post-activation link assurance PASS: founder-direct production snapshot preserved; "
        "descendant current-head proof required; current link assurance only; no activation, public, "
        "provider, economic, rights, vote, or D3 effect."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
