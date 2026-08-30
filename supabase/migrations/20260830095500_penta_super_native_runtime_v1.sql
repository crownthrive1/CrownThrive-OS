-- PentaSuper native runtime v1
-- Native-primary supervision; ChatGPT automations remain fallback until readback proves this path.

create schema if not exists penta_runtime;

create table if not exists penta_runtime.penta_super_runs_v1 (
  run_id uuid primary key default gen_random_uuid(),
  execution_key text not null unique,
  cycle_id text not null,
  scheduled_bucket timestamptz not null,
  status text not null check (status in ('RUNNING','PASS','HOLD','FAILED')),
  preflight jsonb not null default '{}'::jsonb,
  observations jsonb not null default '{}'::jsonb,
  work_item_keys text[] not null default '{}'::text[],
  dail_event_id text,
  started_at timestamptz not null default clock_timestamp(),
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

alter table penta_runtime.penta_super_runs_v1 enable row level security;
revoke all on penta_runtime.penta_super_runs_v1 from public, anon, authenticated;
grant select on penta_runtime.penta_super_runs_v1 to service_role;

create index if not exists penta_super_runs_v1_bucket_idx
  on penta_runtime.penta_super_runs_v1(scheduled_bucket desc);
create index if not exists penta_super_runs_v1_started_idx
  on penta_runtime.penta_super_runs_v1(started_at desc);

create or replace function penta_runtime.penta_super_native_tick_v1(
  p_cycle_id text default null
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_runtime','penta_pm','penta_self','public','chlom_runtime','integration_control','cron'
as $$
declare
  v_cycle text := coalesce(nullif(btrim(p_cycle_id),''), gen_random_uuid()::text);
  v_bucket timestamptz := to_timestamp(floor(extract(epoch from clock_timestamp()) / 300) * 300);
  v_execution_key text;
  v_run_id uuid;
  v_existing penta_runtime.penta_super_runs_v1%rowtype;
  v_project_id uuid;
  v_dnd jsonb;
  v_dail jsonb;
  v_top_problem record;
  v_open_problem_count integer := 0;
  v_latest_native_run record;
  v_scheduler_status text := 'UNKNOWN';
  v_work_keys text[] := '{}'::text[];
  v_observations jsonb := '{}'::jsonb;
  v_cie_key text := 'pentasuper.cie.semantic-drift.v3.61.2.0';
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.super.native.v1',0)) then
    return jsonb_build_object('service','ct.penta.super.native.v1','status','SKIPPED_LOCKED','cycle_id',v_cycle,'authority_expansion',false);
  end if;

  v_execution_key := 'ct.penta.super.native.v1:' || extract(epoch from v_bucket)::bigint::text;
  select * into v_existing from penta_runtime.penta_super_runs_v1 where execution_key=v_execution_key;
  if found then
    return jsonb_build_object(
      'service','ct.penta.super.native.v1',
      'status','IDEMPOTENT_REPLAY',
      'execution_key',v_execution_key,
      'original_run_id',v_existing.run_id,
      'original_status',v_existing.status,
      'authority_expansion',false
    );
  end if;

  insert into penta_runtime.penta_super_runs_v1(execution_key,cycle_id,scheduled_bucket,status)
  values(v_execution_key,v_cycle,v_bucket,'RUNNING') returning run_id into v_run_id;

  v_dnd := public.penta_dnd_preflight_v1(
    'system','ct.penta.super.native.v1','ct.penta.super.v1','supervise',false,true,false
  );

  select id into v_project_id
  from penta_pm.projects
  where canonical_key='ct.penta.pm.production' and status='active'
  order by updated_at desc limit 1;

  if v_project_id is null then
    v_observations := v_observations || jsonb_build_object('penta_pm','HOLD_PROJECT_NOT_FOUND');
  else
    perform penta_pm.work_item_upsert_v1(
      v_project_id,
      'pentasuper.native-execution',
      'PentaSuper native execution and scheduler supervision',
      'Maintain native PentaSuper execution in PentaTime/pg_cron/PentaQueue, detect missed runs and duplicate clocks, and preserve external automation only as fallback until native production readback is certified.',
      'open',null,
      jsonb_build_object('owner','ct.penta.super.v1','priority','P0','authority_ceiling','D2','source','ct.penta.super.native.v1','external_clock_primary',false)
    );
    v_work_keys := array_append(v_work_keys,'pentasuper.native-execution');

    perform penta_pm.work_item_upsert_v1(
      v_project_id,
      'pentasuper.scheduler-failover',
      'PentaSuper native-primary / external-watchdog failover',
      'Prove stable execution IDs, missed-run detection, idempotency and non-duplication between native execution and any external watchdog before retiring temporary external clocks.',
      'open',null,
      jsonb_build_object('owner','ct.penta.super.v1','priority','P0','authority_ceiling','D2','source','ct.penta.super.native.v1')
    );
    v_work_keys := array_append(v_work_keys,'pentasuper.scheduler-failover');

    perform penta_pm.work_item_upsert_v1(
      v_project_id,
      v_cie_key,
      'Repair PentaRelease CIE semantic drift for v3.61.2.0+',
      'Current managed release surfaces were observed projecting CIE as HOLD_INSUFFICIENT_EVIDENCE. For applicable scorable objects CIE must preserve a real numerical cultural-alignment score when the protected scorer is available/integrity-valid; evidence thinness affects confidence/completeness and may affect score but does not replace the score. Preserve historical release evidence and correct only forward/current projections through CIE/PentaRelease.',
      'open',null,
      jsonb_build_object(
        'owner','ct.penta.super.v1','route_owner','CIE/PentaRelease','priority','P0','defect_class','semantic_drift',
        'observed_release','v3.61.2.0','observed_main_sha','30af3f5d92d2b93c1de780b1c2050a0dfb297b77',
        'retired_projection_value','HOLD_INSUFFICIENT_EVIDENCE','rewrite_history',false,'authority_expansion',false
      )
    );
    v_work_keys := array_append(v_work_keys,v_cie_key);
  end if;

  select count(*) into v_open_problem_count
  from penta_self.problem_ledger_v1
  where state not in ('resolved','false_positive','retired');

  select problem_id,priority,severity,state,title,summary,owner_penta,handler_key,authority_class,auto_heal_allowed,source_ref,last_seen_at,next_attempt_at
  into v_top_problem
  from penta_self.problem_ledger_v1
  where state not in ('resolved','false_positive','retired')
  order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end, first_seen_at
  limit 1;

  if v_project_id is not null and v_top_problem.problem_id is not null then
    perform penta_pm.work_item_upsert_v1(
      v_project_id,
      'pentasuper.remediation.'||v_top_problem.problem_id::text,
      'PentaSuper supervised remediation: '||coalesce(v_top_problem.title,v_top_problem.source_ref),
      coalesce(v_top_problem.summary,'Unresolved PentaSELF problem requiring supervised continuation or precise HOLD.'),
      case when v_top_problem.authority_class='D3' then 'blocked' else 'open' end,
      null,
      jsonb_build_object(
        'owner','ct.penta.super.v1','native_healer_owner',v_top_problem.owner_penta,'handler_key',v_top_problem.handler_key,
        'priority',v_top_problem.priority,'severity',v_top_problem.severity,'problem_state',v_top_problem.state,
        'authority_class',v_top_problem.authority_class,'auto_heal_allowed',v_top_problem.auto_heal_allowed,
        'source_ref',v_top_problem.source_ref,'pentaself_problem_id',v_top_problem.problem_id,
        'counter_mutation_prohibited',true,'scheduler_tick_creates_authority',false
      )
    );
    v_work_keys := array_append(v_work_keys,'pentasuper.remediation.'||v_top_problem.problem_id::text);
  end if;

  select d.status,d.start_time,d.end_time into v_latest_native_run
  from cron.job j join cron.job_run_details d on d.jobid=j.jobid
  where j.jobname='ct-pentasuper-native-v1'
  order by d.start_time desc limit 1;

  v_scheduler_status := case
    when exists(select 1 from cron.job where jobname='ct-pentasuper-native-v1' and active) then 'REGISTERED_ACTIVE'
    else 'NOT_REGISTERED'
  end;

  v_observations := v_observations || jsonb_build_object(
    'dnd_preflight',v_dnd,
    'unresolved_pentaself_problems',v_open_problem_count,
    'top_problem_id',v_top_problem.problem_id,
    'top_problem_priority',v_top_problem.priority,
    'native_scheduler',v_scheduler_status,
    'prior_native_job_status',v_latest_native_run.status,
    'prior_native_job_started_at',v_latest_native_run.start_time,
    'bug_squatter_strategy','folded_as_supervised_remediation_over_native_PentaSELF',
    'cie_semantic_drift_work_item',v_cie_key
  );

  v_dail := public.chlom_append_dail_event(
    'penta.super.native.tick',
    'penta_super',
    'ct.penta.super.v1',
    jsonb_build_object(
      'run_id',v_run_id,'execution_key',v_execution_key,'scheduled_bucket',v_bucket,
      'observations',v_observations,'work_item_keys',to_jsonb(v_work_keys),
      'native_primary',true,'external_watchdog_only',true,'authority_expansion',false,'d3_effect',false
    ),
    'ct.penta.super.v1',null,'ct.penta.super.v1','1.0.0',v_execution_key,null,
    'founder-directed native supervisory bootstrap; D0-D2 only',null,'internal'
  );

  update penta_runtime.penta_super_runs_v1
  set status='PASS',preflight=v_dnd,observations=v_observations,work_item_keys=v_work_keys,
      dail_event_id=v_dail->>'event_id',completed_at=clock_timestamp()
  where run_id=v_run_id;

  return jsonb_build_object(
    'service','ct.penta.super.native.v1','status','PASS','run_id',v_run_id,'execution_key',v_execution_key,
    'scheduled_bucket',v_bucket,'work_item_keys',to_jsonb(v_work_keys),'dail_event_id',v_dail->>'event_id',
    'unresolved_pentaself_problems',v_open_problem_count,'native_scheduler',v_scheduler_status,
    'authority_expansion',false,'d3_effect',false
  );
exception when others then
  if v_run_id is not null then
    update penta_runtime.penta_super_runs_v1
    set status='FAILED',observations=coalesce(observations,'{}'::jsonb)||jsonb_build_object('sqlstate',sqlstate,'error',left(sqlerrm,500)),completed_at=clock_timestamp()
    where run_id=v_run_id;
  end if;
  raise;
end
$$;

revoke all on function penta_runtime.penta_super_native_tick_v1(text) from public, anon, authenticated;
grant execute on function penta_runtime.penta_super_native_tick_v1(text) to service_role;

-- Register desired state first. This is the canonical scheduler intent used by PentaSELF/PentaTime reconciliation.
select integration_control.scheduler_desired_job_upsert_v2(
  'ct-pentasuper-native-v1',
  '1,6,11,16,21,26,31,36,41,46,51,56 * * * *',
  'select penta_runtime.penta_super_native_tick_v1();',
  202608300955,
  'github:crownthrive1/CrownThrive-OS:penta/super:native-runtime-v1',
  jsonb_build_object('owner','ct.penta.super.v1','native_primary',true,'external_watchdog_only',true,'authority_ceiling','D2','penta_dnd_scoped',true)
);

do $$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-pentasuper-native-v1' limit 1;
  if v_jobid is not null then perform cron.unschedule(v_jobid); end if;
end $$;

select cron.schedule(
  'ct-pentasuper-native-v1',
  '1,6,11,16,21,26,31,36,41,46,51,56 * * * *',
  'select penta_runtime.penta_super_native_tick_v1();'
);

comment on function penta_runtime.penta_super_native_tick_v1(text) is
'PentaSuper native supervisory tick. Supervises scheduler health, routes CIE semantic drift, folds temporary Bug Squatter behavior over native PentaSELF, creates governed PentaPM work, and appends DAIL evidence. No D3 or authority expansion.';
