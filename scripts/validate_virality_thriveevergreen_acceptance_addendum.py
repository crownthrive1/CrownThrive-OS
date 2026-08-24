#!/usr/bin/env python3
"""Validate the public-safe Virality Music × ThriveEvergreen acceptance record.

This validator performs no network, provider, wallet, ledger, entitlement,
publication, Drive, or other economic mutation. It cross-checks the acceptance
record against the committed product reconciliation and fail-closed authority
invariants.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.acceptance-addendum.v1.json"
PRODUCTS = ROOT / "developers/manifests/virality-thriveevergreen-product-reconciliation.2026-08-24.v1.json"
ATTACHMENTS = ROOT / "developers/manifests/virality-attached-masters-reconciliation.2026-08-24.v1.json"
AUTHORITY_PROJECTION = ROOT / "developers/manifests/virality-thriveevergreen-authority-readiness-projection.2026-08-24.v1.json"
INTEGRATION_RECORD = ROOT / "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.v1.json"
CUSTODY_RECEIPT = ROOT / "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.drive-custody-receipt.v1.json"
RUNTIME_SUPERSESSION = ROOT / "developers/certification/thriveevergreen-production-fabric-runtime-v1-1-supersession-2026-08-24.v1.json"
EDGE_CANDIDATE_STATE = ROOT / "developers/candidates/supabase/virality-commerce-control-v1.1.2/candidate-state.json"
EDGE_CANDIDATE_DIR = EDGE_CANDIDATE_STATE.parent
CANONICAL_EDGE_SOURCE = ROOT / "developers/supabase/functions/virality-commerce-control/index.ts"
CANONICAL_RUNTIME = ROOT / "developers/scripts/thriveevergreen/production-fabric-runtime.v1.1.ts"
CANONICAL_CONTRACT = ROOT / "developers/contracts/thriveevergreen/production-fabric.contracts.v1.1.schema.json"
POLICY_REDUCER_RUNTIME = ROOT / "developers/scripts/thriveevergreen/production-fabric-policy-reducer.v1.1.ts"
POLICY_REDUCER_CONTRACT = ROOT / "developers/contracts/thriveevergreen/production-fabric-policy-reducer.contracts.v1.1.json"
POLICY_REDUCER_TEST = ROOT / "developers/scripts/thriveevergreen/production-fabric-policy-reducer.v1.1.test.ts"
MANAGED_WALLET_ACCEPTANCE_CONTRACT = ROOT / "developers/contracts/commerce-control-acceptance-addendum.v1.json"
MANAGED_WALLET_DOCUMENTATION = ROOT / "commerce/chlom-managed-agent-wallet-base-usdc.mdx"
MANAGED_WALLET_CERTIFICATION = ROOT / "developers/certification/chlom-managed-agent-wallet-and-acceptance-2026-08-24.mdx"
FABRIC_SOURCE_HEAD = "402ae2e2f35536adf0cca1979594067c8f7ed7e6"
SUPPORT_INITIAL_BASE_HEAD = "936acfc64990d9bad11c8a4ed1e6bef7ce81c283"
SUPPORT_CIE_ASSURANCE_MAIN_HEAD = "8f9b9c715bea21221f5952c3853df51efc62387f"
SUPPORT_ECONOMIC_CONTROL_FORWARD_MAIN_HEAD = "e05400a55158818ffc4b7c70eeaf68211726615a"
SUPPORT_AGENT_WALLET_PACKAGE_CERTIFICATION_HEAD = "1cac8cdb0b8da58ad7a01efaa972d589beac581e"
SUPPORT_MANAGED_WALLET_CERTIFICATION_COMMIT = "8794b34ea5aa183b73bcb4960d21bd95c5d43b94"
SUPPORT_LATEST_MAIN_HEAD = "2a0aacd7d326b6837b7ba1b85c4228550724d178"
SUPPORT_MANAGED_WALLET_ACCEPTANCE_COMMIT = "de917a8a7f11541722cbf6d2da8166ff648962a4"
SUPPORT_MANAGED_WALLET_DOCUMENTATION_COMMIT = "e54b54267e25427d54642860a9dcbaeb50ae7bc1"
SUPPORT_COLLISION_HEAD = "58ef7524bae7d2dfcea6573db500c6becd4ef8ff"
SUPPORT_INITIAL_CUSTODY_HEAD = "009aa96fddb363d1e16f06cd24eaea47f63b793c"
SUPPORT_CORRECTION_HEAD = "8171982db8b024fef55bc671a3465fdc21f02f27"
SUPPORT_PULL_REQUEST = 349
NATIVE_STAGED_COMMIT = "74976d22ffc04ec8071533ad9d5ce1b0d292353c"
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
GIT_SHA_RE = re.compile(r"^[a-f0-9]{40}$")
ACCEPTANCE_ROOT_KEYS = frozenset({
    "api_mcp_tool_states",
    "authority",
    "automation",
    "canonical_integration_record",
    "classification",
    "constitutional_rule",
    "institutionalization",
    "latest_receipts",
    "observed_window_utc",
    "overall_decision",
    "planes",
    "product_reconciliation",
    "record_id",
    "recorded_at",
    "release_authorized",
    "remaining_human_or_provider_gates",
    "schema",
    "schema_version",
    "security_verification",
    "source_attachment_evidence",
    "source_binding",
})
AUTHORITY_KEYS = frozenset({
    "d3_human_reserved",
    "economic_activation_performed_by_this_record",
    "economic_decisions",
    "economic_provider_mutation_performed_by_this_record",
    "non_economic_provider_or_control_plane_mutation_observed_in_bound_execution_lineage",
    "record_itself_performs_provider_mutation",
    "provider_success_can_manufacture_authority",
    "provider_success_is_evidence_only",
    "publication_activation_performed_by_this_record",
    "wallet_or_signing_mutation_performed_by_this_record",
})
SOURCE_BINDING_KEYS = frozenset({
    "immutable_fabric_source_head",
    "native_vm_latest_source_before_staging",
    "native_vm_live_archive_sha256",
    "native_vm_live_sites_version",
    "native_vm_live_source_commit",
    "native_vm_staged_branch",
    "native_vm_staged_commit",
    "native_vm_staged_deployment_state",
    "native_vm_worktree_final_readiness_state",
    "support_collision_head_reconciled",
    "support_collision_pull_request",
    "support_correction_head_reconciled",
    "support_initial_custody_head_reconciled",
    "support_initial_base_head",
    "support_cie_assurance_main_head",
    "support_latest_main_head_reconciled",
    "support_latest_main_observed_at",
    "support_reconciled_main_delta_state",
})
PRODUCT_ROOT_KEYS = frozenset({
    "authority", "currency_semantics", "decision_semantics", "final_reconciled_at",
    "generated_at", "global_effective_gates", "manifest_id", "products",
    "semantic_version", "summary", "validation_contract",
})
PRODUCT_ROW_KEYS = frozenset({
    "canonical_candidate", "decision", "decision_reasons", "entitlement",
    "fulfillment", "kind", "name", "native_status", "offer_price", "product_id",
    "provider_aliases", "refund_dispute", "rights_license", "settlement_revenue",
    "sku", "slug", "universe",
})
PRODUCT_SECTION_KEYS = {
    "canonical_candidate": frozenset({"admission_state", "d1_product_version", "exact_active_version", "exact_public_assets", "proposed_thriveevergreen_sku", "source_registry_match", "source_registry_version"}),
    "exact_active_version": frozenset({"content_sha256", "custody_prefix", "id", "license_template", "published_at"}),
    "exact_public_asset": frozenset({"bytes", "path", "sha256"}),
    "offer_price": frozenset({"cash_amount_minor", "crown_credits", "currency", "denomination_rule", "effective_offer_state", "historical_balance_rewrite", "virality_credits_presentation"}),
    "provider_aliases": frozenset({"provider_success_is_authority", "stripe_payment_link_id", "stripe_price_environment_ref", "stripe_price_id", "stripe_product_id"}),
    "rights_license": frozenset({"economic_rights_state", "personal_use_only", "purchaser_license", "rights_status", "rights_tier"}),
    "entitlement": frozenset({"issuance_state", "provider_event_may_grant"}),
    "fulfillment": frozenset({"configured_mode", "configured_route", "download_limit", "effective_state", "signed_link_ttl_minutes", "source_asset_key"}),
    "refund_dispute": frozenset({"effective_state", "policy"}),
    "settlement_revenue": frozenset({"configured_route", "effective_state", "provider_receipt_is_evidence_only"}),
}
PRODUCT_TOP_SECTION_KEYS = {
    "authority": frozenset({"canonical_repository_head_at_final_reconciliation", "canonical_repository_head_at_reconciliation", "constitutional_rule", "native_d1_manifest_version", "native_sites_archive_sha256", "native_sites_deployed_source_commit", "native_sites_provider_version", "observed_at", "source_anchor_sha"}),
    "currency_semantics": frozenset({"canonical_observed_currency", "offer_price_currency", "runtime_v1_1_normalization", "unpriced_or_unknown_currency"}),
    "decision_semantics": frozenset({"advisory_ml_authority", "allowed", "available_rule", "d3", "deny_rule", "hold_rule"}),
    "global_effective_gates": frozenset({"agent_wallet_unattended_value_ceiling_minor", "canonical_crown_credit_underlying_ledger_bound_in_native_sites", "catalog_replacement_performed", "generalized_thriveevergreen_dispatch", "independent_security_hold_on_crown_credits_stripe_trustwallet", "metamask_frontend_state", "native_credits_v2_activated", "native_sites_mutation", "stripe_stablecoin_customer_effective_state", "walletconnect_human_modal_required"}),
    "summary": frozenset({"d1_only_records", "decisions", "deployed_source_registry_records", "exact_active_d1_versions", "native_statuses", "paid_products_economically_available", "source_registry_matches", "total"}),
    "validation_contract": frozenset({"closed_decision_set", "exact_content_digest_rule", "executable", "id"}),
}
DECISION_STATE_MATRIX = {
    "AVAILABLE": {
        "admission": "NON_ECONOMIC_PUBLIC_RESOURCE",
        "offer": "AVAILABLE_ZERO_PRICE",
        "rights": "PERSONAL_NONCOMMERCIAL_ZERO_PRICE",
        "entitlement": "NOT_REQUIRED_PUBLIC_STATIC_DOWNLOAD",
        "fulfillment": "ACTIVE_STATIC_PUBLIC",
        "settlement": "NOT_APPLICABLE_ZERO_PRICE",
    },
    "HOLD": {"admission": "HOLD", "offer": "HOLD", "rights": "HOLD", "entitlement": "HOLD", "fulfillment": "HOLD", "settlement": "HOLD"},
    "DENY": {"admission": "DENY", "offer": "DENY", "rights": "DENY", "entitlement": "HOLD", "fulfillment": "DENY", "settlement": "HOLD"},
}
PROJECTION_ROOT_KEYS = frozenset({
    "schema", "semantic_version", "projection_id", "recorded_at", "decision",
    "authority", "source", "derivation", "authority_readiness_counts",
    "exact_overrides", "release_authorized",
})
PROJECTION_SECTION_KEYS = {
    "authority": frozenset({"constitutional_rule", "decision_set", "projection_can_activate_economic_effects", "provider_success_is_evidence_only", "d3_human_reserved"}),
    "source": frozenset({"observed_product_manifest", "observed_products_sha256", "source_product_count", "observed_decisions", "observed_availability_is_economic_authority"}),
    "derivation": frozenset({"algorithm", "exact_row_evaluator_receipts", "issued_canonical_economic_skus", "free_public_resource_rule", "blocked_source_rule", "retired_source_rule", "row_shape", "materialization", "materialized_rows_sha256"}),
    "authority_readiness_counts": frozenset({"total", "AVAILABLE", "HOLD", "DENY", "paid_products_economically_available"}),
}
PROJECTION_OVERRIDE_KEYS = frozenset({"skus", "observed_decision", "authority_decision", "reason"})
ATTACHMENT_ROOT_KEYS = frozenset({
    "assets", "authority_rule", "conflict_sets", "decision_summary", "generated_at",
    "global_missing_mappings", "manifest_id", "semantic_version", "source_scope",
})
ATTACHMENT_SCOPE_KEYS = frozenset({
    "asset_count", "docx_count", "pdf_count", "source_files_modified", "title_groups",
    "total_bytes", "total_pdf_pages",
})
ATTACHMENT_ASSET_BASE_KEYS = frozenset({
    "accessibility", "bytes", "candidate", "crown_credits", "decision", "edition",
    "entitlement", "file", "format", "fulfillment", "id", "maturity", "offer_price",
    "pages", "print", "provider_aliases", "reasons", "refund_dispute", "rights",
    "settlement_revenue", "sha256", "title", "virality_credits",
})
ATTACHMENT_RELATION_KEYS = frozenset({"source_pair", "distribution_pair"})


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid JSON at {path.relative_to(ROOT)}: {error}")
    if not isinstance(value, dict):
        fail(f"root must be an object: {path.relative_to(ROOT)}")
    return value


def iso(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        fail(f"{label} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(f"{label} is not ISO-8601")
    return parsed


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(content: bytes) -> str:
    prefix = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(prefix + content).hexdigest()


def require(value: bool, message: str) -> None:
    if not value:
        fail(message)


def require_exact_keys(value: dict[str, Any], expected: frozenset[str], label: str) -> None:
    actual = frozenset(value)
    require(actual == expected, f"{label} key drift: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")


def validate_nested_timestamps(value: Any, recorded_at: datetime, path: str = "$") -> None:
    if isinstance(value, list):
        for index, entry in enumerate(value):
            validate_nested_timestamps(entry, recorded_at, f"{path}[{index}]")
        return
    if not isinstance(value, dict):
        return
    for key, entry in value.items():
        child_path = f"{path}.{key}"
        if key.endswith("_at") and isinstance(entry, str):
            require(iso(entry, child_path) <= recorded_at, f"future evidence timestamp at {child_path}")
        validate_nested_timestamps(entry, recorded_at, child_path)


class ProductValidationError(ValueError):
    pass


def product_check(condition: bool, message: str) -> None:
    if not condition:
        raise ProductValidationError(message)


def product_exact_keys(value: Any, expected: frozenset[str], label: str) -> None:
    product_check(isinstance(value, dict), f"{label} must be an object")
    actual = frozenset(value)
    product_check(actual == expected, f"{label} key drift: missing={sorted(expected - actual)} extra={sorted(actual - expected)}")


def validate_observed_product_manifest(manifest: dict[str, Any]) -> None:
    product_exact_keys(manifest, PRODUCT_ROOT_KEYS, "product root")
    for section, expected in PRODUCT_TOP_SECTION_KEYS.items():
        product_exact_keys(manifest.get(section), expected, f"product.{section}")
    product_exact_keys(manifest["summary"].get("decisions"), frozenset({"AVAILABLE", "HOLD", "DENY"}), "product.summary.decisions")
    product_exact_keys(
        manifest["summary"].get("native_statuses"),
        frozenset({"available_free", "blocked", "gso_pending", "institutional_inquiry", "licensing_deposit", "preview_only", "provider_reader_verified", "ready_held", "retired"}),
        "product.summary.native_statuses",
    )
    product_check(manifest["decision_semantics"].get("allowed") == ["AVAILABLE", "HOLD", "DENY"], "observed decision vocabulary drift")
    product_check(manifest["decision_semantics"].get("advisory_ml_authority") is False, "advisory ML became authority")
    product_check(manifest["decision_semantics"].get("d3") == "HUMAN_RESERVED", "D3 reservation drift")
    gates = manifest["global_effective_gates"]
    product_check(gates.get("native_credits_v2_activated") is False, "native credits v2 activated")
    product_check(gates.get("canonical_crown_credit_underlying_ledger_bound_in_native_sites") is False, "unproven Crown Credit binding activated")
    product_check(gates.get("agent_wallet_unattended_value_ceiling_minor") == 0, "Agent Wallet unattended ceiling drift")
    product_check(gates.get("catalog_replacement_performed") is False, "catalog replacement hidden")
    product_check(gates.get("generalized_thriveevergreen_dispatch") == "HOLD_DISABLED", "generalized dispatch drift")

    rows = manifest.get("products")
    product_check(isinstance(rows, list) and len(rows) == 389, "product row count drift")
    seen_skus: set[str] = set()
    for index, row in enumerate(rows):
        label = f"product.products[{index}]"
        product_exact_keys(row, PRODUCT_ROW_KEYS, label)
        for section in ("canonical_candidate", "offer_price", "provider_aliases", "rights_license", "entitlement", "fulfillment", "refund_dispute", "settlement_revenue"):
            product_exact_keys(row.get(section), PRODUCT_SECTION_KEYS[section], f"{label}.{section}")
        candidate = row["canonical_candidate"]
        product_exact_keys(candidate.get("exact_active_version"), PRODUCT_SECTION_KEYS["exact_active_version"], f"{label}.canonical_candidate.exact_active_version")
        assets = candidate.get("exact_public_assets")
        product_check(isinstance(assets, list), f"{label}.canonical_candidate.exact_public_assets must be an array")
        for asset_index, asset in enumerate(assets):
            product_exact_keys(asset, PRODUCT_SECTION_KEYS["exact_public_asset"], f"{label}.canonical_candidate.exact_public_assets[{asset_index}]")
            product_check(SHA256_RE.fullmatch(str(asset.get("sha256", ""))) is not None and isinstance(asset.get("bytes"), int) and asset["bytes"] > 0, f"{label} invalid public asset evidence")

        sku = row.get("sku")
        product_check(isinstance(sku, str) and sku and sku not in seen_skus, f"{label} invalid or duplicate SKU")
        seen_skus.add(sku)
        product_check(all(isinstance(row.get(key), str) and row[key] for key in ("product_id", "slug", "name", "kind", "universe", "native_status")), f"{label} invalid identity field")
        product_check(isinstance(row.get("decision_reasons"), list) and row["decision_reasons"] and all(isinstance(reason, str) and reason for reason in row["decision_reasons"]), f"{label} invalid decision reasons")
        decision = row.get("decision")
        product_check(decision in DECISION_STATE_MATRIX, f"{label} invalid decision")
        expected = DECISION_STATE_MATRIX[decision]
        product_check(candidate.get("admission_state") == expected["admission"], f"{label} admission/decision contradiction")
        product_check(row["offer_price"].get("effective_offer_state") == expected["offer"], f"{label} offer/decision contradiction")
        product_check(row["rights_license"].get("economic_rights_state") == expected["rights"], f"{label} rights/decision contradiction")
        product_check(row["entitlement"].get("issuance_state") == expected["entitlement"], f"{label} entitlement/decision contradiction")
        product_check(row["fulfillment"].get("effective_state") == expected["fulfillment"], f"{label} fulfillment/decision contradiction")
        product_check(row["settlement_revenue"].get("effective_state") == expected["settlement"], f"{label} settlement/decision contradiction")
        product_check(row["offer_price"].get("historical_balance_rewrite") is False, f"{label} historical rewrite activated")
        product_check(row["provider_aliases"].get("provider_success_is_authority") is False, f"{label} provider success became authority")
        product_check(row["entitlement"].get("provider_event_may_grant") is False, f"{label} provider event may grant entitlement")
        product_check(row["settlement_revenue"].get("provider_receipt_is_evidence_only") is True, f"{label} provider receipt became settlement truth")
        if decision == "AVAILABLE":
            offer = row["offer_price"]
            product_check(offer.get("cash_amount_minor") == offer.get("crown_credits") == offer.get("virality_credits_presentation") == 0, f"{label} observed AVAILABLE is not zero-price")
            product_check(len(assets) == 2, f"{label} observed AVAILABLE lacks two exact public assets")


def require_observed_product_rejection(manifest: dict[str, Any], mutate: Any, label: str) -> None:
    probe = copy.deepcopy(manifest)
    mutate(probe)
    try:
        validate_observed_product_manifest(probe)
    except ProductValidationError:
        return
    fail(f"negative product probe was accepted: {label}")


def materialize_authority_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for row in rows:
        sku = row["sku"]
        if sku == "VM-BOOK-ROSETTA-FILED-DRAFT":
            authority_decision = "DENY"
            reasons = ["EXACT_RETIRED_SUPERSEDED_NATIVE_SOURCE_STATE"]
        else:
            authority_decision = "HOLD"
            reasons = ["TRUSTED_EXACT_ROW_ECAC_RECEIPT_ABSENT", "ISSUED_CANONICAL_ECONOMIC_SKU_ABSENT"]
            if row["decision"] == "AVAILABLE":
                reasons.append("OBSERVED_PUBLIC_AVAILABILITY_IS_NOT_EXACT_ECONOMIC_AUTHORITY")
            if sku == "GSO-KEY-STORY-WORLD-PRODUCTION-SYSTEM":
                reasons.append("OBSERVED_BLOCKED_STATE_LACKS_TRUSTED_EXACT_DENY_PROFILE")
        materialized.append({
            "sku": sku,
            "observed_decision": row["decision"],
            "authority_decision": authority_decision,
            "reason_codes": reasons,
        })
    return materialized


def validate_authority_projection(projection: dict[str, Any], products: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    product_exact_keys(projection, PROJECTION_ROOT_KEYS, "authority projection root")
    for section, expected in PROJECTION_SECTION_KEYS.items():
        product_exact_keys(projection.get(section), expected, f"authority projection.{section}")
    overrides = projection.get("exact_overrides")
    product_check(isinstance(overrides, list) and len(overrides) == 3, "authority projection overrides drift")
    for index, override in enumerate(overrides):
        product_exact_keys(override, PROJECTION_OVERRIDE_KEYS, f"authority projection.exact_overrides[{index}]")
    product_check(overrides == [
        {
            "skus": ["VM-FREE-001", "VM-FREE-002"],
            "observed_decision": "AVAILABLE",
            "authority_decision": "HOLD",
            "reason": "OBSERVED_PUBLIC_AVAILABILITY_IS_NOT_EXACT_ECONOMIC_AUTHORITY",
        },
        {
            "skus": ["GSO-KEY-STORY-WORLD-PRODUCTION-SYSTEM"],
            "observed_decision": "DENY",
            "authority_decision": "HOLD",
            "reason": "OBSERVED_BLOCKED_STATE_LACKS_TRUSTED_EXACT_DENY_PROFILE",
        },
        {
            "skus": ["VM-BOOK-ROSETTA-FILED-DRAFT"],
            "observed_decision": "DENY",
            "authority_decision": "DENY",
            "reason": "EXACT_RETIRED_SUPERSEDED_NATIVE_SOURCE_STATE",
        },
    ], "authority projection exact override values drift")
    product_check(projection.get("decision") == "HOLD" and projection.get("release_authorized") is False, "authority projection release drift")
    product_check(projection["authority"].get("decision_set") == ["ECAC", "HOLD", "DENY"], "authority projection decision set drift")
    product_check(projection["authority"].get("projection_can_activate_economic_effects") is False, "authority projection activated effects")
    source_rows = products.get("products")
    product_check(isinstance(source_rows, list), "authority projection source rows missing")
    observed_digest = canonical_digest(source_rows)
    product_check(projection["source"].get("observed_product_manifest") == str(PRODUCTS.relative_to(ROOT)), "authority projection source path drift")
    product_check(projection["source"].get("observed_products_sha256") == observed_digest, "authority projection source digest drift")
    product_check(projection["source"].get("source_product_count") == len(source_rows) == 389, "authority projection source count drift")
    product_check(projection["source"].get("observed_decisions") == {"AVAILABLE": 2, "HOLD": 385, "DENY": 2}, "authority projection observed counts drift")
    product_check(projection["source"].get("observed_availability_is_economic_authority") is False, "observed availability became authority")
    product_check(projection["derivation"].get("exact_row_evaluator_receipts") == 0, "authority projection manufactured exact receipts")
    product_check(projection["derivation"].get("issued_canonical_economic_skus") == 0, "authority projection manufactured canonical SKUs")
    product_check(projection["derivation"].get("row_shape") == ["sku", "observed_decision", "authority_decision", "reason_codes"], "authority projection row shape drift")
    materialized = materialize_authority_projection(source_rows)
    materialized_digest = canonical_digest(materialized)
    product_check(projection["derivation"].get("materialized_rows_sha256") == materialized_digest, "authority projection materialized digest drift")
    counts = {decision: sum(row["authority_decision"] == decision for row in materialized) for decision in ("AVAILABLE", "HOLD", "DENY")}
    product_check(projection["authority_readiness_counts"] == {"total": 389, "AVAILABLE": counts["AVAILABLE"], "HOLD": counts["HOLD"], "DENY": counts["DENY"], "paid_products_economically_available": 0}, "authority projection count drift")
    product_check(counts == {"AVAILABLE": 0, "HOLD": 388, "DENY": 1}, "authority projection authority counts drift")
    return materialized, materialized_digest


def validate_attachment_manifest(attachments: dict[str, Any], recorded_at: datetime) -> None:
    require_exact_keys(attachments, ATTACHMENT_ROOT_KEYS, "attachment manifest root")
    require(attachments.get("manifest_id") == "ct.manifest.virality-attached-masters-reconciliation.2026-08-24.v1", "attachment manifest identity drift")
    require(attachments.get("semantic_version") == "1.0.0", "attachment manifest version drift")
    require(iso(attachments.get("generated_at"), "attachments.generated_at") <= recorded_at, "attachment evidence postdates acceptance")

    scope = attachments.get("source_scope")
    require(isinstance(scope, dict), "attachment source scope missing")
    require_exact_keys(scope, ATTACHMENT_SCOPE_KEYS, "attachment source scope")
    require(scope.get("source_files_modified") is False, "attachment sources were mutated")
    require(attachments.get("decision_summary") == {"AVAILABLE": 0, "HOLD": 16, "DENY": 0}, "attached-source HOLD truth drift")

    assets = attachments.get("assets")
    require(isinstance(assets, list) and len(assets) == 16, "attached-source count drift")
    ids: set[str] = set()
    files: set[str] = set()
    digests: set[str] = set()
    expected_candidates = {
        "A08": "VM-BOOK-WHAT-REALLY-HAPPENED",
        "A09": "VM-BOOK-WHAT-REALLY-HAPPENED",
        "A16": "VM-BOOK-ROSETTA-THE-WOMAN-WHO-MADE-THE-LEGEND-WASH-DISHES",
    }
    null_authority_fields = (
        "offer_price", "crown_credits", "virality_credits", "entitlement", "fulfillment",
        "refund_dispute", "settlement_revenue",
    )
    for index, asset in enumerate(assets):
        require(isinstance(asset, dict), f"attachment asset {index} must be an object")
        keys = frozenset(asset)
        relation_keys = keys & ATTACHMENT_RELATION_KEYS
        require(len(relation_keys) <= 1, f"attachment asset {index} has conflicting relation fields")
        require(keys == ATTACHMENT_ASSET_BASE_KEYS | relation_keys, f"attachment asset {index} key drift")
        asset_id = asset.get("id")
        filename = asset.get("file")
        digest = asset.get("sha256")
        require(isinstance(asset_id, str) and re.fullmatch(r"A(?:0[1-9]|1[0-6])", asset_id) is not None, f"attachment asset {index} id drift")
        require(isinstance(filename, str) and filename != "", f"attachment asset {index} filename missing")
        require(isinstance(digest, str) and SHA256_RE.fullmatch(digest) is not None, f"attachment asset {index} digest invalid")
        require(asset_id not in ids and filename not in files and digest not in digests, f"attachment asset {index} identity is not unique")
        ids.add(asset_id)
        files.add(filename)
        digests.add(digest)
        require(asset.get("decision") == "HOLD", f"attachment asset {asset_id} escaped HOLD")
        require(asset.get("format") in {"PDF", "DOCX"}, f"attachment asset {asset_id} format drift")
        require(isinstance(asset.get("bytes"), int) and asset["bytes"] > 0, f"attachment asset {asset_id} byte count invalid")
        require(isinstance(asset.get("pages"), int) and asset["pages"] > 0, f"attachment asset {asset_id} page count invalid")
        require(isinstance(asset.get("reasons"), list) and asset["reasons"] and all(isinstance(reason, str) and reason for reason in asset["reasons"]), f"attachment asset {asset_id} HOLD reasons missing")
        require(all(asset.get(field) is None for field in null_authority_fields), f"attachment asset {asset_id} contains an economic mapping")
        require(asset.get("provider_aliases") == [], f"attachment asset {asset_id} contains a provider alias")
        require(asset.get("candidate") == expected_candidates.get(asset_id), f"attachment asset {asset_id} candidate evidence drift")

    require(ids == {f"A{index:02d}" for index in range(1, 17)}, "attachment asset id set drift")
    pdf_assets = [asset for asset in assets if asset["format"] == "PDF"]
    docx_assets = [asset for asset in assets if asset["format"] == "DOCX"]
    require(scope == {
        "asset_count": 16,
        "title_groups": len({asset["title"] for asset in assets}),
        "total_bytes": sum(asset["bytes"] for asset in assets),
        "pdf_count": len(pdf_assets),
        "docx_count": len(docx_assets),
        "total_pdf_pages": sum(asset["pages"] for asset in pdf_assets),
        "source_files_modified": False,
    }, "attachment source totals drift")
    require(len(pdf_assets) == 14 and len(docx_assets) == 2 and scope["title_groups"] == 13, "attachment format/title totals drift")

    conflict_sets = attachments.get("conflict_sets")
    require(isinstance(conflict_sets, list) and len(conflict_sets) == 3, "attachment conflict-set drift")
    for index, conflict in enumerate(conflict_sets):
        require(isinstance(conflict, dict) and conflict.get("decision") == "HOLD", f"attachment conflict set {index} escaped HOLD")
        expected = frozenset({"type", "assets", "decision", "rule"})
        if conflict.get("type") == "MUTUALLY_CONFLICTING_MASTERS":
            expected |= frozenset({"token_alignment_percent_approx"})
        else:
            expected |= frozenset({"text_sha256", "matching_extracted_image_hashes"})
            require(isinstance(conflict.get("text_sha256"), str) and SHA256_RE.fullmatch(conflict["text_sha256"]) is not None, f"attachment conflict set {index} digest invalid")
        require_exact_keys(conflict, expected, f"attachment conflict set {index}")
        require(isinstance(conflict.get("assets"), list) and set(conflict["assets"]) <= ids, f"attachment conflict set {index} references unknown assets")


def validate() -> dict[str, Any]:
    acceptance = read_json(ACCEPTANCE)
    products = read_json(PRODUCTS)
    attachments = read_json(ATTACHMENTS)
    authority_projection = read_json(AUTHORITY_PROJECTION)
    integration_record = read_json(INTEGRATION_RECORD)
    custody_receipt = read_json(CUSTODY_RECEIPT)
    runtime_supersession = read_json(RUNTIME_SUPERSESSION)
    edge_candidate = read_json(EDGE_CANDIDATE_STATE)

    require_exact_keys(acceptance, ACCEPTANCE_ROOT_KEYS, "acceptance root")

    require(
        acceptance.get("schema") == "crownthrive.virality_music.thriveevergreen.acceptance.v1"
        and acceptance.get("schema_version") == "1.0.0",
        "acceptance schema/version drift",
    )
    require(acceptance.get("classification") == "PUBLIC_SAFE_MACHINE_RECORD", "classification drift")
    require(acceptance.get("record_id") == "ct.acceptance-addendum.virality-music.thriveevergreen.2026-08-24.v1", "record identity drift")
    require(acceptance.get("overall_decision") == "HOLD", "headline decision drift")
    require(acceptance.get("release_authorized") is False, "release authority manufactured")
    recorded_at = iso(acceptance.get("recorded_at"), "recorded_at")
    validate_nested_timestamps(acceptance, recorded_at)
    integration_generated_at = iso(integration_record.get("generated_at"), "integration_record.generated_at")
    integration_reconciled_at = iso(integration_record.get("last_evidence_reconciled_at"), "integration_record.last_evidence_reconciled_at")
    custody_generated_at = iso(custody_receipt.get("generated_at"), "custody_receipt.generated_at")
    custody_provider_modified_at = iso(custody_receipt.get("evidence_file", {}).get("provider_modified_at"), "custody_receipt.evidence_file.provider_modified_at")
    runtime_supersession_at = iso(runtime_supersession.get("recordedAt"), "runtime_supersession.recordedAt")
    require(max(integration_generated_at, integration_reconciled_at, custody_generated_at, custody_provider_modified_at, runtime_supersession_at) <= recorded_at, "external evidence postdates acceptance")
    canonical = acceptance.get("canonical_integration_record")
    require(isinstance(canonical, dict), "missing canonical integration binding")
    require(canonical == {
        "path": "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.v1.json",
        "implementation_commit": SUPPORT_COLLISION_HEAD,
        "initial_custody_binding_commit": SUPPORT_INITIAL_CUSTODY_HEAD,
        "corrected_custody_binding_commit": SUPPORT_CORRECTION_HEAD,
        "custody_receipt": "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.drive-custody-receipt.v1.json",
        "github_pull_request": SUPPORT_PULL_REQUEST,
        "relationship": "INDEPENDENT_FAIL_CLOSED_ACCEPTANCE_ADDENDUM_NO_ECONOMIC_AUTHORITY",
    }, "canonical integration binding drift")
    window = acceptance.get("observed_window_utc")
    require(isinstance(window, dict), "missing observed window")
    require_exact_keys(window, frozenset({"from", "through"}), "observed_window_utc")
    observed_from = iso(window.get("from"), "observed_window_utc.from")
    observed_through = iso(window.get("through"), "observed_window_utc.through")
    require(observed_from <= observed_through <= recorded_at, "observed window must satisfy from <= through <= recorded_at")

    authority = acceptance.get("authority")
    require(isinstance(authority, dict), "missing authority boundary")
    require_exact_keys(authority, AUTHORITY_KEYS, "authority")
    require(authority.get("economic_decisions") == ["ECAC", "HOLD", "DENY"], "decision vocabulary drift")
    for field in (
        "economic_activation_performed_by_this_record",
        "publication_activation_performed_by_this_record",
        "economic_provider_mutation_performed_by_this_record",
        "record_itself_performs_provider_mutation",
        "wallet_or_signing_mutation_performed_by_this_record",
        "provider_success_can_manufacture_authority",
    ):
        require(authority.get(field) is False, f"authority manufactured through {field}")
    require(authority.get("non_economic_provider_or_control_plane_mutation_observed_in_bound_execution_lineage") is True, "non-economic control mutation lineage hidden")
    require(authority.get("d3_human_reserved") is True, "D3 reservation drift")
    require(authority.get("provider_success_is_evidence_only") is True, "provider evidence boundary drift")

    binding = acceptance.get("source_binding")
    require(isinstance(binding, dict), "missing source binding")
    require_exact_keys(binding, SOURCE_BINDING_KEYS, "source_binding")
    require(binding.get("immutable_fabric_source_head") == FABRIC_SOURCE_HEAD, "Fabric anchor drift")
    require(binding.get("support_initial_base_head") == SUPPORT_INITIAL_BASE_HEAD, "Support initial base drift")
    require(binding.get("support_cie_assurance_main_head") == SUPPORT_CIE_ASSURANCE_MAIN_HEAD, "Support CIE-assurance main head drift")
    require(binding.get("support_latest_main_head_reconciled") == SUPPORT_LATEST_MAIN_HEAD, "Support latest main drift")
    require(binding.get("support_reconciled_main_delta_state") == "RECONCILED_CIE_ASSURANCE_DOCS_WAVE5_ECONOMIC_CONTROL_AGENT_WALLET_PACKAGE_MANAGED_WALLET_ACCEPTANCE_SNAPSHOT_AND_MINTLIFY_NAVIGATION_NO_VM_ECONOMIC_EXECUTION", "Support current-main delta reconciliation drift")
    git_binding = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SUPPORT_LATEST_MAIN_HEAD, "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    require(git_binding.returncode == 0, "actual Git HEAD does not contain the reconciled Support main head")
    require(binding.get("support_collision_head_reconciled") == SUPPORT_COLLISION_HEAD, "Support collision head drift")
    require(binding.get("support_initial_custody_head_reconciled") == SUPPORT_INITIAL_CUSTODY_HEAD, "Support initial custody head drift")
    require(binding.get("support_correction_head_reconciled") == SUPPORT_CORRECTION_HEAD, "Support corrected custody head drift")
    require(binding.get("support_collision_pull_request") == SUPPORT_PULL_REQUEST, "Support PR binding drift")
    require(binding.get("native_vm_staged_commit") == NATIVE_STAGED_COMMIT, "native staged commit drift")
    require(binding.get("native_vm_staged_deployment_state") == "HOLD_NOT_DEPLOYED", "native deployment state drift")
    for field in (
        "immutable_fabric_source_head",
        "support_initial_base_head",
        "support_cie_assurance_main_head",
        "support_latest_main_head_reconciled",
        "support_collision_head_reconciled",
        "support_initial_custody_head_reconciled",
        "support_correction_head_reconciled",
        "native_vm_latest_source_before_staging",
        "native_vm_live_source_commit",
        "native_vm_staged_commit",
    ):
        require(isinstance(binding.get(field), str) and GIT_SHA_RE.fullmatch(binding[field]) is not None, f"invalid git binding: {field}")
    require(isinstance(binding.get("native_vm_live_archive_sha256"), str) and SHA256_RE.fullmatch(binding["native_vm_live_archive_sha256"]) is not None, "invalid native archive digest")

    product = acceptance.get("product_reconciliation")
    require(isinstance(product, dict), "missing product reconciliation")
    records = products.get("products")
    require(isinstance(records, list), "product records missing")
    try:
        validate_observed_product_manifest(products)
        materialized_projection, projection_digest = validate_authority_projection(authority_projection, products)
    except ProductValidationError as error:
        fail(str(error))
    observed_digest = canonical_digest(records)
    require(observed_digest == product.get("observed_records_sha256"), "observed product digest mismatch")
    require(projection_digest == product.get("authority_projection_materialized_rows_sha256"), "authority projection materialized-row digest mismatch")
    require(file_sha256(AUTHORITY_PROJECTION) == product.get("authority_projection_artifact_sha256"), "authority projection artifact digest mismatch")
    require(product.get("observed_manifest") == str(PRODUCTS.relative_to(ROOT)), "observed product path drift")
    require(product.get("authority_projection") == str(AUTHORITY_PROJECTION.relative_to(ROOT)), "authority projection path drift")
    summary = products.get("summary")
    require(isinstance(summary, dict), "product summary missing")
    counts = summary.get("decisions")
    require(isinstance(counts, dict), "product counts missing")
    require(counts == {"AVAILABLE": 2, "HOLD": 385, "DENY": 2}, "observed product count drift")
    require(product.get("observed_public_classification") == {"available": 2, "hold": 385, "deny": 2, "economic_authority": False}, "observed public classification drift")
    expected_authority_counts = {"available": 0, "hold": 388, "deny": 1}
    for key, value in expected_authority_counts.items():
        require(product.get(key) == value, f"authority product {key} count drift")
    require(summary.get("total") == product.get("total") == 389, "product total drift")
    require(product.get("available_scope") == "NONE_UNDER_EXACT_AUTHORITY_READINESS", "availability scope drift")
    require(product.get("canonical_ct_skus_issued") == 0, "canonical SKU authority manufactured")
    require(product.get("exact_per_product_ecac_receipts") == 0, "unexpected exact-row receipt count")
    require(product.get("paid_products_economically_available") == summary.get("paid_products_economically_available") == 0, "paid availability manufactured")
    require(product.get("ready_held_products") == summary.get("native_statuses", {}).get("ready_held") == 353, "ready-HOLD count drift")
    require({row["sku"] for row in materialized_projection if row["authority_decision"] == "DENY"} == {"VM-BOOK-ROSETTA-FILED-DRAFT"}, "authority DENY scope drift")
    hold_index = next(index for index, row in enumerate(records) if row["decision"] == "HOLD")
    require_observed_product_rejection(products, lambda value: value.__setitem__("extra_authority", True), "extra root authority")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index].__setitem__("authority_override", "ECAC"), "extra row authority")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["entitlement"].__setitem__("active", True), "active entitlement injection")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["offer_price"].__setitem__("price_authority", True), "price authority injection")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["settlement_revenue"].__setitem__("payout_authority", True), "settlement authority injection")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["provider_aliases"].__setitem__("unreviewed_provider", "success"), "provider alias injection")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["fulfillment"].__setitem__("active_authority", True), "fulfillment authority injection")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["offer_price"].__setitem__("effective_offer_state", "AVAILABLE_ZERO_PRICE"), "HOLD offer contradiction")
    require_observed_product_rejection(products, lambda value: value["products"][hold_index]["provider_aliases"].__setitem__("provider_success_is_authority", True), "provider success authority injection")
    validate_attachment_manifest(attachments, recorded_at)
    attachment_summary = acceptance.get("source_attachment_evidence")
    require(isinstance(attachment_summary, dict), "attachment evidence summary missing")
    require(attachment_summary.get("manifest") == str(ATTACHMENTS.relative_to(ROOT)), "attachment manifest path drift")
    require(attachment_summary.get("manifest_artifact_sha256") == file_sha256(ATTACHMENTS), "attachment manifest artifact digest mismatch")
    require(attachment_summary.get("candidate_links_are_unissued_non_authoritative") is True, "attachment candidate links were promoted to authority")
    require(attachment_summary.get("exact_native_catalog_pdf_checksum_and_page_mappings") == 0, "unmaterialized attachment-to-catalog binding claimed")
    require(attachment_summary.get("native_catalog_binding_state") == "NOT_MATERIALIZED_NO_EXACT_BINDING_CLAIM", "attachment native-binding evidence was manufactured")

    planes = acceptance.get("planes")
    require(isinstance(planes, dict), "missing plane states")
    fabric = planes.get("thriveevergreen_fabric", {})
    require(fabric.get("inventory") == {
        "bounded_agents": 8,
        "skill_contracts": 12,
        "plugin_packs": 5,
        "pallet_projections": 12,
        "deterministic_algorithms": 10,
        "advisory_ml_models": 3,
    }, "Fabric inventory drift")
    v2 = planes.get("thriveevergreen_v2", {})
    require(v2.get("canonical_engine") == "ct.agent.thriveevergreen-autonomous-publisher.v2", "canonical engine drift")
    require(v2.get("state") == "PRODUCTION_WRITE_ACTIVE_ACCEPTANCE_HOLD", "current v2 state drift")
    require(v2.get("source_head") == FABRIC_SOURCE_HEAD and v2.get("environment") == "production", "current v2 source/environment drift")
    require(v2.get("runtime_mode") == "production_write", "current runtime-mode drift")
    require(v2.get("component_runtime_state") == "production_publisher_active", "current component-state drift")
    require(v2.get("publication_activation_state") == "ECAC" and v2.get("publication_activation_state_namespace") == "ENGINE_CONFIGURATION_NOT_CANDIDATE_DECISION", "engine configuration ECAC was misrepresented")
    require(v2.get("production_effects_enabled") is True and v2.get("current_decision") == "HOLD", "current engine configuration/acceptance boundary drift")
    require(v2.get("candidate_count") == 1 and v2.get("admitted_candidate_count") == 0 and v2.get("verified_publication_count") == 0 and v2.get("candidate_evaluation_state") == "HOLD", "held candidate manufactured publication")
    require(v2.get("d3_human_reserved") is True, "current v2 D3 reservation drift")
    require(v2.get("control_convergence_state") == "RECONVERGED_TO_PRODUCTION_WRITE_AFTER_TRANSIENT_OBSERVER_HOLD", "v2 control convergence evidence hidden")
    require(v2.get("paired_consecutive_current_readbacks") == 3 and v2.get("fabric_and_vm_controls_agree") is True, "paired v2 readback evidence drift")
    require(v2.get("control_state_stability_certified") is False, "transient v2 stability was falsely certified")
    require(v2.get("control_state_stability_gate") == "HOLD_STATE_FLAP_OR_CONTROL_CONVERGENCE_MONITORING_REQUIRED", "transient v2 stability gate hidden")
    require(v2.get("transient_state_evidence") == {
        "observed_at": "2026-08-24T07:36:31Z",
        "runtime_mode": "production_observer",
        "component_runtime_state": "production_observer_scheduled_publication_hold",
        "publication_activation_state": "HOLD",
        "production_effects_enabled": False,
        "current_machine_truth": False,
    }, "transient observer/HOLD evidence was erased")
    historical_v2 = v2.get("drive_bound_historical_implementation_record_evidence", {})
    canonical_v2 = integration_record.get("thriveevergreen_v2", {})
    require(historical_v2 == {
        "record": str(INTEGRATION_RECORD.relative_to(ROOT)),
        "last_evidence_reconciled_at": integration_record.get("last_evidence_reconciled_at"),
        "runtime_mode": canonical_v2.get("runtime_mode"),
        "component_runtime_state": canonical_v2.get("component_runtime_state"),
        "publication_activation_state": canonical_v2.get("publication_activation_state"),
        "production_effects_enabled": canonical_v2.get("production_effects_enabled"),
        "admitted_candidate_count": canonical_v2.get("admitted_candidate_count"),
        "verified_publication_count": canonical_v2.get("verified_publication_count"),
        "current_machine_truth": False,
    }, "historical v2 evidence was mixed into current machine truth")
    money_authority = planes.get("money_movement_production_authority", {})
    require(money_authority.get("state") == "CONDITIONALLY_AUTHORIZED_CONFIGURATION_NO_EXECUTION_OBSERVED_ACCEPTANCE_HOLD", "money-movement authority configuration drift")
    require(money_authority.get("dail_sequence") == 1753 and money_authority.get("dail_event_type") == "THRIVEEVERGREEN_MONEY_MOVEMENT_PRODUCTION_AUTHORITY_V1", "money-movement authority DAIL binding drift")
    require(money_authority.get("money_movement_authorized") is True and money_authority.get("provider_write_authorized") is True, "conditional production authority was hidden")
    require(money_authority.get("requires_exact_ecac_immediately_before_execution") is True and money_authority.get("d3_human_reserved") is True, "money-movement exact-ECAC or D3 boundary drift")
    require(money_authority.get("max_unattended_value_minor") == 0 and money_authority.get("unattended_wallet_execution_authorized") is False, "money-movement unattended ceiling drift")
    require(money_authority.get("money_movement_performed_in_receipt") is False and money_authority.get("provider_write_performed_in_receipt") is False and money_authority.get("rights_grant_performed_in_receipt") is False, "authority configuration was misrepresented as execution")
    require(all(value == 0 for value in money_authority.get("post_authority_effect_rows", {}).values()), "post-authority economic execution rows observed")
    require(money_authority.get("authority_configuration_is_execution_receipt") is False and money_authority.get("current_candidate_and_checkout_gate_decision") == "HOLD", "authority configuration manufactured current execution")
    evaluator = planes.get("exact_ecac_evaluator", {})
    require(evaluator.get("live_v2_state") == "PRODUCTION_WRITE_READ_VERIFIED_ACCEPTANCE_HOLD_TRANSIENT_STABILITY_UNCERTIFIED", "live evaluator state drift")
    require(evaluator.get("inherited_compatibility_candidate_state") == "SUPERSEDED_HOLD_NOT_EXACT_ECAC_AUTHORITY", "inherited compatibility helper misrepresented as ECAC authority")
    require(evaluator.get("inherited_compatibility_candidate_runtime") == "developers/scripts/thriveevergreen/production-fabric-runtime.v1.1.ts", "inherited runtime pointer drift")
    require(evaluator.get("inherited_compatibility_candidate_contract") == "developers/contracts/thriveevergreen/production-fabric.contracts.v1.1.schema.json", "inherited contract pointer drift")
    require(evaluator.get("inherited_candidate_supersession_receipt") == str(RUNTIME_SUPERSESSION.relative_to(ROOT)), "runtime supersession pointer drift")
    require(evaluator.get("staged_policy_reducer_state") == "STAGED_VALIDATION_REDUCER_NOT_ECAC_AUTHORITY", "staged reducer misrepresented as ECAC authority")
    require(evaluator.get("staged_policy_reducer_runtime") == "developers/scripts/thriveevergreen/production-fabric-policy-reducer.v1.1.ts", "policy reducer runtime pointer drift")
    require(evaluator.get("staged_policy_reducer_contract") == "developers/contracts/thriveevergreen/production-fabric-policy-reducer.contracts.v1.1.json", "policy reducer contract pointer drift")
    require(evaluator.get("staged_policy_reducer_test") == str(POLICY_REDUCER_TEST.relative_to(ROOT)), "policy reducer test pointer drift")
    require(all(path.is_file() for path in (CANONICAL_RUNTIME, CANONICAL_CONTRACT, POLICY_REDUCER_RUNTIME, POLICY_REDUCER_CONTRACT, POLICY_REDUCER_TEST, RUNTIME_SUPERSESSION)), "runtime, contract, test, or supersession pointer is missing")
    staged_artifact_sha256 = {
        "runtime": file_sha256(POLICY_REDUCER_RUNTIME),
        "contract": file_sha256(POLICY_REDUCER_CONTRACT),
        "test": file_sha256(POLICY_REDUCER_TEST),
    }
    require(evaluator.get("staged_policy_reducer_artifact_sha256") == staged_artifact_sha256, "policy reducer artifact digest drift")
    require(evaluator.get("staged_policy_reducer_verification") == {"state": "PASS", "tests": 25, "passed": 25, "failed": 0}, "policy reducer test evidence drift")
    require(evaluator.get("trusted_wrapper_must_pin_expected_candidate_and_registry_digests") is True, "trusted wrapper digest pin omitted")
    require(evaluator.get("caller_supplied_gate_states_are_not_independent_authority") is True, "caller gate-state authority boundary drift")
    require(evaluator.get("caller_supplied_matching_digests_are_not_trust") is True, "caller digest-match trust boundary drift")
    require(evaluator.get("staged_v1_1_effect_authorizations") == {
        "provider_write": False,
        "money_movement": False,
        "entitlement_activation": False,
        "publication": False,
    }, "staged reducer effect authorization drift")
    require(runtime_supersession.get("status") == "STAGED_SUPERSESSION_HOLD_NOT_AUTHORITY", "runtime supersession state drift")
    require(runtime_supersession.get("repository") == {
        "canonical": "crownthrive1/CrownThrive-Support",
        "localPreparationBranch": "codex/vm-thriveevergreen-convergence-20260824",
        "targetReviewBranch": "feat/virality-thriveevergreen-production-fabric-20260824",
    }, "runtime supersession repository lineage drift")
    require(runtime_supersession.get("lineage", {}).get("weakCandidateCommit") == SUPPORT_COLLISION_HEAD, "runtime supersession weak lineage drift")
    require(runtime_supersession.get("lineage", {}).get("prePatchHead") == SUPPORT_CORRECTION_HEAD, "runtime supersession parent drift")
    require(runtime_supersession.get("lineage", {}).get("initialCustodyHead") == SUPPORT_INITIAL_CUSTODY_HEAD, "runtime supersession initial custody drift")
    preserved = runtime_supersession.get("preservedArtifacts", {})
    current_preserved_hashes = {
        str(CANONICAL_RUNTIME.relative_to(ROOT)): file_sha256(CANONICAL_RUNTIME),
        str(CANONICAL_CONTRACT.relative_to(ROOT)): file_sha256(CANONICAL_CONTRACT),
        "scripts/tests/thriveevergreen-production-fabric-runtime.v1.1.test.mjs": file_sha256(ROOT / "scripts/tests/thriveevergreen-production-fabric-runtime.v1.1.test.mjs"),
    }
    require(set(preserved) == set(current_preserved_hashes), "runtime supersession preserved-artifact scope drift")
    require(all(preserved[path].get("sha256") == digest and preserved[path].get("bytePreserved") is True for path, digest in current_preserved_hashes.items()), "runtime supersession preserved hashes drift")
    require(runtime_supersession.get("lineage", {}).get("weakArtifactSha256") == current_preserved_hashes, "runtime supersession weak hashes drift")
    canonical_artifacts = integration_record.get("artifact_sha256", {})
    require(canonical_artifacts.get("runtime_v1_1") == current_preserved_hashes[str(CANONICAL_RUNTIME.relative_to(ROOT))], "canonical runtime custody hash drift")
    require(canonical_artifacts.get("runtime_contract_v1_1") == current_preserved_hashes[str(CANONICAL_CONTRACT.relative_to(ROOT))], "canonical contract custody hash drift")
    require(canonical_artifacts.get("runtime_tests") == current_preserved_hashes["scripts/tests/thriveevergreen-production-fabric-runtime.v1.1.test.mjs"], "canonical runtime-test custody hash drift")
    replacement = runtime_supersession.get("stagedValidationReplacement", {})
    require(replacement.get("state") == "STAGED_VALIDATION_ONLY_NOT_ECAC_AUTHORITY", "policy reducer replacement authority drift")
    require(replacement.get("callerSuppliedDigestBindingsAreTrust") is False and replacement.get("exactEcacAuthority") == "EXTERNAL_EXACT_ECAC_REQUIRED", "caller-matched digest trust manufactured")
    expected_staged_receipt_hashes = {
        str(POLICY_REDUCER_RUNTIME.relative_to(ROOT)): staged_artifact_sha256["runtime"],
        str(POLICY_REDUCER_CONTRACT.relative_to(ROOT)): staged_artifact_sha256["contract"],
        str(POLICY_REDUCER_TEST.relative_to(ROOT)): staged_artifact_sha256["test"],
    }
    require(replacement.get("stagedArtifactSha256") == expected_staged_receipt_hashes, "runtime supersession staged-artifact hashes drift")
    require(replacement.get("verification") == {
        "command": "node --experimental-strip-types --test developers/scripts/thriveevergreen/production-fabric-policy-reducer.v1.1.test.ts",
        "state": "PASS", "tests": 25, "passed": 25, "failed": 0,
    }, "runtime supersession staged test evidence drift")
    require(replacement.get("generalizedDispatchAuthorized") is False and replacement.get("economicEffectsAuthorized") is False, "supersession activated effects")
    findings = runtime_supersession.get("findings")
    require(isinstance(findings, list) and len(findings) == 5 and all(finding.get("state") == "OPEN_IN_INHERITED_COMPATIBILITY_HELPER" and finding.get("requiredDisposition") == "HOLD_NOT_AUTHORITY" for finding in findings), "runtime findings hidden or resolved without evidence")
    release_state = runtime_supersession.get("releaseState", {})
    require(release_state.get("deployed") is False and release_state.get("generalizedDispatch") is False and release_state.get("economicEffectsAuthorized") is False, "runtime supersession release authority drift")

    dispatch = planes.get("generalized_dispatch", {})
    require(str(dispatch.get("state", "")).startswith("HOLD"), "generalized dispatch not held")
    require(dispatch.get("canonical_external_dispatch_enabled") is False, "canonical dispatch enabled")
    require(dispatch.get("integration_control_enabled") is False, "integration dispatch enabled")
    require(dispatch.get("runtime_exposure_enabled") is False, "runtime dispatch exposure enabled")
    require(dispatch.get("state") == "HOLD_EXACT_MUTATION_CONTRACT", "dispatch exact-contract HOLD drift")
    require(dispatch.get("blocker") == "LEAST_DATA_SCHEMA_EXPECTED_GATE_DIGEST_IDEMPOTENCY_READ_AFTER_WRITE_COMPENSATION_WRAPPER_AND_INDEPENDENT_CERTIFICATION_INCOMPLETE", "dispatch blocker drift")

    forward = planes.get("economic_control_forward_reconciliation", {})
    require(forward.get("state") == "RECONCILED_CURRENT_MAIN_CONTROL_RECOVERY_NO_ECONOMIC_ACTIVATION", "economic-control forward state drift")
    require(forward.get("source") == "developers/certification/economic-control-forward-reconciliation-2026-08-24.mdx", "economic-control forward source drift")
    require(forward.get("source_main_head") == SUPPORT_ECONOMIC_CONTROL_FORWARD_MAIN_HEAD, "economic-control forward main binding drift")
    for field in ("purchase_performed", "payment_or_payout_performed", "wallet_signing_or_broadcast_performed", "rights_or_entitlement_granted", "generalized_dispatch_enabled"):
        require(forward.get(field) is False, f"economic-control forward reconciliation manufactured {field}")

    cie = planes.get("cie_current_link_assurance", {})
    require(cie.get("framework") == "ct.framework.cultural-imprint-engine" and cie.get("state") == "HOLD_CURRENT_LINK_ASSURANCE_STALE", "CIE current-link HOLD drift")
    require(cie.get("historical_receipt_support_head") == SUPPORT_INITIAL_BASE_HEAD and cie.get("latest_support_main_head") == SUPPORT_LATEST_MAIN_HEAD, "CIE assurance head binding drift")
    require(cie.get("source_migration_version") == "20260824070356" and cie.get("recorded_applied_migration_version") == "20260824070845", "CIE migration version evidence drift")
    for field in ("historical_receipt_reusable_as_current_authority", "matching_applied_version_repository_source_present", "post_ddl_advisor_receipt_present", "actual_function_acl_readback_present", "status_observer_fully_fail_closed", "conflict_receipt_no_authority_fields_revalidated", "thriveevergreen_ecac_effect", "vm_commerce_authority_effect"):
        require(cie.get(field) is False, f"CIE evidence gap or no-authority boundary hidden: {field}")

    crown_credits = planes.get("crown_credits", {})
    require(crown_credits.get("state") == "ACTIVE_SETTLEMENT_RECONCILIATION_PURCHASING_HOLD", "Crown Credits control state drift")
    require(crown_credits.get("control_version") == "1.1.0" and crown_credits.get("runtime_digest") == "da1ba67e0c13825b4835d1526a4afacd4826e1293d49346cdf3501f11039d778", "Crown Credits runtime binding drift")
    require(crown_credits.get("control_http_state") == "PASS_200" and crown_credits.get("offer_count") == 5 and crown_credits.get("reconciliation_canary_state") == "PASS", "Crown Credits recovered readback hidden")
    require(crown_credits.get("provider_write_available") is False and crown_credits.get("purchase_authorized") is False, "Crown Credits authority manufactured")
    require(crown_credits.get("reported_provider_reconciliation_boundary_is_evidence_only") is True and crown_credits.get("exact_chlom_and_thriveevergreen_ecac_required") is True, "Crown Credits provider preconditions misrepresented as authority")
    require(crown_credits.get("current_purchase_or_candidate_internal_ledger_mutation_authorized") is False and crown_credits.get("production_authority_configuration_can_authorize_under_exact_ecac") is True, "Crown Credits conditional ledger-authority boundary drift")
    require(crown_credits.get("provider_success_can_mint_crown_credits") is False, "provider success manufactured Crown Credits")

    stripe_direct = planes.get("stripe_direct", {})
    require(stripe_direct.get("state") == "ACTIVE_READBACK_ONLY_ECONOMIC_AUTHORITY_HOLD", "Stripe Direct control state drift")
    require(stripe_direct.get("control_version") == "1.1.1" and stripe_direct.get("runtime_digest") == "07d50145f9ca843d23a6fdda46fe0ca805dfb679c06544325eb546090f592103", "Stripe Direct runtime binding drift")
    require(stripe_direct.get("control_http_state") == "PASS_200" and stripe_direct.get("platform_account_readback") == stripe_direct.get("connected_account_readback") == "PASS_200", "Stripe Direct recovered readback hidden")
    require(stripe_direct.get("provider_write_available") is False and stripe_direct.get("money_movement_performed") is False and stripe_direct.get("checkout_authorized") is False and stripe_direct.get("crown_credit_topups_authorized") is False, "Stripe Direct authority manufactured")

    credits = planes.get("virality_credits_bridge", {})
    require(credits.get("crown_credits_per_virality_credit") == 25, "Virality/Crown bridge drift")
    require(credits.get("automatic_historical_balance_rewrite") is False, "historical balances would be rewritten")
    require(credits.get("separate_underlying_ledger_created") is False, "duplicate underlying ledger created")
    metamask = planes.get("metamask_embedded", {})
    require(metamask.get("network") == "sapphire_mainnet" and metamask.get("namespaces") == ["EVM", "Solana"], "MetaMask network/namespace evidence drift")
    require(metamask.get("additional_namespace_state") == "NOT_MACHINE_ENUMERATED", "unverified MetaMask namespaces were manufactured")
    require(metamask.get("origin_state") == "FOUNDER_ATTESTED_PROVIDER_READBACK_UNKNOWN", "founder origin attestation misrepresented as provider evidence")
    require(metamask.get("key_export_enabled") is False, "MetaMask key export enabled")
    connect = planes.get("stripe_connect", {})
    require(connect.get("new_native_onboarding_state") == "DISABLED", "Connect onboarding activated")
    require(connect.get("marketplace_destination_charge_authority") is False, "marketplace authority manufactured")
    require(str(connect.get("state", "")).endswith("HOLD"), "Connect CrownThrive authority is not held")
    require(planes.get("walletconnect", {}).get("unattended_value_ceiling_minor") == 0, "WalletConnect unattended ceiling drift")
    agent_wallet = planes.get("dedicated_agent_wallet", {})
    require(agent_wallet.get("unattended_value_ceiling_minor") == 0, "Agent Wallet unattended ceiling drift")
    require(agent_wallet.get("state") == "PERSISTENT_TWAK_RUNNER_PACKAGE_UNBOUND_NOT_INSTALLABLE_HOLD" and agent_wallet.get("lane") == "FOUNDER_REQUIRED_PERSISTENT_TWAK", "persistent Agent Wallet package/current effect state drift")
    require(agent_wallet.get("runner_id") == "ct.runner.chlom-agent-wallet.base-usdc.v1" and agent_wallet.get("runner_identity_collision_with_managed_lane") is True, "Agent Wallet runner-identity collision hidden")
    require(agent_wallet.get("repository_source_head") == SUPPORT_LATEST_MAIN_HEAD and agent_wallet.get("repository_package_state") == "PERSISTENT_TWAK_RUNNER_PACKAGE_UNBOUND_NOT_INSTALLABLE_HOLD", "Agent Wallet repository package lineage drift")
    require(agent_wallet.get("package_source_commit") == "07679e290959b9f9023117f70526b2836c453bfc" and agent_wallet.get("contract_commit") == "29a3d82e70d5c57bcb9b2fab10af99162e7e6891" and agent_wallet.get("certification_claim_commit") == SUPPORT_AGENT_WALLET_PACKAGE_CERTIFICATION_HEAD, "Agent Wallet package/contract/certification split drift")
    require(agent_wallet.get("control_evidence_state") == "HISTORICAL_PRE_MANAGED_BINDING_SUPERSEDED_FOR_CURRENT_RUNTIME_FACTS", "historical persistent-runner control evidence was presented as current")
    require(agent_wallet.get("control_endpoint_state") == "PASS_HTTP_200" and agent_wallet.get("control_version") == "1.0.0", "Agent Wallet control readback drift")
    require(agent_wallet.get("runner_state") == "package_ready" and agent_wallet.get("address_state") == agent_wallet.get("health_state") == "pending", "Agent Wallet runtime gate state drift")
    require(agent_wallet.get("persistent_runner_bound") is False and agent_wallet.get("wallet_creation_performed") is False and agent_wallet.get("encrypted_wallet_created") is False and agent_wallet.get("signing_available") is False, "Agent Wallet capability manufactured")
    require(agent_wallet.get("raw_control_config_autonomous_execution_allowed") is True, "raw Agent Wallet configuration conflict was hidden")
    require(agent_wallet.get("money_movement_authorized_configuration") is True and agent_wallet.get("exact_ecac_required") is True and agent_wallet.get("d3_human_reserved") is True, "Agent Wallet conditional production configuration hidden")
    require(agent_wallet.get("effective_autonomous_value_execution_authorized") is False and agent_wallet.get("execution_effective") is False and agent_wallet.get("unattended_value_ceiling_effectively_enforced") is False, "Agent Wallet effective autonomy or enforcement was manufactured")
    require(agent_wallet.get("private_material_stored_in_thrivebase") is False, "Agent Wallet private-material boundary drift")
    require(agent_wallet.get("independent_acceptance_state") == "HOLD_SOURCE_AND_ACTIVATION_DEFECTS" and len(agent_wallet.get("source_findings", [])) == 7, "Agent Wallet source certification defects hidden")
    require(agent_wallet.get("systemd_verify_state") == "FAIL_EMPTY_USER_SPECIFIER_IN_NON_TEMPLATE_UNIT" and agent_wallet.get("script_file_mode") == "100644_NOT_EXECUTABLE", "Agent Wallet installability defects hidden")
    for field in ("wrapper_enforces_exact_ecac", "saved_automation_inventory_readback_present", "preflight_policy_digest_pinned", "preflight_requires_exact_ecac_receipt", "preflight_rejects_empty_destination", "health_least_data_allowlist", "sensitive_wallet_create_output_cleanup_on_failure", "wallet_password_os_keychain_bound", "installer_and_twak_version_pinned", "no_value_and_unauthorized_sign_canary_sources_present"):
        require(agent_wallet.get(field) is False, f"Agent Wallet fail-closed source defect hidden: {field}")
    require(agent_wallet.get("raw_twak_watch_enabled") is True and agent_wallet.get("hmac_secret_passed_in_process_argv") is True, "Agent Wallet raw watch/secret-argv risk hidden")
    require(agent_wallet.get("health_parse_error_canary") == "FAIL_EXIT_0_STATE_PASS_WITH_FIVE_PARSE_ERRORS", "Agent Wallet health fail-open canary hidden")

    managed_wallet = planes.get("managed_vault_agent_wallet", {})
    require(managed_wallet.get("state") == "ACTIVE_SIGNING_CAPABLE_POLICY_CUSTODY_RECONCILIATION_HOLD" and managed_wallet.get("lane") == "THRIVEBASE_VAULT_SERVER_MANAGED", "managed Agent Wallet evidence/acceptance state drift")
    require(managed_wallet.get("runner_id") == agent_wallet.get("runner_id") and managed_wallet.get("same_runner_id_as_persistent_twak_package") is True, "same-runner custody collision hidden")
    require(managed_wallet.get("satisfies_founder_required_persistent_runner_only_custody") is False, "managed Vault lane was misrepresented as founder-required persistent custody")
    require(managed_wallet.get("main_delta_commits") == {
        "acceptance_contract": SUPPORT_MANAGED_WALLET_ACCEPTANCE_COMMIT,
        "managed_wallet_documentation": SUPPORT_MANAGED_WALLET_DOCUMENTATION_COMMIT,
        "certification_claim": SUPPORT_MANAGED_WALLET_CERTIFICATION_COMMIT,
    }, "managed-wallet main-delta lineage drift")
    expected_managed_artifacts = [
        str(MANAGED_WALLET_ACCEPTANCE_CONTRACT.relative_to(ROOT)),
        str(MANAGED_WALLET_DOCUMENTATION.relative_to(ROOT)),
        str(MANAGED_WALLET_CERTIFICATION.relative_to(ROOT)),
    ]
    require(managed_wallet.get("main_delta_artifacts") == expected_managed_artifacts, "managed-wallet artifact scope drift")
    require(file_sha256(MANAGED_WALLET_ACCEPTANCE_CONTRACT) == "42a0fd90e1a9bf17850b9285fd104f17bcd2a62b084662f0bffca14cc05ff7b6", "managed-wallet acceptance contract digest drift")
    require(file_sha256(MANAGED_WALLET_DOCUMENTATION) == "98fbe05c451f9fff7246378b644bfe60e07278bc5203a6fd49711b25a3cccfb1", "managed-wallet documentation digest drift")
    require(file_sha256(MANAGED_WALLET_CERTIFICATION) == "17db3533c92db6e9dd0868b91e9c050a65f3a163ce2b3ded9a73d7bf1b6dd27f", "managed-wallet certification-claim digest drift")
    managed_contract = read_json(MANAGED_WALLET_ACCEPTANCE_CONTRACT)
    require(managed_contract.get("required_projection") == {
        "money_movement_authorized": True,
        "money_movement_execution_count": 0,
        "max_unattended_value_minor": 0,
        "candidate_decision": "HOLD",
        "checkout_state": "HOLD",
        "authority_vs_execution_distinction_preserved": True,
        "authorized_configuration_is_not_performed_transaction": True,
    }, "managed-wallet acceptance contract projection drift")
    require(managed_wallet.get("control_endpoint_state") == "PASS_HTTP_200" and managed_wallet.get("control_version") == "1.1.0", "managed Agent Wallet control evidence drift")
    require(managed_wallet.get("runner_state") == "active" and managed_wallet.get("health_state") == "pass" and managed_wallet.get("address_state") == "verified", "managed Agent Wallet current state drift")
    require(managed_wallet.get("public_address") == "0x7bc35BEab3bd346590fA6f68C218ccf249759Ab0" and managed_wallet.get("chain_id") == 8453 and managed_wallet.get("primary_asset") == "USDC", "managed Agent Wallet public binding drift")
    require(managed_wallet.get("twak_version") is None and managed_wallet.get("live_metadata_references_unmodified_defective_runner_paths") is True, "managed Agent Wallet source/provider-version gap hidden")
    for field in ("durable_runner_bound", "wallet_creation_performed", "encrypted_wallet_created", "private_material_vaulted_reported", "separate_vault_aliases_reported", "signing_available_for_no_value_canary", "money_movement_authorized_configuration", "exact_ecac_required", "d3_human_reserved", "execution_effective_reported_by_control"):
        require(managed_wallet.get(field) is True, f"managed Agent Wallet positive control evidence drift: {field}")
    for field in ("raw_private_key_persisted", "mnemonic_persisted", "private_material_returned", "raw_secret_export", "vault_principal_separation_proven", "vault_rotation_recovery_readback_present", "execution_receipt_observed", "effective_positive_value_execution_authorized", "unattended_value_ceiling_independently_enforced", "repository_database_migration_source_present", "repository_edge_control_v1_1_source_present", "repository_rollback_receipt_present", "exact_per_intent_ecac_signing_wrapper_source_present", "independent_exact_ecac_signing_wrapper_certified", "production_broadcast_provider_certified", "custody_contract_version_supersession_present"):
        require(managed_wallet.get(field) is False, f"managed Agent Wallet unproved authority/source/custody gate hidden: {field}")
    require(managed_wallet.get("signature_canary_state") == "PASS_NO_VALUE" and managed_wallet.get("unauthorized_sign_negative_canary_state") == "NOT_RUN_HOLD", "managed signing canary boundary drift")
    require(managed_wallet.get("money_movement_execution_count") == managed_wallet.get("unattended_value_ceiling_minor") == 0, "managed wallet execution/ceiling drift")
    require(managed_wallet.get("candidate_decision") == managed_wallet.get("checkout_state") == "HOLD", "managed wallet candidate/checkout HOLD hidden")
    require(managed_wallet.get("post_bind_effect_rows") == {"wallet_ledger_events": 0, "crown_credit_ledger": 0, "entitlements": 0, "wallet_rights_entitlements": 0, "checkout_intents": 0}, "managed wallet post-bind economic rows detected or hidden")
    snapshot = managed_wallet.get("acceptance_snapshot", {})
    require(snapshot.get("snapshot_id") == "517d9cdd-eee9-4645-bfe1-f9078636e157" and snapshot.get("state") == "AUTHORIZED_CONFIGURED_NOT_EXECUTED" and snapshot.get("evidence_sha256") == "fa406254e0ce007be20b021c55b43f3017105c6e72a47b666277373ed1c29348", "managed-wallet acceptance snapshot drift")
    require(snapshot.get("authority_vs_execution_distinction_preserved") is True and snapshot.get("snapshot_is_independent_economic_authority") is False, "managed-wallet snapshot manufactured authority")
    latest_snapshot = managed_wallet.get("latest_scheduled_snapshot", {})
    require(latest_snapshot.get("snapshot_id") == "2e3cf817-47d1-4118-a306-c129d056cf94" and latest_snapshot.get("state") == "AUTHORIZED_CONFIGURED_NOT_EXECUTED" and latest_snapshot.get("observed_at") == "2026-08-24T08:47:00.113866Z", "managed-wallet first scheduled snapshot drift")
    require(latest_snapshot.get("money_movement_execution_count") == latest_snapshot.get("unattended_value_ceiling_minor") == 0 and latest_snapshot.get("candidate_decision") == latest_snapshot.get("checkout_state") == "HOLD", "managed-wallet scheduled snapshot manufactured execution")
    require(latest_snapshot.get("evidence_sha256") == "fa406254e0ce007be20b021c55b43f3017105c6e72a47b666277373ed1c29348" and latest_snapshot.get("authority_vs_execution_distinction_preserved") is True and latest_snapshot.get("economic_authority") is False, "managed-wallet scheduled snapshot manufactured authority")
    require(managed_wallet.get("independent_acceptance_state") == "HOLD_CUSTODY_IDENTITY_SOURCE_WRAPPER_AND_EXECUTION_GATES", "managed-wallet independent HOLD hidden")

    require(planes.get("trustwallet", {}).get("execution_authorized") is False, "Trust Wallet execution activated")
    trustwallet = planes.get("trustwallet", {})
    require(trustwallet.get("hosted_plane_state") == "ACTIVE_HOSTED_READ_QUOTE" and trustwallet.get("control_version") == "1.2.0", "Trust Wallet recovered control state drift")
    require(trustwallet.get("runtime_digest") == "324871d1b93525a833b253d9430a807d86645a0459921eae3096df0f2670b9b3" and trustwallet.get("control_http_state") == "PASS_200", "Trust Wallet runtime binding drift")
    require(trustwallet.get("local_runner_state") == "PERSISTENT_TWAK_PENDING_MANAGED_VAULT_SIGNING_BOUND_SOURCE_UNCERTIFIED" and trustwallet.get("signing_state") == "MANAGED_VAULT_WALLET_BOUND_NO_VALUE_CANARY_PASS", "Trust Wallet persistent/managed signing distinction drift")
    require(trustwallet.get("hosted_signing") is False and trustwallet.get("hosted_broadcast") is False and trustwallet.get("provider_execution_authorized") is False and trustwallet.get("crownthrive_economic_authority_bound") is False and trustwallet.get("execution_authorized") is False, "Trust Wallet signing/broadcast authority manufactured")
    require(planes.get("entitlement_and_fulfillment", {}).get("active_existing_entitlements") == 0, "active entitlement count drift")

    tools = acceptance.get("api_mcp_tool_states")
    require(isinstance(tools, dict), "missing API/MCP states")
    require(tools == {
        "canonical_source": "developers/certification/virality-thriveevergreen-production-integration-2026-08-24.v1.json#api_mcp",
        "canonical_historical_scope_total": 58,
        "canonical_historical_active_count": 11,
        "canonical_historical_staged_count": 6,
        "canonical_historical_disabled_count": 41,
        "live_registry_flag_counts": {"total": 60, "enabled": 13, "disabled": 47},
        "live_registry_observed_at": "2026-08-24T08:33:37.304Z",
        "live_added_since_canonical_historical_scope": [
            {
                "tool_name": "thriveevergreen.money_movement.status",
                "service_id": "thriveevergreen",
                "risk_class": "D0",
                "enabled": True,
                "requires_human_approval": False,
                "created_at": "2026-08-24T07:52:37.817027Z",
                "classification": "READ_STATUS_CONFIGURATION_PROJECTION_NOT_EXECUTION_AUTHORITY",
            },
            {
                "tool_name": "chlom_wallet.agent_wallet.status",
                "service_id": "chlom_wallet",
                "risk_class": "D0",
                "enabled": True,
                "requires_human_approval": False,
                "created_at": "2026-08-24T08:06:17.984922Z",
                "classification": "READ_ONLY_MANAGED_WALLET_STATUS_NOT_SIGNING_OR_EXECUTION_AUTHORITY",
            },
        ],
        "staged_tools_are_registry_disabled": True,
        "enabled_registry_flag_is_execution_authority": False,
        "generalized_dispatch_state": "DISABLED_HOLD_EXACT_MUTATION_CONTRACT",
        "staged_policy_reducer": "developers/scripts/thriveevergreen/production-fabric-policy-reducer.v1.1.ts",
    }, "acceptance API/MCP summary drift")
    canonical_tools = integration_record.get("api_mcp")
    require(isinstance(canonical_tools, dict) and canonical_tools.get("scope_total") == 58, "canonical API/MCP scope drift")
    require(canonical_tools.get("active", {}).get("count") == 11 and len(canonical_tools.get("active", {}).get("tools", [])) == 11, "canonical active-tool count drift")
    require(canonical_tools.get("staged", {}).get("count") == 6 and len(canonical_tools.get("staged", {}).get("tools", [])) == 6, "canonical staged-tool count drift")
    require(canonical_tools.get("disabled", {}).get("count") == 41 and len(canonical_tools.get("disabled", {}).get("tools", [])) == 41, "canonical disabled-tool count drift")
    require("thriveevergreen.publish.dispatch" in canonical_tools.get("disabled", {}).get("tools", []), "generalized dispatch absent from disabled registry")
    require(canonical_tools.get("enabled_flag_is_execution_authority") is False, "enabled flag became execution authority")

    automation = acceptance.get("automation")
    require(isinstance(automation, dict), "missing automation state")
    require(automation.get("duplicate_scheduler_created") is False, "duplicate scheduler created")
    require(automation.get("publisher_slots_per_hour") == 10, "publisher slot count drift")
    require(automation.get("publisher_slot_minutes") == [2, 8, 14, 20, 26, 32, 38, 44, 50, 56], "publisher schedule drift")
    require(automation.get("crown_credits_reconciliation") == "*/10 * * * *", "credit reconcile schedule drift")
    require(automation.get("stablecoin_effective_capability_reconciliation") == "17 */6 * * *", "stablecoin schedule drift")
    require(automation.get("legacy_observer") == "ct-thriveevergreen-hourly-product-cycle-v1 @ 58 * * * *", "legacy observer schedule identity drift")
    acceptance_job = automation.get("commerce_acceptance_snapshot", {})
    require(acceptance_job == {
        "job_id": 143,
        "job_name": "ct-commerce-control-acceptance-snapshot-v1",
        "schedule": "47 * * * *",
        "active": True,
        "run_history": "SUCCEEDED_1_RUN_OBSERVED",
        "latest_run_id": "16414",
        "latest_run_started_at": "2026-08-24T08:47:00.060415Z",
        "latest_run_completed_at": "2026-08-24T08:47:00.117799Z",
        "latest_run_status": "succeeded",
        "latest_run_return": "1 row",
        "snapshot_rows_after_run": 2,
        "fabric_inventory_present": False,
        "same_minute_existing_job_id": 48,
        "same_minute_existing_job_name": "crownthrive-interoperability-hourly-subroute-v1",
        "semantic_duplicate": False,
        "economic_effect": False,
    }, "commerce acceptance snapshot scheduler evidence drift")
    require(automation.get("scheduler_topology_state") == "HOLD_OBSERVER_BUSINESS_RECEIPTS_FAILING_23514_AND_ACCEPTANCE_SNAPSHOT_FIRST_RUN_SUCCEEDED_NOT_IN_V1_FABRIC_INVENTORY_REPOSITORY_SOURCE_ABSENT", "scheduler topology HOLD hidden")
    receipts = acceptance.get("latest_receipts", {})
    wallet_canaries = receipts.get("managed_agent_wallet_canaries", [])
    require([item.get("receipt_type") for item in wallet_canaries] == ["wallet_initialized", "signature_canary", "base_chain_canary"], "managed-wallet canary receipt scope drift")
    require([item.get("evidence_sha256") for item in wallet_canaries] == [
        "64b80e4a6622853fb46ffdc444110cd6521587c7dc39c612e55726e73694e4e3",
        "9600f63e59fcc429e12af45bfcb3fac804dd879ee0907db8f474aa409c203011",
        "8c906a39f18c8cdd4001a8b7c7b3b9757a5c904f7e67d280d212831485b801b3",
    ], "managed-wallet canary evidence digest drift")
    acceptance_snapshot = receipts.get("commerce_acceptance_snapshot", {})
    require(acceptance_snapshot.get("snapshot_id") == "2e3cf817-47d1-4118-a306-c129d056cf94" and acceptance_snapshot.get("schedule_run_id") == "16414", "latest scheduled commerce acceptance snapshot identity drift")
    require(acceptance_snapshot.get("state") == "AUTHORIZED_CONFIGURED_NOT_EXECUTED" and acceptance_snapshot.get("money_movement_execution_count") == 0 and acceptance_snapshot.get("candidate_decision") == acceptance_snapshot.get("checkout_state") == "HOLD" and acceptance_snapshot.get("economic_authority") is False, "commerce acceptance snapshot manufactured execution or authority")
    observer = receipts.get("legacy_observer", {})
    require(observer.get("cron_scheduler_state") == "SUCCEEDED" and observer.get("business_run_state") == "FAILED" and observer.get("business_error_code") == "23514", "observer scheduler/business result distinction hidden")
    require(observer.get("publication_decision") == "HOLD_OBSERVER_ONLY" and observer.get("publication_count") == observer.get("observed_publication_count") == 0 and observer.get("effect_ceiling") == 0, "observer failure manufactured publication or effects")

    security = acceptance.get("security_verification")
    require(isinstance(security, dict), "missing security verification")
    local = security.get("local_native_tests", {})
    require(local.get("full_test_state") == "PASS" and local.get("commerce_tests", 0) >= 137, "native test evidence drift")
    require(security.get("staged_missing_origin_behavior") == "PASS_403_ACROSS_10_ROUTE_LEVEL_TESTS", "staged Origin gate drift")
    edge_summary = security.get("staged_edge_candidate")
    require(isinstance(edge_summary, dict), "staged Edge candidate summary missing")
    require(edge_summary.get("path") == str(EDGE_CANDIDATE_STATE.relative_to(ROOT)), "staged Edge candidate path drift")
    require(edge_candidate.get("state") == edge_summary.get("state") == "STAGED_REPOSITORY_ONLY_NOT_DEPLOYED", "staged Edge deployment state drift")
    require(edge_candidate.get("candidate_version") == edge_summary.get("candidate_version") == "1.1.2-staged-candidate", "staged Edge version drift")
    require(edge_candidate.get("live_edge_function_version") == edge_summary.get("live_edge_function_version") == 4, "live Edge version drift")
    require(edge_candidate.get("live_api_version") == edge_summary.get("live_api_version") == "1.1.1", "live Edge API version drift")
    require(edge_candidate.get("live_state") == edge_summary.get("live_state") == "HOLD_UNCHANGED", "live Edge state was misrepresented")
    canonical_edge_digest = file_sha256(CANONICAL_EDGE_SOURCE)
    require(canonical_edge_digest == edge_candidate.get("canonical_live_source_sha256") == edge_summary.get("canonical_live_source_sha256") == "2a245e6c35c40614da4731c8f8c77ac53fc740c5255ff76601d6fc5aaf29f313", "canonical live Edge source custody drift")
    edge_artifacts = edge_candidate.get("artifact_sha256", {})
    edge_paths = {
        "index_ts": EDGE_CANDIDATE_DIR / "index.ts",
        "control_ts": EDGE_CANDIDATE_DIR / "control.ts",
        "deno_json": EDGE_CANDIDATE_DIR / "deno.json",
        "control_test_ts": EDGE_CANDIDATE_DIR / "control.test.ts",
        "source_contract_test_py": EDGE_CANDIDATE_DIR / "source_contract_test.py",
    }
    require(all(edge_artifacts.get(label) == file_sha256(path) for label, path in edge_paths.items()), "staged Edge artifact digest drift")
    edge_bundle = hashlib.sha256((EDGE_CANDIDATE_DIR / "index.ts").read_bytes() + b"\0" + (EDGE_CANDIDATE_DIR / "control.ts").read_bytes()).hexdigest()
    require(edge_artifacts.get("index_control_bundle") == edge_bundle, "staged Edge bundle digest drift")
    edge_verification = edge_candidate.get("verification", {})
    require(edge_verification.get("node_behavior_tests", {}).get("state") == "PASS" and edge_verification.get("node_behavior_tests", {}).get("passed") == edge_summary.get("behavior_tests_passed") == 15, "staged Edge behavior tests drift")
    require(edge_verification.get("python_source_contract_tests", {}).get("state") == "PASS" and edge_verification.get("python_source_contract_tests", {}).get("passed") == edge_summary.get("source_contract_tests_passed") == 8, "staged Edge source tests drift")
    require(edge_verification.get("node_typescript_syntax_checks", {}).get("state") == "PASS" and edge_verification.get("node_typescript_syntax_checks", {}).get("passed") == edge_summary.get("typescript_syntax_checks_passed") == 2, "staged Edge syntax checks drift")
    require(edge_candidate.get("deployment_authorized") is edge_summary.get("deployment_authorized") is False, "staged Edge deployment authority manufactured")
    require(edge_candidate.get("economic_mutation_authorized") is edge_summary.get("economic_mutation_authorized") is False, "staged Edge economic mutation authority manufactured")
    require(edge_candidate.get("raw_secret_export") is edge_summary.get("raw_secret_export") is False, "staged Edge raw secret export enabled")
    require(edge_candidate.get("verification", {}).get("deno_runtime_check") == edge_summary.get("deno_runtime_check") == "NOT_RUN_DENO_BINARY_UNAVAILABLE_IN_WORKSPACE", "Deno runtime evidence manufactured")
    live = security.get("live_predeployment_canaries", {})
    require(str(live.get("missing_origin_checkout", "")).startswith("FAIL_"), "live missing-Origin defect was hidden")
    security_advisors = security.get("supabase_security_advisors", {})
    require(security_advisors == {"info_count": 6, "warning_count": 0, "error_count": 0, "new_managed_tables_rls_enabled_no_policy_info_count": 3, "info_label_proves_safety": False}, "Supabase security-advisor evidence drift or INFO treated as safety proof")
    performance_advisors = security.get("supabase_performance_advisors", {})
    require(performance_advisors == {"info_count": 621, "warning_count": 0, "error_count": 0, "new_managed_tables_unindexed_foreign_key_info_count": 3, "info_label_proves_safety": False}, "Supabase performance-advisor evidence drift or INFO treated as safety proof")
    matrix = security.get("acceptance_test_matrix")
    require(isinstance(matrix, dict), "missing acceptance test matrix")
    expected_matrix = {
        "exact_origin_cors": "PASS_STAGED_CANONICAL_ORIGIN_REACHES_NORMAL_GATE",
        "wrong_origin_rejection": "PASS_LIVE_AND_STAGED_403",
        "missing_origin_rejection": "FAIL_LIVE_400_PASS_STAGED_403_HOLD_UNTIL_DEPLOYED",
        "malformed_jwt_rejection": "NOT_RUN_HOLD",
        "unauthenticated_checkout": "PASS_LIVE_401_WITH_VALID_PRODUCT_REQUEST",
        "duplicate_idempotency_replay": "PASS_LOCAL_DETERMINISTIC_NO_LIVE_EFFECT",
        "stale_expected_version": "PASS_LOCAL_V1_1_REDUCER",
        "wrong_product": "PASS_LOCAL_REJECTED",
        "wrong_price": "PASS_LOCAL_CLIENT_PRICE_AND_STRIPE_PRICE_ID_TAMPERING_REJECTED_400",
        "wrong_provider_alias": "NOT_RUN_HOLD",
        "amount_mismatch": "PASS_LOCAL_HOLD",
        "currency_mismatch": "NOT_RUN_HOLD",
        "ecac_hold_deny_paths": "PASS_LOCAL_DETERMINISTIC",
        "unauthorized_wallet_signing": "POSITIVE_NO_VALUE_SIGNATURE_PASS_UNAUTHORIZED_SIGN_NEGATIVE_NOT_PROVEN_HOLD",
        "agent_wallet_zero_unattended_ceiling": "PASS_DECLARED_CONTROL_AND_SNAPSHOT_HOLD_PERSISTENT_AND_MANAGED_ENFORCEMENT_NOT_INDEPENDENTLY_CERTIFIED",
        "vault_or_secret_leakage": "PASS_NO_LITERAL_REPOSITORY_OR_PUBLIC_RESPONSE_SECRET_HOLD_MANAGED_VAULT_WRAPPER_ACL_SEPARATION_ROTATION_AND_RECOVERY_SOURCE_UNCERTIFIED",
        "service_role_leakage": "PASS_NEW_MANAGED_TABLE_DIRECT_DML_DENIED_ALL_THREE_ROLES_EXISTING_PRIVILEGED_SERVER_DML_RETAINS_SEPARATE_HOLD",
        "rls_and_actual_grants": "PASS_NEW_MANAGED_TABLES_RLS_ON_NO_POLICIES_DIRECT_DML_DENIED_ANON_AUTH_SERVICE_ROLE_INFO_NOT_SAFETY_PROOF",
        "provider_read_after_write": "ECONOMIC_PROVIDER_READ_AFTER_WRITE_NOT_RUN_HOLD_NON_ECONOMIC_EDGE_SOURCE_PASS_EXACT",
        "rollback_or_compensation": "HOLD_NON_ECONOMIC_EDGE_PRIOR_SOURCES_CAPTURED_NOT_EXECUTED_ECONOMIC_CANARY_NOT_RUN",
    }
    require(matrix == expected_matrix, "acceptance test matrix drift or hidden extra field")
    managed_grants = security.get("actual_grants", {}).get("managed_wallet_tables", {})
    require(managed_grants.get("tables") == [
        "integration_control.agent_wallet_runner_bindings_v1",
        "integration_control.agent_wallet_runner_receipts_v1",
        "integration_control.commerce_control_acceptance_snapshots_v1",
    ], "managed-wallet actual-grant table scope drift")
    require(managed_grants.get("rls_enabled") is True and managed_grants.get("policy_count_each") == 0, "managed-wallet RLS/no-policy evidence hidden")
    for field in ("anon_direct_select_insert_update_delete", "authenticated_direct_select_insert_update_delete", "service_role_direct_select_insert_update_delete"):
        require(managed_grants.get(field) is False, f"managed-wallet direct table privilege unexpectedly granted: {field}")
    managed_routines = security.get("actual_grants", {}).get("managed_wallet_routines", {})
    require(managed_routines == {
        "public_status_functions_anon_and_authenticated_execute": False,
        "public_status_functions_service_role_execute": True,
        "bootstrap_and_snapshot_mutators_anon_authenticated_service_role_execute": False,
        "security_definer": True,
        "search_path_pinned": True,
    }, "managed-wallet routine privilege evidence drift")

    institutional = acceptance.get("institutionalization")
    require(isinstance(institutional, dict), "missing institutionalization state")
    dail = institutional.get("dail", {})
    require(str(dail.get("chain_anchor_state", "")).startswith("HOLD"), "DAIL anchor hold hidden")
    require(isinstance(dail.get("event_count"), int) and dail.get("event_count") >= 1507, "DAIL point-in-time event count predates scheduled acceptance evidence")
    require(isinstance(dail.get("latest_sequence"), int) and dail.get("latest_sequence") >= 1796, "DAIL point-in-time sequence predates scheduled acceptance evidence")
    require(isinstance(dail.get("head_hash"), str) and SHA256_RE.fullmatch(dail["head_hash"]) is not None, "DAIL point-in-time head hash malformed")
    require(isinstance(dail.get("latest_payload_sha256"), str) and SHA256_RE.fullmatch(dail["latest_payload_sha256"]) is not None, "DAIL latest payload digest malformed")
    require(dail.get("historical_integrity_replay_through_sequence") == 1699 and dail.get("current_tail_full_integrity_replay_performed") is False, "DAIL current-tail replay gap hidden")
    require(dail.get("forward_reconciliation_receipt_sequences") == [1741, 1747, 1753] and dail.get("observer_business_failure_sequence") == 1755, "DAIL recovery/observer lineage drift")
    require(dail.get("managed_wallet_receipts") == [
        {
            "sequence": 1767,
            "event_type": "CHLOM_MANAGED_AGENT_WALLET_BOUND_V1",
            "created_at": "2026-08-24T08:20:38.215251Z",
            "payload_sha256": "e3f80f34115e326ae3287b4ecdd01be25cc5e9b61ff0cf18397b83c87aa5c7f2",
            "event_hash": "b3d68d7d1f21bf22c1409a98cba6e95d34639f98f123f41c2797810220ed41ea",
            "chain_anchor_state": "unanchored",
            "signature_ref": None,
        },
        {
            "sequence": 1768,
            "event_type": "COMMERCE_CONTROL_ACCEPTANCE_SNAPSHOT_V1",
            "created_at": "2026-08-24T08:20:38.219176Z",
            "payload_sha256": "6e7d676f90db2e161c69f53c957dddcb6116097554f99e5cb2ca47f09ce7516b",
            "event_hash": "3853fd678b2b38feebece3096eb5cd4d1a1ecefba522141f5ee95710d6abff14",
            "chain_anchor_state": "unanchored",
            "signature_ref": None,
        },
    ], "managed-wallet DAIL receipt binding drift")
    require(dail.get("scheduled_acceptance_snapshot_new_dail_event_observed") is False, "scheduled acceptance snapshot DAIL append was manufactured")
    drive = institutional.get("drive", {})
    require(drive.get("canonical_integration_record_upload_state") == "VERIFIED_PRIVATE_READ_AFTER_WRITE", "canonical Drive custody not verified")
    require(drive.get("acceptance_addendum_upload_state") == "GITHUB_REVIEW_BRANCH_PENDING_OPTIONAL_PRIVATE_CUSTODY", "addendum custody scope hidden")
    evidence_file = custody_receipt.get("evidence_file", {})
    require(evidence_file.get("upload_state") == "success" and evidence_file.get("read_after_write_state") == "verified", "Drive upload/readback receipt drift")
    require(evidence_file.get("download_sha256_match") is True and evidence_file.get("provider_metadata_size_match") is True, "Drive byte/metadata readback drift")
    require(evidence_file.get("public_or_domain_permission_present") is False and evidence_file.get("provider_shared_flag") is False, "Drive custody privacy drift")
    integration_bytes = INTEGRATION_RECORD.read_bytes()
    require(evidence_file.get("source_repository_path") == str(INTEGRATION_RECORD.relative_to(ROOT)), "Drive source path drift")
    require(evidence_file.get("size_bytes") == len(integration_bytes), "Drive receipt byte count is stale")
    require(evidence_file.get("sha256") == hashlib.sha256(integration_bytes).hexdigest(), "Drive receipt SHA-256 is stale")
    require(evidence_file.get("git_blob_sha1") == git_blob_sha1(integration_bytes), "Drive receipt Git blob SHA-1 is stale")
    require(custody_receipt.get("authority", {}).get("receipt_may_manufacture_economic_authority") is False, "Drive receipt manufactured authority")
    github = institutional.get("github", {})
    require(github.get("branch") == "feat/virality-thriveevergreen-production-fabric-20260824", "GitHub branch drift")
    require(github.get("base_ref") == "main", "GitHub base ref drift")
    require(github.get("source_main_head_reconciled") == SUPPORT_LATEST_MAIN_HEAD, "GitHub source-main binding drift")
    require(github.get("pr_base_sha_used_as_current_main_evidence") is False, "GitHub PR base SHA misused as current-main evidence")
    require(github.get("collision_candidate_implementation_head") == SUPPORT_COLLISION_HEAD, "GitHub implementation binding drift")
    require(github.get("initial_custody_head") == SUPPORT_INITIAL_CUSTODY_HEAD, "GitHub initial custody binding drift")
    require(github.get("corrected_custody_head") == SUPPORT_CORRECTION_HEAD, "GitHub corrected custody binding drift")
    require(github.get("workflow_evidence_head") == SUPPORT_COLLISION_HEAD and github.get("observed_workflow_runs") == github.get("observed_workflow_successes") == 5, "historical workflow evidence drift")
    require(github.get("pre_acceptance_parent_head_observed") == SUPPORT_CORRECTION_HEAD, "acceptance parent binding drift")
    require(github.get("pre_acceptance_head_check_state") == "HOLD_FAILURES_PRESENT", "GitHub check failures hidden")
    require(github.get("final_acceptance_head") is None, "uncommitted acceptance cannot claim a final GitHub head")
    require(github.get("final_acceptance_head_checks") == "PENDING_NOT_YET_RUN_HOLD", "final acceptance head check gate hidden")
    require(github.get("pre_acceptance_parent_collision_rtc_state") == "FAIL_CLOSED" and github.get("pre_acceptance_parent_collision_rtc_blocker") == "COLLISION_RTC_GLOBAL_OPEN_PR_317_EXCEEDS_500_FILE_BOUND", "collision RTC blocker hidden")
    require(github.get("pre_acceptance_parent_candidate_contract_collision_tests") == "PASS", "candidate-contract collision tests hidden")
    require(github.get("pre_acceptance_parent_github_advanced_security_state") == "FAIL_UNRESOLVED", "Advanced Security failure hidden")
    require(github.get("prior_published_acceptance_head") == "0e87c8c0d8bf5b7bc7e91a6ef81b845afe16dcc0" and github.get("prior_published_acceptance_head_workflow_runs") == github.get("prior_published_acceptance_head_workflow_successes") == 5, "prior published acceptance workflow readback drift")
    require(github.get("merge_state") == "NOT_MERGED_REVIEW_REQUIRED", "unsafe merge state")
    require(github.get("main_branch_protected") is False, "GitHub protection evidence drift")

    gates = acceptance.get("remaining_human_or_provider_gates")
    require(isinstance(gates, list) and len(gates) >= 10, "remaining gates were hidden")
    for required_gate in (
        "AGENT_E_INDEPENDENT_SECURITY_CERTIFICATION",
        "CERTIFY_GENERALIZED_DISPATCH_EXACT_MUTATION_CONTRACT",
        "COLLISION_RTC_GLOBAL_OPEN_PR_317_EXCEEDS_500_FILE_BOUND",
        "GITHUB_ADVANCED_SECURITY_FAILURE_RESOLUTION",
        "EDGE_CONTROL_EXACT_ORIGIN_AUTH_STREAMING_LIMIT_AND_LEAST_PRIVILEGE_DEPLOYMENT_CERTIFICATION",
        "STATE_FLAP_OR_CONTROL_CONVERGENCE_MONITORING_REQUIRED",
        "CIE_CURRENT_LINK_ASSURANCE_STALE_FOR_LATEST_MAIN_HEAD",
        "CIE_MIGRATION_SOURCE_70356_APPLIED_70845_HISTORY_RECONCILIATION",
        "CIE_POST_DDL_ADVISOR_AND_ACTUAL_FUNCTION_PRIVILEGE_READBACK",
        "CIE_STATUS_OBSERVER_NULL_BOUNDARY_AND_RECEIPT_REVALIDATION_CLOSURE",
        "MONEY_MOVEMENT_PRODUCTION_AUTHORITY_REQUIRES_EXACT_ECAC_PER_EXECUTION_AND_ZERO_UNATTENDED_VALUE",
        "AGENT_WALLET_SYSTEMD_TEMPLATE_USER_AND_WRAPPER_ONLY_EXECUTION_REPAIR",
        "AGENT_WALLET_SYSTEMD_TEMPLATE_AND_EXECUTABLE_MODE_REPAIR",
        "AGENT_WALLET_DISABLE_OR_GOVERN_RAW_TWAK_WATCH_AND_PROVE_EMPTY_AUTOMATION_INVENTORY",
        "AGENT_WALLET_REST_HMAC_ROTATION_AND_WRAPPER_ONLY_ECAC",
        "AGENT_WALLET_PINNED_POLICY_DIGEST_EXACT_ECAC_AND_DESTINATION_VALIDATION",
        "AGENT_WALLET_HEALTH_LEAST_DATA_PARSE_FAIL_CLOSED_AND_NO_VALUE_SIGNING_CANARY",
        "AGENT_WALLET_INSTALLER_PINNING_SECRET_ARGV_KEYCHAIN_AND_RECOVERY_FILE_CUSTODY",
        "AGENT_WALLET_SENSITIVE_CREATE_OUTPUT_TRAP_AND_CUSTODY",
        "AGENT_WALLET_CUSTODY_IDENTITY_COLLISION_PERSISTENT_RUNNER_ONLY_VS_THRIVEBASE_VAULT_SERVER_MANAGED",
        "MANAGED_AGENT_WALLET_DATABASE_MIGRATION_SOURCE_ABSENT_FROM_CURRENT_MAIN_DELTA",
        "MANAGED_AGENT_WALLET_CONTROL_V1_1_EDGE_SOURCE_AND_ROLLBACK_RECEIPT_ABSENT",
        "MANAGED_AGENT_WALLET_EXACT_ECAC_SIGNING_WRAPPER_NOT_INDEPENDENTLY_CERTIFIED",
        "MANAGED_AGENT_WALLET_UNAUTHORIZED_SIGN_NEGATIVE_CANARY_NOT_PROVEN",
        "MANAGED_AGENT_WALLET_PRODUCTION_BROADCAST_PROVIDER_READ_AFTER_WRITE_AND_COMPENSATION_NOT_CERTIFIED",
        "MANAGED_AGENT_WALLET_VAULT_PRINCIPAL_SEPARATION_ROTATION_AND_RECOVERY_READBACK_NOT_PROVEN",
        "ACCEPTANCE_SNAPSHOT_FIRST_RUN_SUCCEEDED_BUT_NOT_IN_FABRIC_INVENTORY_AND_REPOSITORY_SOURCE_ABSENT",
        "LEGACY_OBSERVER_BUSINESS_RECEIPTS_FAIL_23514_DESPITE_PG_CRON_SUCCESS",
        "DAIL_CURRENT_TAIL_FULL_INTEGRITY_REPLAY",
        "DAIL_CHAIN_ANCHORING",
        "DRIVE_STALE_CERTIFICATION_LABELING_OR_ARCHIVAL",
    ):
        require(required_gate in gates, f"missing exact remaining gate: {required_gate}")

    serialized = json.dumps(acceptance, ensure_ascii=False)
    for pattern in (
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"\bsk_(?:live|test)_[A-Za-z0-9]{12,}\b",
        r"\bwhsec_[A-Za-z0-9]{12,}\b",
    ):
        require(re.search(pattern, serialized) is None, "secret-shaped material detected")

    return {
        "status": "PASS",
        "products": product["total"],
        "available": product["available"],
        "hold": product["hold"],
        "deny": product["deny"],
        "native_deployment": binding["native_vm_staged_deployment_state"],
        "generalized_dispatch": dispatch["state"],
        "stripe_connect": connect["state"],
        "observed_records_sha256": observed_digest,
        "authority_projection_materialized_rows_sha256": projection_digest,
        "authority_projection_artifact_sha256": file_sha256(AUTHORITY_PROJECTION),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
