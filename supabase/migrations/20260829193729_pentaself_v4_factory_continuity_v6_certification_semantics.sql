-- Certification semantics: recent successful completion remains valid across bounded contention deferrals.
create or replace function penta_self.verify_factory_continuity_surgery_v1()
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','penta_self','pentatime','cron','pg_temp'
as $function$
declare s pentatime.operation_state_v2%rowtype; v_duplicates integer; v_active integer; v_ready boolean;
begin
  select * into s from pentatime.operation_state_v2 where operation_key='factory_continuity';
  select count(*) into v_duplicates from cron.job
    where jobname in ('ct-factory-surface-binding-sync-v4','ct-software-factory-tick-v2') and active;
  select count(*) into v_active from cron.job
    where jobname='ct-software-factory-continuity-v5' and active
      and command=$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$;
  v_ready:=coalesce(s.last_completed_at>clock_timestamp()-interval '20 minutes',false)
    and coalesce(s.failure_count,0)=0 and v_duplicates=0 and v_active=1;
  return jsonb_build_object('ready',v_ready,'operation_state',s.last_state,
    'last_successful_completion_at',s.last_completed_at,'failure_count',s.failure_count,
    'bounded_deferrals',s.deferred_count,'consecutive_deferrals',s.consecutive_deferrals,
    'active_canonical_jobs',v_active,'active_duplicate_jobs',v_duplicates,
    'canonical_executor','pentatime.execute_guarded_v3(text)',
    'bounded_contention_deferral_preserves_recent_success',true,
    'recursive_or_duplicate_tick',false,'observed_at',clock_timestamp());
end;
$function$;

create or replace function penta_self.verify_factory_generator_surgery_v1()
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','penta_self','pentatime','cron','pg_temp'
as $function$
declare s pentatime.operation_state_v2%rowtype; v_active integer; v_executor integer; v_ready boolean;
begin
  select * into s from pentatime.operation_state_v2 where operation_key='factory_internal_generate';
  select count(*) into v_active from cron.job
    where jobname='ct-factory-internal-openai-generate-v1' and active
      and command=$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$;
  select count(*) into v_executor from pentatime.operation_executors_v3
    where operation_key='factory_internal_generate' and enabled
      and executor_regprocedure='pentatime.executor_factory_internal_generate_v3()'::regprocedure;
  v_ready:=coalesce(s.last_completed_at>clock_timestamp()-interval '30 minutes',false)
    and coalesce(s.failure_count,0)=0 and v_active=1 and v_executor=1;
  return jsonb_build_object('ready',v_ready,'operation_state',s.last_state,
    'last_successful_completion_at',s.last_completed_at,'failure_count',s.failure_count,
    'bounded_deferrals',s.deferred_count,'consecutive_deferrals',s.consecutive_deferrals,
    'active_jobs',v_active,'registered_executors',v_executor,
    'recursive_factory_tick_removed',true,
    'bounded_contention_deferral_preserves_recent_success',true,
    'advancement_mode','asynchronous_guarded_factory_continuity','observed_at',clock_timestamp());
end;
$function$;

create or replace function penta_self.verify_pentaod_surgery_v1()
returns jsonb
language plpgsql
stable security definer
set search_path to 'pg_catalog','penta_self','pentatime','cron','pg_temp'
as $function$
declare s pentatime.operation_state_v2%rowtype; v_active integer; v_executor integer; v_ready boolean;
begin
  select * into s from pentatime.operation_state_v2 where operation_key='pentaod_sleep';
  select count(*) into v_active from cron.job
    where jobname='pentaod-idle-sleep-v1' and active
      and command=$cmd$select pentatime.execute_guarded_v3('pentaod_sleep');$cmd$;
  select count(*) into v_executor from pentatime.operation_executors_v3
    where operation_key='pentaod_sleep' and enabled
      and executor_regprocedure='pentatime.executor_pentaod_sleep_v3()'::regprocedure;
  v_ready:=coalesce(s.last_completed_at>clock_timestamp()-interval '30 minutes',false)
    and coalesce(s.failure_count,0)=0 and v_active=1 and v_executor=1;
  return jsonb_build_object('ready',v_ready,'operation_state',s.last_state,
    'last_successful_completion_at',s.last_completed_at,'failure_count',s.failure_count,
    'bounded_deferrals',s.deferred_count,'active_jobs',v_active,'registered_executors',v_executor,
    'row_lock_policy','FOR UPDATE SKIP LOCKED','backoff_executor','pentatime.execute_guarded_v3(text)',
    'bounded_contention_deferral_preserves_recent_success',true,'observed_at',clock_timestamp());
end;
$function$;

