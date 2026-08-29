-- PentaSELF monotonic desired-state contracts and targeted factory reconciler.
with contracts(contract_key,generation,target_key,desired_state,source_ref,authority_ref,actor_ref) as (
  values
  ('ct.pentaself.job.factory-continuity'::text,3::bigint,'ct-software-factory-continuity-v5'::text,
   jsonb_build_object('active',true,'command',$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$,
     'schedule','0-58/2 * * * *','risk_class','D1','operation_key','factory_continuity',
     'executor','pentatime.executor_factory_continuity_v3()','pentatime_guard','v3',
     'contention_domain','ct:production-governance-write-lane','continuity_contract','ct.penta.factory-continuity.v6',
     'rollback_rule','higher_generation_supersession_only'),
   'production:2026-08-29:factory-continuity-v6'::text,
   'founder-directive:2026-08-29:fix-upgrade-self-certify'::text,
   'PentaSELF/PentaTime/PentaFactory/PentaNurture'::text),
  ('ct.pentaself.job.factory-dispatch'::text,2::bigint,'ct-software-factory-dispatch-v3'::text,
   jsonb_build_object('active',true,'command',$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$,
     'schedule','* * * * *','risk_class','D1','operation_key','factory_dispatch',
     'executor','pentatime.executor_factory_dispatch_v3()','pentatime_guard','v3',
     'contention_domain','ct:production-governance-write-lane','continuity_contract','ct.penta.factory-continuity.v6',
     'rollback_rule','higher_generation_supersession_only'),
   'production:2026-08-29:factory-continuity-v6'::text,
   'founder-directive:2026-08-29:fix-upgrade-self-certify'::text,
   'PentaSELF/PentaTime/PentaFactory/PentaNurture'::text),
  ('ct.pentaself.job.factory-internal-generate'::text,1::bigint,'ct-factory-internal-openai-generate-v1'::text,
   jsonb_build_object('active',true,'command',$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$,
     'schedule','7,17,27,37,47,57 * * * *','risk_class','D2','operation_key','factory_internal_generate',
     'executor','pentatime.executor_factory_internal_generate_v3()','pentatime_guard','v3',
     'contention_domain','ct:production-governance-write-lane','continuity_contract','ct.penta.factory-continuity.v6',
     'recursive_factory_tick_removed',true,'rollback_rule','higher_generation_supersession_only'),
   'production:2026-08-29:factory-continuity-v6'::text,
   'founder-directive:2026-08-29:fix-upgrade-self-certify'::text,
   'PentaSELF/PentaTime/PentaFactory/PentaBuild/PentaNurture'::text)
)
insert into penta_self.desired_state_contracts_v1(
  contract_key,generation,contract_kind,target_key,desired_state,source_ref,authority_ref,actor_ref,evidence_sha256
)
select contract_key,generation,'cron_job',target_key,desired_state,source_ref,authority_ref,actor_ref,
       encode(extensions.digest(convert_to(jsonb_build_object(
         'contract_key',contract_key,'generation',generation,'target_key',target_key,
         'desired_state',desired_state,'source_ref',source_ref,'authority_ref',authority_ref,'actor_ref',actor_ref
       )::text,'UTF8'),'sha256'),'hex')
from contracts
on conflict(contract_key,generation) do nothing;

