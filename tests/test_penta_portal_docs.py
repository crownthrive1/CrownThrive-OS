from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "scripts/penta_portal_docs.py"
FINALIZER = ROOT / "scripts/penta_portal_finalize.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


portal = load_module("penta_portal_docs", GENERATOR)
finalizer = load_module("penta_portal_finalize", FINALIZER)


class PentaPortalDocsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.census = json.loads((ROOT / "data/penta/namespace-census.v1.json").read_text(encoding="utf-8"))
        cls.os_registry = json.loads((ROOT / "data/penta/os-v1.registry.json").read_text(encoding="utf-8"))
        cls.seed = json.loads((ROOT / "data/penta/namespace-candidates.v1.json").read_text(encoding="utf-8"))
        cls.family_registry = json.loads((ROOT / "penta/registry/penta-families.v1.json").read_text(encoding="utf-8"))
        cls.records = cls.census["records"]

    def test_canonical_registry_coverage_is_exact(self):
        canonical = [r for r in self.records if r["namespace_state"] == "canonical"]
        self.assertEqual(len(canonical), self.os_registry["counts"]["total"])
        self.assertEqual(
            {portal.normalize(r["name"]) for r in canonical},
            {portal.normalize(r["canonical_name"]) for r in self.os_registry["systems"]},
        )

    def test_final_census_is_exact_single_identity_universe(self):
        expected = self.os_registry["counts"]["total"] + self.seed["candidate_count"]
        self.assertEqual(len(self.records), expected)
        self.assertEqual(self.census["counts"]["total"], expected)
        for record in self.records:
            self.assertEqual(len(re.findall(r"\bPenta", record["name"])), 1, record["name"])

    def test_every_seed_candidate_is_preserved(self):
        actual = {portal.normalize(r["name"]) for r in self.records}
        self.assertTrue({portal.normalize(x) for x in self.seed["candidates"]}.issubset(actual))

    def test_every_identity_has_one_dedicated_page(self):
        paths = [r["docs_path"] + ".mdx" for r in self.records]
        self.assertEqual(len(paths), len(set(paths)))
        for rel in paths:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_candidate_pages_are_fail_closed(self):
        for record in self.records:
            if record["namespace_state"] == "canonical":
                continue
            text = (ROOT / (record["docs_path"] + ".mdx")).read_text(encoding="utf-8").casefold()
            self.assertIn("not a production claim", text)
            self.assertIn("execution eligible", text)

    def test_family_and_directory_surfaces_exist(self):
        for rel in [
            "pentas.mdx",
            "pentas/all.mdx",
            "pentas/canonical.mdx",
            "pentas/candidates.mdx",
            "pentas/families.mdx",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)
        self.assertEqual(len(self.family_registry["families"]), 15)
        for family in self.family_registry["families"]:
            self.assertTrue((ROOT / f"pentas/families/{family['slug']}.mdx").exists())

    def test_mintlify_has_one_dedicated_pentas_tab(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
        tabs = docs["navigation"]["tabs"]
        matches = [tab for tab in tabs if isinstance(tab, dict) and tab.get("tab") == "Pentas"]
        self.assertEqual(len(matches), 1)

    def test_every_identity_is_in_pentas_navigation_exactly_once(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
        pages = finalizer.iter_navigation_pages(docs)
        self.assertEqual(len(pages), len(set(pages)))
        for record in self.records:
            self.assertEqual(pages.count(record["docs_path"]), 1, record["docs_path"])
        self.assertNotIn("automation/penta-family", pages)
        self.assertNotIn("automation/penta-os-v1", pages)

    def test_aggregate_parser_capture_is_removed(self):
        names = {r["name"] for r in self.records}
        self.assertNotIn(
            "PentaQuery, PentaSearch, PentaRead, PentaList, PentaParse, PentaResolve, PentaTransform, PentaValidate, PentaCache, PentaSync, and PentaIngest",
            names,
        )

    def test_finalizer_and_pentadocs_quality_are_clean(self):
        receipt = finalizer.check()
        self.assertEqual(receipt["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
