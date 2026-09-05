-- Applied migration 20260904063737: penta_balancer_foundation_v1
set lock_timeout = '3s';
set statement_timeout = '45s';

create schema if not exists penta_balancer;
comment on schema penta_balancer is 'PentaBalancer production runtime: bounded scheduler load balancing and temporal cohesion only.';

revoke all on schema penta_balancer from public, anon, authenticated;
grant usage on schema penta_balancer to service_role;

create table if not exists penta_balancer.control_state_v1 (
  singleton_key text primary key default 'primary' check (singleton_key = 'primary'),
  mode text not null default 'WATCH' check (mode in ('NORMAL','WATCH','SHED','RECOVERY','HOLD')),
  pressure_score integer not null default 0 check (pressure_score between 0 and 100),
  cohesion_score integer not null default 0 check (cohesion_score between 0 and 100),
  consecutive_pressure integer not null default 0 check (consecutive_pressure >= 0),
  consecutive_clear integer not null default 0 check (consecutive_clear >= 0),
  metrics jsonb not null default '{}'::jsonb,
  last_decision jsonb not null default '{}'::jsonb,
  last_transition_at timestamptz,
  last_reconcile_at timestamptz,
  last_rebalance_at timestamptz,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_balancer.operation_policy_v1 (
  operation_key text primary key references pentatime.operation_registry_v2(operation_key) on update cascade on delete cascade,
  admission_class text not null default 'normal' check (admission_class in ('critical','high','normal','elastic')),
  priority integer not null default 50 check (priority between 0 and 100),
  shed_allowed boolean not null default true,
  active boolean not null default true,
  rationale text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_balancer.cohesion_targets_v1 (
  target_key text primary key,
  jobname text not null unique,
  required_schedule text not null,
  required_command text not null,
  operation_key text references pentatime.operation_registry_v2(operation_key) on update cascade on delete restrict,
  owner_set text[] not null default '{}'::text[],
  required boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_balancer.decision_events_v1 (
  decision_id uuid primary key default gen_random_uuid(),
  observed_at timestamptz not null default clock_timestamp(),
  prior_mode text,
  decided_mode text not null,
  pressure_score integer not null check (pressure_score between 0 and 100),
  cohesion_score integer not null check (cohesion_score between 0 and 100),
  metrics jsonb not null,
  decision jsonb not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$')
);

create index if not exists penta_balancer_decision_events_observed_idx
  on penta_balancer.decision_events_v1(observed_at desc);
create index if not exists penta_balancer_decision_events_mode_idx
  on penta_balancer.decision_events_v1(decided_mode, observed_at desc);

alter table penta_balancer.control_state_v1 enable row level security;
alter table penta_balancer.operation_policy_v1 enable row level security;
alter table penta_balancer.cohesion_targets_v1 enable row level security;
alter table penta_balancer.decision_events_v1 enable row level security;

insert into penta_balancer.control_state_v1(singleton_key)
values ('primary')
on conflict (singleton_key) do nothing;

create or replace function penta_balancer.pressure_snapshot_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, penta_balancer, cron, pg_temp
as $$
declare
  v_max_connections integer := current_setting('max_connections')::integer;
  v_runner_ceiling integer := coalesce(nullif(current_setting('cron.max_running_jobs', true),''),'32')::integer;
  v_sessions integer := 0;
  v_active integer := 0;
  v_lock_waiters integer := 0;
  v_running_jobs integer := 0;
  v_recent_failed integer := 0;
  v_startup_timeouts integer := 0;
  v_statement_timeouts integer := 0;
  v_deadlocks integer := 0;
  v_connection_failures integer := 0;
  v_session_pct numeric := 0;
  v_active_pct numeric := 0;
  v_raw_score numeric := 0;
  v_score integer := 0;
begin
  select count(*)::integer,
         count(*) filter (where state = 'active')::integer,
         count(*) filter (where wait_event_type = 'Lock')::integer
    into v_sessions, v_active, v_lock_waiters
  from pg_stat_activity;

  with bounded as (
    select status, start_time, end_time, return_message
    from cron.job_run_details
    order by runid desc
    limit 2000
  )
  select
    count(*) filter (where status='running' and end_time is null)::integer,
    count(*) filter (where status='failed' and start_time >= clock_timestamp()-interval '15 minutes')::integer,
    count(*) filter (where status='failed' and start_time >= clock_timestamp()-interval '15 minutes' and coalesce(return_message,'') ilike '%job startup timeout%')::integer,
    count(*) filter (where status='failed' and start_time >= clock_timestamp()-interval '15 minutes' and coalesce(return_message,'') ilike '%statement timeout%')::integer,
    count(*) filter (where status='failed' and start_time >= clock_timestamp()-interval '15 minutes' and coalesce(return_message,'') ilike '%deadlock%')::integer,
    count(*) filter (where status='failed' and start_time >= clock_timestamp()-interval '15 minutes' and coalesce(return_message,'') ilike '%connection failed%')::integer
  into v_running_jobs, v_recent_failed, v_startup_timeouts, v_statement_timeouts, v_deadlocks, v_connection_failures
  from bounded;

  v_session_pct := round(100.0::numeric * v_sessions::numeric / greatest(v_max_connections,1)::numeric,2);
  v_active_pct := round(100.0::numeric * v_active::numeric / greatest(v_max_connections,1)::numeric,2);

  v_raw_score :=
      (v_session_pct * 0.45)
    + (v_active_pct * 0.25)
    + least(20::numeric, v_lock_waiters::numeric * 2.5)
    + least(10::numeric, v_running_jobs::numeric * 0.75)
    + least(15::numeric, v_recent_failed::numeric * 0.50)
    + case when v_startup_timeouts + v_connection_failures > 0 then 8 else 0 end
    + case when v_deadlocks > 0 then 7 else 0 end;
  v_score := least(100, greatest(0, round(v_raw_score)::integer));

  return jsonb_build_object(
    'captured_at', clock_timestamp(),
    'max_connections', v_max_connections,
    'runner_ceiling', v_runner_ceiling,
    'sessions', v_sessions,
    'session_pct', v_session_pct,
    'active_sessions', v_active,
    'active_pct', v_active_pct,
    'lock_waiters', v_lock_waiters,
    'running_cron_jobs', v_running_jobs,
    'recent_failures_15m', v_recent_failed,
    'startup_timeouts_15m', v_startup_timeouts,
    'statement_timeouts_15m', v_statement_timeouts,
    'deadlocks_15m', v_deadlocks,
    'connection_failures_15m', v_connection_failures,
    'pressure_score', v_score,
    'bounded_history_rows', 2000,
    'authority_created', false
  );
end;
$$;

create or replace function penta_balancer.cohesion_snapshot_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, penta_balancer, pentatime, integration_control, cron, pg_temp
as $$
with q as (
  select
    t.target_key,
    t.jobname,
    t.required_schedule,
    t.required_command,
    t.operation_key,
    t.owner_set,
    j.jobid,
    j.active as cron_active,
    j.schedule as actual_schedule,
    j.command as actual_command,
    d.active as desired_active,
    d.schedule as desired_schedule,
    d.command as desired_command,
    d.allow_auto_restore,
    case when t.operation_key is null then true
         else coalesce(o.enabled,false) and coalesce(e.enabled,false)
    end as operation_enabled,
    (
      j.jobid is not null
      and coalesce(j.active,false)
      and j.schedule is not distinct from t.required_schedule
      and j.command is not distinct from t.required_command
      and d.jobname is not null
      and coalesce(d.active,false)
      and coalesce(d.allow_auto_restore,false)
      and d.schedule is not distinct from t.required_schedule
      and d.command is not distinct from t.required_command
      and (t.operation_key is null or (coalesce(o.enabled,false) and coalesce(e.enabled,false)))
    ) as passed
  from penta_balancer.cohesion_targets_v1 t
  left join lateral (
    select c.jobid,c.active,c.schedule,c.command
    from cron.job c
    where c.jobname=t.jobname
    order by c.jobid desc
    limit 1
  ) j on true
  left join integration_control.scheduler_desired_jobs_v2 d on d.jobname=t.jobname
  left join pentatime.operation_registry_v2 o on o.operation_key=t.operation_key
  left join pentatime.operation_executors_v3 e on e.operation_key=t.operation_key
  where t.required
), a as (
  select count(*)::integer as total,
         count(*) filter(where passed)::integer as passed_count,
         coalesce(jsonb_agg(jsonb_build_object(
           'target_key',target_key,
           'jobname',jobname,
           'passed',passed,
           'cron_active',cron_active,
           'actual_schedule',actual_schedule,
           'required_schedule',required_schedule,
           'desired_active',desired_active,
           'allow_auto_restore',allow_auto_restore,
           'operation_key',operation_key,
           'operation_enabled',operation_enabled,
           'owners',owner_set
         ) order by target_key),'[]'::jsonb) as targets
  from q
)
select jsonb_build_object(
  'state',case when total>0 and passed_count=total then 'PASS' else 'DRIFT' end,
  'cohesion_score',case when total=0 then 0 else round(100.0*passed_count/total)::integer end,
  'passed_targets',passed_count,
  'total_targets',total,
  'targets',targets,
  'authority_created',false,
  'observed_at',statement_timestamp()
)
from a;
$$;

revoke all on all tables in schema penta_balancer from public, anon, authenticated;
revoke all on all sequences in schema penta_balancer from public, anon, authenticated;
revoke all on all functions in schema penta_balancer from public, anon, authenticated;
grant select on penta_balancer.control_state_v1, penta_balancer.operation_policy_v1, penta_balancer.cohesion_targets_v1, penta_balancer.decision_events_v1 to service_role;
grant execute on function penta_balancer.pressure_snapshot_v1() to service_role;
grant execute on function penta_balancer.cohesion_snapshot_v1() to service_role;


-- Applied migration 20260904064118: penta_balancer_control_runtime_v1
set lock_timeout = '3s';
set statement_timeout = '60s';

create or replace function penta_balancer.cohesion_snapshot_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, penta_balancer, pentatime, integration_control, penta_self, cron, pg_temp
as $$
with q as (
  select
    t.target_key,
    t.jobname,
    t.required_schedule,
    t.required_command,
    t.operation_key,
    t.owner_set,
    j.jobid,
    j.active as cron_active,
    j.schedule as actual_schedule,
    j.command as actual_command,
    d.active as desired_active,
    d.schedule as desired_schedule,
    d.command as desired_command,
    d.allow_auto_restore,
    p.desired_active as permanent_active,
    p.schedule as permanent_schedule,
    p.command as permanent_command,
    p.enforcement_mode,
    r.auto_repair,
    r.expected_schedule,
    r.expected_command,
    exists(
      select 1 from pentatime.scheduler_registry sr
      where sr.cron_job_name=t.jobname and sr.desired_state='active'
    ) as scheduler_registered,
    case when t.operation_key is null then true
         else coalesce(o.enabled,false) and coalesce(e.enabled,false)
    end as operation_enabled,
    (
      j.jobid is not null
      and coalesce(j.active,false)
      and j.schedule is not distinct from t.required_schedule
      and j.command is not distinct from t.required_command
      and d.jobname is not null
      and coalesce(d.active,false)
      and coalesce(d.allow_auto_restore,false)
      and d.schedule is not distinct from t.required_schedule
      and d.command is not distinct from t.required_command
      and p.jobname is not null
      and coalesce(p.desired_active,false)
      and p.enforcement_mode='exact'
      and p.schedule is not distinct from t.required_schedule
      and p.command is not distinct from t.required_command
      and r.jobname is not null
      and coalesce(r.auto_repair,false)
      and r.expected_schedule is not distinct from t.required_schedule
      and r.expected_command is not distinct from t.required_command
      and exists(select 1 from pentatime.scheduler_registry sr where sr.cron_job_name=t.jobname and sr.desired_state='active')
      and (t.operation_key is null or (coalesce(o.enabled,false) and coalesce(e.enabled,false)))
    ) as passed
  from penta_balancer.cohesion_targets_v1 t
  left join lateral (
    select c.jobid,c.active,c.schedule,c.command
    from cron.job c
    where c.jobname=t.jobname
    order by c.jobid desc
    limit 1
  ) j on true
  left join integration_control.scheduler_desired_jobs_v2 d on d.jobname=t.jobname
  left join penta_self.permanent_cron_desired_state_v1 p on p.jobname=t.jobname
  left join penta_self.required_jobs_v1 r on r.jobname=t.jobname
  left join pentatime.operation_registry_v2 o on o.operation_key=t.operation_key
  left join pentatime.operation_executors_v3 e on e.operation_key=t.operation_key
  where t.required
), a as (
  select count(*)::integer as total,
         count(*) filter(where passed)::integer as passed_count,
         coalesce(jsonb_agg(jsonb_build_object(
           'target_key',target_key,
           'jobname',jobname,
           'passed',passed,
           'cron_active',cron_active,
           'actual_schedule',actual_schedule,
           'required_schedule',required_schedule,
           'desired_active',desired_active,
           'desired_schedule',desired_schedule,
           'allow_auto_restore',allow_auto_restore,
           'permanent_active',permanent_active,
           'permanent_schedule',permanent_schedule,
           'enforcement_mode',enforcement_mode,
           'auto_repair',auto_repair,
           'expected_schedule',expected_schedule,
           'scheduler_registered',scheduler_registered,
           'operation_key',operation_key,
           'operation_enabled',operation_enabled,
           'owners',owner_set
         ) order by target_key),'[]'::jsonb) as targets
  from q
)
select jsonb_build_object(
  'state',case when total>0 and passed_count=total then 'PASS' else 'DRIFT' end,
  'cohesion_score',case when total=0 then 0 else round(100.0*passed_count/total)::integer end,
  'passed_targets',passed_count,
  'total_targets',total,
  'targets',targets,
  'authority_created',false,
  'observed_at',statement_timestamp()
)
from a;
$$;

create or replace function penta_balancer.apply_admission_v1(p_mode text, p_pressure_score integer)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_balancer, pentatime, pg_temp
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_released integer := 0;
  v_normal_deferred integer := 0;
  v_elastic_deferred integer := 0;
  v_rows integer := 0;
begin
  if p_mode not in ('NORMAL','WATCH','SHED','RECOVERY','HOLD') then
    raise exception 'invalid_balancer_mode:%',p_mode;
  end if;

  insert into pentatime.operation_state_v2(operation_key)
  select operation_key from penta_balancer.operation_policy_v1 where active
  on conflict(operation_key) do nothing;

  update pentatime.operation_state_v2 s
     set backoff_until=null,
         consecutive_deferrals=0,
         last_state='BALANCER_RELEASED',
         last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
           ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
         updated_at=v_now
  from penta_balancer.operation_policy_v1 p
  where p.operation_key=s.operation_key
    and p.active
    and p.admission_class in ('critical','high')
    and coalesce(s.last_result->>'balancer_owned','false')='true';
  get diagnostics v_rows=row_count;
  v_released:=v_released+v_rows;

  if p_mode='NORMAL' then
    update pentatime.operation_state_v2 s
       set backoff_until=null,
           consecutive_deferrals=0,
           last_state='BALANCER_RELEASED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
           updated_at=v_now
    where coalesce(s.last_result->>'balancer_owned','false')='true';
    get diagnostics v_rows=row_count;
    v_released:=v_released+v_rows;

  elsif p_mode='RECOVERY' then
    update pentatime.operation_state_v2 s
       set backoff_until=null,
           consecutive_deferrals=0,
           last_state='BALANCER_RELEASED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
           updated_at=v_now
    from penta_balancer.operation_policy_v1 p
    where p.operation_key=s.operation_key
      and p.admission_class='normal'
      and coalesce(s.last_result->>'balancer_owned','false')='true';
    get diagnostics v_rows=row_count;
    v_released:=v_released+v_rows;

    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '30 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_RECOVERY_PACING',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',30,'decided_at',v_now),
           updated_at=v_now
    from penta_balancer.operation_policy_v1 p
    where p.operation_key=s.operation_key
      and p.active and p.shed_allowed and p.admission_class='elastic'
      and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true');
    get diagnostics v_elastic_deferred=row_count;

  elsif p_mode='WATCH' then
    update pentatime.operation_state_v2 s
       set backoff_until=null,
           consecutive_deferrals=0,
           last_state='BALANCER_RELEASED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
           updated_at=v_now
    from penta_balancer.operation_policy_v1 p
    where p.operation_key=s.operation_key
      and p.admission_class='normal'
      and coalesce(s.last_result->>'balancer_owned','false')='true';
    get diagnostics v_rows=row_count;
    v_released:=v_released+v_rows;

    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '75 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_WATCH_DEFERRED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',75,'decided_at',v_now),
           updated_at=v_now
    from penta_balancer.operation_policy_v1 p
    where p.operation_key=s.operation_key
      and p.active and p.shed_allowed and p.admission_class='elastic'
      and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true');
    get diagnostics v_elastic_deferred=row_count;

  else
    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '90 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_SHED_DEFERRED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',90,'decided_at',v_now),
           updated_at=v_now
    from penta_balancer.operation_policy_v1 p
    where p.operation_key=s.operation_key
      and p.active and p.shed_allowed and p.admission_class='normal'
      and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true');
    get diagnostics v_normal_deferred=row_count;

    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '180 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_SHED_DEFERRED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',180,'decided_at',v_now),
           updated_at=v_now
    from penta_balancer.operation_policy_v1 p
    where p.operation_key=s.operation_key
      and p.active and p.shed_allowed and p.admission_class='elastic'
      and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true');
    get diagnostics v_elastic_deferred=row_count;
  end if;

  return jsonb_build_object(
    'state','APPLIED','mode',p_mode,'pressure_score',p_pressure_score,
    'released',v_released,'normal_deferred',v_normal_deferred,'elastic_deferred',v_elastic_deferred,
    'permanent_disables',0,'authority_created',false,'observed_at',v_now
  );
end;
$$;

