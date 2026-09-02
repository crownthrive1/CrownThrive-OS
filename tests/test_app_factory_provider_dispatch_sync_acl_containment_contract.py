from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260902223500_app_factory_provider_dispatch_sync_acl_containment_v1.sql"
)
ROLLBACK = Path(
    "supabase/rollback/20260902223500_app_factory_provider_dispatch_sync_acl_containment_v1_rollback.sql"
)
SIGNATURE = "public.app_factory_provider_dispatch_sync(text,text)"
EXPECTED_DEFINITION_SHA = "1e4a7c1696180fc89fe5aff3f11f581cda1b4cc071124bc4c760b06e7beabb5f"


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_is_exact_definition_bound_and_service_role_only():
    sql = _normalized(MIGRATION)
    assert SIGNATURE in sql
    assert EXPECTED_DEFINITION_SHA in sql
    assert "security_definer_expected" in sql
    assert "definition_drift" in sql
    assert f"revoke all on function {SIGNATURE}" in sql
    assert "from public, anon, authenticated" in sql
    assert f"grant execute on function {SIGNATURE}" in sql
    assert "to service_role" in sql
    assert "anon_execute_still_present" in sql
    assert "authenticated_execute_still_present" in sql
    assert "service_role_execute_missing" in sql


def test_migration_is_acl_only_and_does_not_expand_authority():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "create or replace function public.app_factory_provider_dispatch_sync" not in sql
    assert "grant execute" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "no provider call" in sql
    assert "authority expansion" in sql


def test_recovery_refuses_definition_drift_and_remains_fail_closed():
    sql = _normalized(ROLLBACK)
    assert SIGNATURE in sql
    assert EXPECTED_DEFINITION_SHA in sql
    assert "fail-closed recovery" in sql
    assert "rollback_refuses_changed_app_factory_provider_dispatch_sync_rpc" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
