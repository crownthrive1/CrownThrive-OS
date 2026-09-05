#!/usr/bin/env python3
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260831094500_penta_deterministic_memory_v1.sql"
ROLLBACK = ROOT / "supabase/rollbacks/20260831094500_penta_deterministic_memory_v1.rollback.sql"


class PentaSqlContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.lower = cls.sql.lower()
        cls.rollback = ROLLBACK.read_text(encoding="utf-8")
        cls.rollback_lower = cls.rollback.lower()

    def test_transaction_and_non_destructive_migration(self):
        self.assertRegex(self.lower, r"\bbegin;\s")
        self.assertTrue(self.lower.rstrip().endswith("commit;"))
        self.assertNotIn("drop table", self.lower)
        self.assertNotIn("truncate table", self.lower)
        self.assertNotRegex(self.lower, r"\bdelete\s+from\s+")
        self.assertEqual(0, self.sql.count("\x00"))
        self.assertEqual(0, self.sql.count("\r"))
        self.assertEqual(0, self.sql.count("$$") % 2)

    def test_six_protected_durable_tables_exist(self):
        tables = {
            "penta_memory_namespaces_v1",
            "penta_memory_records_v1",
            "penta_execution_replays_v1",
            "penta_lifecycle_events_v1",
            "penta_memory_family_grants_v1",
            "penta_memory_census_receipts_v1",
        }
        created = set(
            re.findall(
                r"create table if not exists penta_runtime\.([a-z0-9_]+)",
                self.lower,
            )
        )
        self.assertEqual(tables, created)
        for table in tables:
            self.assertIn(
                f"alter table penta_runtime.{table} enable row level security;",
                self.lower,
            )
            self.assertIn(f"on penta_runtime.{table} for all to anon,authenticated", self.lower)

    def test_clients_and_direct_service_role_writes_are_denied(self):
        revoke = re.search(
            r"revoke all on table penta_runtime\.penta_memory_namespaces_v1.*?from public,anon,authenticated,service_role;",
            self.lower,
            re.S,
        )
        self.assertIsNotNone(revoke)
        self.assertIn("grant select on table penta_runtime.penta_memory_namespaces_v1", self.lower)
        self.assertNotRegex(self.lower, r"grant\s+(insert|update|delete|all).*?to service_role")

    def test_pentabrain_is_bounded_semantic_large_and_non_authoritative(self):
        brain = self.lower[self.lower.index("when lower(p_identity_key) = 'penta.brain'") :]
        brain = brain[: brain.index("when lower(p_maturity) not in") ]
        self.assertIn("'profile', 'brain-v1'", brain)
        self.assertIn("'hard_quota_bytes', 1073741824", brain)
        self.assertIn("'working_set_bytes', 268435456", brain)
        self.assertIn("'semantic_determinism', 'bounded-semantic-v1'", brain)
        self.assertIn("'model_version_required', true", brain)
        self.assertIn("not execution_eligible_by_registry", self.lower)
        self.assertIn("'specialist_execution_eligible',false", self.lower)
        self.assertIn("'authority_created',false", self.lower)

    def test_support_mesh_is_exactly_nine_read_only_families(self):
        expected = {
            "OBSERVABILITY_ORGANIC",
            "KNOWLEDGE_DATA",
            "SECURITY_TRUST",
            "ROUTING_INTEROP",
            "RESILIENCE_CONTINUITY",
            "INTELLIGENCE_RESEARCH",
            "AUTOMATION_AGENTIC",
            "SYSTEM_ARCHITECTURE",
            "BUILD_RELEASE",
        }
        grant_block = self.sql[
            self.sql.index("insert into penta_runtime.penta_memory_family_grants_v1") :
            self.sql.index("update penta_runtime.penta_memory_family_grants_v1", self.sql.index("insert into penta_runtime.penta_memory_family_grants_v1"))
        ]
        found = set(re.findall(r"\('penta\.brain','([A-Z_]+)'", grant_block))
        self.assertEqual(expected, found)
        self.assertIn("access_mode='READ_ONLY'", grant_block)
        self.assertIn("cross_family_write=false", grant_block)
        self.assertIn("authority_expansion=false", grant_block)

    def test_actual_live_registry_and_compact_universal_census_contract(self):
        self.assertIn("coalesce(r.source_refs,'{}'::jsonb)", self.sql)
        self.assertNotIn("r.source_snapshot_ref", self.sql)
        self.assertNotIn("r.source_key", self.sql)
        start = self.lower.index("insert into pentamocracy.universal_penta_census_v1(")
        end = self.lower.index("insert into penta_runtime.penta_memory_census_receipts_v1", start)
        census = self.lower[start:end]
        for column in (
            "census_identity",
            "canonical_name",
            "source_kind",
            "source_ref",
            "lifecycle_state",
            "constitutional_status",
            "family_key",
            "source_digest",
            "first_accounted_at",
            "last_accounted_at",
        ):
            self.assertIn(column, census)
        for stale in ("normalized_name", "latest_census_at", "evidence_complete", "duplicate_cluster"):
            self.assertNotIn(stale, census)

    def test_context_query_is_volatile_because_it_writes_receipts(self):
        start = self.lower.index("create or replace function penta_runtime.penta_memory_context_query_v1")
        end = self.lower.index("create or replace function penta_runtime.penta_deterministic_replay_record_v1", start)
        block = self.lower[start:end]
        self.assertNotRegex(block, r"\nstable\s*\n")
        self.assertIn("public.penta_context_query_v1", block)

    def test_replay_and_append_envelopes_fail_closed(self):
        self.assertIn("idempotency collision with different governed memory envelope", self.lower)
        self.assertIn("request hash collision with different deterministic execution envelope", self.lower)
        self.assertIn("provider replay requires a pinned provider version", self.lower)
        self.assertIn("model replay requires pinned provider, provider version, and model version", self.lower)
        self.assertIn("replay_state in ('recorded','match')", self.lower)
        self.assertIn("else v_state := 'mismatch'", self.lower)

    def test_census_and_health_do_not_claim_certification(self):
        self.assertIn("'production_certified',false", self.lower)
        self.assertIn("'independent_certification_required',true", self.lower)
        self.assertIn("entity_kind='penta_memory_namespace'", self.lower)
        self.assertIn("source_kind='penta_memory_namespace'", self.lower)
        self.assertIn("select penta_runtime.penta_memory_reconcile_v1();", self.lower)

    def test_no_money_release_or_provider_authority_mutation(self):
        forbidden = (
            r"insert\s+into\s+[^;]*(stripe|payment|payout|money|entitlement)",
            r"update\s+[^;]*(stripe|payment|payout|money|entitlement)",
            r"insert\s+into\s+[^;]*(release_author|provider_author)",
            r"update\s+[^;]*(release_author|provider_author)",
        )
        for pattern in forbidden:
            self.assertNotRegex(self.lower, pattern)

    def test_rollback_is_containment_only_and_preserves_evidence(self):
        self.assertTrue(self.rollback_lower.rstrip().endswith("commit;"))
        self.assertNotIn("drop table", self.rollback_lower)
        self.assertNotIn("truncate table", self.rollback_lower)
        self.assertNotRegex(self.rollback_lower, r"\bdelete\s+from\s+")
        self.assertIn("memory_state='rollback_hold'", self.rollback_lower)
        self.assertIn("write_enabled=false", self.rollback_lower)
        self.assertIn("revoke execute on function penta_runtime.penta_memory_reconcile_v1", self.rollback_lower)
        self.assertIn("preserve_records", self.rollback_lower)
        self.assertIn("penta_memory_lifecycle_append_v1", self.rollback_lower)


if __name__ == "__main__":
    unittest.main(verbosity=2)
