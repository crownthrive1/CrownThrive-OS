from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / "supabase/migrations/20260905020500_penta_pr_restack_owner_execution_surface_v1.sql").read_text()
LOW = SQL.lower()


def test_exact_assignment_and_authority_bounds():
    assert "PR_RESTACK_CURRENT_MAIN" in SQL
    assert "provider_write_allowed" in SQL
    assert "risk_class not in ('D0','D1','D2')" in SQL
    assert "authority_ceiling not in ('D0','D1','D2')" in SQL
    assert "d3_human_reserved is distinct from true" in LOW
    assert "money_movement_allowed" in SQL
    assert "credential_change_allowed" in SQL
    assert "authority_expansion" in SQL


def test_provider_rechecks_current_main_and_predecessor_exact_head():
    assert "/branches/main" in SQL
    assert "HOLD_CURRENT_MAIN_DRIFT" in SQL
    assert "HOLD_PREDECESSOR_HEAD_DRIFT" in SQL
    assert "HOLD_PREDECESSOR_NOT_OPEN" in SQL
    assert "source_repo is distinct from v_repo" in SQL


def test_successor_is_draft_only_and_provider_readback_required():
    assert "'draft',true" in SQL
    assert "HOLD_RESTACK_PR_READBACK_FAILED" in SQL
    assert "v_read_body#>>'{head,sha}' is distinct from v_successor_head" in SQL
    assert "v_read_body#>>'{base,ref}' is distinct from 'main'" in SQL
    assert "predecessor_preserved',true" in SQL
    assert "predecessor_close_performed',false" in SQL
    assert "merge_performed',false" in SQL
    assert "certification_claimed',false" in SQL


def test_no_merge_close_delete_or_secret_serialization_authority():
    assert "/merge" not in LOW
    assert "method: \"delete\"" not in LOW
    assert "'delete'" not in LOW
    assert "decrypted_secret" in SQL
    assert "v_token" in SQL
    assert "raw_secret" not in LOW
    assert "credential_change_allowed" in SQL
    assert "money_movement_allowed" in SQL
    assert "authority_created',false" in SQL


def test_idempotency_and_concurrency_are_fail_closed():
    assert "assignment_id uuid primary key" in LOW
    assert "pg_try_advisory_xact_lock" in SQL
    assert "SUCCEEDED_IDEMPOTENT" in SQL
    assert "idempotent_existing_successor" in SQL
    assert "HOLD_RESTACK_DIFF_PAGINATION_REQUIRED" in SQL


def test_mobilizer_is_exact_lane_only_and_d3_excluded():
    assert "tag='assignment:PR_RESTACK_CURRENT_MAIN'" in SQL
    assert "risk_class in ('D0','D1','D2')" in SQL
    assert "D3_executed',false" in SQL
    assert "penta_pr_restack_execute_assignment_v1" in SQL
