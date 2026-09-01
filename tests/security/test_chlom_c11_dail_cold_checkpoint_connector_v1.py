from pathlib import Path

MIGRATION = Path("supabase/migrations/20260901103000_chlom_c11_dail_cold_checkpoint_connector_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901103000_chlom_c11_dail_cold_checkpoint_connector_v1_rollback.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_c11_cold_checkpoint_contract_is_source_controlled_and_bounded():
    sql = _sql()
    assert "record_dail_cold_checkpoint_v2" in sql
    assert "enqueue_dail_cold_checkpoint_v1" in sql
    assert "dail_cold_checkpoint_export_chunk_v1" in sql
    assert "complete_dail_cold_checkpoint_v1" in sql
    assert "verify_dail_chain_checkpoint_v3()" in sql
    assert "chlom_runtime.dail.global.v1" not in sql
    assert "chlom_runtime.dail.cold-checkpoint.receipt.v2" in sql
    assert "p_limit > 5000" in sql
    assert "sequence_id <= v_source_max" in sql
    assert "source_head_event_hash" in sql


def test_c11_cold_export_is_fail_closed_and_least_privilege():
    sql = _sql()
    assert "service_role_required" in sql
    assert "revoke all on function public.dail_cold_checkpoint_export_chunk_v1" in sql
    assert "grant execute on function public.dail_cold_checkpoint_export_chunk_v1" in sql
    assert "chunk_chain_verified" in sql
    assert "all_chunk_hashes_verified" in sql
    assert "component_hashes_verified" in sql
    assert "structured_data_parse_verified" in sql
    assert "drive_readback_verified" in sql
    assert "secret_scan" in sql
    assert "HOLD_DAIL_COLD_EXPORT_EVIDENCE_INCOMPLETE" in sql


def test_c11_recovery_drill_requires_isolated_exact_restore():
    sql = _sql()
    assert "restore_target_class" in sql
    assert "isolated_non_production" in sql
    assert "restored_event_count" in sql
    assert "restored_max_sequence_id" in sql
    assert "restored_head_event_hash" in sql
    assert "cold_route_exercised" in sql
    assert "hot_route_unchanged" in sql
    assert "fault_injection_verified" in sql
    assert "provider_exit_path_verified" in sql
    assert "rollback_and_failback_verified" in sql
    assert "HOLD_DAIL_COLD_RECOVERY_DRILL_EVIDENCE_INCOMPLETE" in sql


def test_c11_reuses_existing_external_connector_failure_domain():
    sql = _sql()
    assert "ct.schedule.external-evidence-relay.hourly.v1" in sql
    assert "provider_write_from_database" in sql
    assert "'provider_write_from_database',false" in sql
    assert "ct-dail-cold-checkpoint-due-v1" in sql
    assert "cron.schedule" in sql
    assert "complete_midnight_backup_v2" not in sql


def test_c11_rollback_is_non_destructive_to_history():
    rollback = ROLLBACK.read_text(encoding="utf-8")
    assert "cron.unschedule" in rollback
    assert "drop function if exists" in rollback
    lowered = rollback.lower()
    assert "delete from chlom_runtime.dail_cold_checkpoints_v1" not in lowered
    assert "truncate" not in lowered
    assert "drop table" not in lowered
