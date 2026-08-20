#!/usr/bin/env python3
"""Validate CrownThrive IP-disclosure and CHLOM commercialization governance."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "developers/manifests/ip-disclosure-commercialization-policy.v1.json"
CATALOG = ROOT / "developers/manifests/chlom-agentic-commercial-offer-catalog.v1.json"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Missing required file: {path.relative_to(ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")
    if not isinstance(data, dict):
        fail(f"Expected JSON object: {path.relative_to(ROOT)}")
    return data


def require_text(path: str, *fragments: str) -> None:
    p = ROOT / path
    if not p.is_file():
        fail(f"Missing required file: {path}")
    text = p.read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in text:
            fail(f"Missing required fragment {fragment!r} in {path}")


def main() -> int:
    policy = load(POLICY)
    catalog = load(CATALOG)

    if policy.get("manifest_id") != "ct.manifest.ip-disclosure-commercialization-policy.v1":
        fail("IP disclosure manifest identity drifted")
    if policy.get("phase") != "2.99":
        fail("IP disclosure policy must not silently advance current phase")
    gate = policy.get("pre_publication_gate", {})
    if gate.get("mandatory") is not True or gate.get("default_on_uncertainty") != "HOLD":
        fail("Pre-publication IP gate must be mandatory and fail closed")

    classes = policy.get("classification_classes", {})
    required_classes = {
        "PUBLIC_STANDARD",
        "PUBLIC_DOCTRINE",
        "COPYRIGHT_LICENSED",
        "TRADE_SECRET_CANDIDATE",
        "TRADE_SECRET_CONTROLLED",
        "PATENT_CANDIDATE",
        "TRADEMARK_CANDIDATE",
        "CERTIFICATION_MARK_CANDIDATE",
        "RESTRICTED_INSTITUTIONAL",
        "THIRD_PARTY_LICENSED",
        "RIGHTS_REVIEW",
    }
    if not required_classes.issubset(set(classes)):
        fail(f"Missing IP classification classes: {sorted(required_classes - set(classes))}")
    for cls in ("TRADE_SECRET_CANDIDATE", "TRADE_SECRET_CONTROLLED", "PATENT_CANDIDATE", "RESTRICTED_INSTITUTIONAL", "RIGHTS_REVIEW"):
        if classes.get(cls, {}).get("may_publish") is not False:
            fail(f"{cls} must fail closed for public publication")

    ai = policy.get("ai_assisted_ip", {})
    if ai.get("ai_output_alone_proves_copyright_ownership") is not False:
        fail("AI output alone may not prove copyright ownership")
    if ai.get("ai_output_alone_proves_inventorship") is not False:
        fail("AI output alone may not prove inventorship")

    stripe_policy = policy.get("stripe", {})
    if stripe_policy.get("product_creation_authorized_by_manifest") is not False:
        fail("IP policy may not authorize Stripe product creation")
    if stripe_policy.get("price_creation_authorized_by_manifest") is not False:
        fail("IP policy may not authorize Stripe price creation")
    if stripe_policy.get("checkout_enabled") is not False:
        fail("IP policy may not enable checkout")

    if catalog.get("manifest_id") != "ct.manifest.chlom-agentic-commercial-offer-catalog.v1":
        fail("Commercial offer catalog identity drifted")
    if catalog.get("phase") != "2.99":
        fail("Commercial catalog must remain Phase 2.99 candidate state")
    if catalog.get("default_checkout_enabled") is not False:
        fail("Commercial catalog checkout default must remain false")
    if catalog.get("default_price_status") != "not_authorized":
        fail("Commercial catalog may not invent price authority")

    offers = catalog.get("offers")
    if not isinstance(offers, list) or len(offers) < 14:
        fail("Commercial catalog must preserve the approved product-family breadth")
    ids: set[str] = set()
    allowed_states = {"concept", "candidate", "packaged", "rights_cleared", "pricing_authorized", "fulfillment_certified", "checkout_staged", "live"}
    for offer in offers:
        if not isinstance(offer, dict):
            fail("Commercial offer row must be an object")
        offer_id = offer.get("offer_id")
        if not isinstance(offer_id, str) or not offer_id.startswith("ct.offer.") or offer_id in ids:
            fail(f"Invalid or duplicate offer_id: {offer_id!r}")
        ids.add(offer_id)
        if offer.get("state") not in allowed_states:
            fail(f"Invalid offer state for {offer_id}: {offer.get('state')!r}")
        if not offer.get("protection_layers"):
            fail(f"Offer lacks protection layers: {offer_id}")
        if offer.get("state") == "live":
            fail(f"Phase 2.99 catalog may not mark offer live: {offer_id}")

    stripe = catalog.get("stripe", {})
    if stripe.get("product_creation_authorized_by_catalog") is not False:
        fail("Catalog may not authorize Stripe product creation")
    if stripe.get("price_creation_authorized_by_catalog") is not False:
        fail("Catalog may not authorize Stripe price creation")
    if stripe.get("checkout_enabled") is not False:
        fail("Catalog may not enable checkout")

    phase_map = catalog.get("phase_map", {})
    for phase in ["2.99", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]:
        if phase not in phase_map:
            fail(f"Commercialization phase map missing Phase {phase}")

    require_text(
        "governance/ip-disclosure-and-commercialization-gate.mdx",
        "permanent institutional rule",
        "Public specification / public doctrine",
        "Trade-secret kernel",
        "PATENT_CANDIDATE",
        "concept",
        "Agent responsibilities",
        "Phase 2 / 2.99",
        "Phases 11–20",
    )
    require_text(
        "revenue/chlom-agentic-infrastructure-commercialization.mdx",
        "CHLOM Enterprise License",
        "Agent Governance Runtime",
        "Agent Factory SDK",
        "CHLOM Capability Pallets",
        "Institutional Agent Packs",
        "CHLOM Conformance & Certification",
        "Managed Governance / dS-CaaS",
        "CrownThriveU Agentic Governance Training",
        "OEM / White-Label",
        "MCP / A2A Governance Infrastructure",
        "Qualified Implementer & Developer Marketplace",
        "Enterprise Support & Update Subscription",
        "price_status: not_authorized",
    )
    require_text(
        "developers/templates/ip-disclosure-review-template.v1.yaml",
        "TRADE_SECRET_CONTROLLED",
        "PATENT_CANDIDATE",
        "public_disclosure_risk_reviewed: false",
        "checkout_enabled: false",
    )
    require_text(
        "developers/templates/commercial-offer-manifest-template.v1.yaml",
        "price_status: not_authorized",
        "checkout_enabled: false",
        "ip_disclosure_gate_state: required",
    )
    require_text(
        "developers/offers/phase-2-99-packageable-agentic-offers.v1.yaml",
        "ct.offer.reference-architecture-license",
        "ct.offer.agent-factory-sdk",
        "ct.offer.capability-pallets",
        "ct.offer.institutional-agent-packs",
        "ct.offer.implementation-services",
        "ct.offer.crownthriveu-agentic-training",
        "ct.offer.mcp-a2a-governance",
        "ct.offer.enterprise-support-updates",
        "price_status: not_authorized",
        "checkout_enabled: false",
    )
    require_text(
        "standards/ip-protection-chain-of-title-and-trade-secret.mdx",
        "Pre-publication IP disclosure gate",
        "publish first",
        "trade-secret kernel",
    )
    require_text(
        "AGENTS.md",
        "Pre-publication IP disclosure gate",
        "PATENT_CANDIDATE",
        "commercialization",
    )

    print("IP disclosure and commercialization governance validation passed.")
    print(f"Offer families: {len(offers)}")
    print("Phase 2.99 packageable offer backlog is present and remains non-live.")
    print("Public/licensed/restricted/trade-secret projections remain separated.")
    print("No offer is live; price and checkout authority remain separately gated.")
    print("Phase 2.99 through Phase 20 commercialization responsibilities are mapped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