create or replace function penta_balancer.ensure_core_cohesion_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_balancer, pentatime, integration_control, penta_self, cron, extensions, pg_temp
as $$
declare
  r record;
  v_before jsonb;
  v_after jsonb;
  v_jobid bigint;
  v_generation bigint;
  v_hash text;
  v_changed text[]:='{}'::text[];
  v_now timestamptz:=clock_timestamp();
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:cohesion:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','authority_created',false,'observed_at',v_now);
  end if;

  perform set_config('lock_timeout','2s',true);
  perform set_config('statement_timeout','20s',true);
  v_before:=penta_balancer.cohesion_snapshot_v1();

  for r in
    select * from penta_balancer.cohesion_targets_v1 where required order by target_key
  loop
    select j.jobid into v_jobid from cron.job j where j.jobname=r.jobname order by j.jobid desc limit 1;
    if v_jobid is null then
      perform cron.schedule(r.jobname,r.required_schedule,r.required_command);
      v_changed:=array_append(v_changed,r.jobname||':created');
    elsif exists(select 1 from cron.job j where j.jobid=v_jobid and (not j.active or j.schedule is distinct from r.required_schedule or j.command is distinct from r.required_command)) then
      perform cron.alter_job(v_jobid,schedule=>r.required_schedule,command=>r.required_command,active=>true);
      v_changed:=array_append(v_changed,r.jobname||':cron_converged');
    end if;

    select greatest(
      coalesce((select d.generation+1 from integration_control.scheduler_desired_jobs_v2 d where d.jobname=r.jobname),0),
      coalesce((select max(d.generation)+1 from integration_control.scheduler_desired_jobs_v2 d),202609040300)
    ) into v_generation;

    v_hash:=encode(extensions.digest(convert_to(jsonb_build_object(
      'jobname',r.jobname,'schedule',r.required_schedule,'command',r.required_command,
      'active',true,'generation',v_generation,'source_ref','ct.pentabalancer.temporal-cohesion.v1'
    )::text,'UTF8'),'sha256'),'hex');

    insert into integration_control.scheduler_desired_jobs_v2(
      jobname,schedule,command,database_name,username,active,generation,source_ref,
      desired_sha256,allow_auto_restore,metadata
    ) values(
      r.jobname,r.required_schedule,r.required_command,current_database(),current_user,true,v_generation,
      'ct.pentabalancer.temporal-cohesion.v1',v_hash,true,
      jsonb_build_object('owner_set',to_jsonb(r.owner_set),'cohesion_target','penta.balancer','cohesion_score_target',100,'authority_created',false)
    )
    on conflict(jobname) do update set
      schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,
      username=excluded.username,active=true,generation=excluded.generation,source_ref=excluded.source_ref,
      desired_sha256=excluded.desired_sha256,allow_auto_restore=true,
      metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=v_now;

    insert into penta_self.permanent_cron_desired_state_v1(
      jobname,schedule,command,database_name,username_name,desired_active,enforcement_mode,
      verification_evidence,desired_sha256,verified_at,source_ref
    ) values(
      r.jobname,r.required_schedule,r.required_command,current_database(),current_user,true,'exact',
      jsonb_build_object('owner_set',to_jsonb(r.owner_set),'cohesion_target','penta.balancer','cohesion_score_target',100,'authority_created',false),
      v_hash,v_now,'ct.pentabalancer.temporal-cohesion.v1'
    )
    on conflict(jobname) do update set
      schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,
      username_name=excluded.username_name,desired_active=true,enforcement_mode='exact',
      verification_evidence=penta_self.permanent_cron_desired_state_v1.verification_evidence||excluded.verification_evidence,
      desired_sha256=excluded.desired_sha256,verified_at=v_now,source_ref=excluded.source_ref,updated_at=v_now;

    insert into penta_self.required_jobs_v1(
      jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata
    ) values(
      r.jobname,r.required_schedule,r.required_command,true,'D1',
      jsonb_build_object('owner_set',to_jsonb(r.owner_set),'operation_key',r.operation_key,'cohesion_target','penta.balancer','authority_created',false)
    )
    on conflict(jobname) do update set
      expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,
      auto_repair=true,risk_class='D1',metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=v_now;
  end loop;

  v_after:=penta_balancer.cohesion_snapshot_v1();
  update penta_balancer.control_state_v1
     set cohesion_score=coalesce((v_after->>'cohesion_score')::integer,0),last_reconcile_at=v_now,updated_at=v_now
   where singleton_key='primary';

  return jsonb_build_object(
    'state',case when coalesce((v_after->>'cohesion_score')::integer,0)=100 then 'PASS' else 'HOLD' end,
    'changed',to_jsonb(v_changed),'before',v_before,'after',v_after,
    'authority_created',false,'observed_at',v_now
  );
end;
$$;

create or replace function penta_balancer.control_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_balancer, pentatime, chlom_runtime, extensions, pg_temp
as $$
declare
  v_prev penta_balancer.control_state_v1%rowtype;
  v_metrics jsonb;
  v_cohesion jsonb;
  v_repair jsonb;
  v_admission jsonb;
  v_mode text;
  v_pressure integer;
  v_session_pct numeric;
  v_lock_waiters integer;
  v_startup integer;
  v_statements integer;
  v_deadlocks integer;
  v_connections integer;
  v_running integer;
  v_runner_ceiling integer;
  v_severe boolean;
  v_watch boolean;
  v_consecutive_pressure integer;
  v_consecutive_clear integer;
  v_cohesion_score integer;
  v_now timestamptz:=clock_timestamp();
  v_decision jsonb;
  v_event_payload jsonb;
  v_event_sha text;
  v_dail jsonb;
  v_dail_state text:='not_required';
begin
  perform set_config('lock_timeout','2s',true);
  perform set_config('statement_timeout','25s',true);

  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:control:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','authority_created',false,'observed_at',v_now);
  end if;

  select * into v_prev from penta_balancer.control_state_v1 where singleton_key='primary' for update;
  if not found then
    insert into penta_balancer.control_state_v1(singleton_key) values('primary') returning * into v_prev;
  end if;

  v_metrics:=penta_balancer.pressure_snapshot_v1();
  v_pressure:=coalesce((v_metrics->>'pressure_score')::integer,0);
  v_session_pct:=coalesce((v_metrics->>'session_pct')::numeric,0);
  v_lock_waiters:=coalesce((v_metrics->>'lock_waiters')::integer,0);
  v_startup:=coalesce((v_metrics->>'startup_timeouts_15m')::integer,0);
  v_statements:=coalesce((v_metrics->>'statement_timeouts_15m')::integer,0);
  v_deadlocks:=coalesce((v_metrics->>'deadlocks_15m')::integer,0);
  v_connections:=coalesce((v_metrics->>'connection_failures_15m')::integer,0);
  v_running:=coalesce((v_metrics->>'running_cron_jobs')::integer,0);
  v_runner_ceiling:=coalesce((v_metrics->>'runner_ceiling')::integer,32);

  v_severe := v_session_pct>=85 or v_lock_waiters>=8 or (v_startup+v_connections)>=10 or v_statements>=20 or v_running>=v_runner_ceiling;
  v_watch := v_session_pct>=65 or v_lock_waiters>=3 or (v_startup+v_connections)>=3 or v_statements>=8 or v_deadlocks>=1;

  v_consecutive_pressure:=case when v_severe or v_watch then v_prev.consecutive_pressure+1 else 0 end;
  v_consecutive_clear:=case when not v_severe and not v_watch then v_prev.consecutive_clear+1 else 0 end;

  if v_severe then v_mode:='SHED';
  elsif v_watch then v_mode:='WATCH';
  elsif v_prev.mode in ('SHED','WATCH','RECOVERY','HOLD') and v_consecutive_clear<3 then v_mode:='RECOVERY';
  else v_mode:='NORMAL';
  end if;

  v_cohesion:=penta_balancer.cohesion_snapshot_v1();
  v_cohesion_score:=coalesce((v_cohesion->>'cohesion_score')::integer,0);
  if v_cohesion_score<100 then
    v_repair:=penta_balancer.ensure_core_cohesion_v1();
    v_cohesion:=coalesce(v_repair->'after',v_cohesion);
    v_cohesion_score:=coalesce((v_cohesion->>'cohesion_score')::integer,0);
    if v_cohesion_score<100 then v_mode:='HOLD'; end if;
  end if;

  v_admission:=penta_balancer.apply_admission_v1(v_mode,v_pressure);
  v_decision:=jsonb_build_object(
    'mode',v_mode,'pressure_score',v_pressure,'cohesion_score',v_cohesion_score,
    'admission',v_admission,'cohesion',v_cohesion,'cohesion_repair',v_repair,
    'sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
    'business_work_executed',false,'provider_write',false,'money_movement',false,'d3_effect',false,
    'decided_at',v_now
  );

  update penta_balancer.control_state_v1
     set mode=v_mode,pressure_score=v_pressure,cohesion_score=v_cohesion_score,
         consecutive_pressure=v_consecutive_pressure,consecutive_clear=v_consecutive_clear,
         metrics=v_metrics,last_decision=v_decision,
         last_transition_at=case when v_prev.mode is distinct from v_mode then v_now else v_prev.last_transition_at end,
         last_reconcile_at=case when v_repair is not null then v_now else v_prev.last_reconcile_at end,
         updated_at=v_now
   where singleton_key='primary';

  if v_prev.mode is distinct from v_mode or v_prev.cohesion_score is distinct from v_cohesion_score or extract(minute from v_now)::integer=0 then
    v_event_payload:=jsonb_build_object(
      'prior_mode',v_prev.mode,'decided_mode',v_mode,'pressure_score',v_pressure,'cohesion_score',v_cohesion_score,
      'metrics',v_metrics,'decision',v_decision,'observed_at',v_now
    );
    v_event_sha:=encode(extensions.digest(convert_to(v_event_payload::text,'UTF8'),'sha256'),'hex');
    insert into penta_balancer.decision_events_v1(
      observed_at,prior_mode,decided_mode,pressure_score,cohesion_score,metrics,decision,evidence_sha256
    ) values(v_now,v_prev.mode,v_mode,v_pressure,v_cohesion_score,v_metrics,v_decision,v_event_sha);

    if pg_try_advisory_xact_lock(hashtext('chlom_runtime.dail.global.v1')) then
      begin
        v_dail:=chlom_runtime.append_dail_event(
          'penta.balancer.control-decision','scheduler_load_balance','penta.balancer',
          v_event_payload||jsonb_build_object('evidence_sha256',v_event_sha,'authority_created',false),
          'PentaBalancer/PentaTime/PentaClock/PentaTick',null,'PentaBalancer','1.0.0',
          v_event_sha,'penta_balancer.control_tick_v1()','ct.scheduler-topology.production.v1',null,'internal'
        );
        v_dail_state:='recorded';
      exception when others then
        v_dail_state:='deferred_error:'||sqlstate;
      end;
    else
      v_dail_state:='deferred_lock_busy';
    end if;
  end if;

  return jsonb_build_object(
    'state','SUCCEEDED','mode',v_mode,'pressure_score',v_pressure,'cohesion_score',v_cohesion_score,
    'metrics',v_metrics,'admission',v_admission,'cohesion',v_cohesion,'dail_state',v_dail_state,
    'authority_created',false,'observed_at',v_now
  );
end;
$$;

create or replace function penta_balancer.executor_v1()
returns jsonb
language sql
security definer
set search_path = pg_catalog, penta_balancer
as $$ select penta_balancer.control_tick_v1(); $$;

create or replace function penta_balancer.status_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, penta_balancer
as $$
select jsonb_build_object(
  'service','PentaBalancer',
  'state',case when s.cohesion_score=100 and s.mode<>'HOLD' then 'ACTIVE' else 'WATCH' end,
  'control_state',to_jsonb(s),
  'current_pressure',penta_balancer.pressure_snapshot_v1(),
  'current_cohesion',penta_balancer.cohesion_snapshot_v1(),
  'sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
  'authority_created',false,'observed_at',statement_timestamp()
)
from penta_balancer.control_state_v1 s where s.singleton_key='primary';
$$;

create or replace function penta_balancer.canary_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_balancer, pentatime, cron, extensions, pg_temp
as $$
declare
  v_tick jsonb;
  v_status jsonb;
  v_cohesion integer;
  v_rls boolean;
  v_anon_exec boolean;
  v_auth_exec boolean;
  v_service_exec boolean;
  v_job_ok boolean;
  v_single_scope boolean;
  v_pass boolean;
  v_evidence jsonb;
  v_sha text;
