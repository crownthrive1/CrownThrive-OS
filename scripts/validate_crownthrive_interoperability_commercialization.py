#!/usr/bin/env python3
"""Validate non-operative CrownThrive Interoperability commercialization candidates."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "developers/manifests/crownthrive-interoperability-commercialization.v1.json"
CHANGELOG = ROOT / "changelog/crownthrive-interoperability-commercialization-2026-08-22.mdx"


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
    assert data["plugin_id"] == "ct.plugin.crownthrive-interoperability-fabric"
    assert data["state"] == "CANDIDATE_D3_HUMAN_REVIEW_REQUIRED"
    for key in (
        "live_offer",
        "checkout_enabled",
        "stripe_objects_created",
        "entitlement_active",
        "operative_license",
        "public_distribution",
        "tax_accounting_review_complete",
        "counsel_review_complete",
        "fulfillment_certified",
        "refund_dispute_certified",
        "support_sla_certified",
        "D3_auto",
    ):
        assert data[key] is False, key

    licenses = data["license_candidates"]
    assert len(licenses) == 6
    assert all(item["operative"] is False for item in licenses)
    assert {item["tier_code"] for item in licenses} == {
        "DEVELOPER",
        "TEAM",
        "GOVERNANCE",
        "ENTERPRISE",
        "MANAGED_ADAPTER",
        "CERTIFIED_LISTING",
    }
    listing = next(item for item in licenses if item["tier_code"] == "CERTIFIED_LISTING")
    assert listing["state"] == "hold"
    assert listing["minimum_phase"] == 20
    assert "cannot silently improve" in listing["conflict_firewall"]

    offers = data["offer_candidates"]
    assert offers["count"] == 10
    assert offers["live_count"] == 0
    assert offers["checkout_enabled_count"] == 0
    assert offers["stripe_objects_created_count"] == 0
    assert offers["entitlement_active_count"] == 0

    assert data["protected_kernel_transfer"] is False
    assert data["history_policy"] == "append_or_supersede_never_silent_delete"
    assert len(data["required_activation_gates"]) >= 9

    text = CHANGELOG.read_text(encoding="utf-8").lower()
    for phrase in (
        "d3 human review required",
        "live offers: zero",
        "checkout",
        "non-operative",
        "may never silently improve",
        "append-or-supersede",
    ):
        assert phrase in text, phrase

    print("CrownThrive Interoperability commercialization invariants: PASS")


if __name__ == "__main__":
    main()
