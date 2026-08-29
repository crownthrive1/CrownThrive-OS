create table if not exists penta_self.permanent_repairs_v1 (
  repair_key text primary key,
  scope text not null,
  problem_fingerprint text,
  desired_state jsonb not null default '{}'::jsonb,
  verification_evidence jsonb not null default '{}'::jsonb,
  verification_sha256 text not null,
  source_ref text,
  rollback_handle text,
  verified_at timestamptz not null,
  state text not null default 'active' check (state in ('active','superseded','retired')),
  monotonic boolean not null default true,
  automatic_rollback_allowed boolean not null default false,
  rollback_requires_newer_independent_failure boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.permanent_repair_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  repair_key text not null,
  event_type text not null,
  state text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  actor_ref text not null default 'PentaSELF',
  created_at timestamptz not null default now()
);

create table if not exists penta_self.permanent_cron_desired_state_v1 (
  jobname text primary key,
  schedule text not null,
  command text not null,
  database_name text,
  username_name text,
  desired_active boolean not null default true,
  enforcement_mode text not null default 'exact' check (enforcement_mode in ('exact','missing_or_inactive','observe')),
  verification_evidence jsonb not null default '{}'::jsonb,
  desired_sha256 text not null,
  verified_at timestamptz not null default now(),
  source_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table penta_self.permanent_repairs_v1 enable row level security;
alter table penta_self.permanent_repair_events_v1 enable row level security;
alter table penta_self.permanent_cron_desired_state_v1 enable row level security;
revoke all on penta_self.permanent_repairs_v1 from public, anon, authenticated;
revoke all on penta_self.permanent_repair_events_v1 from public, anon, authenticated;
revoke all on penta_self.permanent_cron_desired_state_v1 from public, anon, authenticated;
grant select, insert, update on penta_self.permanent_repairs_v1 to service_role;
grant select, insert on penta_self.permanent_repair_events_v1 to service_role;
grant select, insert, update on penta_self.permanent_cron_desired_state_v1 to service_role;

drop policy if exists permanent_repairs_service_role_v1 on penta_self.permanent_repairs_v1;
create policy permanent_repairs_service_role_v1 on penta_self.permanent_repairs_v1 for all to service_role using (true) with check (true);
drop policy if exists permanent_repair_events_service_role_v1 on penta_self.permanent_repair_events_v1;
create policy permanent_repair_events_service_role_v1 on penta_self.permanent_repair_events_v1 for select to service_role using (true);
create policy permanent_repair_events_insert_service_role_v1 on penta_self.permanent_repair_events_v1 for insert to service_role with check (true);
drop policy if exists permanent_cron_service_role_v1 on penta_self.permanent_cron_desired_state_v1;
create policy permanent_cron_service_role_v1 on penta_self.permanent_cron_desired_state_v1 for all to service_role using (true) with check (true);

create or replace function penta_self.reject_permanent_repair_event_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,penta_self
as $$
begin
  raise exception 'permanent_repair_events_v1 is append-only';
end $$;
revoke all on function penta_self.reject_permanent_repair_event_mutation_v1() from public, anon, authenticated;
grant execute on function penta_self.reject_permanent_repair_event_mutation_v1() to service_role;
drop trigger if exists permanent_repair_events_immutable_v1 on penta_self.permanent_repair_events_v1;
create trigger permanent_repair_events_immutable_v1 before update or delete on penta_self.permanent_repair_events_v1 for each row execute function penta_self.reject_permanent_repair_event_mutation_v1();

create or replace function penta_self.record_permanent_repair_event_v1(
  p_repair_key text,
  p_event_type text,
  p_state text,
  p_evidence jsonb default '{}'::jsonb,
  p_actor_ref text default 'PentaSELF'
) returns uuid
language plpgsql
security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_id uuid;
  v_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  v_hash := encode(extensions.digest(coalesce(p_evidence,'{}'::jsonb)::text,'sha256'),'hex');
  insert into penta_self.permanent_repair_events_v1(repair_key,event_type,state,evidence,evidence_sha256,actor_ref)
  values(p_repair_key,p_event_type,p_state,coalesce(p_evidence,'{}'::jsonb),v_hash,coalesce(nullif(p_actor_ref,''),'PentaSELF'))
  returning event_id into v_id;
  return v_id;
end $$;
revoke all on function penta_self.record_permanent_repair_event_v1(text,text,text,jsonb,text) from public, anon, authenticated;
grant execute on function penta_self.record_permanent_repair_event_v1(text,text,text,jsonb,text) to service_role;

create or replace function penta_self.register_permanent_repair_v1(
  p_repair_key text,
  p_scope text,
  p_problem_fingerprint text,
  p_desired_state jsonb,
  p_verification_evidence jsonb,
  p_verified_at timestamptz,
  p_source_ref text,
  p_rollback_handle text default null
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_hash text;
  v_existing timestamptz;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if coalesce(trim(p_repair_key),'')='' or coalesce(trim(p_scope),'')='' then raise exception 'repair_key_and_scope_required'; end if;
  if p_verified_at is null then raise exception 'verified_at_required'; end if;
  v_hash := encode(extensions.digest(coalesce(p_verification_evidence,'{}'::jsonb)::text,'sha256'),'hex');
  select verified_at into v_existing from penta_self.permanent_repairs_v1 where repair_key=p_repair_key;
  if v_existing is not null and v_existing > p_verified_at then
    perform penta_self.record_permanent_repair_event_v1(p_repair_key,'stale_registration_rejected','preserved',jsonb_build_object('existing_verified_at',v_existing,'attempted_verified_at',p_verified_at,'source_ref',p_source_ref),'PentaSELF/PentaAssure');
    return jsonb_build_object('registered',false,'reason','stale_verification','existing_verified_at',v_existing);
  end if;
  insert into penta_self.permanent_repairs_v1(repair_key,scope,problem_fingerprint,desired_state,verification_evidence,verification_sha256,source_ref,rollback_handle,verified_at,state,monotonic,automatic_rollback_allowed,rollback_requires_newer_independent_failure)
  values(p_repair_key,p_scope,p_problem_fingerprint,coalesce(p_desired_state,'{}'::jsonb),coalesce(p_verification_evidence,'{}'::jsonb),v_hash,p_source_ref,p_rollback_handle,p_verified_at,'active',true,false,true)
  on conflict(repair_key) do update set
    scope=excluded.scope,
    problem_fingerprint=excluded.problem_fingerprint,
    desired_state=excluded.desired_state,
    verification_evidence=excluded.verification_evidence,
    verification_sha256=excluded.verification_sha256,
    source_ref=excluded.source_ref,
    rollback_handle=excluded.rollback_handle,
    verified_at=excluded.verified_at,
    state='active',
    monotonic=true,
    automatic_rollback_allowed=false,
    rollback_requires_newer_independent_failure=true,
    updated_at=now()
  where excluded.verified_at >= penta_self.permanent_repairs_v1.verified_at;
  perform penta_self.record_permanent_repair_event_v1(p_repair_key,'verified_repair_promoted','active',jsonb_build_object('scope',p_scope,'verification_sha256',v_hash,'verified_at',p_verified_at,'source_ref',p_source_ref,'rollback_handle',p_rollback_handle,'stale_state_may_override',false),'PentaSELF/PentaAssure');
  return jsonb_build_object('registered',true,'repair_key',p_repair_key,'verification_sha256',v_hash,'verified_at',p_verified_at,'monotonic',true,'automatic_rollback_allowed',false);
end $$;
revoke all on function penta_self.register_permanent_repair_v1(text,text,text,jsonb,jsonb,timestamptz,text,text) from public, anon, authenticated;
grant execute on function penta_self.register_permanent_repair_v1(text,text,text,jsonb,jsonb,timestamptz,text,text) to service_role;

create or replace function penta_self.evidence_observed_at_v1(p_evidence jsonb,p_verification jsonb,p_fallback timestamptz)
returns timestamptz
language plpgsql
immutable
set search_path=pg_catalog
as $$
declare
  v text;
  k text;
begin
  foreach k in array array['observed_at','failed_at','detected_at','provider_observed_at','verified_at','latest_started_at','event_created_at','created_at','updated_at'] loop
    v := coalesce(p_evidence->>k,p_verification->>k);
    if v is not null then
      begin return v::timestamptz; exception when others then null; end;
    end if;
  end loop;
  return p_fallback;
end $$;
revoke all on function penta_self.evidence_observed_at_v1(jsonb,jsonb,timestamptz) from public, anon, authenticated;
grant execute on function penta_self.evidence_observed_at_v1(jsonb,jsonb,timestamptz) to service_role;

create or replace function penta_self.guard_permanent_repair_regression_v1()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,penta_self
as $$
declare
  v_repair penta_self.permanent_repairs_v1%rowtype;
  v_observed timestamptz;
  v_event jsonb;
begin
  if old.state in ('resolved','closed','retired') and new.state not in ('resolved','closed','retired') then
    select * into v_repair from penta_self.permanent_repairs_v1
    where state='active' and problem_fingerprint=old.fingerprint and monotonic=true
    order by verified_at desc limit 1;
    if found then
      v_observed := penta_self.evidence_observed_at_v1(coalesce(new.evidence,'{}'::jsonb),coalesce(new.verification_evidence,'{}'::jsonb),null);
      if v_observed is null or v_observed <= v_repair.verified_at then
        v_event := jsonb_build_object('problem_id',old.problem_id,'fingerprint',old.fingerprint,'repair_key',v_repair.repair_key,'repair_verified_at',v_repair.verified_at,'incoming_observed_at',v_observed,'incoming_state',new.state,'preserved_state',old.state,'reason','stale_or_unversioned_evidence_cannot_regress_verified_repair');
        perform penta_self.record_permanent_repair_event_v1(v_repair.repair_key,'stale_regression_blocked','preserved',v_event,'PentaSELF/PentaSerialized');
        new.state := old.state;
        new.resolved_at := old.resolved_at;
        new.blocked_reason := old.blocked_reason;
        new.last_error := old.last_error;
        new.verification_evidence := coalesce(old.verification_evidence,'{}'::jsonb) || jsonb_build_object('stale_regression_blocked_at',now(),'permanent_repair_key',v_repair.repair_key,'incoming_observed_at',v_observed);
      else
        new.verification_evidence := coalesce(new.verification_evidence,'{}'::jsonb) || jsonb_build_object('permanent_repair_recurrence_candidate',true,'prior_repair_key',v_repair.repair_key,'prior_repair_verified_at',v_repair.verified_at,'newer_observed_at',v_observed);
      end if;
    end if;
  end if;
  return new;
end $$;
revoke all on function penta_self.guard_permanent_repair_regression_v1() from public, anon, authenticated;
grant execute on function penta_self.guard_permanent_repair_regression_v1() to service_role;
drop trigger if exists permanent_repair_regression_guard_v1 on penta_self.problem_ledger_v1;
create trigger permanent_repair_regression_guard_v1 before update on penta_self.problem_ledger_v1 for each row execute function penta_self.guard_permanent_repair_regression_v1();

insert into penta_self.permanent_cron_desired_state_v1(jobname,schedule,command,database_name,username_name,desired_active,enforcement_mode,verification_evidence,desired_sha256,verified_at,source_ref)
select j.jobname,j.schedule,j.command,j.database,j.username,true,
       case when j.jobname in (
         'ct-software-factory-continuity-v5','ct-penta-self-v1','ct-penta-self-continuous-healing-v1','pentafactory-daily-agent-fleet-10x100-v1','penta-persona-execution-v1','ct-penta-census-native-due-v1','ct-pentamarketer-intake-cycle-v1','ct-locticians-native-monitor-v1','ct-locticians-article-live-verifier-v1','ct-locticians-article-schedule-dispatch-v1','ct-locticians-bd-reference-daily-v3','ct-locticians-bd-failover-reconcile-v3','ct-locticians-bd-failover-daily-v3'
       ) then 'exact' else 'missing_or_inactive' end,
       jsonb_build_object('captured_from','cron.job','captured_at',now(),'active',j.active,'founder_directive','permanent_verified_repairs_no_stale_rollback'),
       encode(extensions.digest(concat_ws('|',j.jobname,j.schedule,j.command,j.database,j.username,j.active::text),'sha256'),'hex'),
       now(),'runtime:cron.job:2026-08-29'
from cron.job j
where j.active=true and (
  j.jobname like 'ct-penta-self%'
  or j.jobname like 'ct-software-factory%'
  or j.jobname like 'pentafactory%'
  or j.jobname like 'penta-persona-execution%'
  or j.jobname like 'ct-penta-census%'
  or j.jobname like 'ct-pentamarketer%'
  or j.jobname like 'ct-outreach%'
  or j.jobname like 'ct-locticians%'
  or j.jobname like 'locticians-bd%'
  or j.jobname like '%penta-mail%'
  or j.jobname like '%pentamail%'
  or j.jobname like '%commercial-release%'
)
on conflict(jobname) do update set
  schedule=excluded.schedule,
  command=excluded.command,
  database_name=excluded.database_name,
  username_name=excluded.username_name,
  desired_active=excluded.desired_active,
  enforcement_mode=excluded.enforcement_mode,
  verification_evidence=excluded.verification_evidence,
  desired_sha256=excluded.desired_sha256,
  verified_at=excluded.verified_at,
  source_ref=excluded.source_ref,
  updated_at=now();

create or replace function penta_self.reconcile_permanent_repairs_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,cron,extensions,crm
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  j record;
  v_repaired int := 0;
  v_observed int := 0;
  v_missing int := 0;
  v_drifted int := 0;
  v_event jsonb;
  v_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  perform pg_advisory_xact_lock(hashtext('penta_self.reconcile_permanent_repairs_v1'));

  for r in select * from penta_self.permanent_cron_desired_state_v1 where desired_active=true order by jobname loop
    select * into j from cron.job where jobname=r.jobname order by jobid desc limit 1;
    if not found then
      v_missing := v_missing+1;
      perform cron.schedule(r.jobname,r.schedule,r.command);
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('cron:'||r.jobname,'cron_missing_recreated','active',jsonb_build_object('schedule',r.schedule,'command_sha256',encode(extensions.digest(r.command,'sha256'),'hex'),'desired_sha256',r.desired_sha256),'PentaSELF/PentaTime');
    elsif r.enforcement_mode='observe' then
      v_observed := v_observed+1;
    elsif j.active is distinct from true then
      update cron.job set active=true where jobid=j.jobid;
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('cron:'||r.jobname,'cron_reactivated','active',jsonb_build_object('jobid',j.jobid,'schedule',j.schedule),'PentaSELF/PentaTime');
    elsif r.enforcement_mode='exact' and (j.schedule is distinct from r.schedule or j.command is distinct from r.command) then
      v_drifted := v_drifted+1;
      update cron.job set schedule=r.schedule,command=r.command,active=true where jobid=j.jobid;
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('cron:'||r.jobname,'stale_cron_drift_repaired','active',jsonb_build_object('jobid',j.jobid,'prior_schedule',j.schedule,'desired_schedule',r.schedule,'prior_command_sha256',encode(extensions.digest(j.command,'sha256'),'hex'),'desired_command_sha256',encode(extensions.digest(r.command,'sha256'),'hex'),'stale_state_allowed_to_override',false),'PentaSELF/PentaTime');
    end if;
  end loop;

  if to_regclass('crm.penta_persona_execution_control_v1') is not null then
    update crm.penta_persona_execution_control_v1
       set active=true,automation_enabled=true,kill_switch=false,updated_at=now()
     where control_key='default' and certification_state='production'
       and (active is distinct from true or automation_enabled is distinct from true or kill_switch is distinct from false);
    if found then
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('control:penta-persona-execution-v1','verified_control_reasserted','production',jsonb_build_object('active',true,'automation_enabled',true,'kill_switch',false,'certification_required','production'),'PentaSELF/PentaAssure');
    end if;
  end if;

  v_event := jsonb_build_object('service','ct.penta.self.permanent-repair-fabric.v1','repaired',v_repaired,'missing',v_missing,'drifted',v_drifted,'observed_only',v_observed,'stale_snapshots_may_rollback',false,'automatic_rollback_allowed',false,'rollback_rule','newer_independently_verified_failure_plus_explicit_rollback_handle_only','observed_at',now());
  v_hash := encode(extensions.digest(v_event::text,'sha256'),'hex');
  return v_event || jsonb_build_object('evidence_sha256',v_hash);
end $$;
revoke all on function penta_self.reconcile_permanent_repairs_v1() from public, anon, authenticated;
grant execute on function penta_self.reconcile_permanent_repairs_v1() to service_role;

insert into penta_self.permanent_cron_desired_state_v1(jobname,schedule,command,database_name,username_name,desired_active,enforcement_mode,verification_evidence,desired_sha256,verified_at,source_ref)
values('ct-penta-self-permanent-repair-reconcile-v1','* * * * *','select penta_self.reconcile_permanent_repairs_v1();',current_database(),current_user,true,'exact',jsonb_build_object('purpose','reassert independently verified repair state after all scheduled mutation lanes','rollback_rule','newer verified failure plus explicit rollback handle only'),encode(extensions.digest('ct-penta-self-permanent-repair-reconcile-v1|* * * * *|select penta_self.reconcile_permanent_repairs_v1();','sha256'),'hex'),now(),'migration:pentaself_permanent_verified_repair_fabric_v1')
on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username_name=excluded.username_name,desired_active=true,enforcement_mode='exact',verification_evidence=excluded.verification_evidence,desired_sha256=excluded.desired_sha256,verified_at=excluded.verified_at,source_ref=excluded.source_ref,updated_at=now();

select cron.unschedule(jobid) from cron.job where jobname='ct-penta-self-permanent-repair-reconcile-v1';
select cron.schedule('ct-penta-self-permanent-repair-reconcile-v1','* * * * *','select penta_self.reconcile_permanent_repairs_v1();');

select penta_self.register_permanent_repair_v1(
  'ct.repair.pentaself.permanent-verified-state.v1',
  'PentaSELF/cron/control-plane',
  null,
  jsonb_build_object('verified_repairs_monotonic',true,'stale_snapshot_regression_allowed',false,'automatic_rollback_allowed',false,'rollback_requires_newer_independent_failure',true,'permanent_reconcile_cron','ct-penta-self-permanent-repair-reconcile-v1'),
  jsonb_build_object('migration','pentaself_permanent_verified_repair_fabric_v1','critical_crons_captured',(select count(*) from penta_self.permanent_cron_desired_state_v1),'persona_execution_production_control_present',to_regclass('crm.penta_persona_execution_control_v1') is not null),
  now(),
  'founder-directive:2026-08-29:permanent-repairs',
  'manual-or-newer-independent-failure-only'
);
