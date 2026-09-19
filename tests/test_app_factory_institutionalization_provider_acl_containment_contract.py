from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260901181024_app_factory_institutionalization_provider_acl_containment_v1.sql"
)
ROLLBACK = Path(
    "supabase/rollback/20260901181024_app_factory_institutionalization_provider_acl_containment_v1_rollback.sql"
)

TARGETS = {
    "public.app_factory_institutionalize_recertification_dispatch()": "1ff2f6fbed6c40848d9989fe9cb64b3aab38607b23d3fc814da3775110a91182",
    "public.app_factory_institutionalize_release_dispatch()": "08ecbc29fa387b24ab8196aaeb1a6a9fab52b4dced8d3e128f897de2107c105a",
    "public.app_factory_merge_institutionalization_dispatch()": "1e7b4da06177c944eee21c22268e01ace12e2adb216a22a30d9c31e156b6b979",
    "public.app_factory_merge_recertification_dispatch()": "218a5cf728f3e083fb6d32e72201a99f01ceed1721f201a9f11cede1af95b81c",
}


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_contracts_exact_institutionalization_dispatch_cohort():
    sql = _normalized(MIGRATION)
    for signature, expected_sha in TARGETS.items():
        assert signature in sql
        assert expected_sha in sql
        assert f"revoke all on function {signature}" in sql
        assert f"grant execute on function {signature}" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "anon_execute_still_present" in sql
    assert "authenticated_execute_still_present" in sql
    assert "service_role_execute_missing" in sql


def test_migration_is_acl_only_and_does_not_rewrite_dispatchers():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for signature in TARGETS:
        function_name = signature.split("(", 1)[0]
        assert f"create or replace function {function_name}" not in sql
    assert "grant execute" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql


def test_preflight_requires_exact_security_definer_bytes():
    sql = _normalized(MIGRATION)
    assert "security_definer_expected" in sql
    assert "definition_drift" in sql
    assert "pg_get_functiondef" in sql
    for expected_sha in TARGETS.values():
        assert expected_sha in sql


def test_recovery_refuses_definition_drift_and_never_reopens_end_user_execute():
    sql = _normalized(ROLLBACK)
    assert "fail-closed recovery" in sql
    assert "rollback_refuses_changed_app_factory_institutionalization_rpc" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
    for signature, expected_sha in TARGETS.items():
        assert signature in sql
        assert expected_sha in sql
