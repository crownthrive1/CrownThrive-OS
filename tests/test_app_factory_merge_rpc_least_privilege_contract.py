from pathlib import Path


MIGRATION = Path("supabase/migrations/20260901171500_app_factory_merge_rpc_least_privilege_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901171500_app_factory_merge_rpc_least_privilege_v1_rollback.sql")
SIGNATURE = "public.app_factory_merge_production_pr(text,text,boolean)"
INCIDENT_DEFINITION_SHA = "29af46e774a7fd6fadec29f063928bc96950a6a4021d185f07dbf69ceb02f394"


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_targets_only_exact_merge_rpc_and_removes_end_user_execute():
    sql = _normalized(MIGRATION)
    assert SIGNATURE in sql
    assert INCIDENT_DEFINITION_SHA in sql
    assert "app_factory_merge_rpc_definition_drift" in sql
    assert f"revoke all on function {SIGNATURE}" in sql
    assert "from public, anon, authenticated" in sql
    assert f"grant execute on function {SIGNATURE}" in sql
    assert "to service_role" in sql
    assert "app_factory_merge_rpc_anon_execute_still_present" in sql
    assert "app_factory_merge_rpc_authenticated_execute_still_present" in sql
    assert "app_factory_merge_rpc_service_role_execute_missing" in sql


def test_migration_does_not_change_merge_function_body_or_expand_authority():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function public.app_factory_merge_production_pr" not in sql
    assert "app_factory_github_token" not in sql
    assert "grant execute" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql


def test_recovery_is_definition_bound_and_never_reopens_known_vulnerable_acl():
    sql = _normalized(ROLLBACK)
    assert SIGNATURE in sql
    assert INCIDENT_DEFINITION_SHA in sql
    assert "fail-closed recovery" in sql
    assert "rollback_refuses_changed_app_factory_merge_rpc" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql


def test_incident_contract_documents_provider_write_and_no_authority_expansion():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "vaulted github token" in sql
    assert "provider" in sql
    assert "service-role only" in sql
    assert "does not change function bytes" in sql
