from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "supabase/migrations/20260905230500_penta_pr_exact_head_detail_refresh_v1.sql").read_text()
LOW = SQL.lower()


def test_refresh_is_exact_pr_and_exact_head_bound():
    assert "p_pr_number bigint" in SQL
    assert "p_expected_head_sha text" in SQL
    assert "HOLD_HEAD_MISMATCH" in SQL
    assert "HOLD_PROVIDER_HEAD_DRIFT" in SQL
    assert "head_sha=lower(p_expected_head_sha)" in SQL
    assert "terminal_state is null" in SQL


def test_refresh_is_read_only_and_service_role_scoped():
    assert "service_role_required" in SQL
    assert "grant execute on function penta_pr.reconcile_github_pr_detail_exact_v1" in LOW
    assert "provider_write',false" in SQL
    assert "authority_created',false" in SQL
    assert "raw_provider_body_stored',false" in SQL
    assert "'post'::extensions.http_method" not in LOW
    assert "'patch'::extensions.http_method" not in LOW
    assert "'put'::extensions.http_method" not in LOW
    assert "'delete'::extensions.http_method" not in LOW


def test_rate_budget_and_provider_reads_fail_closed():
    assert "/rate_limit" in SQL
    assert "HOLD_PROVIDER_RATE_BUDGET" in SQL
    assert "/pulls/'||p_pr_number::text" in SQL
    assert "/check-runs?per_page=100" in SQL
    assert "HOLD_CHECK_RUN_PAGINATION_REQUIRED" in SQL
    assert "HOLD_PROVIDER_CHECK_READBACK" in SQL


def test_check_projection_matches_existing_lifecycle_semantics():
    assert "('success','neutral','skipped')" in SQL
    assert "when v_pending>0 then 'PENDING'" in SQL
    assert "when v_bad>0 then 'FAILURE'" in SQL
    assert "else 'SUCCESS'" in SQL
    assert "check_runs_nonpass" in SQL
    assert "check_runs_pending" in SQL


def test_evidence_is_hashed_and_dail_appended_without_raw_provider_body():
    assert "extensions.digest" in SQL
    assert "detail_response_sha256" in SQL
    assert "check_runs_response_sha256" in SQL
    assert "chlom_runtime.append_dail_event" in SQL
    assert "PROVIDER_DETAIL_EXACT_READBACK" in SQL
    assert "v_detail.content" not in SQL.split("return jsonb_build_object", 1)[-1]


def test_no_authority_expansion_or_unrelated_release_actions():
    assert "/merge" not in LOW
    assert "money_movement" not in LOW
    assert "rights grant" not in LOW
    assert "credential mutation" not in LOW
    assert "force merge" not in LOW
    assert "create extension" not in LOW
