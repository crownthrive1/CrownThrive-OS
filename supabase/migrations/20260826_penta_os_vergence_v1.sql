-- CrownThrive-OS / PentaVergence v1
-- Canonical, idempotent convergence runtime for CrownThrive OS.
-- This migration is additive and fail-closed. It does not delete repositories,
-- force-push branches, manufacture authority, or infer provider deployment state.

create schema if not exists penta_runtime;

create table if not exists penta_runtime.repository_registry_v1 (
  repository_full_name text primary key,
  canonical_role text not null,
  enabled boolean not null default true,
  mutation_policy text not null default 'governed',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table penta_runtime.repository_registry_v1 enable row level security;
alter table penta_runtime.repository_registry_v1 force row level security;
revoke all on penta_runtime.repository_registry_v1 from public, anon, authenticated;
grant select, insert, update, delete on penta_runtime.repository_registry_v1 to service_role;

insert into penta_runtime.repository_registry_v1(
  repository_full_name, canonical_role, mutation_policy, metadata
) values
  ('crownthrive1/CrownThrive-OS', 'PentaOS institutional source and PentaDocs', 'governed', jsonb_build_object('canonical', true)),
  ('crownthrive1/CrownThrive-CIE', 'CIE child framework repository', 'governed', '{}'::jsonb),
  ('crownthrive1/chlom-protocol', 'CHLOM protocol child repository', 'governed', '{}'::jsonb)
on conflict(repository_full_name) do update set
  canonical_role = excluded.canonical_role,
  mutation_policy = excluded.mutation_policy,
  metadata = penta_runtime.repository_registry_v1.metadata || excluded.metadata,
  enabled = true,
  updated_at = now();

create table if not exists penta_runtime.vergence_jobs_v1 (
  job_id uuid primary key default gen_random_uuid(),
  cycle_key text not null,
  repository_full_name text not null references penta_runtime.repository_registry_v1(repository_full_name),
  mode text not null check (mode in ('continuity', 'deep', 'manual')),
  state text not null default 'queued' check (state in ('queued', 'claimed', 'completed', 'failed')),
  request jsonb not null default '{}'::jsonb,
  result jsonb,
  worker_run_id text,
  available_at timestamptz not null default now(),
  claimed_at timestamptz,
  completed_at timestamptz,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(cycle_key, repository_full_name)
);
create index if not exists vergence_jobs_v1_claim_idx
  on penta_runtime.vergence_jobs_v1(repository_full_name, state, available_at, created_at);
alter table penta_runtime.vergence_jobs_v1 enable row level security;
alter table penta_runtime.vergence_jobs_v1 force row level security;
revoke all on penta_runtime.vergence_jobs_v1 from public, anon, authenticated;
grant select, insert, update, delete on penta_runtime.vergence_jobs_v1 to service_role;

create table if not exists penta_runtime.vergence_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  job_id uuid not null references penta_runtime.vergence_jobs_v1(job_id) on delete cascade,
  repository_full_name text not null,
  mode text not null,
  disposition text not null,
  report jsonb not null,
  evidence_sha256 text,
  created_at timestamptz not null default now()
);
alter table penta_runtime.vergence_receipts_v1 enable row level security;
alter table penta_runtime.vergence_receipts_v1 force row level security;
revoke all on penta_runtime.vergence_receipts_v1 from public, anon, authenticated;
grant select, insert on penta_runtime.vergence_receipts_v1 to service_role;

create or replace function penta_runtime.penta_vergence_enqueue_v1(p_mode text default 'continuity')
returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_temp
as $$
declare
  v_mode text := lower(coalesce(p_mode, 'continuity'));
  v_cycle text;
  v_count integer := 0;
