-- CrownThrive OS Phase 3.5
-- PentaSecurity bounded runtime + credential-continuity v3/PentaTime cutover.
-- Originators: PentaBuild/PentaCredentials/PentaTime/PentaSecurity.
-- Independent certification remains required. D3 remains human-reserved.

create schema if not exists penta_security;

create table if not exists penta_security.runtime_review_receipts_v1 (
  review_id uuid primary key default gen_random_uuid(),
  system_key text not null,
  runtime_ref text not null,
  disposition text not null,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  dail_event_id uuid not null,
  dail_event_hash text not null,
  reviewed_at timestamptz not null default clock_timestamp(),
  reviewer_system_key text not null default 'penta.security',
  authority_expansion boolean not null default false
);
create unique index if not exists penta_security_runtime_review_receipts_v1_dedupe
  on penta_security.runtime_review_receipts_v1(system_key,evidence_sha256);

create or replace function penta_security.reject_runtime_review_receipt_mutation_v1()
returns trigger language plpgsql security definer set search_path='pg_catalog','penta_security'
as $fn$ begin raise exception 'append_only_runtime_review_receipt'; end $fn$;
drop trigger if exists penta_security_runtime_review_receipts_immutable_v1 on penta_security.runtime_review_receipts_v1;
create trigger penta_security_runtime_review_receipts_immutable_v1
before update or delete on penta_security.runtime_review_receipts_v1
for each row execute function penta_security.reject_runtime_review_receipt_mutation_v1();

create or replace function penta_security.review_system_v1(p_system_key text)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','penta_security','public','chlom_runtime','extensions'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_row public.penta_system_registry%rowtype;
  v_ref text; v_target text; v_schema text; v_name text;
  v_count integer:=0; v_security_definer boolean:=false;
  v_public boolean:=false; v_anon boolean:=false; v_authenticated boolean:=false; v_service boolean:=false;
  v_functions jsonb:='[]'::jsonb; v_disposition text; v_payload jsonb; v_sha text; v_dail jsonb;
  v_event_id uuid; v_event_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into v_row from public.penta_system_registry where system_key=p_system_key;
  if not found then raise exception 'system_not_registered'; end if;
  v_ref:=btrim(coalesce(v_row.runtime_ref,''));
  if v_ref='' then v_disposition:='HOLD_RUNTIME_REF_MISSING';
  elsif v_ref like 'function:%' then v_target:=substring(v_ref from 10);
  elsif v_ref like 'rpc:%' then v_target:=substring(v_ref from 5);
  elsif v_ref like 'postgres:%' then v_target:=substring(v_ref from 10);
  else v_target:=split_part(v_ref,';',1); end if;
  v_target:=split_part(v_target,'(',1);
  if v_disposition is null and v_target ~ '^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$' then
    v_schema:=split_part(v_target,'.',1); v_name:=split_part(v_target,'.',2);
    select count(*),coalesce(bool_or(p.prosecdef),false),
           coalesce(bool_or(has_function_privilege('public',p.oid,'EXECUTE')),false),
           coalesce(bool_or(has_function_privilege('anon',p.oid,'EXECUTE')),false),
           coalesce(bool_or(has_function_privilege('authenticated',p.oid,'EXECUTE')),false),
           coalesce(bool_or(has_function_privilege('service_role',p.oid,'EXECUTE')),false),
           coalesce(jsonb_agg(jsonb_build_object(
             'identity',p.oid::regprocedure::text,
             'security_definer',p.prosecdef,
             'public_execute',has_function_privilege('public',p.oid,'EXECUTE'),
             'anon_execute',has_function_privilege('anon',p.oid,'EXECUTE'),
             'authenticated_execute',has_function_privilege('authenticated',p.oid,'EXECUTE'),
             'service_role_execute',has_function_privilege('service_role',p.oid,'EXECUTE'),
             'definition_sha256',encode(extensions.digest(convert_to(pg_get_functiondef(p.oid),'UTF8'),'sha256'),'hex')
           ) order by p.oid::regprocedure::text),'[]'::jsonb)
      into v_count,v_security_definer,v_public,v_anon,v_authenticated,v_service,v_functions
      from pg_proc p join pg_namespace n on n.oid=p.pronamespace
      where n.nspname=v_schema and p.proname=v_name;
    if v_count=0 then v_disposition:='HOLD_RUNTIME_NOT_FOUND';
    elsif v_security_definer and (v_public or v_anon or v_authenticated) then v_disposition:='HOLD_SECURITY_DEFINER_EXECUTE_EXPOSURE';
    else v_disposition:='PASS'; end if;
  elsif v_disposition is null then v_disposition:='HOLD_PROVIDER_OR_UNSUPPORTED_RUNTIME_REQUIRES_SPECIALIST'; end if;
  v_payload:=jsonb_build_object(
    'contract','ct.penta.security.runtime-review.v1','system_key',v_row.system_key,'canonical_name',v_row.canonical_name,
    'system_version',v_row.version,'runtime_ref',v_row.runtime_ref,'runtime_target',v_target,'risk_ceiling',v_row.risk_ceiling,
    'did_uri',v_row.metadata->>'did_uri','fingerprint_id',v_row.metadata->>'fingerprint_id','function_count',v_count,
    'security_definer_present',v_security_definer,'public_execute',v_public,'anon_execute',v_anon,
    'authenticated_execute',v_authenticated,'service_role_execute',v_service,'functions',v_functions,
    'disposition',v_disposition,'provider_write',false,'credential_change',false,'money_movement',false,
    'd3_execution',false,'authority_expansion',false,'reviewed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_dail:=public.chlom_append_dail_event(
    p_event_type=>'penta.security.runtime-review.completed.v1',p_entity_type=>'penta_security_review',p_entity_id=>v_row.system_key,
    p_payload=>v_payload||jsonb_build_object('evidence_sha256',v_sha),p_actor_ref=>'PentaSecurity',p_actor_did=>null,
    p_agent_id=>'penta.security',p_entity_version=>'1.0.0',p_correlation_id=>'penta-security-review:'||v_row.system_key,
    p_causation_id=>null,p_authority_basis=>'Bounded D1 read-only runtime/ACL security review; certification remains independent',
    p_approval_id=>null,p_visibility_class=>'internal');
  v_event_id:=nullif(v_dail->>'event_id','')::uuid;
  select event_hash into v_event_hash from chlom_runtime.dail_events where event_id=v_event_id;
  if v_event_hash is null then raise exception 'DAIL_PENTASECURITY_READBACK_FAILED'; end if;
  insert into penta_security.runtime_review_receipts_v1(system_key,runtime_ref,disposition,evidence,evidence_sha256,dail_event_id,dail_event_hash)
  values(v_row.system_key,v_row.runtime_ref,v_disposition,v_payload,v_sha,v_event_id,v_event_hash)
  on conflict(system_key,evidence_sha256) do nothing;
  return v_payload||jsonb_build_object('evidence_sha256',v_sha,'dail_event_id',v_event_id,'dail_event_hash',v_event_hash);
