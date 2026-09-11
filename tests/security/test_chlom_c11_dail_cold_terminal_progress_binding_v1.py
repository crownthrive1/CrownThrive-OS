from pathlib import Path

MIGRATION = Path("supabase/migrations/20260901103300_chlom_c11_dail_cold_terminal_progress_binding_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901103300_chlom_c11_dail_cold_terminal_progress_binding_v1_rollback.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_terminal_completion_requires_durable_progress_chain():
    sql = _sql()
    assert "complete_dail_cold_checkpoint_v2" in sql
    assert "export_complete" in sql
    assert "export_cursor_sequence_id" in sql
    assert "exported_event_count" in sql
    assert "export_chunk_count" in sql
    assert "export_last_event_hash" in sql
    assert "export_chain_sha256" in sql
    assert "HOLD_DAIL_COLD_DURABLE_EXPORT_PROGRESS_MISMATCH" in sql


def test_terminal_completion_binds_minimum_data_export_mode():
    sql = _sql()
    assert "lineage_metadata_no_payload_body" in sql
    assert "payload_body_included" in sql
    assert "is distinct from false" in sql


def test_service_role_cannot_bypass_v2_terminal_wrapper():
    sql = _sql()
    assert "revoke all on function chlom_runtime.complete_dail_cold_checkpoint_v1" in sql
    assert "service_role" in sql
    assert "grant execute on function chlom_runtime.complete_dail_cold_checkpoint_v2" in sql
    assert "chlom_runtime.complete_dail_cold_checkpoint_v1(" in sql


def test_due_generator_advertises_mandatory_terminal_rpc():
    sql = _sql()
    assert "enqueue_dail_cold_checkpoint_v3" in sql
    assert "terminal_progress_binding_required" in sql
    assert "chlom_runtime.complete_dail_cold_checkpoint_v2" in sql
    assert "ct-dail-cold-checkpoint-due-v1" in sql


def test_terminal_binding_rollback_preserves_history():
    rollback = ROLLBACK.read_text(encoding="utf-8")
    lowered = rollback.lower()
    assert "cron.unschedule" in rollback
    assert "enqueue_dail_cold_checkpoint_v2(false)" in rollback
    assert "grant execute on function chlom_runtime.complete_dail_cold_checkpoint_v1" in rollback
    assert "delete from" not in lowered
    assert "truncate" not in lowered
    assert "drop table" not in lowered
