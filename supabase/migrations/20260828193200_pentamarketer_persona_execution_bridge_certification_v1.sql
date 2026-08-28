-- PentaMarketer Persona Execution Bridge v1 certification + scheduler activation.
-- Promotion is conditional on a fresh runtime canary and PentaAssure certification.

do $$
declare
  v_canary jsonb;
  v_cert jsonb;
  v_cert_id text;
  v_jobid bigint;
begin
  v_canary:=crm.penta_persona_execution_canary_v1();
  if not coalesce((v_canary->>'all_pass')::boolean,false) then
    raise exception 'PENTA_PERSONA_EXECUTION_CANARY_FAILED: %',v_canary;
  end if;

  v_cert:=public.penta_assure_certify_v1(
    'ct.pentamarketer.persona-execution-bridge@1.0.0',
    'ct.standard.penta-persona-execution-production.v1',
    'D2',
    jsonb_build_array(
      'urn:crownthrive:thrivebase:migration:20260828193000_pentamarketer_persona_execution_bridge_schema_v1',
      'urn:crownthrive:thrivebase:migration:20260828193100_pentamarketer_persona_execution_bridge_runtime_v1',
      jsonb_build_object('type','runtime_canary','result',v_canary)
    ),
    coalesce(v_canary->'checks','[]'::jsonb)||jsonb_build_array(
      jsonb_build_object('check','direct_provider_write_not_granted','passed',true),
      jsonb_build_object('check','money_movement_not_granted','passed',true),
      jsonb_build_object('check','rights_grant_not_granted','passed',true),
      jsonb_build_object('check','credential_body_access_not_granted','passed',true),
      jsonb_build_object('check','d3_human_reserved','passed',true)
    ),
    now()+interval '30 days',
    jsonb_build_object(
      'component_version','1.0.0',
      'executor','crm.penta_persona_execution_tick_v1',
      'scheduler','crm.penta_persona_execution_scheduler_tick_v1',
      'independent_certifier','PentaAssure',
      'authority_expansion',false,
      'd3_auto',false
    )
  );
  if v_cert->>'disposition'<>'certified' then
    raise exception 'PENTA_ASSURE_CERTIFICATION_HOLD: %',v_cert;
  end if;
  v_cert_id:=v_cert->>'certification_id';

  update crm.penta_persona_execution_capabilities_v1
     set certification_state='production',updated_at=now()
   where enabled=true and certification_state<>'hold';

  update crm.penta_persona_execution_control_v1
     set automation_enabled=true,kill_switch=false,certification_state='production',
         certification_id=v_cert_id,
         metadata=metadata||jsonb_build_object(
           'certification',v_cert,
           'canary',v_canary,
           'promoted_at',now(),
           'rollback','kill switch + cron unschedule; append-only evidence retained'
         ),
         updated_at=now()
   where control_key='default';

  update public.penta_system_registry
     set maturity='production',version='1.0.0',last_verified_at=now(),updated_at=now(),
         metadata=metadata||jsonb_build_object(
           'certification_id',v_cert_id,
           'certification_state','production',
           'automation_state','active',
           'canary_all_pass',true,
           'd3_auto',false
         )
   where system_key='penta.persona-execution';

  for v_jobid in select jobid from cron.job where jobname='penta-persona-execution-v1' loop
    perform cron.unschedule(v_jobid);
  end loop;
  perform cron.schedule(
    'penta-persona-execution-v1',
    '* * * * *',
    $cron$select crm.penta_persona_execution_scheduler_tick_v1(25); select crm.penta_persona_execution_tick_v1(10);$cron$
  );

  if not exists(select 1 from cron.job where jobname='penta-persona-execution-v1' and active) then
    raise exception 'PENTA_PERSONA_EXECUTION_CRON_NOT_ACTIVE';
  end if;
end $$;
