import json, pathlib, tempfile, unittest, importlib.util

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

scribe = load_module("pentascribe", ROOT/"penta/scribe/pentascribe.py")
marketer = load_module("pentamarketer", ROOT/"penta/marketer/pentamarketer.py")

class PentaScribeTests(unittest.TestCase):
    def setUp(self): self.registry = json.loads((ROOT/"penta/scribe/registry.json").read_text())
    def test_registry_valid(self): self.assertEqual([], scribe.validate_registry(self.registry))
    def test_reconcile_passes(self): self.assertEqual("PASS", scribe.reconcile(self.registry)["result"])
    def test_compiler_emits_all_products(self):
        with tempfile.TemporaryDirectory() as d:
            names = {p.name for p in scribe.compile_registry(self.registry, pathlib.Path(d))}
            self.assertEqual({"GLOSSARY.md","DICTIONARY.md","INDEX.md","FAQ.md","TRADEMARK_LEDGER.md","ALIASES.md","reconciliation.json"}, names)
    def test_registered_symbol_requires_evidence(self):
        bad = json.loads(json.dumps(self.registry)); bad["terms"][0]["trademark"]["symbol"] = "®"
        self.assertTrue(any("® prohibited" in e for e in scribe.validate_registry(bad)))

class PentaMarketerTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT/"penta/scribe/registry.json").read_text())
        self.policy = json.loads((ROOT/"penta/marketer/policy.json").read_text())
        self.campaign = json.loads((ROOT/"penta/marketer/campaign.example.json").read_text())
    def test_example_campaign_valid(self):
        errors, resolved = marketer.validate_campaign(self.campaign, self.registry, self.policy)
        self.assertEqual([], errors); self.assertEqual(3, len(resolved))
    def test_unknown_term_fails_closed(self):
        c = dict(self.campaign); c["terms"] = ["Made Up System"]
        errors, _ = marketer.validate_campaign(c, self.registry, self.policy)
        self.assertTrue(any("unknown/unapproved" in e for e in errors))
    def test_manifest_is_plan_only(self):
        m = marketer.compile_manifest(self.campaign, self.registry, self.policy)
        self.assertEqual("PLAN_ONLY", m["publication_state"]); self.assertEqual(64, len(m["manifest_sha256"]))
    def test_registered_symbol_is_bound_to_exact_mark(self):
        registry = json.loads(json.dumps(self.registry))
        registry["terms"][0]["trademark"] = {"status": "registered", "symbol": "®", "jurisdiction": "US", "registration": "TEST-REGISTRATION-EVIDENCE"}
        allowed = dict(self.campaign); allowed["message"] = "CrownThrive® uses governed institutional terminology."
        errors, _ = marketer.validate_campaign(allowed, registry, self.policy)
        self.assertFalse(any("® used" in e for e in errors))
        blocked = dict(self.campaign); blocked["message"] = "PentaScribe® uses governed institutional terminology."
        errors, _ = marketer.validate_campaign(blocked, registry, self.policy)
        self.assertTrue(any("® used" in e for e in errors))

if __name__ == "__main__": unittest.main()