create or replace function penta_self.reconcile_factory_continuity_v6()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','integration_control','pentatime','cron','extensions','chlom_runtime','pg_temp'
as $function$
declare
  v_schedule jsonb;
  v_job record;
  v_retired_deactivated integer:=0;
  v_domains_updated integer:=0;
  v_cont jsonb;
  v_gen jsonb;
  v_dispatch jsonb;
  v_ready boolean;
  v_payload jsonb;
  v_sha text;
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct:pentaself:factory-continuity-v6',0)) then
    return jsonb_build_object('state','DEFERRED_LOCKED','ready',false,'observed_at',clock_timestamp());
  end if;

  v_schedule:=integration_control.scheduler_permanence_reconcile_v2();

  for v_job in
    select jobid,jobname from cron.job
    where jobname in ('ct-software-factory-tick-v2','ct-factory-surface-binding-sync-v4') and active
    order by jobid
  loop
    perform cron.alter_job(v_job.jobid,active=>false);
    v_retired_deactivated:=v_retired_deactivated+1;
  end loop;

  update pentatime.operation_registry_v2
  set domain_key='ct:production-governance-write-lane',
      metadata=metadata||jsonb_build_object('shared_factory_write_lane',true,
        'continuity_contract','ct.penta.factory-continuity.v6',
        'source_ref','penta_self.reconcile_factory_continuity_v6()'),
      updated_at=now()
  where operation_key in ('factory_continuity','factory_dispatch','factory_internal_generate','factory_surface_binding_sync')
    and (domain_key is distinct from 'ct:production-governance-write-lane'
      or coalesce(metadata->>'continuity_contract','')<>'ct.penta.factory-continuity.v6');
  get diagnostics v_domains_updated=row_count;

  v_cont:=penta_self.verify_factory_continuity_surgery_v1();
  v_gen:=penta_self.verify_factory_generator_surgery_v1();
  select jsonb_build_object(
    'operation_state',s.last_state,'last_completed_at',s.last_completed_at,
    'active_guarded_jobs',(select count(*) from cron.job where jobname='ct-software-factory-dispatch-v3'
      and active and command=$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$),
    'executor_registered',exists(select 1 from pentatime.operation_executors_v3
      where operation_key='factory_dispatch' and enabled and executor_regprocedure='pentatime.executor_factory_dispatch_v3()'::regprocedure)
  ) into v_dispatch
  from pentatime.operation_state_v2 s where s.operation_key='factory_dispatch';

  v_ready:=coalesce((v_cont->>'ready')::boolean,false)
    and coalesce((v_gen->>'ready')::boolean,false)
    and coalesce((v_dispatch->>'active_guarded_jobs')::integer,0)=1
    and coalesce((v_dispatch->>'executor_registered')::boolean,false);

  v_payload:=jsonb_build_object(
    'service','ct.penta.self.factory-continuity-reconciler.v6',
    'state',case when v_ready then 'VERIFIED' else 'PENDING_RUNTIME_VERIFICATION' end,
    'ready',v_ready,'scheduler_reconcile',v_schedule,
    'retired_clocks_deactivated',v_retired_deactivated,
    'operation_domains_updated',v_domains_updated,
    'continuity',v_cont,'generator',v_gen,'dispatch',v_dispatch,
    'direct_cron_table_write',false,'cron_identity_preserved',true,
    'D3_human_reserved',true,'provider_write',false,'observed_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  return v_payload||jsonb_build_object('evidence_sha256',v_sha);
end;
$function$;
revoke all on function penta_self.reconcile_factory_continuity_v6() from public,anon,authenticated;
grant execute on function penta_self.reconcile_factory_continuity_v6() to service_role;

create or replace function penta_self.surgical_orchestrator_v4()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','public','extensions','pg_temp'
as $function$
declare
  v_cycle uuid:=gen_random_uuid(); v_pre jsonb; v_factory jsonb; v_truth jsonb; v_intake jsonb;
  v_surgery_pre jsonb; v_permanent jsonb; v_core jsonb; v_heal jsonb;
  v_surgery_post jsonb; v_resolutions jsonb; v_post jsonb; v_state text:='healthy';
begin
  if not pg_try_advisory_xact_lock(hashtext('ct:pentaself:surgical-orchestrator-v4')) then
    return jsonb_build_object('service','ct.penta.self.surgical-orchestrator.v4','state','SKIPPED_LOCKED','at',now());
  end if;
  v_pre:=penta_self.enforce_desired_state_v1();
  v_factory:=penta_self.reconcile_factory_continuity_v6();
  begin v_truth:=penta_self.reconcile_current_truth_v2(); exception when others then v_truth:=jsonb_build_object('state','failed','error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')); end;
  begin v_intake:=penta_self.message_intake_v1(v_cycle,100); exception when others then v_intake:=jsonb_build_object('state','failed','error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')); end;
  v_surgery_pre:=penta_self.current_truth_surgical_triage_v3(25);
  v_permanent:=penta_self.permanent_repair_tick_v4();
  v_core:=penta_self.tick_v1();
  begin v_heal:=penta_self.problem_heal_cycle_v1(v_cycle,12); exception when others then v_heal:=jsonb_build_object('state','failed','error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')); end;
  v_surgery_post:=penta_self.current_truth_surgical_triage_v3(25);
  v_resolutions:=penta_self.reconcile_verified_problem_resolutions_v2();
  v_post:=penta_self.enforce_desired_state_v1();
  if coalesce(v_permanent->>'state','HEALTHY')='DEGRADED'
     or coalesce(v_core->>'state','HEALTHY') in ('FAILED','DEGRADED')
     or coalesce(v_factory->>'state','')='FAILED' then v_state:='degraded'; end if;
  return jsonb_build_object('service','ct.penta.self.surgical-orchestrator.v4','state',v_state,
    'workflow',jsonb_build_array('diagnose','repair','certify','nurture','discharge'),
    'preflight',v_pre,'factory_continuity_v6',v_factory,'current_truth',v_truth,'message_intake',v_intake,
    'surgery_pre',v_surgery_pre,'permanent_repairs',v_permanent,'core',v_core,'bounded_heal',v_heal,
    'surgery_post',v_surgery_post,'verified_resolutions',v_resolutions,'postflight',v_post,
    'repair_evaluator_version','4.0.0','shallow_repeat_recovery_disabled',true,
    'D3_human_reserved',true,'observed_at',now());
end;
$function$;

-- Materialize the new highest-generation contracts and run the targeted reconciler.
select penta_self.enforce_desired_state_v1();
select penta_self.reconcile_factory_continuity_v6();

do $do$
declare v_cycle uuid:=gen_random_uuid(); v_payload jsonb; v_sha text;
begin
  v_payload:=jsonb_build_object('contract','ct.penta.factory-continuity.v6.monotonic-desired-state',
    'contracts',jsonb_build_object('factory_continuity_generation',3,'factory_dispatch_generation',2,'factory_generator_generation',1),
    'targeted_reconciler','penta_self.reconcile_factory_continuity_v6()',
    'retired_clock_policy','inactive_in_place','higher_generation_supersession_only',true,
    'D3_human_reserved',true,'provider_write',false,'credential_material',false,'installed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,after_sha256,evidence)
    values(v_cycle,'self.reconcile','install_factory_monotonic_contracts_v6','scheduler-family:ct-software-factory',
      'applied',true,'D1',v_sha,v_payload);
  perform chlom_runtime.append_dail_event('pentaself.factory-continuity.v6.monotonic-contracts-installed','self_reconciliation',
    'ct.penta.factory-continuity.v6',v_payload,'PentaSELF/PentaTime/PentaFactory/PentaNurture',null,'PentaSELF','4.0.0',v_sha,null,
    'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal');
end;
$do$;