#!/usr/bin/env python3
"""Validate CrownThrive's governed credit-only Commercial Release Factory.

This validator is provider-free, secret-free, and deterministic. It proves the
public release contract fails closed; it does not grant rights, set prices,
move credits, publish to Sites, mutate DNS, or create provider authority.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers" / "manifests" / "commercial-release-factory.v1.json"

EXPECTED_GATE_ORDER = [
    "rights_provenance",
    "pricing_tax",
    "private_fulfillment",
    "credit_checkout_webhook",
    "entitlement_license",
    "refund_dispute_rollback",
    "accessibility_device",
    "dns_tls_route",
    "governed_acceptance_publication",
]

EXPECTED_SURFACES = {
    "launch": {
        "platform_id": "ct.platform.crownthrive-launch",
        "surface_id": "ct.surface.crownthrive-launch.production",
        "product_prefix": "CT-LAUNCH-",
        "count": 10,
    },
    "ready": {
        "platform_id": "ct.platform.crownthrive-ready",
        "surface_id": "ct.surface.crownthrive-ready.production",
        "product_prefix": "CT-READY-",
        "count": 10,
    },
    "procure": {
        "platform_id": "ct.platform.crownthrive-procure",
        "surface_id": "ct.surface.crownthrive-procure.production",
        "product_prefix": "CT-PROCURE-",
        "count": 10,
    },
}

REQUIRED_SKILLS = {
    "ct.skill.release.source-normalization.v1",
    "ct.skill.release.rights-package.v1",
    "ct.skill.release.pricing-tax-package.v1",
    "ct.skill.release.private-fulfillment-package.v1",
    "ct.skill.release.credit-checkout-webhook.v1",
    "ct.skill.release.entitlement-license.v1",
    "ct.skill.release.refund-dispute-rollback.v1",
    "ct.skill.release.accessibility-device.v1",
    "ct.skill.release.dns-tls-route.v1",
    "ct.skill.release.governed-acceptance.v1",
    "ct.skill.release.sites-feed-projection.v1",
    "ct.skill.release.site-readback.v1",
    "ct.skill.release.evidence-hashchain.v1",
    "ct.skill.release.credential-alias-resolution.v1",
    "ct.skill.release.provider-capability-check.v1",
    "ct.skill.release.drift-reconciliation.v1",
    "ct.skill.release.rollback-replay.v1",
    "ct.skill.release.agent-replication-contract.v1",
}

REQUIRED_ALGORITHMS = {
    "ct.alg.release.prfi.v1",
    "ct.alg.release.geca.v1",
    "ct.alg.release.crom.v1",
    "ct.alg.release.pfrg.v1",
    "ct.alg.release.dtrs.v1",
    "ct.alg.release.acrt.v1",
    "ct.alg.release.irhg.v1",
    "ct.alg.release.rrcg.v1",
}

REQUIRED_INVARIANTS = {
    "all_required_gates_pass_before_release_pass",
    "originator_never_self_approves",
    "unknown_or_stale_evidence_holds",
    "credit_checkout_never_implies_rights_or_entitlement",
    "stripe_per_sku_objects_are_forbidden_for_these_surfaces",
    "publish_requires_certified_route_read_after_write_and_rollback",
    "custom_domain_requires_dns_and_tls_evidence",
    "ready_preserves_professional_authority_firewall",
    "procure_preserves_commercial_conflict_firewall",
    "secrets_and_private_evidence_never_enter_public_projection",
}


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_manifest(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    agent = data.get("agent", {})
    if agent.get("agent_id") != "ct.agent.commercial-release-packager":
        errors.append("unexpected release-factory agent identity")
    if agent.get("vote_eligible") is not False:
        errors.append("release-factory agent must remain non-voting")
    if agent.get("self_approval") is not False:
        errors.append("release-factory agent must not self-approve")
    if agent.get("production_activation_authority") is not False:
        errors.append("originating agent cannot hold production activation authority")
    if agent.get("autonomy_ceiling") != "A2" or agent.get("decision_ceiling") != "D2":
        errors.append("agent authority must remain bounded to A2/D2")

    commerce = data.get("commerce_contract", {})
    if commerce.get("product_checkout_mode") != "crown_credits_only":
        errors.append("Launch/Ready/Procure must remain Crown Credits-only")
    if commerce.get("stripe_per_product_objects") is not False:
        errors.append("per-product Stripe objects are prohibited for these surfaces")
    if commerce.get("stripe_role") != "separate_governed_credit_funding_rail_only":
        errors.append("Stripe role drifted beyond the separate governed funding rail")
    for field in (
        "payment_evidence_is_entitlement",
        "credit_debit_is_license",
        "direct_provider_publish_from_originator",
    ):
        if commerce.get(field) is not False:
            errors.append(f"commerce separation invariant failed: {field}")
    for field in ("entitlement_requires_license_binding", "fulfillment_requires_entitlement"):
        if commerce.get(field) is not True:
            errors.append(f"required commerce dependency missing: {field}")

    gates = data.get("gate_dimensions", [])
    keys = [g.get("key") for g in gates]
    seq = [g.get("sequence") for g in gates]
    if keys != EXPECTED_GATE_ORDER:
        errors.append("gate order or required gate set changed")
    if seq != list(range(1, len(EXPECTED_GATE_ORDER) + 1)):
        errors.append("gate sequence must be contiguous and ordered")
    for gate in gates:
        if gate.get("severity") != "HARD":
            errors.append(f"gate {gate.get('key')} must be HARD")
        if gate.get("default_state") != "HOLD":
            errors.append(f"gate {gate.get('key')} must fail closed to HOLD")
        if not gate.get("reviewer_ref"):
            errors.append(f"gate {gate.get('key')} lacks independent reviewer routing")
    if gates and gates[-1].get("reviewer_ref") != "ct.relay.agent-d":
        errors.append("governed acceptance must route through mandatory Agent D")

    surfaces = data.get("surfaces", [])
    by_key = {s.get("key"): s for s in surfaces}
    if set(by_key) != set(EXPECTED_SURFACES):
        errors.append("surface set must be exactly Launch, Ready, Procure")
    seen_skus: set[str] = set()
    for key, expected in EXPECTED_SURFACES.items():
        surface = by_key.get(key, {})
        for field in ("platform_id", "surface_id"):
            if surface.get(field) != expected[field]:
                errors.append(f"{key}: incorrect {field}")
        if surface.get("provider_system") != "Sites":
            errors.append(f"{key}: provider must remain Sites")
        if surface.get("credit_only") is not True:
            errors.append(f"{key}: credit_only must be true")
        if surface.get("publish_mode") != "governed_dynamic_feed":
            errors.append(f"{key}: direct provider-write publication is not allowed")
        if surface.get("provider_connection_state") != "verified":
            errors.append(f"{key}: provider connection must be verified before projection")
        if surface.get("provider_health_state") != "healthy":
            errors.append(f"{key}: provider surface is not healthy")
        if surface.get("current_route_state") == "CERTIFIED" and not surface.get("preferred_custom_domain"):
            errors.append(f"{key}: certified route lacks explicit custom-domain target")
        products = surface.get("products", [])
        if len(products) != expected["count"]:
            errors.append(f"{key}: expected {expected['count']} products")
        if any(not sku.startswith(expected["product_prefix"]) for sku in products):
            errors.append(f"{key}: SKU namespace mismatch")
        dupes = seen_skus.intersection(products)
        if dupes:
            errors.append(f"cross-surface duplicate SKU(s): {sorted(dupes)}")
        seen_skus.update(products)
        if not surface.get("aggregate_sha256") or len(surface["aggregate_sha256"]) != 64:
            errors.append(f"{key}: missing exact aggregate SHA-256")
        if not surface.get("source_commit") or len(surface["source_commit"]) != 40:
            errors.append(f"{key}: missing exact source commit")

    if len(seen_skus) != 30:
        errors.append("factory must bind exactly 30 unique candidate.4 products")

    skills = {x.get("skill_id") for x in data.get("skills", [])}
    if skills != REQUIRED_SKILLS:
        errors.append("release skill suite is incomplete or contains unreviewed additions")
    for skill in data.get("skills", []):
        if skill.get("mcp_state") != "disabled":
            errors.append(f"skill {skill.get('skill_id')} must start with MCP disabled")

    algorithms = data.get("protected_algorithms", [])
    algorithm_ids = {x.get("id") for x in algorithms}
    if algorithm_ids != REQUIRED_ALGORITHMS:
        errors.append("protected algorithm registry mismatch")
    for algorithm in algorithms:
        if algorithm.get("public_body") is not False:
            errors.append(f"protected body exposure prohibited: {algorithm.get('id')}")

    invariants = set(data.get("invariants", []))
    if not REQUIRED_INVARIANTS.issubset(invariants):
        errors.append("one or more required release invariants are missing")

    return errors


def run_negative_tests(data: dict[str, Any]) -> list[str]:
    """Prove representative unsafe mutations are rejected."""
    failures: list[str] = []
    cases: list[tuple[str, dict[str, Any]]] = []

    mutated = copy.deepcopy(data)
    mutated["commerce_contract"]["stripe_per_product_objects"] = True
    cases.append(("per_sku_stripe", mutated))

    mutated = copy.deepcopy(data)
    mutated["agent"]["self_approval"] = True
    cases.append(("self_approval", mutated))

    mutated = copy.deepcopy(data)
    mutated["gate_dimensions"] = mutated["gate_dimensions"][:-1]
    cases.append(("skip_governed_acceptance", mutated))

    mutated = copy.deepcopy(data)
    mutated["gate_dimensions"][0]["default_state"] = "PASS"
    cases.append(("rights_fail_open", mutated))

    mutated = copy.deepcopy(data)
    mutated["surfaces"][0]["credit_only"] = False
    cases.append(("cash_product_drift", mutated))

    mutated = copy.deepcopy(data)
    mutated["surfaces"][1]["publish_mode"] = "direct_provider_write"
    cases.append(("direct_sites_write", mutated))

    mutated = copy.deepcopy(data)
    mutated["protected_algorithms"][0]["public_body"] = True
    cases.append(("algorithm_body_exposure", mutated))

    mutated = copy.deepcopy(data)
    mutated["skills"][0]["mcp_state"] = "production"
    cases.append(("premature_mcp_activation", mutated))

    for name, candidate in cases:
        if not validate_manifest(candidate):
            failures.append(f"negative test failed to reject: {name}")

    return failures


def main() -> int:
    data = load_manifest()
    errors = validate_manifest(data)
    negative_failures = run_negative_tests(data)
    digest = canonical_sha256(data)

    print("CrownThrive Commercial Release Factory validation")
    print(f"Manifest: {MANIFEST.relative_to(ROOT)}")
    print(f"Manifest canonical SHA-256: {digest}")
    print(f"Bound products: {sum(len(x.get('products', [])) for x in data.get('surfaces', []))}")
    print(f"Hard gates: {len(data.get('gate_dimensions', []))}")
    print(f"Reusable skills: {len(data.get('skills', []))}")
    print(f"Protected algorithm contracts: {len(data.get('protected_algorithms', []))}")
    print("Negative authorization tests: 8")

    for error in errors + negative_failures:
        print(f"ERROR: {error}")

    if errors or negative_failures:
        print(f"FAILED with {len(errors) + len(negative_failures)} error(s).")
        return 1

    print("PASS_CONTROLLED_TEST — contract and negative authorization checks passed.")
    print("No publication, rights grant, price authorization, credit movement, Stripe write, DNS mutation, or provider write was executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