begin
  if v_mode not in ('continuity', 'deep', 'manual') then
    raise exception 'unsupported PentaVergence mode: %', v_mode;
  end if;

  if v_mode = 'deep' then
    v_cycle := 'deep:' || to_char(timezone('America/New_York', now()), 'YYYY-MM-DD');
  elsif v_mode = 'continuity' then
    v_cycle := 'continuity:' || floor(extract(epoch from now()) / 14400)::bigint::text;
  else
    v_cycle := 'manual:' || to_char(now(), 'YYYYMMDDHH24MISSMS');
  end if;

  insert into penta_runtime.vergence_jobs_v1(cycle_key, repository_full_name, mode, request)
  select
    v_cycle,
    r.repository_full_name,
    v_mode,
    jsonb_build_object(
      'contract', 'ct.penta.vergence.request.v1',
      'source', 'CrownThrive-OS',
      'mode', v_mode,
      'requested_at', now()
    )
  from penta_runtime.repository_registry_v1 r
  where r.enabled
  on conflict(cycle_key, repository_full_name) do nothing;

  get diagnostics v_count = row_count;
  return jsonb_build_object(
    'contract', 'ct.penta.vergence.enqueue.v1',
    'cycle_key', v_cycle,
    'mode', v_mode,
    'jobs_created', v_count,
    'scheduled_at', now()
  );
end;
$$;
revoke all on function penta_runtime.penta_vergence_enqueue_v1(text) from public, anon, authenticated;
grant execute on function penta_runtime.penta_vergence_enqueue_v1(text) to service_role;

create or replace function penta_runtime.penta_vergence_deep_gate_v1()
returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_temp
as $$
declare
  v_local timestamp := timezone('America/New_York', now());
begin
  if extract(hour from v_local)::integer <> 23 then
    return jsonb_build_object(
      'contract', 'ct.penta.vergence.deep-gate.v1',
      'result', 'NOOP_OUTSIDE_23_LOCAL',
      'timezone', 'America/New_York',
      'local_time', v_local
    );
  end if;
  return penta_runtime.penta_vergence_enqueue_v1('deep');
end;
$$;
revoke all on function penta_runtime.penta_vergence_deep_gate_v1() from public, anon, authenticated;
grant execute on function penta_runtime.penta_vergence_deep_gate_v1() to service_role;

create or replace function penta_runtime.penta_vergence_claim_v1(
  p_repository text,
  p_worker_run_id text default null
)
returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_temp
as $$
declare
  v_job penta_runtime.vergence_jobs_v1%rowtype;
begin
  with candidate as (
    select job_id
    from penta_runtime.vergence_jobs_v1
    where repository_full_name = p_repository
      and state = 'queued'
      and available_at <= now()
    order by
      case mode when 'deep' then 0 when 'manual' then 1 else 2 end,
      created_at,
      job_id
    for update skip locked
    limit 1
  )
  update penta_runtime.vergence_jobs_v1 j
  set state = 'claimed',
      claimed_at = now(),
      worker_run_id = p_worker_run_id,
      updated_at = now()
  from candidate c
  where j.job_id = c.job_id
  returning j.* into v_job;

  if v_job.job_id is null then
    return jsonb_build_object('claimed', false, 'repository', p_repository);
  end if;

  return jsonb_build_object(
    'claimed', true,
    'job_id', v_job.job_id,
    'cycle_key', v_job.cycle_key,
    'repository', v_job.repository_full_name,
    'mode', v_job.mode,
    'request', v_job.request
  );
end;
$$;
revoke all on function penta_runtime.penta_vergence_claim_v1(text, text) from public, anon, authenticated;
grant execute on function penta_runtime.penta_vergence_claim_v1(text, text) to service_role;

create or replace function penta_runtime.penta_vergence_complete_v1(
  p_job_id uuid,
  p_report jsonb,
  p_evidence_sha256 text default null
)
returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_temp
as $$
declare
  v_job penta_runtime.vergence_jobs_v1%rowtype;
  v_disposition text;
