from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20260829021500_penta_self_forward_repair_persistence_v2.sql"
CONTRACT = ROOT / "data/penta/pentaself-forward-repair-persistence.v2.json"


def test_contract_is_forward_only_and_d3_closed() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["contract"] == "ct.penta.self.forward-repair.v2"
    assert contract["status"] == "production"
    assert contract["state_rules"]["repair_direction"] == "forward_only"
    assert contract["state_rules"]["automatic_rollback"] is False
    assert contract["state_rules"]["verified_resolution_is_monotonic"] is True
    assert contract["state_rules"]["reopen_requires"] == "newer_independent_failure_evidence"
    assert contract["d3_human_reserved"] is True
    assert "does_not_execute_d3" in contract["non_authorities"]


def test_migration_declares_redundant_watchdogs() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "ct-penta-self-persistence-guard-v2" in sql
    assert "ct-penta-self-persistence-watchdog-v2" in sql
    assert "select penta_self.persistence_guard_tick_v2();" in sql
    assert "penta_self.required_cron_contracts_v2" in sql
    assert "penta_self.problem_resolution_watermarks_v2" in sql
    assert "penta_self.external_truth_cache_v2" in sql


def test_migration_never_automatically_rolls_back_or_deletes_history() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    normalized = " ".join(sql.lower().split())
    assert "rollback_performed',false" in normalized
    assert "repair_drift_forward" in normalized
    assert "quarantine_duplicate" in normalized
    assert "update cron.job set active=false" in normalized
    assert "delete from cron.job" not in normalized
    assert "drop table penta_self.persistence_receipts_v2" not in normalized
    assert "drop table penta_self.problem_resolution_watermarks_v2" not in normalized


def test_new_internal_surface_is_service_role_only_and_receipts_are_append_only() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for table in (
        "required_cron_contracts_v2",
        "persistence_receipts_v2",
        "problem_resolution_watermarks_v2",
        "external_truth_cache_v2",
    ):
        assert f"alter table penta_self.{table} enable row level security" in sql
    assert "revoke all on penta_self.required_cron_contracts_v2" in sql
    assert "from public,anon,authenticated" in sql
    assert "persistence_receipts_immutable_v2" in sql
    assert "raise exception 'penta_self.persistence_receipts_v2 is append-only'" in sql


def test_verified_resolution_cannot_be_reopened_by_older_observation() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "coalesce(p.last_seen_at,p.updated_at,p.created_at)<=w.verified_at" in sql
    assert "newer independent failure required" in sql
