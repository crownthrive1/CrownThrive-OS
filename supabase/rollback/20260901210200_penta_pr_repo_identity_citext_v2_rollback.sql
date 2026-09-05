-- Fail-closed recovery for 20260901210200_penta_pr_repo_identity_citext_v2.
-- Restores TEXT comparison semantics and rehydrates every archived case-alias row.
-- The archive is retained as evidence; no provider state or external authority changes.

begin;

-- Refuse recovery if custody or the two reviewed direct read-model dependencies drift.
do $preflight$
declare
  v_view_deps text[];
  v_bad_view_contract integer;
begin
  if to_regclass('penta_pr.lifecycle') is null
     or to_regclass('penta_pr.lifecycle_identity_alias_archive_v2') is null then
    raise exception 'rollback_refuses_missing_penta_pr_identity_custody';
  end if;

  select coalesce(array_agg(format('%I.%I', n.nspname, c.relname) order by n.nspname, c.relname), array[]::text[])
    into v_view_deps
  from pg_attribute a
  join pg_depend d
    on d.refobjid = a.attrelid
   and d.refobjsubid = a.attnum
   and d.classid = 'pg_rewrite'::regclass
  join pg_rewrite r on r.oid = d.objid
  join pg_class c on c.oid = r.ev_class
  join pg_namespace n on n.oid = c.relnamespace
  where a.attrelid = 'penta_pr.lifecycle'::regclass
    and a.attname = 'repo'
    and not a.attisdropped
    and c.relkind = 'v';

  if v_view_deps <> array[
       'penta_pr.current_zero_delta_candidates_v3',
       'penta_runtime.current_vergence_repairs_v3'
     ]::text[] then
    raise exception 'rollback_refuses_repo_view_dependency_topology_changed:%', v_view_deps;
  end if;

  select count(*) into v_bad_view_contract
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where (n.nspname, c.relname) in (
      ('penta_pr', 'current_zero_delta_candidates_v3'),
      ('penta_runtime', 'current_vergence_repairs_v3')
    )
    and (pg_get_userbyid(c.relowner) <> 'postgres' or c.relacl is not null or c.reloptions is not null);

  if v_bad_view_contract <> 0 then
    raise exception 'rollback_refuses_repo_view_security_contract_changed:%', v_bad_view_contract;
  end if;
end
$preflight$;

-- PostgreSQL cannot ALTER the lifecycle repo type while these views depend on it.
-- Drop only the exact reviewed read models; any new downstream dependency fails closed.
drop view penta_pr.current_zero_delta_candidates_v3;
drop view penta_runtime.current_vergence_repairs_v3;

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

-- Restore the pre-migration read models and their TEXT comparison semantics. CREATE
-- VIEW restores the same owner-only NULL ACL that existed before the forward migration;
-- no explicit REVOKE is issued because that would materialize a different relacl.
create view penta_pr.current_zero_delta_candidates_v3 as
select
  l.repo,
  l.pr_number,
  l.head_sha,
  q.execution_id,
  q.finding_id,
  q.updated_at as verified_at,
  q.receipt
from penta_pr.lifecycle l
join lateral (
  select q_1.*
  from penta_runtime.remediation_execution_queue_v1 q_1
  where q_1.pr_number = l.pr_number
    and q_1.state = 'verified'::text
    and q_1.head_sha = l.head_sha
    and coalesce((q_1.receipt ->> 'no_code_delta'::text)::boolean, false) = true
  order by q_1.updated_at desc
  limit 1
) q on true
where l.terminal_state is null;

create view penta_runtime.current_vergence_repairs_v3 as
select
  v.repair_id,
  v.job_id,
  v.repository_full_name,
  v.pr_number,
  v.head_sha,
  v.disposition,
  v.state,
  v.factory_backlog_id,
  v.evidence,
  v.created_at,
  v.updated_at
from penta_runtime.vergence_repairs_v1 v
join penta_pr.lifecycle l
  on l.repo = v.repository_full_name
 and l.pr_number = v.pr_number
 and l.head_sha = v.head_sha
where l.terminal_state is null;

-- Exact rollback postcondition: repository identity column is TEXT; custody remains
-- append-only and both reviewed read models are restored with the prior TEXT/ACL contract.
do $verify$
declare
  v_repo_view_type text;
  v_bad_view_contract integer;
begin
  if format_type(
       (select atttypid from pg_attribute
        where attrelid='penta_pr.lifecycle'::regclass and attname='repo' and not attisdropped),
       null
     ) <> 'text' then
    raise exception 'rollback_refuses_non_text_repo_identity';
  end if;

  if to_regclass('penta_pr.current_zero_delta_candidates_v3') is null
     or to_regclass('penta_runtime.current_vergence_repairs_v3') is null then
    raise exception 'rollback_refuses_dependent_view_recreation_missing';
  end if;

  select format_type(a.atttypid, a.atttypmod)
    into v_repo_view_type
  from pg_attribute a
  where a.attrelid = 'penta_pr.current_zero_delta_candidates_v3'::regclass
    and a.attname = 'repo'
    and not a.attisdropped;

  if v_repo_view_type <> 'text' then
    raise exception 'rollback_refuses_zero_delta_repo_contract_changed:%', v_repo_view_type;
  end if;

  select count(*) into v_bad_view_contract
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where (n.nspname, c.relname) in (
      ('penta_pr', 'current_zero_delta_candidates_v3'),
      ('penta_runtime', 'current_vergence_repairs_v3')
    )
    and (pg_get_userbyid(c.relowner) <> 'postgres' or c.relacl is not null or c.reloptions is not null);

  if v_bad_view_contract <> 0 then
    raise exception 'rollback_refuses_repo_view_security_contract_not_preserved:%', v_bad_view_contract;
  end if;
end
$verify$;

commit;
