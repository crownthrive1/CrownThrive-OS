#!/usr/bin/env python3
"""Validate the public-safe Sacred History Wave 1 release projection."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/sacred-history-release-packet.v1.json"
SOURCES = ROOT / "knowledge/sacred-history-source-register.mdx"
ASSETS = ROOT / "knowledge/curriculum-study-asset-register.mdx"
CHANGELOG = ROOT / "changelog/sacred-history-wave-1-institutionalization-2026-08-24.mdx"
NAV = ROOT / "docs.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def read(path: Path) -> str:
    if not path.is_file():
        fail(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(text: str, fragment: str, source: Path) -> None:
    if fragment not in text:
        fail(f"missing {fragment!r} in {source.relative_to(ROOT)}")


def main() -> int:
    manifest = json.loads(read(MANIFEST))
    source_text = read(SOURCES)
    asset_text = read(ASSETS)
    changelog_text = read(CHANGELOG)

    expected = {
        "schema_version": "1.0.0",
        "manifest_id": "ct.manifest.sacred-history-release-packet.v1",
        "manifest_version": "1.0.0",
        "canonical_content_id": "ct.content.sacred-history",
        "content_identity_state": "owner_validation_required",
        "directive_relation": "additive_continuation",
        "public_projection": True,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail(f"identity/state drift: {key}")

    authority = manifest["authority"]
    if authority.get("autonomy_ceiling") != "A2" or authority.get("delegation_ceiling") != "D2":
        fail("authority must remain A2/D2")
    for key in ("self_approval_allowed", "authority_manufacture_allowed", "economic_authority_manufacture_allowed"):
        if authority.get(key) is not False:
            fail(f"authority prohibition drift: {key}")
    if authority.get("d3_human_reserved") is not True:
        fail("D3 must remain human-reserved")

    baseline = manifest["production_baseline"]
    if baseline.get("url") != "https://kjvsermontoolkit.crownthrive.com":
        fail("production baseline URL drift")
    if baseline.get("state") != "preserved_live" or baseline.get("new_deployment_created") is not False:
        fail("preserved production baseline drift")

    source_ids = set(re.findall(r"^\| `(S\d+)` \|", source_text, flags=re.MULTILINE))
    expected_source_ids = {f"S{value}" for value in range(124, 132)}
    if not expected_source_ids.issubset(source_ids):
        fail("Sacred History source continuation must include S124-S131")
    if any(f"S{value}" in source_ids for value in range(27, 124)):
        fail("Sacred History source continuation collides with S27-S123")
    refs = manifest["source_lineage"]["public_source_refs"]
    if len(refs) != len(set(refs)) or set(refs) != expected_source_ids:
        fail("manifest source reference drift")
    if not set(refs).issubset(source_ids):
        fail("manifest references source IDs absent from continuation")

    domain = manifest["domain_foundation"]
    required_counts = {
        "table_count": 21,
        "security_invoker_view_count": 1,
        "rls_enabled_table_count": 21,
        "sacred_history_security_advisor_lint_count": 0,
        "canonical_entity_count": 1125,
        "relationship_count": 2000,
        "claim_record_count": 0,
    }
    for key, value in required_counts.items():
        if domain.get(key) != value:
            fail(f"domain evidence drift: {key}")

    routes = manifest["routes"]
    if routes.get("planned_count") != len(routes.get("planned", [])) or routes.get("planned_count") != 9:
        fail("route count drift")
    if routes.get("production_published_count") != 0 or routes.get("candidate_state") != "SOURCE_CHECKOUT_BLOCKED":
        fail("route publication must remain held")
    if routes.get("existing_kjv_reader_preserved") is not True or routes.get("existing_storefront_preserved") is not True:
        fail("existing product preservation removed")

    claims = manifest["claims"]
    if claims != {
        "record_count": 0,
        "state": "NOT_CREATED",
        "versioning_contract_present": True,
        "approved_public_claim_count": 0,
    }:
        fail("claim state must remain explicit and zero")

    cie = manifest["cie_review"]
    if cie.get("subject_type") not in {"content", "offer_use"}:
        fail("CIE subject type must be content or offer_use")
    if cie.get("state") != "HOLD_PENDING_PROTECTED_REVIEW" or cie.get("pass_receipt_count") != 0:
        fail("public projection cannot manufacture CIE PASS")
    if cie.get("authority_effect") != "none" or cie.get("public_contract_can_manufacture_pass") is not False:
        fail("CIE authority boundary drift")

    chlom = manifest["chlom_rights"]
    if chlom.get("permission_state") != "HOLD" or chlom.get("allow_receipt_count") != 0:
        fail("CHLOM must remain HOLD without an ALLOW receipt")
    if chlom.get("cie_pass_substitutes_for_chlom_allow") is not False:
        fail("CIE may not substitute for CHLOM")

    products = manifest["product_factory"]
    if products.get("blueprint_count") != 1000 or products.get("strict_finished_product_count") != 0:
        fail("product blueprint/completion accounting drift")
    for key in (
        "verified_product_asset_count",
        "drive_master_asset_count",
        "issued_sku_count",
        "issued_license_count",
        "activated_price_count",
        "configured_new_entitlement_count",
    ):
        if products.get(key) != 0:
            fail(f"unverified completion evidence introduced: {key}")
    if products.get("commercial_state") != "HOLD" or products.get("lifecycle_state") != "sourcing":
        fail("candidate lifecycle/commercial separation drift")

    evergreen = manifest["thriveevergreen"]
    if evergreen.get("candidate_state") != "NOT_SUBMITTED" or evergreen.get("ecac_state") != "HOLD":
        fail("ThriveEvergreen candidate/ECAC state drift")
    if evergreen.get("economic_effects_enabled") is not False or evergreen.get("provider_ids_are_aliases") is not True:
        fail("economic/provider identity boundary drift")

    commerce = manifest["payment_entitlement_fulfillment"]
    if commerce.get("new_checkout_enabled") is not False:
        fail("new checkout may not be enabled")
    for key in ("provider_writes", "wallet_or_credit_movements", "entitlements_issued"):
        if commerce.get(key) != 0:
            fail(f"economic effect must remain zero: {key}")
    for key in ("new_payment_state", "new_entitlement_state", "new_fulfillment_state"):
        if commerce.get(key) != "NOT_CONFIGURED":
            fail(f"payment/entitlement/fulfillment state drift: {key}")

    wallet = manifest["wallet"]
    if wallet.get("unattended_value_ceiling") != 0 or wallet.get("execution_count") != 0:
        fail("wallet execution/value ceiling must remain zero")
    if wallet.get("existing_lanes_preserved") is not True:
        fail("existing wallet/credit lanes must remain preserved")

    run_packet = manifest["run_packet"]
    for key in ("run_id", "repository", "repository_baseline_sha", "acceptance_tests", "rollback", "unresolved", "next_run"):
        if key not in run_packet:
            fail(f"run packet missing: {key}")
    if run_packet["acceptance_tests"].get("strict_product_completion") != "PASS_ZERO":
        fail("strict completion acceptance drift")

    rollback = manifest["rollback"]
    if rollback.get("additive_only") is not True or rollback.get("sku_level_isolation") is not True:
        fail("additive/SKU isolation removed")
    if rollback.get("global_storefront_hold") is not False or rollback.get("existing_payment_rail_migration") is not False:
        fail("global hold or payment migration introduced")

    require(asset_text, "ct.content.sacred-history", ASSETS)
    for fragment in ("PASS", "OPEN / NOT PASS", "BLOCKED / NOT PASS", "zero completed SKUs", "no global hold"):
        require(changelog_text, fragment, CHANGELOG)

    nav = json.loads(read(NAV))
    pages: list[str] = []
    for tab in nav.get("navigation", {}).get("tabs", []):
        for group in tab.get("groups", []):
            pages.extend(group.get("pages", []))
    for route in (
        "knowledge/sacred-history-source-register",
        "changelog/sacred-history-wave-1-institutionalization-2026-08-24",
    ):
        if pages.count(route) != 1:
            fail(f"navigation route must appear exactly once: {route}")

    public_text = "\n".join([read(MANIFEST), source_text, asset_text, changelog_text])
    for pattern in (
        r"SUPABASE_SERVICE_ROLE_KEY",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"(?i)service[_ -]?role[_ -]?(?:key|secret)\s*[:=]",
        r"(?i)access[_ -]?token\s*[:=]",
        r"(?i)provider[_ -]?(?:customer|payment|session|task)[_ -]?id\s*[:=]",
        r"(?i)wallet[_ -]?owner[_ -]?(?:email|name|id)\s*[:=]",
    ):
        if re.search(pattern, public_text):
            fail(f"secret/restricted identifier pattern detected: {pattern}")
    for claim in (
        "1000 finished products",
        "1,000 finished products",
        "fully certified",
        "rights cleared",
        "sacred history is live",
    ):
        if claim in public_text.lower():
            fail(f"unsupported claim detected: {claim}")

    print(json.dumps({
        "status": "PASS",
        "manifest_id": manifest["manifest_id"],
        "production_baseline": baseline["deployment_version"],
        "source_refs": len(refs),
        "planned_routes": routes["planned_count"],
        "published_new_routes": routes["production_published_count"],
        "blueprints": products["blueprint_count"],
        "strict_finished_products": products["strict_finished_product_count"],
        "cie": cie["state"],
        "chlom": chlom["permission_state"],
        "ecac": evergreen["ecac_state"],
        "economic_effects": "DENY",
        "global_storefront_hold": rollback["global_storefront_hold"],
        "nav_entries": 2,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
