import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data/penta/penta-census-production-certification.v1.json"
MIGRATION = ROOT / "supabase/migrations/20260829022500_penta_census_readonly_core_production_certification_v1.sql"


class PentaCensusProductionCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_bounded_core_is_production(self):
        self.assertEqual(self.contract["component_key"], "penta.census")
        self.assertEqual(self.contract["state"], "production")
        self.assertIn("scheduled heartbeat and daily major census", self.contract["production_scope"])
        self.assertIn("governed handoff routing", self.contract["production_scope"])

    def test_provider_writes_remain_excluded(self):
        excluded = set(self.contract["excluded_scope"])
        self.assertIn("unattended Google Drive write", excluded)
        self.assertIn("unattended Google Sheets write", excluded)
        self.assertIn("arbitrary provider mutation", excluded)
        self.assertIn("money movement", excluded)

    def test_certification_is_evidence_gated(self):
        requirements = self.contract["evidence_requirements"]
        self.assertTrue(requirements["policy_enabled"])
        self.assertTrue(requirements["latest_census_completed"])
        self.assertTrue(requirements["scheduler_active"])
        self.assertEqual(requirements["scheduler_latest_status"], "succeeded")
        self.assertTrue(requirements["founder_report_queued"])
        self.assertIn("raise exception 'penta_census_scheduler_not_verified'", self.sql)
        self.assertIn("raise exception 'penta_census_guardrails_failed'", self.sql)

    def test_privacy_and_d3_remain_closed(self):
        requirements = self.contract["evidence_requirements"]
        self.assertFalse(requirements["raw_cookie_exposure"])
        self.assertFalse(requirements["raw_secret_exposure"])
        self.assertFalse(requirements["personal_income_inference"])
        self.assertTrue(requirements["d3_human_reserved"])
        self.assertFalse(self.contract["authority_expansion"])

    def test_permanent_repair_guard_is_bound(self):
        permanence = self.contract["permanence"]
        self.assertFalse(permanence["stale_snapshot_regression_allowed"])
        self.assertTrue(permanence["rollback_requires_newer_independent_failure"])
        self.assertIn("penta_self.register_permanent_repair_v1", self.sql)


if __name__ == "__main__":
    unittest.main()
