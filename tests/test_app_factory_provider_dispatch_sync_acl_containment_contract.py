from pathlib import Path

MIGRATION = Path("supabase/migrations/20260903114000_app_factory_provider_dispatch_sync_acl_containment_v1.sql")
ROLLBACK = Path("supabase/rollback/20260903114000_app_factory_provider_dispatch_sync_acl_containment_v1_rollback.sql")
SIGNATURE = "public.app_factory_provider_dispatch_sync(text,text)"
EXPECTED_SHA = "1e4a7c1696180fc89fe5aff3f11f581cda1b4cc071124bc4c760b06e7beabb5f"


def _normalized(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_migration_is_exact_definition_bound_and_least_privilege():
    sql = _normalized(MIGRATION)
    assert SIGNATURE in sql
    assert EXPECTED_SHA in sql
    assert "security_definer_expected" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
    assert "service_role_execute_missing" in sql


def test_recovery_contract_is_fail_closed_and_never_restores_end_user_execute():
    sql = _normalized(ROLLBACK)
    assert SIGNATURE in sql
    assert EXPECTED_SHA in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "grant execute" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql


def test_source_contract_declares_no_authority_expansion_or_provider_dispatch_invocation():
    sql = _normalized(MIGRATION)
    assert "does not invoke provider dispatch" in sql
    assert "does not invoke provider dispatch, change credentials, move money" in sql
    assert "create d3/other authority" in sql
