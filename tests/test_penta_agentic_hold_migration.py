import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260827181500_penta_agentic_hold_governance_v1.sql"


class PentaAgenticHoldMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8").lower()

    def test_all_five_penta_layers_are_required(self):
        for layer in ("discover", "govern", "execute", "verify", "preserve"):
            self.assertIn(f"'{layer}'", self.sql)

    def test_agent_registry_and_independence_are_enforced(self):
        self.assertIn("agent_registry_v1", self.sql)
        self.assertIn("originator self-approval is prohibited", self.sql)
        self.assertIn("verify layer must be independently produced", self.sql)
        self.assertIn("cardinality(v_agents)<3", self.sql)
        self.assertIn("v_govern_agent is not distinct from v_verify_agent", self.sql)

    def test_d3_founder_binding_and_exact_head_baseline_remain_required(self):
        self.assertIn("p_founder_authority_ref", self.sql)
        self.assertIn("v_binding.expires_at", self.sql)
        self.assertIn("rb.exact_head_sha=v_case.exact_head_sha", self.sql)
        self.assertIn("rb.state='verified'", self.sql)

    def test_effects_remain_separate_and_zero_cost(self):
        self.assertIn("check (not provider_effect)", self.sql)
        self.assertIn("check (paid_cost_minor = 0)", self.sql)
        self.assertIn("'certified',false", self.sql)
        self.assertIn("'runtime_activated',false", self.sql)

    def test_legacy_topology_is_superseded_without_deletion(self):
        self.assertIn("historical_superseded", self.sql)
        self.assertIn("ct.legacy.abcds.scheduler-governance", self.sql)
        self.assertNotIn("delete from chlom_runtime", self.sql)
        self.assertNotIn("drop table", self.sql)

    def test_service_role_only_and_scheduled_self_heal(self):
        self.assertIn("from public,anon,authenticated", self.sql)
        self.assertIn("to service_role", self.sql)
        self.assertIn("penta-agentic-hold-governance-v1", self.sql)
        self.assertIn("penta_agentic_hold_tick_v1", self.sql)


if __name__ == "__main__":
    unittest.main()
