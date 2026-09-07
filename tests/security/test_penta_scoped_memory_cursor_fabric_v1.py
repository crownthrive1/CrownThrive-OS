from pathlib import Path

MIGRATION = Path("supabase/migrations/20260906222500_penta_scoped_memory_cursor_fabric_v1.sql")


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_reuses_existing_cookie_context_and_continuity_pointer():
    text = source()
    assert "public.penta_cookie_install_v1" in text
    assert "public.penta_cookie_observe_v1" in text
    assert "public.penta_context_ingest_v1" in text
    assert "public.penta_context_query_v1" in text
    assert "scoped_memory_v1" in text
    assert "memory_pointer_source','scoped_memory_v1'" in text
    assert "create table" not in text.lower()


def test_security_definer_does_not_trust_current_user_for_caller_identity():
    text = source()
    assert "session_user in ('postgres','supabase_admin')" in text
    assert "request.jwt.claims" in text
    assert "penta_system_claim_required" in text
    assert "cross_penta_caller_denied" in text
    assert "if current_user not in" not in text


def test_owner_and_actor_spoofing_fail_closed():
    text = source()
    assert "owner_override_not_authorized" in text
    assert "actor_override_not_authorized" in text
    assert "v_owner<>v_system.system_key" in text
    assert "v_actor<>'penta.context'" in text
    assert "'penta.context'" in text


def test_pointer_provenance_is_bound_to_exact_system_scope_and_tenant():
    text = source()
    assert "scoped_memory_pointer_identity_mismatch" in text
    assert "r.context_id::text=v_continuity_cursor" in text
    assert "r.scope_key=v_scope" in text
    assert "r.system_ref=v_system.system_key" in text
    assert "r.tenant_ref='crownthrive'" in text


def test_cursor_requires_explicit_cookie_cas_revision():
    text = source()
    assert "p_expected_cookie_revision" in text
    assert "expected_cookie_revision_required" in text
    assert "stale_cookie_revision" in text
    assert "for update nowait" in text
    assert "'cas_required',true" in text
    assert "prior_cookie_revision" in text


def test_active_cursor_requires_bounded_lease():
    text = source()
    assert "active_cursor_lease_required" in text
    assert "cursor_lease_expired" in text
    assert "cursor_lease_too_long" in text
    assert "interval '24 hours'" in text
    assert "lease_required_for_active" in text
    assert "expired_active_cursor" in text


def test_semantic_replay_is_no_change_not_new_mutation():
    text = source()
    assert "v_existing_cursor_id=v_cursor_id" in text
    assert "'state','no_change'" in text
    assert "v_cursor_id:=public.penta_protocol_sha256_v1" in text


def test_cursor_is_minimal_scoped_and_deterministic():
    text = source()
    for token in (
        "ct.penta.scoped-memory-cursor.v1",
        "memory_scope",
        "cursor_id",
        "continuity_cursor_ref",
        "continuity_contract_ref",
        "subject_ref",
        "subject_sha256",
        "next_predicate",
        "deterministic",
        "append_supersede_only",
    ):
        assert token in text
    assert "left(v_memory,512)" in text
    assert "memory_summary_sha256" in text


def test_does_not_invent_second_memory_namespace():
    text = source()
    assert "v_scope:=nullif(btrim(v_pointer->>'scope'),'')" in text
    assert "scoped_memory_pointer_required" in text
    assert "pointer_cursor_aligned" in text
    assert "continuity_pointer_ready" in text
    assert "'penta:'||lower" not in text


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


def test_service_role_acl_and_redaction_are_bounded():
    text = source()
    assert "service_role_required" in text
    assert "revoke all on function public.penta_scoped_memory_cursor_write_v1" in text
    assert "grant execute on function public.penta_scoped_memory_cursor_write_v1" in text
    assert "public.penta_context_redact_v1" in text
    assert "memory_summary_too_long" in text
    assert "next_predicate_too_long" in text
    assert "greatest(1,least(coalesce(p_limit,4),8))" in text


def test_reconcile_is_idempotent_pointer_gated_and_does_not_reset_existing_cursor():
    text = source()
    assert "from public.penta_system_registry s" in text
    assert "s.maturity<>'retired'" in text
    assert "pointer_missing" in text
    assert "penta_scoped_memory_cursor_reconcile_v1" in text
    assert "coalesce(c.observed_state->'scoped_cursor'->>'contract','')<>'ct.penta.scoped-memory-cursor.v1'" in text
    assert "r.current_revision" in text


def test_contention_is_deferred_instead_of_overwriting():
    text = source()
    assert "lock_not_available" in text
    assert "deferred_contention" in text
    assert "retryable" in text
