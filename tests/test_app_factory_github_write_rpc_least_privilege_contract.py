from pathlib import Path


MIGRATION = Path("supabase/migrations/20260901173500_app_factory_github_write_rpc_least_privilege_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901173500_app_factory_github_write_rpc_least_privilege_v1_rollback.sql")

TARGETS = {
    "public.app_factory_github_create_new_file(text,text,text,text,text)": "de12cceb489ebbcee07ddbdfa9bbd3899f93ea5213009728820d63a5c71cd4c5",
    "public.app_factory_merge_receipt_pr(text,text,boolean)": "d608455915b902bedf3f810140f4098991bd7c7ac5a5a3d25a4f3928cd31170f",
    "public.app_factory_public_android_canary_apply_known_repairs()": "ce7863a4dcaa1f9b66f3e74d6705fb4f928d3c17305d7cfcb49dc420211a6745",
    "public.app_factory_publish_final_release_receipts()": "8b0a8258912c75edeba900133765a411a09c7ed0013a8413c7b4f460ca8ce6f0",
}


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_covers_exact_provider_write_cohort_and_contracts_end_user_execute():
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


def test_migration_is_acl_only_and_cannot_rewrite_provider_executors():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for signature in TARGETS:
        function_name = signature.split("(", 1)[0]
        assert f"create or replace function {function_name}" not in sql
    assert "grant execute" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql


def test_preflight_is_exact_definition_bound_and_fail_closed_on_drift():
    sql = _normalized(MIGRATION)
    assert "security_definer_expected" in sql
    assert "definition_drift" in sql
    assert "pg_get_functiondef" in sql
    for expected_sha in TARGETS.values():
        assert expected_sha in sql


def test_recovery_refuses_definition_drift_and_never_reopens_end_user_execute():
    sql = _normalized(ROLLBACK)
    assert "fail-closed recovery" in sql
    assert "rollback_refuses_changed_app_factory_github_write_rpc" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
    for signature, expected_sha in TARGETS.items():
        assert signature in sql
        assert expected_sha in sql
