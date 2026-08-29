-- Adopt the current provider-observed active pg_cron schedule into the monotonic
-- desired-state registry without changing any job's behavior or authority.
-- Future removal or modification requires an explicit newer generation.

create table if not exists integration_control.scheduler_baseline_receipts_v2(
  receipt_id uuid primary key default gen_random_uuid(),
  baseline_key text not null unique,
  generation bigint not null,
  active_job_count integer not null,
  adopted_job_count integer not null,
  excluded_job_count integer not null,
  drift_count integer not null,
  baseline_sha256 text not null,
  metadata jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

alter table integration_control.scheduler_baseline_receipts_v2 enable row level security;
revoke all on integration_control.scheduler_baseline_receipts_v2 from public,anon,authenticated;
grant select,insert on integration_control.scheduler_baseline_receipts_v2 to service_role;
drop policy if exists scheduler_baseline_receipts_select_v2 on integration_control.scheduler_baseline_receipts_v2;
create policy scheduler_baseline_receipts_select_v2
  on integration_control.scheduler_baseline_receipts_v2
  for select to service_role using(true);
drop policy if exists scheduler_baseline_receipts_insert_v2 on integration_control.scheduler_baseline_receipts_v2;
create policy scheduler_baseline_receipts_insert_v2
  on integration_control.scheduler_baseline_receipts_v2
  for insert to service_role with check(true);

create or replace function integration_control.scheduler_baseline_receipts_immutable_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,integration_control
as $$
begin
  raise exception 'scheduler_baseline_receipts_v2 is append-only';
end $$;

revoke all on function integration_control.scheduler_baseline_receipts_immutable_v2() from public,anon,authenticated;
grant execute on function integration_control.scheduler_baseline_receipts_immutable_v2() to service_role;
drop trigger if exists scheduler_baseline_receipts_immutable_v2 on integration_control.scheduler_baseline_receipts_v2;
create trigger scheduler_baseline_receipts_immutable_v2
before update or delete on integration_control.scheduler_baseline_receipts_v2
for each row execute function integration_control.scheduler_baseline_receipts_immutable_v2();

do $adopt$
declare
  v_job record;
  v_generation bigint:=2026082905;
  v_adopted integer:=0;
  v_active integer:=0;
  v_excluded integer:=0;
  v_drift integer:=0;
  v_baseline jsonb;
  v_digest text;
begin
  select count(*) into v_active from cron.job where active;

  for v_job in
    select jobname,schedule,command,database,username
    from cron.job
    where active
      and jobname<>'ct-scheduler-permanence-canary-v2'
    order by jobname
  loop
    perform integration_control.scheduler_desired_job_upsert_v2(
      v_job.jobname,
      v_job.schedule,
      v_job.command,
      v_generation,
      'ct.scheduler.adopted-production-baseline.v2',
      jsonb_build_object(
        'adopted_from_existing_active_cron',true,
        'behavior_changed',false,
        'authority_created',false,
        'database',v_job.database,
        'username',v_job.username,
        'removal_requires_newer_generation',true,
        'rollback_policy','monotonic'
      )
    );
    v_adopted:=v_adopted+1;
  end loop;

  select count(*) into v_excluded
  from cron.job
  where active and jobname='ct-scheduler-permanence-canary-v2';

  perform cron.unschedule(jobid)
  from cron.job
  where jobname='ct-scheduler-permanence-canary-v2';

  update integration_control.scheduler_desired_jobs_v2
  set active=false,
      allow_auto_restore=false,
      generation=greatest(generation,2026082906),
      source_ref='ct.pentaself.scheduler-permanence.v2.canary.retired',
      metadata=metadata||jsonb_build_object(
        'retired_at',now(),
        'reason','certification_canary_complete',
        'restore_forbidden',true
      ),
      updated_at=now()
  where jobname='ct-scheduler-permanence-canary-v2';

  perform integration_control.scheduler_permanence_reconcile_v2();

  select count(*) into v_drift
  from cron.job j
  join integration_control.scheduler_desired_jobs_v2 d using(jobname)
  where d.active and d.allow_auto_restore
    and (j.schedule<>d.schedule or j.command<>d.command or not j.active);

  select jsonb_agg(jsonb_build_object(
    'jobname',j.jobname,'schedule',j.schedule,
    'command',j.command,'active',j.active
  ) order by j.jobname)
  into v_baseline
  from cron.job j
  where j.active;

  v_digest:=encode(extensions.digest(
    convert_to(coalesce(v_baseline,'[]'::jsonb)::text,'UTF8'),'sha256'
  ),'hex');

  insert into integration_control.scheduler_baseline_receipts_v2(
    baseline_key,generation,active_job_count,adopted_job_count,
    excluded_job_count,drift_count,baseline_sha256,metadata
  ) values(
    'ct.scheduler.production-baseline.20260829.v2',
    v_generation,
    (select count(*) from cron.job where active),
    v_adopted,v_excluded,v_drift,v_digest,
    jsonb_build_object(
      'adopted_from_provider_truth',true,
      'behavior_changed',false,
      'authority_created',false,
      'temporary_canary_retired',true,
      'removal_requires_newer_generation',true
    )
  ) on conflict(baseline_key) do nothing;
end
$adopt$;

select integration_control.scheduler_permanence_reconcile_v2();
