from pathlib import Path

MIGRATION = Path("supabase/migrations/20260905223500_penta_pr_exact_detail_refresh_v1.sql")


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_exact_head_identity_and_single_pr_scope_are_mandatory():
    text = source()
    assert "p_expected_head_sha !~ '^[0-9a-f]{40}$'" in text
    assert "where repo=p_repo and pr_number=p_pr_number and terminal_state is null" in text
    assert "lower(coalesce(v_row.head_sha,'')) <> p_expected_head_sha" in text
    assert "v_observed_head <> p_expected_head_sha" in text
    assert "HOLD_HEAD_DRIFT" in text


def test_provider_surface_is_read_only_and_bounded():
    text = source().lower()
    assert "'get'::extensions.http_method" in text
    assert "/pulls/'||p_pr_number::text" in text
    assert "/check-runs?per_page=100" in text
    assert "hold_check_run_pagination_required" in text
    assert "provider_write',false" in text
    assert "raw_provider_body_stored',false" in text
    for forbidden in ("'post'::extensions.http_method", "'put'::extensions.http_method", "'patch'::extensions.http_method", "'delete'::extensions.http_method"):
        assert forbidden not in text


def test_check_aggregation_matches_canonical_nonfailure_contract():
    text = source()
    assert "coalesce(v_check->>'status','')<>'completed'" in text
    assert "not in ('success','neutral','skipped')" in text
    assert "when v_pending>0 then 'PENDING'" in text
    assert "when v_bad>0 then 'FAILURE'" in text
    assert "else 'SUCCESS'" in text


def test_superseded_check_attempts_are_collapsed_by_logical_identity():
    text = source()
    assert "row_number() over" in text
    assert "j.value#>>'{app,slug}'" in text
    assert "j.value->>'name'" in text
    assert "where ranked.rn=1" in text
    assert "v_logical_total:=v_logical_total+1" in text
    assert "check_runs_logical_total" in text
    assert "check_run_identity','app_slug+name_latest'" in text
    assert "when v_logical_total=0 then 'UNKNOWN'" in text


def test_latest_logical_nonpass_still_fails_closed():
    text = source()
    assert "coalesce(v_check->>'conclusion','') not in ('success','neutral','skipped')" in text
    assert "v_bad:=v_bad+1" in text
    assert "when v_bad>0 then 'FAILURE'" in text
    assert "superseded cancelled/failed attempt cannot poison a later successful rerun" in text
    assert "A currently-latest cancelled/failed check still fails closed" in text


def test_concurrency_and_lifecycle_cas_fail_closed():
    text = source()
    assert "pg_try_advisory_xact_lock" in text
    assert "for update" in text.lower()
    assert "where id=v_row.id and head_sha=p_expected_head_sha and terminal_state is null" in text
    assert "HOLD_LIFECYCLE_CHANGED_DURING_READBACK" in text


def test_service_role_only_wrapper_and_no_authority_expansion():
    text = source().lower()
    assert "revoke all on function public.penta_pr_refresh_exact_detail_v1(text,bigint,text) from public, anon, authenticated" in text
    assert "grant execute on function public.penta_pr_refresh_exact_detail_v1(text,bigint,text) to service_role" in text
    assert "authority_created',false" in text
    assert "security definer" in text


def test_governed_evidence_append_is_present():
    text = source()
    assert "chlom_runtime.append_dail_event" in text
    assert "penta_pr.lifecycle.github_exact_detail_reconciliation" in text
    assert "PROVIDER_DETAIL_READBACK_EXACT" in text
    assert "detail_response_sha256" in text
    assert "check_runs_response_sha256" in text