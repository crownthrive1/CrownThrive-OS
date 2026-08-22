#!/usr/bin/env python3
"""Deterministic public-safe release-package generator for CrownThrive credit products."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0.0"
SOURCE_SYSTEM = "commercial-gap-sites-2026-08-21-v1"
BASE_DIMENSIONS = (
    "package_integrity",
    "rights_licensing",
    "pricing_tax",
    "fulfillment",
    "checkout_webhook",
    "entitlement",
    "accessibility",
    "dns_tls",
    "destination_readiness",
)
READY_EXTRA_DIMENSIONS = ("qualified_professional_review",)
FORBIDDEN_KEYS = {
    "secret",
    "token",
    "password",
    "credential",
    "private_key",
    "api_key",
    "vault_secret",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ReleaseFactoryError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def assert_public_safe(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_KEYS:
                raise ReleaseFactoryError(f"forbidden key at {path}.{key}")
            assert_public_safe(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_public_safe(child, f"{path}[{index}]")


def platform_for(product: dict[str, Any]) -> str:
    manifest_platform = str(product.get("platform") or "").strip().lower()
    if manifest_platform in {"launch", "ready", "procure"}:
        return manifest_platform
    sku = str(product.get("sku") or "")
    if sku.startswith("CT-LAUNCH-"):
        return "launch"
    if sku.startswith("CT-READY-"):
        return "ready"
    if sku.startswith("CT-PROCURE-"):
        return "procure"
    raise ReleaseFactoryError(f"unsupported platform for SKU {sku!r}")


def gate(
    key: str,
    sequence: int,
    state: str,
    reasons: Iterable[str],
    *,
    evidence_ref: str | None = None,
    independent: bool = False,
) -> dict[str, Any]:
    if state not in {"pending", "pass", "hold", "fail", "not_applicable"}:
        raise ReleaseFactoryError(f"invalid gate state {state}")
    return {
        "dimension_key": key,
        "sequence": sequence,
        "state": state,
        "reason_codes": list(reasons),
        "evidence_ref": evidence_ref,
        "independent": independent,
    }


def build_release_package(
    product: dict[str, Any],
    surface: dict[str, Any],
    price_band: dict[str, Any],
    *,
    source_system: str = SOURCE_SYSTEM,
) -> dict[str, Any]:
    assert_public_safe(product)
    assert_public_safe(surface)
    assert_public_safe(price_band)

    sku = str(product["sku"])
    platform = platform_for(product)
    version = str(product["version"])
    asset_sha = str(product["asset_sha256"])
    byte_size = int(product["byte_size"])
    review_receipt = str(surface.get("package_review_receipt") or "")
    package_qa = str(surface.get("package_qa") or "")
    integrity_pass = bool(SHA256_RE.fullmatch(asset_sha) and byte_size > 0 and review_receipt and package_qa == "PASS")

    dimensions = list(BASE_DIMENSIONS)
    if platform == "ready":
        dimensions.extend(READY_EXTRA_DIMENSIONS)

    gates = [
        gate(
            "package_integrity",
            1,
            "pass" if integrity_pass else "hold",
            ["EXISTING_PACKAGE_QA_AND_EXACT_ASSET_HASH_VERIFIED"]
            if integrity_pass
            else ["PACKAGE_INTEGRITY_EVIDENCE_INCOMPLETE"],
            evidence_ref=review_receipt or None,
            independent=integrity_pass,
        ),
        gate("rights_licensing", 2, "hold", ["RIGHTS_LICENSE_PENDING_CHLOM"]),
        gate(
            "pricing_tax",
            3,
            "hold",
            ["CREDIT_PRICE_COMPARABLES_PENDING", "TAX_CLASSIFICATION_PENDING", "PRICE_AUTHORITY_PENDING"],
        ),
        gate(
            "fulfillment",
            4,
            "hold",
            ["PRIVATE_FULFILLMENT_OBJECT_MISSING", "DELIVERY_CANARY_PENDING", "ROLLBACK_READBACK_PENDING"],
        ),
        gate(
            "checkout_webhook",
            5,
            "hold",
            ["CREDIT_OFFER_BINDING_MISSING", "WEBHOOK_IDEMPOTENCY_CANARY_PENDING", "CHECKOUT_REMAINS_CLOSED"],
        ),
        gate(
            "entitlement",
            6,
            "hold",
            ["OFFER_RELEASE_BINDING_MISSING", "LICENSE_ACCEPTANCE_CANARY_PENDING", "ENTITLEMENT_DELIVERY_CHAIN_PENDING"],
        ),
        gate(
            "accessibility",
            7,
            "hold",
            ["EXACT_MOBILE_VIEWPORT_REVIEW_PENDING", "KEYBOARD_AND_ASSISTIVE_TECH_REVIEW_PENDING", "NO_CONFORMANCE_CLAIM"],
        ),
        gate("dns_tls", 8, "hold", ["CUSTOM_DOMAIN_DNS_TLS_UNVERIFIED", "CANONICAL_ROUTE_READBACK_PENDING"]),
        gate(
            "destination_readiness",
            9,
            "hold",
            ["CHATGPT_SITES_DYNAMIC_FEED_CONSUMER_UNVERIFIED", "DIRECT_PROVIDER_WRITE_NOT_AUTHORIZED"],
        ),
    ]
    if platform == "ready":
        gates.append(
            gate(
                "qualified_professional_review",
                10,
                "hold",
                ["QUALIFIED_PROFESSIONAL_SCOPE_REVIEW_PENDING", "NO_PROFESSIONAL_CONCLUSION_AUTHORIZED"],
            )
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "sku": sku,
        "title": product["title"],
        "product_type": product.get("product_type", "toolkit"),
        "asset_version": version,
        "asset_sha256": asset_sha,
        "asset_byte_size": byte_size,
        "platform": platform,
        "platform_id": surface["platform_id"],
        "surface_id": surface["surface_id"],
        "provider_url": surface["provider_url"],
        "preferred_custom_domain": surface.get("preferred_custom_domain"),
        "credit_only": True,
        "checkout_mode": "credits_only",
        "checkout_state": "closed",
        "stripe_objects_created": False,
        "candidate_credit_band": {
            "policy_version": price_band["policy_version"],
            "state": "hold_pending_comparables_and_authority",
            "minimum_credits": price_band["minimum_credits"],
            "target_credits": price_band["target_credits"],
            "maximum_credits": price_band["maximum_credits"],
            "minimum_comparables": price_band["minimum_comparables"],
            "minimum_sources": price_band["minimum_sources"],
        },
        "tax_profile_candidate": product.get("tax_profile_candidate", "document_download"),
        "rights_state": "hold",
        "fulfillment_state": "hold_private_object_missing",
        "entitlement_state": "hold",
        "accessibility_state": surface.get("accessibility_state", "practices_tested_not_conformance_claim"),
        "dns_tls_state": "hold_custom_domain_unverified",
        "destination_state": "hold_feed_consumer_unverified",
        "governed_acceptance_state": "waiting_for_all_certifications_then_sovereign_vote",
        "required_dimensions": dimensions,
        "source_system": source_system,
        "workflow": {
            "originating_agent": "ct.agent.commercial-release-packager",
            "independent_certifier": "ct.chlom.agent.release-certifier",
            "autopublish_policy": "ct.site.autopublish.v1",
            "publisher_adapter": "ct.adapter.dynamic-feed.v1",
            "direct_sites_provider_write": False,
            "read_after_write_required": True,
            "rollback_required": True,
        },
        "gates": gates,
    }
    manifest["package_sha256"] = sha256_json(manifest)
    assert_public_safe(manifest)
    return manifest


def generate(input_payload: dict[str, Any]) -> dict[str, Any]:
    assert_public_safe(input_payload)
    surfaces = input_payload["surfaces"]
    price_bands = input_payload["price_bands"]
    source_system = input_payload.get("source_system", SOURCE_SYSTEM)
    packages: list[dict[str, Any]] = []
    for product in sorted(input_payload["products"], key=lambda row: row["sku"]):
        platform = platform_for(product)
        product_type = product.get("product_type", "toolkit")
        packages.append(
            build_release_package(product, surfaces[platform], price_bands[product_type], source_system=source_system)
        )

    output = {
        "schema_version": SCHEMA_VERSION,
        "source_system": source_system,
        "package_count": len(packages),
        "packages": packages,
        "direct_provider_write": False,
        "checkout_enabled": False,
        "sovereign_votes_created": False,
    }
    output["output_sha256"] = sha256_json(output)
    assert_public_safe(output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    generated = generate(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
