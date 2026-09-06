from pathlib import Path

MIGRATION = Path("supabase/migrations/20260906222500_penta_scoped_memory_cursor_fabric_v1.sql")


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_reuses_existing_cookie_and_context_fabrics():
    text = source()
    assert "public.penta_cookie_install_v1" in text
    assert "public.penta_cookie_observe_v1" in text
    assert "public.penta_context_ingest_v1" in text
    assert "public.penta_context_query_v1" in text
    assert "create table" not in text.lower()


def test_cursor_is_minimal_scoped_and_deterministic():
    text = source()
    for token in (
        "ct.penta.scoped-memory-cursor.v1",
        "memory_scope",
        "cursor_id",
        "subject_ref",
        "subject_sha256",
        "next_predicate",
        "deterministic",
        "append_supersede_only",
    ):
        assert token in text
    assert "left(v_memory,512)" in text
    assert "memory_summary_sha256" in text


def test_pentachat_and_pentabrain_are_assist_only():
    text = source()
    assert "'penta_chat_assist','context_only'" in text
    assert "'penta_brain_assist','planning_only'" in text
    assert "'penta_chat','context_only'" in text
    assert "'penta_brain','planning_only'" in text


def test_no_destructive_or_authority_expansion_paths():
    text = source().lower()
    for forbidden in (
        "drop table",
        "truncate ",
        "delete from public.penta_protocol_cookies",
        "delete from public.penta_context",
        "force merge",
        "create extension",
    ):
        assert forbidden not in text
    assert "'destructive_authority',false" in text
    assert "'authority_created',false" in text
    assert "d3_human_reserved" in text


def test_service_role_only_and_redaction_bounded():
    text = source()
    assert "service_role_required" in text
    assert "revoke all on function public.penta_scoped_memory_cursor_write_v1" in text
    assert "grant execute on function public.penta_scoped_memory_cursor_write_v1" in text
    assert "public.penta_context_redact_v1" in text
    assert "memory_summary_too_long" in text
    assert "next_predicate_too_long" in text


def test_reconcile_is_idempotent_and_future_compatible():
    text = source()
    assert "from public.penta_system_registry s" in text
    assert "s.maturity<>'retired'" in text
    assert "missing_scoped_cursor" in text
    assert "penta_scoped_memory_cursor_reconcile_v1" in text
    assert "penta_cookie_install_v1" in text
