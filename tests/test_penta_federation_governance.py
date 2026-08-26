import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


governance = load_module("pentascribe_federation_governance_test", ROOT / "penta/scribe/federation_governance.py")
marketer = load_module("pentamarketer_federation_governance_test", ROOT / "penta/marketer/pentamarketer.py")


class PentaFederationGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "penta/scribe/registry.json").read_text(encoding="utf-8"))
        self.sources = json.loads((ROOT / "penta/scribe/sources.registry.json").read_text(encoding="utf-8"))
        self.policy = json.loads((ROOT / "penta/marketer/policy.json").read_text(encoding="utf-8"))
        self.campaign = json.loads((ROOT / "penta/marketer/campaign.example.json").read_text(encoding="utf-8"))

    def synthetic_source(self, directory: str, identity_id: str = "penta.foo") -> dict:
        path = pathlib.Path(directory) / "components.json"
        path.write_text(json.dumps({
            "components": [{
                "key": identity_id,
                "name": "PentaFoo",
                "aliases": [],
            }]
        }), encoding="utf-8")
        return {
            "schema_version": "1.1.0",
            "sources": [{
                "source_id": "synthetic-components",
                "type": "penta_component_registry",
                "path": path.as_posix(),
                "authority": "canonical_component",
            }],
            "equivalences": [],
            "blocked_terms": [],
        }

    def synthetic_registry(self) -> dict:
        return {
            "terms": [{
                "id": "foo-seed",
                "canonical": "PentaFoo",
                "aliases": [],
                "status": "canonical",
                "kind": "system",
                "source": "synthetic",
                "trademark": {"status": "unverified", "symbol": "", "jurisdiction": None, "registration": None},
            }]
        }

    def test_current_federation_authority_audit_passes(self):
        result = governance.audit_federation(self.registry, self.sources)
        self.assertEqual("PASS", result["result"])
        self.assertEqual(0, result["conflict_count"])
        self.assertGreater(result["overlap_count"], 0)

    def test_ambiguous_authority_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = self.synthetic_source(directory)
            result = governance.audit_federation(self.synthetic_registry(), sources)
            self.assertEqual("FAIL", result["result"])
            self.assertEqual(1, result["conflict_count"])
            self.assertEqual("AMBIGUOUS_SEMANTIC_AUTHORITY", result["conflicts"][0]["reason"])

    def test_declared_equivalence_allows_compatibility_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = self.synthetic_source(directory)
            sources["equivalences"] = [{
                "equivalence_id": "foo-compat",
                "ids": ["foo-seed", "penta.foo"],
                "reason": "synthetic compatibility mapping",
            }]
            result = governance.audit_federation(self.synthetic_registry(), sources)
            self.assertEqual("PASS", result["result"])
            self.assertEqual(0, result["conflict_count"])
            self.assertEqual(1, result["overlap_count"])

    def test_candidate_queue_is_stable_and_never_auto_promotes(self):
        discovery = {
            "candidate_count": 2,
            "federated_observation_count": 4,
            "rejected_observation_count": 1,
            "candidates": [
                {"observed": "PentaFuture", "proposed_id": "pentafuture", "count": 2, "sources": ["a.md"], "symbols": []},
                {"observed": "PentaSignalX", "proposed_id": "pentasignalx", "count": 30, "sources": ["b.md"], "symbols": ["™"]},
            ],
        }
        first = governance.build_candidate_queue(discovery)
        second = governance.build_candidate_queue(discovery)
        self.assertEqual(first, second)
        self.assertEqual(2, first["review_count"])
        self.assertEqual("high", first["items"][0]["priority"])
        self.assertTrue(all(item["status"] == "REVIEW_REQUIRED" for item in first["items"]))
        self.assertTrue(all(item["automatic_promotion"] is False for item in first["items"]))

    def test_pentamarketer_refuses_ambiguous_federation(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = self.synthetic_source(directory)
            registry = self.synthetic_registry()
            campaign = dict(self.campaign)
            campaign["terms"] = ["PentaFoo"]
            errors, _ = marketer.validate_campaign(campaign, registry, self.policy, sources)
            self.assertTrue(any("federation authority conflict" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