end $fn$;

create or replace function penta_security.status_v1()
returns jsonb language sql stable security definer set search_path='pg_catalog','penta_security','public'
as $fn$
select jsonb_build_object('contract','ct.penta.security.runtime-review.v1',
  'registry',(select to_jsonb(s) from public.penta_system_registry s where system_key='penta.security'),
  'latest_review',(select to_jsonb(r) from penta_security.runtime_review_receipts_v1 r order by reviewed_at desc limit 1),
  'observed_at',clock_timestamp());
$fn$;
revoke all on schema penta_security from public;
grant usage on schema penta_security to service_role;
revoke all on function penta_security.review_system_v1(text) from public,anon,authenticated;
grant execute on function penta_security.review_system_v1(text) to service_role;
revoke all on function penta_security.status_v1() from public,anon,authenticated;
grant execute on function penta_security.status_v1() to service_role;

create table if not exists integration_control.credential_continuity_scheduler_receipts_v3 (
  receipt_id uuid primary key default gen_random_uuid(), execution_key text not null unique,
  execution_kind text not null, function_ref text not null, scheduler_jobname text,
  result_state text not null, result jsonb not null default '{}'::jsonb, result_sha256 text not null,
  dail_event_id uuid not null, dail_event_hash text not null, started_at timestamptz not null,
  completed_at timestamptz not null, authority_expansion boolean not null default false,
  created_at timestamptz not null default clock_timestamp());

create or replace function integration_control.credential_continuity_cycle_v3(
  p_execution_kind text default 'canonical_schedule',
  p_scheduler_jobname text default 'crownthrive_credential_continuity_daily',
  p_execution_key text default null)
