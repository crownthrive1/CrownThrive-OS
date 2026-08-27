"""Static fail-closed checks for the held DAIL v2 database/Edge source.

These checks do not substitute for applying the migration to a disposable
PostgreSQL database. They prevent known evidence-promotion and ingress-boundary
regressions while that integration environment remains unavailable.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260826233102_dail_evidence_spine_v2.sql"
EDGE = ROOT / "supabase/functions/dail-external-ingress"
FACTORY = ROOT / "developers/manifests/dail-factory-continuation.v2.json"


class DailSupabaseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = MIGRATION.read_text(encoding="utf-8")
        cls.lower = cls.sql.lower()

    def test_migration_is_atomic_and_verifies_before_and_after_cutover(self) -> None:
        self.assertRegex(self.sql, r"(?m)^begin;\s*$")
        self.assertRegex(self.sql, r"(?m)^commit;\s*$")
        self.assertLess(self.lower.index("begin;"), self.lower.index("do $preflight$"))
        self.assertIn("inherited ledger verification did not pass", self.lower)
        self.assertIn("do $postflight$", self.lower)
        self.assertNotRegex(self.lower, r"\bdrop\s+table\b|\btruncate\s+table\b")

    def test_legacy_writer_is_retired_instead_of_bypassing_v2(self) -> None:
        self.assertIn("legacy dail append is retired", self.lower)
        self.assertIn(
            "revoke all on function chlom_runtime.append_dail_event(",
            self.lower,
        )
        self.assertIn("legacy writer does not use the canonical chain lock", self.lower)

    def test_reserved_evidence_and_anchor_states_need_dedicated_admission(self) -> None:
        self.assertRegex(
            self.sql,
            r"if p_evidence_class in \(\s*'E2_SEPARATE_WORKLOAD_VERIFIED',\s*"
            r"'E5_EXTERNAL_ASYMMETRIC_ATTESTED',\s*'E6_INDEPENDENTLY_ANCHORED'",
        )
        self.assertIn("if p_chain_anchor_state <> 'unanchored'", self.sql)
        self.assertIn("dedicated authenticated verifier", self.lower)

    def test_e4_ingress_has_a_separate_vault_authenticated_boundary(self) -> None:
        for required in (
            "DAIL_EXTERNAL_INGRESS_ADMISSION_HMAC_KEY_V2".lower(),
            "p_admission_mac",
            "vault.decrypted_secrets",
            "dail-external-ingress-v2|",
            "external verification receipt is not bound to this exact ingress projection",
            "create unique index dail_events_v2_verification_receipt_unique",
        ):
            self.assertIn(required, self.lower)

        acl = self.lower[self.lower.index("do $function_acl$") :]
        grant_block = acl.split("for r in")[-1]
        self.assertNotIn("'ingest_verified_external_event_v2'", grant_block)
        self.assertIn("'dail_ingest_verified_external_event_v2'", grant_block)

    def test_append_replay_compares_every_caller_controlled_preimage_field(self) -> None:
        replay = self.lower[
            self.lower.index("if v_existing.schema_version = v_schema_version") :
            self.lower.index("raise exception using", self.lower.index("if v_existing.schema_version"))
        ]
        for field in (
            "actor_ref",
            "actor_did",
            "agent_id",
            "entity_version",
            "correlation_id",
            "causation_id",
            "authority_basis",
            "approval_id",
            "visibility_class",
            "payload_ref",
            "correction_of_event_id",
            "supersedes_event_id",
            "chain_anchor_state",
            "signature_ref",
        ):
            self.assertIn(field, replay)

    def test_v2_corrections_cannot_mask_hash_failure(self) -> None:
        self.assertIn(
            "if coalesce(r.schema_version, '1.0.0') in ('1.0.0', '1.1.0')",
            self.lower,
        )
        self.assertIn("dail_integrity_corrections_v2_reject_update_delete", self.lower)
        self.assertIn("dail_integrity_corrections_v2_reject_truncate", self.lower)
        self.assertIn(
            "revoke all on table chlom_runtime.dail_integrity_corrections",
            self.lower,
        )

    def test_portable_numeric_dialect_is_enforced_in_both_hash_paths(self) -> None:
        self.assertIn("jsonb_uses_portable_numbers_v1", self.lower)
        self.assertIn("portable integer-only canonical json dialect", self.lower)

    def test_factory_source_cannot_self_promote_or_fork(self) -> None:
        table_start = self.lower.index(
            "create table chlom_runtime.factory_continuation_receipts_v2"
        )
        table_end = self.lower.index(
            "alter table chlom_runtime.dail_events", table_start
        )
        table = self.lower[table_start:table_end]
        state_check = re.search(r"state in \(([^)]*)\)", table)
        self.assertIsNotNone(state_check)
        states = state_check.group(1) if state_check else ""
        self.assertNotIn("completed", states)
        self.assertNotIn("implemented", states)
        for field in (
            "security_verifier_id",
            "security_receipt_sha256",
            "test_verifier_id",
            "test_receipt_sha256",
            "retry_count",
            "provider_request_digest",
            "readback_digest",
        ):
            self.assertIn(field, table)
        self.assertIn("would fork or skip the stream", self.lower)
        self.assertIn("must advance exactly once", self.lower)

        manifest = json.loads(FACTORY.read_text(encoding="utf-8"))
        controls = manifest["continuation_controls"]
        self.assertEqual(controls["claim_algorithm_source_state"], "SPECIFIED_RUNTIME_PENDING")
        self.assertEqual(
            controls["expired_running_claim_reclaim_source_state"],
            "SPECIFIED_RUNTIME_PENDING",
        )
        self.assertFalse(manifest["receipt_surfaces"]["cross_shape_substitution_allowed"])

    def test_append_only_tables_have_rls_acl_and_mutation_guards(self) -> None:
        tables = {
            "dail_events": "dail_events_v2",
            "dail_integrity_corrections": "dail_integrity_corrections_v2",
            "external_ingress_receipts_v2": "external_ingress_receipts_v2",
            "external_verification_receipts_v2": "external_verification_receipts_v2",
            "external_anchor_receipts_v2": "external_anchor_receipts_v2",
            "processing_receipts_v2": "processing_receipts_v2",
            "factory_continuation_receipts_v2": "factory_continuation_receipts_v2",
        }
        for table, trigger_prefix in tables.items():
            with self.subTest(table=table):
                self.assertIn(f"alter table chlom_runtime.{table} force row level security", self.lower)
                self.assertIn(f"revoke all on table chlom_runtime.{table}", self.lower)
                self.assertIn(f"{trigger_prefix}_reject_truncate", self.lower)

    def test_edge_reads_exact_bytes_and_never_projects_secret_material(self) -> None:
        handler = (EDGE / "handler.ts").read_text(encoding="utf-8")
        index = (EDGE / "index.ts").read_text(encoding="utf-8")
        readme = (EDGE / "README.md").read_text(encoding="utf-8")
        combined = handler + index
        self.assertIn("request.arrayBuffer()", handler)
        self.assertNotIn("await request.json(", handler)
        self.assertNotIn("await request.text(", handler)
        self.assertNotIn("console.", combined)
        self.assertIn("p_admission_mac", handler)
        self.assertIn("DAIL_INGRESS_ADMISSION_HMAC_KEY", handler)
        self.assertIn("verify_jwt = false", readme)
        self.assertNotRegex(handler, r"p_raw_body\s*:")
        self.assertNotRegex(handler, r"p_signature_header\s*:")

    def test_sql_dollar_quotes_are_paired(self) -> None:
        tags = re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", self.sql)
        for tag in set(tags):
            with self.subTest(tag=tag):
                self.assertEqual(tags.count(tag) % 2, 0)


if __name__ == "__main__":
    unittest.main()
