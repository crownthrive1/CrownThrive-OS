-- PentaPR lifecycle v2 repository identity normalization.
-- Root cause: provider-truth writers store lower(repo) while GitHub reconciliation
-- stores the provider's canonical casing. The text UNIQUE(repo, pr_number) therefore
-- permits multiple lifecycle rows for one GitHub PR and can let stale/terminal aliases
-- outrank current provider truth. This migration contracts identity ambiguity without
-- granting provider, D3, money, rights, credential, or vote authority.

begin;

create extension if not exists citext with schema extensions;

-- Fail closed if a future schema introduces FK or dependent-view coupling that this
-- bounded type conversion has not been reviewed against. PostgreSQL refuses ALTER
-- COLUMN TYPE while dependent views exist, so the two current read-only views are
-- explicitly preserved and recreated below with their external TEXT contract intact.
do $preflight$
declare
  v_fk_count integer;
  v_view_deps text[];
  v_bad_view_contract integer;
begin
  if to_regclass('penta_pr.lifecycle') is null then
    raise exception 'penta_pr_lifecycle_missing';
  end if;

  select count(*) into v_fk_count
  from pg_constraint
  where contype = 'f'
    and (conrelid = 'penta_pr.lifecycle'::regclass
         or confrelid = 'penta_pr.lifecycle'::regclass);

  if v_fk_count <> 0 then
    raise exception 'penta_pr_lifecycle_fk_topology_changed:%', v_fk_count;
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
    raise exception 'penta_pr_repo_view_dependency_topology_changed:%', v_view_deps;
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
    raise exception 'penta_pr_repo_view_security_contract_changed:%', v_bad_view_contract;
  end if;
end
$preflight$;

create table if not exists penta_pr.lifecycle_identity_alias_archive_v2 (
  alias_row_id uuid primary key,
  canonical_identity text not null,
  archive_batch text not null,
  row_snapshot jsonb not null,
  archived_at timestamptz not null default clock_timestamp()
);

alter table penta_pr.lifecycle_identity_alias_archive_v2 enable row level security;
revoke all on table penta_pr.lifecycle_identity_alias_archive_v2 from public, anon, authenticated;

-- Snapshot duplicate-group current truth before any row can be removed. This is used both
-- to fail closed on ambiguous active heads and to prove that deduplication did not terminalize
-- or rewind an active lifecycle row.
create temporary table penta_pr_identity_preflight_v2 on commit drop as
select
  lower(btrim(l.repo)) as canonical_repo,
  l.pr_number,
  count(*) as row_count,
  count(*) filter (where l.terminal_state is null) as active_rows,
  count(distinct l.head_sha) filter (
    where l.terminal_state is null and l.head_sha is not null
  ) as active_head_count,
  min(l.head_sha) filter (
    where l.terminal_state is null and l.head_sha is not null
  ) as active_head_sha,
  count(distinct nullif(coalesce(l.metadata,'{}'::jsonb)->>'classification','')) filter (
    where l.terminal_state is null
  ) as active_classification_count,
  count(distinct nullif(coalesce(l.metadata,'{}'::jsonb)->>'disposition','')) filter (
    where l.terminal_state is null
  ) as active_disposition_count,
  max(l.provider_updated_at) filter (where l.terminal_state is null) as latest_active_provider_updated_at,
  max(l.last_observed_at) filter (where l.terminal_state is null) as latest_active_observed_at
from penta_pr.lifecycle l
group by lower(btrim(l.repo)), l.pr_number
having count(*) > 1;

do $identity_conflict_preflight$
declare
  v_active_head_conflicts integer;
  v_active_classification_conflicts integer;
  v_active_disposition_conflicts integer;
begin
  select count(*) into v_active_head_conflicts
  from penta_pr_identity_preflight_v2
  where active_rows > 1 and active_head_count > 1;

  if v_active_head_conflicts <> 0 then
    raise exception 'penta_pr_active_alias_head_conflict:%', v_active_head_conflicts;
  end if;

  select count(*) into v_active_classification_conflicts
  from penta_pr_identity_preflight_v2
  where active_rows > 1 and active_classification_count > 1;

  if v_active_classification_conflicts <> 0 then
    raise exception 'penta_pr_active_alias_classification_conflict:%', v_active_classification_conflicts;
  end if;

  select count(*) into v_active_disposition_conflicts
  from penta_pr_identity_preflight_v2
  where active_rows > 1 and active_disposition_count > 1;

  if v_active_disposition_conflicts <> 0 then
    raise exception 'penta_pr_active_alias_disposition_conflict:%', v_active_disposition_conflicts;
  end if;
end
$identity_conflict_preflight$;

-- Preserve every case-alias row before deduplication. Current active truth always outranks
-- terminal history. Within the same lifecycle class, freshest provider/readback truth outranks
-- spelling/classification preferences. This prevents an active canonical alias from collapsing
-- to a CLOSED/terminal row merely because the terminal row is lower-case or classified.
with ranked as (
  select
    l.*,
    row_number() over (
      partition by lower(btrim(l.repo)), l.pr_number
      order by
        (l.terminal_state is null) desc,
        l.provider_updated_at desc nulls last,
        l.last_observed_at desc nulls last,
        ((coalesce(l.metadata, '{}'::jsonb) ->> 'classification') is not null) desc,
        (l.repo = lower(btrim(l.repo))) desc,
        l.first_seen_at asc,
        l.id asc
    ) as identity_rank
  from penta_pr.lifecycle l
), aliases as (
  select * from ranked where identity_rank > 1
)
insert into penta_pr.lifecycle_identity_alias_archive_v2(
  alias_row_id, canonical_identity, archive_batch, row_snapshot
)
select
  id,
  lower(btrim(repo)) || '#' || pr_number::text,
  '20260901210200_penta_pr_repo_identity_citext_v2',
  to_jsonb(aliases) - 'identity_rank'
