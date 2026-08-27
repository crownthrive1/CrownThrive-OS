#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migration_lineage/legacy_local_timestamp_drift/local_only_versions/20260824070356_cie_post_activation_link_assurance_v1.sql"
MANIFEST = ROOT / "developers/manifests/cie-post-activation-link-assurance.v1.json"
LIVE_RECEIPT = ROOT / "developers/manifests/cie-post-activation-link-assurance-live-receipt-20260824.v1.json"
DOC = ROOT / "standards/cie-post-activation-link-assurance.md"
EXPECTED_DIGEST = "e5e6ac0e9cf6749ba361435bb65ad212f78562960d0b5522898e06583b8d86c2"


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def require(text: str, values: tuple[str, ...], label: str) -> None:
    missing = [v for v in values if v not in text]
    if missing:
        fail(f"{label} missing invariants: {missing}")


def require_false_map(value: object, label: str) -> None:
    if not isinstance(value, dict) or not value:
        fail(f"{label} must be a non-empty object")
    for key, flag in value.items():
        if flag is not False:
            fail(f"{label} expanded: {key}")


def main() -> int:
    for path in (MIGRATION, MANIFEST, LIVE_RECEIPT, DOC):
        if not path.is_file():
            fail(f"missing artifact: {path.relative_to(ROOT)}")

    sql = MIGRATION.read_text(encoding="utf-8")
    lower = sql.lower()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = json.loads(LIVE_RECEIPT.read_text(encoding="utf-8"))
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

    require_false_map(manifest.get("hard_boundaries"), "manifest hard boundary")

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

    # Live receipt is historical evidence from the pre-merge test snapshot, never reusable authority.
    if live.get("assurance_id") != manifest.get("assurance_id"):
        fail("live receipt assurance identity mismatch")
    if live.get("canonical_engine_name") != "Cultural Imprint Engine":
        fail("live receipt engine identity drift")
    if live.get("evidence_class") != "historical_live_readback_not_reusable_authority":
        fail("live receipt must be explicitly historical/non-reusable")
    if live.get("source_head_before_apply") != "40b72186fd09afb65117d1ca85d258294af22aab":
        fail("live receipt source head drift")
    db = live.get("database_migration", {})
    if db.get("source_file_version") != "20260824070356" or db.get("applied_version") != "20260824070845" or db.get("apply_state") != "success":
        fail("live database migration evidence drift")

    original = live.get("original_production_authority", {})
    if original.get("authority_mode") != "founder_direct":
        fail("live receipt must retain founder_direct authority")
    if original.get("activation_receipt_id") != "8b638a18-81e8-4f4a-b6c2-d54340d61d36":
        fail("live receipt activation receipt drift")
    if original.get("founder_request_id") != "8af419dd-5bdd-4f5e-be72-a8b9bc73b8ad":
        fail("live receipt Founder request drift")
    if original.get("authority_snapshot_rewritten") is not False:
        fail("live receipt may not rewrite production authority")
    if original.get("protected_canary_verdict") != "PASS" or original.get("protected_canary_score") != "100.00":
        fail("live receipt protected canary evidence drift")
    if original.get("rollback_state") != "ready":
        fail("live receipt rollback readiness drift")

    compare = live.get("github_descendant_evidence", {})
    if compare.get("status") != "ahead" or compare.get("ahead_by") != 386 or compare.get("behind_by") != 0:
        fail("live receipt descendant evidence drift")
    if compare.get("base_sha") != original.get("activation_parent_head"):
        fail("live receipt comparison must start at activation parent")
    if compare.get("head_sha") != live.get("source_base_support_main"):
        fail("live receipt comparison head must match tested Support main")

    assurance = live.get("live_assurance", {})
    if assurance.get("state") != "PRODUCTION_ACTIVE_CURRENT_LINK_ASSURED":
        fail("live assurance status did not pass")
    if assurance.get("refresh_result") != "LINKED_GOVERNED_POST_ACTIVATION_ASSURANCE":
        fail("live assurance refresh result drift")
    if assurance.get("link_state") != "linked_governed":
        fail("live assurance link state drift")
    for key in ("guardian_verified", "family_verified", "interoperability_verified"):
        if assurance.get(key) is not True:
            fail(f"live assurance missing verification: {key}")
    if assurance.get("production_authority_rewritten") is not False:
        fail("live assurance rewrote production authority")

    post = live.get("post_refresh_state", {})
    if post.get("package_state") != "maintained" or post.get("repository_state") != "linked_governed" or post.get("algorithm_invocation_state") != "production_limited":
        fail("post-refresh bounded production state drift")
    if post.get("operationally_enabled") is not True or post.get("public_activation_allowed") is not False:
        fail("post-refresh operational/public boundary drift")
    if post.get("commercial_state") != "hold" or post.get("can_vote") is not False or post.get("d3_human_reserved") is not True:
        fail("post-refresh commerce/vote/D3 boundary drift")
    for key in (
        "production_parent_head_unchanged",
        "production_child_head_unchanged",
        "production_exact_version_ref_unchanged",
        "production_content_sha256_unchanged",
        "production_authority_request_id_unchanged",
        "production_activation_receipt_unchanged",
    ):
        if post.get(key) is not True:
            fail(f"post-refresh authority snapshot changed: {key}")

    require_false_map(live.get("hard_boundaries"), "live receipt hard boundary")
    if "not authority" not in str(live.get("reuse_rule", "")).lower() or "must not be reused" not in str(live.get("reuse_rule", "")).lower():
        fail("live receipt reuse rule must prohibit authority/reuse")

    joined = "\n".join((sql, json.dumps(manifest, sort_keys=True), json.dumps(live, sort_keys=True), doc))
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
        "descendant current-head proof required; historical live receipt non-reusable; current link "
        "assurance only; no activation, public, provider, economic, rights, vote, or D3 effect."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
