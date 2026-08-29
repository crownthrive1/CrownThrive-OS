-- CrownThrive OS / PentaSELF forward-repair persistence v2
-- Production-applied first, then projected here without secret material.
-- Invariant: repairs are forward-only; verified state is never silently rolled back.

create schema if not exists penta_self;

create table if not exists penta_self.required_cron_contracts_v2 (
  jobname text primary key,
  schedule text not null,
  command text not null,
  desired_active boolean not null default true,
  owner_penta text not null default 'PentaSELF/PentaTime/PentaSerialized',
  authority_class text not null default 'D1',
  repair_mode text not null default 'FORWARD_ONLY',
  rollback_policy text not null default 'EXPLICIT_VERIFIED_AUTHORITY_ONLY',
  protected boolean not null default true,
  specification_sha256 text not null,
  last_jobid bigint,
  last_reconciled_at timestamptz,
  last_observed_status text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint required_cron_repair_mode_v2 check (repair_mode in ('FORWARD_ONLY','HOLD_ON_CONFLICT'))
);

create table if not exists penta_self.persistence_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  resource_key text not null,
  action text not null,
  state text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  actor_ref text not null default 'PentaSELF/PentaTime/PentaSerialized',
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists persistence_receipts_resource_time_v2 on penta_self.persistence_receipts_v2(resource_key, observed_at desc);