from aliases
on conflict (alias_row_id) do nothing;

-- Remove only aliases whose complete original row was preserved by this exact batch.
delete from penta_pr.lifecycle l
using penta_pr.lifecycle_identity_alias_archive_v2 a
where a.archive_batch = '20260901210200_penta_pr_repo_identity_citext_v2'
  and a.alias_row_id = l.id;

-- Prove that no duplicate group containing active provider truth collapsed to terminal or
-- changed its uniquely known active head/freshness before changing the storage type.
do $survivor_verify$
declare
  v_terminalized_active integer;
  v_active_head_rewound integer;
  v_active_provider_rewound integer;
  v_active_observation_rewound integer;
begin
  select count(*) into v_terminalized_active
  from penta_pr_identity_preflight_v2 p
  join penta_pr.lifecycle l
    on lower(btrim(l.repo)) = p.canonical_repo
   and l.pr_number = p.pr_number
  where p.active_rows > 0
    and l.terminal_state is not null;

  if v_terminalized_active <> 0 then
    raise exception 'penta_pr_active_alias_terminalized:%', v_terminalized_active;
  end if;

  select count(*) into v_active_head_rewound
  from penta_pr_identity_preflight_v2 p
  join penta_pr.lifecycle l
    on lower(btrim(l.repo)) = p.canonical_repo
   and l.pr_number = p.pr_number
  where p.active_rows > 0
    and p.active_head_count = 1
    and l.head_sha is distinct from p.active_head_sha;

  if v_active_head_rewound <> 0 then
    raise exception 'penta_pr_active_alias_head_changed:%', v_active_head_rewound;
  end if;

  select count(*) into v_active_provider_rewound
  from penta_pr_identity_preflight_v2 p
  join penta_pr.lifecycle l
    on lower(btrim(l.repo)) = p.canonical_repo
   and l.pr_number = p.pr_number
  where p.active_rows > 0
    and p.latest_active_provider_updated_at is not null
    and l.provider_updated_at is distinct from p.latest_active_provider_updated_at;

  if v_active_provider_rewound <> 0 then
    raise exception 'penta_pr_active_alias_provider_freshness_changed:%', v_active_provider_rewound;
  end if;

  select count(*) into v_active_observation_rewound
  from penta_pr_identity_preflight_v2 p
  join penta_pr.lifecycle l
    on lower(btrim(l.repo)) = p.canonical_repo
   and l.pr_number = p.pr_number
  where p.active_rows > 0
    and p.latest_active_provider_updated_at is null
    and p.latest_active_observed_at is not null
    and l.last_observed_at is distinct from p.latest_active_observed_at;

  if v_active_observation_rewound <> 0 then
    raise exception 'penta_pr_active_alias_observation_freshness_changed:%', v_active_observation_rewound;
  end if;
end
$survivor_verify$;

-- Preserve the two current direct read-model dependencies before the type conversion.
-- Their definitions are recreated immediately after ALTER TYPE. No downstream views
-- currently depend on either surface; any future dependency causes DROP VIEW to fail
-- closed rather than CASCADE through unknown consumers.
drop view penta_pr.current_zero_delta_candidates_v3;
drop view penta_runtime.current_vergence_repairs_v3;

-- Make repository identity comparisons and UNIQUE(repo, pr_number) case-insensitive.
alter table penta_pr.lifecycle
  alter column repo type extensions.citext
  using btrim(repo)::extensions.citext;

-- Recreate current read models with the same columns and least-privilege contract.
create view penta_pr.current_zero_delta_candidates_v3 as
select
  l.repo::text as repo,
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
  on l.repo = v.repository_full_name::extensions.citext
 and l.pr_number = v.pr_number
 and l.head_sha = v.head_sha
where l.terminal_state is null;

-- Exact postcondition: one row per case-insensitive repository/PR identity, both
-- dependent views remain present with their pre-migration TEXT-facing/ACL contract.
do $verify$
declare
  v_dupes integer;
  v_repo_view_type text;
  v_bad_view_contract integer;
begin
  select count(*) into v_dupes
  from (
    select lower(repo::text), pr_number
    from penta_pr.lifecycle
    group by lower(repo::text), pr_number
    having count(*) > 1
  ) q;

  if v_dupes <> 0 then
    raise exception 'penta_pr_case_identity_duplicate_remaining:%', v_dupes;
  end if;

  if format_type(
       (select atttypid from pg_attribute
        where attrelid='penta_pr.lifecycle'::regclass and attname='repo' and not attisdropped),
       null
     ) not in ('citext', 'extensions.citext') then
    raise exception 'penta_pr_repo_not_citext';
  end if;

  if to_regclass('penta_pr.current_zero_delta_candidates_v3') is null
     or to_regclass('penta_runtime.current_vergence_repairs_v3') is null then
    raise exception 'penta_pr_repo_dependent_view_recreation_missing';
  end if;

  select format_type(a.atttypid, a.atttypmod)
    into v_repo_view_type
  from pg_attribute a
  where a.attrelid = 'penta_pr.current_zero_delta_candidates_v3'::regclass
    and a.attname = 'repo'
    and not a.attisdropped;

  if v_repo_view_type <> 'text' then
    raise exception 'penta_pr_zero_delta_repo_contract_changed:%', v_repo_view_type;
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
    raise exception 'penta_pr_repo_view_security_contract_not_preserved:%', v_bad_view_contract;
  end if;
end
$verify$;

comment on table penta_pr.lifecycle_identity_alias_archive_v2 is
  'Lossless custody of case-variant PentaPR lifecycle rows collapsed by repository identity normalization v2. Historical evidence only; grants no runtime authority.';

commit;
