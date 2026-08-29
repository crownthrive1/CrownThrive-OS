-- CrownThrive OS — PentaSELF monotonic production convergence v2
-- Purpose: preserve newer certified production state, make repair/source convergence durable,
-- and prevent stale observations or stale scheduler definitions from rolling back working lanes.
-- Legitimate provider/circuit/kill-switch holds remain fail-closed. Rollback requires a bounded D3 authorization.

create schema if not exists penta_self;

create table if not exists penta_self.rollback_authorizations_v1 (
  authorization_id uuid primary key default gen_random_uuid(),
  subject_key text not null,
  authority_class text not null default 'D3' check (authority_class = 'D3'),
  authority_ref text not null,
  reason text not null,
  authorized_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  check (expires_at > authorized_at)
);
create index if not exists rollback_authorizations_subject_active_idx
  on penta_self.rollback_authorizations_v1(subject_key, expires_at)
  where consumed_at is null;
alter table penta_self.rollback_authorizations_v1 enable row level security;
revoke all on penta_self.rollback_authorizations_v1 from public, anon, authenticated;
grant select, insert, update on penta_self.rollback_authorizations_v1 to service_role;
drop policy if exists rollback_authorizations_service_role_v1 on penta_self.rollback_authorizations_v1;
create policy rollback_authorizations_service_role_v1 on penta_self.rollback_authorizations_v1
  for all to service_role using (true) with check (true);