create table if not exists penta_self.problem_resolution_watermarks_v2 (
  fingerprint text primary key,
  problem_id uuid,
  title text not null,
  verified_state text not null default 'resolved',
  verified_at timestamptz not null,
  verification_evidence jsonb not null,
  verification_sha256 text not null,
  reopen_policy text not null default 'NEWER_INDEPENDENT_FAILURE_ONLY',
  source_ref text,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists penta_self.external_truth_cache_v2 (
  truth_key text primary key,
  state text not null,
  observed_at timestamptz not null,
  expires_at timestamptz,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  source_ref text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table penta_self.required_cron_contracts_v2 enable row level security;
alter table penta_self.persistence_receipts_v2 enable row level security;
alter table penta_self.problem_resolution_watermarks_v2 enable row level security;
alter table penta_self.external_truth_cache_v2 enable row level security;
revoke all on penta_self.required_cron_contracts_v2,penta_self.persistence_receipts_v2,penta_self.problem_resolution_watermarks_v2,penta_self.external_truth_cache_v2 from public,anon,authenticated;
grant select,insert,update,delete on penta_self.required_cron_contracts_v2,penta_self.problem_resolution_watermarks_v2,penta_self.external_truth_cache_v2 to service_role;
grant select,insert on penta_self.persistence_receipts_v2 to service_role;

drop policy if exists required_cron_contracts_service_v2 on penta_self.required_cron_contracts_v2;
create policy required_cron_contracts_service_v2 on penta_self.required_cron_contracts_v2 for all to service_role using (true) with check (true);
drop policy if exists persistence_receipts_select_service_v2 on penta_self.persistence_receipts_v2;
create policy persistence_receipts_select_service_v2 on penta_self.persistence_receipts_v2 for select to service_role using (true);
drop policy if exists persistence_receipts_insert_service_v2 on penta_self.persistence_receipts_v2;
create policy persistence_receipts_insert_service_v2 on penta_self.persistence_receipts_v2 for insert to service_role with check (true);
drop policy if exists problem_resolution_watermarks_service_v2 on penta_self.problem_resolution_watermarks_v2;
create policy problem_resolution_watermarks_service_v2 on penta_self.problem_resolution_watermarks_v2 for all to service_role using (true) with check (true);
drop policy if exists external_truth_cache_service_v2 on penta_self.external_truth_cache_v2;
create policy external_truth_cache_service_v2 on penta_self.external_truth_cache_v2 for all to service_role using (true) with check (true);

create or replace function penta_self.persistence_receipts_immutable_v2()
returns trigger language plpgsql security definer set search_path=pg_catalog,penta_self as $$
begin
  raise exception 'penta_self.persistence_receipts_v2 is append-only';
end $$;
revoke all on function penta_self.persistence_receipts_immutable_v2() from public,anon,authenticated;
grant execute on function penta_self.persistence_receipts_immutable_v2() to service_role;
drop trigger if exists persistence_receipts_immutable_v2 on penta_self.persistence_receipts_v2;
create trigger persistence_receipts_immutable_v2 before update or delete on penta_self.persistence_receipts_v2 for each row execute function penta_self.persistence_receipts_immutable_v2();

create or replace function penta_self.append_persistence_receipt_v2(p_resource_key text,p_action text,p_state text,p_evidence jsonb default '{}'::jsonb)
returns uuid language plpgsql security definer set search_path=pg_catalog,penta_self,extensions,chlom_runtime as $$
declare
  v_id uuid;
  v_sha text;
  v_payload jsonb;
begin
  v_payload:=jsonb_build_object('resource_key',p_resource_key,'action',p_action,'state',p_state,'evidence',coalesce(p_evidence,'{}'::jsonb),'observed_at',now());
  v_sha:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
  insert into penta_self.persistence_receipts_v2(resource_key,action,state,evidence,evidence_sha256)
  values(p_resource_key,p_action,p_state,coalesce(p_evidence,'{}'::jsonb),v_sha) returning receipt_id into v_id;
  begin
    perform chlom_runtime.append_dail_event('pentaself.persistence.'||lower(p_action),'runtime_persistence',p_resource_key,v_payload,'PentaSELF/PentaTime/PentaSerialized',null,'PentaSELF','2.0.0',v_sha,null,'ct.penta.self.forward-repair.v2',null,'internal');
  exception when others then null;
  end;
  return v_id;
end $$;
revoke all on function penta_self.append_persistence_receipt_v2(text,text,text,jsonb) from public,anon,authenticated;
grant execute on function penta_self.append_persistence_receipt_v2(text,text,text,jsonb) to service_role;

create or replace function penta_self.cache_external_truth_v2(p_truth_key text,p_state text,p_observed_at timestamptz,p_expires_at timestamptz,p_evidence jsonb,p_source_ref text)
returns jsonb language plpgsql security definer set search_path=pg_catalog,penta_self,extensions as $$
declare v_sha text;
begin
  v_sha:=encode(extensions.digest(coalesce(p_evidence,'{}'::jsonb)::text,'sha256'),'hex');
  insert into penta_self.external_truth_cache_v2(truth_key,state,observed_at,expires_at,evidence,evidence_sha256,source_ref)
  values(p_truth_key,p_state,p_observed_at,p_expires_at,coalesce(p_evidence,'{}'::jsonb),v_sha,p_source_ref)
  on conflict(truth_key) do update set state=excluded.state,observed_at=excluded.observed_at,expires_at=excluded.expires_at,evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,source_ref=excluded.source_ref,updated_at=now();
  return jsonb_build_object('truth_key',p_truth_key,'state',p_state,'evidence_sha256',v_sha,'authority_created',false);
end $$;
revoke all on function penta_self.cache_external_truth_v2(text,text,timestamptz,timestamptz,jsonb,text) from public,anon,authenticated;
grant execute on function penta_self.cache_external_truth_v2(text,text,timestamptz,timestamptz,jsonb,text) to service_role;

create or replace function penta_self.resolve_problem_verified_v2(p_title text,p_reason text,p_evidence jsonb,p_source_ref text,p_reopen_policy text default 'NEWER_INDEPENDENT_FAILURE_ONLY')
returns jsonb language plpgsql security definer set search_path=pg_catalog,penta_self,extensions as $$
declare
  v_row penta_self.problem_ledger_v1%rowtype;
  v_sha text;
  v_count integer:=0;
begin
  v_sha:=encode(extensions.digest(coalesce(p_evidence,'{}'::jsonb)::text,'sha256'),'hex');
  for v_row in select * from penta_self.problem_ledger_v1 where title=p_title and state not in ('resolved','closed','dismissed') for update loop
    update penta_self.problem_ledger_v1
       set state='resolved',resolved_at=now(),next_attempt_at=null,blocked_reason=null,last_error=null,
           verification_evidence=coalesce(verification_evidence,'{}'::jsonb)||jsonb_build_object('verified_resolution_v2',jsonb_build_object('reason',p_reason,'source_ref',p_source_ref,'evidence',coalesce(p_evidence,'{}'::jsonb),'evidence_sha256',v_sha,'verified_at',now(),'forward_repair',true,'rollback_performed',false)),
           updated_at=now()
     where problem_id=v_row.problem_id;
    insert into penta_self.problem_resolution_watermarks_v2(fingerprint,problem_id,title,verified_at,verification_evidence,verification_sha256,reopen_policy,source_ref,metadata)
    values(v_row.fingerprint,v_row.problem_id,v_row.title,now(),coalesce(p_evidence,'{}'::jsonb),v_sha,p_reopen_policy,p_source_ref,jsonb_build_object('reason',p_reason,'forward_repair',true,'rollback_performed',false))
    on conflict(fingerprint) do update set problem_id=excluded.problem_id,title=excluded.title,verified_at=excluded.verified_at,verification_evidence=excluded.verification_evidence,verification_sha256=excluded.verification_sha256,reopen_policy=excluded.reopen_policy,source_ref=excluded.source_ref,active=true,metadata=penta_self.problem_resolution_watermarks_v2.metadata||excluded.metadata,updated_at=now();
    v_count:=v_count+1;
  end loop;
  perform penta_self.append_persistence_receipt_v2('problem:'||p_title,'VERIFIED_RESOLUTION',case when v_count>0 then 'resolved' else 'not_open' end,jsonb_build_object('count',v_count,'reason',p_reason,'source_ref',p_source_ref,'verification_sha256',v_sha));
  return jsonb_build_object('title',p_title,'resolved_count',v_count,'verification_sha256',v_sha);
end $$;
revoke all on function penta_self.resolve_problem_verified_v2(text,text,jsonb,text,text) from public,anon,authenticated;
grant execute on function penta_self.resolve_problem_verified_v2(text,text,jsonb,text,text) to service_role;

create or replace function penta_self.reconcile_resolution_watermarks_v2()
returns jsonb language plpgsql security definer set search_path=pg_catalog,penta_self as $$
declare v_fixed integer:=0;
begin
  update penta_self.problem_ledger_v1 p
     set state='resolved',resolved_at=coalesce(p.resolved_at,w.verified_at),next_attempt_at=null,blocked_reason=null,last_error=null,
         verification_evidence=coalesce(p.verification_evidence,'{}'::jsonb)||jsonb_build_object('resolution_watermark_reapplied',jsonb_build_object('verified_at',w.verified_at,'verification_sha256',w.verification_sha256,'source_ref',w.source_ref,'reopen_policy',w.reopen_policy,'reapplied_at',now())),
         updated_at=now()
    from penta_self.problem_resolution_watermarks_v2 w
   where w.active=true and w.fingerprint=p.fingerprint
     and p.state not in ('resolved','closed','dismissed')
     and coalesce(p.last_seen_at,p.updated_at,p.created_at)<=w.verified_at;
  get diagnostics v_fixed=row_count;
  if v_fixed>0 then perform penta_self.append_persistence_receipt_v2('pentaself.problem-watermarks','REAPPLY_VERIFIED_STATE','repaired',jsonb_build_object('problems_repaired',v_fixed)); end if;
  return jsonb_build_object('repaired',v_fixed,'policy','newer independent failure required','rollback_performed',false);
end $$;
revoke all on function penta_self.reconcile_resolution_watermarks_v2() from public,anon,authenticated;
grant execute on function penta_self.reconcile_resolution_watermarks_v2() to service_role;

create or replace function penta_self.reconcile_required_crons_v2()
returns jsonb language plpgsql security definer set search_path=pg_catalog,penta_self,cron,extensions as $$
declare
  v_contract record;
  v_job record;
  v_jobid bigint;
  v_created integer:=0;
  v_repaired integer:=0;
  v_duplicates_this integer:=0;
  v_duplicates_total integer:=0;
  v_latest_status text;
begin
  perform pg_advisory_xact_lock(hashtextextended('penta_self.required_crons.v2',0));
  for v_contract in select * from penta_self.required_cron_contracts_v2 where desired_active=true order by jobname loop
    select * into v_job from cron.job where jobname=v_contract.jobname order by jobid desc limit 1;
    if not found then
      select cron.schedule(v_contract.jobname,v_contract.schedule,v_contract.command) into v_jobid;
      v_created:=v_created+1;
      perform penta_self.append_persistence_receipt_v2('cron:'||v_contract.jobname,'CREATE_MISSING','active',jsonb_build_object('jobid',v_jobid,'schedule',v_contract.schedule,'command_sha256',v_contract.specification_sha256,'repair_mode','FORWARD_ONLY'));
    else
      v_jobid:=v_job.jobid;
      if v_job.schedule is distinct from v_contract.schedule or v_job.command is distinct from v_contract.command or v_job.active is distinct from true then
        update cron.job set schedule=v_contract.schedule,command=v_contract.command,active=true where jobid=v_jobid;
        v_repaired:=v_repaired+1;
        perform penta_self.append_persistence_receipt_v2('cron:'||v_contract.jobname,'REPAIR_DRIFT_FORWARD','active',jsonb_build_object('jobid',v_jobid,'schedule',v_contract.schedule,'command_sha256',v_contract.specification_sha256,'rollback_performed',false));
      end if;
      update cron.job set active=false where jobname=v_contract.jobname and jobid<>v_jobid and active=true;
      get diagnostics v_duplicates_this=row_count;
      v_duplicates_total:=v_duplicates_total+v_duplicates_this;
      if v_duplicates_this>0 then perform penta_self.append_persistence_receipt_v2('cron:'||v_contract.jobname,'QUARANTINE_DUPLICATE','quarantined',jsonb_build_object('kept_jobid',v_jobid,'duplicates_quarantined',v_duplicates_this,'deleted',false)); end if;
    end if;
    select status into v_latest_status from cron.job_run_details where jobid=v_jobid order by start_time desc limit 1;
    update penta_self.required_cron_contracts_v2 set last_jobid=v_jobid,last_reconciled_at=now(),last_observed_status=v_latest_status,updated_at=now() where jobname=v_contract.jobname;
  end loop;
  return jsonb_build_object('created',v_created,'repaired',v_repaired,'duplicates_quarantined',v_duplicates_total,'forward_only',true,'rollback_performed',false,'observed_at',now());
end $$;
revoke all on function penta_self.reconcile_required_crons_v2() from public,anon,authenticated;
grant execute on function penta_self.reconcile_required_crons_v2() to service_role;

create or replace function penta_self.persistence_guard_tick_v2()
returns jsonb language plpgsql security definer set search_path=pg_catalog,penta_self as $$
declare v_crons jsonb; v_problems jsonb; v_result jsonb;
begin
  v_crons:=penta_self.reconcile_required_crons_v2();
  v_problems:=penta_self.reconcile_resolution_watermarks_v2();
  v_result:=jsonb_build_object('service','ct.penta.self.forward-repair.v2','state','succeeded','crons',v_crons,'problems',v_problems,'forward_repair_only',true,'automatic_rollback',false,'observed_at',now());
  perform penta_self.append_persistence_receipt_v2('ct.penta.self.forward-repair.v2','GUARD_TICK','succeeded',v_result);
  return v_result;
exception when others then
  begin perform penta_self.append_persistence_receipt_v2('ct.penta.self.forward-repair.v2','GUARD_TICK','failed',jsonb_build_object('error_sqlstate',sqlstate,'error_class','guard_tick_failure','raw_error_preserved',false,'observed_at',now())); exception when others then null; end;
  raise;
end $$;
revoke all on function penta_self.persistence_guard_tick_v2() from public,anon,authenticated;
grant execute on function penta_self.persistence_guard_tick_v2() to service_role;

insert into penta_self.required_cron_contracts_v2(jobname,schedule,command,desired_active,specification_sha256,metadata)
select j.jobname,j.schedule,j.command,true,encode(extensions.digest(j.schedule||E'\n'||j.command,'sha256'),'hex'),jsonb_build_object('captured_from_live_production',true,'captured_at',now(),'forward_repair_only',true,'automatic_rollback',false)
from cron.job j
where j.active=true and (
  j.jobname in ('ct-software-factory-continuity-v5','ct-penta-self-v1','ct-penta-self-continuous-healing-v1','pentafactory-daily-agent-fleet-10x100-v1','ct-penta-census-native-due-v1','penta-persona-execution-v1','ct-pentamarketer-intake-cycle-v1','ct-locticians-native-monitor-v1','ct-locticians-bd-reference-daily-v3','ct-locticians-article-live-verifier-v1','ct-locticians-article-schedule-dispatch-v1','ct-locticians-bd-failover-reconcile-v3','ct-locticians-bd-failover-daily-v3','locticians-bd-contract-watch-v1')
  or j.jobname like 'ct-outreach-%' or j.jobname like '%penta-mail%' or j.jobname like '%pentamarketer%'
)
on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,desired_active=true,specification_sha256=excluded.specification_sha256,metadata=penta_self.required_cron_contracts_v2.metadata||excluded.metadata,updated_at=now();

insert into penta_self.required_cron_contracts_v2(jobname,schedule,command,desired_active,specification_sha256,metadata)
values
('ct-penta-self-persistence-guard-v2','* * * * *','select penta_self.persistence_guard_tick_v2();',true,encode(extensions.digest('* * * * *'||E'\n'||'select penta_self.persistence_guard_tick_v2();','sha256'),'hex'),jsonb_build_object('role','primary_watchdog','repairs_peer',true,'forward_repair_only',true)),
('ct-penta-self-persistence-watchdog-v2','2-59/5 * * * *','select penta_self.persistence_guard_tick_v2();',true,encode(extensions.digest('2-59/5 * * * *'||E'\n'||'select penta_self.persistence_guard_tick_v2();','sha256'),'hex'),jsonb_build_object('role','redundant_watchdog','repairs_peer',true,'forward_repair_only',true))
on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,desired_active=true,specification_sha256=excluded.specification_sha256,metadata=penta_self.required_cron_contracts_v2.metadata||excluded.metadata,updated_at=now();

select penta_self.reconcile_required_crons_v2();