begin
  select * into v_job
  from penta_runtime.vergence_jobs_v1
  where job_id = p_job_id
  for update;

  if v_job.job_id is null then
    raise exception 'PentaVergence job not found';
  end if;
  if v_job.state <> 'claimed' then
    raise exception 'PentaVergence job not claimed: %', v_job.state;
  end if;

  v_disposition := case
    when coalesce((p_report ->> 'mutations')::integer, 0) > 0 then 'MUTATED'
    else 'OBSERVED'
  end;

  update penta_runtime.vergence_jobs_v1
  set state = 'completed',
      result = p_report,
      error = null,
      completed_at = now(),
      updated_at = now()
  where job_id = p_job_id;

  insert into penta_runtime.vergence_receipts_v1(
    job_id, repository_full_name, mode, disposition, report, evidence_sha256
  ) values (
    p_job_id, v_job.repository_full_name, v_job.mode, v_disposition, p_report, p_evidence_sha256
  );

  return jsonb_build_object(
    'contract', 'ct.penta.vergence.complete.v1',
    'job_id', p_job_id,
    'state', 'completed',
    'disposition', v_disposition
  );
end;
$$;
revoke all on function penta_runtime.penta_vergence_complete_v1(uuid, jsonb, text) from public, anon, authenticated;
grant execute on function penta_runtime.penta_vergence_complete_v1(uuid, jsonb, text) to service_role;

create or replace function penta_runtime.penta_vergence_release_v1(
  p_job_id uuid,
  p_error text default 'worker_failed'
)
returns jsonb
language plpgsql
security definer
set search_path = penta_runtime, pg_temp
as $$
declare
  v_released boolean;
begin
  update penta_runtime.vergence_jobs_v1
  set state = 'queued',
      claimed_at = null,
      worker_run_id = null,
      available_at = now() + interval '15 minutes',
      error = left(coalesce(p_error, 'worker_failed'), 1000),
      updated_at = now()
  where job_id = p_job_id
    and state = 'claimed';

  v_released := found;
  return jsonb_build_object(
    'contract', 'ct.penta.vergence.release.v1',
    'job_id', p_job_id,
    'released', v_released
  );
end;
$$;
revoke all on function penta_runtime.penta_vergence_release_v1(uuid, text) from public, anon, authenticated;
grant execute on function penta_runtime.penta_vergence_release_v1(uuid, text) to service_role;

create or replace function penta_runtime.penta_vergence_status_v1()
returns jsonb
language sql
stable
security definer
set search_path = penta_runtime, pg_temp
as $$
  select jsonb_build_object(
    'contract', 'ct.penta.vergence.status.v1',
    'queued', (select count(*) from penta_runtime.vergence_jobs_v1 where state = 'queued'),
    'claimed', (select count(*) from penta_runtime.vergence_jobs_v1 where state = 'claimed'),
    'completed', (select count(*) from penta_runtime.vergence_jobs_v1 where state = 'completed'),
    'failed', (select count(*) from penta_runtime.vergence_jobs_v1 where state = 'failed'),
    'last_completed_at', (select max(completed_at) from penta_runtime.vergence_jobs_v1 where state = 'completed'),
    'cadence', jsonb_build_object(
      'continuity', 'every_4_hours',
      'deep', '23:00 America/New_York'
    ),
    'generated_at', now()
  );
$$;
revoke all on function penta_runtime.penta_vergence_status_v1() from public, anon, authenticated;
grant execute on function penta_runtime.penta_vergence_status_v1() to service_role;

-- PentaBase owns substantive cadence. Workers may poll more often but must not
-- perform convergence work unless a queued job exists.
do $$
begin
  perform cron.unschedule(jobid)
  from cron.job
  where jobname in (
    'penta-vergence-continuity-4h-v1',
    'penta-vergence-deep-local-gate-v1'
  );
exception
  when undefined_table then null;
end;
$$;

select cron.schedule(
  'penta-vergence-continuity-4h-v1',
  '23 */4 * * *',
  $$select penta_runtime.penta_vergence_enqueue_v1('continuity');$$
);

select cron.schedule(
  'penta-vergence-deep-local-gate-v1',
  '0 * * * *',
  $$select penta_runtime.penta_vergence_deep_gate_v1();$$
);
