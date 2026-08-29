import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data/penta/pentaself-permanent-verified-repairs.v1.json"
MIGRATION = ROOT / "supabase/migrations/20260829021000_pentaself_permanent_verified_repair_fabric_v1.sql"


class PentaSelfPermanentRepairContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.sql = MIGRATION.read_text(encoding="utf-8")

    def test_verified_repairs_are_monotonic(self):
        invariants = self.contract["invariants"]
        self.assertTrue(invariants["verified_repair_is_monotonic"])
        self.assertFalse(invariants["stale_or_unversioned_evidence_may_regress_resolved_state"])
        self.assertFalse(invariants["bootstrap_defaults_may_override_newer_verified_state"])
        self.assertFalse(invariants["automatic_rollback_allowed"])
        self.assertTrue(invariants["rollback_requires_newer_independently_verified_failure"])
        self.assertTrue(invariants["rollback_requires_explicit_handle"])

    def test_regression_guard_and_append_only_evidence_exist(self):
        self.assertIn("guard_permanent_repair_regression_v1", self.sql)
        self.assertIn("stale_regression_blocked", self.sql)
        self.assertIn("permanent_repair_events_immutable_v1", self.sql)
        self.assertIn("stale_or_unversioned_evidence_cannot_regress_verified_repair", self.sql)

    def test_scheduler_reconciler_is_exact_and_recurring(self):
        runtime = self.contract["runtime"]
        self.assertEqual(runtime["schedule"], "* * * * *")
        self.assertIn("reconcile_permanent_repairs_v1", self.sql)
        self.assertIn("cron_missing_recreated", self.sql)
        self.assertIn("cron_reactivated", self.sql)
        self.assertIn("stale_cron_drift_repaired", self.sql)

    def test_rollback_is_not_removed(self):
        safety = self.contract["safety"]
        self.assertFalse(safety["rollback_removed"])
        self.assertIn("newer independently verified regression", safety["rollback_semantics"])

    def test_no_authority_expansion(self):
        safety = self.contract["safety"]
        self.assertFalse(safety["credential_material_stored_in_source"])
        self.assertFalse(safety["money_movement_granted"])
        self.assertFalse(safety["rights_granted"])
        self.assertFalse(self.contract["invariants"]["d3_bypass"])


if __name__ == "__main__":
    unittest.main()
