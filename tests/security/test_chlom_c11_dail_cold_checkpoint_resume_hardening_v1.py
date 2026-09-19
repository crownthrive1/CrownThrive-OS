from pathlib import Path

MIGRATION = Path("supabase/migrations/20260901103200_chlom_c11_dail_cold_checkpoint_resume_hardening_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901103200_chlom_c11_dail_cold_checkpoint_resume_hardening_v1_rollback.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_hardened_export_omits_dail_payload_bodies():
    sql = _sql()
    assert "payload_body_included" in sql
    assert "'payload_body_included',false" in sql
    assert "'payload',e.payload" not in sql
    assert "payload_sha256" in sql
    assert "export_scope','ledger_lineage" in sql


def test_export_resume_is_durable_and_cas_guarded():
    sql = _sql()
    assert "record_dail_cold_export_progress_v1" in sql
    assert "export_cursor_sequence_id" in sql
    assert "exported_event_count" in sql
    assert "export_chunk_count" in sql
    assert "export_chain_sha256" in sql
    assert "DAIL cold export cursor CAS conflict" in sql
    assert "for update" in sql.lower()
    assert "job_state in ('queued','hold')" in sql


def test_progress_rechecks_canonical_chunk_before_advancing_cursor():
    sql = _sql()
    assert "public.dail_cold_checkpoint_export_chunk_v1(" in sql
    assert "chunk_sha256" in sql
    assert "chunk_last_sequence_id" in sql
    assert "chunk_last_event_hash" in sql
    assert "does not match canonical chunk" in sql


def test_wrapper_preserves_existing_external_connector_boundary():
    sql = _sql()
    assert "enqueue_dail_cold_checkpoint_v2" in sql
    assert "enqueue_dail_cold_checkpoint_v1(p_force)" in sql
    assert "ct-dail-cold-checkpoint-due-v1" in sql
    assert "record_dail_cold_export_progress_v1" in sql
    assert "provider_write" in sql
    assert "googleapis.com" not in sql.lower()
    assert "drive.google.com" not in sql.lower()


def test_resume_hardening_is_least_privilege_and_security_preserving_on_rollback():
    sql = _sql()
    rollback = ROLLBACK.read_text(encoding="utf-8")
    assert "service_role_required" in sql
    assert "revoke all on function chlom_runtime.record_dail_cold_export_progress_v1" in sql
    assert "grant execute on function chlom_runtime.record_dail_cold_export_progress_v1" in sql
    assert "Deliberately retain the hardened public.dail_cold_checkpoint_export_chunk_v1" in rollback
    assert "drop table" not in rollback.lower()
    assert "delete from" not in rollback.lower()
