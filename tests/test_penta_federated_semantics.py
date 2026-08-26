import json
import pathlib
import tempfile
import unittest
import importlib.util

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


scribe = load_module("pentascribe_federation_test", ROOT / "penta/scribe/pentascribe.py")
marketer = load_module("pentamarketer_federation_test", ROOT / "penta/marketer/pentamarketer.py")


class PentaFederatedSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "penta/scribe/registry.json").read_text(encoding="utf-8"))
        self.sources = json.loads((ROOT / "penta/scribe/sources.registry.json").read_text(encoding="utf-8"))
        self.policy = json.loads((ROOT / "penta/marketer/policy.json").read_text(encoding="utf-8"))
        self.campaign = json.loads((ROOT / "penta/marketer/campaign.example.json").read_text(encoding="utf-8"))

    def test_federation_resolves_system_component_alias_and_primitive(self):
        vocab = scribe.build_federated_vocabulary(self.registry, self.sources)
        for name in ("PentaMedia", "PentaRoute", "PentaML", "PentaTun"):
            self.assertIn(scribe.semantic_key(name), vocab, name)
        self.assertNotIn(scribe.semantic_key("PentaCapital"), vocab)

    def test_discovery_separates_federated_rejected_and_true_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            source = pathlib.Path(d) / "input.md"
            source.write_text("PentaMedia PentaTun PentaCapital PentaFuture", encoding="utf-8")
            result = scribe.discover_candidates(self.registry, [source], self.sources)
            self.assertEqual(["PentaFuture"], [item["observed"] for item in result["candidates"]])
            self.assertEqual({"PentaMedia", "PentaTun"}, {item["observed"] for item in result["federated_observations"]})
            self.assertEqual(["PentaCapital"], [item["observed"] for item in result["rejected_observations"]])

    def test_marketer_accepts_federated_terms(self):
        campaign = dict(self.campaign)
        campaign["terms"] = ["PentaMedia", "PentaRoute", "PentaTun"]
        errors, resolved = marketer.validate_campaign(campaign, self.registry, self.policy, self.sources)
        self.assertEqual([], errors)
        self.assertEqual(3, len(resolved))
        self.assertTrue(all(item["authority_source"] for item in resolved))

    def test_federation_never_infers_registered_mark_status(self):
        campaign = dict(self.campaign)
        campaign["terms"] = ["PentaMedia"]
        campaign["message"] = "PentaMedia® is ready."
        errors, _ = marketer.validate_campaign(campaign, self.registry, self.policy, self.sources)
        self.assertTrue(any("® used" in error for error in errors))

    def test_federated_index_exceeds_seed_without_mutating_seed(self):
        before = json.dumps(self.registry, sort_keys=True)
        index = scribe.federated_index_document(self.registry, self.sources)
        self.assertGreater(index["resolved_identity_count"], len(self.registry["terms"]))
        self.assertEqual(before, json.dumps(self.registry, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
