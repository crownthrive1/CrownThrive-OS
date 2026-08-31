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


class AdapterTests(unittest.TestCase):
    def test_generates_installable_metadata_adapters_for_all_declared_ecosystems(self) -> None:
        output = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, output)
        catalog = {
            "source_sha": SOURCE_SHA,
            "components": [
                {
                    "component_id": "ct.test.adapter",
                    "canonical_name": "Adapter Test",
                    "component_type": "plugin",
                    "version": "3.63.4.0",
                    "source_path": "developers/manifests/test.json",
                    "source_fingerprint": "b" * 64,
                    "catalog_state": "ELIGIBLE",
                    "offer_ids": ["ct.test.adapter.commercial-request-quote"],
                }
            ],
        }
        index = generate_adapters(catalog, output)
        self.assertEqual(index["component_count"], 1)
        self.assertEqual(
            set(index["ecosystems"]),
            {"npm", "pypi", "maven", "nuget", "cargo", "go", "composer", "rubygems", "swift", "dart", "oci"},
        )
        slug = index["components"][0]["slug"]
        package_json = json.loads((output / slug / "npm/package.json").read_text())
        self.assertEqual(package_json["crownthrive"]["publicationAuthorized"], False)
        tomllib.loads((output / slug / "pypi/pyproject.toml").read_text())
        tomllib.loads((output / slug / "cargo/Cargo.toml").read_text())
        ET.parse(output / slug / "maven/pom.xml")
        ET.parse(next((output / slug / "nuget").glob("*.nuspec")))
        json.loads((output / slug / "composer/composer.json").read_text())
        oci_index = json.loads((output / slug / "oci/index.json").read_text())
        self.assertEqual(oci_index["schemaVersion"], 2)
        self.assertTrue((output / "adapter-index.json").exists())

    def test_adapter_generation_is_deterministic(self) -> None:
        out1 = Path(tempfile.mkdtemp())
        out2 = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out1)
        self.addCleanup(shutil.rmtree, out2)
        catalog = {
            "source_sha": SOURCE_SHA,
            "components": [
                {
                    "component_id": "ct.test.deterministic-adapter",
                    "canonical_name": "Deterministic Adapter",
                    "component_type": "module",
                    "version": "1.2.3-rc.1",
                    "source_fingerprint": "c" * 64,
                }
            ],
        }
        first = generate_adapters(catalog, out1)
        second = generate_adapters(catalog, out2)
        self.assertEqual(first, second)
        first_files = {
            path.relative_to(out1).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in out1.rglob("*")
            if path.is_file()
        }
        second_files = {
            path.relative_to(out2).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in out2.rglob("*")
            if path.is_file()
        }
        self.assertEqual(first_files, second_files)


class MeshRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.routing = json.loads(
            (ROOT / "commercialization/routing/mesh-routing.v1.json").read_text(encoding="utf-8")
        )

    def test_hot_read_routes_without_side_effect_authority(self) -> None:
        envelope = build_dispatch_envelope(
            self.routing,
            "commercial.catalog.list",
            {"query": "plugins"},
            source_sha=SOURCE_SHA,
        )
        self.assertEqual(envelope["lane"], "hot")
        self.assertFalse(envelope["side_effects"])
        self.assertEqual(envelope["state"], "READ_READY")
        self.assertEqual(len(envelope["target_mcp_servers"]), 1)

    def test_warm_side_effect_requires_explicit_authority(self) -> None:
        request = {"principal_did": "did:example:buyer", "idempotency_key": "idem-1"}
        with self.assertRaises(MeshRouteError):
            build_dispatch_envelope(
                self.routing,
                "commercial.license.quote.request",
                request,
                source_sha=SOURCE_SHA,
                dail_state="PASS",
                chlom_state="PASS",
            )

    def test_chlom_and_dail_gates_are_enforced(self) -> None:
        request = {"principal_did": "did:example:buyer", "idempotency_key": "idem-2"}
        with self.assertRaises(MeshRouteError):
            build_dispatch_envelope(
                self.routing,
                "commercial.license.quote.request",
                request,
                source_sha=SOURCE_SHA,
                authorize_side_effects=True,
                dail_state="HOLD",
                chlom_state="PASS",
            )
        with self.assertRaises(MeshRouteError):
            build_dispatch_envelope(
                self.routing,
                "commercial.license.quote.request",
                request,
                source_sha=SOURCE_SHA,
                authorize_side_effects=True,
                dail_state="PASS",
                chlom_state="HOLD",
            )

    def test_wallet_circuit_breaker_denies_money_lane(self) -> None:
        request = {"principal_did": "did:example:buyer", "idempotency_key": "idem-3"}
        with self.assertRaises(MeshRouteError):
            build_dispatch_envelope(
                self.routing,
                "commercial.wallet.intent.create",
                request,
                source_sha=SOURCE_SHA,
                authorize_side_effects=True,
                dail_state="PASS",
                chlom_state="PASS",
                wallet_state="UNAVAILABLE",
            )

    def test_valid_warm_chlom_dispatch_targets_both_mcp_servers(self) -> None:
        request = {"principal_did": "did:example:buyer", "idempotency_key": "idem-4"}
        envelope = build_dispatch_envelope(
            self.routing,
            "commercial.license.quote.request",
            request,
            source_sha=SOURCE_SHA,
            authorize_side_effects=True,
            dail_state="PASS",
            chlom_state="PASS",
        )
        self.assertEqual(envelope["lane"], "warm")
        self.assertTrue(envelope["execution_authorized"])
        self.assertFalse(envelope["provider_execution_performed"])
        self.assertEqual(len(envelope["target_mcp_servers"]), 2)

    def test_mcp_contract_covers_every_registered_mesh_operation(self) -> None:
        contract = json.loads(
            (ROOT / "commercialization/mcp/commercialization-tools.v1.json").read_text(encoding="utf-8")
        )
        declared = {tool["name"]: tool for tool in contract["tools"]}
        routed = {
            operation: lane_name
            for lane_name, lane in self.routing["lanes"].items()
            for operation in lane["operations"]
        }
        self.assertEqual(set(declared), set(routed))
        for operation, lane_name in routed.items():
            self.assertEqual(declared[operation]["lane"], lane_name)
            self.assertEqual(
                declared[operation]["side_effects"],
                self.routing["lanes"][lane_name]["side_effects_allowed"],
            )

    def test_openapi_contract_is_server_neutral_and_mesh_bound(self) -> None:
        contract = json.loads(
            (ROOT / "commercialization/api/openapi.v1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(contract["openapi"], "3.1.0")
        self.assertNotIn("servers", contract)
        self.assertTrue(contract["x-crownthrive-no-live-server-assertion"])
        operations = {
            operation["x-crownthrive-mesh-operation"]
            for path_item in contract["paths"].values()
            for operation in path_item.values()
            if isinstance(operation, dict) and "x-crownthrive-mesh-operation" in operation
        }
        routed = {
            operation
            for lane in self.routing["lanes"].values()
            for operation in lane["operations"]
        }
        self.assertTrue(operations.issubset(routed))

    def test_secret_bearing_dispatch_is_rejected(self) -> None:
        with self.assertRaises(MeshRouteError):
            build_dispatch_envelope(
                self.routing,
                "commercial.catalog.list",
                {"access_token": "not-allowed"},
                source_sha=SOURCE_SHA,
            )