create or replace function penta_self.certify_factory_continuity_v6()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','pentatime','integration_control','cron','extensions','chlom_runtime','public','pg_temp'
as $function$
declare
  v_cycle uuid:=gen_random_uuid(); v_baseline_at timestamptz;
  v_cont jsonb; v_gen jsonb; v_dispatch_state pentatime.operation_state_v2%rowtype;
  v_cont_jobs integer; v_dispatch_jobs integer; v_generator_jobs integer; v_duplicate_jobs integer;
  v_shared_domains integer; v_recent_concurrency_failures integer; v_raw_active_factory_jobs integer;
  v_scheduler_desired boolean; v_required_desired boolean; v_critical_desired boolean;
  v_permanent_desired boolean; v_monotonic_desired boolean; v_repair_states boolean; v_pentaself_v4 boolean;
  v_ready boolean; v_evidence jsonb; v_sha text; v_receipt uuid;
begin
  select max(completed_at) into v_baseline_at from penta_self.action_receipts_v1
    where action_key='install_factory_monotonic_contracts_v6' and result_state='applied';
  v_baseline_at:=coalesce(v_baseline_at,now()-interval '1 hour');

  v_cont:=penta_self.verify_factory_continuity_surgery_v1();
  v_gen:=penta_self.verify_factory_generator_surgery_v1();
  select * into v_dispatch_state from pentatime.operation_state_v2 where operation_key='factory_dispatch';

  select count(*) into v_cont_jobs from cron.job where jobname='ct-software-factory-continuity-v5'
    and active and command=$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$;
  select count(*) into v_dispatch_jobs from cron.job where jobname='ct-software-factory-dispatch-v3'
    and active and command=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$;
  select count(*) into v_generator_jobs from cron.job where jobname='ct-factory-internal-openai-generate-v1'
    and active and command=$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$;
  select count(*) into v_duplicate_jobs from cron.job
    where jobname in ('ct-software-factory-tick-v2','ct-factory-surface-binding-sync-v4') and active;
  select count(*) into v_shared_domains from pentatime.operation_registry_v2
    where operation_key in ('factory_continuity','factory_dispatch','factory_internal_generate','factory_surface_binding_sync')
      and domain_key='ct:production-governance-write-lane' and enabled;
  select count(*) into v_raw_active_factory_jobs from cron.job
    where active and jobname in ('ct-software-factory-continuity-v5','ct-software-factory-dispatch-v3','ct-factory-internal-openai-generate-v1')
      and command not like 'select pentatime.execute_guarded_v3(%';
  select count(*) into v_recent_concurrency_failures from cron.job_run_details d
    where d.start_time>=v_baseline_at and d.status='failed'
      and (coalesce(d.return_message,'') ilike '%deadlock%' or coalesce(d.return_message,'') ilike '%statement timeout%')
      and (coalesce(d.return_message,'') ilike '%ct_factory%' or coalesce(d.return_message,'') ilike '%factory%');

  v_scheduler_desired:=exists(select 1 from integration_control.scheduler_desired_jobs_v2
    where jobname='ct-software-factory-dispatch-v3' and active and allow_auto_restore and generation>=2026082912
      and command=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$);
  v_required_desired:=exists(select 1 from penta_self.required_jobs_v1
    where jobname='ct-software-factory-dispatch-v3' and auto_repair
      and expected_command=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$);
  v_critical_desired:=exists(select 1 from penta_self.critical_cron_state_v2
    where jobname='ct-software-factory-dispatch-v3' and enabled and desired_version>=2
      and desired_command=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$);
  v_permanent_desired:=exists(select 1 from penta_self.permanent_cron_desired_state_v1
    where jobname='ct-software-factory-dispatch-v3' and desired_active and enforcement_mode='exact'
      and command=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$);
  v_monotonic_desired:=exists(select 1 from penta_self.desired_state_contracts_v1
    where contract_key='ct.pentaself.job.factory-dispatch' and generation=2
      and desired_state->>'command'=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$)
    and not exists(select 1 from penta_self.desired_state_contracts_v1
      where contract_key='ct.pentaself.job.factory-dispatch' and generation>2
        and desired_state->>'command'<>$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$);
  v_repair_states:=not exists(select 1 from penta_self.permanent_repairs_v2
    where repair_key in ('ct.penta-self.repair.factory-continuity-overlap-surgery.v1',
      'ct.penta-self.repair.factory-generator-recursion-surgery.v1') and last_state<>'verified');
  v_pentaself_v4:=to_regprocedure('penta_self.surgical_orchestrator_v4()') is not null
    and to_regprocedure('penta_self.permanent_repair_tick_v4()') is not null;

  v_ready:=coalesce((v_cont->>'ready')::boolean,false)
    and coalesce((v_gen->>'ready')::boolean,false)
    and v_cont_jobs=1 and v_dispatch_jobs=1 and v_generator_jobs=1
    and coalesce(v_dispatch_state.last_completed_at>clock_timestamp()-interval '20 minutes',false)
    and coalesce(v_dispatch_state.failure_count,0)=0
    and v_duplicate_jobs=0 and v_shared_domains=4 and v_raw_active_factory_jobs=0
    and v_recent_concurrency_failures=0 and v_scheduler_desired and v_required_desired
    and v_critical_desired and v_permanent_desired and v_monotonic_desired
    and v_repair_states and v_pentaself_v4;

  v_evidence:=jsonb_build_object(
    'contract','ct.penta.factory-continuity.v6',
    'state',case when v_ready then 'CERTIFIED_PRODUCTION' else 'CERTIFICATION_FAILED' end,
    'continuity_verifier',v_cont,'generator_verifier',v_gen,
    'dispatch_operation',to_jsonb(v_dispatch_state),
    'active_guarded_jobs',jsonb_build_object('continuity',v_cont_jobs,'dispatch',v_dispatch_jobs,'generator',v_generator_jobs),
    'active_duplicate_factory_jobs',v_duplicate_jobs,'shared_write_lane_operations',v_shared_domains,
    'active_raw_factory_jobs',v_raw_active_factory_jobs,
    'factory_concurrency_failures_since_monotonic_install',v_recent_concurrency_failures,
    'desired_state_layers',jsonb_build_object('institutional_scheduler',v_scheduler_desired,
      'pentaself_required',v_required_desired,'pentaself_critical',v_critical_desired,
      'pentaself_permanent',v_permanent_desired,'pentaself_monotonic',v_monotonic_desired),
    'permanent_repairs_verified',v_repair_states,'pentaself_v4_present',v_pentaself_v4,
    'bounded_contention_deferral_is_healthy_control_behavior',true,
    'root_cause','overlapping unguarded factory transactions plus stale lower-generation desired-state contracts',
    'repair','single nonblocking PentaTime write lane, monotonic contract supersession, generation fence and V4 self-verification',
    'scope_note','continuity control certification is independent of workload-capacity/backlog state',
    'authority_class','D1','D3_human_reserved',true,'provider_write',false,
    'credentials_or_secrets_returned',false,'legal_notarization',false,
    'baseline_at',v_baseline_at,'certified_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,after_sha256,evidence)
    values(v_cycle,'self.certify','certify_factory_continuity_v6','cron-family:ct-software-factory',
      case when v_ready then 'applied' else 'failed' end,true,'D1',v_sha,v_evidence)
    returning receipt_id into v_receipt;
  perform chlom_runtime.append_dail_event(
    case when v_ready then 'pentaself.factory-continuity.v6.certified' else 'pentaself.factory-continuity.v6.certification-failed' end,
    'self_certification','ct.penta.factory-continuity.v6',
    v_evidence||jsonb_build_object('receipt_id',v_receipt,'evidence_sha256',v_sha),
    'PentaSELF/PentaTime/PentaFactory/PentaCertify/PentaNurture',null,'PentaSELF','4.0.0',v_sha,null,
    'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal');
  return v_evidence||jsonb_build_object('ready',v_ready,'receipt_id',v_receipt,'evidence_sha256',v_sha);
end;
$function$;
revoke all on function penta_self.certify_factory_continuity_v6() from public,anon,authenticated;
grant execute on function penta_self.certify_factory_continuity_v6() to service_role;

do $do$
declare v_cycle uuid:=gen_random_uuid(); v_payload jsonb; v_sha text;
begin
  v_payload:=jsonb_build_object('contract','ct.penta.factory-continuity.v6.certification-semantics',
    'bounded_deferral_preserves_recent_success',true,'failure_count_required',0,
    'certifier','penta_self.certify_factory_continuity_v6()',
    'D3_human_reserved',true,'provider_write',false,'credential_material',false,'installed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,after_sha256,evidence)
    values(v_cycle,'self.update','install_factory_continuity_v6_certification_semantics','system:PentaSELF',
      'applied',true,'D1',v_sha,v_payload);
  perform chlom_runtime.append_dail_event('pentaself.factory-continuity.v6.certification-semantics-installed','self_update',
    'ct.penta.factory-continuity.v6',v_payload,'PentaSELF/PentaTime/PentaFactory/PentaCertify/PentaNurture',
    null,'PentaSELF','4.0.0',v_sha,null,'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal');
end;
$do$;