from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_SCRIPT = ROOT / "scripts/penta_operational_knowledge.py"
ENTRYPOINT_SCRIPT = ROOT / "scripts/penta_operational_knowledge_entrypoint.py"

core_spec = importlib.util.spec_from_file_location("penta_operational_knowledge", CORE_SCRIPT)
assert core_spec and core_spec.loader
core = importlib.util.module_from_spec(core_spec)
sys.modules[core_spec.name] = core
core_spec.loader.exec_module(core)

entry_spec = importlib.util.spec_from_file_location("penta_operational_knowledge_entrypoint", ENTRYPOINT_SCRIPT)
assert entry_spec and entry_spec.loader
entrypoint = importlib.util.module_from_spec(entry_spec)
sys.modules[entry_spec.name] = entrypoint
entry_spec.loader.exec_module(entrypoint)
knowledge = entrypoint.core


class PentaOperationalKnowledgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        entrypoint.validate_taxonomy_contract()
        cls.census = json.loads((ROOT / "data/penta/namespace-census.v1.json").read_text(encoding="utf-8"))
        cls.taxonomy = json.loads((ROOT / "data/penta/operational-taxonomy.v1.json").read_text(encoding="utf-8"))
        cls.operational = json.loads((ROOT / "data/penta/operational-knowledge.v1.json").read_text(encoding="utf-8"))
        cls.agent = json.loads((ROOT / "data/penta/agent-knowledge.v1.json").read_text(encoding="utf-8"))
        cls.records = cls.operational["records"]

    def test_complete_namespace_has_one_operational_record(self):
        self.assertEqual(self.census["counts"]["total"], len(self.records))
        self.assertEqual(406, len(self.records))
        self.assertEqual(len(self.records), len({r["identity"] for r in self.records}))
        self.assertEqual(len(self.records), len({r["docs_path"] for r in self.records}))

    def test_every_canonical_identity_has_layer_and_job(self):
        canonical = [r for r in self.records if r["namespace_state"] == "canonical"]
        self.assertEqual(214, len(canonical))
        for record in canonical:
            self.assertTrue(record["layers"], record["identity"])
            self.assertTrue(record["jobs"], record["identity"])
            self.assertIn("operator", record["audiences"])

    def test_every_noncanonical_identity_routes_through_canonicalization_lane(self):
        candidates = [r for r in self.records if r["namespace_state"] != "canonical"]
        self.assertEqual(192, len(candidates))
        for record in candidates:
            self.assertIn("control-governance", record["layers"], record["identity"])
            self.assertIn("data-knowledge", record["layers"], record["identity"])
            self.assertIn("govern", record["jobs"], record["identity"])
            self.assertIn("document", record["jobs"], record["identity"])
            provenance = record["classification_provenance"]["jobs"]
            self.assertTrue(provenance.startswith("candidate_canonicalization"), record["identity"])

    def test_docs_inferred_family_does_not_seed_candidate_operational_jobs(self):
        census_by_name = {r["name"]: r for r in self.census["records"]}
        for record in self.records:
            if record["namespace_state"] == "canonical":
                continue
            census = census_by_name[record["identity"]]
            if census.get("assignment_state") != "docs_inferred":
                continue
            provenance = record["classification_provenance"]["jobs"]
            self.assertNotIn("registry_family", provenance, record["identity"])

    def test_taxonomy_references_resolve(self):
        valid_layers = {x["id"] for x in self.taxonomy["layers"]}
        valid_jobs = {x["id"] for x in self.taxonomy["jobs"]}
        valid_lifecycle = {x["id"] for x in self.taxonomy["lifecycle_stages"]}
        valid_audiences = {x["id"] for x in self.taxonomy["audiences"]}
        for record in self.records:
            self.assertFalse(set(record["layers"]) - valid_layers, record["identity"])
            self.assertFalse(set(record["jobs"]) - valid_jobs, record["identity"])
            self.assertFalse(set(record["lifecycle_stages"]) - valid_lifecycle, record["identity"])
            self.assertFalse(set(record["audiences"]) - valid_audiences, record["identity"])

    def test_candidate_docs_never_manufacture_execution_authority(self):
        candidates = [r for r in self.records if r["namespace_state"] != "canonical"]
        self.assertEqual(192, len(candidates))
        for record in candidates:
            self.assertFalse(record["execution_eligible_by_registry"], record["identity"])
            self.assertIn("perform independent runtime/provider writes", " ".join(record["forbidden_actions"]))
            self.assertNotIn("operator", record["audiences"])
            self.assertNotIn("release", record["lifecycle_stages"])
            self.assertNotIn("operate", record["lifecycle_stages"])

    def test_machine_manifests_are_one_to_one(self):
        self.assertEqual(406, self.agent["record_count"])
        self.assertEqual(self.records, self.agent["records"])
        lines = [json.loads(x) for x in (ROOT / "data/penta/agent-knowledge.v1.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertEqual(self.records, lines)

    def test_every_penta_page_has_one_operational_contract(self):
        for record in self.records:
            path = ROOT / (record["docs_path"] + ".mdx")
            text = path.read_text(encoding="utf-8")
            self.assertEqual(1, text.count(knowledge.BEGIN), record["identity"])
            self.assertEqual(1, text.count(knowledge.END), record["identity"])
            for required in [
                "## Operational classification",
                "## When to use",
                "## When not to use",
                "## Quickstart",
                "## Developer guide",
                "## Invocation & interfaces",
                "## Authority, permissions & non-authorities",
                "## Reliability, failure modes & recovery",
                "## Testing, assurance & production certification",
                "## Agent ingestion contract",
                "## Troubleshooting",
                "## Machine-readable knowledge",
            ]:
                self.assertIn(required, text, f"{record['identity']} missing {required}")

    def test_cross_cutting_surfaces_are_navigated_once(self):
        docs = json.loads((ROOT / "docs.json").read_text(encoding="utf-8"))
        pages = knowledge.nav_pages(docs)
        expected = [
            "pentas/operational", "pentas/development", "pentas/quickstarts", "pentas/agents", "pentas/integrations", "pentas/runbooks",
            "pentas/layers", "pentas/jobs", "pentas/lifecycle", "pentas/audiences",
        ]
        expected += [f'pentas/layers/{x["id"]}' for x in self.taxonomy["layers"]]
        expected += [f'pentas/jobs/{x["id"]}' for x in self.taxonomy["jobs"]]
        expected += [f'pentas/lifecycle/{x["id"]}' for x in self.taxonomy["lifecycle_stages"]]
        expected += [f'pentas/audiences/{x["id"]}' for x in self.taxonomy["audiences"]]
        for page in expected:
            self.assertEqual(1, pages.count(page), page)

    def test_agent_contract_is_fail_closed(self):
        self.assertTrue(self.agent["routing_contract"]["fail_closed"])
        invariant = self.agent["authority_invariant"].casefold()
        for token in ["maturity", "provider permission", "financial authority", "rights authority", "d3"]:
            self.assertIn(token, invariant)

    def test_deterministic_operational_check_passes(self):
        result = knowledge.check()
        self.assertEqual("PASS", result["status"])
        self.assertEqual(406, result["identities"])
        self.assertEqual(13, result["layers"])
        self.assertEqual(18, result["jobs"])


if __name__ == "__main__":
    unittest.main()
