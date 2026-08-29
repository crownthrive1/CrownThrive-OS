from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PentaMailerDynamicPoolTests(unittest.TestCase):
    def read(self, migration: str) -> str:
        path = ROOT / "supabase" / "migrations" / migration
        self.assertTrue(path.exists(), f"missing migration: {path}")
        return path.read_text(encoding="utf-8")

    def test_pool_policy_is_40k_operational_on_50k_provider_plan(self) -> None:
        text = self.read("20260829203000_pentamailer_40k_dynamic_pool_policy_v1.sql")
        self.assertIn("50000", text)
        self.assertIn("40000", text)
        self.assertIn("10000", text)
        self.assertIn("30000", text)
        self.assertIn("20000", text)
        self.assertIn("provider_plan_headroom", text)
        self.assertIn("system_internal_has_first_claim_on_entire_pool", text)
        self.assertIn("marketing_is_residual_after_system_internal_demand", text)
        self.assertIn("higher_generation_supersession_only", text)

    def test_locticians_contract_is_500_per_day_and_10k_per_month(self) -> None:
        text = self.read("20260829203000_pentamailer_40k_dynamic_pool_policy_v1.sql")
        self.assertIn("locticians_daily_cap", text)
        self.assertIn("locticians_monthly_cap", text)
        self.assertIn("500_per_day_10000_per_month_dynamic_40k_pool", text)
        self.assertIn("'daily_cap',500", text)
        self.assertIn("'monthly_cap',10000", text)
        self.assertIn("'total_cap',120000", text)

    def test_allocator_reserves_internal_demand_before_marketing(self) -> None:
        text = self.read("20260829204000_pentamailer_40k_dynamic_pool_runtime_v1.sql")
        self.assertIn("system_internal_due_pending", text)
        self.assertIn("p.operational_monthly_cap-v_system_committed-v_system_due_pending", text)
        self.assertIn("system_internal_first_claim", text)
        self.assertIn("marketing_residual_dynamic", text)
        self.assertIn("locticians_protected_remaining", text)
        self.assertIn("other_marketing_available_now", text)

    def test_all_claim_paths_use_dynamic_pool(self) -> None:
        text = self.read("20260829204000_pentamailer_40k_dynamic_pool_runtime_v1.sql")
        self.assertIn("penta_mail_pool_status_v2", text)
        self.assertIn("crm.penta_marketer_claim_outbox_v2", text)
        self.assertIn("public.penta_mail_claim_outbox_v2", text)
        self.assertIn("select * from crm.penta_marketer_claim_outbox_v2(p_limit)", text)
        self.assertIn("pool_policy','ct.pentamailer.pool.40k.v1", text)

    def test_growth_reservations_respect_dynamic_residual(self) -> None:
        text = self.read("20260829204500_pentamailer_growth_reserve_dynamic_pool_v2.sql")
        self.assertIn("penta_mail_pool_status_v2", text)
        self.assertIn("locticians_dynamic_pool_or_daily_cap", text)
        self.assertIn("other_marketing_dynamic_residual_exhausted", text)
        self.assertIn("pentamailer_40k_pool_exhausted", text)

    def test_pentaself_is_desired_state_driven_not_legacy_hardcoded(self) -> None:
        text = self.read("20260829205000_pentaself_desired_state_dynamic_pool_v2.sql")
        self.assertIn("desired_state_driven", text)
        self.assertIn("penta_mail_pool_reconcile_v2", text)
        self.assertIn("higher_generation_supersession_only", text)
        self.assertNotIn("daily_cap=200,monthly_cap=5000", text)
        self.assertNotIn("marketing_monthly_cap=12500", text)


if __name__ == "__main__":
    unittest.main()
