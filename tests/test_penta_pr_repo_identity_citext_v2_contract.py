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


def test_active_truth_outranks_terminal_alias_and_provider_freshness_outranks_spelling():
    sql = _normalized(MIGRATION)
    ranking = sql.split("row_number() over", 1)[1].split("as identity_rank", 1)[0]
    assert "(l.terminal_state is null) desc" in ranking
    assert "l.provider_updated_at desc nulls last" in ranking
    assert ranking.index("(l.terminal_state is null) desc") < ranking.index("l.provider_updated_at desc nulls last")
    assert ranking.index("l.provider_updated_at desc nulls last") < ranking.index("(l.repo = lower(btrim(l.repo))) desc")


def test_conflicting_active_heads_and_semantics_fail_closed_before_delete():
    sql = _normalized(MIGRATION)
    assert "penta_pr_identity_preflight_v2" in sql
    assert "active_head_count" in sql
    assert "penta_pr_active_alias_head_conflict" in sql
    assert "penta_pr_active_alias_classification_conflict" in sql
    assert "penta_pr_active_alias_disposition_conflict" in sql
    preflight_pos = sql.index("penta_pr_active_alias_head_conflict")
    delete_pos = sql.index("delete from penta_pr.lifecycle")
    assert preflight_pos < delete_pos


def test_survivor_verification_prevents_active_terminalization_head_or_freshness_rewind():
    sql = _normalized(MIGRATION)
    assert "penta_pr_active_alias_terminalized" in sql
    assert "penta_pr_active_alias_head_changed" in sql
    assert "penta_pr_active_alias_provider_freshness_changed" in sql
    assert "penta_pr_active_alias_observation_freshness_changed" in sql
    survivor_verify_pos = sql.index("penta_pr_active_alias_terminalized")
    alter_pos = sql.index("alter table penta_pr.lifecycle alter column repo type extensions.citext")
    assert survivor_verify_pos < alter_pos


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


def test_preflight_refuses_unreviewed_fk_and_repo_view_dependency_topology_changes():
    sql = _normalized(MIGRATION)
    assert "contype = 'f'" in sql
    assert "penta_pr_lifecycle_fk_topology_changed" in sql
    assert "penta_pr_lifecycle_missing" in sql
    assert "penta_pr.current_zero_delta_candidates_v3" in sql
    assert "penta_runtime.current_vergence_repairs_v3" in sql
    assert "penta_pr_repo_view_dependency_topology_changed" in sql
    assert "penta_pr_repo_view_security_contract_changed" in sql


def test_forward_conversion_preserves_current_repo_dependent_views_and_text_facing_contract():
    sql = _normalized(MIGRATION)
    alter_pos = sql.index("alter table penta_pr.lifecycle alter column repo type extensions.citext")
    zero_drop = sql.index("drop view penta_pr.current_zero_delta_candidates_v3")
    vergence_drop = sql.index("drop view penta_runtime.current_vergence_repairs_v3")
    zero_create = sql.index("create view penta_pr.current_zero_delta_candidates_v3 as")
    vergence_create = sql.index("create view penta_runtime.current_vergence_repairs_v3 as")
    assert zero_drop < alter_pos
    assert vergence_drop < alter_pos
    assert alter_pos < zero_create
    assert alter_pos < vergence_create
    assert "l.repo::text as repo" in sql
    assert "l.repo = v.repository_full_name::extensions.citext" in sql
    assert "penta_pr_zero_delta_repo_contract_changed" in sql
    assert "penta_pr_repo_view_security_contract_not_preserved" in sql


def test_rollback_restores_text_semantics_and_exact_archived_rows_without_dropping_custody():
    sql = _normalized(ROLLBACK)
    assert "fail-closed recovery" in sql
    assert "alter column repo type text" in sql
    assert "jsonb_populate_record(null::penta_pr.lifecycle, a.row_snapshot)" in sql
    assert "a.alias_row_id" in sql
    assert "rollback_refuses_missing_penta_pr_identity_custody" in sql
    assert "drop table penta_pr.lifecycle_identity_alias_archive_v2" not in sql
    assert "grant execute" not in sql


def test_rollback_preserves_views_and_restores_original_text_join_semantics():
    sql = _normalized(ROLLBACK)
    alter_pos = sql.index("alter table penta_pr.lifecycle alter column repo type text")
    zero_drop = sql.index("drop view penta_pr.current_zero_delta_candidates_v3")
    vergence_drop = sql.index("drop view penta_runtime.current_vergence_repairs_v3")
    zero_create = sql.index("create view penta_pr.current_zero_delta_candidates_v3 as")
    vergence_create = sql.index("create view penta_runtime.current_vergence_repairs_v3 as")
    assert zero_drop < alter_pos
    assert vergence_drop < alter_pos
    assert alter_pos < zero_create
    assert alter_pos < vergence_create
    assert "on l.repo = v.repository_full_name and l.pr_number = v.pr_number" in sql
    assert "rollback_refuses_repo_view_dependency_topology_changed" in sql
    assert "rollback_refuses_repo_view_security_contract_not_preserved" in sql
