from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/20260901233721_cos_candidate_chlom_authority_rights_review_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901233721_cos_candidate_chlom_authority_rights_review_v1_rollback.sql"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_chlom_review_is_exact_candidate_and_technical_only():
    sql = text(MIGRATION)
    assert "review_cos_release_candidate_authority_rights_v1" in sql
    assert "cos_release_candidates_v1" in sql
    assert "cos_release_candidate_events_v1" in sql
    assert "provider_readback" in sql and "chlom_cie" in sql
    assert "production_hot" in sql
    assert "pass_technical_no_authority_or_rights_mutation_observed" in sql
    assert "legal_rights_conclusion',false" in sql
    assert "third_party_rights_validated',false" in sql
    assert "new_rights_granted',false" in sql
    assert "existing_rights_modified',false" in sql
    assert "release_authority_created',false" in sql
    assert "certification_created',false" in sql
    assert "independent_certification',false" in sql
    assert "d3_execution',false" in sql
    assert "authority_expansion',false" in sql


def test_chlom_review_is_service_role_only_append_only_and_dail_bound():
    sql = text(MIGRATION)
    assert "revoke all on function chlom_runtime.review_cos_release_candidate_authority_rights_v1(text) from public, anon, authenticated" in sql
    assert "grant execute on function chlom_runtime.review_cos_release_candidate_authority_rights_v1(text) to service_role" in sql
    assert "before update or delete" in sql
    assert "chlom_cos_candidate_authority_rights_receipt_append_only" in sql
    assert "chlom_append_dail_event" in sql
    assert "dail_event_hash" in sql


def test_chlom_rollback_fails_closed_without_erasing_evidence():
    sql = text(ROLLBACK)
    assert "hold_review_runtime_rolled_back_fail_closed" in sql
    assert "historical_receipts_preserved',true" in sql
    assert "drop table" not in sql
    assert "delete from chlom_runtime.cos_release_candidate_authority_rights_receipts_v1" not in sql
    assert "legal_rights_conclusion',false" in sql
    assert "authority_expansion',false" in sql
