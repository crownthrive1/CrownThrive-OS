import re
from pathlib import Path

MIGRATION = Path('supabase/migrations/20260901191000_penta_security_governance_source_policy_pack_v1.sql')
ROLLBACK = Path('supabase/rollback/20260901191000_penta_security_governance_source_policy_pack_v1_rollback.sql')

POLICY_2020 = 'ct.penta.security.policy.institutional-pre-release-certification-v2.v1'
SOURCE_2020 = 'supabase/migrations/20260831074800_penta_institutional_pre_release_certification_v2.sql'
POLICY_1894 = 'ct.penta.security.policy.penta-assure-independent-certifier-integrity-v2.v1'
SOURCE_1894 = 'supabase/migrations/20260830194000_penta_assure_independent_certifier_integrity_v2.sql'

SQL_OBJECT = re.compile(
    r"\b(?:create|alter|drop)\s+(?:or\s+replace\s+)?(?:table|function|view|sequence|policy|trigger)\s+"
    r"(?:if\s+(?:not\s+)?exists\s+)?([A-Za-z_][A-Za-z0-9_.]*)",
    re.IGNORECASE,
)


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_policy_pack_targets_exact_governance_repairs_and_existing_reviewer():
    sql = _text(MIGRATION)
    assert "review_github_provider_source_v1(text,text)" in sql
    for policy, source in ((POLICY_2020, SOURCE_2020), (POLICY_1894, SOURCE_1894)):
        assert policy in sql
        assert source in sql


def test_2020_policy_requires_certification_order_and_separation_controls():
    sql = _text(MIGRATION)
    assert "penta_change_precert_status_v2" in sql
    assert "penta_change_postrelease_status_v2" in sql
    assert "penta_change_issue_certification_v2" in sql
    assert "ORIGINATOR_CANNOT_CERTIFY" in sql
    assert "SUBJECT_DIGEST_MISMATCH" in sql
    assert "separation_of_duties_satisfied" in sql
    assert "v_pre:=integration_control.penta_change_precert_status_v1" in sql


def test_1894_policy_requires_concrete_certifier_identity_and_service_role_acl():
    sql = _text(MIGRATION)
    assert "certifier_id" in sql
    assert "originator_id" in sql
    assert "self_certification_detected" in sql
    assert "certifier_is_builder" in sql
    assert "certifier_is_producer" in sql
    assert "d3_human_reserved" in sql
    assert "independence_contract_version" in sql
    assert "penta_assure_certify_v1(text,text,text,jsonb,jsonb,timestamptz,jsonb)" in sql
    assert "to service_role;" in sql


def test_policy_pack_is_review_only_and_authority_neutral():
    sql = _text(MIGRATION).lower()
    assert "authority_effect" in sql
    assert sql.count("'none'") >= 2
    assert "provider-write" in sql or "provider write" in sql
    assert "does not rewrite" in sql


def test_policy_pack_forbids_end_user_certification_and_explicit_authority_expansion():
    sql = _text(MIGRATION).lower()
    assert "to anon" in sql
    assert "to authenticated" in sql
    assert "to public" in sql
    assert "'authority_expansion',true" in sql or "'authority_expansion', true" in sql


def test_policy_data_literals_do_not_claim_target_runtime_objects_in_collision_scanner():
    sql = _text(MIGRATION)
    assert SQL_OBJECT.findall(sql) == []


def test_rollback_preserves_history_and_retires_both_policies_fail_closed():
    sql = _text(ROLLBACK).lower()
    assert POLICY_2020 in sql
    assert POLICY_1894 in sql
    assert "'1.0.1'" in sql
    assert "'retired'" in sql
    assert "'1.0.0'" in sql
    assert "delete from penta_security.provider_source_policies_v1" not in sql
    assert "update penta_security.provider_source_policies_v1" not in sql
    assert "hold_policy_not_active" in sql or "fail closed" in sql
