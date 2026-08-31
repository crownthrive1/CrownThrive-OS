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


class WalletBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent_policy = json.loads(
            (ROOT / "runners/chlom-agent-wallet/config/policy.base-usdc.json").read_text(encoding="utf-8")
        ) if (ROOT / "runners/chlom-agent-wallet/config/policy.base-usdc.json").exists() else {
            "primary_chain": {"chain_id": 8453},
            "primary_asset": {"symbol": "USDC"},
            "execution": {
                "max_unattended_value_minor": 0,
                "idempotency_required": True,
                "read_after_write_required": True,
            },
        }
        cls.contract = json.loads(
            (ROOT / "commercialization/chlom/wallet-bridge.contract.v1.json").read_text(encoding="utf-8")
        )
        cls.policy = WalletPolicy.from_documents(cls.agent_policy, cls.contract)

    def base_intent(self, amount: int = 0) -> dict[str, object]:
        return {
            "intent_id": "intent-001",
            "idempotency_key": "idem-001",
            "principal_did": "did:example:buyer",
            "component_id": "ct.test.product",
            "component_version": "1.0.0",
            "offer_id": "ct.offer.test",
            "license_id": "ct.license.test",
            "amount_minor": amount,
            "currency": "USD",
            "purpose": "license",
            "source_sha": SOURCE_SHA,
            "quote_fingerprint": "quote-hash" if amount else "NO_QUOTE_FREE",
            "requested_at": "2026-08-30T00:00:00Z",
            "wallet_route": "CHLOM_WALLET" if amount else "NONE",
            "ecac_state": "PASS" if amount else "NOT_REQUIRED",
            "license_acceptance_state": "PASS",
        }

    def test_free_intent_never_routes_money(self) -> None:
        envelope = build_execution_envelope(self.base_intent(0), self.policy)
        self.assertEqual(envelope["execution_mode"], "FREE_NO_TRANSFER")
        self.assertEqual(envelope["amount_minor"], 0)

    def test_paid_intent_requires_human_authorization_at_zero_ceiling(self) -> None:
        with self.assertRaises(WalletBridgeError):
            build_execution_envelope(self.base_intent(2500), self.policy)
        envelope = build_execution_envelope(
            self.base_intent(2500), self.policy, human_authorized=True
        )
        self.assertEqual(envelope["execution_mode"], "AUTHORIZED_PROVIDER_HANDOFF")
        self.assertFalse(envelope["settlement_creates_entitlement"])

    def test_paid_intent_requires_ecac(self) -> None:
        intent = self.base_intent(2500)
        intent["ecac_state"] = "HOLD"
        with self.assertRaises(WalletBridgeError):
            build_execution_envelope(intent, self.policy, human_authorized=True)

    def test_secret_fields_are_rejected(self) -> None:
        intent = self.base_intent(0)
        intent["private_key"] = "do-not-store"
        with self.assertRaises(WalletBridgeError):
            build_execution_envelope(intent, self.policy)

    def test_state_machine_rejects_invalid_transition(self) -> None:
        assert_transition(self.contract, "DRAFT", "QUOTED")
        with self.assertRaises(WalletBridgeError):
            assert_transition(self.contract, "DRAFT", "SETTLED")


class PackageTests(unittest.TestCase):
    def test_scanner_signatures_do_not_self_trigger(self) -> None:
        repo = Path(tempfile.mkdtemp())
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        self.addCleanup(shutil.rmtree, out)
        target = repo / "scripts/commercialization/package_release.py"
        target.parent.mkdir(parents=True)
        target.write_text((ROOT / "scripts/commercialization/package_release.py").read_text(), encoding="utf-8")
        manifest = create_release(repo, out, "1.0.0-rc.1", SOURCE_SHA)
        self.assertEqual(manifest["release_state"], "BUILT_UNPUBLISHED")

    def test_actual_secret_like_payload_is_rejected(self) -> None:
        repo = Path(tempfile.mkdtemp())
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        self.addCleanup(shutil.rmtree, out)
        target = repo / "commercialization/bad.txt"
        target.parent.mkdir(parents=True)
        target.write_text("token=" + "sk" + "_live_" + "A" * 24, encoding="utf-8")
        with self.assertRaises(PackageError):
            create_release(repo, out, "1.0.0-rc.1", SOURCE_SHA)

    def test_release_includes_catalog_and_release_note_attachments(self) -> None:
        repo = Path(tempfile.mkdtemp())
        out = Path(tempfile.mkdtemp())
        catalog = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        self.addCleanup(shutil.rmtree, out)
        self.addCleanup(shutil.rmtree, catalog)
        (repo / "commercialization").mkdir(parents=True)
        (repo / "commercialization/README.md").write_text("stable\n", encoding="utf-8")
        notes = repo / "notes.md"
        notes.write_text("# Release notes\n", encoding="utf-8")
        for source_name in ["catalog.json", "offers.json", "install-index.json", "mesh-routing.json", "readiness.json"]:
            write_json(catalog / source_name, {"source_sha": SOURCE_SHA, "name": source_name})
        write_json(catalog / "registry-adapters/adapter-index.json", {"source_sha": SOURCE_SHA})
        write_text_target = catalog / "registry-adapters/test/npm/package.json"
        write_text_target.parent.mkdir(parents=True, exist_ok=True)
        write_text_target.write_text('{"name":"@crownthrive/test","version":"1.0.0"}\n', encoding="utf-8")
        manifest = create_release(
            repo,
            out,
            "1.0.0-rc.1",
            SOURCE_SHA,
            catalog_dir=catalog,
            release_notes=notes,
        )
        names = {item["name"] for item in manifest["artifacts"]}
        self.assertTrue(
            {
                "RELEASE_NOTES.md",
                "CATALOG.json",
                "OFFERS.json",
                "INSTALL_INDEX.json",
                "MESH_ROUTING.json",
                "READINESS.json",
                "REGISTRY_ADAPTERS.zip",
                "REGISTRY_ADAPTERS.tar.gz",
            }.issubset(names)
        )
        checksum_text = (out / "SHA256SUMS").read_text(encoding="utf-8")
        self.assertIn("CATALOG.json", checksum_text)
        self.assertIn("RELEASE_NOTES.md", checksum_text)
        self.assertIn("REGISTRY_ADAPTERS.zip", checksum_text)

    def test_release_archives_are_reproducible(self) -> None:
        repo = Path(tempfile.mkdtemp())
        out1 = Path(tempfile.mkdtemp())
        out2 = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        self.addCleanup(shutil.rmtree, out1)
        self.addCleanup(shutil.rmtree, out2)
        (repo / "commercialization").mkdir(parents=True)
        (repo / "commercialization/README.md").write_text("stable\n", encoding="utf-8")
        (repo / "scripts/commercialization").mkdir(parents=True)
        script = repo / "scripts/commercialization/tool.py"
        script.write_text("print('ok')\n", encoding="utf-8")
        script.chmod(0o755)
        first = create_release(repo, out1, "1.0.0-rc.1", SOURCE_SHA)
        second = create_release(repo, out2, "1.0.0-rc.1", SOURCE_SHA)
        for artifact in first["artifacts"]:
            other = next(item for item in second["artifacts"] if item["name"] == artifact["name"])
            self.assertEqual(artifact["sha256"], other["sha256"])


if __name__ == "__main__":
    unittest.main()
