-- Canonical factory scheduler state and monotonic generation fence.
create or replace function integration_control.guard_scheduler_desired_generation_v3()
returns trigger
language plpgsql
security definer
set search_path='pg_catalog','integration_control'
as $function$
begin
  if new.generation < old.generation then
    raise exception using errcode='55000', message=format(
      'stale_scheduler_generation_rejected:%s:new=%s:current=%s',old.jobname,new.generation,old.generation
    );
  end if;
  if new.generation = old.generation and (
       new.schedule is distinct from old.schedule
    or new.command is distinct from old.command
    or new.active is distinct from old.active
    or new.allow_auto_restore is distinct from old.allow_auto_restore
  ) then
    raise exception using errcode='55000', message=format(
      'same_generation_scheduler_mutation_rejected:%s:generation=%s',old.jobname,old.generation
    );
  end if;
  return new;
end;
$function$;
revoke all on function integration_control.guard_scheduler_desired_generation_v3() from public,anon,authenticated;
drop trigger if exists trg_scheduler_desired_generation_v3 on integration_control.scheduler_desired_jobs_v2;
create trigger trg_scheduler_desired_generation_v3
before update on integration_control.scheduler_desired_jobs_v2
for each row execute function integration_control.guard_scheduler_desired_generation_v3();

insert into integration_control.scheduler_desired_jobs_v2(
  jobname,schedule,command,database_name,username,active,generation,source_ref,desired_sha256,allow_auto_restore,metadata
)
select x.jobname,x.schedule,x.command,'postgres','postgres',x.active,2026082912,
       'ct.scheduler.factory-continuity-v6.canonical',
       encode(extensions.digest(convert_to(jsonb_build_object(
         'jobname',x.jobname,'schedule',x.schedule,'command',x.command,'active',x.active,
         'generation',2026082912,'allow_auto_restore',x.allow_auto_restore
       )::text,'UTF8'),'sha256'),'hex'),
       x.allow_auto_restore,
       jsonb_build_object(
         'owner',x.owner_ref,'generation',2026082912,
         'continuity_contract','ct.penta.factory-continuity.v6',
         'contention_domain','ct:production-governance-write-lane',
         'canonical_executor','pentatime.execute_guarded_v3(text)',
         'direct_runtime_call_forbidden',x.active,
         'rollback_policy','higher_generation_supersession_only',
         'authority_created',false,'new_external_clock',false,
         'source_ref','migration:factory_continuity_v6_scheduler_generation_fence'
       )
from (values
  ('ct-software-factory-continuity-v5'::text,'0-58/2 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$::text,true,true,'PentaFactory/PentaTime'::text),
  ('ct-software-factory-dispatch-v3'::text,'* * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$::text,true,true,'PentaFactory/PentaTime'::text),
  ('ct-factory-internal-openai-generate-v1'::text,'7,17,27,37,47,57 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$::text,true,true,'PentaFactory/PentaBuild/PentaTime'::text),
  ('ct-software-factory-tick-v2'::text,'*/5 * * * *'::text,$cmd$select public.ct_factory_tick();$cmd$::text,false,false,'PentaFactory'::text),
  ('ct-factory-surface-binding-sync-v4'::text,'12,27,42,57 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_surface_binding_sync');$cmd$::text,false,false,'PentaFactory/PentaWire/PentaTime'::text)
) as x(jobname,schedule,command,active,allow_auto_restore,owner_ref)
on conflict(jobname) do update set
  schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,
  username=excluded.username,active=excluded.active,generation=excluded.generation,
  source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,
  allow_auto_restore=excluded.allow_auto_restore,
  metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,
  updated_at=now()
where excluded.generation >= integration_control.scheduler_desired_jobs_v2.generation;

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
        perform cron.alter_job(c.jobid,schedule=>d.schedule,command=>d.command,
          database=>coalesce(d.database_name,c.database),username=>coalesce(d.username,c.username),active=>true);
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
          jsonb_build_object('jobid',c.jobid,'schedule',c.schedule,'command',c.command,'active',c.active),
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
    'generation_floor',(select min(generation) from integration_control.scheduler_desired_jobs_v2 where active=true),
    'observed_at',now()
  );
end;
$function$;

select integration_control.scheduler_permanence_reconcile_v2();

do $do$
declare v_cycle uuid:=gen_random_uuid(); v_payload jsonb; v_sha text;
begin
  v_payload:=jsonb_build_object(
    'contract','ct.penta.factory-continuity.v6.scheduler-generation-fence',
    'scheduler_generation',2026082912,'stale_dispatch_source_superseded',true,
    'generation_regression_rejected',true,'same_generation_behavior_mutation_rejected',true,
    'reconcile_mutation_api','cron.alter_job','job_identity_preserved',true,
    'D3_human_reserved',true,'provider_write',false,'credential_material',false,
    'installed_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(
    cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,after_sha256,evidence
  ) values (
    v_cycle,'self.schedule','install_factory_scheduler_generation_fence_v6','scheduler-family:ct-software-factory',
    'applied',true,'D1',v_sha,v_payload
  );
  perform chlom_runtime.append_dail_event(
    'pentaself.factory-scheduler.v6.generation-fence-installed','scheduler_security',
    'ct.penta.factory-continuity.v6',v_payload,
    'PentaSELF/PentaTime/PentaFactory/PentaNurture',null,'PentaSELF','4.0.0',v_sha,null,
    'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal'
  );
end;
$do$;