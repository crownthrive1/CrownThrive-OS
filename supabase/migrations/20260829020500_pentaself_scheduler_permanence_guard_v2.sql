-- CrownThrive OS / PentaSELF scheduler permanence guard v2
-- Rejects stale desired-state generations and restores only the newest governed schedule.

create table if not exists integration_control.scheduler_desired_jobs_v2 (
  jobname text primary key,
  schedule text not null,
  command text not null,
  database_name text not null default current_database(),
  username text not null default current_user,
  active boolean not null default true,
  generation bigint not null,
  source_ref text not null,
  desired_sha256 text not null,
  allow_auto_restore boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.scheduler_reconcile_events_v2 (
  event_id uuid primary key default gen_random_uuid(),
  jobname text not null,
  generation bigint not null,
  observed_state jsonb not null default '{}'::jsonb,
  desired_state jsonb not null default '{}'::jsonb,
  action text not null,
  result_state text not null,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now()
);

alter table integration_control.scheduler_desired_jobs_v2 enable row level security;
alter table integration_control.scheduler_reconcile_events_v2 enable row level security;
revoke all on integration_control.scheduler_desired_jobs_v2 from public, anon, authenticated;
revoke all on integration_control.scheduler_reconcile_events_v2 from public, anon, authenticated;
grant select, insert, update, delete on integration_control.scheduler_desired_jobs_v2 to service_role;
grant select, insert on integration_control.scheduler_reconcile_events_v2 to service_role;
drop policy if exists scheduler_desired_jobs_service_role_v2 on integration_control.scheduler_desired_jobs_v2;
create policy scheduler_desired_jobs_service_role_v2 on integration_control.scheduler_desired_jobs_v2 for all to service_role using (true) with check (true);
drop policy if exists scheduler_reconcile_events_select_service_role_v2 on integration_control.scheduler_reconcile_events_v2;
create policy scheduler_reconcile_events_select_service_role_v2 on integration_control.scheduler_reconcile_events_v2 for select to service_role using (true);
drop policy if exists scheduler_reconcile_events_insert_service_role_v2 on integration_control.scheduler_reconcile_events_v2;
create policy scheduler_reconcile_events_insert_service_role_v2 on integration_control.scheduler_reconcile_events_v2 for insert to service_role with check (true);

create or replace function integration_control.scheduler_reconcile_events_immutable_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,integration_control as $$
begin
  raise exception 'scheduler_reconcile_events_v2 is append-only';
end $$;
revoke all on function integration_control.scheduler_reconcile_events_immutable_v2() from public, anon, authenticated;
grant execute on function integration_control.scheduler_reconcile_events_immutable_v2() to service_role;
drop trigger if exists scheduler_reconcile_events_immutable_v2 on integration_control.scheduler_reconcile_events_v2;
create trigger scheduler_reconcile_events_immutable_v2 before update or delete on integration_control.scheduler_reconcile_events_v2 for each row execute function integration_control.scheduler_reconcile_events_immutable_v2();

create or replace function integration_control.scheduler_desired_job_upsert_v2(
  p_jobname text,
  p_schedule text,
  p_command text,
  p_generation bigint,
  p_source_ref text,
  p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path=pg_catalog,integration_control,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_digest text;
  v_existing_generation bigint;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_jobname is null or btrim(p_jobname)='' or p_schedule is null or btrim(p_schedule)='' or p_command is null or btrim(p_command)='' then raise exception 'jobname_schedule_command_required'; end if;
  select generation into v_existing_generation from integration_control.scheduler_desired_jobs_v2 where jobname=p_jobname;
  if v_existing_generation is not null and p_generation < v_existing_generation then
    return jsonb_build_object('updated',false,'reason','stale_generation_rejected','jobname',p_jobname,'existing_generation',v_existing_generation,'attempted_generation',p_generation);
  end if;
  v_digest := encode(extensions.digest(convert_to(jsonb_build_object('jobname',p_jobname,'schedule',p_schedule,'command',p_command,'generation',p_generation)::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.scheduler_desired_jobs_v2(jobname,schedule,command,generation,source_ref,desired_sha256,metadata,updated_at)
  values(p_jobname,p_schedule,p_command,p_generation,p_source_ref,v_digest,coalesce(p_metadata,'{}'::jsonb),now())
  on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,generation=excluded.generation,source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=now()
  where excluded.generation >= integration_control.scheduler_desired_jobs_v2.generation;
  return jsonb_build_object('updated',true,'jobname',p_jobname,'generation',p_generation,'desired_sha256',v_digest);
end $$;
revoke all on function integration_control.scheduler_desired_job_upsert_v2(text,text,text,bigint,text,jsonb) from public, anon, authenticated;
grant execute on function integration_control.scheduler_desired_job_upsert_v2(text,text,text,bigint,text,jsonb) to service_role;

create or replace function integration_control.scheduler_permanence_reconcile_v2()
returns jsonb
language plpgsql security definer
set search_path=pg_catalog,integration_control,cron,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  d record;
  c record;
  v_action text;
  v_digest text;
  v_checked int:=0;
  v_restored int:=0;
  v_healthy int:=0;
  v_failed int:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.scheduler.permanence.v2',0)) then return jsonb_build_object('state','locked','checked',0); end if;
  for d in select * from integration_control.scheduler_desired_jobs_v2 where active=true and allow_auto_restore=true order by jobname loop
    v_checked:=v_checked+1;
    select jobid,jobname,schedule,command,database,username,active into c from cron.job where jobname=d.jobname order by jobid desc limit 1;
    begin
      if c.jobid is null then
        perform cron.schedule(d.jobname,d.schedule,d.command);
        v_action:='restored_missing'; v_restored:=v_restored+1;
      elsif c.schedule is distinct from d.schedule or c.command is distinct from d.command or c.active is distinct from true then
        perform cron.unschedule(c.jobid);
        perform cron.schedule(d.jobname,d.schedule,d.command);
        v_action:='restored_drift'; v_restored:=v_restored+1;
      else
        v_action:='healthy'; v_healthy:=v_healthy+1;
      end if;
      v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('jobname',d.jobname,'generation',d.generation,'action',v_action,'observed_schedule',c.schedule,'observed_command',c.command,'desired_schedule',d.schedule,'desired_command',d.command)::text,'UTF8'),'sha256'),'hex');
      if v_action<>'healthy' then
        insert into integration_control.scheduler_reconcile_events_v2(jobname,generation,observed_state,desired_state,action,result_state,evidence_sha256)
        values(d.jobname,d.generation,jsonb_build_object('jobid',c.jobid,'schedule',c.schedule,'command',c.command,'active',c.active),jsonb_build_object('schedule',d.schedule,'command',d.command,'active',true,'source_ref',d.source_ref),v_action,'applied',v_digest);
      end if;
    exception when others then
      v_failed:=v_failed+1;
      v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('jobname',d.jobname,'generation',d.generation,'error_state',sqlstate)::text,'UTF8'),'sha256'),'hex');
      insert into integration_control.scheduler_reconcile_events_v2(jobname,generation,observed_state,desired_state,action,result_state,evidence_sha256)
      values(d.jobname,d.generation,jsonb_build_object('jobid',c.jobid,'schedule',c.schedule,'active',c.active),jsonb_build_object('schedule',d.schedule,'active',true,'source_ref',d.source_ref),'restore_failed','failed',v_digest);
    end;
  end loop;
  return jsonb_build_object('state',case when v_failed>0 then 'degraded' else 'ok' end,'checked',v_checked,'healthy',v_healthy,'restored',v_restored,'failed',v_failed,'generation_floor',(select min(generation) from integration_control.scheduler_desired_jobs_v2 where active=true),'observed_at',now());
