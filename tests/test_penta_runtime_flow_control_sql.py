import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = next((ROOT / "supabase/migrations").glob("*_penta_runtime_flow_control_v1.sql"))
SQL = MIGRATION.read_text()


def function_body(name: str) -> str:
    match = re.search(
        rf"create or replace function penta_runtime\.{name}\b.*?\$\$(.*?)\$\$;",
        SQL,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"missing function {name}")
    return match.group(1)


class PentaRuntimeFlowControlSqlTests(unittest.TestCase):
    def test_migration_installs_no_scheduler_network_or_provider_enablement(self):
        executable = "\n".join(
            line for line in SQL.splitlines() if not line.lstrip().startswith("--")
        ).lower()
        for forbidden in ("cron.schedule(", "net.http_", "http_post(", "enabled=true"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, executable)

    def test_campaign_and_activation_gates_recheck_exact_provider_containment(self):
        for name in ("campaign_status_v1", "assert_runtime_active_v1"):
            body = function_body(name)
            with self.subTest(function=name):
                self.assertIn("runtime_release_baselines_v1", body)
                self.assertIn("ct.adapter.github.actions.v1", body)
                self.assertIn("state in ('queued','claimed')", body)
                self.assertIn("not enabled", body)

    def test_retry_delay_is_declared_validated_and_used_only_by_release(self):
        release = function_body("release_flow_lease_v1")
        admit = function_body("admit_candidate_v1")
        self.assertIn("p_retry_delay_seconds integer default 60", SQL)
        self.assertIn("p_retry_delay_seconds not between 0 and 3600", release)
        self.assertIn("make_interval(secs=>p_retry_delay_seconds)", release)
        self.assertNotIn("p_retry_delay_seconds", admit)

    def test_sensitive_tables_are_force_rls_and_service_role_is_regranted_read_only(self):
        for table in (
            "runtime_release_baselines_v1",
            "component_registry_rollback_v1",
            "runtime_activation_receipts_v1",
        ):
            with self.subTest(table=table):
                self.assertIn(f"alter table penta_runtime.{table} force row level security", SQL)
                self.assertIn(
                    f"revoke all on penta_runtime.{table} from public, anon, authenticated, service_role",
                    SQL,
                )
                self.assertIn(f"grant select on penta_runtime.{table} to service_role", SQL)

    def test_component_registry_reconciliation_preserves_exact_rollback_evidence(self):
        self.assertIn("component_registry_rollback_v1", SQL)
        self.assertIn("prior_row_sha256", SQL)
        self.assertIn("where component_key = 'penta.route'", SQL)
        self.assertIn("canonical_name = 'PentaRoute'", SQL)
        self.assertIn("'{}'::text[]", SQL)
        self.assertIn("array['PentaLoadBalancer']::text[]", SQL)


if __name__ == "__main__":
    unittest.main()
