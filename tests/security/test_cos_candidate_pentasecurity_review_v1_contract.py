from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/20260901233134_cos_candidate_pentasecurity_exact_review_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901233134_cos_candidate_pentasecurity_exact_review_v1_rollback.sql"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_exact_candidate_security_review_is_bounded_and_independent():
    sql = text(MIGRATION)
    assert "penta_security.review_cos_release_candidate_v1" in sql
    assert "cos_release_candidates_v1" in sql
    assert "cos_release_candidate_events_v1" in sql
    assert "github_security_check_receipts_v2" in sql
    assert "candidate_tree_exact_match" in sql
    assert "security_policy_job" in sql
    assert "codeql_compatibility_job" in sql
    assert "current_main_security_green" in sql
    assert "independent_certification',false" in sql
    assert "release_decision',false" in sql
    assert "rights_disposition',false" in sql
    assert "provider_write',false" in sql
    assert "money_movement',false" in sql
    assert "d3_execution',false" in sql
    assert "authority_expansion',false" in sql


def test_exact_candidate_review_is_service_role_only_and_append_only():
    sql = text(MIGRATION)
    assert "revoke all on function penta_security.review_cos_release_candidate_v1(text) from public, anon, authenticated" in sql
    assert "grant execute on function penta_security.review_cos_release_candidate_v1(text) to service_role" in sql
    assert "before update or delete" in sql
    assert "pentasecurity_cos_candidate_review_append_only" in sql


def test_rollback_preserves_receipts_and_fails_closed():
    sql = text(ROLLBACK)
    assert "hold_review_runtime_rolled_back_fail_closed" in sql
    assert "historical_receipts_preserved',true" in sql
    assert "drop table" not in sql
    assert "delete from penta_security.cos_release_candidate_review_receipts_v1" not in sql
    assert "independent_certification',false" in sql
    assert "authority_expansion',false" in sql
