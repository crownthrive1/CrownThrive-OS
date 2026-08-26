import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scribe = load_module("pentascribe_candidate_disposition_test", ROOT / "penta/scribe/pentascribe.py")


class PentaCandidateDispositionTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "penta/scribe/registry.json").read_text(encoding="utf-8"))
        self.sources = json.loads((ROOT / "penta/scribe/sources.registry.json").read_text(encoding="utf-8"))
        self.vocab = scribe.build_federated_vocabulary(self.registry, self.sources)
        self.blocked = scribe.blocked_vocabulary(self.sources)

    def resolve(self, name):
        return self.vocab.get(scribe.semantic_key(name))

    def test_current_system_candidates_are_federated(self):
        expected = {
            "PentaGreen": "penta.green",
            "PentaOFAC": "penta.ofac",
            "PentaPR": "penta.pr",
            "PentaMerge": "penta.merge",
            "PentaCloser": "penta.closer",
        }
        for name, identity_id in expected.items():
            with self.subTest(name=name):
                resolved = self.resolve(name)
                self.assertIsNotNone(resolved)
                self.assertEqual(identity_id, resolved["id"])
                self.assertEqual("canonical_system", resolved["authority"])

    def test_pentamap_resolves_to_pentamaps_component(self):
        resolved = self.resolve("PentaMap")
        self.assertIsNotNone(resolved)
        self.assertEqual("penta.maps", resolved["id"])
        self.assertEqual("PentaMaps", resolved["canonical"])
        self.assertEqual("canonical_component", resolved["authority"])

    def test_redundant_or_superseded_candidates_are_blocked(self):
        for name in ("PentaAnalytics", "PentaLegal", "PentaFramework"):
            with self.subTest(name=name):
                self.assertIn(scribe.semantic_key(name), self.blocked)
                self.assertIsNone(self.resolve(name))

    def test_original_nine_candidate_names_no_longer_enter_review_queue(self):
        names = {
            "PentaAnalytics", "PentaCloser", "PentaFramework", "PentaGreen",
            "PentaLegal", "PentaMap", "PentaMerge", "PentaOFAC", "PentaPR",
        }
        discovery = scribe.discover_candidates(
            self.registry,
            [ROOT / "README.md", ROOT / "docs", ROOT / "data", ROOT / "penta"],
            self.sources,
        )
        candidates = {item["observed"] for item in discovery["candidates"]}
        self.assertFalse(names & candidates, f"resolved candidate(s) resurfaced: {sorted(names & candidates)}")

    def test_registration_does_not_create_trademark_state(self):
        for name in ("PentaGreen", "PentaOFAC", "PentaPR", "PentaMerge", "PentaCloser"):
            resolved = self.resolve(name)
            self.assertIsNone(resolved.get("term"))


if __name__ == "__main__":
    unittest.main()
