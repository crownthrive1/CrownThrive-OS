-- Reversible operational rollback for PentaMarketer Persona Execution Bridge v1.
-- Preserve schema, requests, events, certification evidence, and historical lineage.

do $$
declare v_jobid bigint;
begin
  for v_jobid in select jobid from cron.job where jobname='penta-persona-execution-v1' loop
    perform cron.unschedule(v_jobid);
  end loop;

  update crm.penta_persona_execution_control_v1
     set automation_enabled=false,
         kill_switch=true,
         certification_state='hold',
         metadata=metadata||jsonb_build_object(
           'rollback_at',now(),
           'rollback_reason','operator_or_assurance_initiated',
           'evidence_preserved',true
         ),
         updated_at=now()
   where control_key='default';

  update crm.penta_persona_execution_capabilities_v1
     set certification_state='hold',updated_at=now()
   where enabled=true;

  update crm.penta_persona_execution_playbooks_v1
     set enabled=false,updated_at=now()
   where enabled=true;

  update crm.penta_persona_execution_requests_v1
     set state='cancelled',
         error_code='BRIDGE_ROLLBACK',
         error_message='Cancelled by Persona Execution Bridge rollback; evidence preserved.',
         completed_at=coalesce(completed_at,now()),
         lease_expires_at=null,
         updated_at=now()
   where state in ('queued','retry_wait');

  update public.penta_system_registry
     set maturity='hold',
         metadata=metadata||jsonb_build_object(
           'certification_state','hold',
           'automation_state','disabled',
           'rollback_at',now(),
           'evidence_preserved',true
         ),
         updated_at=now()
   where system_key='penta.persona-execution';
end $$;
