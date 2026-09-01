-- Fail-closed recovery for 20260901210200_penta_pr_repo_identity_citext_v2.
-- Restores TEXT comparison semantics and rehydrates every archived case-alias row.
-- The archive is retained as evidence; no provider state or external authority changes.

begin;

-- Refuse recovery if the custody table is missing.
do $preflight$
begin
  if to_regclass('penta_pr.lifecycle') is null
     or to_regclass('penta_pr.lifecycle_identity_alias_archive_v2') is null then
    raise exception 'rollback_refuses_missing_penta_pr_identity_custody';
  end if;
end
$preflight$;

alter table penta_pr.lifecycle
  alter column repo type text
  using repo::text;

-- Rehydrate only rows preserved by the exact migration batch. UUID identity is the
-- immutable restoration key. Different repository casing is again distinct under TEXT.
insert into penta_pr.lifecycle(
  id, repo, pr_number, head_sha, base_ref, first_seen_at, deadline_at,
  disposition, reason, stack_parent_pr, labels, mergeable, checks_state,
  terminal_state, terminal_at, metadata, last_observed_at, provider_updated_at
)
select
  x.id, x.repo, x.pr_number, x.head_sha, x.base_ref, x.first_seen_at, x.deadline_at,
  x.disposition, x.reason, x.stack_parent_pr, x.labels, x.mergeable, x.checks_state,
  x.terminal_state, x.terminal_at, x.metadata, x.last_observed_at, x.provider_updated_at
from penta_pr.lifecycle_identity_alias_archive_v2 a
cross join lateral jsonb_populate_record(null::penta_pr.lifecycle, a.row_snapshot) as x
where a.archive_batch = '20260901210200_penta_pr_repo_identity_citext_v2'
  and not exists (select 1 from penta_pr.lifecycle l where l.id = a.alias_row_id);

-- Exact rollback postcondition: repository identity column is TEXT. The archive remains
-- append-only custody and is intentionally not dropped.
do $verify$
begin
  if format_type(
       (select atttypid from pg_attribute
        where attrelid='penta_pr.lifecycle'::regclass and attname='repo' and not attisdropped),
       null
     ) <> 'text' then
    raise exception 'rollback_refuses_non_text_repo_identity';
  end if;
end
$verify$;

commit;
