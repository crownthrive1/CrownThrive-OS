#!/usr/bin/env python3
"""Validate the dated Sacred History execution readback without promoting held work."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = (
    ROOT
    / "developers/manifests/sacred-history-execution-readback.2026-08-26.v1.json"
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> int:
    if not MANIFEST.is_file():
        fail(f"missing manifest: {MANIFEST.relative_to(ROOT)}")

    raw = MANIFEST.read_text(encoding="utf-8")
    data = json.loads(raw)

    if data.get("schema_version") != "1.0.0":
        fail("schema version drift")
    if data.get("canonical_content_id") != "ct.content.sacred-history":
        fail("canonical content identity drift")
    if data.get("institutional_phase") != "3":
        fail("institutional phase drift")

    authority = data["authority"]
    if authority.get("autonomy_ceiling") != "A2":
        fail("autonomy ceiling drift")
    if authority.get("delegation_ceiling") != "D2":
        fail("delegation ceiling drift")
    if authority.get("d3_human_reserved") is not True:
        fail("D3 must remain human-reserved")
    if authority.get("self_approval_allowed") is not False:
        fail("self-approval prohibition drift")
    if authority.get("economic_authority_manufacture_allowed") is not False:
        fail("economic authority prohibition drift")

    baseline = data["production_baseline"]
    if baseline.get("global_storefront_hold") is not False:
        fail("existing storefront must not enter a global hold")
    for key in (
        "existing_reader_preserved",
        "existing_storefront_preserved",
        "existing_stripe_rail_preserved",
        "existing_credit_core_preserved",
        "existing_entitlements_preserved",
    ):
        if baseline.get(key) is not True:
            fail(f"production-preservation drift: {key}")

    routes = data["sacred_history_routes"]
    if routes.get("manifest_count") != 9:
        fail("route-manifest count drift")
    if routes.get("substantive_public_route_count") != 0:
        fail("soft-404 routes may not be reported as substantive")
    if routes.get("soft_404_fallback_count") != 9:
        fail("soft-404 count drift")
    if routes.get("soft_404_noindex_present") is not False:
        fail("the current noindex defect must remain explicit")

    graph = data["knowledge_graph"]
    expected_graph = {
        "node_count": 1125,
        "relationship_count": 2000,
        "source_count": 30,
        "claim_count": 9,
        "claim_version_count": 9,
        "evidence_record_count": 9,
        "text_record_count": 5,
        "domain_event_count": 18,
    }
    for key, expected in expected_graph.items():
        if graph.get(key) != expected:
            fail(f"knowledge-graph count drift: {key}")

    governance = data["governance"]
    if governance.get("cie_review") != "HOLD_PENDING_INDEPENDENT_REVIEW":
        fail("CIE hold drift")
    if governance.get("chlom_review") != "HOLD_PENDING_EXACT_ITEM_AND_PRODUCT_RIGHTS":
        fail("CHLOM hold drift")
    if governance.get("public_claim_count") != 0:
        fail("unreviewed claims may not be public")
    if governance.get("invented_scripture_created") != 0:
        fail("invented scripture prohibition drift")

    commerce = data["commerce"]
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
        if commerce.get(key) != expected:
            fail(f"product-completion accounting drift: {key}")
    if commerce.get("global_storefront_hold") is not False:
        fail("SKU-level holds must not become a global storefront hold")

    security = data["security"]
    if security.get("direct_checkout_intents_rls") != "DISABLED":
        fail("current RLS defect must remain explicit until separately remediated")
    if security.get("blind_rls_enablement_applied") is not False:
        fail("blind RLS enablement is not authorized")
    if security.get("raw_secret_values_in_manifest") is not False:
        fail("manifest secret-state drift")

    updates = data["update_pipeline"]
    if updates.get("monitor_record_count") != 8:
        fail("source-monitor count drift")
    if updates.get("observation_record_count") != 0:
        fail("unobserved monitors may not be reported as operating")
    if updates.get("active_automated_monitor_count") != 0:
        fail("candidate monitors may not be reported as active")

    forbidden_patterns = (
        r"sk_live_",
        r"rk_live_",
        r"whsec_",
        r"SUPABASE_SERVICE_ROLE_KEY",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"(?i)access[_ -]?token\s*[:=]",
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
                "open_security_defect": security["direct_checkout_security_finding"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
