from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260829205500_pentaself_scheduler_authority_inversion_fix_v1.sql"


class PentaSelfSchedulerAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = MIGRATION.read_text(encoding="utf-8")

    def test_scheduler_desired_state_is_authoritative(self) -> None:
        self.assertIn("integration_control.scheduler_desired_jobs_v2", self.text)
        self.assertIn("order by generation desc", self.text)
        self.assertIn("scheduler_authority", self.text)
        self.assertIn("higher_generation_supersession_only", self.text)

    def test_required_jobs_are_projection_not_authority(self) -> None:
        self.assertIn("required_job_projection_synced", self.text)
        self.assertIn("expected_schedule=d.schedule", self.text)
        self.assertIn("expected_command=d.command", self.text)
        self.assertIn("auto_repair=d.active", self.text)

    def test_repairs_are_dail_bound_and_bounded(self) -> None:
        self.assertIn("scheduler.pentaself.reconciled", self.text)
        self.assertIn("authority_created',false", self.text)
        self.assertIn("d3_human_reserved',true", self.text)
        self.assertIn("new_clock_created_only_if_desired_missing", self.text)


if __name__ == "__main__":
    unittest.main()
