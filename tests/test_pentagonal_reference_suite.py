from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/pentagonal_reference_suite.py"

spec = importlib.util.spec_from_file_location("pentagonal_reference_suite", SCRIPT)
assert spec and spec.loader
suite = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = suite
spec.loader.exec_module(suite)


class PentagonalReferenceSuiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "data/penta/pentagonal-reference.v1.json").read_text(encoding="utf-8"))

    def test_five_axes_are_registry_grounded(self):
        component_registry = json.loads((ROOT / "penta/registry/penta-component-registry.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(["truth", "authority", "execution", "interoperation", "continuity"], component_registry["axes"])
        self.assertEqual(component_registry["axes"], [x["id"] for x in self.manifest["pentagonal_model"]["axes"]])
        self.assertEqual(5, self.manifest["counts"]["pentagonal_axes"])

    def test_penta_definition_separates_identity_from_agent_and_authority(self):
        definition = self.manifest["penta_definition"].casefold()
        for phrase in ["stable", "contract-bounded", "not synonymous", "autonomous agent", "does not by itself grant"]:
            self.assertIn(phrase, definition)

    def test_dictionary_is_deep_and_source_linked(self):
        self.assertGreaterEqual(self.manifest["counts"]["terms"], 80)
        terms = self.manifest["terms"]
        self.assertEqual(len(terms), len({x["term"].casefold() for x in terms}))
        for record in terms:
            self.assertTrue(record["definition"])
            self.assertTrue(record["machine_rule"])
            self.assertTrue(record["source_refs"])
            self.assertEqual(64, len(record["record_sha256"]))
        required = {"Penta", "Pentagonal Architecture", "PentaScribe", "PentaDocs", "CHLOM", "DAIL", "Exact-head"}
        self.assertTrue(required.issubset({x["term"] for x in terms}))

    def test_full_paper_series(self):
        self.assertGreaterEqual(self.manifest["counts"]["papers"], 10)
        paper_ids = {x["id"] for x in self.manifest["papers"]}
        for required in {
            "penta-doctrine",
            "pentagonal-architecture",
            "penta-authority-evidence-state",
            "penta-development-contract",
            "penta-agent-ingestion-routing",
            "penta-lifecycle-reliability",
            "penta-documentation-semantics",
        }:
            self.assertIn(required, paper_ids)
        for paper in self.manifest["papers"]:
            path = ROOT / (paper["route"] + ".mdx")
            self.assertTrue(path.exists(), path)
            text = path.read_text(encoding="utf-8")
            self.assertIn("## Thesis", text)
            self.assertIn("## Machine/implementation consequences", text)

    def test_reference_routes_are_navigated_once(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
        pages = suite.nav_pages(docs)
        for route in self.manifest["reference_routes"]:
            self.assertEqual(1, pages.count(route), route)

    def test_agent_and_developer_boot_sequences_are_wired(self):
        agent_text = (ROOT / "pentas/agents.mdx").read_text(encoding="utf-8")
        dev_text = (ROOT / "pentas/development.mdx").read_text(encoding="utf-8")
        portal_text = (ROOT / "pentas.mdx").read_text(encoding="utf-8")
        self.assertEqual(1, agent_text.count(suite.BEGIN_AGENT))
        self.assertIn("data/penta/pentagonal-reference.v1.json", agent_text)
        self.assertEqual(1, dev_text.count(suite.BEGIN_DEV))
        self.assertIn("Pentagonal developer read order", dev_text)
        self.assertEqual(1, portal_text.count(suite.BEGIN_PORTAL))
        self.assertIn("Pentagonal reference suite", portal_text)

    def test_jsonl_is_machine_ingestible_and_one_to_one(self):
        lines = [
            json.loads(line)
            for line in (ROOT / "data/penta/pentagonal-reference.v1.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        expected = self.manifest["counts"]["terms"] + self.manifest["counts"]["papers"]
        self.assertEqual(expected, len(lines))
        self.assertEqual(self.manifest["terms"], [{k: v for k, v in x.items() if k != "record_type"} for x in lines if x["record_type"] == "term"])
        self.assertEqual(self.manifest["papers"], [{k: v for k, v in x.items() if k != "record_type"} for x in lines if x["record_type"] == "paper"])

    def test_reference_pages_carry_current_manifest_hash(self):
        expected = f"<!-- pentagonal-reference-sha256:{self.manifest['manifest_sha256']} -->"
        for route in self.manifest["reference_routes"]:
            path = ROOT / (route + ".mdx")
            self.assertTrue(path.exists(), path)
            self.assertIn(expected, path.read_text(encoding="utf-8"), route)

    def test_deterministic_check_passes(self):
        result = suite.check()
        self.assertEqual("PASS", result["status"])
        self.assertEqual(5, result["axes"])
        self.assertGreaterEqual(result["terms"], 80)
        self.assertGreaterEqual(result["papers"], 10)


if __name__ == "__main__":
    unittest.main()
