-- PentaSELF V4 permanent-repair evaluator.
create or replace function penta_self.evaluate_permanent_repair_v4(
  p_repair_key text,p_repair_class text,p_desired_state jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','integration_control','crm','pentatime','public','extensions','cron','pg_temp'
as $function$
declare v_result jsonb; v_ready boolean:=true; v_error_class text;
begin
  case p_repair_class
    when 'scheduler_permanence' then v_result:=integration_control.scheduler_permanence_reconcile_v2();
    when 'scheduler_no_rollback' then v_result:=integration_control.scheduler_no_automatic_rollback_audit_v2();
    when 'current_truth' then v_result:=penta_self.reconcile_current_truth_v2();
    when 'marketing_event_projection' then v_result:=crm.penta_marketer_refresh_event_projection_v2(coalesce(p_desired_state->>'campaign_ref','ct.pentamarketer.locticians.claim.20260827.v1'));
    when 'bd_warm_failover' then v_result:=integration_control.locticians_bd_warm_failover_reconcile_v3();
    when 'stripe_webhook_health' then v_result:=integration_control.stripe_webhook_health_reconcile_v2();
    when 'paypal_webhook_health' then v_result:=integration_control.paypal_webhook_health_reconcile_v2();
    when 'penta_fabric_health' then v_result:=penta_self.penta_fabric_health_reconcile_v2();
    when 'provider_alert_ingress' then v_result:=integration_control.institutional_provider_alert_health_reconcile_v2();
    when 'provider_current_truth' then v_result:=integration_control.paypal_current_truth_v4();
    when 'dail_terminal_projection' then v_result:=integration_control.penta_mail_terminal_projection_status_v1();
    when 'locticians_provider_implementation' then
      v_result:=jsonb_build_object(
        'status',public.locticians_all_post_types_status_v4(),
        'operation',(select to_jsonb(s) from pentatime.operation_state_v2 s where operation_key='locticians_all_post_types'),
        'cron',(select to_jsonb(j) from cron.job j where jobname='ct-locticians-all-post-types-maintenance-v4' and active order by jobid desc limit 1)
      );
    when 'locticians_provider_types' then v_result:=public.locticians_all_post_types_status_v4();
    when 'commercial_release_repair' then
      v_result:=jsonb_build_object(
        'status',integration_control.commercial_release_repair_status_v3(),
        'registry',(select to_jsonb(f) from integration_control.penta_factory_registry_v1 f where factory_key='penta.commercial-release-factory'),
        'operation',(select to_jsonb(s) from pentatime.operation_state_v2 s where operation_key='commercial_release_repair')
      );
    when 'factory_continuity_surgery' then v_result:=penta_self.verify_factory_continuity_surgery_v1();
    when 'factory_generator_surgery' then v_result:=penta_self.verify_factory_generator_surgery_v1();
    when 'pentaod_lock_surgery' then v_result:=penta_self.verify_pentaod_surgery_v1();
    when 'scheduler_surgery' then
      if p_repair_key='ct.penta-self.repair.penta-crawler-pentatime-guard.v1' then
        v_result:=jsonb_build_object(
          'cron',(select to_jsonb(j) from cron.job j where jobname='ct-penta-crawler-roam-v3' and active order by jobid desc limit 1),
          'operation',(select to_jsonb(s) from pentatime.operation_state_v2 s where operation_key='penta_crawler'),
          'executor',(select executor_regprocedure::text from pentatime.operation_executors_v3 where operation_key='penta_crawler' and enabled)
        );
      elsif p_repair_key='ct.penta-self.repair.paypal-pentatime-backoff.v4' then
        v_result:=jsonb_build_object(
          'webhook_operation',(select to_jsonb(s) from pentatime.operation_state_v2 s where operation_key='paypal_webhook_reconcile'),
          'receipt_operation',(select to_jsonb(s) from pentatime.operation_state_v2 s where operation_key='paypal_live_receipt_reconcile'),
          'webhook_cron',(select to_jsonb(j) from cron.job j where jobname='ct-paypal-webhook-reconcile-v3' and active order by jobid desc limit 1),
          'receipt_cron',(select to_jsonb(j) from cron.job j where jobname='ct-paypal-live-receipt-reconcile-v1' and active order by jobid desc limit 1)
        );
      elsif p_repair_key='ct.penta-self.repair.pentatime-registered-executor-fabric.v3' then
        v_result:=jsonb_build_object(
          'registered_executors',(select count(*) from pentatime.operation_executors_v3 where enabled),
          'required_jobs_converged',(select count(*) from penta_self.required_jobs_v1 rj join pentatime.operation_registry_v2 o on rj.jobname=o.metadata->>'job' where rj.auto_repair and rj.expected_command=format('select pentatime.execute_guarded_v3(%L);',o.operation_key)),
          'active_jobs_converged',(select count(*) from cron.job j join pentatime.operation_registry_v2 o on j.jobname=o.metadata->>'job' where j.active and j.command=format('select pentatime.execute_guarded_v3(%L);',o.operation_key))
        );
      else v_result:=integration_control.scheduler_permanence_reconcile_v2();
      end if;
    else
      v_ready:=false; v_error_class:='HANDLER_UNREGISTERED';
      v_result:=jsonb_build_object('state','HOLD_HANDLER_UNREGISTERED','repair_key',p_repair_key,
        'repair_class',p_repair_class,'automatic_retry',false,'authority_manufactured',false);
  end case;

  if p_repair_class='scheduler_permanence' then
    v_ready:=coalesce(v_result->>'state','')='ok';
  elsif p_repair_class='scheduler_no_rollback' then
    v_ready:=coalesce(v_result->>'state','')='PASS';
  elsif p_repair_class='provider_current_truth' then
    v_ready:=coalesce((v_result->>'transport_current')::boolean,false);
  elsif p_repair_class='dail_terminal_projection' then
    v_ready:=coalesce(v_result->>'state','')='HEALTHY' and coalesce((v_result->>'unbound_terminal_receipts')::integer,0)=0;
  elsif p_repair_class='locticians_provider_implementation' then
    v_ready:=v_result#>>'{status,state}'='production_ready'
      and coalesce((v_result#>>'{status,counts,readiness_failures}')::integer,0)=0
      and v_result#>>'{cron,command}'=$cmd$select pentatime.execute_guarded_v3('locticians_all_post_types');$cmd$;
  elsif p_repair_class='locticians_provider_types' then
    v_ready:=coalesce(v_result->>'state','')='production_ready';
  elsif p_repair_class='commercial_release_repair' then
    v_ready:=v_result#>>'{registry,runtime_state}'='active'
      and not coalesce((v_result#>>'{registry,evidence,observer_only}')::boolean,true);
  elsif p_repair_class in ('factory_continuity_surgery','factory_generator_surgery','pentaod_lock_surgery') then
    v_ready:=coalesce((v_result->>'ready')::boolean,false);
  elsif p_repair_class='scheduler_surgery' and p_repair_key='ct.penta-self.repair.penta-crawler-pentatime-guard.v1' then
    v_ready:=v_result#>>'{cron,command}'=$cmd$select pentatime.execute_guarded_v3('penta_crawler');$cmd$ and v_result->>'executor' is not null;
  elsif p_repair_class='scheduler_surgery' and p_repair_key='ct.penta-self.repair.paypal-pentatime-backoff.v4' then
    v_ready:=v_result#>>'{webhook_cron,command}'=$cmd$select pentatime.execute_guarded_v3('paypal_webhook_reconcile');$cmd$
      and v_result#>>'{receipt_cron,command}'=$cmd$select pentatime.execute_guarded_v3('paypal_live_receipt_reconcile');$cmd$;
  elsif p_repair_class='scheduler_surgery' and p_repair_key='ct.penta-self.repair.pentatime-registered-executor-fabric.v3' then
    v_ready:=coalesce((v_result->>'registered_executors')::integer,0)>=13;
  elsif p_repair_class='scheduler_surgery' then
    v_ready:=coalesce(v_result->>'state','') in ('ok','PASS');
  end if;

  if not v_ready and v_error_class is null then v_error_class:='CURRENT_TRUTH_NOT_VERIFIED'; end if;
  return jsonb_build_object('ready',v_ready,'result',coalesce(v_result,'{}'::jsonb),
    'error_class',v_error_class,'repair_key',p_repair_key,'repair_class',p_repair_class,
    'evaluator','ct.penta.self.permanent-repair-evaluator.v4','observed_at',clock_timestamp());
exception when others then
  return jsonb_build_object('ready',false,
    'result',jsonb_build_object('error_class',sqlstate,'error_message_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')),
    'error_class',sqlstate,'repair_key',p_repair_key,'repair_class',p_repair_class,
    'evaluator','ct.penta.self.permanent-repair-evaluator.v4','observed_at',clock_timestamp());
end;
$function$;
revoke all on function penta_self.evaluate_permanent_repair_v4(text,text,jsonb) from public,anon,authenticated;
grant execute on function penta_self.evaluate_permanent_repair_v4(text,text,jsonb) to service_role;

create or replace function penta_self.permanent_repair_tick_v4()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','extensions','chlom_runtime','pg_temp'
as $function$
declare
  r penta_self.permanent_repairs_v2%rowtype; v_eval jsonb; v_result jsonb;
  v_state text; v_previous text; v_error_class text; v_digest text;
  v_ok integer:=0; v_failed integer:=0; v_transitioned integer:=0; v_should_emit boolean;
begin
  for r in select * from penta_self.permanent_repairs_v2 where enabled order by repair_key loop
    v_previous:=r.last_state;
    v_eval:=penta_self.evaluate_permanent_repair_v4(r.repair_key,r.repair_class,r.desired_state);
    v_result:=coalesce(v_eval->'result','{}'::jsonb);
    v_state:=case when coalesce((v_eval->>'ready')::boolean,false) then 'verified' else 'degraded' end;
    v_error_class:=case when v_state='verified' then null else coalesce(v_eval->>'error_class','CURRENT_TRUTH_NOT_VERIFIED') end;
    if v_state='verified' then v_ok:=v_ok+1; else v_failed:=v_failed+1; end if;
    v_should_emit:=v_previous is distinct from v_state or r.last_verified_at is null or r.last_verified_at<now()-interval '6 hours';
    update penta_self.permanent_repairs_v2
      set last_state=v_state,last_result=v_result,last_error_class=v_error_class,last_attempt_at=now(),
          last_verified_at=case when v_state='verified' then now() else last_verified_at end,updated_at=now()
      where repair_key=r.repair_key;
    if v_should_emit then
      if v_previous is distinct from v_state then v_transitioned:=v_transitioned+1; end if;
      v_digest:=encode(extensions.digest(convert_to(jsonb_build_object('repair_key',r.repair_key,
        'generation',r.generation,'state',v_state,'result',v_result,'evaluator','v4','observed_at',now())::text,'UTF8'),'sha256'),'hex');
      insert into penta_self.permanent_repair_events_v2(repair_key,generation,event_type,state,evidence,evidence_sha256)
        values(r.repair_key,r.generation,'verification_tick_v4',v_state,v_result,v_digest);
    end if;
  end loop;
  if v_transitioned>0 or v_failed>0 then
    perform chlom_runtime.append_dail_event('pentaself.permanent_repairs.tick','self_healing','ct.penta.self.permanent-repairs.v4',
      jsonb_build_object('verified',v_ok,'degraded',v_failed,'state_transitions',v_transitioned,
        'handler_gap_fail_closed',true,'observed_at',now()),
      'PentaSELF/PentaAssure/PentaTime/PentaNurture',null,'PentaSELF','4.0.0',
      encode(extensions.digest(convert_to(v_ok::text||':'||v_failed::text||':'||v_transitioned::text,'UTF8'),'sha256'),'hex'),
      null,'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal');
  end if;
  return jsonb_build_object('state',case when v_failed>0 then 'DEGRADED' else 'HEALTHY' end,
    'verified',v_ok,'degraded',v_failed,'state_transitions',v_transitioned,
    'evaluator_version','4.0.0','observed_at',now());
end;
$function$;
revoke all on function penta_self.permanent_repair_tick_v4() from public,anon,authenticated;
grant execute on function penta_self.permanent_repair_tick_v4() to service_role;

create or replace function penta_self.surgical_orchestrator_v4()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','public','extensions','pg_temp'
as $function$
declare
  v_cycle uuid:=gen_random_uuid(); v_pre jsonb; v_truth jsonb; v_intake jsonb;
  v_surgery_pre jsonb; v_permanent jsonb; v_core jsonb; v_heal jsonb;
  v_surgery_post jsonb; v_resolutions jsonb; v_post jsonb; v_state text:='healthy';
begin
  if not pg_try_advisory_xact_lock(hashtext('ct:pentaself:surgical-orchestrator-v4')) then
    return jsonb_build_object('service','ct.penta.self.surgical-orchestrator.v4','state','SKIPPED_LOCKED','at',now());
  end if;
  v_pre:=penta_self.enforce_desired_state_v1();
  begin v_truth:=penta_self.reconcile_current_truth_v2(); exception when others then v_truth:=jsonb_build_object('state','failed','error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')); end;
  begin v_intake:=penta_self.message_intake_v1(v_cycle,100); exception when others then v_intake:=jsonb_build_object('state','failed','error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')); end;
  v_surgery_pre:=penta_self.current_truth_surgical_triage_v3(25);
  v_permanent:=penta_self.permanent_repair_tick_v4();
  v_core:=penta_self.tick_v1();
  begin v_heal:=penta_self.problem_heal_cycle_v1(v_cycle,12); exception when others then v_heal:=jsonb_build_object('state','failed','error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex')); end;
  v_surgery_post:=penta_self.current_truth_surgical_triage_v3(25);
  v_resolutions:=penta_self.reconcile_verified_problem_resolutions_v2();
  v_post:=penta_self.enforce_desired_state_v1();
  if coalesce(v_permanent->>'state','HEALTHY')='DEGRADED' or coalesce(v_core->>'state','HEALTHY') in ('FAILED','DEGRADED') then v_state:='degraded'; end if;
  return jsonb_build_object('service','ct.penta.self.surgical-orchestrator.v4','state',v_state,
    'workflow',jsonb_build_array('diagnose','repair','certify','nurture','discharge'),
    'preflight',v_pre,'current_truth',v_truth,'message_intake',v_intake,'surgery_pre',v_surgery_pre,
    'permanent_repairs',v_permanent,'core',v_core,'bounded_heal',v_heal,'surgery_post',v_surgery_post,
    'verified_resolutions',v_resolutions,'postflight',v_post,'repair_evaluator_version','4.0.0',
    'shallow_repeat_recovery_disabled',true,'D3_human_reserved',true,'observed_at',now());
end;
$function$;
revoke all on function penta_self.surgical_orchestrator_v4() from public,anon,authenticated;
grant execute on function penta_self.surgical_orchestrator_v4() to service_role;

create or replace function public.penta_self_tick_v1()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','penta_self'
as $function$select penta_self.surgical_orchestrator_v4();$function$;

update pentatime.operation_registry_v2
set metadata=metadata||jsonb_build_object('orchestrator','penta_self.surgical_orchestrator_v4()',
  'repair_evaluator_version','4.0.0','source_ref','migration:pentaself_v4_permanent_repair_evaluator'),updated_at=now()
where operation_key='penta_self';

select penta_self.register_permanent_repair_v2(
  'ct.penta-self.repair.factory-continuity-overlap-surgery.v1',2026082912,'factory_continuity_surgery',
  'ct.scheduler-topology.production.v1',
  jsonb_build_object('canonical_job','ct-software-factory-continuity-v5','guarded_dispatch_job','ct-software-factory-dispatch-v3',
    'duplicate_jobs',jsonb_build_array('ct-factory-surface-binding-sync-v4','ct-software-factory-tick-v2'),
    'verification_function','penta_self.verify_factory_continuity_surgery_v1()',
    'continuity_contract','ct.penta.factory-continuity.v6'),
  jsonb_build_object('owner','PentaFactory/PentaTime/PentaSELF/PentaNurture','reopen_on_regression',true,'self_certifying',true)
);
select penta_self.register_permanent_repair_v2(
  'ct.penta-self.repair.factory-generator-recursion-surgery.v1',2026082912,'factory_generator_surgery',
  'ct.scheduler-topology.production.v1',
  jsonb_build_object('operation_key','factory_internal_generate','verification_function','penta_self.verify_factory_generator_surgery_v1()',
    'recursive_factory_tick_removed',true,'continuity_contract','ct.penta.factory-continuity.v6'),
  jsonb_build_object('owner','PentaFactory/PentaBuild/PentaTime/PentaSELF/PentaNurture','reopen_on_regression',true,'self_certifying',true)
);
select penta_self.register_permanent_repair_v2(
  'ct.penta-self.repair.pentaod-lock-surgery.v1',2026082912,'pentaod_lock_surgery','ct.scheduler-topology.production.v1',
  jsonb_build_object('operation_key','pentaod_sleep','row_lock_policy','FOR UPDATE SKIP LOCKED','verification_function','penta_self.verify_pentaod_surgery_v1()'),
  jsonb_build_object('owner','PentaOD/PentaTime/PentaSELF/PentaNurture','reopen_on_regression',true,'evaluator_version','4.0.0')
);
select penta_self.register_permanent_repair_v2(
  'ct.penta-self.repair.locticians-all-post-types.v4',2026082912,'locticians_provider_types','ct.scheduler-topology.production.v1',
  jsonb_build_object('status','public.locticians_all_post_types_status_v4()','required_state','production_ready','guarded_operation','locticians_all_post_types'),
  jsonb_build_object('owner_pentas',jsonb_build_array('PentaMarketer','PentaFactory','PentaCertify','PentaTime','PentaSELF'),'evaluator_version','4.0.0')
);

do $do$
declare v_cycle uuid:=gen_random_uuid(); v_payload jsonb; v_sha text;
begin
  v_payload:=jsonb_build_object('contract','ct.penta.self.v4','repair_evaluator','v4',
    'newly_supported_repair_classes',jsonb_build_array('factory_continuity_surgery','factory_generator_surgery','pentaod_lock_surgery','locticians_provider_types'),
    'handler_gap_fail_closed',true,'orchestrator','penta_self.surgical_orchestrator_v4()',
    'D3_human_reserved',true,'provider_write',false,'credential_material',false,'installed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,after_sha256,evidence)
    values(v_cycle,'self.update','install_pentaself_v4_permanent_repair_evaluator','system:PentaSELF','applied',true,'D1',v_sha,v_payload);
  perform chlom_runtime.append_dail_event('pentaself.v4.permanent-repair-evaluator.installed','self_update','ct.penta.self.v4',
    v_payload,'PentaSELF/PentaTime/PentaFactory/PentaCertify/PentaNurture',null,'PentaSELF','4.0.0',v_sha,null,
    'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal');
end;
$do$;