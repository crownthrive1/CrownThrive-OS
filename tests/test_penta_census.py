from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.penta_census import build_report


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


class PentaCensusTests(unittest.TestCase):
    def make_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        write_json(
            root / "data/penta/namespace-census.v1.json",
            {
                "records": [
                    {
                        "name": "PentaKnown",
                        "namespace_state": "canonical",
                        "canonical_machine_key": "penta.known",
                    },
                    {
                        "name": "PentaCandidate",
                        "namespace_state": "candidate",
                        "canonical_machine_key": None,
                    },
                ]
            },
        )
        return root

    def test_known_namespace_reference_does_not_drift(self) -> None:
        root = self.make_root()
        path = root / "runtime/example.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("TARGET = 'PentaKnown'\n", encoding="utf-8")

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 0)
        self.assertEqual(report["counts"]["advisory_unstructured_symbol_references"], 0)

    def test_governed_extension_is_known_without_canonical_promotion(self) -> None:
        root = self.make_root()
        write_json(
            root / "data/penta/systems.extensions.example.json",
            {
                "systems": [
                    {
                        "machine_key": "penta.extension",
                        "canonical_name": "PentaExtension",
                        "maturity": "implemented",
                    }
                ]
            },
        )
        path = root / "runtime/example.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("TARGET = 'PentaExtension'\n", encoding="utf-8")

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 0)
        self.assertEqual(report["counts"]["advisory_unstructured_symbol_references"], 0)
        self.assertEqual(report["counts"]["known_namespace_identities"], 3)

    def test_unknown_structured_identity_declaration_is_hard_gated(self) -> None:
        root = self.make_root()
        write_json(
            root / "penta/registry/example.json",
            {
                "systems": [
                    {
                        "canonical_name": "PentaNewThing",
                        "machine_key": "penta.new-thing",
                    }
                ]
            },
        )

        report = build_report(root)

        self.assertEqual(report["counts"]["unknown_declared_display_identities"], 1)
        self.assertEqual(report["counts"]["unknown_declared_machine_identities"], 1)
        self.assertEqual(report["counts"]["strict_unknown_declarations"], 2)
        self.assertEqual(report["unknown_declared_display_identities"][0]["value"], "PentaNewThing")
        self.assertEqual(report["unknown_declared_machine_identities"][0]["value"], "penta.new-thing")

    def test_root_penta_registry_single_token_name_is_identity_declaration(self) -> None:
        root = self.make_root()
        write_json(
            root / "penta/registry/provision.json",
            {
                "schema_version": "1.0.0",
                "registry_id": "ct.penta.provision.v1",
                "canonical_name": "PentaProvision",
                "status": "active",
            },
        )

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 1)
        self.assertEqual(report["unknown_declared_display_identities"][0]["value"], "PentaProvision")

    def test_family_and_composite_canonical_names_are_not_penta_identities(self) -> None:
        root = self.make_root()
        write_json(
            root / "penta/registry/families.json",
            {
                "registry_id": "ct.registry.penta-families.v1",
                "canonical_name": "Penta Family of Families",
                "families": [
                    {
                        "family_id": "example",
                        "canonical_name": "Penta Example Family",
                    }
                ],
            },
        )

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 0)

    def test_system_key_only_component_bridge_is_not_penta_identity(self) -> None:
        root = self.make_root()
        write_json(
            root / "data/penta/component.json",
            {
                "registry_id": "ct.pentamarketer.persona-execution-bridge.v1",
                "system_key": "penta.persona-execution",
                "canonical_name": "PentaMarketer Persona Execution Bridge",
                "version": "1.0.0",
            },
        )

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 0)

    def test_unstructured_code_symbol_is_advisory_not_identity_promotion(self) -> None:
        root = self.make_root()
        path = root / "runtime/example.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("class PentaNewThingError(Exception):\n    pass\n", encoding="utf-8")

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 0)
        self.assertEqual(report["counts"]["advisory_unstructured_symbol_references"], 1)
        self.assertEqual(report["advisory_unstructured_symbol_references"][0]["value"], "PentaNewThingError")
        self.assertEqual(report["advisory_unstructured_symbol_references"][0]["state"], "SEMANTIC_REVIEW_PENDING")

    def test_non_identity_penta_machine_events_are_not_declarations(self) -> None:
        root = self.make_root()
        write_json(
            root / "data/penta/events.json",
            {
                "events": [
                    "penta.marketer.queue.enqueued",
                    "penta.operations.duration_seconds",
                ]
            },
        )

        report = build_report(root)

        self.assertEqual(report["counts"]["strict_unknown_declarations"], 0)

    def test_report_is_deterministic(self) -> None:
        root = self.make_root()
        path = root / "scripts/example.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("TARGET = 'PentaKnown'\n", encoding="utf-8")

        first = build_report(root)
        second = build_report(root)

        self.assertEqual(first, second)
        self.assertEqual(len(first["source_digest_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
