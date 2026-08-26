#!/usr/bin/env python3
"""Validate a Sacred History execution receipt without promoting held work."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "developers/manifests/sacred-history-execution-readback.2026-08-26.v1.json"
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def no_constant(value: str) -> None:
    fail(f"non-finite JSON constant is not allowed: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def section(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        fail(f"missing or invalid section: {key}")
    return value


def require_equal(mapping: dict[str, Any], key: str, expected: Any, scope: str) -> None:
    if mapping.get(key) != expected:
        fail(f"{scope}.{key} drift: expected {expected!r}, got {mapping.get(key)!r}")


def require_not_pass(mapping: dict[str, Any], key: str, scope: str) -> None:
    value = str(mapping.get(key, ""))
    if value == "PASS" or value.startswith("PASS_"):
        fail(f"unsupported PASS in {scope}.{key}: {value}")


def main() -> int:
    if not MANIFEST.is_file():
        fail(f"missing manifest: {MANIFEST.relative_to(ROOT)}")

    raw = MANIFEST.read_text(encoding="utf-8")
    data = json.loads(raw, object_pairs_hook=unique_object, parse_constant=no_constant)
    if not isinstance(data, dict):
        fail("manifest root must be an object")

    for key in (
        "authority",
        "production_baseline",
        "changes_made",
        "sacred_history_routes",
        "traditions",
        "sacred_text_registry",
        "source_provenance",
        "slavery_history",
        "knowledge_graph",
        "evidence_receipts",
        "governance",
        "commerce",
        "stripe_wallet_partner_circle",
        "payment_and_entitlement_regression",
        "security",
        "mobile_accessibility_search_seo",
        "update_pipeline",
        "institutionalization",
        "rollback",
    ):
        section(data, key)

    require_equal(data, "schema_version", "1.0.0", "manifest")
    require_equal(data, "manifest_version", "1.0.0", "manifest")
    require_equal(
        data,
        "manifest_id",
        "ct.manifest.sacred-history-execution-readback.2026-08-26.v1",
        "manifest",
    )
    require_equal(data, "canonical_content_id", "ct.content.sacred-history", "manifest")
    require_equal(data, "institutional_phase", "3", "manifest")
    require_equal(data, "visibility", "public", "manifest")

    authority = section(data, "authority")
    for key, expected in (
        ("autonomy_ceiling", "A2"),
        ("delegation_ceiling", "D2"),
        ("d3_human_reserved", True),
        ("self_approval_allowed", False),
        ("economic_authority_manufacture_allowed", False),
    ):
        require_equal(authority, key, expected, "authority")

    baseline = section(data, "production_baseline")
    require_equal(baseline, "global_storefront_hold", False, "production_baseline")
    require_equal(
        baseline,
        "current_production_deployment_id",
        None,
        "production_baseline",
    )
    for key in (
        "existing_reader_not_mutated_by_this_pass",
        "existing_storefront_not_mutated_by_this_pass",
        "existing_stripe_rail_not_mutated_by_this_pass",
        "existing_credit_core_not_mutated_by_this_pass",
        "existing_entitlements_not_mutated_by_this_pass",
    ):
        require_equal(baseline, key, True, "production_baseline")
    require_equal(
        baseline,
        "existing_entitlements_end_to_end_reverified_this_pass",
        False,
        "production_baseline",
    )

    routes = section(data, "sacred_history_routes")
    for key, expected in (
        ("manifest_count", 9),
        ("substantive_public_route_count", 0),
        ("soft_404_fallback_count", 9),
        ("soft_404_http_status", 200),
        ("soft_404_noindex_present", False),
    ):
        require_equal(routes, key, expected, "sacred_history_routes")
    paths = routes.get("paths")
    if not isinstance(paths, list) or len(paths) != 9 or len(set(paths)) != 9:
        fail("Sacred History routes must contain nine unique paths")
    if any(not isinstance(path, str) or not path.startswith("/sacred-history") for path in paths):
        fail("Sacred History route namespace drift")

    traditions = section(data, "traditions")
    require_equal(traditions, "internal_knowledge_graph_candidate_count", 60, "traditions")
    require_equal(traditions, "public_count", 0, "traditions")
    require_equal(traditions, "research_state", "scoped", "traditions")
    classified_names: list[str] = []
    for key, expected in (
        ("denominations", 4),
        ("movements", 7),
        ("practices", 5),
        ("religious_communities", 7),
        ("tradition_records", 37),
    ):
        values = traditions.get(key)
        if not isinstance(values, list) or len(values) != expected:
            fail(f"traditions.{key} count drift")
        classified_names.extend(values)
    if len(classified_names) != 60 or len(set(classified_names)) != 60:
        fail("tradition candidate identities must total 60 unique records")

    texts = section(data, "sacred_text_registry")
    require_equal(texts, "record_count", 5, "sacred_text_registry")
    require_equal(texts, "full_text_ingested_count", 0, "sacred_text_registry")
    text_records = texts.get("records")
    if not isinstance(text_records, list) or len(text_records) != 5:
        fail("Sacred Text Registry must contain five records")
    if any(record.get("public_reproduction_state") == "cleared" for record in text_records):
        fail("no Sacred Text Registry record is cleared for full reproduction")

    provenance = section(data, "source_provenance")
    require_equal(provenance, "source_record_count", 30, "source_provenance")
    require_equal(provenance, "wave_1_claim_source_count", 9, "source_provenance")
    claim_receipts = provenance.get("claim_evidence_receipts")
    sources = provenance.get("wave_1_sources")
    if not isinstance(claim_receipts, list) or len(claim_receipts) != 9:
        fail("claim/evidence receipt count drift")
    if not isinstance(sources, list) or len(sources) != 9:
        fail("Wave-1 source count drift")
    for key in ("claim_id", "evidence_id", "source_id"):
        values = [receipt.get(key) for receipt in claim_receipts]
        if any(not isinstance(value, str) or not value for value in values):
            fail(f"missing claim/evidence receipt identifier: {key}")
        if len(set(values)) != 9:
            fail(f"claim/evidence receipt identifiers must be unique: {key}")
    if any("claim_class" in source for source in sources):
        fail("claim classes belong to atomic claim receipts, not source records")
    for source in sources:
        if source.get("institution") == "UNESCO":
            require_equal(source, "rights_state", "link_cite_only", "UNESCO source")
            require_equal(source, "commercial_use_state", "hold", "UNESCO source")

    graph = section(data, "knowledge_graph")
    expected_graph = {
        "node_count": 1125,
        "relationship_count": 2000,
        "source_count": 30,
        "claim_count": 9,
        "claim_version_count": 10,
        "evidence_record_count": 9,
        "text_record_count": 5,
        "domain_event_count": 21,
    }
    for key, expected in expected_graph.items():
        require_equal(graph, key, expected, "knowledge_graph")

    changes = section(data, "changes_made")
    for key, expected in (
        ("database_schema_ddl_changes_this_pass", 0),
        ("claim_records_added", graph["claim_count"]),
        ("claim_version_records_added", graph["claim_version_count"]),
        ("evidence_link_records_added", graph["evidence_record_count"]),
        ("sacred_text_registry_records_added", graph["text_record_count"]),
        ("domain_events_added", graph["domain_event_count"]),
        ("new_money_movements", 0),
        ("new_entitlements_issued", 0),
    ):
        require_equal(changes, key, expected, "changes_made")

    governance = section(data, "governance")
    require_equal(governance, "evidence_review", "PASS_WITH_CONDITIONS", "governance")
    require_equal(
        governance,
        "cie_review",
        "HOLD_PENDING_INDEPENDENT_REVIEW",
        "governance",
    )
    require_equal(
        governance,
        "chlom_review",
        "HOLD_PENDING_EXACT_ITEM_AND_PRODUCT_RIGHTS",
        "governance",
    )
    for key in (
        "public_claim_count",
        "public_tradition_count",
        "unsupported_scriptural_crosswalks_created",
        "invented_scripture_created",
    ):
        require_equal(governance, key, 0, "governance")
    require_equal(
        governance,
        "restricted_or_initiatory_corpus_reproduced",
        False,
        "governance",
    )

    receipts = section(data, "evidence_receipts")
    review_receipts = section(receipts, "thrivebase_review_receipts")
    canary_receipts = section(receipts, "commerce_canary_receipts")
    repository = section(receipts, "repository")
    if len(review_receipts) != 3 or len(set(review_receipts.values())) != 3:
        fail("three unique ThriveBase review receipts are required")
    if len(canary_receipts) != 5 or len(set(canary_receipts.values())) != 5:
        fail("five unique commerce canary receipts are required")
    require_equal(repository, "pull_request_number", 496, "evidence_receipts.repository")
    require_equal(repository, "pull_request_state", "draft_open", "evidence_receipts.repository")

    commerce = section(data, "commerce")
    expected_commerce = {
        "product_target": 1000,
        "product_blueprint_count": 1000,
        "claim_linked_blueprint_count": 160,
        "strict_finished_product_count": 0,
        "product_artifact_count": 0,
        "drive_product_master_count": 0,
        "issued_sku_count": 0,
        "issued_license_count": 0,
        "activated_price_count": 0,
        "new_entitlement_count": 0,
        "commerce_binding_count": 0,
        "target_progress_percent": 0,
    }
    for key, expected in expected_commerce.items():
        require_equal(commerce, key, expected, "commerce")
    require_equal(commerce, "global_storefront_hold", False, "commerce")
    require_equal(
        commerce,
        "thriveevergreen_integration_state",
        "NO_NEW_PRODUCT_BINDINGS_OR_SKUS",
        "commerce",
    )

    stripe = section(data, "stripe_wallet_partner_circle")
    require_equal(stripe, "stripe_connect_production_authority", False, "stripe_wallet_partner_circle")
    require_equal(
        stripe,
        "stripe_connect_oauth_connection_state",
        "HOLD_UNEXPECTED_OAUTH_AUTHORITY_REGRESSION",
        "stripe_wallet_partner_circle",
    )
    require_equal(stripe, "partner_settlement_authorized", False, "stripe_wallet_partner_circle")
    require_equal(stripe, "live_money_movement_executed", False, "stripe_wallet_partner_circle")
    require_not_pass(stripe, "live_credit_topup_acceptance", "stripe_wallet_partner_circle")

    regression = section(data, "payment_and_entitlement_regression")
    require_equal(regression, "schema_uniqueness_constraints_present", "PASS", "regression")
    for key in (
        "duplicate_webhook_runtime_replay_current",
        "wallet_topup_credit_once",
        "successful_license_issue_current",
        "entitlement_issue_once_current",
        "protected_download_with_active_entitlement",
        "expired_or_invalid_entitlement_denial",
        "live_refund_reconciliation",
        "grandfathered_rail_functional_acceptance",
    ):
        require_not_pass(regression, key, "payment_and_entitlement_regression")
    require_equal(regression, "current_active_entitlement_count", 0, "regression")

    security = section(data, "security")
    control = section(security, "checkout_internal_table_control")
    for key, expected in (
        ("row_level_security_enabled", False),
        ("policy_count", 0),
        ("row_count", 0),
        ("anonymous_schema_usage", False),
        ("authenticated_schema_usage", False),
        ("anonymous_table_dml", False),
        ("authenticated_table_dml", False),
        ("public_exposure_evidenced", False),
        ("blind_rls_enablement_applied", False),
        ("new_direct_checkout_activation_blocked_pending_security_review", True),
    ):
        require_equal(control, key, expected, "security.checkout_internal_table_control")
    require_equal(security, "rotation_or_revocation_verified", False, "security")
    require_equal(security, "raw_secret_values_in_manifest", False, "security")
    require_equal(security, "existing_payment_rail_global_hold", False, "security")

    discovery = section(data, "mobile_accessibility_search_seo")
    require_equal(discovery, "mobile_sacred_history_test", "NOT_RUN_NO_SUBSTANTIVE_ROUTE", "discovery")
    require_equal(discovery, "accessibility_sacred_history_test", "NOT_RUN_NO_SUBSTANTIVE_ROUTE", "discovery")
    require_equal(discovery, "new_sacred_history_search_index", "NOT_DEPLOYED", "discovery")
    require_equal(discovery, "sacred_history_soft_404_indexability", "FAIL_NOINDEX_MISSING", "discovery")

    updates = section(data, "update_pipeline")
    for key, expected in (
        ("monitor_record_count", 8),
        ("observation_record_count", 0),
        ("active_automated_monitor_count", 0),
        ("state", "CANDIDATE_NOT_OPERATING"),
        ("self_publication_allowed", False),
    ):
        require_equal(updates, key, expected, "update_pipeline")

    institution = section(data, "institutionalization")
    require_equal(institution, "subagents_spawned", 3, "institutionalization")
    require_equal(institution, "autonomous_publication_agents", 0, "institutionalization")
    if len(institution.get("subagent_runs", [])) != 3:
        fail("three bounded advisory subagent run records are required")
    for key, expected_path in (
        (
            "documentation_files_changed",
            "platforms/kjv-visualized-sermon-toolkit-institutional-registry.mdx",
        ),
        (
            "manifest_files_created",
            "developers/manifests/sacred-history-execution-readback.2026-08-26.v1.json",
        ),
        (
            "validation_scripts_created",
            "scripts/validate_sacred_history_execution_readback_v1.py",
        ),
    ):
        values = institution.get(key)
        if values != [expected_path]:
            fail(f"institutionalization path drift: {key}")

    rollback = section(data, "rollback")
    require_equal(rollback, "additive_only", True, "rollback")
    require_equal(rollback, "existing_storefront_global_hold", False, "rollback")
    require_equal(rollback, "replacement_site_created", False, "rollback")

    forbidden_patterns = (
        r"sk_(?:live|test)_",
        r"rk_(?:live|test)_",
        r"whsec_",
        r"ghp_[A-Za-z0-9]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
        r"AIza[0-9A-Za-z_-]{30,}",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        r"SUPABASE_SERVICE_ROLE_KEY",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"(?i)authorization\s*[:=]\s*bearer\s+\S+",
        r"(?i)(?:api[_ -]?key|client[_ -]?secret|password)\s*[:=]\s*[^\s,\"}]+",
        r"(?i)postgres(?:ql)?://[^\s\"]+",
    )
    for pattern in forbidden_patterns:
        if re.search(pattern, raw):
            fail(f"restricted secret pattern detected: {pattern}")

    print(
        json.dumps(
            {
                "status": "PASS_MANIFEST_INVARIANTS_ONLY",
                "manifest_id": data["manifest_id"],
                "global_storefront_hold": baseline["global_storefront_hold"],
                "substantive_sacred_history_routes": routes[
                    "substantive_public_route_count"
                ],
                "strict_finished_products": commerce["strict_finished_product_count"],
                "cie": governance["cie_review"],
                "chlom": governance["chlom_review"],
                "checkout_security_state": control["registry_finding_state"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
