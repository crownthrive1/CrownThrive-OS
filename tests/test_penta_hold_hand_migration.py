import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260827173000_penta_hold_hand_crawler_v1.sql"


class HoldHandMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8").lower()

    def test_persistent_hand_and_append_only_resolution_surfaces_exist(self):
        for name in (
            "hold_hands_v1", "hold_crawler_observations_v1",
            "hold_remediation_tasks_v1", "hold_resolutions_v1",
        ):
            self.assertIn(name, self.sql)

    def test_crawler_and_resolution_are_separate(self):
        crawler = self.sql.split("create or replace function penta_runtime.penta_hold_crawler_tick_v1", 1)[1]
        crawler = crawler.split("create or replace function penta_runtime.resolve_hold_if_ready_v1", 1)[0]
        self.assertNotIn("insert into penta_runtime.hold_resolutions_v1", crawler)
        self.assertIn("certification_effect',false", crawler)

    def test_provider_and_paid_cost_effects_are_forbidden(self):
        self.assertIn("check (not provider_effect)", self.sql)
        self.assertIn("check (paid_cost_minor = 0)", self.sql)
        self.assertIn("check (not certification_effect)", self.sql)

    def test_resolution_requires_distinct_verified_baseline(self):
        self.assertIn("rb.state='verified'", self.sql)
        self.assertIn("rb.independent_verifier_ref is distinct from b.founder_ref", self.sql)
        self.assertIn("baseline.verified_by=any(hand.producer_ids)", self.sql)

    def test_historical_hold_is_never_deleted(self):
        self.assertNotIn("delete from penta_runtime.d3_campaign_holds_v1", self.sql)
        self.assertIn("historical_hold_preserved", self.sql)

    def test_crawler_schedule_is_bounded(self):
        self.assertIn("penta-hold-hand-crawler-v1", self.sql)
        self.assertIn("'*/5 * * * *'", self.sql)


if __name__ == "__main__":
    unittest.main()
