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

    def test_known_namespace_and_machine_key_do_not_drift(self) -> None:
        root = self.make_root()
        path = root / "runtime/example.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("TARGET = 'PentaKnown'\nKEY = 'penta.known'\n", encoding="utf-8")

        report = build_report(root)

        self.assertEqual(report["counts"]["total_unknown_observations"], 0)

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
        path.write_text("TARGET = 'PentaExtension'\nKEY = 'penta.extension'\n", encoding="utf-8")

        report = build_report(root)

        self.assertEqual(report["counts"]["total_unknown_observations"], 0)
        self.assertEqual(report["counts"]["known_namespace_identities"], 3)

    def test_unknown_symbol_and_machine_key_are_routed_as_candidates(self) -> None:
        root = self.make_root()
        path = root / "runtime/example.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("TARGET = 'PentaNewThing'\nKEY = 'penta.new-thing'\n", encoding="utf-8")

        report = build_report(root)

        self.assertEqual(report["counts"]["unknown_display_symbols"], 1)
        self.assertEqual(report["counts"]["unknown_machine_keys"], 1)
        self.assertEqual(report["unknown_display_symbols"][0]["value"], "PentaNewThing")
        self.assertEqual(report["unknown_machine_keys"][0]["value"], "penta.new-thing")
        self.assertEqual(report["routing"]["unknown_identity_state"], "CANDIDATE_DISCOVERY")
        self.assertFalse(report["routing"]["automatic_canonical_registration"])

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
