from pathlib import Path


MIGRATION = Path("supabase/migrations/20260901160800_penta_help_security_rls_baseline_v1.sql")
ROLLBACK = Path("supabase/rollback/20260901160800_penta_help_security_rls_baseline_v1.rollback.sql")

TARGETS = (
    "penta_help.requests_v1",
    "penta_help.routes_v1",
    "penta_help.liaison_threads_v1",
    "penta_help.receipts_v1",
    "penta_security.runtime_review_receipts_v1",
)


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_migration_enables_deny_by_default_rls_without_force_rls():
    sql = _sql(MIGRATION)
    for target in TARGETS:
        assert f"alter table {target} enable row level security;" in sql
        assert f"revoke all on table {target} from public, anon, authenticated;" in sql
        assert f"alter table {target} force row level security" not in sql

    assert "create policy" not in sql
    assert "grant select" not in sql or "to anon" not in sql
    assert "grant insert" not in sql or "to anon" not in sql
    assert "grant update" not in sql or "to anon" not in sql
    assert "grant delete" not in sql or "to anon" not in sql
    assert "grant select" not in sql or "to authenticated" not in sql


def test_migration_requires_expected_bypassrls_semantics_and_no_existing_policy_or_end_user_acl():
    sql = _sql(MIGRATION)
    assert "rolname in ('postgres','service_role') and not x.rolbypassrls" in sql
    assert "rolname in ('anon','authenticated') and x.rolbypassrls" in sql
    assert "penta_security_rls_baseline_preexisting_policy" in sql
    assert "penta_security_rls_baseline_end_user_direct_grant_present" in sql
    assert "aclexplode" in sql


def test_service_only_status_surface_reports_exact_security_predicates():
    sql = _sql(MIGRATION)
    assert "penta_security.penta_help_rls_baseline_status_v1()" in sql
    assert "pass_rls_deny_by_default_baseline" in sql
    assert "rls_enabled_count" in sql
    assert "force_rls_count" in sql
    assert "policy_count" in sql
    assert "end_user_direct_grant_count" in sql
    assert "role_semantics_ok" in sql
    assert "revoke all on function penta_security.penta_help_rls_baseline_status_v1() from public, anon, authenticated;" in sql
    assert "grant execute on function penta_security.penta_help_rls_baseline_status_v1() to service_role;" in sql


def test_rollback_is_fail_closed_against_successor_access_control_state():
    sql = _sql(ROLLBACK)
    assert "rollback_refused_successor_policy" in sql
    assert "rollback_refused_force_rls_successor" in sql
    assert "rollback_refused_end_user_grant" in sql
    assert "aclexplode" in sql
    for target in TARGETS:
        assert f"alter table {target} disable row level security;" in sql


def test_source_does_not_create_authority_or_force_rls():
    sql = _sql(MIGRATION)
    forbidden = (
        "create role ",
        "alter role ",
        "grant service_role to",
        "grant authenticated to",
        "grant anon to",
        "force row level security;",
    )
    for token in forbidden:
        assert token not in sql
