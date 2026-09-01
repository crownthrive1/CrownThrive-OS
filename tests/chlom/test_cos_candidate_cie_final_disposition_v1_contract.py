from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase/migrations/20260901234107_cos_candidate_cie_final_disposition_v1.sql"
ROLLBACK = ROOT / "supabase/rollback/20260901234107_cos_candidate_cie_final_disposition_v1_rollback.sql"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_cie_final_disposition_is_current_link_bound_and_non_activating():
    sql = text(MIGRATION)
    assert "review_cos_release_candidate_cie_final_disposition_v1" in sql
    assert "repository_parent_child_link_receipts_v1" in sql
    assert "cie_production_certification_bridge_status_v1" in sql
    assert "linked_governed" in sql
    assert "guardian_verified" in sql
    assert "family_verified" in sql
    assert "interoperability_verified" in sql
    assert "source_reauthorization_performed',false" in sql
    assert "founder_request_reused',false" in sql
    assert "activation_authorized',false" in sql
    assert "provider_write_effect',false" in sql
    assert "economic_effect',false" in sql
    assert "rights_effect',false" in sql
    assert "vote_effect',false" in sql
    assert "d3_auto',false" in sql
    assert "independent_certification',false" in sql


def test_cie_disposition_is_service_role_only_append_only_and_dail_bound():
    sql = text(MIGRATION)
    assert "revoke all on function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(text) from public, anon, authenticated" in sql
    assert "grant execute on function chlom_runtime.review_cos_release_candidate_cie_final_disposition_v1(text) to service_role" in sql
    assert "before update or delete" in sql
    assert "cie_cos_candidate_disposition_append_only" in sql
    assert "cie.cos-release-candidate-final-disposition.completed.v1" in sql
    assert "dail_event_hash" in sql


def test_cie_rollback_is_fail_closed_and_preserves_receipts():
    sql = text(ROLLBACK)
    assert "hold_review_runtime_rolled_back_fail_closed" in sql
    assert "historical_receipts_preserved',true" in sql
    assert "drop table" not in sql
    assert "delete from chlom_runtime.cos_release_candidate_cie_disposition_receipts_v1" not in sql
    assert "source_reauthorization_performed',false" in sql
    assert "activation_authorized',false" in sql
