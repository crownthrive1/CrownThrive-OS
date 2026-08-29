-- CrownThrive OS / PentaSELF monotonic repair persistence v2
-- Applied to production before source projection. No authority expansion.

create table if not exists penta_self.certified_problem_resolutions_v2 (
  fingerprint text primary key,
  problem_id uuid not null,
  resolution_version bigint not null default 1 check (resolution_version > 0),
  terminal_state text not null default 'verified_resolved' check (terminal_state in ('resolved','verified_resolved','closed','superseded')),
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  verification_evidence jsonb not null default '{}'::jsonb,
  certified_by text not null,
  certified_at timestamptz not null default now(),
  regression_policy jsonb not null default jsonb_build_object(
    'requires_fresh_observation',true,
    'requires_regression_verified',true,
    'requires_evidence_sha256',true,
    'stale_reopen_prohibited',true
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.problem_regression_events_v2 (
  regression_event_id uuid primary key default gen_random_uuid(),
  problem_id uuid not null,
  fingerprint text not null,
  prior_terminal_state text not null,
  regression_state text not null,
  observation_at timestamptz not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null default '{}'::jsonb,
  certified_by text not null,
  created_at timestamptz not null default now()
);

alter table penta_self.certified_problem_resolutions_v2 enable row level security;
alter table penta_self.problem_regression_events_v2 enable row level security;
revoke all on penta_self.certified_problem_resolutions_v2 from public, anon, authenticated;
revoke all on penta_self.problem_regression_events_v2 from public, anon, authenticated;
grant select,insert,update on penta_self.certified_problem_resolutions_v2 to service_role;
grant select,insert on penta_self.problem_regression_events_v2 to service_role;

drop policy if exists certified_problem_resolutions_service_v2 on penta_self.certified_problem_resolutions_v2;
create policy certified_problem_resolutions_service_v2 on penta_self.certified_problem_resolutions_v2 for all to service_role using (true) with check (true);
drop policy if exists problem_regression_events_service_v2 on penta_self.problem_regression_events_v2;
create policy problem_regression_events_service_v2 on penta_self.problem_regression_events_v2 for select to service_role using (true);
drop policy if exists problem_regression_events_insert_service_v2 on penta_self.problem_regression_events_v2;
create policy problem_regression_events_insert_service_v2 on penta_self.problem_regression_events_v2 for insert to service_role with check (true);

create or replace function penta_self.problem_monotonic_guard_v2()
returns trigger
language plpgsql
security definer
set search_path=pg_catalog,penta_self
as $$
declare
  v_cert penta_self.certified_problem_resolutions_v2%rowtype;
  v_regression_verified boolean := false;
  v_observed_at timestamptz;
  v_regression_sha text;
begin
  if tg_op='DELETE' then
    select * into v_cert from penta_self.certified_problem_resolutions_v2 where fingerprint=old.fingerprint;
    if found and coalesce(current_setting('penta_self.explicit_terminal_delete',true),'') <> 'authorized' then
      raise exception 'certified_problem_delete_prohibited:%',old.fingerprint;
    end if;
    return old;
  end if;

  if tg_op='UPDATE' then
    new.first_seen_at := least(coalesce(old.first_seen_at,new.first_seen_at,now()),coalesce(new.first_seen_at,old.first_seen_at,now()));
    new.last_seen_at := greatest(coalesce(old.last_seen_at,'-infinity'::timestamptz),coalesce(new.last_seen_at,'-infinity'::timestamptz));
    new.attempt_count := greatest(coalesce(old.attempt_count,0),coalesce(new.attempt_count,0));
    new.verification_evidence := coalesce(old.verification_evidence,'{}'::jsonb) || coalesce(new.verification_evidence,'{}'::jsonb);
    if old.resolved_at is not null and new.resolved_at is null then new.resolved_at := old.resolved_at; end if;
  end if;

  select * into v_cert from penta_self.certified_problem_resolutions_v2 where fingerprint=new.fingerprint;
  if found and new.state not in ('resolved','verified_resolved','closed','superseded') then
    v_regression_verified := lower(coalesce(new.evidence->>'regression_verified','false'))='true';
    v_regression_sha := lower(coalesce(new.evidence->>'regression_evidence_sha256',''));
    begin
      v_observed_at := nullif(new.evidence->>'observed_at','')::timestamptz;
    exception when others then
      v_observed_at := null;
    end;
    v_observed_at := coalesce(v_observed_at,new.last_seen_at,now());

    if not v_regression_verified
       or v_regression_sha !~ '^[0-9a-f]{64}$'
       or v_observed_at <= v_cert.certified_at then
      new.state := v_cert.terminal_state;
      new.resolved_at := coalesce(new.resolved_at,v_cert.certified_at);
      new.verification_evidence := coalesce(new.verification_evidence,'{}'::jsonb) || v_cert.verification_evidence;
      new.evidence := coalesce(new.evidence,'{}'::jsonb) || jsonb_build_object(
        'stale_reopen_suppressed',true,
        'suppressed_at',now(),
        'certified_resolution_version',v_cert.resolution_version,
        'certified_resolution_sha256',v_cert.evidence_sha256,
        'latest_suppressed_observation_at',v_observed_at
      );
    end if;
  end if;

  new.updated_at := now();
  return new;
end $$;

revoke all on function penta_self.problem_monotonic_guard_v2() from public,anon,authenticated;
grant execute on function penta_self.problem_monotonic_guard_v2() to service_role;

drop trigger if exists problem_monotonic_guard_v2 on penta_self.problem_ledger_v1;
create trigger problem_monotonic_guard_v2
before insert or update or delete on penta_self.problem_ledger_v1
for each row execute function penta_self.problem_monotonic_guard_v2();

create or replace function penta_self.certify_problem_resolution_v2(
  p_problem_id uuid,
  p_terminal_state text,
  p_verification_evidence jsonb,
  p_actor_ref text,
  p_resolution_version bigint default 1
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_problem penta_self.problem_ledger_v1%rowtype;
  v_payload jsonb;
  v_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_terminal_state not in ('resolved','verified_resolved','closed','superseded') then raise exception 'invalid_terminal_state'; end if;
  select * into v_problem from penta_self.problem_ledger_v1 where problem_id=p_problem_id for update;
  if not found then raise exception 'problem_not_found'; end if;
  v_payload := jsonb_build_object(
    'problem_id',v_problem.problem_id,
    'fingerprint',v_problem.fingerprint,
    'terminal_state',p_terminal_state,
    'resolution_version',p_resolution_version,
    'verification_evidence',coalesce(p_verification_evidence,'{}'::jsonb),
    'certified_by',p_actor_ref,
    'certified_at',now()
  );
  v_sha := encode(extensions.digest(v_payload::text,'sha256'),'hex');

  insert into penta_self.certified_problem_resolutions_v2(
    fingerprint,problem_id,resolution_version,terminal_state,evidence_sha256,verification_evidence,certified_by,certified_at,updated_at
  ) values(
    v_problem.fingerprint,v_problem.problem_id,p_resolution_version,p_terminal_state,v_sha,coalesce(p_verification_evidence,'{}'::jsonb),p_actor_ref,now(),now()
  )
  on conflict(fingerprint) do update set
    problem_id=excluded.problem_id,
    resolution_version=greatest(penta_self.certified_problem_resolutions_v2.resolution_version,excluded.resolution_version),
    terminal_state=case when excluded.resolution_version>=penta_self.certified_problem_resolutions_v2.resolution_version then excluded.terminal_state else penta_self.certified_problem_resolutions_v2.terminal_state end,
    evidence_sha256=case when excluded.resolution_version>=penta_self.certified_problem_resolutions_v2.resolution_version then excluded.evidence_sha256 else penta_self.certified_problem_resolutions_v2.evidence_sha256 end,
    verification_evidence=penta_self.certified_problem_resolutions_v2.verification_evidence||excluded.verification_evidence,
    certified_by=case when excluded.resolution_version>=penta_self.certified_problem_resolutions_v2.resolution_version then excluded.certified_by else penta_self.certified_problem_resolutions_v2.certified_by end,
    certified_at=case when excluded.resolution_version>=penta_self.certified_problem_resolutions_v2.resolution_version then excluded.certified_at else penta_self.certified_problem_resolutions_v2.certified_at end,
    updated_at=now();

  update penta_self.problem_ledger_v1
     set state=p_terminal_state,
         verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||coalesce(p_verification_evidence,'{}'::jsonb)||jsonb_build_object('resolution_sha256',v_sha,'resolution_version',p_resolution_version,'certified_by',p_actor_ref),
         resolved_at=now(),
         next_attempt_at=null,
         blocked_reason=null,
         last_error=null,
         updated_at=now()
   where problem_id=p_problem_id;

  return jsonb_build_object('problem_id',p_problem_id,'state',p_terminal_state,'resolution_version',p_resolution_version,'evidence_sha256',v_sha,'sticky',true);
end $$;

create or replace function penta_self.certify_problem_regression_v2(
  p_problem_id uuid,
  p_regression_state text,
  p_observation_at timestamptz,
  p_evidence jsonb,
  p_actor_ref text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_problem penta_self.problem_ledger_v1%rowtype;
  v_cert penta_self.certified_problem_resolutions_v2%rowtype;
  v_sha text;
  v_evidence jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_regression_state in ('resolved','verified_resolved','closed','superseded') then raise exception 'invalid_regression_state'; end if;
  select * into v_problem from penta_self.problem_ledger_v1 where problem_id=p_problem_id for update;
  if not found then raise exception 'problem_not_found'; end if;
  select * into v_cert from penta_self.certified_problem_resolutions_v2 where fingerprint=v_problem.fingerprint for update;
  if not found then raise exception 'no_certified_resolution'; end if;
  if p_observation_at <= v_cert.certified_at then raise exception 'stale_regression_observation'; end if;
  v_evidence := coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object('regression_verified',true,'observed_at',p_observation_at,'certified_by',p_actor_ref);
  v_sha := encode(extensions.digest(v_evidence::text,'sha256'),'hex');
  v_evidence := v_evidence||jsonb_build_object('regression_evidence_sha256',v_sha);

  insert into penta_self.problem_regression_events_v2(problem_id,fingerprint,prior_terminal_state,regression_state,observation_at,evidence_sha256,evidence,certified_by)
  values(v_problem.problem_id,v_problem.fingerprint,v_cert.terminal_state,p_regression_state,p_observation_at,v_sha,v_evidence,p_actor_ref);
  delete from penta_self.certified_problem_resolutions_v2 where fingerprint=v_problem.fingerprint;
  update penta_self.problem_ledger_v1 set state=p_regression_state,evidence=coalesce(evidence,'{}'::jsonb)||v_evidence,resolved_at=null,next_attempt_at=now(),updated_at=now() where problem_id=p_problem_id;
  return jsonb_build_object('problem_id',p_problem_id,'state',p_regression_state,'regression_evidence_sha256',v_sha,'reopened',true);
end $$;

create or replace function penta_self.reconcile_certified_problem_state_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_repaired int := 0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  update penta_self.problem_ledger_v1 p
     set state=r.terminal_state,
         resolved_at=coalesce(p.resolved_at,r.certified_at),
         next_attempt_at=null,
         blocked_reason=null,
         last_error=null,
         verification_evidence=coalesce(p.verification_evidence,'{}'::jsonb)||r.verification_evidence||jsonb_build_object('monotonic_reconciled_at',now(),'resolution_sha256',r.evidence_sha256),
         updated_at=now()
    from penta_self.certified_problem_resolutions_v2 r
   where p.fingerprint=r.fingerprint
     and p.state not in ('resolved','verified_resolved','closed','superseded');
  get diagnostics v_repaired=row_count;
  return jsonb_build_object('service','ct.penta.self.monotonic-resolution.v2','repaired',v_repaired,'rollback_from_stale_observation',false,'reconciled_at',now());
end $$;

revoke all on function penta_self.certify_problem_resolution_v2(uuid,text,jsonb,text,bigint) from public,anon,authenticated;
revoke all on function penta_self.certify_problem_regression_v2(uuid,text,timestamptz,jsonb,text) from public,anon,authenticated;
revoke all on function penta_self.reconcile_certified_problem_state_v2() from public,anon,authenticated;
grant execute on function penta_self.certify_problem_resolution_v2(uuid,text,jsonb,text,bigint) to service_role;
grant execute on function penta_self.certify_problem_regression_v2(uuid,text,timestamptz,jsonb,text) to service_role;
grant execute on function penta_self.reconcile_certified_problem_state_v2() to service_role;

create table if not exists penta_self.critical_cron_state_v2 (
  jobname text primary key,
  desired_schedule text not null,
  desired_command text not null,
  desired_version bigint not null default 1 check (desired_version > 0),
  state_sha256 text not null,
  enabled boolean not null default true,
  reconciliation_mode text not null default 'restore_missing_or_inactive' check (reconciliation_mode in ('observe_only','restore_missing_or_inactive')),
  authority_ref text not null default 'ct.penta.self.scheduler-permanence.v2',
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.cron_state_events_v2 (
  event_id uuid primary key default gen_random_uuid(),
  jobname text not null,
  event_type text not null,
  observed_schedule text,
  observed_command text,
  desired_version bigint,
  details jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

alter table penta_self.critical_cron_state_v2 enable row level security;
alter table penta_self.cron_state_events_v2 enable row level security;
revoke all on penta_self.critical_cron_state_v2 from public,anon,authenticated;
revoke all on penta_self.cron_state_events_v2 from public,anon,authenticated;
grant select,insert,update on penta_self.critical_cron_state_v2 to service_role;
grant select,insert on penta_self.cron_state_events_v2 to service_role;
create policy critical_cron_state_service_v2 on penta_self.critical_cron_state_v2 for all to service_role using (true) with check (true);
create policy cron_state_events_service_v2 on penta_self.cron_state_events_v2 for select to service_role using (true);
create policy cron_state_events_insert_service_v2 on penta_self.cron_state_events_v2 for insert to service_role with check (true);

create or replace function penta_self.critical_cron_state_monotonic_guard_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self as $$
begin
  if tg_op='DELETE' then raise exception 'critical_cron_state_delete_prohibited:%',old.jobname; end if;
  if tg_op='UPDATE' and new.desired_version < old.desired_version then raise exception 'cron_version_downgrade_prohibited:%',old.jobname; end if;
  if tg_op='UPDATE' and new.desired_version=old.desired_version and (new.desired_schedule,new.desired_command) is distinct from (old.desired_schedule,old.desired_command) then raise exception 'same_version_cron_mutation_prohibited:%',old.jobname; end if;
  new.updated_at:=now();
  return new;
end $$;
revoke all on function penta_self.critical_cron_state_monotonic_guard_v2() from public,anon,authenticated;
grant execute on function penta_self.critical_cron_state_monotonic_guard_v2() to service_role;
drop trigger if exists critical_cron_state_monotonic_guard_v2 on penta_self.critical_cron_state_v2;
create trigger critical_cron_state_monotonic_guard_v2 before update or delete on penta_self.critical_cron_state_v2 for each row execute function penta_self.critical_cron_state_monotonic_guard_v2();

insert into penta_self.critical_cron_state_v2(jobname,desired_schedule,desired_command,desired_version,state_sha256,evidence)
select j.jobname,j.schedule,j.command,1,encode(extensions.digest(concat_ws('|',j.jobname,j.schedule,j.command),'sha256'),'hex'),jsonb_build_object('captured_from_live_pg_cron',true,'captured_at',now(),'policy','active_newer_state_is_never_overwritten')
from cron.job j
where j.jobname in (
  'ct-penta-self-v1','ct-penta-self-continuous-healing-v1','ct-software-factory-continuity-v5',
  'penta-persona-execution-v1','ct-penta-census-native-due-v1','pentafactory-daily-agent-fleet-10x100-v1',
  'ct-pentamarketer-intake-cycle-v1','ct-locticians-native-monitor-v1','ct-locticians-article-live-verifier-v1',
  'ct-locticians-article-schedule-dispatch-v1','ct-locticians-bd-reference-daily-v3',
  'ct-locticians-bd-failover-reconcile-v3','ct-locticians-bd-failover-daily-v3','locticians-bd-contract-watch-v1'
)
on conflict(jobname) do nothing;

create or replace function penta_self.reconcile_critical_crons_v2()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,cron
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  j record;
  v_restored int:=0;
  v_reactivated int:=0;
  v_drift int:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  for r in select * from penta_self.critical_cron_state_v2 where enabled loop
    select * into j from cron.job where jobname=r.jobname order by jobid desc limit 1;
    if not found then
      if r.reconciliation_mode='restore_missing_or_inactive' then
        perform cron.schedule(r.jobname,r.desired_schedule,r.desired_command);
        v_restored:=v_restored+1;
        insert into penta_self.cron_state_events_v2(jobname,event_type,desired_version,details) values(r.jobname,'RESTORED_MISSING',r.desired_version,jsonb_build_object('schedule',r.desired_schedule,'state_sha256',r.state_sha256));
      end if;
    elsif not j.active and j.schedule=r.desired_schedule and j.command=r.desired_command then
      if r.reconciliation_mode='restore_missing_or_inactive' then
        perform cron.alter_job(j.jobid,active=>true);
        v_reactivated:=v_reactivated+1;
        insert into penta_self.cron_state_events_v2(jobname,event_type,observed_schedule,observed_command,desired_version,details) values(r.jobname,'REACTIVATED_EXACT',j.schedule,j.command,r.desired_version,jsonb_build_object('jobid',j.jobid));
      end if;
    elsif j.schedule is distinct from r.desired_schedule or j.command is distinct from r.desired_command then
      v_drift:=v_drift+1;
      insert into penta_self.cron_state_events_v2(jobname,event_type,observed_schedule,observed_command,desired_version,details) values(r.jobname,'ACTIVE_DRIFT_OBSERVED_NOT_OVERWRITTEN',j.schedule,j.command,r.desired_version,jsonb_build_object('jobid',j.jobid,'active',j.active,'no_rollback',true,'required_action','register_higher_version_if_successor_is_intended'));
    end if;
  end loop;
  perform penta_self.reconcile_certified_problem_state_v2();
  return jsonb_build_object('service','ct.penta.self.scheduler-permanence.v2','restored_missing',v_restored,'reactivated_exact',v_reactivated,'active_drift_observed_not_overwritten',v_drift,'rollback_performed',false,'reconciled_at',now());
end $$;

revoke all on function penta_self.reconcile_critical_crons_v2() from public,anon,authenticated;
grant execute on function penta_self.reconcile_critical_crons_v2() to service_role;

select cron.unschedule(jobid) from cron.job where jobname='ct-penta-self-monotonic-reconcile-v2';
select cron.schedule('ct-penta-self-monotonic-reconcile-v2','* * * * *','select penta_self.reconcile_critical_crons_v2();');

select penta_self.reconcile_critical_crons_v2();