create table if not exists penta_self.production_invariants_v2 (
  invariant_key text primary key,
  subject_key text not null,
  desired_version text not null,
  desired_state jsonb not null,
  source_ref text not null,
  source_sha text,
  authority_ref text not null,
  authority_class text not null default 'D2',
  rollback_requires_d3 boolean not null default true,
  enforcement_mode text not null default 'reconcile'
    check (enforcement_mode in ('observe','reconcile','block_regression')),
  enabled boolean not null default true,
  effective_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table penta_self.production_invariants_v2 enable row level security;
revoke all on penta_self.production_invariants_v2 from public, anon, authenticated;
grant select, insert, update on penta_self.production_invariants_v2 to service_role;
drop policy if exists production_invariants_service_role_v2 on penta_self.production_invariants_v2;
create policy production_invariants_service_role_v2 on penta_self.production_invariants_v2
  for all to service_role using (true) with check (true);

create table if not exists penta_self.required_cron_contracts_v2 (
  jobname text primary key,
  schedule text not null,
  command text not null,
  authority_ref text not null,
  protected_from_stale_rewrite boolean not null default true,
  enabled boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table penta_self.required_cron_contracts_v2 enable row level security;
revoke all on penta_self.required_cron_contracts_v2 from public, anon, authenticated;
grant select, insert, update on penta_self.required_cron_contracts_v2 to service_role;
drop policy if exists required_cron_contracts_service_role_v2 on penta_self.required_cron_contracts_v2;
create policy required_cron_contracts_service_role_v2 on penta_self.required_cron_contracts_v2
  for all to service_role using (true) with check (true);

create table if not exists penta_self.monotonic_guard_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  run_kind text not null,
  state text not null,
  checked_count integer not null default 0,
  repaired_count integer not null default 0,
  held_count integer not null default 0,
  details jsonb not null default '{}'::jsonb,
  payload_sha256 text not null,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists monotonic_guard_receipts_observed_idx
  on penta_self.monotonic_guard_receipts_v2(observed_at desc);
alter table penta_self.monotonic_guard_receipts_v2 enable row level security;
revoke all on penta_self.monotonic_guard_receipts_v2 from public, anon, authenticated;
grant select, insert on penta_self.monotonic_guard_receipts_v2 to service_role;
drop policy if exists monotonic_guard_receipts_read_service_role_v2 on penta_self.monotonic_guard_receipts_v2;
create policy monotonic_guard_receipts_read_service_role_v2 on penta_self.monotonic_guard_receipts_v2
  for select to service_role using (true);
drop policy if exists monotonic_guard_receipts_insert_service_role_v2 on penta_self.monotonic_guard_receipts_v2;
create policy monotonic_guard_receipts_insert_service_role_v2 on penta_self.monotonic_guard_receipts_v2
  for insert to service_role with check (true);

create or replace function penta_self.reject_monotonic_receipt_mutation_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self as $$
begin
  raise exception 'penta_self.monotonic_guard_receipts_v2 is append-only';
end $$;
revoke all on function penta_self.reject_monotonic_receipt_mutation_v2() from public, anon, authenticated;
grant execute on function penta_self.reject_monotonic_receipt_mutation_v2() to service_role;
drop trigger if exists monotonic_guard_receipts_immutable_v2 on penta_self.monotonic_guard_receipts_v2;
create trigger monotonic_guard_receipts_immutable_v2 before update or delete
on penta_self.monotonic_guard_receipts_v2 for each row
execute function penta_self.reject_monotonic_receipt_mutation_v2();

create or replace function penta_self.has_active_rollback_authorization_v1(p_subject_key text)
returns boolean language sql stable security definer set search_path=pg_catalog,penta_self as $$
  select exists(
    select 1 from penta_self.rollback_authorizations_v1
    where subject_key=p_subject_key and authority_class='D3'
      and consumed_at is null and authorized_at<=now() and expires_at>now()
  )
$$;
revoke all on function penta_self.has_active_rollback_authorization_v1(text) from public, anon, authenticated;
grant execute on function penta_self.has_active_rollback_authorization_v1(text) to service_role;

create or replace function penta_self.prevent_unapproved_regression_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self as $$
declare
  v_subject text := tg_argv[0];
  v_old jsonb := to_jsonb(old);
  v_new jsonb := to_jsonb(new);
  v_identity text;
  v_old_num numeric;
  v_new_num numeric;
begin
  if penta_self.has_active_rollback_authorization_v1(v_subject) then return new; end if;

  if v_subject='ct.pentamarketer.locticians.claim.20260827.v1' then
    v_identity := coalesce(v_new->>'campaign_id',v_new->>'campaign_key',v_new->>'stable_id',v_new->>'contract_key',v_old->>'campaign_id',v_old->>'campaign_key',v_old->>'stable_id',v_old->>'contract_key');
    if v_identity=v_subject then
      if coalesce(v_old->>'daily_cap','') ~ '^[0-9]+$' and coalesce(v_new->>'daily_cap','') ~ '^[0-9]+$' then
        v_old_num := (v_old->>'daily_cap')::numeric; v_new_num := (v_new->>'daily_cap')::numeric;
        if v_old_num>=200 and v_new_num<200 then raise exception 'unapproved campaign daily-cap regression for %',v_subject; end if;
      end if;
      if coalesce(v_old->>'monthly_cap','') ~ '^[0-9]+$' and coalesce(v_new->>'monthly_cap','') ~ '^[0-9]+$' then
        v_old_num := (v_old->>'monthly_cap')::numeric; v_new_num := (v_new->>'monthly_cap')::numeric;
        if v_old_num>=5000 and v_new_num<5000 then raise exception 'unapproved campaign monthly-cap regression for %',v_subject; end if;
      end if;
    end if;
  elsif v_subject='ct.pentamarketer.persona-execution-bridge' then
    if lower(coalesce(v_old->>'certification_state',''))='production'
       and lower(coalesce(v_new->>'certification_state',''))<>'production' then
      raise exception 'unapproved production certification regression for %',v_subject;
    end if;
  elsif v_subject='ct.locticians.brilliant-directories.api-fabric.v3' then
    if coalesce(v_new->'metadata'->>'provider_key_id','') in ('15','16') then
      raise exception 'stale failed Brilliant Directories bootstrap key may not replace current V3 lane';
    end if;
  end if;
  return new;
end $$;
revoke all on function penta_self.prevent_unapproved_regression_v2() from public, anon, authenticated;
grant execute on function penta_self.prevent_unapproved_regression_v2() to service_role;

do $$
begin
  if to_regclass('crm.penta_marketer_campaign_v1') is not null then
    execute 'drop trigger if exists penta_marketer_campaign_no_regression_v2 on crm.penta_marketer_campaign_v1';
    execute 'create trigger penta_marketer_campaign_no_regression_v2 before update on crm.penta_marketer_campaign_v1 for each row execute function penta_self.prevent_unapproved_regression_v2(''ct.pentamarketer.locticians.claim.20260827.v1'')';
  end if;
  if to_regclass('crm.penta_persona_execution_control_v1') is not null then
    execute 'drop trigger if exists penta_persona_execution_no_regression_v2 on crm.penta_persona_execution_control_v1';
    execute 'create trigger penta_persona_execution_no_regression_v2 before update on crm.penta_persona_execution_control_v1 for each row execute function penta_self.prevent_unapproved_regression_v2(''ct.pentamarketer.persona-execution-bridge'')';
  end if;
  if to_regclass('integration_control.locticians_provider_key_lanes_v1') is not null then
    execute 'drop trigger if exists locticians_bd_key_lane_no_regression_v2 on integration_control.locticians_provider_key_lanes_v1';
    execute 'create trigger locticians_bd_key_lane_no_regression_v2 before update on integration_control.locticians_provider_key_lanes_v1 for each row execute function penta_self.prevent_unapproved_regression_v2(''ct.locticians.brilliant-directories.api-fabric.v3'')';
  end if;
end $$;

insert into penta_self.production_invariants_v2
(invariant_key,subject_key,desired_version,desired_state,source_ref,source_sha,authority_ref,authority_class,enforcement_mode,metadata)
values
('pentaself.monotonic.v2','ct.penta.self.continuous-healing.v1','2.0.0',jsonb_build_object('state','production','failure_aggregation','fail_closed','repair_persistence','source_plus_runtime','rollback','explicit_d3_only'),'CrownThrive-OS/supabase/migrations/20260829021500_penta_self_monotonic_production_convergence_v2.sql',null,'Founder directive 2026-08-28','D2','block_regression',jsonb_build_object('stale_observation_may_not_overwrite_newer_success',true,'provider_holds_preserved',true)),
('pentamarketer.locticians.campaign','ct.pentamarketer.locticians.claim.20260827.v1','3.0.0',jsonb_build_object('daily_cap',200,'monthly_cap',5000,'minimum_queue_watermark',40,'target_queue_watermark',80,'state','ACTIVE'),'CrownThrive-OS/contracts/locticians-dynamic-outreach-v3.json',null,'Founder directive 2026-08-28','D2','block_regression',jsonb_build_object('effective_rate_remains_provider_adaptive',true)),
('persona.execution.bridge','ct.pentamarketer.persona-execution-bridge','1.0.0',jsonb_build_object('certification_state','production','automation_enabled',true,'kill_switch',false),'CrownThrive-OS PentaMarketer Persona Execution Bridge v1',null,'ct.assure.39f515758c338556216a24cb741f21bb','D2','block_regression',jsonb_build_object('d3_auto',false)),
('locticians.bd.fabric','ct.locticians.brilliant-directories.api-fabric.v3','3.1.0',jsonb_build_object('primary_lane','WARM_PRIMARY','shared_provider_quota',true,'switch_on_429',false,'reference_execution_authority',false),'CrownThrive-OS/contracts/locticians-dynamic-outreach-v3.json',null,'ct.locticians.brilliant-directories.api-fabric.v3','D2','block_regression',jsonb_build_object('provider_or_circuit_failure_may_degrade_observed_state',true))
on conflict (invariant_key) do update set
  subject_key=excluded.subject_key, desired_version=excluded.desired_version,
  desired_state=excluded.desired_state, source_ref=excluded.source_ref,
  source_sha=coalesce(excluded.source_sha,penta_self.production_invariants_v2.source_sha),
  authority_ref=excluded.authority_ref, authority_class=excluded.authority_class,
  enforcement_mode=excluded.enforcement_mode,
  metadata=penta_self.production_invariants_v2.metadata||excluded.metadata,
  enabled=true, effective_at=greatest(penta_self.production_invariants_v2.effective_at,now()), updated_at=now();

insert into penta_self.required_cron_contracts_v2(jobname,schedule,command,authority_ref,metadata)
values
('ct-software-factory-continuity-v5','*/2 * * * *','select public.ct_factory_continuity_cycle(1); select penta_self.penta_self_monotonic_guard_v2(''factory_post'');','ct.penta.self.continuous-healing.v1',jsonb_build_object('failure_does_not_authorize_configuration_rollback',true)),
('ct-penta-self-v1','*/2 * * * *','select public.penta_self_tick_guarded_v2();','ct.penta.self.continuous-healing.v1',jsonb_build_object('guarded',true)),
('ct-penta-self-continuous-healing-v1','1-59/2 * * * *','select public.penta_self_continuous_healing_tick_guarded_v2();','ct.penta.self.continuous-healing.v1',jsonb_build_object('guarded',true)),
('ct-penta-self-monotonic-guard-v2','* * * * *','select penta_self.penta_self_monotonic_guard_v2(''watchdog'');','ct.penta.self.continuous-healing.v1',jsonb_build_object('independent_watchdog',true)),
('ct-penta-self-monotonic-daily-v2','43 6 * * *','select penta_self.penta_self_monotonic_guard_v2(''daily_receipt'');','ct.penta.self.continuous-healing.v1',jsonb_build_object('daily_receipt',true)),
('penta-persona-execution-v1','* * * * *','select crm.penta_marketer_growth_factory_seed_v1(); select crm.penta_persona_execution_scheduler_tick_v1(25); select crm.penta_persona_execution_tick_v1(10);','ct.pentamarketer.persona-execution-bridge',jsonb_build_object('production',true)),
('pentafactory-daily-agent-fleet-10x100-v1','5 8 * * *','select public.pentafactory_daily_fleet_tick_v1();','ct.pentafactory.daily-agent-fleet.v1',jsonb_build_object('production',true)),
('ct-penta-census-native-due-v1','*/5 * * * *','select integration_control.penta_census_scheduler_tick_v1();','ct.penta.census.v1.1',jsonb_build_object('runtime_operating',true,'canonical_maturity','implemented')),
('ct-pentamarketer-intake-cycle-v1','7,22,37,52 * * * *','select crm.locticians_native_action_cycle_v1(25); select crm.penta_marketer_external_email_cycle_v1(25); select crm.penta_marketer_promote_ready_external_email_v1(25); select crm.penta_marketer_service_form_cycle_v1(25);','ct.pentamarketer.persona-execution-bridge',jsonb_build_object('production',true)),
('ct-locticians-native-monitor-v1','*/15 * * * *','select crm.locticians_native_monitor_cycle_v1();','ct.locticians.brilliant-directories.api-fabric.v3',jsonb_build_object('production',true)),
('ct-locticians-bd-reference-daily-v3','31 6 * * *','select integration_control.locticians_bd_reference_daily_receipt_v3();','ct.locticians.brilliant-directories.api-fabric.v3',jsonb_build_object('reference_execution_authority',false)),
('ct-locticians-bd-failover-reconcile-v3','11 * * * *','select integration_control.locticians_bd_warm_failover_reconcile_v3();','ct.locticians.brilliant-directories.api-fabric.v3',jsonb_build_object('switch_on_429',false)),
('ct-locticians-bd-failover-daily-v3','37 6 * * *','select integration_control.locticians_bd_warm_failover_daily_receipt_v3();','ct.locticians.brilliant-directories.api-fabric.v3',jsonb_build_object('daily_receipt',true)),
('ct-locticians-article-schedule-dispatch-v1','5,15,25,35,45,55 * * * *','select public.locticians_article_schedule_dispatch_v1(5);','ct.route.locticians.bd-articles.production.v1',jsonb_build_object('ambiguous_outcome','quarantine')),
('ct-locticians-article-live-verifier-v1','*/10 * * * *','select public.locticians_article_schedule_due_verifier_v1(10);','ct.route.locticians.bd-articles.production.v1',jsonb_build_object('read_after_write',true))
on conflict (jobname) do update set
  schedule=excluded.schedule, command=excluded.command, authority_ref=excluded.authority_ref,
  protected_from_stale_rewrite=true, enabled=true,
  metadata=penta_self.required_cron_contracts_v2.metadata||excluded.metadata, updated_at=now();

create or replace function penta_self.penta_self_monotonic_guard_v2(p_run_kind text default 'watchdog')
returns jsonb language plpgsql security definer
set search_path=pg_catalog,penta_self,cron,crm,integration_control,public,chlom_runtime,extensions as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_job record; v_existing record;
  v_checked integer := 0; v_repaired integer := 0; v_held integer := 0;
  v_details jsonb := '[]'::jsonb; v_payload jsonb; v_digest text; v_receipt uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.self.monotonic.guard.v2',0)) then
    return jsonb_build_object('state','SKIPPED_LOCKED','run_kind',p_run_kind,'observed_at',now());
  end if;

  for v_job in select * from penta_self.required_cron_contracts_v2 where enabled order by jobname loop
    v_checked := v_checked+1;
    select jobid,jobname,schedule,command,active into v_existing
      from cron.job where jobname=v_job.jobname order by jobid desc limit 1;
    if not found then
      perform cron.schedule(v_job.jobname,v_job.schedule,v_job.command);
      v_repaired := v_repaired+1;
      v_details := v_details||jsonb_build_array(jsonb_build_object('jobname',v_job.jobname,'action','created'));
    elsif v_existing.schedule is distinct from v_job.schedule
       or v_existing.command is distinct from v_job.command
       or v_existing.active is distinct from true then
      update cron.job set schedule=v_job.schedule,command=v_job.command,active=true where jobid=v_existing.jobid;
      v_repaired := v_repaired+1;
      v_details := v_details||jsonb_build_array(jsonb_build_object('jobname',v_job.jobname,'action','reconciled','previous_schedule',v_existing.schedule,'previous_active',v_existing.active));
    end if;
  end loop;

  if to_regclass('crm.penta_persona_execution_control_v1') is not null then
    update crm.penta_persona_execution_control_v1
       set active=true,automation_enabled=true,certification_state='production',
           metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('monotonic_guard_version','2.0.0','last_guarded_at',now(),'rollback_requires_d3',true),updated_at=now()
     where control_key='default' and kill_switch=false
       and (active is distinct from true or automation_enabled is distinct from true or certification_state is distinct from 'production');
    if found then v_repaired:=v_repaired+1; end if;
  end if;

  if to_regclass('integration_control.locticians_provider_key_lanes_v1') is not null then
    update integration_control.locticians_provider_key_lanes_v1
       set enabled=false, provider_status='stale_failed_bootstrap_quarantined', dispatch_state='HOLD_STALE_BOOTSTRAP',
           metadata=coalesce(metadata,'{}'::jsonb)-'supersedes_failed_bootstrap_provider_key_id'||jsonb_build_object('monotonic_guard_version','2.0.0','stale_bootstrap_reentry_forbidden',true,'switch_on_429',false),updated_at=now()
     where service_id='locticians' and coalesce(metadata->>'provider_key_id','') in ('15','16');
    if found then
      v_held:=v_held+1;
      v_details:=v_details||jsonb_build_array(jsonb_build_object('subject','locticians_bd_key_lanes','action','stale_failed_key_quarantined'));
    end if;
  end if;

  if to_regclass('penta_self.problem_ledger_v1') is not null and to_regclass('cron.job_run_details') is not null then
    with latest_success as (
      select j.jobname,max(d.start_time) as success_at
      from cron.job j join cron.job_run_details d on d.jobid=j.jobid
      where d.status='succeeded' group by j.jobname
    )
    update penta_self.problem_ledger_v1 p
       set state='resolved',resolved_at=coalesce(p.resolved_at,now()),
           verification_evidence=coalesce(p.verification_evidence,'{}'::jsonb)||jsonb_build_object('resolved_by','penta_self_monotonic_guard_v2','latest_success_at',s.success_at,'stale_failure_did_not_rollback_runtime',true),updated_at=now()
      from latest_success s
     where p.state not in ('resolved','closed','superseded','cancelled')
       and p.title='Latest active cron execution failed: '||s.jobname
       and s.success_at>coalesce((p.evidence->>'failed_at')::timestamptz,p.last_seen_at);
    if found then v_repaired:=v_repaired+1; end if;
  end if;

  v_payload:=jsonb_build_object(
    'state',case when v_held>0 then 'DEGRADED_GUARDED' else 'PASS' end,
    'run_kind',p_run_kind,'checked_count',v_checked,'repaired_count',v_repaired,'held_count',v_held,
    'details',v_details,'rollback_requires_d3',true,'provider_and_circuit_holds_preserved',true,
    'stale_observation_may_not_overwrite_newer_success',true,'observed_at',now());
  v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
  insert into penta_self.monotonic_guard_receipts_v2(run_kind,state,checked_count,repaired_count,held_count,details,payload_sha256)
  values(p_run_kind,v_payload->>'state',v_checked,v_repaired,v_held,v_details,v_digest)
  returning receipt_id into v_receipt;

  if p_run_kind in ('daily_receipt','migration_canary') or v_repaired>0 or v_held>0 then
    perform chlom_runtime.append_dail_event('pentaself.monotonic_guard.receipt','production_convergence','ct.penta.self.continuous-healing.v1',v_payload,'PentaSELF/PentaSerialized',null,'PentaSELF','2.0.0',v_digest,null,'ct.penta.self.continuous-healing.v1',null,'internal');
  end if;
  return v_payload||jsonb_build_object('receipt_id',v_receipt,'payload_sha256',v_digest);
end $$;
revoke all on function penta_self.penta_self_monotonic_guard_v2(text) from public, anon, authenticated;
grant execute on function penta_self.penta_self_monotonic_guard_v2(text) to service_role;

create or replace function public.penta_self_tick_guarded_v2()
returns jsonb language plpgsql security definer set search_path=pg_catalog,public,penta_self,extensions as $$
declare v_pre jsonb; v_tick jsonb; v_post jsonb;
begin
  v_pre:=penta_self.penta_self_monotonic_guard_v2('pentaself_pre');
  begin v_tick:=public.penta_self_tick_v1();
  exception when others then v_tick:=jsonb_build_object('state','FAILED','error_class',sqlstate,'error_sha256',encode(extensions.digest(sqlerrm,'sha256'),'hex')); end;
  v_post:=penta_self.penta_self_monotonic_guard_v2('pentaself_post');
  return jsonb_build_object('state',case when coalesce(v_tick->>'state','') in ('FAILED','DEGRADED') then 'DEGRADED' else 'PASS' end,'pre',v_pre,'tick',v_tick,'post',v_post,'rollback_performed',false);
end $$;
revoke all on function public.penta_self_tick_guarded_v2() from public, anon, authenticated;
grant execute on function public.penta_self_tick_guarded_v2() to service_role;

create or replace function public.penta_self_continuous_healing_tick_guarded_v2()
returns jsonb language plpgsql security definer set search_path=pg_catalog,public,penta_self,extensions as $$
declare v_pre jsonb; v_tick jsonb; v_post jsonb;
begin
  v_pre:=penta_self.penta_self_monotonic_guard_v2('healing_pre');
  begin v_tick:=public.penta_self_continuous_healing_tick_v1();
  exception when others then v_tick:=jsonb_build_object('state','FAILED','error_class',sqlstate,'error_sha256',encode(extensions.digest(sqlerrm,'sha256'),'hex')); end;
  v_post:=penta_self.penta_self_monotonic_guard_v2('healing_post');
  return jsonb_build_object('state',case when coalesce(v_tick->>'state','') in ('FAILED','DEGRADED') then 'DEGRADED' else 'PASS' end,'pre',v_pre,'tick',v_tick,'post',v_post,'rollback_performed',false);
end $$;
revoke all on function public.penta_self_continuous_healing_tick_guarded_v2() from public, anon, authenticated;
grant execute on function public.penta_self_continuous_healing_tick_guarded_v2() to service_role;

select penta_self.penta_self_monotonic_guard_v2('migration_canary');
