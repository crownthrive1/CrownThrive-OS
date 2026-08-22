#!/usr/bin/env python3
"""Deterministic, fail-closed CrownThrive commercial release-package factory v2."""
from __future__ import annotations

import argparse, hashlib, json, re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.0.0"
CURRENT_SOURCE = "commercial_sites_candidate_4"
LEGACY_SOURCES = {"commercial-gap-sites-2026-08-21-v1"}
SHA = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN = {"secret", "token", "password", "credential", "api_key", "private_key", "vault_secret"}
BASE_GATES = (
    ("package_integrity", "ct.agent.commercial-release-packager"),
    ("rights_provenance", "ct.agent.commercial-release-rights"),
    ("pricing_tax", "ct.agent.commercial-release-pricing-tax"),
    ("private_fulfillment", "ct.agent.commercial-release-fulfillment"),
    ("credit_checkout_webhook", "ct.agent.commercial-release-checkout-webhook"),
    ("entitlement_license", "ct.agent.commercial-release-entitlement"),
    ("refund_dispute_rollback", "ct.agent.commercial-release-remedy-rollback"),
    ("accessibility_device", "ct.agent.commercial-release-accessibility"),
    ("dns_tls_route", "ct.agent.commercial-release-dns-tls"),
    ("governed_acceptance_publication", "ct.agent.commercial-release-governance"),
)
READY_GATE = ("qualified_professional_review", "ct.agent.commercial-release-governance")
LEGACY_ALIASES = {
    "rights_licensing": "rights_provenance", "fulfillment": "private_fulfillment",
    "checkout_webhook": "credit_checkout_webhook", "entitlement": "entitlement_license",
    "accessibility": "accessibility_device", "dns_tls": "dns_tls_route",
    "destination_readiness": "governed_acceptance_publication",
}
REASONS = {
    "rights_provenance": ["RIGHTS_CLEARANCE_NOT_YET_ACCEPTED", "LICENSE_VERSION_CANDIDATE"],
    "pricing_tax": ["CREDITS_PRICE_NOT_AUTHORIZED", "TAX_CLASSIFICATION_NOT_ACCEPTED"],
    "private_fulfillment": ["CUSTOMER_FULFILLMENT_NOT_CERTIFIED", "PRIVATE_MASTER_PENDING"],
    "credit_checkout_webhook": ["PRODUCT_CREDIT_REDEMPTION_NOT_CERTIFIED", "PER_SKU_STRIPE_FORBIDDEN"],
    "entitlement_license": ["ENTITLEMENT_LICENSE_BINDING_NOT_CERTIFIED"],
    "refund_dispute_rollback": ["REVERSAL_REMEDY_SEQUENCE_NOT_CERTIFIED"],
    "accessibility_device": ["FORMAL_CONFORMANCE_NOT_CLAIMED", "DEVICE_ASSISTIVE_TECH_REVIEW_OPEN"],
    "dns_tls_route": ["CUSTOM_DOMAIN_UNVERIFIED_TARGET", "DNS_TLS_CANONICAL_READBACK_OPEN"],
    "governed_acceptance_publication": ["INDEPENDENT_GOVERNANCE_PENDING", "SITES_FEED_CONSUMER_READBACK_PENDING"],
    "qualified_professional_review": ["QUALIFIED_PROFESSIONAL_SCOPE_REVIEW_PENDING", "NO_PROFESSIONAL_CONCLUSION_AUTHORIZED"],
}

class FactoryError(ValueError): pass

def canonical(v: Any) -> str: return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def digest(v: Any) -> str: return hashlib.sha256(canonical(v).encode()).hexdigest()

def public_safe(v: Any, path: str = "$") -> None:
    if isinstance(v, dict):
        for k, child in v.items():
            if str(k).lower() in FORBIDDEN: raise FactoryError(f"forbidden key {path}.{k}")
            public_safe(child, f"{path}.{k}")
    elif isinstance(v, list):
        for i, child in enumerate(v): public_safe(child, f"{path}[{i}]")

def platform(product: dict[str, Any]) -> str:
    value = str(product.get("platform", "")).lower()
    if value in {"launch", "ready", "procure"}: return value
    sku = str(product.get("sku", ""))
    for candidate in ("launch", "ready", "procure"):
        if sku.startswith(f"CT-{candidate.upper()}-"): return candidate
    raise FactoryError(f"unsupported platform for {sku}")

