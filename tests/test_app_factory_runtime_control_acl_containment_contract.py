from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260901182032_app_factory_runtime_control_acl_containment_v1.sql"
)
ROLLBACK = Path(
    "supabase/rollback/20260901182032_app_factory_runtime_control_acl_containment_v1_rollback.sql"
)

TARGETS = {
    "public.app_factory_android_closeout_dispatch(text)": "73fdbfd341ed5ed84b57e982b67c9ada53025d62cc5fd5b7ee164c699f3ac97a",
    "public.app_factory_dcv_control_dispatch(text)": "1f2e3d9bebe6732efc7230333e128bb14fdbd84d6cd775b66bd52fb8fe105731",
    "public.app_factory_root_route_dispatch()": "0d62beb998f4b7de4874c1ac6d4bb2dbcfc73214d8513eb4ed0a0f7e96e0cc45",
    "public.app_factory_runtime_evidence_dispatch(text)": "7c01fd5730c13997ec25c1d0569c452a7731d1b8fe9c504cf5e880dbef16bdc7",
}


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_contracts_exact_runtime_control_dispatch_cohort():
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
    assert "rollback_refuses_changed_app_factory_runtime_control_rpc" in sql
    assert "to service_role" in sql
    assert "to anon" not in sql
    assert "to authenticated" not in sql
    assert "to public" not in sql
    assert "anon_execute_present" in sql
    assert "authenticated_execute_present" in sql
    for signature, expected_sha in TARGETS.items():
        assert signature in sql
        assert expected_sha in sql