begin
  v_tick:=penta_balancer.control_tick_v1();
  v_status:=penta_balancer.status_v1();
  v_cohesion:=coalesce((v_status->'current_cohesion'->>'cohesion_score')::integer,0);

  select bool_and(c.relrowsecurity) into v_rls
  from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='penta_balancer' and c.relkind='r';

  v_anon_exec:=has_function_privilege('anon','penta_balancer.control_tick_v1()','EXECUTE');
  v_auth_exec:=has_function_privilege('authenticated','penta_balancer.control_tick_v1()','EXECUTE');
  v_service_exec:=has_function_privilege('service_role','penta_balancer.control_tick_v1()','EXECUTE');

  select exists(
    select 1 from cron.job
    where jobname='ct-pentabalancer-control-v1' and active and schedule='* * * * *'
      and command='select pentatime.execute_guarded_v3(''penta_balancer'');'
  ) into v_job_ok;

  select count(*)=1 into v_single_scope
  from pentatime.operation_registry_v2 where owner_penta like 'PentaBalancer%';

  v_pass:=coalesce(v_rls,false) and not v_anon_exec and not v_auth_exec and v_service_exec
    and v_job_ok and v_single_scope and v_cohesion=100 and coalesce(v_tick->>'state','')='SUCCEEDED';

  v_evidence:=jsonb_build_object(
    'semantic_pass',v_pass,'tick',v_tick,'status',v_status,'rls_all_tables',v_rls,
    'anon_execute',v_anon_exec,'authenticated_execute',v_auth_exec,'service_role_execute',v_service_exec,
    'canonical_job_exact',v_job_ok,'single_operation_scope',v_single_scope,'cohesion_score',v_cohesion,
    'provider_write',false,'money_movement',false,'d3_effect',false,'authority_created',false,
    'observed_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  return jsonb_build_object('state',case when v_pass then 'PASS' else 'HOLD' end,'evidence',v_evidence,'evidence_sha256',v_sha);
end;
$$;

insert into pentatime.operation_registry_v2(
  operation_key,domain_key,owner_penta,enabled,base_backoff_seconds,max_backoff_seconds,metadata
) values(
  'penta_balancer','ct:scheduler-load-balance-lane','PentaBalancer/PentaTime/PentaClock/PentaTick',true,5,60,
  jsonb_build_object(
    'job','ct-pentabalancer-control-v1','sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
    'business_work_execution',false,'provider_write',false,'money_movement',false,'d3_effect',false,
    'authority_created',false,'admission_model','temporary_backoff_only_no_permanent_disable',
    'cohesion_partners',jsonb_build_array('PentaTime','PentaClock','PentaTick','PentaCrons')
  )
)
on conflict(operation_key) do update set
  domain_key=excluded.domain_key,owner_penta=excluded.owner_penta,enabled=true,
  base_backoff_seconds=excluded.base_backoff_seconds,max_backoff_seconds=excluded.max_backoff_seconds,
  metadata=pentatime.operation_registry_v2.metadata||excluded.metadata,updated_at=clock_timestamp();

insert into pentatime.operation_executors_v3(operation_key,executor_regprocedure,authority_ceiling,enabled,metadata)
values(
  'penta_balancer','penta_balancer.executor_v1()'::regprocedure,'D1',true,
  jsonb_build_object('sole_responsibility','scheduler_load_balance_and_temporal_cohesion','authority_created',false)
)
on conflict(operation_key) do update set
  executor_regprocedure=excluded.executor_regprocedure,authority_ceiling='D1',enabled=true,
  metadata=pentatime.operation_executors_v3.metadata||excluded.metadata,updated_at=clock_timestamp();

insert into penta_balancer.operation_policy_v1(operation_key,admission_class,priority,shed_allowed,rationale,metadata)
select
  o.operation_key,
  case
    when o.operation_key in ('penta_balancer','penta_tick','penta_clock','penta_self','scheduler_permanence_audit','pentaod_reconcile','pentaod_heartbeat') then 'critical'
    when o.operation_key in ('penta_certify','production_classifier','provider_evidence','penta_wire','credential_continuity','communications_survival','factory_continuity','factory_dispatch') then 'high'
    when o.operation_key in ('penta_persona_factory','penta_planner','phase3_discovery','penta_crawler','factory_internal_generate','commercial_release_repair') then 'elastic'
    else 'normal'
  end,
  case
    when o.operation_key in ('penta_balancer','penta_tick','penta_clock','penta_self','scheduler_permanence_audit','pentaod_reconcile','pentaod_heartbeat') then 100
    when o.operation_key in ('penta_certify','production_classifier','provider_evidence','penta_wire','credential_continuity','communications_survival','factory_continuity','factory_dispatch') then 80
    when o.operation_key in ('penta_persona_factory','penta_planner','phase3_discovery','penta_crawler','factory_internal_generate','commercial_release_repair') then 25
    else 50
  end,
  case when o.operation_key in (
    'penta_balancer','penta_tick','penta_clock','penta_self','scheduler_permanence_audit','pentaod_reconcile','pentaod_heartbeat',
    'penta_certify','production_classifier','provider_evidence','penta_wire','credential_continuity','communications_survival','factory_continuity','factory_dispatch'
  ) then false else true end,
  case
    when o.operation_key in ('penta_balancer','penta_tick','penta_clock') then 'Temporal core; never shed.'
    when o.operation_key in ('penta_self','scheduler_permanence_audit','pentaod_reconcile','pentaod_heartbeat') then 'Continuity core; never shed.'
    when o.operation_key in ('penta_certify','production_classifier','provider_evidence','penta_wire','credential_continuity','communications_survival','factory_continuity','factory_dispatch') then 'High-priority governed work; preserved during pressure.'
    when o.operation_key in ('penta_persona_factory','penta_planner','phase3_discovery','penta_crawler','factory_internal_generate','commercial_release_repair') then 'Elastic work; temporarily paced under pressure and automatically released.'
    else 'Standard governed operation; temporary pacing permitted only in SHED or HOLD.'
  end,
  jsonb_build_object('source_ref','ct.pentabalancer.production.v1','permanent_disable',false,'authority_created',false)
from pentatime.operation_registry_v2 o
on conflict(operation_key) do update set
  admission_class=excluded.admission_class,priority=excluded.priority,shed_allowed=excluded.shed_allowed,
  active=true,rationale=excluded.rationale,metadata=penta_balancer.operation_policy_v1.metadata||excluded.metadata,
  updated_at=clock_timestamp();

insert into penta_balancer.cohesion_targets_v1(
  target_key,jobname,required_schedule,required_command,operation_key,owner_set,required,metadata
) values
('penta_tick','ct-pentatick-wake-v1','* * * * *','select pentatime.execute_guarded_v3(''penta_tick'');','penta_tick',array['PentaTick','PentaTime','PentaCrons'],true,jsonb_build_object('cohesion_weight',25)),
('penta_time','ct-pentatime-reconcile-v1','0,10,20,30,40,50 * * * *','select pentatime.pentacrons_reconcile_v1();',null,array['PentaTime','PentaCrons'],true,jsonb_build_object('cohesion_weight',25)),
('penta_clock','ct-pentaclock-dail-sync-v1','7,17,27,37,47,57 * * * *','select pentatime.execute_guarded_v3(''penta_clock'');','penta_clock',array['PentaClock','PentaTime','PentaCrons'],true,jsonb_build_object('cohesion_weight',25)),
('penta_balancer','ct-pentabalancer-control-v1','* * * * *','select pentatime.execute_guarded_v3(''penta_balancer'');','penta_balancer',array['PentaBalancer','PentaTime','PentaClock','PentaTick'],true,jsonb_build_object('cohesion_weight',25))
on conflict(target_key) do update set
  jobname=excluded.jobname,required_schedule=excluded.required_schedule,required_command=excluded.required_command,
  operation_key=excluded.operation_key,owner_set=excluded.owner_set,required=true,
  metadata=penta_balancer.cohesion_targets_v1.metadata||excluded.metadata,updated_at=clock_timestamp();

insert into pentatime.scheduler_registry(
  scheduler_name,cron_job_name,owner_layer,criticality,desired_state,recovery_policy,notes
) values(
  'PentaBalancer Control','ct-pentabalancer-control-v1','PentaBalancer/PentaTime/PentaClock/PentaTick','critical','active',
  'exact desired-state restore; bounded admission backoff; no permanent disable',
  'PentaBalancer performs scheduler load balancing and temporal cohesion only. All business and domain jobs remain owned by their existing Pentas.'
)
on conflict(scheduler_name) do update set
  cron_job_name=excluded.cron_job_name,owner_layer=excluded.owner_layer,criticality=excluded.criticality,
  desired_state='active',recovery_policy=excluded.recovery_policy,notes=excluded.notes,updated_at=clock_timestamp();

update public.penta_system_registry
set purpose='Deterministic scheduler load balancing, temporary admission pacing, redundancy restoration, and exact temporal cohesion with PentaTime, PentaClock, PentaTick, and PentaCrons.',
    authority_boundary='D0-D1 bounded load observation, temporary admission backoff, and exact scheduler cohesion only; no business workflow execution, provider write, money movement, content generation, self-approval, or D3 authority.',
    risk_ceiling='D1',runtime_ref='schema:penta_balancer/function:penta_balancer.control_tick_v1()',
    metadata=metadata||jsonb_build_object(
      'runtime_state','runtime_present_canary_pending','sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
      'cohesion_target',100,'cohesion_partners',jsonb_build_array('PentaTime','PentaClock','PentaTick','PentaCrons'),
      'admission_model','temporary_backoff_only_no_permanent_disable','smart_determination','deterministic_pressure_hysteresis',
      'authority_expansion',false
    ),updated_at=clock_timestamp()
where system_key='penta.balancer';

update integration_control.penta_identity_registry_v1
set maturity='implemented',activation_state='ACTIVE',runtime_state='RUNTIME_PRESENT',registration_state='live_runtime_canary_pending',
    labels=array_replace(array_replace(labels,'activation:active_fail_closed','activation:active'),'runtime:implemented_source','runtime:runtime_present'),
    metadata=metadata||jsonb_build_object('sole_responsibility','scheduler_load_balance_and_temporal_cohesion','cohesion_target',100,'authority_expansion',false),
    updated_at=clock_timestamp()
where identity_key='penta.balancer';

revoke all on all functions in schema penta_balancer from public, anon, authenticated;
grant execute on all functions in schema penta_balancer to service_role;



-- Applied migration 20260904064349: penta_balancer_nonblocking_admission_v1
set lock_timeout = '3s';
set statement_timeout = '45s';

create or replace function penta_balancer.apply_admission_v1(p_mode text, p_pressure_score integer)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_balancer, pentatime, pg_temp
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_released integer := 0;
  v_normal_deferred integer := 0;
  v_elastic_deferred integer := 0;
  v_rows integer := 0;
  v_state_rows integer := 0;
begin
  if p_mode not in ('NORMAL','WATCH','SHED','RECOVERY','HOLD') then
    raise exception 'invalid_balancer_mode:%',p_mode;
  end if;

  select count(*)::integer into v_state_rows
  from pentatime.operation_state_v2 s
  join penta_balancer.operation_policy_v1 p using(operation_key)
  where p.active;

  with candidates as (
    select s.operation_key
    from pentatime.operation_state_v2 s
    join penta_balancer.operation_policy_v1 p using(operation_key)
    where p.active
      and p.admission_class in ('critical','high')
      and coalesce(s.last_result->>'balancer_owned','false')='true'
    for update of s skip locked
  )
  update pentatime.operation_state_v2 s
     set backoff_until=null,
         consecutive_deferrals=0,
         last_state='BALANCER_RELEASED',
         last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
           ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
         updated_at=v_now
  from candidates c
  where c.operation_key=s.operation_key;
  get diagnostics v_rows=row_count;
  v_released:=v_released+v_rows;

  if p_mode='NORMAL' then
    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      where coalesce(s.last_result->>'balancer_owned','false')='true'
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=null,
           consecutive_deferrals=0,
           last_state='BALANCER_RELEASED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_rows=row_count;
    v_released:=v_released+v_rows;

  elsif p_mode='RECOVERY' then
    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      join penta_balancer.operation_policy_v1 p using(operation_key)
      where p.admission_class='normal'
        and coalesce(s.last_result->>'balancer_owned','false')='true'
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=null,
           consecutive_deferrals=0,
           last_state='BALANCER_RELEASED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_rows=row_count;
    v_released:=v_released+v_rows;

    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      join penta_balancer.operation_policy_v1 p using(operation_key)
      where p.active and p.shed_allowed and p.admission_class='elastic'
        and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true')
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '30 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_RECOVERY_PACING',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',30,'decided_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_elastic_deferred=row_count;

  elsif p_mode='WATCH' then
    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      join penta_balancer.operation_policy_v1 p using(operation_key)
      where p.admission_class='normal'
        and coalesce(s.last_result->>'balancer_owned','false')='true'
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=null,
           consecutive_deferrals=0,
           last_state='BALANCER_RELEASED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',false,'balancer_mode',p_mode,'released_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_rows=row_count;
    v_released:=v_released+v_rows;

    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      join penta_balancer.operation_policy_v1 p using(operation_key)
      where p.active and p.shed_allowed and p.admission_class='elastic'
        and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true')
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '75 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_WATCH_DEFERRED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',75,'decided_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_elastic_deferred=row_count;

  else
    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      join penta_balancer.operation_policy_v1 p using(operation_key)
      where p.active and p.shed_allowed and p.admission_class='normal'
        and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true')
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '90 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_SHED_DEFERRED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',90,'decided_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_normal_deferred=row_count;

    with candidates as (
      select s.operation_key
      from pentatime.operation_state_v2 s
      join penta_balancer.operation_policy_v1 p using(operation_key)
      where p.active and p.shed_allowed and p.admission_class='elastic'
        and (s.backoff_until is null or s.backoff_until<=v_now or coalesce(s.last_result->>'balancer_owned','false')='true')
      for update of s skip locked
    )
    update pentatime.operation_state_v2 s
       set backoff_until=v_now+interval '180 seconds',
           last_deferred_at=v_now,
           last_state='BALANCER_SHED_DEFERRED',
           last_result=(case when jsonb_typeof(coalesce(s.last_result,'{}'::jsonb))='object' then coalesce(s.last_result,'{}'::jsonb) else '{}'::jsonb end)
             ||jsonb_build_object('balancer_owned',true,'balancer_mode',p_mode,'pressure_score',p_pressure_score,'defer_seconds',180,'decided_at',v_now),
           updated_at=v_now
    from candidates c
    where c.operation_key=s.operation_key;
    get diagnostics v_elastic_deferred=row_count;
  end if;

  return jsonb_build_object(
    'state','APPLIED','mode',p_mode,'pressure_score',p_pressure_score,
    'state_rows_observed',v_state_rows,'released',v_released,
    'normal_deferred',v_normal_deferred,'elastic_deferred',v_elastic_deferred,
    'concurrency_policy','skip_locked','permanent_disables',0,
    'authority_created',false,'observed_at',v_now
  );
end;
$$;

revoke all on function penta_balancer.apply_admission_v1(text,integer) from public, anon, authenticated;
grant execute on function penta_balancer.apply_admission_v1(text,integer) to service_role;


-- Applied migration 20260904065235: penta_specialist_maturation_controller_v1
set lock_timeout='3s';
set statement_timeout='60s';

create or replace function integration_control.penta_specialist_maturation_refresh_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,public,extensions,pg_temp
as $$
declare
  v_rows integer:=0;
  v_now timestamptz:=clock_timestamp();
begin
  with source_rows as (
    select
      s.system_key,
      s.version,
      s.canonical_name,
      s.maturity,
      s.runtime_ref,
      s.risk_ceiling,
      br.id as build_request_id,
      br.status as build_status,
      exists(
        select 1 from public.penta_system_production_receipts_v1 r
        where r.system_key=s.system_key and r.system_version=s.version and r.passed
          and not r.provider_write and not r.money_movement and not r.d3_effect
          and coalesce((r.evidence->>'semantic_pass')::boolean,false)
      ) as exact_nonprovider_receipt,
      exists(
        select 1 from public.penta_system_production_receipts_v1 r
        where r.system_key=s.system_key and r.system_version=s.version and r.passed
          and r.provider_write and not r.money_movement and not r.d3_effect
      ) as exact_provider_receipt
    from public.penta_system_registry s
    left join public.ct_factory_build_requests br
      on br.request_key='penta-helper:productionize:'||s.system_key||':'||s.version
    where s.system_key like 'penta.%'
  ), classified as (
    select sr.*,
      case
        when sr.maturity='production' then 'production'
        when sr.exact_nonprovider_receipt then 'promote_ready'
        when sr.exact_provider_receipt then 'provider_promote_ready'
        when sr.build_status in ('failed','hold','cancelled') then 'repair_retry'
        when sr.runtime_ref is not null then 'canary_certify'
        when sr.maturity='implemented' then 'runtime_build'
        else 'implementation_build'
      end as disposition,
      case
        when sr.maturity='production' then array['PentaCertify','PentaCensus']::text[]
        when sr.exact_nonprovider_receipt or sr.exact_provider_receipt then array['PentaCertify','PentaCensus']::text[]
        when sr.build_status in ('failed','hold','cancelled') then array['PentaHeal','PentaFactory','PentaTest','PentaCertify']::text[]
        when sr.runtime_ref is not null then array['PentaTest','PentaSecurity','PentaCertify','PentaWire']::text[]
        when sr.maturity='implemented' then array['PentaFactory','PentaBuild','PentaTest','PentaSecurity','PentaCertify']::text[]
        else array['PentaPlanner','PentaFactory','PentaBuild','PentaTest','PentaSecurity','PentaCertify']::text[]
      end as assigned_pentas,
      case
        when sr.maturity='production' then 100
        when sr.exact_nonprovider_receipt or sr.exact_provider_receipt then 100
        when sr.build_status in ('failed','hold','cancelled') then 95
        when sr.runtime_ref is not null then 90
        when sr.maturity='implemented' then 80
        else 60
      end as priority,
      case
        when sr.maturity='production' then 'verified'
        when sr.exact_nonprovider_receipt or sr.exact_provider_receipt then 'in_progress'
        when sr.build_status='queued' then 'routed'
        when sr.build_status in ('claimed','building','validating','approved','implemented') then 'in_progress'
        when sr.build_status='hold' then 'held'
        when sr.build_status in ('failed','cancelled') then 'failed'
        else 'queued'
      end as mobilization_state
    from source_rows sr
  ), prepared as (
    select c.*,
      jsonb_build_object(
        'contract','ct.penta.specialist-maturation.v1',
        'system_key',c.system_key,'system_version',c.version,'canonical_name',c.canonical_name,
        'source_maturity',c.maturity,'runtime_ref',c.runtime_ref,'risk_ceiling',c.risk_ceiling,
        'disposition',c.disposition,'assigned_pentas',to_jsonb(c.assigned_pentas),'priority',c.priority,
        'build_request_id',c.build_request_id,'build_status',c.build_status,
        'exact_nonprovider_receipt',c.exact_nonprovider_receipt,'exact_provider_receipt',c.exact_provider_receipt,
        'determination_model','deterministic_evidence_directed',
        'production_requires_exact_receipt',true,'blanket_promotion_forbidden',true,
        'authority_created',false,'assessed_at',v_now
      ) as evidence
    from classified c
  )
  insert into integration_control.penta_production_mobilization_v1(
    handoff_key,discovery_key,entity_kind,entity_key,tag,risk_class,target_ref,target_node_id,
    packet_id,state,evidence_sha256,evidence,created_at,updated_at,completed_at
  )
  select
    'ct.penta.specialist-production:'||p.system_key||':'||p.version,
    'ct.campaign.all-pentas-production-government.v1','system',p.system_key,p.disposition,
    case when p.risk_ceiling in ('D0','D1','D2') then p.risk_ceiling else 'D2' end,
    'factory://crownthrive-os-v2-factory/'||p.system_key||'/'||p.version,
    p.assigned_pentas[1],null,p.mobilization_state,
    encode(extensions.digest(convert_to(p.evidence::text,'UTF8'),'sha256'),'hex'),p.evidence,
    v_now,v_now,case when p.mobilization_state='verified' then v_now else null end
  from prepared p
  on conflict(handoff_key) do update set
    discovery_key=excluded.discovery_key,entity_kind=excluded.entity_kind,entity_key=excluded.entity_key,
    tag=excluded.tag,risk_class=excluded.risk_class,target_ref=excluded.target_ref,target_node_id=excluded.target_node_id,
    state=excluded.state,evidence_sha256=excluded.evidence_sha256,
    evidence=integration_control.penta_production_mobilization_v1.evidence||excluded.evidence,
    updated_at=v_now,
    completed_at=case when excluded.state='verified' then coalesce(integration_control.penta_production_mobilization_v1.completed_at,v_now) else null end;
  get diagnostics v_rows=row_count;

  update public.penta_system_registry s
     set metadata=s.metadata||jsonb_build_object(
       'specialist_maturation_lane',m.tag,
       'specialist_maturation_state',m.state,
       'specialist_maturation_target',m.target_node_id,
       'specialist_maturation_assessed_at',v_now,
       'smart_determination','deterministic_evidence_directed',
       'blanket_promotion',false
     ),updated_at=v_now
  from integration_control.penta_production_mobilization_v1 m
  where m.handoff_key='ct.penta.specialist-production:'||s.system_key||':'||s.version
    and s.system_key like 'penta.%';

  return jsonb_build_object(
    'state','REFRESHED','rows',v_rows,
    'production',(select count(*) from public.penta_system_registry where system_key like 'penta.%' and maturity='production'),
    'nonproduction',(select count(*) from public.penta_system_registry where system_key like 'penta.%' and maturity<>'production'),
    'by_disposition',coalesce((
      select jsonb_object_agg(tag,n) from (
        select tag,count(*)::integer n
        from integration_control.penta_production_mobilization_v1
        where handoff_key like 'ct.penta.specialist-production:%'
        group by tag order by tag
      ) x
    ),'{}'::jsonb),
    'authority_created',false,'observed_at',v_now
  );
end;
$$;

create or replace function integration_control.penta_specialist_promote_ready_v1(p_limit integer default 25)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,public,extensions,pg_temp
as $$
declare
  r record;
  v_result jsonb;
  v_promoted integer:=0;
  v_failed integer:=0;
  v_details jsonb:='[]'::jsonb;
  v_error text;
  v_now timestamptz:=clock_timestamp();
begin
  p_limit:=greatest(1,least(coalesce(p_limit,25),50));

  for r in
    select s.system_key,s.version,
      exists(
        select 1 from public.penta_system_production_receipts_v1 x
        where x.system_key=s.system_key and x.system_version=s.version and x.passed
          and not x.provider_write and not x.money_movement and not x.d3_effect
          and coalesce((x.evidence->>'semantic_pass')::boolean,false)
      ) as has_nonprovider,
      exists(
        select 1 from public.penta_system_production_receipts_v1 x
        where x.system_key=s.system_key and x.system_version=s.version and x.passed
          and x.provider_write and not x.money_movement and not x.d3_effect
      ) as has_provider
    from public.penta_system_registry s
    where s.system_key like 'penta.%' and s.maturity<>'production'
      and exists(
        select 1 from public.penta_system_production_receipts_v1 x
        where x.system_key=s.system_key and x.system_version=s.version and x.passed
          and not x.money_movement and not x.d3_effect
      )
    order by case when s.runtime_ref is not null then 0 else 1 end,s.system_key
    limit p_limit
  loop
    begin
      if r.has_nonprovider then
        v_result:=public.penta_promote_from_production_receipt_v1(r.system_key);
      elsif r.has_provider then
        v_result:=public.penta_promote_provider_production_receipt_v1(r.system_key);
      else
        continue;
      end if;

      if coalesce(v_result->>'state','')='PRODUCTION' then
        v_promoted:=v_promoted+1;
        update integration_control.penta_identity_registry_v1 i
           set maturity='production',activation_state='ACTIVE',runtime_state='RUNTIME_PRESENT',registration_state='live_runtime',
               labels=case when array_position(i.labels,'maturity:implemented') is not null then array_replace(i.labels,'maturity:implemented','maturity:production')
                           when array_position(i.labels,'maturity:specified') is not null then array_replace(i.labels,'maturity:specified','maturity:production')
                           else i.labels end,
               metadata=i.metadata||jsonb_build_object('specialist_production_promoted_at',v_now,'authority_expansion',false),
               updated_at=v_now
         where i.identity_key=r.system_key;

        update integration_control.penta_production_mobilization_v1 m
           set state='verified',tag='production',completed_at=coalesce(completed_at,v_now),updated_at=v_now,
               evidence=m.evidence||jsonb_build_object('promotion_result',v_result,'promoted_at',v_now,'authority_created',false),
               evidence_sha256=encode(extensions.digest(convert_to((m.evidence||jsonb_build_object('promotion_result',v_result,'promoted_at',v_now,'authority_created',false))::text,'UTF8'),'sha256'),'hex')
         where m.handoff_key='ct.penta.specialist-production:'||r.system_key||':'||r.version;
      else
        v_failed:=v_failed+1;
      end if;
      v_details:=v_details||jsonb_build_array(jsonb_build_object('system_key',r.system_key,'result',v_result));
    exception when others then
      v_error:=sqlstate||':'||sqlerrm;
      v_failed:=v_failed+1;
      update integration_control.penta_production_mobilization_v1 m
         set state='failed',updated_at=v_now,
             evidence=m.evidence||jsonb_build_object('promotion_error_sqlstate',sqlstate,'promotion_error_sha256',encode(extensions.digest(convert_to(v_error,'UTF8'),'sha256'),'hex'),'failed_at',v_now),
             evidence_sha256=encode(extensions.digest(convert_to((m.evidence||jsonb_build_object('promotion_error_sqlstate',sqlstate,'failed_at',v_now))::text,'UTF8'),'sha256'),'hex')
       where m.handoff_key='ct.penta.specialist-production:'||r.system_key||':'||r.version;
      v_details:=v_details||jsonb_build_array(jsonb_build_object('system_key',r.system_key,'state','FAILED','sqlstate',sqlstate));
    end;
  end loop;

  return jsonb_build_object('state','COMPLETED','promoted',v_promoted,'failed',v_failed,'details',v_details,'authority_created',false,'observed_at',v_now);
end;
$$;

create or replace function integration_control.penta_specialist_maturation_tick_v1(p_limit integer default 20)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,public,penta_balancer,extensions,pg_temp
as $$
declare
  r record;
  v_mode text:='WATCH';
  v_effective integer:=0;
  v_refresh jsonb;
  v_promotions jsonb;
  v_dispatch jsonb;
  v_build_id uuid;
  v_dispatched integer:=0;
  v_failed integer:=0;
  v_details jsonb:='[]'::jsonb;
  v_error text;
  v_evidence jsonb;
  v_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  perform set_config('lock_timeout','2s',true);
  perform set_config('statement_timeout','45s',true);

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:specialist-maturation:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','authority_created',false,'observed_at',v_now);
  end if;

  select mode into v_mode from penta_balancer.control_state_v1 where singleton_key='primary';
  v_mode:=coalesce(v_mode,'WATCH');
  p_limit:=greatest(1,least(coalesce(p_limit,20),50));
  v_effective:=case v_mode when 'HOLD' then 0 when 'SHED' then 1 when 'WATCH' then least(3,p_limit) when 'RECOVERY' then least(8,p_limit) else p_limit end;

  v_refresh:=integration_control.penta_specialist_maturation_refresh_v1();
  v_promotions:=integration_control.penta_specialist_promote_ready_v1(25);

  if v_effective>0 then
    for r in
      select m.handoff_key,m.entity_key as system_key,m.tag,m.state,m.evidence,
             coalesce((m.evidence->>'priority')::integer,50) as priority,
             coalesce(array(select jsonb_array_elements_text(m.evidence->'assigned_pentas')),'{}'::text[]) as assigned_pentas
      from integration_control.penta_production_mobilization_v1 m
      join public.penta_system_registry s on s.system_key=m.entity_key
      where m.handoff_key like 'ct.penta.specialist-production:%'
        and s.maturity<>'production'
        and m.tag not in ('promote_ready','provider_promote_ready','production')
        and m.state in ('queued','failed','held')
      order by coalesce((m.evidence->>'priority')::integer,50) desc,m.updated_at,m.entity_key
      limit v_effective
      for update of m skip locked
    loop
      begin
        v_dispatch:=public.penta_helper_request_productionization_v1(r.system_key,null);
        v_build_id:=nullif(v_dispatch->>'build_request_id','')::uuid;

        if v_build_id is not null then
          update public.ct_factory_build_requests b
             set priority=greatest(b.priority,r.priority),
                 requirements=(case when jsonb_typeof(coalesce(b.requirements,'{}'::jsonb))='object' then coalesce(b.requirements,'{}'::jsonb) else jsonb_build_object('legacy_requirements',b.requirements) end)
                   ||jsonb_build_object(
                     'specialist_maturation_lane',r.tag,
                     'assigned_pentas',to_jsonb(r.assigned_pentas),
                     'penta_balancer_mode',v_mode,
                     'production_requires_exact_receipt',true,
                     'smart_determination','deterministic_evidence_directed',
                     'authority_created',false
                   ),
                 evidence=coalesce(b.evidence,'{}'::jsonb)||jsonb_build_object(
                   'maturation_controller','PentaCertify/PentaHelper/PentaFactory/PentaTest',
                   'penta_balancer_mode_at_dispatch',v_mode,'dispatched_at',v_now,'authority_expansion',false
                 ),
                 updated_at=v_now
           where b.id=v_build_id;
        end if;

        update integration_control.penta_production_mobilization_v1 m
           set state='routed',target_node_id=coalesce(r.assigned_pentas[1],target_node_id),updated_at=v_now,
               evidence=m.evidence||jsonb_build_object('dispatch_result',v_dispatch,'dispatched_at',v_now,'penta_balancer_mode',v_mode,'authority_created',false),
               evidence_sha256=encode(extensions.digest(convert_to((m.evidence||jsonb_build_object('dispatch_result',v_dispatch,'dispatched_at',v_now,'penta_balancer_mode',v_mode,'authority_created',false))::text,'UTF8'),'sha256'),'hex')
         where m.handoff_key=r.handoff_key;
        v_dispatched:=v_dispatched+1;
        v_details:=v_details||jsonb_build_array(jsonb_build_object('system_key',r.system_key,'lane',r.tag,'build_request_id',v_build_id,'state',v_dispatch->>'state'));
      exception when others then
        v_error:=sqlstate||':'||sqlerrm;
        v_failed:=v_failed+1;
        update integration_control.penta_production_mobilization_v1 m
           set state='failed',updated_at=v_now,
               evidence=m.evidence||jsonb_build_object('dispatch_error_sqlstate',sqlstate,'dispatch_error_sha256',encode(extensions.digest(convert_to(v_error,'UTF8'),'sha256'),'hex'),'failed_at',v_now),
               evidence_sha256=encode(extensions.digest(convert_to((m.evidence||jsonb_build_object('dispatch_error_sqlstate',sqlstate,'failed_at',v_now))::text,'UTF8'),'sha256'),'hex')
         where m.handoff_key=r.handoff_key;
        v_details:=v_details||jsonb_build_array(jsonb_build_object('system_key',r.system_key,'state','FAILED','sqlstate',sqlstate));
      end;
    end loop;
  end if;

  v_evidence:=jsonb_build_object(
    'contract','ct.penta.specialist-maturation.v1','controller','PentaCertify/PentaHelper/PentaFactory/PentaTest/PentaSecurity',
    'penta_balancer_mode',v_mode,'requested_limit',p_limit,'effective_limit',v_effective,
    'refresh',v_refresh,'promotions',v_promotions,'dispatched',v_dispatched,'dispatch_failed',v_failed,'details',v_details,
    'new_scheduler_created',false,'existing_scheduler','penta-certify-production-classifier-v1',
    'blanket_promotion',false,'production_requires_exact_receipt',true,'authority_created',false,'observed_at',v_now
  );
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.penta_certify_receipts_v3(event_type,state,evidence)
  values('penta.certify.specialist-maturation',case when v_failed=0 then 'completed' else 'partial' end,v_evidence||jsonb_build_object('evidence_sha256',v_sha));

  update integration_control.penta_production_campaigns_v1 c
     set metadata=c.metadata||jsonb_build_object(
       'specialist_maturation_controller','PentaCertify/PentaHelper/PentaFactory/PentaTest/PentaSecurity',
       'specialist_maturation_existing_clock','penta-certify-production-classifier-v1',
       'specialist_maturation_last_mode',v_mode,
       'specialist_maturation_last_run_at',v_now,
       'specialist_maturation_last_evidence_sha256',v_sha,
       'specialist_maturation_exact_receipt_required',true,
       'no_duplicate_clock',true,'authority_created',false
     ),last_cycle_at=v_now,updated_at=v_now
   where c.campaign_key='ct.campaign.all-pentas-production-government.v1';

  return jsonb_build_object('state',case when v_effective=0 then 'DEFERRED_BY_BALANCER' else 'COMPLETED' end,
    'penta_balancer_mode',v_mode,'effective_limit',v_effective,'promotions',v_promotions,
    'dispatched',v_dispatched,'dispatch_failed',v_failed,'details',v_details,'evidence_sha256',v_sha,
    'authority_created',false,'observed_at',v_now);
end;
$$;

create or replace function pentatime.executor_production_classifier_v3()
returns jsonb
language sql
security definer
set search_path=pg_catalog,integration_control
as $$
select jsonb_build_object(
  'classify',integration_control.penta_certify_classify_production_dispositions_v1(),
  'resolve',integration_control.penta_certify_resolve_nonblocking_dispositions_v3(),
  'specialist_maturation',integration_control.penta_specialist_maturation_tick_v1(20)
);
$$;

update pentatime.operation_registry_v2
set owner_penta='PentaCertify/PentaHelper/PentaFactory/PentaTest/PentaSecurity',
    metadata=metadata||jsonb_build_object(
      'specialist_maturation','ct.penta.specialist-maturation.v1',
      'adaptive_to_pentabalancer',true,'exact_receipt_required',true,
      'existing_clock_reused',true,'new_clock_created',false,'authority_created',false
    ),updated_at=clock_timestamp()
where operation_key='production_classifier';

update penta_balancer.operation_policy_v1
set admission_class='high',priority=85,shed_allowed=false,
    rationale='PentaCertify production classification remains available; specialist dispatch self-throttles against PentaBalancer mode.',
    metadata=metadata||jsonb_build_object('adaptive_internal_dispatch',true,'authority_created',false),updated_at=clock_timestamp()
where operation_key='production_classifier';

revoke all on function integration_control.penta_specialist_maturation_refresh_v1() from public,anon,authenticated;
revoke all on function integration_control.penta_specialist_promote_ready_v1(integer) from public,anon,authenticated;
revoke all on function integration_control.penta_specialist_maturation_tick_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.penta_specialist_maturation_refresh_v1() to service_role;
grant execute on function integration_control.penta_specialist_promote_ready_v1(integer) to service_role;
grant execute on function integration_control.penta_specialist_maturation_tick_v1(integer) to service_role;



-- Applied migration 20260904065745: penta_balancer_production_metadata_and_rebalance_stamp_v1
set lock_timeout='3s';
set statement_timeout='45s';

create or replace function penta_balancer.control_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_balancer, pentatime, chlom_runtime, extensions, pg_temp
as $$
declare
  v_prev penta_balancer.control_state_v1%rowtype;
  v_metrics jsonb;
  v_cohesion jsonb;
  v_repair jsonb;
  v_admission jsonb;
  v_mode text;
  v_pressure integer;
  v_session_pct numeric;
  v_lock_waiters integer;
  v_startup integer;
  v_statements integer;
  v_deadlocks integer;
  v_connections integer;
  v_running integer;
  v_runner_ceiling integer;
  v_severe boolean;
  v_watch boolean;
  v_consecutive_pressure integer;
  v_consecutive_clear integer;
  v_cohesion_score integer;
  v_now timestamptz:=clock_timestamp();
  v_decision jsonb;
  v_event_payload jsonb;
  v_event_sha text;
  v_dail jsonb;
  v_dail_state text:='not_required';
begin
  perform set_config('lock_timeout','2s',true);
  perform set_config('statement_timeout','25s',true);

  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:control:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','authority_created',false,'observed_at',v_now);
  end if;

  select * into v_prev from penta_balancer.control_state_v1 where singleton_key='primary' for update;
  if not found then
    insert into penta_balancer.control_state_v1(singleton_key) values('primary') returning * into v_prev;
  end if;

  v_metrics:=penta_balancer.pressure_snapshot_v1();
  v_pressure:=coalesce((v_metrics->>'pressure_score')::integer,0);
  v_session_pct:=coalesce((v_metrics->>'session_pct')::numeric,0);
  v_lock_waiters:=coalesce((v_metrics->>'lock_waiters')::integer,0);
  v_startup:=coalesce((v_metrics->>'startup_timeouts_15m')::integer,0);
  v_statements:=coalesce((v_metrics->>'statement_timeouts_15m')::integer,0);
  v_deadlocks:=coalesce((v_metrics->>'deadlocks_15m')::integer,0);
  v_connections:=coalesce((v_metrics->>'connection_failures_15m')::integer,0);
  v_running:=coalesce((v_metrics->>'running_cron_jobs')::integer,0);
  v_runner_ceiling:=coalesce((v_metrics->>'runner_ceiling')::integer,32);

  v_severe := v_session_pct>=85 or v_lock_waiters>=8 or (v_startup+v_connections)>=10 or v_statements>=20 or v_running>=v_runner_ceiling;
  v_watch := v_session_pct>=65 or v_lock_waiters>=3 or (v_startup+v_connections)>=3 or v_statements>=8 or v_deadlocks>=1;

  v_consecutive_pressure:=case when v_severe or v_watch then v_prev.consecutive_pressure+1 else 0 end;
  v_consecutive_clear:=case when not v_severe and not v_watch then v_prev.consecutive_clear+1 else 0 end;

  if v_severe then v_mode:='SHED';
  elsif v_watch then v_mode:='WATCH';
  elsif v_prev.mode in ('SHED','WATCH','RECOVERY','HOLD') and v_consecutive_clear<3 then v_mode:='RECOVERY';
  else v_mode:='NORMAL';
  end if;

  v_cohesion:=penta_balancer.cohesion_snapshot_v1();
  v_cohesion_score:=coalesce((v_cohesion->>'cohesion_score')::integer,0);
  if v_cohesion_score<100 then
    v_repair:=penta_balancer.ensure_core_cohesion_v1();
    v_cohesion:=coalesce(v_repair->'after',v_cohesion);
    v_cohesion_score:=coalesce((v_cohesion->>'cohesion_score')::integer,0);
    if v_cohesion_score<100 then v_mode:='HOLD'; end if;
  end if;

  v_admission:=penta_balancer.apply_admission_v1(v_mode,v_pressure);
  v_decision:=jsonb_build_object(
    'mode',v_mode,'pressure_score',v_pressure,'cohesion_score',v_cohesion_score,
    'admission',v_admission,'cohesion',v_cohesion,'cohesion_repair',v_repair,
    'sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
    'business_work_executed',false,'provider_write',false,'money_movement',false,'d3_effect',false,
    'decided_at',v_now
  );

  update penta_balancer.control_state_v1
     set mode=v_mode,pressure_score=v_pressure,cohesion_score=v_cohesion_score,
         consecutive_pressure=v_consecutive_pressure,consecutive_clear=v_consecutive_clear,
         metrics=v_metrics,last_decision=v_decision,
         last_transition_at=case when v_prev.mode is distinct from v_mode then v_now else v_prev.last_transition_at end,
         last_reconcile_at=case when v_repair is not null then v_now else v_prev.last_reconcile_at end,
         last_rebalance_at=v_now,
         updated_at=v_now
   where singleton_key='primary';

  if v_prev.mode is distinct from v_mode or v_prev.cohesion_score is distinct from v_cohesion_score or extract(minute from v_now)::integer=0 then
    v_event_payload:=jsonb_build_object(
      'prior_mode',v_prev.mode,'decided_mode',v_mode,'pressure_score',v_pressure,'cohesion_score',v_cohesion_score,
      'metrics',v_metrics,'decision',v_decision,'observed_at',v_now
    );
    v_event_sha:=encode(extensions.digest(convert_to(v_event_payload::text,'UTF8'),'sha256'),'hex');
    insert into penta_balancer.decision_events_v1(
      observed_at,prior_mode,decided_mode,pressure_score,cohesion_score,metrics,decision,evidence_sha256
    ) values(v_now,v_prev.mode,v_mode,v_pressure,v_cohesion_score,v_metrics,v_decision,v_event_sha);

    if pg_try_advisory_xact_lock(hashtext('chlom_runtime.dail.global.v1')) then
      begin
        v_dail:=chlom_runtime.append_dail_event(
          'penta.balancer.control-decision','scheduler_load_balance','penta.balancer',
          v_event_payload||jsonb_build_object('evidence_sha256',v_event_sha,'authority_created',false),
          'PentaBalancer/PentaTime/PentaClock/PentaTick',null,'PentaBalancer','1.0.0',
          v_event_sha,'penta_balancer.control_tick_v1()','ct.scheduler-topology.production.v1',null,'internal'
        );
        v_dail_state:='recorded';
      exception when others then
        v_dail_state:='deferred_error:'||sqlstate;
      end;
    else
      v_dail_state:='deferred_lock_busy';
    end if;
  end if;

  return jsonb_build_object(
    'state','SUCCEEDED','mode',v_mode,'pressure_score',v_pressure,'cohesion_score',v_cohesion_score,
    'metrics',v_metrics,'admission',v_admission,'cohesion',v_cohesion,'dail_state',v_dail_state,
    'last_rebalance_at',v_now,'authority_created',false,'observed_at',v_now
  );
end;
$$;

update public.penta_system_registry s
set metadata=s.metadata||jsonb_build_object(
      'runtime_state','production_verified',
      'production_receipt_id','19566a4d-0703-4ead-8300-5aee2cdec842',
      'production_evidence_sha256','2d6a553db545581b26af155168ab7f2e15f4ad7a7c00d47318989d61ed2fdf3',
      'production_verified_at',clock_timestamp(),
      'cohesion_target',100,
      'authority_expansion',false
    ),
    updated_at=clock_timestamp()
where s.system_key='penta.balancer' and s.maturity='production';

update integration_control.penta_identity_registry_v1 i
set metadata=i.metadata||jsonb_build_object(
      'runtime_state','production_verified',
      'production_receipt_id','19566a4d-0703-4ead-8300-5aee2cdec842',
      'production_evidence_sha256','2d6a553db545581b26af155168ab7f2e15f4ad7a7c00d47318989d61ed2fdf3',
      'cohesion_target',100,
      'authority_expansion',false
    ),
    updated_at=clock_timestamp()
where i.identity_key='penta.balancer' and i.maturity='production';

revoke all on function penta_balancer.control_tick_v1() from public,anon,authenticated;
grant execute on function penta_balancer.control_tick_v1() to service_role;


-- Applied migration 20260904070313: penta_balancer_managed_job_admission_v1
set lock_timeout='3s';
set statement_timeout='60s';

create table if not exists penta_balancer.job_policy_v1 (
  jobname text primary key,
  original_schedule text not null,
  original_command text not null,
  original_command_sha256 text not null check (original_command_sha256 ~ '^[0-9a-f]{64}$'),
  admission_class text not null check (admission_class in ('critical','high','normal','elastic')),
  priority integer not null check (priority between 0 and 100),
  shed_allowed boolean not null default true,
  cooldown_seconds integer not null default 0 check (cooldown_seconds between 0 and 86400),
  max_runtime_seconds integer not null default 180 check (max_runtime_seconds between 5 and 900),
  owner_penta text not null,
  rationale text not null,
  source_ref text not null default 'ct.pentabalancer.managed-job-admission.v1',
  active boolean not null default true,
  instrumented boolean not null default false,
  instrumented_at timestamptz,
  restored_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create table if not exists penta_balancer.job_state_v1 (
  jobname text primary key references penta_balancer.job_policy_v1(jobname) on update cascade on delete cascade,
  last_attempt_at timestamptz,
  last_admitted_at timestamptz,
  last_completed_at timestamptz,
  last_deferred_at timestamptz,
  last_state text,
  last_mode text,
  last_duration_ms bigint,
  admitted_count bigint not null default 0,
  completed_count bigint not null default 0,
  deferred_count bigint not null default 0,
  overlap_deferred_count bigint not null default 0,
  cooldown_deferred_count bigint not null default 0,
  pressure_deferred_count bigint not null default 0,
  last_result jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

create index if not exists penta_balancer_job_policy_class_idx
  on penta_balancer.job_policy_v1(admission_class,priority desc) where active and instrumented;
create index if not exists penta_balancer_job_state_completed_idx
  on penta_balancer.job_state_v1(last_completed_at desc);
create index if not exists penta_balancer_job_state_deferred_idx
  on penta_balancer.job_state_v1(last_deferred_at desc) where deferred_count>0;

alter table penta_balancer.job_policy_v1 enable row level security;
alter table penta_balancer.job_state_v1 enable row level security;
revoke all on penta_balancer.job_policy_v1,penta_balancer.job_state_v1 from public,anon,authenticated;
grant select on penta_balancer.job_policy_v1,penta_balancer.job_state_v1 to service_role;

create or replace function penta_balancer.executor_authorized_v1()
returns boolean
language sql
stable
security definer
set search_path=pg_catalog,pg_temp
as $$
select session_user in ('postgres','supabase_admin')
   or coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')='service_role';
$$;

create or replace function penta_balancer.execute_managed_job_v1(p_jobname text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,extensions,pg_temp
as $$
declare
  p penta_balancer.job_policy_v1%rowtype;
  s penta_balancer.job_state_v1%rowtype;
  v_mode text:='WATCH';
  v_now timestamptz:=clock_timestamp();
  v_started timestamptz;
  v_duration_ms bigint;
  v_allowed boolean:=false;
  v_reason text;
  v_actual_sha text;
  v_result jsonb;
begin
  if not penta_balancer.executor_authorized_v1() then
    raise exception 'service_role_required';
  end if;
  if p_jobname is null or btrim(p_jobname)='' then raise exception 'jobname_required'; end if;

  select * into p from penta_balancer.job_policy_v1 where jobname=p_jobname and active and instrumented;
  if not found then raise exception 'managed_job_policy_not_active:%',p_jobname; end if;

  v_actual_sha:=encode(extensions.digest(convert_to(p.original_command,'UTF8'),'sha256'),'hex');
  if v_actual_sha is distinct from p.original_command_sha256 then
    raise exception 'managed_job_command_integrity_failed:%',p_jobname;
  end if;
  if p.original_command !~* '^\s*(select|call)\b' then
    raise exception 'managed_job_command_not_permitted:%',p_jobname;
  end if;

  insert into penta_balancer.job_state_v1(jobname) values(p_jobname)
  on conflict(jobname) do nothing;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:managed-job:'||p_jobname,0)) then
    update penta_balancer.job_state_v1
       set last_attempt_at=v_now,last_deferred_at=v_now,last_state='DEFERRED_OVERLAP',
           overlap_deferred_count=overlap_deferred_count+1,deferred_count=deferred_count+1,
           last_result=jsonb_build_object('state','DEFERRED_OVERLAP','jobname',p_jobname,'authority_created',false,'observed_at',v_now),
           updated_at=v_now
     where jobname=p_jobname;
    return jsonb_build_object('state','DEFERRED_OVERLAP','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;

  select * into s from penta_balancer.job_state_v1 where jobname=p_jobname for update;
  select mode into v_mode from penta_balancer.control_state_v1 where singleton_key='primary';
  v_mode:=coalesce(v_mode,'WATCH');

  if p.cooldown_seconds>0 and s.last_completed_at is not null
     and s.last_completed_at+make_interval(secs=>p.cooldown_seconds)>v_now then
    v_reason:='cooldown_until:'||(s.last_completed_at+make_interval(secs=>p.cooldown_seconds))::text;
    update penta_balancer.job_state_v1
       set last_attempt_at=v_now,last_deferred_at=v_now,last_state='DEFERRED_COOLDOWN',last_mode=v_mode,
           cooldown_deferred_count=cooldown_deferred_count+1,deferred_count=deferred_count+1,
           last_result=jsonb_build_object('state','DEFERRED_COOLDOWN','jobname',p_jobname,'mode',v_mode,
             'cooldown_seconds',p.cooldown_seconds,'reason',v_reason,'authority_created',false,'observed_at',v_now),
           updated_at=v_now
     where jobname=p_jobname;
    return jsonb_build_object('state','DEFERRED_COOLDOWN','jobname',p_jobname,'mode',v_mode,
      'cooldown_seconds',p.cooldown_seconds,'reason',v_reason,'authority_created',false,'observed_at',v_now);
  end if;

  v_allowed:=case p.admission_class
    when 'critical' then true
    when 'high' then true
    when 'normal' then v_mode in ('NORMAL','RECOVERY') or (v_mode='WATCH' and p.priority>=70)
    when 'elastic' then v_mode='NORMAL' or (v_mode='RECOVERY' and p.priority>=70)
    else false end;

  if not v_allowed then
    v_reason:='mode_'||lower(v_mode)||'_class_'||p.admission_class;
    update penta_balancer.job_state_v1
       set last_attempt_at=v_now,last_deferred_at=v_now,last_state='DEFERRED_PRESSURE',last_mode=v_mode,
           pressure_deferred_count=pressure_deferred_count+1,deferred_count=deferred_count+1,
           last_result=jsonb_build_object('state','DEFERRED_PRESSURE','jobname',p_jobname,'mode',v_mode,
             'admission_class',p.admission_class,'priority',p.priority,'reason',v_reason,
             'authority_created',false,'observed_at',v_now),updated_at=v_now
     where jobname=p_jobname;
    return jsonb_build_object('state','DEFERRED_PRESSURE','jobname',p_jobname,'mode',v_mode,
      'admission_class',p.admission_class,'priority',p.priority,'reason',v_reason,
      'authority_created',false,'observed_at',v_now);
  end if;

  v_started:=clock_timestamp();
  update penta_balancer.job_state_v1
     set last_attempt_at=v_now,last_admitted_at=v_started,last_state='ADMITTED',last_mode=v_mode,
         admitted_count=admitted_count+1,
         last_result=jsonb_build_object('state','ADMITTED','jobname',p_jobname,'mode',v_mode,
           'admission_class',p.admission_class,'priority',p.priority,'authority_created',false,'observed_at',v_started),
         updated_at=v_started
   where jobname=p_jobname;

  perform set_config('lock_timeout','5s',true);
  perform set_config('statement_timeout',p.max_runtime_seconds::text||'s',true);
  execute p.original_command;

  v_duration_ms:=greatest(0,round(extract(epoch from (clock_timestamp()-v_started))*1000)::bigint);
  v_result:=jsonb_build_object('state','EXECUTED','jobname',p_jobname,'mode',v_mode,
    'admission_class',p.admission_class,'priority',p.priority,'duration_ms',v_duration_ms,
    'original_command_sha256',p.original_command_sha256,'authority_created',false,'observed_at',clock_timestamp());
  update penta_balancer.job_state_v1
     set last_completed_at=clock_timestamp(),last_state='EXECUTED',last_mode=v_mode,
         last_duration_ms=v_duration_ms,completed_count=completed_count+1,last_result=v_result,updated_at=clock_timestamp()
   where jobname=p_jobname;
  return v_result;
end;
$$;

create or replace function penta_balancer.instrument_job_v1(
  p_jobname text,
  p_admission_class text,
  p_priority integer,
  p_cooldown_seconds integer,
  p_max_runtime_seconds integer,
  p_owner_penta text,
  p_rationale text
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,pentatime,penta_self,integration_control,cron,extensions,pg_temp
as $$
declare
  j cron.job%rowtype;
  p_existing penta_balancer.job_policy_v1%rowtype;
  v_count integer;
  v_original_command text;
  v_original_schedule text;
  v_sha text;
  v_wrapper text;
  v_generation bigint;
  v_desired_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if p_admission_class not in ('critical','high','normal','elastic') then raise exception 'invalid_admission_class'; end if;
  p_priority:=greatest(0,least(coalesce(p_priority,50),100));
  p_cooldown_seconds:=greatest(0,least(coalesce(p_cooldown_seconds,0),86400));
  p_max_runtime_seconds:=greatest(5,least(coalesce(p_max_runtime_seconds,180),900));
  if coalesce(btrim(p_owner_penta),'')='' then raise exception 'owner_penta_required'; end if;
  if coalesce(btrim(p_rationale),'')='' then raise exception 'rationale_required'; end if;
  if p_jobname in ('ct-pentabalancer-control-v1','ct-pentatick-wake-v1','ct-pentatime-reconcile-v1','ct-pentaclock-dail-sync-v1') then
    raise exception 'core_temporal_job_must_not_be_wrapped:%',p_jobname;
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:instrument:'||p_jobname,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;

  select count(*)::integer into v_count from cron.job where jobname=p_jobname;
  if v_count<>1 then
    return jsonb_build_object('state',case when v_count=0 then 'HOLD_MISSING_JOB' else 'HOLD_DUPLICATE_JOBNAME' end,
      'jobname',p_jobname,'matching_jobs',v_count,'authority_created',false,'observed_at',v_now);
  end if;
  select * into j from cron.job where jobname=p_jobname for update;
  if not j.active then return jsonb_build_object('state','HOLD_INACTIVE_JOB','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;

  select * into p_existing from penta_balancer.job_policy_v1 where jobname=p_jobname;
  v_wrapper:=format('select penta_balancer.execute_managed_job_v1(%L);',p_jobname);

  if j.command=v_wrapper then
    if p_existing.jobname is null or not p_existing.instrumented then
      raise exception 'wrapper_present_without_active_policy:%',p_jobname;
    end if;
    v_original_command:=p_existing.original_command;
    v_original_schedule:=p_existing.original_schedule;
  else
    if j.command !~* '^\s*(select|call)\b' then raise exception 'unsupported_original_command:%',p_jobname; end if;
    v_original_command:=j.command;
    v_original_schedule:=j.schedule;
  end if;

  v_sha:=encode(extensions.digest(convert_to(v_original_command,'UTF8'),'sha256'),'hex');
  insert into penta_balancer.job_policy_v1(
    jobname,original_schedule,original_command,original_command_sha256,admission_class,priority,shed_allowed,
    cooldown_seconds,max_runtime_seconds,owner_penta,rationale,source_ref,active,instrumented,instrumented_at,metadata
  ) values(
    p_jobname,v_original_schedule,v_original_command,v_sha,p_admission_class,p_priority,
    p_admission_class in ('normal','elastic'),p_cooldown_seconds,p_max_runtime_seconds,p_owner_penta,p_rationale,
    'ct.pentabalancer.managed-job-admission.v1',true,true,v_now,
    jsonb_build_object('wrapper_command',v_wrapper,'schedule_preserved',true,'job_owner_preserved',true,
      'original_command_sha256',v_sha,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    original_schedule=excluded.original_schedule,original_command=excluded.original_command,
    original_command_sha256=excluded.original_command_sha256,admission_class=excluded.admission_class,
    priority=excluded.priority,shed_allowed=excluded.shed_allowed,cooldown_seconds=excluded.cooldown_seconds,
    max_runtime_seconds=excluded.max_runtime_seconds,owner_penta=excluded.owner_penta,rationale=excluded.rationale,
    source_ref=excluded.source_ref,active=true,instrumented=true,instrumented_at=coalesce(penta_balancer.job_policy_v1.instrumented_at,v_now),
    restored_at=null,metadata=penta_balancer.job_policy_v1.metadata||excluded.metadata,updated_at=v_now;

  insert into penta_balancer.job_state_v1(jobname) values(p_jobname) on conflict(jobname) do nothing;
  if j.command is distinct from v_wrapper then
    perform cron.alter_job(j.jobid,command=>v_wrapper,active=>true);
  end if;

  select greatest(coalesce(max(generation),202609040700)+1,202609040700) into v_generation
  from integration_control.scheduler_desired_jobs_v2;
  v_desired_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',p_jobname,'schedule',j.schedule,'command',v_wrapper,'active',true,'generation',v_generation,
    'source_ref','ct.pentabalancer.managed-job-admission.v1','original_command_sha256',v_sha
  )::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.scheduler_desired_jobs_v2(
    jobname,schedule,command,database_name,username,active,generation,source_ref,desired_sha256,allow_auto_restore,metadata
  ) values(
    p_jobname,j.schedule,v_wrapper,coalesce(j.database,current_database()),coalesce(j.username,current_user),true,v_generation,
    'ct.pentabalancer.managed-job-admission.v1',v_desired_sha,true,
    jsonb_build_object('PentaBalancer_managed',true,'original_command',v_original_command,'original_command_sha256',v_sha,
      'admission_class',p_admission_class,'priority',p_priority,'cooldown_seconds',p_cooldown_seconds,
      'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username=excluded.username,
    active=true,generation=excluded.generation,source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,
    allow_auto_restore=true,metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=v_now;

  insert into penta_self.permanent_cron_desired_state_v1(
    jobname,schedule,command,database_name,username_name,desired_active,enforcement_mode,
    verification_evidence,desired_sha256,verified_at,source_ref
  ) values(
    p_jobname,j.schedule,v_wrapper,coalesce(j.database,current_database()),coalesce(j.username,current_user),true,'exact',
    jsonb_build_object('PentaBalancer_managed',true,'original_command_sha256',v_sha,'admission_class',p_admission_class,
      'priority',p_priority,'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false),
    v_desired_sha,v_now,'ct.pentabalancer.managed-job-admission.v1'
  )
  on conflict(jobname) do update set
    schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username_name=excluded.username_name,
    desired_active=true,enforcement_mode='exact',
    verification_evidence=penta_self.permanent_cron_desired_state_v1.verification_evidence||excluded.verification_evidence,
    desired_sha256=excluded.desired_sha256,verified_at=v_now,source_ref=excluded.source_ref,updated_at=v_now;

  insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
  values(
    p_jobname,j.schedule,v_wrapper,true,'D1',
    jsonb_build_object('PentaBalancer_managed',true,'original_command_sha256',v_sha,'admission_class',p_admission_class,
      'priority',p_priority,'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,
    risk_class=case when penta_self.required_jobs_v1.risk_class='D2' then 'D2' else 'D1' end,
    metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=v_now;

  update pentatime.scheduler_registry
     set notes=coalesce(notes,'')||case when coalesce(notes,'')='' then '' else ' ' end||
       'PentaBalancer admission wrapper active; original owner and schedule preserved; reversible by exact command hash.',
       updated_at=v_now
   where cron_job_name=p_jobname and coalesce(notes,'') not like '%PentaBalancer admission wrapper active%';

  return jsonb_build_object('state','INSTRUMENTED','jobname',p_jobname,'schedule',j.schedule,
    'wrapper_command',v_wrapper,'original_command_sha256',v_sha,'admission_class',p_admission_class,
    'priority',p_priority,'cooldown_seconds',p_cooldown_seconds,'max_runtime_seconds',p_max_runtime_seconds,
    'owner_penta',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false,'observed_at',v_now);
end;
$$;

create or replace function penta_balancer.restore_job_v1(p_jobname text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,pentatime,penta_self,integration_control,cron,extensions,pg_temp
as $$
declare
  p penta_balancer.job_policy_v1%rowtype;
  j cron.job%rowtype;
  v_wrapper text;
  v_generation bigint;
  v_desired_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:instrument:'||p_jobname,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;
  select * into p from penta_balancer.job_policy_v1 where jobname=p_jobname for update;
  if not found then return jsonb_build_object('state','NOT_MANAGED','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;
  select * into j from cron.job where jobname=p_jobname order by jobid desc limit 1 for update;
  if not found then return jsonb_build_object('state','HOLD_MISSING_JOB','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;
  if encode(extensions.digest(convert_to(p.original_command,'UTF8'),'sha256'),'hex') is distinct from p.original_command_sha256 then
    raise exception 'restore_integrity_failed:%',p_jobname;
  end if;
  v_wrapper:=format('select penta_balancer.execute_managed_job_v1(%L);',p_jobname);
  if j.command is distinct from v_wrapper and j.command is distinct from p.original_command then
    return jsonb_build_object('state','HOLD_EXTERNAL_COMMAND_DRIFT','jobname',p_jobname,'actual_command',j.command,
      'expected_wrapper',v_wrapper,'authority_created',false,'observed_at',v_now);
  end if;
  perform cron.alter_job(j.jobid,schedule=>p.original_schedule,command=>p.original_command,active=>true);

  select greatest(coalesce(max(generation),202609040700)+1,202609040700) into v_generation
  from integration_control.scheduler_desired_jobs_v2;
  v_desired_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',p_jobname,'schedule',p.original_schedule,'command',p.original_command,'active',true,
    'generation',v_generation,'source_ref','ct.pentabalancer.managed-job-restore.v1'
  )::text,'UTF8'),'sha256'),'hex');

  update integration_control.scheduler_desired_jobs_v2
     set schedule=p.original_schedule,command=p.original_command,active=true,generation=v_generation,
         source_ref='ct.pentabalancer.managed-job-restore.v1',desired_sha256=v_desired_sha,allow_auto_restore=true,
         metadata=metadata||jsonb_build_object('PentaBalancer_managed',false,'restored_at',v_now,'authority_created',false),updated_at=v_now
   where jobname=p_jobname;
  update penta_self.permanent_cron_desired_state_v1
     set schedule=p.original_schedule,command=p.original_command,desired_active=true,enforcement_mode='exact',
         verification_evidence=verification_evidence||jsonb_build_object('PentaBalancer_managed',false,'restored_at',v_now,'authority_created',false),
         desired_sha256=v_desired_sha,verified_at=v_now,source_ref='ct.pentabalancer.managed-job-restore.v1',updated_at=v_now
   where jobname=p_jobname;
  update penta_self.required_jobs_v1
     set expected_schedule=p.original_schedule,expected_command=p.original_command,auto_repair=true,
         metadata=metadata||jsonb_build_object('PentaBalancer_managed',false,'restored_at',v_now,'authority_created',false),updated_at=v_now
   where jobname=p_jobname;
  update penta_balancer.job_policy_v1 set instrumented=false,restored_at=v_now,updated_at=v_now where jobname=p_jobname;

  return jsonb_build_object('state','RESTORED','jobname',p_jobname,'schedule',p.original_schedule,
    'original_command_sha256',p.original_command_sha256,'authority_created',false,'observed_at',v_now);
end;
$$;

create or replace function penta_balancer.managed_jobs_status_v1()
returns jsonb
language sql
stable
security definer
set search_path=pg_catalog,penta_balancer,cron,pg_temp
as $$
select jsonb_build_object(
  'managed_jobs',count(*) filter(where p.instrumented and p.active),
  'by_class',coalesce((select jsonb_object_agg(admission_class,n) from (
    select admission_class,count(*)::integer n from penta_balancer.job_policy_v1 where instrumented and active group by admission_class order by admission_class
  ) x),'{}'::jsonb),
  'actual_command_drift',count(*) filter(where p.instrumented and p.active and j.command is distinct from format('select penta_balancer.execute_managed_job_v1(%L);',p.jobname)),
  'deferred_total',coalesce(sum(s.deferred_count),0),
  'completed_total',coalesce(sum(s.completed_count),0),
  'jobs',coalesce(jsonb_agg(jsonb_build_object(
    'jobname',p.jobname,'admission_class',p.admission_class,'priority',p.priority,
    'cooldown_seconds',p.cooldown_seconds,'max_runtime_seconds',p.max_runtime_seconds,
    'owner_penta',p.owner_penta,'instrumented',p.instrumented,'cron_active',j.active,
    'actual_schedule',j.schedule,'expected_schedule',p.original_schedule,
    'wrapper_exact',j.command is not distinct from format('select penta_balancer.execute_managed_job_v1(%L);',p.jobname),
    'last_state',s.last_state,'last_mode',s.last_mode,'last_completed_at',s.last_completed_at,
    'completed_count',s.completed_count,'deferred_count',s.deferred_count
  ) order by p.priority desc,p.jobname),'[]'::jsonb),
  'authority_created',false,'observed_at',statement_timestamp()
)
from penta_balancer.job_policy_v1 p
left join penta_balancer.job_state_v1 s using(jobname)
left join cron.job j on j.jobname=p.jobname
where p.instrumented and p.active;
$$;

revoke all on all functions in schema penta_balancer from public,anon,authenticated;
grant execute on function penta_balancer.executor_authorized_v1() to service_role;
grant execute on function penta_balancer.execute_managed_job_v1(text) to service_role;
grant execute on function penta_balancer.instrument_job_v1(text,text,integer,integer,integer,text,text) to service_role;
grant execute on function penta_balancer.restore_job_v1(text) to service_role;
grant execute on function penta_balancer.managed_jobs_status_v1() to service_role;



-- Applied migration 20260904070425: penta_balancer_command_validation_regex_fix_v1
set lock_timeout='3s';
set statement_timeout='45s';

create or replace function penta_balancer.execute_managed_job_v1(p_jobname text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,extensions,pg_temp
as $$
declare
  p penta_balancer.job_policy_v1%rowtype;
  s penta_balancer.job_state_v1%rowtype;
  v_mode text:='WATCH';
  v_now timestamptz:=clock_timestamp();
  v_started timestamptz;
  v_duration_ms bigint;
  v_allowed boolean:=false;
  v_reason text;
  v_actual_sha text;
  v_result jsonb;
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if p_jobname is null or btrim(p_jobname)='' then raise exception 'jobname_required'; end if;

  select * into p from penta_balancer.job_policy_v1 where jobname=p_jobname and active and instrumented;
  if not found then raise exception 'managed_job_policy_not_active:%',p_jobname; end if;

  v_actual_sha:=encode(extensions.digest(convert_to(p.original_command,'UTF8'),'sha256'),'hex');
  if v_actual_sha is distinct from p.original_command_sha256 then raise exception 'managed_job_command_integrity_failed:%',p_jobname; end if;
  if p.original_command !~* '^[[:space:]]*(select|call)([[:space:]]|$)' then
    raise exception 'managed_job_command_not_permitted:%',p_jobname;
  end if;

  insert into penta_balancer.job_state_v1(jobname) values(p_jobname) on conflict(jobname) do nothing;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:managed-job:'||p_jobname,0)) then
    update penta_balancer.job_state_v1
       set last_attempt_at=v_now,last_deferred_at=v_now,last_state='DEFERRED_OVERLAP',
           overlap_deferred_count=overlap_deferred_count+1,deferred_count=deferred_count+1,
           last_result=jsonb_build_object('state','DEFERRED_OVERLAP','jobname',p_jobname,'authority_created',false,'observed_at',v_now),updated_at=v_now
     where jobname=p_jobname;
    return jsonb_build_object('state','DEFERRED_OVERLAP','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;

  select * into s from penta_balancer.job_state_v1 where jobname=p_jobname for update;
  select mode into v_mode from penta_balancer.control_state_v1 where singleton_key='primary';
  v_mode:=coalesce(v_mode,'WATCH');

  if p.cooldown_seconds>0 and s.last_completed_at is not null
     and s.last_completed_at+make_interval(secs=>p.cooldown_seconds)>v_now then
    v_reason:='cooldown_until:'||(s.last_completed_at+make_interval(secs=>p.cooldown_seconds))::text;
    update penta_balancer.job_state_v1
       set last_attempt_at=v_now,last_deferred_at=v_now,last_state='DEFERRED_COOLDOWN',last_mode=v_mode,
           cooldown_deferred_count=cooldown_deferred_count+1,deferred_count=deferred_count+1,
           last_result=jsonb_build_object('state','DEFERRED_COOLDOWN','jobname',p_jobname,'mode',v_mode,
             'cooldown_seconds',p.cooldown_seconds,'reason',v_reason,'authority_created',false,'observed_at',v_now),updated_at=v_now
     where jobname=p_jobname;
    return jsonb_build_object('state','DEFERRED_COOLDOWN','jobname',p_jobname,'mode',v_mode,
      'cooldown_seconds',p.cooldown_seconds,'reason',v_reason,'authority_created',false,'observed_at',v_now);
  end if;

  v_allowed:=case p.admission_class
    when 'critical' then true
    when 'high' then true
    when 'normal' then v_mode in ('NORMAL','RECOVERY') or (v_mode='WATCH' and p.priority>=70)
    when 'elastic' then v_mode='NORMAL' or (v_mode='RECOVERY' and p.priority>=70)
    else false end;

  if not v_allowed then
    v_reason:='mode_'||lower(v_mode)||'_class_'||p.admission_class;
    update penta_balancer.job_state_v1
       set last_attempt_at=v_now,last_deferred_at=v_now,last_state='DEFERRED_PRESSURE',last_mode=v_mode,
           pressure_deferred_count=pressure_deferred_count+1,deferred_count=deferred_count+1,
           last_result=jsonb_build_object('state','DEFERRED_PRESSURE','jobname',p_jobname,'mode',v_mode,
             'admission_class',p.admission_class,'priority',p.priority,'reason',v_reason,
             'authority_created',false,'observed_at',v_now),updated_at=v_now
     where jobname=p_jobname;
    return jsonb_build_object('state','DEFERRED_PRESSURE','jobname',p_jobname,'mode',v_mode,
      'admission_class',p.admission_class,'priority',p.priority,'reason',v_reason,
      'authority_created',false,'observed_at',v_now);
  end if;

  v_started:=clock_timestamp();
  update penta_balancer.job_state_v1
     set last_attempt_at=v_now,last_admitted_at=v_started,last_state='ADMITTED',last_mode=v_mode,
         admitted_count=admitted_count+1,
         last_result=jsonb_build_object('state','ADMITTED','jobname',p_jobname,'mode',v_mode,
           'admission_class',p.admission_class,'priority',p.priority,'authority_created',false,'observed_at',v_started),updated_at=v_started
   where jobname=p_jobname;

  perform set_config('lock_timeout','5s',true);
  perform set_config('statement_timeout',p.max_runtime_seconds::text||'s',true);
  execute p.original_command;

  v_duration_ms:=greatest(0,round(extract(epoch from (clock_timestamp()-v_started))*1000)::bigint);
  v_result:=jsonb_build_object('state','EXECUTED','jobname',p_jobname,'mode',v_mode,
    'admission_class',p.admission_class,'priority',p.priority,'duration_ms',v_duration_ms,
    'original_command_sha256',p.original_command_sha256,'authority_created',false,'observed_at',clock_timestamp());
  update penta_balancer.job_state_v1
     set last_completed_at=clock_timestamp(),last_state='EXECUTED',last_mode=v_mode,
         last_duration_ms=v_duration_ms,completed_count=completed_count+1,last_result=v_result,updated_at=clock_timestamp()
   where jobname=p_jobname;
  return v_result;
end;
$$;

create or replace function penta_balancer.instrument_job_v1(
  p_jobname text,p_admission_class text,p_priority integer,p_cooldown_seconds integer,
  p_max_runtime_seconds integer,p_owner_penta text,p_rationale text
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,pentatime,penta_self,integration_control,cron,extensions,pg_temp
as $$
declare
  j cron.job%rowtype;
  p_existing penta_balancer.job_policy_v1%rowtype;
  v_count integer;
  v_original_command text;
  v_original_schedule text;
  v_sha text;
  v_wrapper text;
  v_generation bigint;
  v_desired_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if p_admission_class not in ('critical','high','normal','elastic') then raise exception 'invalid_admission_class'; end if;
  p_priority:=greatest(0,least(coalesce(p_priority,50),100));
  p_cooldown_seconds:=greatest(0,least(coalesce(p_cooldown_seconds,0),86400));
  p_max_runtime_seconds:=greatest(5,least(coalesce(p_max_runtime_seconds,180),900));
  if coalesce(btrim(p_owner_penta),'')='' then raise exception 'owner_penta_required'; end if;
  if coalesce(btrim(p_rationale),'')='' then raise exception 'rationale_required'; end if;
  if p_jobname in ('ct-pentabalancer-control-v1','ct-pentatick-wake-v1','ct-pentatime-reconcile-v1','ct-pentaclock-dail-sync-v1') then
    raise exception 'core_temporal_job_must_not_be_wrapped:%',p_jobname;
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:instrument:'||p_jobname,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;

  select count(*)::integer into v_count from cron.job where jobname=p_jobname;
  if v_count<>1 then
    return jsonb_build_object('state',case when v_count=0 then 'HOLD_MISSING_JOB' else 'HOLD_DUPLICATE_JOBNAME' end,
      'jobname',p_jobname,'matching_jobs',v_count,'authority_created',false,'observed_at',v_now);
  end if;
  select * into j from cron.job where jobname=p_jobname for update;
  if not j.active then return jsonb_build_object('state','HOLD_INACTIVE_JOB','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;

  select * into p_existing from penta_balancer.job_policy_v1 where jobname=p_jobname;
  v_wrapper:=format('select penta_balancer.execute_managed_job_v1(%L);',p_jobname);
  if j.command=v_wrapper then
    if p_existing.jobname is null or not p_existing.instrumented then raise exception 'wrapper_present_without_active_policy:%',p_jobname; end if;
    v_original_command:=p_existing.original_command;
    v_original_schedule:=p_existing.original_schedule;
  else
    if j.command !~* '^[[:space:]]*(select|call)([[:space:]]|$)' then raise exception 'unsupported_original_command:%',p_jobname; end if;
    v_original_command:=j.command;
    v_original_schedule:=j.schedule;
  end if;

  v_sha:=encode(extensions.digest(convert_to(v_original_command,'UTF8'),'sha256'),'hex');
  insert into penta_balancer.job_policy_v1(
    jobname,original_schedule,original_command,original_command_sha256,admission_class,priority,shed_allowed,
    cooldown_seconds,max_runtime_seconds,owner_penta,rationale,source_ref,active,instrumented,instrumented_at,metadata
  ) values(
    p_jobname,v_original_schedule,v_original_command,v_sha,p_admission_class,p_priority,
    p_admission_class in ('normal','elastic'),p_cooldown_seconds,p_max_runtime_seconds,p_owner_penta,p_rationale,
    'ct.pentabalancer.managed-job-admission.v1',true,true,v_now,
    jsonb_build_object('wrapper_command',v_wrapper,'schedule_preserved',true,'job_owner_preserved',true,
      'original_command_sha256',v_sha,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    original_schedule=excluded.original_schedule,original_command=excluded.original_command,
    original_command_sha256=excluded.original_command_sha256,admission_class=excluded.admission_class,
    priority=excluded.priority,shed_allowed=excluded.shed_allowed,cooldown_seconds=excluded.cooldown_seconds,
    max_runtime_seconds=excluded.max_runtime_seconds,owner_penta=excluded.owner_penta,rationale=excluded.rationale,
    source_ref=excluded.source_ref,active=true,instrumented=true,instrumented_at=coalesce(penta_balancer.job_policy_v1.instrumented_at,v_now),
    restored_at=null,metadata=penta_balancer.job_policy_v1.metadata||excluded.metadata,updated_at=v_now;

  insert into penta_balancer.job_state_v1(jobname) values(p_jobname) on conflict(jobname) do nothing;
  if j.command is distinct from v_wrapper then perform cron.alter_job(j.jobid,command=>v_wrapper,active=>true); end if;

  select greatest(coalesce(max(generation),202609040700)+1,202609040700) into v_generation from integration_control.scheduler_desired_jobs_v2;
  v_desired_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',p_jobname,'schedule',j.schedule,'command',v_wrapper,'active',true,'generation',v_generation,
    'source_ref','ct.pentabalancer.managed-job-admission.v1','original_command_sha256',v_sha
  )::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.scheduler_desired_jobs_v2(
    jobname,schedule,command,database_name,username,active,generation,source_ref,desired_sha256,allow_auto_restore,metadata
  ) values(
    p_jobname,j.schedule,v_wrapper,coalesce(j.database,current_database()),coalesce(j.username,current_user),true,v_generation,
    'ct.pentabalancer.managed-job-admission.v1',v_desired_sha,true,
    jsonb_build_object('PentaBalancer_managed',true,'original_command',v_original_command,'original_command_sha256',v_sha,
      'admission_class',p_admission_class,'priority',p_priority,'cooldown_seconds',p_cooldown_seconds,
      'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username=excluded.username,
    active=true,generation=excluded.generation,source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,
    allow_auto_restore=true,metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=v_now;

  insert into penta_self.permanent_cron_desired_state_v1(
    jobname,schedule,command,database_name,username_name,desired_active,enforcement_mode,
    verification_evidence,desired_sha256,verified_at,source_ref
  ) values(
    p_jobname,j.schedule,v_wrapper,coalesce(j.database,current_database()),coalesce(j.username,current_user),true,'exact',
    jsonb_build_object('PentaBalancer_managed',true,'original_command_sha256',v_sha,'admission_class',p_admission_class,
      'priority',p_priority,'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false),
    v_desired_sha,v_now,'ct.pentabalancer.managed-job-admission.v1'
  )
  on conflict(jobname) do update set
    schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username_name=excluded.username_name,
    desired_active=true,enforcement_mode='exact',
    verification_evidence=penta_self.permanent_cron_desired_state_v1.verification_evidence||excluded.verification_evidence,
    desired_sha256=excluded.desired_sha256,verified_at=v_now,source_ref=excluded.source_ref,updated_at=v_now;

  insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
  values(
    p_jobname,j.schedule,v_wrapper,true,'D1',
    jsonb_build_object('PentaBalancer_managed',true,'original_command_sha256',v_sha,'admission_class',p_admission_class,
      'priority',p_priority,'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,
    risk_class=case when penta_self.required_jobs_v1.risk_class='D2' then 'D2' else 'D1' end,
    metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=v_now;

  update pentatime.scheduler_registry
     set notes=coalesce(notes,'')||case when coalesce(notes,'')='' then '' else ' ' end||
       'PentaBalancer admission wrapper active; original owner and schedule preserved; reversible by exact command hash.',
       updated_at=v_now
   where cron_job_name=p_jobname and coalesce(notes,'') not like '%PentaBalancer admission wrapper active%';

  return jsonb_build_object('state','INSTRUMENTED','jobname',p_jobname,'schedule',j.schedule,
    'wrapper_command',v_wrapper,'original_command_sha256',v_sha,'admission_class',p_admission_class,
    'priority',p_priority,'cooldown_seconds',p_cooldown_seconds,'max_runtime_seconds',p_max_runtime_seconds,
    'owner_penta',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false,'observed_at',v_now);
end;
$$;

revoke all on function penta_balancer.execute_managed_job_v1(text) from public,anon,authenticated;
revoke all on function penta_balancer.instrument_job_v1(text,text,integer,integer,integer,text,text) from public,anon,authenticated;
grant execute on function penta_balancer.execute_managed_job_v1(text) to service_role;
grant execute on function penta_balancer.instrument_job_v1(text,text,integer,integer,integer,text,text) to service_role;


-- Applied migration 20260904070544: penta_balancer_cron_lock_compatibility_fix_v1
set lock_timeout='3s';
set statement_timeout='45s';

create or replace function penta_balancer.instrument_job_v1(
  p_jobname text,p_admission_class text,p_priority integer,p_cooldown_seconds integer,
  p_max_runtime_seconds integer,p_owner_penta text,p_rationale text
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,pentatime,penta_self,integration_control,cron,extensions,pg_temp
as $$
declare
  j cron.job%rowtype;
  p_existing penta_balancer.job_policy_v1%rowtype;
  v_count integer;
  v_original_command text;
  v_original_schedule text;
  v_sha text;
  v_wrapper text;
  v_generation bigint;
  v_desired_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if p_admission_class not in ('critical','high','normal','elastic') then raise exception 'invalid_admission_class'; end if;
  p_priority:=greatest(0,least(coalesce(p_priority,50),100));
  p_cooldown_seconds:=greatest(0,least(coalesce(p_cooldown_seconds,0),86400));
  p_max_runtime_seconds:=greatest(5,least(coalesce(p_max_runtime_seconds,180),900));
  if coalesce(btrim(p_owner_penta),'')='' then raise exception 'owner_penta_required'; end if;
  if coalesce(btrim(p_rationale),'')='' then raise exception 'rationale_required'; end if;
  if p_jobname in ('ct-pentabalancer-control-v1','ct-pentatick-wake-v1','ct-pentatime-reconcile-v1','ct-pentaclock-dail-sync-v1') then
    raise exception 'core_temporal_job_must_not_be_wrapped:%',p_jobname;
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:instrument:'||p_jobname,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;

  select count(*)::integer into v_count from cron.job where jobname=p_jobname;
  if v_count<>1 then
    return jsonb_build_object('state',case when v_count=0 then 'HOLD_MISSING_JOB' else 'HOLD_DUPLICATE_JOBNAME' end,
      'jobname',p_jobname,'matching_jobs',v_count,'authority_created',false,'observed_at',v_now);
  end if;
  select * into j from cron.job where jobname=p_jobname;
  if not j.active then return jsonb_build_object('state','HOLD_INACTIVE_JOB','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;

  select * into p_existing from penta_balancer.job_policy_v1 where jobname=p_jobname;
  v_wrapper:=format('select penta_balancer.execute_managed_job_v1(%L);',p_jobname);
  if j.command=v_wrapper then
    if p_existing.jobname is null or not p_existing.instrumented then raise exception 'wrapper_present_without_active_policy:%',p_jobname; end if;
    v_original_command:=p_existing.original_command;
    v_original_schedule:=p_existing.original_schedule;
  else
    if j.command !~* '^[[:space:]]*(select|call)([[:space:]]|$)' then raise exception 'unsupported_original_command:%',p_jobname; end if;
    v_original_command:=j.command;
    v_original_schedule:=j.schedule;
  end if;

  v_sha:=encode(extensions.digest(convert_to(v_original_command,'UTF8'),'sha256'),'hex');
  insert into penta_balancer.job_policy_v1(
    jobname,original_schedule,original_command,original_command_sha256,admission_class,priority,shed_allowed,
    cooldown_seconds,max_runtime_seconds,owner_penta,rationale,source_ref,active,instrumented,instrumented_at,metadata
  ) values(
    p_jobname,v_original_schedule,v_original_command,v_sha,p_admission_class,p_priority,
    p_admission_class in ('normal','elastic'),p_cooldown_seconds,p_max_runtime_seconds,p_owner_penta,p_rationale,
    'ct.pentabalancer.managed-job-admission.v1',true,true,v_now,
    jsonb_build_object('wrapper_command',v_wrapper,'schedule_preserved',true,'job_owner_preserved',true,
      'original_command_sha256',v_sha,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    original_schedule=excluded.original_schedule,original_command=excluded.original_command,
    original_command_sha256=excluded.original_command_sha256,admission_class=excluded.admission_class,
    priority=excluded.priority,shed_allowed=excluded.shed_allowed,cooldown_seconds=excluded.cooldown_seconds,
    max_runtime_seconds=excluded.max_runtime_seconds,owner_penta=excluded.owner_penta,rationale=excluded.rationale,
    source_ref=excluded.source_ref,active=true,instrumented=true,instrumented_at=coalesce(penta_balancer.job_policy_v1.instrumented_at,v_now),
    restored_at=null,metadata=penta_balancer.job_policy_v1.metadata||excluded.metadata,updated_at=v_now;

  insert into penta_balancer.job_state_v1(jobname) values(p_jobname) on conflict(jobname) do nothing;
  if j.command is distinct from v_wrapper then perform cron.alter_job(j.jobid,command=>v_wrapper,active=>true); end if;

  select greatest(coalesce(max(generation),202609040700)+1,202609040700) into v_generation from integration_control.scheduler_desired_jobs_v2;
  v_desired_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',p_jobname,'schedule',j.schedule,'command',v_wrapper,'active',true,'generation',v_generation,
    'source_ref','ct.pentabalancer.managed-job-admission.v1','original_command_sha256',v_sha
  )::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.scheduler_desired_jobs_v2(
    jobname,schedule,command,database_name,username,active,generation,source_ref,desired_sha256,allow_auto_restore,metadata
  ) values(
    p_jobname,j.schedule,v_wrapper,coalesce(j.database,current_database()),coalesce(j.username,current_user),true,v_generation,
    'ct.pentabalancer.managed-job-admission.v1',v_desired_sha,true,
    jsonb_build_object('PentaBalancer_managed',true,'original_command',v_original_command,'original_command_sha256',v_sha,
      'admission_class',p_admission_class,'priority',p_priority,'cooldown_seconds',p_cooldown_seconds,
      'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username=excluded.username,
    active=true,generation=excluded.generation,source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,
    allow_auto_restore=true,metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=v_now;

  insert into penta_self.permanent_cron_desired_state_v1(
    jobname,schedule,command,database_name,username_name,desired_active,enforcement_mode,
    verification_evidence,desired_sha256,verified_at,source_ref
  ) values(
    p_jobname,j.schedule,v_wrapper,coalesce(j.database,current_database()),coalesce(j.username,current_user),true,'exact',
    jsonb_build_object('PentaBalancer_managed',true,'original_command_sha256',v_sha,'admission_class',p_admission_class,
      'priority',p_priority,'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false),
    v_desired_sha,v_now,'ct.pentabalancer.managed-job-admission.v1'
  )
  on conflict(jobname) do update set
    schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username_name=excluded.username_name,
    desired_active=true,enforcement_mode='exact',
    verification_evidence=penta_self.permanent_cron_desired_state_v1.verification_evidence||excluded.verification_evidence,
    desired_sha256=excluded.desired_sha256,verified_at=v_now,source_ref=excluded.source_ref,updated_at=v_now;

  insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
  values(
    p_jobname,j.schedule,v_wrapper,true,'D1',
    jsonb_build_object('PentaBalancer_managed',true,'original_command_sha256',v_sha,'admission_class',p_admission_class,
      'priority',p_priority,'owner',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,
    risk_class=case when penta_self.required_jobs_v1.risk_class='D2' then 'D2' else 'D1' end,
    metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=v_now;

  update pentatime.scheduler_registry
     set notes=coalesce(notes,'')||case when coalesce(notes,'')='' then '' else ' ' end||
       'PentaBalancer admission wrapper active; original owner and schedule preserved; reversible by exact command hash.',
       updated_at=v_now
   where cron_job_name=p_jobname and coalesce(notes,'') not like '%PentaBalancer admission wrapper active%';

  return jsonb_build_object('state','INSTRUMENTED','jobname',p_jobname,'schedule',j.schedule,
    'wrapper_command',v_wrapper,'original_command_sha256',v_sha,'admission_class',p_admission_class,
    'priority',p_priority,'cooldown_seconds',p_cooldown_seconds,'max_runtime_seconds',p_max_runtime_seconds,
    'owner_penta',p_owner_penta,'schedule_preserved',true,'reversible',true,'authority_created',false,'observed_at',v_now);
end;
$$;

create or replace function penta_balancer.restore_job_v1(p_jobname text)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,pentatime,penta_self,integration_control,cron,extensions,pg_temp
as $$
declare
  p penta_balancer.job_policy_v1%rowtype;
  j cron.job%rowtype;
  v_wrapper text;
  v_generation bigint;
  v_desired_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:instrument:'||p_jobname,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','jobname',p_jobname,'authority_created',false,'observed_at',v_now);
  end if;
  select * into p from penta_balancer.job_policy_v1 where jobname=p_jobname for update;
  if not found then return jsonb_build_object('state','NOT_MANAGED','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;
  select * into j from cron.job where jobname=p_jobname order by jobid desc limit 1;
  if not found then return jsonb_build_object('state','HOLD_MISSING_JOB','jobname',p_jobname,'authority_created',false,'observed_at',v_now); end if;
  if encode(extensions.digest(convert_to(p.original_command,'UTF8'),'sha256'),'hex') is distinct from p.original_command_sha256 then
    raise exception 'restore_integrity_failed:%',p_jobname;
  end if;
  v_wrapper:=format('select penta_balancer.execute_managed_job_v1(%L);',p_jobname);
  if j.command is distinct from v_wrapper and j.command is distinct from p.original_command then
    return jsonb_build_object('state','HOLD_EXTERNAL_COMMAND_DRIFT','jobname',p_jobname,'actual_command',j.command,
      'expected_wrapper',v_wrapper,'authority_created',false,'observed_at',v_now);
  end if;
  perform cron.alter_job(j.jobid,schedule=>p.original_schedule,command=>p.original_command,active=>true);

  select greatest(coalesce(max(generation),202609040700)+1,202609040700) into v_generation from integration_control.scheduler_desired_jobs_v2;
  v_desired_sha:=encode(extensions.digest(convert_to(jsonb_build_object(
    'jobname',p_jobname,'schedule',p.original_schedule,'command',p.original_command,'active',true,
    'generation',v_generation,'source_ref','ct.pentabalancer.managed-job-restore.v1'
  )::text,'UTF8'),'sha256'),'hex');

  update integration_control.scheduler_desired_jobs_v2
     set schedule=p.original_schedule,command=p.original_command,active=true,generation=v_generation,
         source_ref='ct.pentabalancer.managed-job-restore.v1',desired_sha256=v_desired_sha,allow_auto_restore=true,
         metadata=metadata||jsonb_build_object('PentaBalancer_managed',false,'restored_at',v_now,'authority_created',false),updated_at=v_now
   where jobname=p_jobname;
  update penta_self.permanent_cron_desired_state_v1
     set schedule=p.original_schedule,command=p.original_command,desired_active=true,enforcement_mode='exact',
         verification_evidence=verification_evidence||jsonb_build_object('PentaBalancer_managed',false,'restored_at',v_now,'authority_created',false),
         desired_sha256=v_desired_sha,verified_at=v_now,source_ref='ct.pentabalancer.managed-job-restore.v1',updated_at=v_now
   where jobname=p_jobname;
  update penta_self.required_jobs_v1
     set expected_schedule=p.original_schedule,expected_command=p.original_command,auto_repair=true,
         metadata=metadata||jsonb_build_object('PentaBalancer_managed',false,'restored_at',v_now,'authority_created',false),updated_at=v_now
   where jobname=p_jobname;
  update penta_balancer.job_policy_v1 set instrumented=false,restored_at=v_now,updated_at=v_now where jobname=p_jobname;

  return jsonb_build_object('state','RESTORED','jobname',p_jobname,'schedule',p.original_schedule,
    'original_command_sha256',p.original_command_sha256,'authority_created',false,'observed_at',v_now);
end;
$$;

revoke all on function penta_balancer.instrument_job_v1(text,text,integer,integer,integer,text,text) from public,anon,authenticated;
revoke all on function penta_balancer.restore_job_v1(text) from public,anon,authenticated;
grant execute on function penta_balancer.instrument_job_v1(text,text,integer,integer,integer,text,text) to service_role;
grant execute on function penta_balancer.restore_job_v1(text) to service_role;


-- Applied migration 20260904071138: penta_balancer_managed_admission_canary_v1
set lock_timeout='3s';
set statement_timeout='45s';

create or replace function penta_balancer.managed_admission_canary_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_balancer,pentatime,penta_self,integration_control,cron,extensions,pg_temp
as $$
declare
  v_jobname text:='__penta_balancer_receipt_canary__';
  v_command text:='select 1;';
  v_command_sha text;
  v_exec jsonb;
  v_exec_state jsonb;
  v_managed jsonb;
  v_cohesion jsonb;
  v_hash_integrity boolean:=false;
  v_registry_alignment boolean:=false;
  v_no_core_wrapped boolean:=false;
  v_restore_present boolean:=false;
  v_anon_exec boolean:=false;
  v_auth_exec boolean:=false;
  v_service_exec boolean:=false;
  v_pass boolean:=false;
  v_evidence jsonb;
  v_evidence_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if not penta_balancer.executor_authorized_v1() then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:managed-admission-canary:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','authority_created',false,'observed_at',v_now);
  end if;

  v_command_sha:=encode(extensions.digest(convert_to(v_command,'UTF8'),'sha256'),'hex');
  insert into penta_balancer.job_policy_v1(
    jobname,original_schedule,original_command,original_command_sha256,admission_class,priority,shed_allowed,
    cooldown_seconds,max_runtime_seconds,owner_penta,rationale,active,instrumented,metadata
  ) values(
    v_jobname,'0 0 1 1 *',v_command,v_command_sha,'critical',100,false,0,10,
    'PentaBalancer','Ephemeral production-receipt execution canary.',true,true,
    jsonb_build_object('ephemeral',true,'production_receipt_canary',true,'authority_created',false)
  )
  on conflict(jobname) do update set
    original_schedule=excluded.original_schedule,original_command=excluded.original_command,
    original_command_sha256=excluded.original_command_sha256,admission_class='critical',priority=100,
    shed_allowed=false,cooldown_seconds=0,max_runtime_seconds=10,owner_penta='PentaBalancer',
    rationale=excluded.rationale,active=true,instrumented=true,metadata=excluded.metadata,updated_at=v_now;

  begin
    v_exec:=penta_balancer.execute_managed_job_v1(v_jobname);
    select to_jsonb(s) into v_exec_state from penta_balancer.job_state_v1 s where s.jobname=v_jobname;
  exception when others then
    delete from penta_balancer.job_policy_v1 where jobname=v_jobname;
    raise;
  end;

  delete from penta_balancer.job_policy_v1 where jobname=v_jobname;

  v_managed:=penta_balancer.managed_jobs_status_v1();
  v_cohesion:=penta_balancer.cohesion_snapshot_v1();

  select coalesce(bool_and(
    encode(extensions.digest(convert_to(p.original_command,'UTF8'),'sha256'),'hex')=p.original_command_sha256
  ),false) into v_hash_integrity
  from penta_balancer.job_policy_v1 p
  where p.active and p.instrumented;

  select coalesce(bool_and(
    j.active
    and j.schedule=p.original_schedule
    and j.command=format('select penta_balancer.execute_managed_job_v1(%L);',p.jobname)
    and d.active and d.allow_auto_restore and d.schedule=p.original_schedule
    and d.command=format('select penta_balancer.execute_managed_job_v1(%L);',p.jobname)
    and ps.desired_active and ps.enforcement_mode='exact' and ps.schedule=p.original_schedule
    and ps.command=format('select penta_balancer.execute_managed_job_v1(%L);',p.jobname)
    and r.auto_repair and r.expected_schedule=p.original_schedule
    and r.expected_command=format('select penta_balancer.execute_managed_job_v1(%L);',p.jobname)
  ),false) into v_registry_alignment
  from penta_balancer.job_policy_v1 p
  join cron.job j on j.jobname=p.jobname
  join integration_control.scheduler_desired_jobs_v2 d on d.jobname=p.jobname
  join penta_self.permanent_cron_desired_state_v1 ps on ps.jobname=p.jobname
  join penta_self.required_jobs_v1 r on r.jobname=p.jobname
  where p.active and p.instrumented;

  select not exists(
    select 1 from penta_balancer.job_policy_v1 p
    where p.active and p.instrumented
      and p.jobname in ('ct-pentabalancer-control-v1','ct-pentatick-wake-v1','ct-pentatime-reconcile-v1','ct-pentaclock-dail-sync-v1')
  ) into v_no_core_wrapped;

  v_restore_present:=to_regprocedure('penta_balancer.restore_job_v1(text)') is not null;
  v_anon_exec:=has_function_privilege('anon','penta_balancer.execute_managed_job_v1(text)','EXECUTE');
  v_auth_exec:=has_function_privilege('authenticated','penta_balancer.execute_managed_job_v1(text)','EXECUTE');
  v_service_exec:=has_function_privilege('service_role','penta_balancer.execute_managed_job_v1(text)','EXECUTE');

  v_pass:=coalesce(v_exec->>'state','')='EXECUTED'
    and coalesce((v_exec_state->>'completed_count')::bigint,0)>=1
    and coalesce((v_managed->>'managed_jobs')::integer,0)>=7
    and coalesce((v_managed->>'actual_command_drift')::integer,-1)=0
    and coalesce((v_managed->>'deferred_total')::bigint,0)>=1
    and coalesce((v_cohesion->>'cohesion_score')::integer,0)=100
    and v_hash_integrity and v_registry_alignment and v_no_core_wrapped and v_restore_present
    and not v_anon_exec and not v_auth_exec and v_service_exec;

  v_evidence:=jsonb_build_object(
    'semantic_pass',v_pass,
    'synthetic_execution',v_exec,
    'synthetic_state_before_cleanup',v_exec_state,
    'ephemeral_cleanup_complete',not exists(select 1 from penta_balancer.job_policy_v1 where jobname=v_jobname),
    'managed_status',v_managed,
    'cohesion',v_cohesion,
    'hash_integrity',v_hash_integrity,
    'registry_alignment',v_registry_alignment,
    'core_temporal_jobs_unwrapped',v_no_core_wrapped,
    'restore_function_present',v_restore_present,
    'anon_execute',v_anon_exec,
    'authenticated_execute',v_auth_exec,
    'service_role_execute',v_service_exec,
    'provider_write',false,'money_movement',false,'d3_effect',false,
    'permanent_disables',0,'authority_created',false,'observed_at',clock_timestamp()
  );
  v_evidence_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

  return jsonb_build_object(
    'state',case when v_pass then 'PASS' else 'HOLD' end,
    'evidence',v_evidence,'evidence_sha256',v_evidence_sha
  );
end;
$$;

create or replace function penta_balancer.full_status_v1()
returns jsonb
language sql
stable
security definer
set search_path=pg_catalog,penta_balancer,integration_control,public,pg_temp
as $$
select jsonb_build_object(
  'service','PentaBalancer',
  'core',penta_balancer.status_v1(),
  'managed_jobs',penta_balancer.managed_jobs_status_v1(),
  'specialist_maturation',jsonb_build_object(
    'production',(select count(*) from public.penta_system_registry where system_key like 'penta.%' and maturity='production'),
    'nonproduction',(select count(*) from public.penta_system_registry where system_key like 'penta.%' and maturity<>'production'),
    'by_disposition',coalesce((select jsonb_object_agg(tag,n) from (
      select tag,count(*)::integer n from integration_control.penta_production_mobilization_v1
      where handoff_key like 'ct.penta.specialist-production:%' group by tag order by tag
    ) x),'{}'::jsonb),
    'exact_receipt_required',true,'blanket_promotion',false
  ),
  'sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
  'authority_created',false,'observed_at',statement_timestamp()
);
$$;

revoke all on function penta_balancer.managed_admission_canary_v1() from public,anon,authenticated;
revoke all on function penta_balancer.full_status_v1() from public,anon,authenticated;
grant execute on function penta_balancer.managed_admission_canary_v1() to service_role;
grant execute on function penta_balancer.full_status_v1() to service_role;


-- Applied migration 20260904071743: penta_balancer_github_source_custody_v1
set lock_timeout='3s';
set statement_timeout='90s';

create or replace function integration_control.penta_balancer_github_put_source_v1(
  p_path text,
  p_content text,
  p_message text
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions,chlom_runtime,pg_temp
as $$
declare
  v_repo constant text:='crownthrive1/CrownThrive-OS';
  v_branch constant text:='codex/pentabalancer-production-20260904';
  v_ref constant text:='codex%2Fpentabalancer-production-20260904';
  v_token text;
  v_get extensions.http_response;
  v_put extensions.http_response;
  v_verify extensions.http_response;
  v_get_body jsonb;
  v_put_body jsonb;
  v_verify_body jsonb;
  v_existing_sha text;
  v_expected_sha text;
  v_verified_sha text;
  v_verified_content text;
  v_payload jsonb;
  v_now timestamptz:=clock_timestamp();
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;
  if p_path not in (
    'supabase/migrations/20260904070000_pentabalancer_production_replay.sql',
    'docs/evidence/PENTABALANCER_PRODUCTION_20260904.json',
    'docs/runbooks/PENTABALANCER_PRODUCTION.md'
  ) then
    raise exception 'github_path_not_allowlisted:%',p_path;
  end if;
  if p_content is null or octet_length(convert_to(p_content,'UTF8'))=0 then raise exception 'content_required'; end if;
  if octet_length(convert_to(p_content,'UTF8'))>900000 then raise exception 'content_too_large'; end if;
  if coalesce(btrim(p_message),'')='' then raise exception 'message_required'; end if;

  select decrypted_secret into v_token
  from vault.decrypted_secrets
  where name='APP_FACTORY_GITHUB_TOKEN' and nullif(decrypted_secret,'') is not null
  order by updated_at desc nulls last,created_at desc nulls last
  limit 1;
  if v_token is null then raise exception 'github_token_unavailable'; end if;

  v_expected_sha:=encode(extensions.digest(convert_to(p_content,'UTF8'),'sha256'),'hex');
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','60000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','10000');

  select * into v_get from chlom_runtime.dail_http_v1((
    'GET',
    'https://api.github.com/repos/'||v_repo||'/contents/'||p_path||'?ref='||v_ref,
    array[
      extensions.http_header('Authorization','Bearer '||v_token),
      extensions.http_header('Accept','application/vnd.github+json'),
      extensions.http_header('X-GitHub-Api-Version','2022-11-28'),
      extensions.http_header('User-Agent','CrownThrive-PentaBalancer-Custody/1.0')
    ],null,null
  )::extensions.http_request);

  if v_get.status=200 then
    v_get_body:=coalesce(v_get.content,'{}')::jsonb;
    v_existing_sha:=nullif(v_get_body->>'sha','');
  elsif v_get.status=404 then
    v_existing_sha:=null;
  else
    raise exception 'github_preflight_failed:%',v_get.status;
  end if;

  v_payload:=jsonb_strip_nulls(jsonb_build_object(
    'message',p_message,
    'content',replace(encode(convert_to(p_content,'UTF8'),'base64'),E'\n',''),
    'branch',v_branch,
    'sha',v_existing_sha
  ));

  select * into v_put from chlom_runtime.dail_http_v1((
    'PUT',
    'https://api.github.com/repos/'||v_repo||'/contents/'||p_path,
    array[
      extensions.http_header('Authorization','Bearer '||v_token),
      extensions.http_header('Accept','application/vnd.github+json'),
      extensions.http_header('X-GitHub-Api-Version','2022-11-28'),
      extensions.http_header('Content-Type','application/json'),
      extensions.http_header('User-Agent','CrownThrive-PentaBalancer-Custody/1.0')
    ],'application/json',v_payload::text
  )::extensions.http_request);
  if v_put.status not in (200,201) then
    raise exception 'github_write_failed:%:%',v_put.status,left(coalesce(v_put.content,''),240);
  end if;
  v_put_body:=coalesce(v_put.content,'{}')::jsonb;

  select * into v_verify from chlom_runtime.dail_http_v1((
    'GET',
    'https://api.github.com/repos/'||v_repo||'/contents/'||p_path||'?ref='||v_ref,
    array[
      extensions.http_header('Authorization','Bearer '||v_token),
      extensions.http_header('Accept','application/vnd.github+json'),
      extensions.http_header('X-GitHub-Api-Version','2022-11-28'),
      extensions.http_header('User-Agent','CrownThrive-PentaBalancer-Custody/1.0')
    ],null,null
  )::extensions.http_request);
  if v_verify.status<>200 then raise exception 'github_readback_failed:%',v_verify.status; end if;
  v_verify_body:=coalesce(v_verify.content,'{}')::jsonb;
  v_verified_content:=convert_from(decode(replace(coalesce(v_verify_body->>'content',''),E'\n',''),'base64'),'UTF8');
  v_verified_sha:=encode(extensions.digest(convert_to(v_verified_content,'UTF8'),'sha256'),'hex');
  if v_verified_sha is distinct from v_expected_sha then
    raise exception 'github_readback_hash_mismatch:%:%',v_expected_sha,v_verified_sha;
  end if;

  perform extensions.http_reset_curlopt();
  return jsonb_build_object(
    'state','VERIFIED','repo',v_repo,'branch',v_branch,'path',p_path,
    'write_status',v_put.status,'content_sha256',v_expected_sha,
    'blob_sha',v_verify_body->>'sha','commit_sha',v_put_body->'commit'->>'sha',
    'bytes',octet_length(convert_to(p_content,'UTF8')),
    'secret_exposed',false,'authority_created',false,'observed_at',v_now
  );
exception when others then
  perform extensions.http_reset_curlopt();
  raise;
end;
$$;

create or replace function integration_control.penta_balancer_github_source_custody_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,public,penta_balancer,supabase_migrations,extensions,pg_temp
as $$
declare
  v_sql text;
  v_manifest text;
  v_runbook text;
  v_migrations jsonb;
  v_receipts jsonb;
  v_status jsonb;
  v_sql_write jsonb;
  v_manifest_write jsonb;
  v_runbook_write jsonb;
  v_evidence jsonb;
  v_evidence_sha text;
  v_now timestamptz:=clock_timestamp();
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentabalancer:github-source-custody:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','authority_created',false,'observed_at',v_now);
  end if;

  with selected as (
    select version,name,array_to_string(statements,E'\n') as sql_text
    from supabase_migrations.schema_migrations
    where name in (
      'penta_balancer_foundation_v1',
      'penta_balancer_control_runtime_v1',
      'penta_balancer_nonblocking_admission_v1',
      'penta_specialist_maturation_controller_v1',
      'penta_balancer_production_metadata_and_rebalance_stamp_v1',
      'penta_balancer_managed_job_admission_v1',
      'penta_balancer_command_validation_regex_fix_v1',
      'penta_balancer_cron_lock_compatibility_fix_v1',
      'penta_balancer_managed_admission_canary_v1',
      'penta_balancer_github_source_custody_v1'
    )
  )
  select
    string_agg(format(E'-- Applied migration %s: %s\n%s\n',version,name,sql_text),E'\n\n' order by version),
    jsonb_agg(jsonb_build_object(
      'version',version,'name',name,'sql_chars',length(sql_text),
      'sql_sha256',encode(extensions.digest(convert_to(sql_text,'UTF8'),'sha256'),'hex')
    ) order by version)
  into v_sql,v_migrations
  from selected;

  if jsonb_array_length(coalesce(v_migrations,'[]'::jsonb))<>10 then
    raise exception 'migration_source_incomplete:%',jsonb_array_length(coalesce(v_migrations,'[]'::jsonb));
  end if;

  select coalesce(jsonb_agg(jsonb_build_object(
    'receipt_id',r.receipt_id,'system_key',r.system_key,'system_version',r.system_version,
    'canary_key',r.canary_key,'passed',r.passed,'evidence_sha256',r.evidence_sha256,
    'authority_ceiling',r.authority_ceiling,'provider_write',r.provider_write,
    'money_movement',r.money_movement,'d3_effect',r.d3_effect,'observed_at',r.observed_at
  ) order by r.observed_at),'[]'::jsonb)
  into v_receipts
  from public.penta_system_production_receipts_v1 r
  where r.system_key='penta.balancer' and r.system_version='1.5.0';

  v_status:=penta_balancer.full_status_v1();
  v_manifest:=jsonb_pretty(jsonb_build_object(
    'contract','ct.pentabalancer.production-source-custody.v1',
    'repository','crownthrive1/CrownThrive-OS',
    'branch','codex/pentabalancer-production-20260904',
    'replay_path','supabase/migrations/20260904070000_pentabalancer_production_replay.sql',
    'replay_sha256',encode(extensions.digest(convert_to(v_sql,'UTF8'),'sha256'),'hex'),
    'replay_bytes',octet_length(convert_to(v_sql,'UTF8')),
    'migrations',v_migrations,
    'production_receipts',v_receipts,
    'runtime_status',v_status,
    'sole_responsibility','scheduler_load_balance_and_temporal_cohesion',
    'cohesion_target',100,
    'blanket_promotion',false,
    'exact_receipt_required',true,
    'provider_write',false,'money_movement',false,'d3_effect',false,
    'authority_created',false,'generated_at',v_now
  ));

  v_runbook:=format(E'# PentaBalancer Production Runtime\n\n## Scope\n\nPentaBalancer has one production responsibility: scheduler load balancing and exact temporal cohesion with PentaTime, PentaClock, PentaTick, and PentaCrons. It does not execute business workflows, move money, perform provider writes, generate content, or create authority.\n\n## Runtime contract\n\n- Pressure is measured from bounded PostgreSQL session, lock, cron-runner, and recent-failure observations.\n- The controller uses deterministic hysteresis across NORMAL, WATCH, SHED, RECOVERY, and HOLD.\n- Critical and high-priority lanes remain available. Normal and elastic lanes may be temporarily deferred under pressure.\n- No operation or cron is permanently disabled by PentaBalancer.\n- Managed jobs retain their original schedule, owner, original command, and SHA-256. `penta_balancer.restore_job_v1(text)` performs exact reversible restoration.\n- Core temporal jobs are never wrapped.\n- Exact cohesion is continuously checked across live cron, desired state, permanent state, PentaSELF repair expectations, scheduler registration, and operation enablement.\n\n## Production evidence\n\nThe authoritative receipt set and current runtime readback are stored in `docs/evidence/PENTABALANCER_PRODUCTION_20260904.json`. The byte-exact applied migration replay is stored in `supabase/migrations/20260904070000_pentabalancer_production_replay.sql`.\n\n## All-Penta maturation\n\nThe existing PentaCertify clock now invokes the specialist maturation controller. It routes each nonproduction Penta through the existing PentaHelper, PentaFactory, PentaTest, PentaSecurity, and PentaCertify chain according to deterministic evidence. Production promotion remains fail-closed and requires an exact system-version receipt. Blanket promotion is forbidden.\n\n## Recovery\n\n1. Read `penta_balancer.full_status_v1()`.\n2. Confirm `cohesion_score = 100` and `actual_command_drift = 0`.\n3. Use `penta_balancer.ensure_core_cohesion_v1()` only for core temporal drift.\n4. Use `penta_balancer.restore_job_v1(jobname)` for an exact managed-job rollback.\n5. Never modify an original command without updating and recertifying its SHA-256 custody record.\n\nGenerated: %s\n',v_now::text);

  v_sql_write:=integration_control.penta_balancer_github_put_source_v1(
    'supabase/migrations/20260904070000_pentabalancer_production_replay.sql',v_sql,
    'feat(pentabalancer): custody production runtime replay'
  );
  v_manifest_write:=integration_control.penta_balancer_github_put_source_v1(
    'docs/evidence/PENTABALANCER_PRODUCTION_20260904.json',v_manifest,
    'docs(pentabalancer): add production evidence manifest'
  );
  v_runbook_write:=integration_control.penta_balancer_github_put_source_v1(
    'docs/runbooks/PENTABALANCER_PRODUCTION.md',v_runbook,
    'docs(pentabalancer): add production operations runbook'
  );

  v_evidence:=jsonb_build_object(
    'state','VERIFIED','sql',v_sql_write,'manifest',v_manifest_write,'runbook',v_runbook_write,
    'replay_sha256',encode(extensions.digest(convert_to(v_sql,'UTF8'),'sha256'),'hex'),
    'migration_count',jsonb_array_length(v_migrations),
    'production_receipt_count',jsonb_array_length(v_receipts),
    'secret_exposed',false,'authority_created',false,'observed_at',v_now
  );
  v_evidence_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');

  insert into integration_control.penta_certify_receipts_v3(event_type,state,evidence)
  values('penta.balancer.github-source-custody','completed',v_evidence||jsonb_build_object('evidence_sha256',v_evidence_sha));

  update public.penta_system_registry
     set metadata=metadata||jsonb_build_object(
       'github_repository','crownthrive1/CrownThrive-OS',
       'github_branch','codex/pentabalancer-production-20260904',
       'github_replay_path','supabase/migrations/20260904070000_pentabalancer_production_replay.sql',
       'github_replay_sha256',v_evidence->>'replay_sha256',
       'github_source_custody_state','verified',
       'github_source_custody_evidence_sha256',v_evidence_sha,
       'github_source_custody_at',v_now
     ),updated_at=v_now
   where system_key='penta.balancer';

  return v_evidence||jsonb_build_object('evidence_sha256',v_evidence_sha);
end;
$$;

revoke all on function integration_control.penta_balancer_github_put_source_v1(text,text,text) from public,anon,authenticated;
revoke all on function integration_control.penta_balancer_github_source_custody_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_balancer_github_put_source_v1(text,text,text) to service_role;
grant execute on function integration_control.penta_balancer_github_source_custody_v1() to service_role;