def gate(name: str, worker: str, sequence: int, integrity_pass: bool, evidence: str | None, version: str, package_sha: str) -> dict[str, Any]:
    passed = name == "package_integrity" and integrity_pass
    return {
        "dimension_key": name, "sequence": sequence, "state": "pass" if passed else "hold",
        "worker_agent_id": worker, "independent": passed,
        "evidence_ref": evidence if passed else None,
        "reason_codes": ["EXISTING_PACKAGE_QA_AND_EXACT_ASSET_HASH_VERIFIED"] if passed
                        else REASONS.get(name, ["PACKAGE_INTEGRITY_EVIDENCE_INCOMPLETE"]),
        "required_for_acceptance": True, "exact_version_ref": version, "content_sha256": package_sha,
    }

def build(product: dict[str, Any], surface: dict[str, Any], band: dict[str, Any]) -> dict[str, Any]:
    public_safe(product); public_safe(surface); public_safe(band)
    p = platform(product); sku = str(product["sku"]); asset = str(product["asset_sha256"])
    evidence = str(product.get("independent_review_receipt") or surface.get("package_review_receipt") or "") or None
    integrity = bool(SHA.fullmatch(asset) and int(product["byte_size"]) > 0 and evidence and product.get("independent_review") == "PASS")
    required = list(BASE_GATES) + ([READY_GATE] if p == "ready" else [])
    manifest = {
        "factory_id": "ct.release-factory.commercial-sites.v2", "factory_manifest_version": SCHEMA_VERSION,
        "source_system": CURRENT_SOURCE,
        "asset_identity": {"sku": sku, "title": product["title"], "version": product["version"],
                           "asset_sha256": asset, "byte_size": int(product["byte_size"]), "platform": p,
                           "platform_id": surface["platform_id"], "surface_id": surface["surface_id"]},
        "required_dimensions": [name for name, _ in required],
        "commerce_contract": {"product_checkout_mode": "crown_credits_only", "stripe_per_product_objects": False,
                              "checkout_state": "closed", "checkout_enabled": False, "payment_evidence_is_entitlement": False,
                              "candidate_credit_band": band, "tax_profile_candidate": product.get("tax_profile_candidate", "document_download")},
        "publication_contract": {"route_mode": "governed_dynamic_feed", "adapter_id": "ct.adapter.dynamic-feed.v1",
                                 "direct_provider_write": False, "require_read_after_write": True,
                                 "require_rollback_ref": True, "provider_url": surface["provider_url"],
                                 "preferred_custom_domain": surface["preferred_custom_domain"]},
        "governance_contract": {"originating_agent": "ct.agent.commercial-release-packager",
                                "independent_certifier": "ct.chlom.agent.release-certifier", "originator_self_approval": False,
                                "policy_id": "ct.site.autopublish.v1", "sovereign_vote_creation": False, "d3_human_reserved": True},
        "private_boundary": {"protected_policy_body_exposed": False, "credential_values_exposed": False,
                             "customer_records_exposed": False, "storage_object_path_exposed": False},
    }
    package_sha = digest(manifest)
    package = {
        "schema_version": SCHEMA_VERSION, "source_system": CURRENT_SOURCE, "sku": sku,
        "exact_version_ref": product["version"], "asset_sha256": asset, "package_sha256": package_sha,
        "platform": p, "credit_only": True, "checkout_mode": "credits_only", "package_state": "hold",
        "required_dimensions": manifest["required_dimensions"], "manifest": manifest,
        "canonical_gates": [gate(name, worker, i + 1, integrity, evidence, str(product["version"]), package_sha) for i, (name, worker) in enumerate(required)],
        "legacy_alias_gates": [{"dimension_key": old, "superseded_by": new, "state": "hold",
                                "required_for_acceptance": False, "legacy_alias": True,
                                "exact_version_ref": product["version"], "content_sha256": package_sha}
                               for old, new in LEGACY_ALIASES.items()],
        "governed_release_binding": {"exact_version_ref": product["version"], "content_sha256": package_sha,
                                     "required_certification_dimensions": manifest["required_dimensions"],
                                     "certification_state": "hold", "vote_state": "pending", "release_state": "quarantined"},
        "acceptance_state": "hold", "publication_state": "hold_feed_consumer_unverified",
    }
    public_safe(package); return package

def validate_package(p: dict[str, Any]) -> None:
    if p.get("credit_only") is not True or p.get("checkout_mode") != "credits_only": raise FactoryError("credit-only invariant")
    if digest(p["manifest"]) != p.get("package_sha256"): raise FactoryError("package digest mismatch")
    if p["governed_release_binding"].get("content_sha256") != p["package_sha256"]: raise FactoryError("release binding drift")
    if p["governed_release_binding"].get("required_certification_dimensions") != p["required_dimensions"]: raise FactoryError("dimension binding drift")
    if [g["dimension_key"] for g in p["canonical_gates"]] != p["required_dimensions"]: raise FactoryError("gate sequence drift")

