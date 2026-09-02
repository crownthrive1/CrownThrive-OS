from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260901143000_penta_assignment_transport_result_isolation_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901143000_penta_assignment_transport_result_isolation_v1_rollback.sql"


class PentaAssignmentTransportResultIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")

    def test_census_transport_completion_cannot_synthesize_owner_pass(self) -> None:
        self.assertIn("HOLD_ASSIGNMENT_OWNER_SEMANTIC_RESULT_MISSING", self.migration)
        self.assertIn("transport_completion_is_not_owner_pass", self.migration)
        self.assertIn("penta_assignment_owner_results_v1", self.migration)
        self.assertIn("r.result_state='PASS'", self.migration)
        self.assertIn("r.exact_head_sha is not distinct from a.exact_head_sha", self.migration)
        census_block = self.migration.split("if d.dispatch_kind='CENSUS_HANDOFF' then", 1)[1].split("elsif d.dispatch_kind='OS20_TASK' then", 1)[0]
        self.assertNotIn("penta_assignment_record_owner_result_v1", census_block)
        self.assertNotIn("'PASS'", census_block)

    def test_completed_os20_task_without_owner_result_is_hold_not_pass(self) -> None:
        os20_block = self.migration.split("elsif d.dispatch_kind='OS20_TASK' then", 1)[1].split("end if;\n  end loop;", 1)[0]
        self.assertIn("t.status='completed'", os20_block)
        self.assertIn("HOLD_ASSIGNMENT_OWNER_SEMANTIC_RESULT_MISSING", os20_block)
        self.assertIn("execution_completion_is_not_owner_pass", os20_block)
        self.assertIn("semantic_owner_result_required", os20_block)
        self.assertNotIn("penta_assignment_record_owner_result_v1", os20_block)
        self.assertNotIn("'PASS'", os20_block)

    def test_reconciler_reports_zero_new_pass_results(self) -> None:
        self.assertIn("'new_pass_results',0", self.migration)
        self.assertIn("'completed_from_existing_owner_results',v_progress", self.migration)
        self.assertIn("'execution_completion_is_not_owner_pass',true", self.migration)
        self.assertIn("'semantic_owner_result_required',true", self.migration)

    def test_forward_path_preserves_no_authority_expansion(self) -> None:
        forbidden = (
            "PASS_CERTIFIED",
            "LICENSE_GRANTED",
            "provider_write=true",
            "credential_change=true",
            "money_movement=true",
            "rights_grant=true",
            "vote_effect=true",
            "quorum_effect=true",
            "d3_execution=true",
        )
        for token in forbidden:
            self.assertNotIn(token, self.migration)
        self.assertIn("'authority_created',false", self.migration)
        self.assertIn("'authority_expansion',false", self.migration)
        self.assertIn("to service_role", self.migration)

    def test_recovery_never_restores_transport_to_pass_semantics(self) -> None:
        self.assertIn("HOLD_ASSIGNMENT_OWNER_RECONCILIATION_DISABLED_FAIL_CLOSED", self.rollback)
        self.assertIn("transport completion cannot synthesize semantic owner PASS", self.rollback)
        self.assertIn("'new_pass_results',0", self.rollback)
        self.assertIn("'semantic_owner_result_required',true", self.rollback)
        self.assertIn("'authority_created',false", self.rollback)
        self.assertIn("'authority_expansion',false", self.rollback)
        self.assertNotIn("penta_assignment_record_owner_result_v1", self.rollback)
        self.assertNotIn("'PASS'", self.rollback)


if __name__ == "__main__":
    unittest.main()
