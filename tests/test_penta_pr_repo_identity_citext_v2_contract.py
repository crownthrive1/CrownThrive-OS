from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/20260901210200_penta_pr_repo_identity_citext_v2.sql"
)
ROLLBACK = Path(
    "supabase/rollback/20260901210200_penta_pr_repo_identity_citext_v2_rollback.sql"
)


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_migration_contracts_case_insensitive_repo_identity_at_storage_boundary():
    sql = _normalized(MIGRATION)
    assert "create extension if not exists citext with schema extensions" in sql
    assert "alter column repo type extensions.citext" in sql
    assert "partition by lower(btrim(l.repo)), l.pr_number" in sql
    assert "penta_pr.lifecycle_identity_alias_archive_v2" in sql
    assert "to_jsonb(aliases) - 'identity_rank'" in sql
    assert "penta_pr_case_identity_duplicate_remaining" in sql


def test_migration_preserves_alias_history_before_removal_and_creates_no_external_authority():
    sql = _normalized(MIGRATION)
    archive_pos = sql.index("insert into penta_pr.lifecycle_identity_alias_archive_v2")
    delete_pos = sql.index("delete from penta_pr.lifecycle")
    alter_pos = sql.index("alter table penta_pr.lifecycle alter column repo type extensions.citext")
    assert archive_pos < delete_pos < alter_pos
    assert "revoke all on table penta_pr.lifecycle_identity_alias_archive_v2 from public, anon, authenticated" in sql
    assert "grant execute" not in sql
    assert "grant all" not in sql
    assert "provider mutation" not in sql


def test_preflight_refuses_unreviewed_fk_topology_change():
    sql = _normalized(MIGRATION)
    assert "contype = 'f'" in sql
    assert "penta_pr_lifecycle_fk_topology_changed" in sql
    assert "penta_pr_lifecycle_missing" in sql


def test_rollback_restores_text_semantics_and_exact_archived_rows_without_dropping_custody():
    sql = _normalized(ROLLBACK)
    assert "fail-closed recovery" in sql
    assert "alter column repo type text" in sql
    assert "jsonb_populate_record(null::penta_pr.lifecycle, a.row_snapshot)" in sql
    assert "a.alias_row_id" in sql
    assert "rollback_refuses_missing_penta_pr_identity_custody" in sql
    assert "drop table penta_pr.lifecycle_identity_alias_archive_v2" not in sql
    assert "grant execute" not in sql
