#!/usr/bin/env python3
"""Build deterministic, fail-closed CrownThrive commercial release packages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

POLICY_PATH = Path("developers/reference/commercial-release/release-policy.v1.json")
INVENTORY_PATH = Path("developers/reference/commercial-release/commercial-gap-products.v1.json")

FORBIDDEN_SECRET_KEYS = {
    "password", "secret", "secret_value", "api_key", "private_key", "token",
    "access_token", "refresh_token", "vault_id", "credential_value"
}

def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")

def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def package_id(sku: str) -> str:
    return f"ct.release-package.{sku.lower().replace('_', '-').replace('ct-', '')}.v1"

def gate_state(code: str) -> tuple[str, dict[str, Any]]:
    if code == "package_integrity":
        return "PASS", {
            "evidence_class": "packaged_asset_digest_and_existing_independent_package_review",
            "technical_claim_only": True,
        }
    if code == "destination_readiness":
        return "HOLD", {
            "historical_provider_preview": "deployment_succeeded",
            "current_external_probe": "HOLD_UNREADABLE_FROM_CURRENT_PROBE",
            "custom_domain_readback": False,
        }
    return "HOLD", {"evidence_required": True}

def build_package(product: dict[str, Any], platform: dict[str, Any], policy: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    pricing = inventory["pricing_policy"]
    tax = inventory["tax_profile"]
    gates: list[dict[str, Any]] = []
    for gate in policy["gates"]:
        applies_to = gate.get("applies_to")
        if applies_to and platform["platform_key"] not in applies_to:
            continue
        state, evidence = gate_state(gate["code"])
        if gate["code"] == "package_integrity":
            evidence = {
                **evidence,
                "asset_version_count": product["asset_version_count"],
                "asset_set_sha256": product["asset_set_sha256"],
                "candidate_version": product["candidate_version"],
                "package_review_receipt": platform["package_review_receipt"],
                "platform_aggregate_sha256": platform["aggregate_sha256"],
                "new_sovereign_review": False,
            }
        gates.append({
            "code": gate["code"],
            "label": gate["label"],
            "reviewer_class": gate["reviewer_class"],
            "human_required": gate["human_required"],
            "state": state,
            "producer_agent_id": "ct.agent.commercial-release-packager",
            "independent_reviewer_id": None,
            "evidence": evidence,
        })

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "package_id": package_id(product["sku"]),
        "sku": product["sku"],
        "platform": {
            "platform_id": platform["platform_id"],
            "name": platform["name"],
            "provider_system": "ChatGPT Sites",
            "provider_preview": platform["provider_preview"],
            "target_hostname": platform["target_hostname"],
            "source_build_commit": platform["source_build_commit"],
            "aggregate_sha256": platform["aggregate_sha256"],
            "operating_agent_id": platform["agent_id"],
            "boundary": platform["boundary"],
        },
        "product": {
            "slug": product["slug"],
            "title": product["title"],
            "product_type": product["product_type"],
            "candidate_version": product["candidate_version"],
            "lifecycle_state": product["lifecycle_state"],
            "license_version": product["license_version"],
            "asset_version_count": product["asset_version_count"],
            "asset_set_sha256": product["asset_set_sha256"],
            "support_boundary": product["support_boundary"],
        },
        "pricing": {
            "pricing_policy_version": pricing["version"],
            "candidate_credit_price": pricing["target_credits"],
            "authorized_credit_price": None,
            "minimum_credits": pricing["minimum_credits"],
            "maximum_credits": pricing["maximum_credits"],
            "minimum_comparables": pricing["minimum_comparables"],
            "minimum_sources": pricing["minimum_sources"],
            "comparables_recorded": 0,
            "sources_recorded": 0,
            "state": "HOLD_COMPARABLES_AND_INDEPENDENT_PRICE_CERTIFICATION",
        },
        "tax": {
            "tax_profile_code": tax["code"],
            "provider_tax_code": tax["stripe_tax_code"],
            "provider_code_state": tax["provider_code_state"],
            "legal_taxability_state": tax["legal_taxability_state"],
            "state": "HOLD_JURISDICTION_REVIEW",
        },
        "commerce": {
            "denomination": "Crown Credits",
            "credit_only": True,
            "cash_checkout_enabled": False,
            "credit_checkout_enabled": False,
            "stripe_product_created": False,
            "stripe_price_created": False,
            "webhook_endpoint_active": False,
            "atomic_redemption_proven": False,
            "exact_replay_idempotency_proven": False,
            "out_of_order_handling_proven": False,
            "entitlement_issue_reversal_proven": False,
            "state": "HOLD",
        },
        "domain": {
            "provider_preview_state": platform["provider_preview_state"],
            "target_hostname": platform["target_hostname"],
            "dns_authority_state": "UNVERIFIED",
            "tls_state": "UNVERIFIED",
            "https_readback": False,
            "canonical_redirect_readback": False,
            "current_cpanel_inventory_match": False,
            "state": "HOLD_DNS_TLS_AND_ROUTE_READBACK",
        },
        "publication": {
            "provider_system": "ChatGPT Sites",
            "provider_preview": platform["provider_preview"],
            "historical_deployment_state": "succeeded",
            "current_external_probe_state": platform["external_probe_2026_08_22"],
            "source_build_commit": platform["source_build_commit"],
            "publish_candidate_created": False,
            "provider_write_authorized": False,
            "rollback_version_bound": False,
            "readback_proven": False,
            "automatic_publication_eligible": False,
            "state": "HOLD",
        },
        "credential_contract": {
            "credential_source": "Supabase Vault alias through CHLOM Vault broker",
            "raw_secret_return": False,
            "primary_and_recovery_alias_required": True,
            "runtime_binding_state": "HOLD_UNTIL_PROVIDER_OPERATION_REQUIRES_CREDENTIAL",
        },
        "governance": {
            "producer_agent_id": "ct.agent.commercial-release-packager",
            "self_approval": False,
            "sovereign_voters": policy["sovereign_rule"]["voters"],
            "minimum_approvals": policy["sovereign_rule"]["minimum_approvals"],
            "agent_d_required": policy["sovereign_rule"]["agent_d_required"],
            "any_block_holds": policy["sovereign_rule"]["any_block_holds"],
            "recorded_approvals": 0,
            "agent_d_approval_recorded": False,
            "accepted_exact_digest": None,
        },
        "gates": gates,
        "overall_state": "HOLD",
        "next_actions": [
            "collect rights and customer-license evidence",
            "collect pricing comparables and independent price certification",
            "record jurisdiction-specific tax decision",
            "prove protected fulfillment, credit redemption, webhook idempotency, entitlement and reversal",
            "complete accessibility and security review",
            "complete DNS, TLS, ChatGPT Sites publish/readback/rollback/reapply proof",
            "obtain exact-digest independent governance acceptance",
        ],
    }
    payload["package_sha256"] = sha256_hex(payload)
    return payload

def scan_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            if normalized in FORBIDDEN_SECRET_KEYS:
                errors.append(f"{path}.{key}")
            errors.extend(scan_forbidden_keys(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(scan_forbidden_keys(child, f"{path}[{index}]"))
    return errors

def validate_package(package: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = copy.deepcopy(package)
    actual_digest = expected.pop("package_sha256", None)
    expected_digest = sha256_hex(expected)
    if actual_digest != expected_digest:
        errors.append("package digest mismatch")
    if package.get("commerce", {}).get("cash_checkout_enabled") is not False:
        errors.append("cash checkout must remain disabled")
    if package.get("commerce", {}).get("credit_only") is not True:
        errors.append("commercial gap sites must remain credit-only")
    platform_key = package.get("platform", {}).get("platform_id", "").rsplit("-", 1)[-1]
    required = {g["code"] for g in policy["gates"] if not g.get("applies_to") or platform_key in g["applies_to"]}
    if package.get("publication", {}).get("automatic_publication_eligible") is True:
        accepted = {g["code"] for g in package.get("gates", []) if g.get("state") == "ACCEPTED"}
        if accepted != required or package.get("overall_state") != "ACCEPTED":
            errors.append("automatic publication cannot precede all accepted gates")
    producer = package.get("governance", {}).get("producer_agent_id")
    for gate in package.get("gates", []):
        if gate.get("independent_reviewer_id") and gate["independent_reviewer_id"] == producer:
            errors.append(f"self review prohibited for {gate.get('code')}")
    expected_gate_count = sum(1 for g in policy["gates"] if not g.get("applies_to") or platform_key in g["applies_to"])
    if len(package.get("gates", [])) != expected_gate_count:
        errors.append("gate count mismatch")
    if package.get("domain", {}).get("state") == "ACCEPTED":
        if not package["domain"].get("https_readback") or package["domain"].get("tls_state") != "VERIFIED":
            errors.append("domain acceptance requires TLS and HTTPS readback")
    errors.extend(f"forbidden secret-shaped key at {path}" for path in scan_forbidden_keys(package))
    return errors

def build_all(inventory_path: Path, policy_path: Path, output_dir: Path) -> dict[str, Any]:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    platform_by_key = {p["platform_key"]: p for p in inventory["platforms"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = []
    common_defaults = inventory["product_defaults"]["common"]
    platform_defaults = inventory["product_defaults"]["by_platform"]
    for compact_product in sorted(inventory["products"], key=lambda item: item["sku"]):
        platform = platform_by_key[compact_product["platform_key"]]
        product = {
            **common_defaults,
            **platform_defaults[compact_product["platform_key"]],
            **compact_product,
            "platform_id": platform["platform_id"],
        }
        package = build_package(product, platform, policy, inventory)
        errors = validate_package(package, policy)
        if errors:
            raise ValueError(f"{product['sku']}: {'; '.join(errors)}")
        path = output_dir / f"{product['sku'].lower()}.json"
        path.write_bytes(canonical_bytes(package))
        packages.append(package)
    summary = {
        "schema_version": "1.0.0",
        "run_id": "ct.release-package-run.commercial-gap-sites.v1",
        "product_count": len(packages),
        "platform_counts": {
            key: sum(1 for p in packages if p["platform"]["platform_id"] == platform["platform_id"])
            for key, platform in sorted(platforms_from_inventory(inventory).items())
        },
        "accepted_count": sum(1 for p in packages if p["overall_state"] == "ACCEPTED"),
        "hold_count": sum(1 for p in packages if p["overall_state"] == "HOLD"),
        "cash_checkout_enabled_count": sum(1 for p in packages if p["commerce"]["cash_checkout_enabled"]),
        "credit_checkout_enabled_count": sum(1 for p in packages if p["commerce"]["credit_checkout_enabled"]),
        "automatic_publication_eligible_count": sum(1 for p in packages if p["publication"]["automatic_publication_eligible"]),
        "package_digests": {p["sku"]: p["package_sha256"] for p in packages},
    }
    summary["summary_sha256"] = sha256_hex(summary)
    (output_dir / "summary.json").write_bytes(canonical_bytes(summary))
    return summary

def platforms_from_inventory(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["platform_key"]: p for p in inventory["platforms"]}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument("--output", type=Path, default=Path("build/commercial-release-packages"))
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    summary = build_all(args.inventory, args.policy, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
