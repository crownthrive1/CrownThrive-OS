from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260901033000_penta_helper_bounded_retry_enforcement_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901033000_penta_helper_bounded_retry_enforcement_v1_rollback.sql"


class PentaHelperBoundedRetryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")

    def test_autonomous_pick_excludes_waiting_external(self) -> None:
        self.assertIn("state in ('raised','triaged','waiting_evidence')", self.migration)
        self.assertNotIn("state in ('raised','triaged','waiting_evidence','waiting_external') and next_action_at<=now()", self.migration)

    def test_autonomous_pick_enforces_attempt_budget(self) -> None:
        self.assertIn("attempt_count<max_attempts", self.migration)
        self.assertIn("attempt_count>=max_attempts", self.migration)
        self.assertIn("state='waiting_external'", self.migration)

    def test_exhausted_unresolved_success_cannot_rearm(self) -> None:
        resolved = "when p_success and coalesce((p_result->>'resolved')::boolean,false) then 'resolved'"
        exhausted = "when r.attempt_count>=r.max_attempts then 'waiting_external'"
        self.assertIn(resolved, self.migration)
        self.assertIn(exhausted, self.migration)
        self.assertLess(self.migration.index(resolved), self.migration.index(exhausted))
        self.assertIn("Callers cannot use p_state to silently rearm exhausted unresolved work", self.migration)

    def test_waiting_external_has_no_automatic_next_action(self) -> None:
        self.assertIn("v_state in ('triaged','waiting_evidence')", self.migration)
        self.assertNotIn("v_state in ('triaged','waiting_evidence','waiting_external')", self.migration)

    def test_d3_human_reservation_remains_present(self) -> None:
        self.assertIn("risk_class='D3'", self.migration)
        self.assertIn("state='waiting_human'", self.migration)
        self.assertIn("Human-reserved authority is required", self.migration)

    def test_recovery_never_restores_known_unbounded_retry_shape(self) -> None:
        self.assertIn("PENTA_HELP_AUTONOMOUS_RETRY_DISABLED_FAIL_CLOSED", self.rollback)
        self.assertIn("'automatic_retry_enabled',false", self.rollback)
        self.assertIn("'task_count',0", self.rollback)
        self.assertIn("to service_role", self.rollback.lower())
        self.assertNotIn("state in ('raised','triaged','waiting_evidence','waiting_external')", self.rollback)
        self.assertNotIn("when p_success then 'triaged'", self.rollback)
        self.assertIn("known unbounded-retry defect", self.rollback.lower())


if __name__ == "__main__":
    unittest.main()
