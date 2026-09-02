from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260902192500_penta_pr_stale_restack_two_phase_v2.sql"
)
ROLLBACK = (
    ROOT
    / "supabase"
    / "rollback"
    / "20260902192500_penta_pr_stale_restack_two_phase_v2_rollback.sql"
)
SQL_ACCEPTANCE = ROOT / "tests" / "sql" / "penta_pr_stale_restack_two_phase_v2.sql"


def migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_initial_stale_classification_is_two_phase() -> None:
    sql = migration_text()
    assert "'version','2.0.1'" in sql
    assert "v_has_successor<>v_has_handoff" in sql
    assert "stale_restack_successor_and_handoff_must_be_supplied_together" in sql
    assert "not v_has_successor and not v_has_handoff" in sql
    assert "restack_pair_complete" in sql
    assert "stale_predecessor_requires_successor_or_handoff_before_close" not in sql


def test_stale_terminalization_requires_complete_pair() -> None:
    sql = migration_text()
    assert sql.count("stale_predecessor_terminalization_requires_successor_and_handoff") >= 2
    assert "metadata->>'successor_pr_number'" in sql
    assert "metadata->>'handoff_receipt_ref'" in sql
    assert "successor_pr_number AND handoff_receipt_ref required before predecessor terminalization" in sql


def test_exact_identity_and_authority_boundaries_remain_fail_closed() -> None:
    sql = migration_text()
    assert "exact_pr_identity_required" in sql
    assert "HOLD_PR_NOT_TRACKED_OR_HEAD_MISMATCH" in sql
    assert "service_role_required" in sql
    assert sql.count("'authority_created',false") >= 5
    assert "security definer" in sql.lower()
    assert "set search_path to 'pg_catalog', 'penta_pr'" in sql.lower()


def test_transactional_acceptance_and_rollback_are_present() -> None:
    acceptance = SQL_ACCEPTANCE.read_text(encoding="utf-8").lower()
    rollback = ROLLBACK.read_text(encoding="utf-8")
    assert acceptance.startswith("-- ct.penta.pr-terminalization-policy.v2")
    assert "begin;" in acceptance
    assert acceptance.rstrip().endswith("rollback;")
    assert "TEST_FAIL_SUCCESSOR_ONLY_ACCEPTED" in SQL_ACCEPTANCE.read_text(encoding="utf-8")
    assert "TEST_FAIL_PROVIDER_TERMINAL_BEFORE_PAIR" in SQL_ACCEPTANCE.read_text(encoding="utf-8")
    assert "'version','2.0.0'" in rollback
    assert "stale_predecessor_requires_successor_or_handoff_before_close" in rollback
