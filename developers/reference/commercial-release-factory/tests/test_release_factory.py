#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_release_packages import ReleaseFactoryError, generate  # noqa: E402
from validate_release_packages import validate  # noqa: E402

SKUS = {
    "launch": [
        ("CT-LAUNCH-90D-001", "90-Day Business Launch Planner"),
        ("CT-LAUNCH-BEAUTY-001", "Beauty Pro Business OS"),
        ("CT-LAUNCH-BIZ-001", "Service Business Operating System"),
        ("CT-LAUNCH-COACH-001", "Coach / Consultant Authority OS"),
        ("CT-LAUNCH-CREATOR-001", "Creator Business Operating System"),
        ("CT-LAUNCH-DIGITAL-001", "Digital Seller Launch OS"),
        ("CT-LAUNCH-INTAKE-001", "Client Intake & Onboarding Pack"),
        ("CT-LAUNCH-KPI-001", "KPI & Weekly Operating Dashboard"),
        ("CT-LAUNCH-MIN-001", "Church & Ministry Operations Kit"),
        ("CT-LAUNCH-SOP-001", "SOP Builder Pack"),
    ],
    "ready": [
        ("CT-READY-A11Y-001", "Accessibility Preparation Pack"),
        ("CT-READY-AI-001", "AI Governance Readiness Pack"),
        ("CT-READY-EVIDENCE-001", "Evidence Binder Preparation Pack"),
        ("CT-READY-IR-001", "Incident Response Preparation Pack"),
        ("CT-READY-LAUNCH-001", "Business Launch Readiness Pack"),
        ("CT-READY-POLICY-001", "Policy System Readiness Pack"),
        ("CT-READY-PRIV-001", "Privacy & Data Readiness Pack"),
        ("CT-READY-SEC-001", "Cybersecurity Readiness Pack"),
        ("CT-READY-TRUST-001", "Customer & Partner Trust Pack"),
        ("CT-READY-VENDOR-001", "Vendor Risk Readiness Pack"),
    ],
    "procure": [
        ("CT-PROCURE-COMP-001", "Vendor Compare Workspace"),
        ("CT-PROCURE-CREATIVE-001", "Creative & Media Sourcing OS"),
        ("CT-PROCURE-DUE-001", "Vendor Due-Diligence Evidence Pack"),
        ("CT-PROCURE-MKT-001", "Marketing & Advertising Sourcing OS"),
        ("CT-PROCURE-NEG-001", "Negotiation Planning Pack"),
        ("CT-PROCURE-OPS-001", "Operations & Professional Services Sourcing OS"),
        ("CT-PROCURE-RFP-001", "RFP Builder Pack"),
        ("CT-PROCURE-RFQ-001", "RFQ Builder Pack"),
        ("CT-PROCURE-SOW-001", "SOW & Acceptance Pack"),
        ("CT-PROCURE-TECH-001", "Technology / SaaS Sourcing OS"),
    ],
}


def fixture() -> dict:
    products = []
    for platform, rows in SKUS.items():
        for sku, title in rows:
            products.append(
                {
                    "sku": sku,
                    "title": title,
                    "product_type": "toolkit",
                    "platform": platform,
                    "version": "1.0.0-candidate.4",
                    "asset_sha256": hashlib.sha256(sku.encode()).hexdigest(),
                    "byte_size": 16384,
                    "tax_profile_candidate": "document_download",
                }
            )
    surfaces = {
        platform: {
            "surface_id": f"ct.surface.crownthrive-{platform}.production",
            "platform_id": f"ct.platform.crownthrive-{platform}",
            "provider_url": f"https://crownthrive-{platform}.crownthrive.chatgpt.site",
            "preferred_custom_domain": f"{platform}.crownthrive.com",
            "package_qa": "PASS",
            "package_review_receipt": f"ct.integrity.{platform}.candidate4.review",
            "accessibility_state": "practices_tested_not_conformance_claim",
        }
        for platform in SKUS
    }
    return {
        "source_system": "commercial-gap-sites-2026-08-21-v1",
        "products": products,
        "surfaces": surfaces,
        "price_bands": {
            "toolkit": {
                "policy_version": "ct-pricing-v2",
                "minimum_credits": 9900,
                "target_credits": 14900,
                "maximum_credits": 29900,
                "minimum_comparables": 3,
                "minimum_sources": 2,
            }
        },
    }


class ReleaseFactoryTests(unittest.TestCase):
    def test_exact_30_product_hold_packet(self) -> None:
        output = generate(fixture())
        summary = validate(output, expected_products=30)
        self.assertEqual(summary, {"packages": 30, "pass_gates": 30, "hold_gates": 250})
        self.assertEqual(sum(1 for p in output["packages"] if p["platform"] == "ready"), 10)
        self.assertTrue(all(p["checkout_state"] == "closed" for p in output["packages"]))
        self.assertTrue(all(p["destination_state"].startswith("hold_") for p in output["packages"]))

    def test_ready_requires_professional_review(self) -> None:
        output = generate(fixture())
        ready = next(p for p in output["packages"] if p["platform"] == "ready")
        self.assertEqual(len(ready["gates"]), 10)
        self.assertEqual(ready["gates"][-1]["dimension_key"], "qualified_professional_review")
        self.assertEqual(ready["gates"][-1]["state"], "hold")

    def test_secret_shape_rejected(self) -> None:
        payload = fixture()
        payload["products"][0]["api_key"] = "must-not-pass"
        with self.assertRaises(ReleaseFactoryError):
            generate(payload)

    def test_generator_deterministic(self) -> None:
        first = generate(fixture())
        second = generate(fixture())
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
