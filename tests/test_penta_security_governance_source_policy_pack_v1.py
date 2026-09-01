from pathlib import Path

MIGRATION = Path('supabase/migrations/20260901191000_penta_security_governance_source_policy_pack_v1.sql')
ROLLBACK = Path('supabase/rollback/20260901191000_penta_security_governance_source_policy_pack_v1_rollback.sql')
POLICY_KEY = 'ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
SOURCE_PATH = 'supabase/migrations/20260831074800_penta_institutional_pre_release_certification_v2.sql'


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_policy_targets_exact_2020_governance_migration_and_existing_reviewer():
    sql = _text(MIGRATION)
    assert POLICY_KEY in sql
    assert SOURCE_PATH in sql
    assert "review_github_provider_source_v1(text,text)" in sql
    assert "penta_change_precert_status_v2" in sql
    assert "penta_change_postrelease_status_v2" in sql
    assert "penta_change_issue_certification_v2" in sql
    assert "ORIGINATOR_CANNOT_CERTIFY" in sql
    assert "SUBJECT_DIGEST_MISMATCH" in sql
    assert "separation_of_duties_satisfied" in sql


def test_policy_is_review_only_and_authority_neutral():
    sql = _text(MIGRATION).lower()
    assert "authority_effect" in sql
    assert "'none'" in sql
    assert "provider_write" not in sql
    assert "credential_change" not in sql
    assert "money_movement" not in sql
    assert "grant execute on function" in sql  # literal being required from the reviewed #2020 source
    assert "to service_role;" in sql


def test_policy_forbids_old_v1_issuer_path_and_end_user_issue_v2_execution():
    sql = _text(MIGRATION)
    assert "v_pre:=integration_control.penta_change_precert_status_v1" in sql
    assert "to anon" in sql
    assert "to authenticated" in sql


def test_rollback_preserves_history_and_fails_closed_by_retiring_successor():
    sql = _text(ROLLBACK).lower()
    assert POLICY_KEY in sql
    assert "'1.0.1'" in sql
    assert "'retired'" in sql
    assert "'1.0.0'" in sql
    assert "delete from penta_security.provider_source_policies_v1" not in sql
    assert "update penta_security.provider_source_policies_v1" not in sql
    assert "hold_policy_not_active" in sql or "fail closed" in sql
