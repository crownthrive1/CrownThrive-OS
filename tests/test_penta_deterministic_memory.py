#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "runtime" / "penta_deterministic_memory.py"
SPEC = importlib.util.spec_from_file_location("penta_deterministic_memory", MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
SPEC.loader.exec_module(mod)


class PentaDeterministicMemoryTests(unittest.TestCase):
    def fixture(self) -> tempfile.TemporaryDirectory[str]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        for path in ("config", "data/penta", "penta/registry"):
            (root / path).mkdir(parents=True, exist_ok=True)

        config = json.loads(
            (Path(__file__).resolve().parents[1] / mod.CONFIG_PATH).read_text(encoding="utf-8")
        )
        (root / mod.CONFIG_PATH).write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")

        systems = [
            {
                "machine_key": "penta.brain",
                "canonical_name": "PentaBrain",
                "kind": "system",
                "maturity": "implemented",
                "risk_ceiling": "D2",
                "execution_eligible_by_registry": False,
            },
            {
                "machine_key": "penta.context",
                "canonical_name": "PentaContext",
                "kind": "system",
                "maturity": "production",
                "risk_ceiling": "D2",
                "execution_eligible_by_registry": True,
            },
            {
                "machine_key": "penta.route",
                "canonical_name": "PentaRoute",
                "kind": "system",
                "maturity": "implemented",
                "risk_ceiling": "D2",
                "execution_eligible_by_registry": True,
            },
            {
                "machine_key": "penta.future",
                "canonical_name": "PentaFuture",
                "kind": "system",
                "maturity": "specified",
                "risk_ceiling": "D1",
                "execution_eligible_by_registry": False,
            },
        ]
        os_registry = {
            "registry_id": "fixture.penta.os",
            "version": "1.0.0",
            "counts": {"total": len(systems)},
            "systems": systems,
        }
        (root / mod.OS_REGISTRY_PATH).write_text(json.dumps(os_registry, indent=2) + "\n")
        census = {
            "records": [
                {"canonical_machine_key": "penta.brain", "family_id": "observability-organic"},
                {"canonical_machine_key": "penta.context", "family_id": "knowledge-semantics-data"},
                {"canonical_machine_key": "penta.route", "family_id": "routing-interoperability"},
                {"canonical_machine_key": "penta.future", "family_id": "automation-agentic"},
            ]
        }
        (root / mod.NAMESPACE_CENSUS_PATH).write_text(json.dumps(census, indent=2) + "\n")
        families = {
            "families": [
                {"family_id": "observability-organic", "explicit_members": ["PentaBrain"]},
                {"family_id": "knowledge-semantics-data", "explicit_members": ["PentaContext"]},
                {"family_id": "routing-interoperability", "explicit_members": ["PentaRoute"]},
                {"family_id": "automation-agentic", "explicit_members": ["PentaFuture"]},
            ]
        }
        (root / mod.FAMILY_REGISTRY_PATH).write_text(json.dumps(families, indent=2) + "\n")
        tmp.root = root
        return tmp

    def test_repeated_build_is_identical(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            first = mod.build_manifest(root)
            second = mod.build_manifest(root)
            self.assertEqual(mod.render_manifest(first), mod.render_manifest(second))
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])

    def test_every_member_has_literal_quota_and_survival_contract(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            self.assertEqual(4, manifest["counts"]["canonical_pentas"])
            for row in manifest["assignments"]:
                self.assertGreater(row["hard_quota_bytes"], 0)
                self.assertGreater(row["working_set_bytes"], 0)
                self.assertEqual("strict-v1", row["orchestration_determinism"])
                self.assertIn("restart_behavior", row["survival_contract"])

    def test_pentabrain_is_large_active_fail_closed_non_pm_executable(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            brain = next(row for row in manifest["assignments"] if row["machine_key"] == "penta.brain")
            self.assertEqual("brain-v1", brain["memory_profile"])
            self.assertEqual(1073741824, brain["hard_quota_bytes"])
            self.assertTrue(brain["write_enabled"])
            self.assertEqual("ACTIVE_FAIL_CLOSED", brain["activation_state"])
            self.assertFalse(brain["execution_eligible_by_registry"])
            self.assertEqual("anchor", brain["brain_mesh_role"])
            self.assertEqual("bounded-semantic-v1", brain["semantic_determinism"])
            self.assertTrue(brain["model_version_required"])

    def test_specified_member_is_cold_reserved_without_promotion(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            future = next(row for row in manifest["assignments"] if row["machine_key"] == "penta.future")
            self.assertEqual("cold-reserved-v1", future["memory_profile"])
            self.assertFalse(future["write_enabled"])
            self.assertEqual("COLD_RESERVED", future["activation_state"])

    def test_receipt_is_stable_across_input_key_order(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            a = mod.deterministic_receipt(
                manifest,
                machine_key="penta.brain",
                operation="health.assess",
                input_value={"b": 2, "a": 1},
                result_value={"state": "hold", "score": 5},
            )
            b = mod.deterministic_receipt(
                manifest,
                machine_key="penta.brain",
                operation="health.assess",
                input_value={"a": 1, "b": 2},
                result_value={"score": 5, "state": "hold"},
            )
            self.assertEqual(a["request_hash"], b["request_hash"])
            self.assertEqual(a["result_sha256"], b["result_sha256"])
            self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])

    def test_semantic_model_requires_pinned_versions(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            with self.assertRaises(mod.DeterministicMemoryError):
                mod.deterministic_receipt(
                    manifest,
                    machine_key="penta.future",
                    operation="draft",
                    input_value={"topic": "x"},
                    model="model-x",
                )

    def test_provider_execution_requires_pinned_provider_version(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            with self.assertRaises(mod.DeterministicMemoryError):
                mod.deterministic_receipt(
                    manifest,
                    machine_key="penta.context",
                    operation="provider.read",
                    input_value={"key": "x"},
                    provider="provider-x",
                )

    def test_unclassified_member_fails_closed(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            path = root / mod.NAMESPACE_CENSUS_PATH
            census = json.loads(path.read_text())
            census["records"] = [
                row for row in census["records"]
                if row["canonical_machine_key"] != "penta.route"
            ]
            path.write_text(json.dumps(census))
            family_path = root / mod.FAMILY_REGISTRY_PATH
            families = json.loads(family_path.read_text())
            for family in families["families"]:
                family["explicit_members"] = [
                    name for name in family["explicit_members"] if name != "PentaRoute"
                ]
            family_path.write_text(json.dumps(families))
            with self.assertRaises(mod.DeterministicMemoryError):
                mod.build_manifest(root)

    def test_manifest_tamper_is_detected(self):
        tmp = self.fixture()
        root = tmp.root
        with tmp:
            manifest = mod.build_manifest(root)
            tampered = copy.deepcopy(manifest)
            tampered["assignments"][0]["hard_quota_bytes"] += 1
            with self.assertRaises(mod.DeterministicMemoryError):
                mod.validate_manifest(
                    tampered,
                    config=json.loads((root / mod.CONFIG_PATH).read_text()),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
