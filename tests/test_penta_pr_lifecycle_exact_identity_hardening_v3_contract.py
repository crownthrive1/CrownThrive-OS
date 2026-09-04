from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260903222000_penta_pr_lifecycle_exact_identity_hardening_v3.sql"
)
ROLLBACK = Path(
    "supabase/rollback/20260903222000_penta_pr_lifecycle_exact_identity_hardening_v3_rollback.sql"
)


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_classifier_converges_case_only_repo_aliases_on_exact_head():
    sql = _normalized(MIGRATION)
    assert "v_repo text := trim(coalesce(p_repo, ''))" in sql
    assert "where lower(repo) = lower(v_repo)" in sql
    assert "and head_sha = p_head_sha" in sql
    assert "or head_sha is null" not in sql
    assert "get diagnostics v_rows = row_count" in sql
    assert "'lifecycle_rows_updated', v_rows" in sql


def test_classifier_remains_fail_closed_and_does_not_expand_authority():
    sql = _normalized(MIGRATION)
    assert "security definer" in sql
    assert "exact_pr_identity_required" in sql
    assert "pr_owner_required" in sql
    assert "next_predicate_required" in sql
    assert "external_hold_review_at_required" in sql
    assert "provenance_ref_required" in sql
    assert "authority_created', false" in sql
    assert "grant execute" not in sql
    assert "grant all" not in sql


def test_stale_sequence_guard_remains_in_force_after_hardening():
    sql = _normalized(MIGRATION)
    assert "stale_restack_required" in sql
    assert "handoff_required_before_terminalization" in sql
    assert "invalid_successor_pr_number" in sql
    assert "current_merge_ready" in sql


def test_rollback_restores_post_sequence_pre_hardening_classifier():
    sql = _normalized(ROLLBACK)
    assert "fail-closed rollback" in sql
    assert "where repo = p_repo" in sql
    assert "and (head_sha = p_head_sha or head_sha is null)" in sql
    assert "grant execute" not in sql
    assert "grant all" not in sql