returns jsonb language plpgsql security definer
set search_path='pg_catalog','integration_control','public','chlom_runtime','extensions'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_started timestamptz:=clock_timestamp(); v_completed timestamptz; v_key text; v_result jsonb; v_payload jsonb;
  v_sha text; v_dail jsonb; v_event_id uuid; v_event_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_execution_kind not in ('manual_canary','scheduler_canary','canonical_schedule') then raise exception 'invalid_execution_kind'; end if;
  v_key:=coalesce(nullif(p_execution_key,''),p_execution_kind||':'||coalesce(p_scheduler_jobname,'none')||':'||to_char(date_trunc('minute',v_started),'YYYYMMDDHH24MI'));
  if exists(select 1 from integration_control.credential_continuity_scheduler_receipts_v3 where execution_key=v_key) then
    return jsonb_build_object('state','idempotent_replay','execution_key',v_key,'receipt',(select to_jsonb(r) from integration_control.credential_continuity_scheduler_receipts_v3 r where r.execution_key=v_key));
  end if;
  v_result:=integration_control.credential_continuity_cycle_v2(); v_completed:=clock_timestamp();
  v_payload:=jsonb_build_object('contract','ct.penta.credentials.continuity-cycle.v3','execution_key',v_key,
    'execution_kind',p_execution_kind,'scheduler_jobname',p_scheduler_jobname,'function_ref','integration_control.credential_continuity_cycle_v3()',
    'delegated_internal_ref','integration_control.credential_continuity_cycle_v2()','result',coalesce(v_result,'{}'::jsonb),
    'started_at',v_started,'completed_at',v_completed,
    'public_execute',has_function_privilege('public','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
    'anon_execute',has_function_privilege('anon','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
    'authenticated_execute',has_function_privilege('authenticated','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
    'service_role_execute',has_function_privilege('service_role','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
    'credential_values_exposed',false,'credential_change',false,'authority_expansion',false,'d3_execution',false);
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_dail:=public.chlom_append_dail_event(
    p_event_type=>'penta.credentials.continuity-cycle.completed.v3',p_entity_type=>'credential_continuity_execution',p_entity_id=>v_key,
    p_payload=>v_payload,p_actor_ref=>'PentaCredentials/PentaTime',p_actor_did=>null,p_agent_id=>'penta.credentials',p_entity_version=>'3.0.0',
    p_correlation_id=>v_key,p_causation_id=>null,
    p_authority_basis=>'Bounded D2 credential metadata continuity refresh; no credential value creation, rotation or exposure',
    p_approval_id=>null,p_visibility_class=>'internal');
  v_event_id:=nullif(v_dail->>'event_id','')::uuid;
  select event_hash into v_event_hash from chlom_runtime.dail_events where event_id=v_event_id;
  if v_event_hash is null then raise exception 'DAIL_CREDENTIAL_CONTINUITY_READBACK_FAILED'; end if;
  insert into integration_control.credential_continuity_scheduler_receipts_v3(
    execution_key,execution_kind,function_ref,scheduler_jobname,result_state,result,result_sha256,dail_event_id,dail_event_hash,started_at,completed_at)
  values(v_key,p_execution_kind,'integration_control.credential_continuity_cycle_v3()',p_scheduler_jobname,'SUCCEEDED',coalesce(v_result,'{}'::jsonb),v_sha,v_event_id,v_event_hash,v_started,v_completed);
  return jsonb_build_object('state','SUCCEEDED','execution_key',v_key,'result',v_result,'result_sha256',v_sha,
    'dail_event_id',v_event_id,'dail_event_hash',v_event_hash,'started_at',v_started,'completed_at',v_completed,
    'credential_values_exposed',false,'authority_expansion',false);
end $fn$;
revoke all on function integration_control.credential_continuity_cycle_v2() from public,anon,authenticated;
grant execute on function integration_control.credential_continuity_cycle_v2() to service_role;
revoke all on function integration_control.credential_continuity_cycle_v3(text,text,text) from public,anon,authenticated;
grant execute on function integration_control.credential_continuity_cycle_v3(text,text,text) to service_role;

create or replace function pentatime.executor_credential_continuity_v3()
returns jsonb language plpgsql security definer set search_path='pg_catalog','pentatime','integration_control'
as $fn$
declare v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  return integration_control.credential_continuity_cycle_v3('canonical_schedule','crownthrive_credential_continuity_daily',null);
end $fn$;
revoke all on function pentatime.executor_credential_continuity_v3() from public,anon,authenticated;
grant execute on function pentatime.executor_credential_continuity_v3() to service_role;

insert into pentatime.operation_registry_v2(operation_key,domain_key,owner_penta,enabled,base_backoff_seconds,max_backoff_seconds,metadata,updated_at)
values('credential_continuity','credentials','PentaCredentials',true,15,900,
  jsonb_build_object('family','PentaCredentials/PentaTime/PentaCrons','contract','ct.penta.credentials.continuity-cycle.v3',
    'provider_write',false,'credential_change',false,'money_movement',false,'d3_execution',false,'authority_expansion',false),now())
on conflict(operation_key) do update set domain_key=excluded.domain_key,owner_penta=excluded.owner_penta,enabled=true,
  base_backoff_seconds=excluded.base_backoff_seconds,max_backoff_seconds=excluded.max_backoff_seconds,
  metadata=pentatime.operation_registry_v2.metadata||excluded.metadata,updated_at=now();

insert into pentatime.operation_executors_v3(operation_key,executor_regprocedure,authority_ceiling,enabled,metadata,updated_at)
values('credential_continuity','pentatime.executor_credential_continuity_v3()'::regprocedure,'D2',true,
  jsonb_build_object('family','PentaCredentials/PentaTime/PentaCrons','contract','ct.penta.credentials.continuity-cycle.v3',
    'provider_write',false,'credential_change',false,'authority_expansion',false),now())
on conflict(operation_key) do update set executor_regprocedure=excluded.executor_regprocedure,authority_ceiling=excluded.authority_ceiling,
  enabled=true,metadata=pentatime.operation_executors_v3.metadata||excluded.metadata,updated_at=now();

create or replace function integration_control.credential_continuity_v3_security_test_v1()
returns jsonb language plpgsql stable security definer set search_path='pg_catalog','integration_control','pentatime','cron'
as $fn$
declare
  v_job_command text; v_v2_public boolean; v_v2_anon boolean; v_v2_authenticated boolean; v_v2_service boolean;
  v_v3_public boolean; v_v3_anon boolean; v_v3_authenticated boolean; v_v3_service boolean;
  v_executor text; v_enabled boolean; v_pass boolean;
begin
  select command into v_job_command from cron.job where jobname='crownthrive_credential_continuity_daily' order by jobid desc limit 1;
  select has_function_privilege('public','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('anon','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('authenticated','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('service_role','integration_control.credential_continuity_cycle_v2()','EXECUTE'),
         has_function_privilege('public','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
         has_function_privilege('anon','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
         has_function_privilege('authenticated','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE'),
         has_function_privilege('service_role','integration_control.credential_continuity_cycle_v3(text,text,text)','EXECUTE')
    into v_v2_public,v_v2_anon,v_v2_authenticated,v_v2_service,v_v3_public,v_v3_anon,v_v3_authenticated,v_v3_service;
  select executor_regprocedure::text,enabled into v_executor,v_enabled from pentatime.operation_executors_v3 where operation_key='credential_continuity';
  v_pass:=not v_v2_public and not v_v2_anon and not v_v2_authenticated and v_v2_service
    and not v_v3_public and not v_v3_anon and not v_v3_authenticated and v_v3_service
    and v_job_command='select pentatime.execute_guarded_v3(''credential_continuity'');'
    and v_enabled and v_executor='pentatime.executor_credential_continuity_v3()';
  return jsonb_build_object('contract','ct.penta.credentials.continuity-cycle.v3.security-test','passed',v_pass,
    'expected_job_command','select pentatime.execute_guarded_v3(''credential_continuity'');','observed_job_command',v_job_command,
    'executor',v_executor,'executor_enabled',v_enabled,
    'v2',jsonb_build_object('public',v_v2_public,'anon',v_v2_anon,'authenticated',v_v2_authenticated,'service_role',v_v2_service),
    'v3',jsonb_build_object('public',v_v3_public,'anon',v_v3_anon,'authenticated',v_v3_authenticated,'service_role',v_v3_service),
    'rollback_preserves_hardened_acl',true,'credential_values_exposed',false,'authority_expansion',false,'observed_at',clock_timestamp());
end $fn$;
revoke all on function integration_control.credential_continuity_v3_security_test_v1() from public,anon,authenticated;
grant execute on function integration_control.credential_continuity_v3_security_test_v1() to service_role;

-- Preserve one canonical scheduler clock and move execution behind PentaTime.
do $do$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='crownthrive_credential_continuity_daily' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule('crownthrive_credential_continuity_daily','23 */6 * * *','select pentatime.execute_guarded_v3(''credential_continuity'');');
  else
    perform cron.alter_job(v_jobid,schedule=>'23 */6 * * *',command=>'select pentatime.execute_guarded_v3(''credential_continuity'');',active=>true);
  end if;
end $do$;
update integration_control.scheduler_desired_jobs_v2
set schedule='23 */6 * * *',command='select pentatime.execute_guarded_v3(''credential_continuity'');',
    generation=generation+1,source_ref='ct.penta.credentials.continuity-cycle.v3',active=true,allow_auto_restore=true,
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('owner','PentaCredentials/PentaTime/PentaCrons',
      'contract','ct.penta.credentials.continuity-cycle.v3','single_native_clock',true,'authority_expansion',false),updated_at=now()
where jobname='crownthrive_credential_continuity_daily';

-- Runtime-present, still pending independent certification.
update public.penta_system_registry
set runtime_ref='function:penta_security.review_system_v1(text)',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('runtime_contract','ct.penta.security.runtime-review.v1',
      'implementation_state','runtime_active_pending_independent_certification','bounded_runtime_risk','D1','provider_write',false,
      'credential_change',false,'money_movement',false,'d3_human_reserved',true,'authority_expansion',false,
      'source_ref','supabase/migrations/20260830233000_penta_security_and_credential_continuity_contract_v1.sql'),
    updated_at=now()
where system_key='penta.security';
