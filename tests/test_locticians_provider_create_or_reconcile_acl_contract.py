from pathlib import Path


MIGRATION = Path("supabase/migrations/20260903001200_locticians_provider_create_or_reconcile_acl_v1.sql")
ROLLBACK = Path("supabase/rollback/20260903001200_locticians_provider_create_or_reconcile_acl_v1_rollback.sql")
SIGNATURE = "integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)"
EXPECTED_SHA = "3453a6b6ece69dc2d75cb1a48bf64dd11c9bd9a72a93e68ce8e6695ac4cc8947"


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_is_exact_definition_bound_and_acl_only():
    sql = _normalized(MIGRATION)
    assert SIGNATURE in sql
    assert EXPECTED_SHA in sql
    assert "pg_get_functiondef" in sql
    assert "security definer" in sql
    assert "revoke execute on function" in sql
    assert "from public, anon, authenticated" in sql
    assert "to postgres, service_role" in sql
    assert "create or replace function integration_control.locticians_universal_provider_create_or_reconcile_v4" not in sql


def test_migration_requires_negative_and_service_role_readback():
    sql = _normalized(MIGRATION)
    assert "anon execute remains enabled" in sql
    assert "authenticated execute remains enabled" in sql
    assert "service_role execute missing" in sql
    assert "postgres execute missing" in sql


def test_recovery_is_monotonic_and_never_reopens_end_user_execution():
    sql = _normalized(ROLLBACK)
    assert SIGNATURE in sql
    assert EXPECTED_SHA in sql
    assert "rollback_refuses_changed_locticians_provider_rpc" in sql
    assert "from public, anon, authenticated" in sql
    assert "to postgres, service_role" in sql
    assert "to public" not in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
