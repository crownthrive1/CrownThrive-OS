begin;

create or replace function penta_self.scheduler_reconcile_v1(p_cycle_id uuid default gen_random_uuid())
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,penta_self,integration_control,cron,chlom_runtime,extensions,pg_temp
as $$
declare
  r record;
  d integration_control.scheduler_desired_jobs_v2%rowtype;
  v_jobid bigint;
  v_schedule text;
  v_command text;
  v_active boolean;
  v_expected_schedule text;
  v_expected_command text;
  v_expected_active boolean;
  v_risk text;
  v_checked int:=0;
  v_healed int:=0;
  v_missing int:=0;
  v_drift int:=0;
  v_projection_synced int:=0;
  v_finding uuid;
  v_repairs jsonb:='[]'::jsonb;
  v_receipt jsonb;
begin
  for r in
    select * from penta_self.required_jobs_v1
    where auto_repair=true
    order by jobname
  loop
    v_checked:=v_checked+1;
    v_expected_schedule:=r.expected_schedule;
    v_expected_command:=r.expected_command;
    v_expected_active:=true;
    v_risk:=coalesce(r.risk_class,'D1');

    select * into d
    from integration_control.scheduler_desired_jobs_v2
    where jobname=r.jobname
    order by generation desc,updated_at desc
    limit 1;

    if found and d.allow_auto_restore then
      v_expected_schedule:=d.schedule;
      v_expected_command:=d.command;
      v_expected_active:=d.active;

      if r.expected_schedule is distinct from d.schedule
         or r.expected_command is distinct from d.command
         or r.auto_repair is distinct from d.active
         or coalesce(r.metadata->>'scheduler_desired_generation','') is distinct from d.generation::text then
        update penta_self.required_jobs_v1
        set expected_schedule=d.schedule,
            expected_command=d.command,
            auto_repair=d.active,
            metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
              'scheduler_authority','integration_control.scheduler_desired_jobs_v2',
              'scheduler_desired_generation',d.generation,
              'scheduler_desired_source_ref',d.source_ref,
              'rollback_rule','higher_generation_supersession_only',
              'projection_synced_at',clock_timestamp()
            ),
            updated_at=clock_timestamp()
        where jobname=r.jobname;
        v_projection_synced:=v_projection_synced+1;
      end if;
    end if;

    select jobid,schedule,command,active
    into v_jobid,v_schedule,v_command,v_active
    from cron.job
    where jobname=r.jobname
    order by jobid
    limit 1;

    if not v_expected_active then
      if v_jobid is not null and coalesce(v_active,false) then
        v_drift:=v_drift+1;
        insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence)
        values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'scheduler_should_be_inactive',
          jsonb_build_object('live_schedule',v_schedule,'desired_generation',case when d.jobname is not null then d.generation else null end))
        returning finding_id into v_finding;
        perform cron.alter_job(v_jobid,active=>false);
        update penta_self.findings_v1 set state='healed',resolved_at=now() where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','deactivate_superseded_scheduler','cron:'||r.jobname,'applied',true,v_risk,
          jsonb_build_object('jobid',v_jobid,'desired_generation',case when d.jobname is not null then d.generation else null end));
        v_healed:=v_healed+1;
        v_repairs:=v_repairs||jsonb_build_array(jsonb_build_object('jobname',r.jobname,'action','deactivated','jobid',v_jobid));
      end if;
      continue;
    end if;

    if v_jobid is null then
      v_missing:=v_missing+1;
      insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence)
      values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'required_scheduler_missing',
        jsonb_build_object('expected_schedule',v_expected_schedule,'risk_class',v_risk,
          'scheduler_desired_generation',case when d.jobname is not null then d.generation else null end))
      returning finding_id into v_finding;
      begin
        perform cron.schedule(r.jobname,v_expected_schedule,v_expected_command);
        update penta_self.findings_v1 set state='healed',resolved_at=now() where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','schedule_missing_job','cron:'||r.jobname,'applied',true,v_risk,
          jsonb_build_object('schedule',v_expected_schedule,
            'command_sha256',encode(extensions.digest(convert_to(v_expected_command,'UTF8'),'sha256'),'hex'),
            'scheduler_desired_generation',case when d.jobname is not null then d.generation else null end));
        v_healed:=v_healed+1;
        v_repairs:=v_repairs||jsonb_build_array(jsonb_build_object('jobname',r.jobname,'action','created','schedule',v_expected_schedule));
      exception when others then
        update penta_self.findings_v1
        set state='delegated',evidence=evidence||jsonb_build_object('repair_error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'))
        where finding_id=v_finding;
      end;
    elsif coalesce(v_active,false)=false
       or v_schedule is distinct from v_expected_schedule
       or v_command is distinct from v_expected_command then
      v_drift:=v_drift+1;
      insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence)
      values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'scheduler_drift_or_inactive',
        jsonb_build_object('actual_schedule',v_schedule,'expected_schedule',v_expected_schedule,'active',v_active,
          'command_matches',v_command is not distinct from v_expected_command,
          'scheduler_authority','integration_control.scheduler_desired_jobs_v2',
          'scheduler_desired_generation',case when d.jobname is not null then d.generation else null end))
      returning finding_id into v_finding;
      begin
        perform cron.alter_job(v_jobid,schedule=>v_expected_schedule,command=>v_expected_command,active=>true);
        update penta_self.findings_v1 set state='healed',resolved_at=now() where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','repair_scheduler_drift','cron:'||r.jobname,'applied',true,v_risk,
          jsonb_build_object('jobid',v_jobid,'schedule',v_expected_schedule,'active',true,
            'scheduler_desired_generation',case when d.jobname is not null then d.generation else null end));
        v_healed:=v_healed+1;
        v_repairs:=v_repairs||jsonb_build_array(jsonb_build_object('jobname',r.jobname,'action','reconciled','jobid',v_jobid,'schedule',v_expected_schedule));
      exception when others then
        update penta_self.findings_v1
        set state='delegated',evidence=evidence||jsonb_build_object('repair_error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'))
        where finding_id=v_finding;
      end;
    end if;
  end loop;

  if v_healed>0 or v_projection_synced>0 then
    v_receipt:=chlom_runtime.append_dail_event(
      'scheduler.pentaself.reconciled','scheduler_topology','ct.scheduler-topology.production.v1',
      jsonb_build_object(
        'cycle_id',p_cycle_id,'checked',v_checked,'missing',v_missing,
        'drifted_or_inactive',v_drift,'healed',v_healed,
        'required_job_projection_synced',v_projection_synced,
        'scheduler_authority','integration_control.scheduler_desired_jobs_v2',
        'rollback_rule','higher_generation_supersession_only','repairs',v_repairs,
        'new_clock_created_only_if_desired_missing',true,'authority_created',false,
        'd3_human_reserved',true,'observed_at',clock_timestamp()
      ),
      'PentaSELF/PentaTime/PentaTick/PentaWork/PentaNurture',null,'PentaSELF','1.1.0',
      encode(extensions.digest(convert_to(p_cycle_id::text||':'||v_checked::text||':'||v_healed::text||':'||v_projection_synced::text,'UTF8'),'sha256'),'hex'),
      null,'founder-directive:2026-08-29:scheduler-authority-monotonic',null,'internal'
    );
  end if;

  return jsonb_build_object(
    'service','ct.penta.self.scheduler-reconcile.v1','checked',v_checked,'missing',v_missing,
    'drifted_or_inactive',v_drift,'healed',v_healed,
    'required_job_projection_synced',v_projection_synced,
    'scheduler_authority','integration_control.scheduler_desired_jobs_v2',
    'rollback_rule','higher_generation_supersession_only','dail_receipt',v_receipt,
    'at',clock_timestamp()
  );
end;
$$;

revoke all on function penta_self.scheduler_reconcile_v1(uuid) from public,anon,authenticated;
grant execute on function penta_self.scheduler_reconcile_v1(uuid) to service_role;

commit;