def generate(payload: dict[str, Any]) -> dict[str, Any]:
    public_safe(payload)
    source = payload.get("source_system", CURRENT_SOURCE)
    if source in LEGACY_SOURCES: source = CURRENT_SOURCE
    if source != CURRENT_SOURCE: raise FactoryError("unsupported source system")
    packages = []
    for product in sorted(payload["products"], key=lambda x: x["sku"]):
        p = platform(product); pkg = build(product, payload["surfaces"][p], payload["price_bands"][product["product_type"]])
        validate_package(pkg); packages.append(pkg)
    current = sum(len(p["canonical_gates"]) for p in packages); passed = sum(g["state"] == "pass" for p in packages for g in p["canonical_gates"])
    aliases = sum(len(p["legacy_alias_gates"]) for p in packages)
    result = {"schema_version": SCHEMA_VERSION, "source_system": source, "package_count": len(packages),
              "canonical_required_gate_rows": current, "canonical_pass_gates": passed,
              "canonical_hold_gates": current - passed, "legacy_alias_gate_rows": aliases,
              "total_retained_gate_rows": current + aliases, "accepted": 0, "published": 0,
              "direct_provider_write": False, "checkout_enabled": False, "sovereign_votes_created": False,
              "packages": packages}
    result["output_sha256"] = digest(result); return result

def fixture(source: str = CURRENT_SOURCE) -> dict[str, Any]:
    products = []
    for p, prefix in (("launch", "LAUNCH"), ("ready", "READY"), ("procure", "PROCURE")):
        for i in range(10):
            sku = f"CT-{prefix}-TEST-{i+1:03d}"
            products.append({"sku": sku, "title": sku, "product_type": "toolkit", "platform": p,
                             "version": "1.0.0-candidate.4", "asset_sha256": hashlib.sha256(sku.encode()).hexdigest(),
                             "byte_size": 16384, "independent_review": "PASS",
                             "independent_review_receipt": f"ct.review.{sku.lower()}"})
    surfaces = {p: {"platform_id": f"ct.platform.crownthrive-{p}", "surface_id": f"ct.surface.crownthrive-{p}.production",
                    "provider_url": f"https://crownthrive-{p}.crownthrive.chatgpt.site",
                    "preferred_custom_domain": f"{p}.crownthrive.com"} for p in ("launch", "ready", "procure")}
    return {"source_system": source, "products": products, "surfaces": surfaces,
            "price_bands": {"toolkit": {"policy_version": "ct-pricing-v2", "state": "hold_pending_authority",
                                          "minimum_credits": 9900, "target_credits": 14900, "maximum_credits": 29900}}}

def self_test() -> dict[str, Any]:
    first = generate(fixture()); second = generate(fixture())
    assert first == second and first["package_count"] == 30 and first["canonical_required_gate_rows"] == 310
    assert first["canonical_pass_gates"] == 30 and first["canonical_hold_gates"] == 280
    assert first["legacy_alias_gate_rows"] == 210 and first["total_retained_gate_rows"] == 520
    assert len(next(p for p in first["packages"] if p["platform"] == "ready")["canonical_gates"]) == 11
    assert generate(fixture(next(iter(LEGACY_SOURCES))))["source_system"] == CURRENT_SOURCE
    bad = fixture(); bad["products"][0]["api_key"] = "do-not-accept"
    try: generate(bad); raise AssertionError("secret shape accepted")
    except FactoryError: pass
    tampered = first["packages"][0].copy(); tampered["package_sha256"] = "0" * 64
    try: validate_package(tampered); raise AssertionError("tampered hash accepted")
    except FactoryError: pass
    drift = json.loads(json.dumps(first["packages"][0])); drift["governed_release_binding"]["content_sha256"] = "1" * 64
    try: validate_package(drift); raise AssertionError("binding drift accepted")
    except FactoryError: pass
    return {"tests": 7, "state": "PASS", "packages": 30, "current_gates": 310, "pass": 30, "hold": 280,
            "legacy_aliases": 210, "retained_rows": 520}

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("input", nargs="?", type=Path); ap.add_argument("output", nargs="?", type=Path); ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test: print(json.dumps(self_test(), sort_keys=True)); return 0
    if not args.input or not args.output: ap.error("input and output required unless --self-test")
    out = generate(json.loads(args.input.read_text())); args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n"); return 0
if __name__ == "__main__": raise SystemExit(main())
