"""CHLOM offer derivation and validation for the COS commercial catalog."""

from __future__ import annotations

from typing import Any, Mapping

from scripts.commercialization.catalog_core import SourceRecord, get_path

def offer_from_explicit_block(source: SourceRecord, source_sha: str | None) -> dict[str, Any] | None:
    block = source.record.get("commercialization")
    if not isinstance(block, Mapping):
        return None
    offer_type = str(block.get("offer_type", "NEGOTIATED_COMMERCIAL"))
    offer_id = str(block.get("offer_id") or f"{source.component_id}.{offer_type.lower()}")
    return {
        "offer_id": offer_id,
        "component_id": source.component_id,
        "component_version": source.version,
        "offer_type": offer_type,
        "license_id": block.get("license_id"),
        "offer_state": block.get("offer_state", "HOLD"),
        "price_mode": block.get("price_mode", "NEGOTIATED"),
        "amount_minor": block.get("amount_minor"),
        "currency": block.get("currency", "USD"),
        "wallet_route": block.get("wallet_route", "CHLOM_QUOTE_THEN_WALLET"),
        "entitlement_type": block.get("entitlement_type", "none_until_authorized"),
        "economic_gate_state": block.get("economic_gate_state", "HOLD"),
        "rights_gate_state": block.get("rights_gate_state", "HOLD"),
        "certification_fingerprint": source.source_fingerprint,
        "source_sha": source_sha,
        "contact": block.get("contact"),
    }


def generated_offers(
    source: SourceRecord,
    policy: Mapping[str, Any],
    source_sha: str | None,
) -> list[dict[str, Any]]:
    explicit = offer_from_explicit_block(source, source_sha)
    if explicit is not None:
        return [explicit]

    commercial = policy["commercialization"]
    offers: list[dict[str, Any]] = []
    free_authorized = any(
        get_path(source.record, path) is True
        for path in commercial.get("free_evaluation_authorization_paths", [])
    )
    if (
        commercial.get("free_evaluation_offer_enabled", False)
        and (
            not commercial.get("free_evaluation_requires_explicit_authorization", True)
            or free_authorized
        )
    ):
        offers.append(
            {
                "offer_id": f"{source.component_id}.community-evaluation",
                "component_id": source.component_id,
                "component_version": source.version,
                "offer_type": "FREE_EVALUATION",
                "license_id": commercial["free_evaluation_license_id"],
                "offer_state": "ACTIVE",
                "price_mode": "FREE",
                "amount_minor": commercial["free_evaluation_price_minor"],
                "currency": commercial["free_evaluation_currency"],
                "wallet_route": "NONE",
                "entitlement_type": "non_production_evaluation",
                "economic_gate_state": "NOT_REQUIRED",
                "rights_gate_state": "PASS",
                "certification_fingerprint": source.source_fingerprint,
                "source_sha": source_sha,
            }
        )
    offers.append(
        {
            "offer_id": f"{source.component_id}.commercial-request-quote",
            "component_id": source.component_id,
            "component_version": source.version,
            "offer_type": "NEGOTIATED_COMMERCIAL",
            "license_id": "ct.license.chlom-negotiated-commercial.v1",
            "offer_state": "REQUEST_QUOTE",
            "price_mode": "NEGOTIATED",
            "amount_minor": None,
            "currency": "USD",
            "wallet_route": "CHLOM_QUOTE_THEN_WALLET",
            "entitlement_type": "none_until_executed_agreement_and_settlement",
            "economic_gate_state": "HOLD",
            "rights_gate_state": "PASS",
            "certification_fingerprint": source.source_fingerprint,
            "source_sha": source_sha,
            "contact": policy.get("licensing_contact"),
        }
    )
    return offers


def validate_offer(offer: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    required = [
        "offer_id",
        "component_id",
        "component_version",
        "offer_type",
        "license_id",
        "offer_state",
        "price_mode",
        "currency",
        "wallet_route",
        "entitlement_type",
    ]
    for key in required:
        if offer.get(key) in (None, ""):
            failures.append(f"missing:{key}")

    price_mode = offer.get("price_mode")
    offer_state = offer.get("offer_state")
    amount = offer.get("amount_minor")
    if price_mode == "FREE" and amount != 0:
        failures.append("free_offer_amount_must_be_zero")
    if price_mode in {"FIXED", "METERED"} and offer_state == "ACTIVE":
        if not isinstance(amount, int) or amount < 0:
            failures.append("active_fixed_or_metered_offer_requires_nonnegative_amount")
        if offer.get("economic_gate_state") != "PASS":
            failures.append("active_fixed_or_metered_offer_requires_economic_gate_PASS")
        if offer.get("wallet_route") != "CHLOM_WALLET":
            failures.append("active_fixed_or_metered_offer_requires_CHLOM_WALLET")
    if price_mode == "NEGOTIATED" and amount is not None:
        failures.append("negotiated_offer_must_not_invent_amount")
    if offer.get("rights_gate_state") != "PASS" and offer_state in {"ACTIVE", "REQUEST_QUOTE"}:
        failures.append("visible_offer_requires_rights_gate_PASS")
    return failures
