import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penta_pm_reconcile", ROOT / "scripts" / "penta_pm_reconcile.py")
pm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pm)
POLICY = json.loads((ROOT / "config" / "penta_pm_policy.json").read_text())


class PentaPMTests(unittest.TestCase):
    def test_docs_lane_routes_to_docs_milestone(self):
        c = pm.classify([
            {"name": "penta:authority:pr"},
            {"name": "penta:lane:docs"},
            {"name": "penta:risk:d2"},
            {"name": "penta:stage:nurture"},
        ], POLICY)
        self.assertEqual(c["milestone"], "Documentation & Institutional Knowledge")
        self.assertEqual(c["owner"], "pr")
        self.assertEqual(c["risk"], "d2")
        self.assertEqual(c["stage"], "nurture")

    def test_unknown_lane_falls_back_to_os_convergence(self):
        c = pm.classify([{"name": "penta:lane:unknown"}], POLICY)
        self.assertEqual(c["milestone"], "OS Production Convergence")

    def test_development_link_recognizes_closes_and_refs(self):
        self.assertIsNotNone(pm.LINK_RE.search("Closes #585\nRefs #584"))
        self.assertIsNotNone(pm.LINK_RE.search("refs #584"))

    def test_plain_issue_number_is_not_development_link(self):
        self.assertIsNone(pm.LINK_RE.search("See issue #584 for context"))

    def test_receipt_is_deterministically_hashed(self):
        r = pm.receipt("crownthrive1/CrownThrive-OS", "check", [], [])
        self.assertEqual(len(r["receipt_sha256"]), 64)
        self.assertEqual(r["schema"], "ct.penta.pm.receipt.v1")

    def test_policy_has_required_project_fields(self):
        required = {"Artifact ID", "Penta Owner", "Lane", "Stage", "Risk", "Milestone", "DAIL Receipt", "CHLOM Decision"}
        self.assertTrue(required.issubset(set(POLICY["project_fields"])))

    def test_policy_has_eight_initial_milestones(self):
        self.assertEqual(len(POLICY["milestones"]), 8)


if __name__ == "__main__":
    unittest.main()
