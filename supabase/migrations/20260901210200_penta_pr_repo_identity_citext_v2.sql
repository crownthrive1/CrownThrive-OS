-- PentaPR lifecycle v2 repository identity normalization.
-- Root cause: provider-truth writers store lower(repo) while GitHub reconciliation
-- stores the provider's canonical casing. The text UNIQUE(repo, pr_number) therefore
-- permits two active rows for one GitHub PR and can leave the fresh provider row
-- unclassified. This migration contracts identity ambiguity without granting any
-- provider, D3, money, rights, credential, or vote authority.

begin;

create extension if not exists citext with schema extensions;

-- Fail closed if a future schema introduces FK coupling that this bounded type
-- conversion has not been reviewed against.
do $preflight$
declare
  v_fk_count integer;
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

-- Preserve every case-alias row before deduplication. Survivor selection prefers an
-- already-classified row, then the lower-case spelling, then freshest provider truth.
with ranked as (
  select
    l.*,
    row_number() over (
      partition by lower(btrim(l.repo)), l.pr_number
      order by
        ((coalesce(l.metadata, '{}'::jsonb) ->> 'classification') is not null) desc,
        (l.repo = lower(btrim(l.repo))) desc,
        l.provider_updated_at desc nulls last,
        l.last_observed_at desc nulls last,
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

-- Make repository identity comparisons and UNIQUE(repo, pr_number) case-insensitive.
-- This fixes both reconciliation lookup and all future writers at the storage boundary.
alter table penta_pr.lifecycle
  alter column repo type extensions.citext
  using btrim(repo)::extensions.citext;

-- Exact postcondition: one row per case-insensitive repository/PR identity.
do $verify$
declare
  v_dupes integer;
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
end
$verify$;

comment on table penta_pr.lifecycle_identity_alias_archive_v2 is
  'Lossless custody of case-variant PentaPR lifecycle rows collapsed by repository identity normalization v2. Historical evidence only; grants no runtime authority.';

commit;