end $$;
revoke all on function integration_control.scheduler_permanence_reconcile_v2() from public, anon, authenticated;
grant execute on function integration_control.scheduler_permanence_reconcile_v2() to service_role;

select integration_control.scheduler_desired_job_upsert_v2('ct-software-factory-continuity-v5','*/2 * * * *','select public.ct_factory_continuity_cycle(1);',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaFactory/PentaSELF','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-penta-self-v1','*/2 * * * *','select public.penta_self_tick_v1();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaSELF','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-penta-self-continuous-healing-v1','1-59/2 * * * *','select public.penta_self_continuous_healing_tick_v1();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaSELF','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('pentafactory-daily-agent-fleet-10x100-v1','5 8 * * *','select public.pentafactory_daily_fleet_tick_v1();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaFactory','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('locticians-bd-contract-watch-v1','17 6 * * *','select public.locticians_bd_contract_watch_tick_v1();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaAssure/PentaUpdate','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-penta-census-native-due-v1','*/5 * * * *','select integration_control.penta_census_scheduler_tick_v1();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaCensus','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-pentamarketer-intake-cycle-v1','7,22,37,52 * * * *','select crm.locticians_native_action_cycle_v1(25); select crm.penta_marketer_external_email_cycle_v1(25); select crm.penta_marketer_promote_ready_external_email_v1(25); select crm.penta_marketer_service_form_cycle_v1(25);',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaMarketer','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-locticians-native-monitor-v1','*/15 * * * *','select crm.locticians_native_monitor_cycle_v1();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaMarketer/PentaAssure','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-locticians-bd-reference-daily-v3','31 6 * * *','select integration_control.locticians_bd_reference_daily_receipt_v3();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaUpdate/PentaAssure','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-locticians-article-live-verifier-v1','*/10 * * * *','select public.locticians_article_schedule_due_verifier_v1(10);',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaCertify','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-locticians-article-schedule-dispatch-v1','5,15,25,35,45,55 * * * *','select public.locticians_article_schedule_dispatch_v1(5);',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaMarketer/PentaTime','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-locticians-bd-failover-reconcile-v3','11 * * * *','select integration_control.locticians_bd_warm_failover_reconcile_v3();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaCredentials/PentaAssure','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('ct-locticians-bd-failover-daily-v3','37 6 * * *','select integration_control.locticians_bd_warm_failover_daily_receipt_v3();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaCredentials/PentaAssure','rollback_policy','monotonic'));
select integration_control.scheduler_desired_job_upsert_v2('penta-persona-execution-v1','* * * * *','select crm.penta_marketer_growth_factory_seed_v1(); select crm.penta_persona_execution_scheduler_tick_v1(25); select crm.penta_persona_execution_tick_v1(10);',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaMarketer/PentaWorkforce','rollback_policy','monotonic'));

insert into integration_control.scheduler_desired_jobs_v2(jobname,schedule,command,database_name,username,active,generation,source_ref,desired_sha256,allow_auto_restore,metadata)
select j.jobname,j.schedule,j.command,j.database,j.username,true,2026082901,'ct.pentaself.scheduler-permanence.v2',encode(extensions.digest(convert_to(jsonb_build_object('jobname',j.jobname,'schedule',j.schedule,'command',j.command,'generation',2026082901)::text,'UTF8'),'sha256'),'hex'),true,jsonb_build_object('owner','PentaMarketer/PentaMail','captured_from_verified_production',true,'rollback_policy','monotonic')
from cron.job j
where j.jobname in ('ct-outreach-daily-planner-v1','ct-outreach-scheduler-tick-v1')
on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username=excluded.username,active=true,generation=greatest(integration_control.scheduler_desired_jobs_v2.generation,excluded.generation),source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,allow_auto_restore=true,metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=now();

select integration_control.scheduler_desired_job_upsert_v2('ct-scheduler-permanence-guard-v2','* * * * *','select integration_control.scheduler_permanence_reconcile_v2();',2026082901,'ct.pentaself.scheduler-permanence.v2',jsonb_build_object('owner','PentaSELF/PentaTime','self_protecting',true,'rollback_policy','monotonic'));
select cron.unschedule(jobid) from cron.job where jobname='ct-scheduler-permanence-guard-v2';
select cron.schedule('ct-scheduler-permanence-guard-v2','* * * * *','select integration_control.scheduler_permanence_reconcile_v2();');
select integration_control.scheduler_permanence_reconcile_v2();
