from pathlib import Path


MIGRATION = Path("supabase/migrations/20260901174500_app_factory_provider_dispatch_rpc_least_privilege_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901174500_app_factory_provider_dispatch_rpc_least_privilege_v1_rollback.sql")

TARGETS = {
    "public.app_factory_operational_cleanup_dispatch(text)": "b1db1dfd098ea8553e9ecf4b8896b14c565cbd1d171bf46863576b1e11305a59",
    "public.app_factory_ssl_control_dispatch(text)": "5a85557bc1a27317920fae869dddddd24e042f9342b3c4e75ebb1c615c060a79",
    "public.app_factory_docroot_control_dispatch(text)": "78ecf659712ff65755664bff5a7738a3d77e0db4a4f4cab09e0a0f2026625827",
    "public.app_factory_storage_repair_dispatch(text)": "4581b2893095468929def1ed00e7c755a8dd85a4f7b5a42bbc4f9549ae9cfd57",
}


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_contracts_exact_provider_dispatch_rpc_cohort():
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


def test_migration_is_acl_only_and_does_not_rewrite_provider_dispatchers():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for signature in TARGETS:
        function_name = signature.split("(", 1)[0]
        assert f"create or replace function {function_name}" not in sql
    assert "grant execute" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql


def test_preflight_requires_expected_security_definer_bytes():
    sql = _normalized(MIGRATION)
    assert "security_definer_expected" in sql
    assert "definition_drift" in sql
    assert "pg_get_functiondef" in sql
    for expected_sha in TARGETS.values():
        assert expected_sha in sql


def test_recovery_refuses_definition_drift_and_never_reopens_end_user_execute():
    sql = _normalized(ROLLBACK)
    assert "fail-closed recovery" in sql
    assert "rollback_refuses_changed_app_factory_provider_dispatch_rpc" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
    for signature, expected_sha in TARGETS.items():
        assert signature in sql
        assert expected_sha in sql
