from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/penta_portal_docs.py"

spec = importlib.util.spec_from_file_location("penta_portal_docs", SCRIPT)
assert spec and spec.loader
portal = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = portal
spec.loader.exec_module(portal)

class PentaPortalDocsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.census = json.loads((ROOT / "data/penta/namespace-census.v1.json").read_text(encoding="utf-8"))
        cls.os_registry = json.loads((ROOT / "data/penta/os-v1.registry.json").read_text(encoding="utf-8"))
        cls.seed = json.loads((ROOT / "data/penta/namespace-candidates.v1.json").read_text(encoding="utf-8"))
        cls.records = cls.census["records"]

    def test_canonical_registry_coverage_is_exact(self):
        canonical = [r for r in self.records if r["namespace_state"] == "canonical"]
        self.assertEqual(len(canonical), self.os_registry["counts"]["total"])
        self.assertEqual(
            {portal.normalize(r["name"]) for r in canonical},
            {portal.normalize(r["canonical_name"]) for r in self.os_registry["systems"]},
        )

    def test_every_seed_candidate_is_preserved(self):
        actual = {portal.normalize(r["name"]) for r in self.records}
        self.assertTrue({portal.normalize(x) for x in self.seed["candidates"]}.issubset(actual))
        self.assertGreaterEqual(len(self.records), self.os_registry["counts"]["total"] + self.seed["candidate_count"])

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
            "pentas/index.mdx",
            "pentas/all.mdx",
            "pentas/canonical/index.mdx",
            "pentas/candidates/index.mdx",
            "pentas/families.mdx",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)
        family_registry = json.loads((ROOT / "penta/registry/penta-families.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(len(family_registry["families"]), 15)
        for family in family_registry["families"]:
            self.assertTrue((ROOT / f"pentas/families/{family['slug']}.mdx").exists())

    def test_mintlify_has_dedicated_pentas_tab(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
        tabs = docs["navigation"]["tabs"]
        matches = [tab for tab in tabs if isinstance(tab, dict) and tab.get("tab") == "Pentas"]
        self.assertEqual(len(matches), 1)

    def test_generator_is_clean(self):
        portal.check_artifacts()

if __name__ == "__main__":
    unittest.main()
