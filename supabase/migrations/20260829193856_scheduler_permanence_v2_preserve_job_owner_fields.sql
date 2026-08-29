-- Preserve pg_cron database/username ownership fields during in-place desired-state repair.
create or replace function integration_control.scheduler_permanence_reconcile_v2()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','cron','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  d record; c record; v_action text; v_digest text;
  v_checked int:=0; v_restored int:=0; v_healthy int:=0; v_failed int:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.scheduler.permanence.v2',0)) then
    return jsonb_build_object('state','locked','checked',0);
  end if;
  for d in select * from integration_control.scheduler_desired_jobs_v2 where active=true and allow_auto_restore=true order by jobname loop
    v_checked:=v_checked+1;
    select jobid,jobname,schedule,command,database,username,active into c
      from cron.job where jobname=d.jobname order by jobid desc limit 1;
    begin
      if c.jobid is null then
        perform cron.schedule(d.jobname,d.schedule,d.command);
        v_action:='restored_missing'; v_restored:=v_restored+1;
      elsif c.schedule is distinct from d.schedule or c.command is distinct from d.command or c.active is distinct from true then
        perform cron.alter_job(c.jobid,schedule=>d.schedule,command=>d.command,active=>true);
        v_action:='restored_drift_in_place'; v_restored:=v_restored+1;
      else
        v_action:='healthy'; v_healthy:=v_healthy+1;
      end if;
      v_digest:=encode(extensions.digest(convert_to(jsonb_build_object(
        'jobname',d.jobname,'generation',d.generation,'action',v_action,
        'observed_schedule',c.schedule,'observed_command',c.command,
        'desired_schedule',d.schedule,'desired_command',d.command
      )::text,'UTF8'),'sha256'),'hex');
      if v_action<>'healthy' then
        insert into integration_control.scheduler_reconcile_events_v2(
          jobname,generation,observed_state,desired_state,action,result_state,evidence_sha256
        ) values (
          d.jobname,d.generation,
          jsonb_build_object('jobid',c.jobid,'schedule',c.schedule,'command',c.command,'active',c.active,
            'database_preserved',c.database,'username_preserved',c.username),
          jsonb_build_object('schedule',d.schedule,'command',d.command,'active',true,'source_ref',d.source_ref),
          v_action,'applied',v_digest
        );
      end if;
    exception when others then
      v_failed:=v_failed+1;
      v_digest:=encode(extensions.digest(convert_to(jsonb_build_object(
        'jobname',d.jobname,'generation',d.generation,'error_state',sqlstate
      )::text,'UTF8'),'sha256'),'hex');
      insert into integration_control.scheduler_reconcile_events_v2(
        jobname,generation,observed_state,desired_state,action,result_state,evidence_sha256
      ) values (
        d.jobname,d.generation,jsonb_build_object('jobid',c.jobid,'schedule',c.schedule,'active',c.active),
        jsonb_build_object('schedule',d.schedule,'active',true,'source_ref',d.source_ref),
        'restore_failed','failed',v_digest
      );
    end;
  end loop;
  return jsonb_build_object(
    'state',case when v_failed>0 then 'degraded' else 'ok' end,
    'checked',v_checked,'healthy',v_healthy,'restored',v_restored,'failed',v_failed,
    'mutation_api','cron.alter_job','job_identity_preserved',true,
    'database_and_username_preserved',true,
    'generation_floor',(select min(generation) from integration_control.scheduler_desired_jobs_v2 where active=true),
    'observed_at',now()
  );
end;
$function$;

do $do$
declare v_cycle uuid:=gen_random_uuid(); v_payload jsonb; v_sha text;
begin
  v_payload:=jsonb_build_object('contract','ct.scheduler.permanence.v2.owner-field-preservation',
    'mutation_api','cron.alter_job','mutable_fields',jsonb_build_array('schedule','command','active'),
    'preserved_fields',jsonb_build_array('database','username'),'job_identity_preserved',true,
    'D3_human_reserved',true,'provider_write',false,'credential_material',false,'installed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,after_sha256,evidence)
    values(v_cycle,'self.schedule','install_scheduler_owner_field_preservation_v2','scheduler-fabric:PentaTime',
      'applied',true,'D1',v_sha,v_payload);
  perform chlom_runtime.append_dail_event('scheduler.permanence.owner-fields-preserved','scheduler_security',
    'ct.scheduler.permanence.v2',v_payload,'PentaSELF/PentaTime/PentaAssure',null,'PentaTime','2.1.0',v_sha,null,
    'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal');
end;
$do$;