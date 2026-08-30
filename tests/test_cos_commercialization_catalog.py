from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.commercialization.build_catalog import (
    CatalogError,
    build_catalog,
    validate_offer,
    validate_routing,
)
from scripts.commercialization.chlom_wallet_bridge import (
    WalletBridgeError,
    WalletPolicy,
    assert_transition,
    build_execution_envelope,
)
from scripts.commercialization.generate_adapters import generate_adapters
from scripts.commercialization.mesh_router import MeshRouteError, build_dispatch_envelope
from scripts.commercialization.package_release import PackageError, create_release

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = "a" * 40


def copy_control_files(target: Path) -> None:
    for relative in [
        "commercialization/policy.v1.json",
        "commercialization/package-targets.v1.json",
        "commercialization/routing/mesh-routing.v1.json",
        "commercialization/chlom/wallet-bridge.contract.v1.json",
        "commercialization/products/cos-community-discovery.v1.json",
        "commercialization/products/cos-commercial-license-request.v1.json",
    ]:
        source = ROOT / relative
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class CatalogTests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp)
        copy_control_files(temp)
        return temp

    def test_lifecycle_active_without_explicit_certification_is_withheld(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/active-only.json",
            {
                "component_id": "ct.test.active-only",
                "canonical_name": "Active Only",
                "component_type": "module",
                "version": "1.0.0",
                "lifecycle_state": "active",
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        withheld = {
            item["component_id"]: item["withheld_reasons"]
            for item in result["catalog"]["withheld"]
        }
        self.assertIn("ct.test.active-only", withheld)
        self.assertIn("missing_explicit_production_certification", withheld["ct.test.active-only"])

    def test_certified_component_gets_free_and_quote_offers(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/certified.json",
            {
                "component_id": "ct.test.certified",
                "canonical_name": "Certified Component",
                "component_type": "plugin",
                "version": "2.1.0",
                "production_certification": "PASS",
                "visibility": "public",
                "free_evaluation_authorized": True,
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        eligible = {item["component_id"] for item in result["catalog"]["components"]}
        self.assertIn("ct.test.certified", eligible)
        offers = [
            item
            for item in result["offers"]["offers"]
            if item["component_id"] == "ct.test.certified"
        ]
        self.assertEqual({item["price_mode"] for item in offers}, {"FREE", "NEGOTIATED"})
        self.assertEqual(
            next(item for item in offers if item["price_mode"] == "NEGOTIATED")["amount_minor"],
            None,
        )

    def test_certified_component_without_explicit_free_rights_gets_quote_only(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/quote-only.json",
            {
                "component_id": "ct.test.quote-only",
                "canonical_name": "Quote Only",
                "component_type": "module",
                "version": "1.0.0",
                "production_certification": "PASS",
                "visibility": "public",
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        offers = [
            item
            for item in result["offers"]["offers"]
            if item["component_id"] == "ct.test.quote-only"
        ]
        self.assertEqual([item["price_mode"] for item in offers], ["NEGOTIATED"])
        self.assertEqual(offers[0]["offer_state"], "REQUEST_QUOTE")

    def test_restricted_certified_component_is_withheld(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/restricted.json",
            {
                "component_id": "ct.test.restricted",
                "version": "1.0.0",
                "production_certification": "PASS",
                "visibility": "restricted",
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        row = next(
            item
            for item in result["catalog"]["withheld"]
            if item["component_id"] == "ct.test.restricted"
        )
        self.assertTrue(any(reason.startswith("blocked_visibility") for reason in row["withheld_reasons"]))

    def test_active_fixed_price_requires_economic_pass_and_wallet(self) -> None:
        base = {
            "offer_id": "ct.offer.fixed",
            "component_id": "ct.test",
            "component_version": "1.0.0",
            "offer_type": "FIXED_PRICE",
            "license_id": "ct.license.test",
            "offer_state": "ACTIVE",
            "price_mode": "FIXED",
            "amount_minor": 100,
            "currency": "USD",
            "wallet_route": "NONE",
            "entitlement_type": "licensed",
            "economic_gate_state": "HOLD",
            "rights_gate_state": "PASS",
        }
        failures = validate_offer(base)
        self.assertIn("active_fixed_or_metered_offer_requires_economic_gate_PASS", failures)
        self.assertIn("active_fixed_or_metered_offer_requires_CHLOM_WALLET", failures)

    def test_vault_reference_metadata_is_not_treated_as_secret_material(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/vault-ref.json",
            {
                "component_id": "ct.test.vault-ref",
                "version": "1.0.0",
                "production_certification": "PASS",
                "client_secret_source": "runtime_vault_reference_only",
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        eligible = {item["component_id"] for item in result["catalog"]["components"]}
        self.assertIn("ct.test.vault-ref", eligible)

    def test_arbitrary_value_under_secret_key_is_rejected(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/bad-secret.json",
            {
                "component_id": "ct.test.bad-secret",
                "version": "1.0.0",
                "production_certification": "PASS",
                "client_secret": "actual-secret-value",
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        self.assertEqual(result["catalog"]["counts"]["parse_failures"], 1)
        self.assertNotIn(
            "ct.test.bad-secret",
            {item["component_id"] for item in result["catalog"]["components"]},
        )

    def test_conflicting_certification_records_are_withheld(self) -> None:
        repo = self.make_repo()
        write_json(
            repo / "developers/manifests/conflict-pass.json",
            {
                "component_id": "ct.test.conflict",
                "version": "1.0.0",
                "production_certification": "PASS",
            },
        )
        write_json(
            repo / "data/conflict-hold.json",
            {
                "component_id": "ct.test.conflict",
                "version": "1.0.0",
                "production_certification": "HOLD",
            },
        )
        result = build_catalog(repo, repo / "out", SOURCE_SHA)
        row = next(
            item
            for item in result["catalog"]["withheld"]
            if item["component_id"] == "ct.test.conflict"
        )
        self.assertIn("conflicting_commercialization_source_records", row["withheld_reasons"])
        self.assertEqual(row["source_record_count"], 2)

    def test_catalog_is_deterministic(self) -> None:
        repo = self.make_repo()
        first = build_catalog(repo, repo / "out1", SOURCE_SHA)
        second = build_catalog(repo, repo / "out2", SOURCE_SHA)
        self.assertEqual(first["catalog"], second["catalog"])
        self.assertEqual(first["offers"], second["offers"])
        self.assertEqual(first["readiness"], second["readiness"])

    def test_routing_hot_lane_is_read_only(self) -> None:
        routing = json.loads(
            (ROOT / "commercialization/routing/mesh-routing.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_routing(routing), [])
        routing["lanes"]["hot"]["side_effects_allowed"] = True
        self.assertIn("hot_lane_must_be_read_only", validate_routing(routing))


