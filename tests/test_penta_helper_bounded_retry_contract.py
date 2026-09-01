from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260901033000_penta_helper_bounded_retry_enforcement_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901033000_penta_helper_bounded_retry_enforcement_v1_rollback.sql"
BRIDGE = ROOT / "supabase/migrations/20260901034500_penta_pr_terminal_provider_schema_bridge_v1.sql"
BRIDGE_ROLLBACK = ROOT / "supabase/rollback/20260901034500_penta_pr_terminal_provider_schema_bridge_v1_rollback.sql"


class PentaHelperBoundedRetryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.migration = MIGRATION.read_text(encoding="utf-8")
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")

    def test_autonomous_pick_excludes_waiting_external(self) -> None:
        self.assertIn("state in ('raised','triaged','waiting_evidence')", self.migration)
        self.assertNotIn(
            "state in ('raised','triaged','waiting_evidence','waiting_external') and next_action_at<=now()",
            self.migration,
        )

    def test_autonomous_pick_enforces_attempt_budget(self) -> None:
        self.assertIn("attempt_count<max_attempts", self.migration)
        self.assertIn("attempt_count>=max_attempts", self.migration)
        self.assertIn("state='waiting_external'", self.migration)

    def test_successful_but_unresolved_exhaustion_cannot_rearm(self) -> None:
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

    def test_rollback_preserves_exact_pre_repair_retry_shape(self) -> None:
        self.assertIn(
            "state in ('raised','triaged','waiting_evidence','waiting_external')",
            self.rollback,
        )
        self.assertIn(
            "when p_success then 'triaged' when r.attempt_count>=r.max_attempts then 'waiting_external'",
            self.rollback,
        )


class PentaPRTerminalProviderSchemaBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bridge = BRIDGE.read_text(encoding="utf-8")
        cls.rollback = BRIDGE_ROLLBACK.read_text(encoding="utf-8")

    def test_public_wrappers_delegate_to_canonical_implementations(self) -> None:
        self.assertIn("create or replace function public.penta_pr_closeout_claim_v1", self.bridge)
        self.assertIn("select integration_control.penta_pr_closeout_claim_v1", self.bridge)
        self.assertIn("create or replace function public.penta_pr_closeout_result_v1", self.bridge)
        self.assertIn("select integration_control.penta_pr_closeout_result_v1", self.bridge)

    def test_wrappers_are_service_role_only(self) -> None:
        self.assertIn(
            "revoke all on function public.penta_pr_closeout_claim_v1(uuid,text,text) from public,anon,authenticated",
            self.bridge,
        )
        self.assertIn(
            "grant execute on function public.penta_pr_closeout_claim_v1(uuid,text,text) to service_role",
            self.bridge,
        )
        self.assertIn(
            "revoke all on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text) from public,anon,authenticated",
            self.bridge,
        )
        self.assertIn(
            "grant execute on function public.penta_pr_closeout_result_v1(uuid,boolean,integer,text,text,text,text,boolean,jsonb,text,bigint,text,text,text) to service_role",
            self.bridge,
        )

    def test_bridge_does_not_duplicate_claim_or_terminal_logic(self) -> None:
        self.assertNotIn("wake_token_sha256", self.bridge)
        self.assertNotIn("penta_change_append_v1", self.bridge)
        self.assertNotIn("ready_for_terminal", self.bridge)
        self.assertIn("business logic", self.bridge.lower())

    def test_rollback_removes_only_compatibility_wrappers(self) -> None:
        self.assertIn("drop function if exists public.penta_pr_closeout_claim_v1", self.rollback)
        self.assertIn("drop function if exists public.penta_pr_closeout_result_v1", self.rollback)
        self.assertNotIn("drop function if exists integration_control", self.rollback)


if __name__ == "__main__":
    unittest.main()
