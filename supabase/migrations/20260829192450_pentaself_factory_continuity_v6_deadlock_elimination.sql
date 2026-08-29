-- CrownThrive COS / PentaSELF factory continuity V6
-- Permanent deadlock elimination for the software-factory scheduler family.

create or replace function pentatime.executor_factory_dispatch_v3()
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','public'
as $function$
declare
  v_result jsonb;
begin
  v_result := public.ct_factory_dispatch_tick();
  return jsonb_build_object(
    'executed', true,
    'state', 'SUCCEEDED',
    'contract', 'ct.pentatime.factory-dispatch.v3',
    'result', coalesce(v_result,'{}'::jsonb),
    'authority_effect', 'none_beyond_existing_authority',
    'provider_write_manufactured', false,
    'observed_at', clock_timestamp()
  );
end;
$function$;

revoke all on function pentatime.executor_factory_dispatch_v3() from public, anon, authenticated;
grant execute on function pentatime.executor_factory_dispatch_v3() to service_role;

insert into pentatime.operation_registry_v2(
  operation_key,domain_key,owner_penta,enabled,base_backoff_seconds,max_backoff_seconds,metadata
) values (
  'factory_dispatch','ct:production-governance-write-lane','PentaFactory/PentaTime',true,5,180,
  jsonb_build_object(
    'job','ct-software-factory-dispatch-v3',
    'class','factory_dispatch',
    'execution_contract','v3',
    'continuity_contract','v6',
    'direct_runtime_call_forbidden',true,
    'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination'
  )
)
on conflict(operation_key) do update set
  domain_key=excluded.domain_key,
  owner_penta=excluded.owner_penta,
  enabled=true,
  base_backoff_seconds=excluded.base_backoff_seconds,
  max_backoff_seconds=excluded.max_backoff_seconds,
  metadata=pentatime.operation_registry_v2.metadata||excluded.metadata,
  updated_at=now();

insert into pentatime.operation_executors_v3(
  operation_key,executor_regprocedure,authority_ceiling,enabled,metadata
) values (
  'factory_dispatch','pentatime.executor_factory_dispatch_v3()'::regprocedure,'D2',true,
  jsonb_build_object(
    'family','PentaFactory/PentaTime',
    'continuity_contract','v6',
    'provider_write_authority_created',false,
    'D3_authority_created',false
  )
)
on conflict(operation_key) do update set
  executor_regprocedure=excluded.executor_regprocedure,
  authority_ceiling=excluded.authority_ceiling,
  enabled=true,
  metadata=pentatime.operation_executors_v3.metadata||excluded.metadata,
  updated_at=now();

insert into pentatime.operation_state_v2(operation_key)
values('factory_dispatch')
on conflict(operation_key) do nothing;

update pentatime.operation_registry_v2
set domain_key='ct:production-governance-write-lane',
    metadata=metadata||jsonb_build_object(
      'shared_factory_write_lane',true,
      'continuity_contract','v6',
      'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination'
    ),
    updated_at=now()
where operation_key in ('factory_continuity','factory_internal_generate','factory_surface_binding_sync');

do $do$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-software-factory-continuity-v5' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule('ct-software-factory-continuity-v5','0-58/2 * * * *',$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$);
  else
    perform cron.alter_job(v_jobid,schedule=>'0-58/2 * * * *',command=>$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$,active=>true);
  end if;

  select jobid into v_jobid from cron.job where jobname='ct-software-factory-dispatch-v3' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule('ct-software-factory-dispatch-v3','* * * * *',$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$);
  else
    perform cron.alter_job(v_jobid,schedule=>'* * * * *',command=>$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$,active=>true);
  end if;

  select jobid into v_jobid from cron.job where jobname='ct-factory-internal-openai-generate-v1' order by jobid desc limit 1;
  if v_jobid is null then
    perform cron.schedule('ct-factory-internal-openai-generate-v1','7,17,27,37,47,57 * * * *',$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$);
  else
    perform cron.alter_job(v_jobid,schedule=>'7,17,27,37,47,57 * * * *',command=>$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$,active=>true);
  end if;

  select jobid into v_jobid from cron.job where jobname='ct-software-factory-tick-v2' order by jobid desc limit 1;
  if v_jobid is not null then perform cron.alter_job(v_jobid,active=>false); end if;

  select jobid into v_jobid from cron.job where jobname='ct-factory-surface-binding-sync-v4' order by jobid desc limit 1;
  if v_jobid is not null then perform cron.alter_job(v_jobid,active=>false); end if;
end;
$do$;

insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
values
('ct-software-factory-continuity-v5','0-58/2 * * * *',$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$,true,'D1',
 jsonb_build_object('owner','PentaFactory/PentaTime','operation_key','factory_continuity','continuity_contract','v6','contention_domain','ct:production-governance-write-lane','direct_runtime_call_forbidden',true,'monotonic_generation',2026082911,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination')),
('ct-software-factory-dispatch-v3','* * * * *',$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$,true,'D1',
 jsonb_build_object('owner','PentaFactory/PentaTime','operation_key','factory_dispatch','continuity_contract','v6','contention_domain','ct:production-governance-write-lane','direct_runtime_call_forbidden',true,'monotonic_generation',2,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination')),
('ct-factory-internal-openai-generate-v1','7,17,27,37,47,57 * * * *',$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$,true,'D2',
 jsonb_build_object('owner','PentaFactory/PentaBuild/PentaTime','operation_key','factory_internal_generate','continuity_contract','v6','contention_domain','ct:production-governance-write-lane','recursive_factory_tick_removed',true,'monotonic_generation',2026082911,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination')),
('ct-software-factory-tick-v2','*/5 * * * *',$cmd$select public.ct_factory_tick();$cmd$,false,'D0',
 jsonb_build_object('owner','PentaFactory','retired_duplicate',true,'superseded_by','ct-software-factory-dispatch-v3','continuity_contract','v6','monotonic_generation',2026082911,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination')),
('ct-factory-surface-binding-sync-v4','12,27,42,57 * * * *',$cmd$select pentatime.execute_guarded_v3('factory_surface_binding_sync');$cmd$,false,'D0',
 jsonb_build_object('owner','PentaFactory/PentaWire/PentaTime','retired_duplicate_clock',true,'surface_sync_retained_inside','factory_continuity','continuity_contract','v6','monotonic_generation',2026082911,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination'))
on conflict(jobname) do update set
  expected_schedule=excluded.expected_schedule,
  expected_command=excluded.expected_command,
  auto_repair=excluded.auto_repair,
  risk_class=excluded.risk_class,
  metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,
  updated_at=now();

insert into penta_self.critical_cron_state_v2(
  jobname,desired_schedule,desired_command,desired_version,state_sha256,enabled,reconciliation_mode,authority_ref,evidence
)
select x.jobname,x.schedule,x.command,2,
       encode(extensions.digest(convert_to(jsonb_build_object('jobname',x.jobname,'schedule',x.schedule,'command',x.command,'desired_version',2)::text,'UTF8'),'sha256'),'hex'),
       true,'restore_missing_or_inactive','ct.penta.self.scheduler-permanence.v2',
       jsonb_build_object('continuity_contract','v6','forward_only',true,'D3_human_reserved',true,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination')
from (values
 ('ct-software-factory-continuity-v5'::text,'0-58/2 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$::text),
 ('ct-software-factory-dispatch-v3'::text,'* * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$::text)
) as x(jobname,schedule,command)
on conflict(jobname) do update set
  desired_schedule=excluded.desired_schedule,
  desired_command=excluded.desired_command,
  desired_version=greatest(penta_self.critical_cron_state_v2.desired_version,excluded.desired_version),
  state_sha256=excluded.state_sha256,
  enabled=true,
  reconciliation_mode=excluded.reconciliation_mode,
  authority_ref=excluded.authority_ref,
  evidence=penta_self.critical_cron_state_v2.evidence||excluded.evidence,
  updated_at=now();

insert into penta_self.permanent_cron_desired_state_v1(
  jobname,schedule,command,desired_active,enforcement_mode,verification_evidence,desired_sha256,verified_at,source_ref
)
select x.jobname,x.schedule,x.command,x.desired_active,x.enforcement_mode,
       jsonb_build_object('continuity_contract','v6','forward_only',true,'D3_human_reserved',true,'source_ref','migration:pentaself_factory_continuity_v6_deadlock_elimination'),
       encode(extensions.digest(convert_to(jsonb_build_object('jobname',x.jobname,'schedule',x.schedule,'command',x.command,'desired_active',x.desired_active)::text,'UTF8'),'sha256'),'hex'),
       now(),'migration:pentaself_factory_continuity_v6_deadlock_elimination'
from (values
 ('ct-software-factory-continuity-v5'::text,'0-58/2 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$::text,true,'exact'::text),
 ('ct-software-factory-dispatch-v3'::text,'* * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$::text,true,'exact'::text),
 ('ct-factory-internal-openai-generate-v1'::text,'7,17,27,37,47,57 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$::text,true,'exact'::text),
 ('ct-software-factory-tick-v2'::text,'*/5 * * * *'::text,$cmd$select public.ct_factory_tick();$cmd$::text,false,'observe'::text),
 ('ct-factory-surface-binding-sync-v4'::text,'12,27,42,57 * * * *'::text,$cmd$select pentatime.execute_guarded_v3('factory_surface_binding_sync');$cmd$::text,false,'observe'::text),
 ('ct-penta-self-permanent-repair-reconcile-v1'::text,'* * * * *'::text,$cmd$select penta_self.reconcile_permanent_repairs_v1();$cmd$::text,false,'observe'::text)
) as x(jobname,schedule,command,desired_active,enforcement_mode)
on conflict(jobname) do update set
  schedule=excluded.schedule,
  command=excluded.command,
  desired_active=excluded.desired_active,
  enforcement_mode=excluded.enforcement_mode,
  verification_evidence=penta_self.permanent_cron_desired_state_v1.verification_evidence||excluded.verification_evidence,
  desired_sha256=excluded.desired_sha256,
  verified_at=excluded.verified_at,
  source_ref=excluded.source_ref,
  updated_at=now();

-- Preserve the legacy reconciler as a safe compatibility surface. It may not write cron.job directly.
create or replace function penta_self.reconcile_permanent_repairs_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','cron','extensions','crm'
as $function$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  j record;
  v_repaired int := 0;
  v_observed int := 0;
  v_missing int := 0;
  v_drifted int := 0;
  v_event jsonb;
  v_hash text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  perform pg_advisory_xact_lock(hashtext('penta_self.reconcile_permanent_repairs_v1'));

  for r in select * from penta_self.permanent_cron_desired_state_v1 where desired_active=true order by jobname loop
    select * into j from cron.job where jobname=r.jobname order by jobid desc limit 1;
    if not found then
      v_missing := v_missing+1;
      perform cron.schedule(r.jobname,r.schedule,r.command);
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('cron:'||r.jobname,'cron_missing_recreated','active',jsonb_build_object('schedule',r.schedule,'command_sha256',encode(extensions.digest(r.command,'sha256'),'hex'),'desired_sha256',r.desired_sha256),'PentaSELF/PentaTime');
    elsif r.enforcement_mode='observe' then
      v_observed := v_observed+1;
    elsif j.active is distinct from true then
      perform cron.alter_job(j.jobid,active=>true);
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('cron:'||r.jobname,'cron_reactivated','active',jsonb_build_object('jobid',j.jobid,'schedule',j.schedule),'PentaSELF/PentaTime');
    elsif r.enforcement_mode='exact' and (j.schedule is distinct from r.schedule or j.command is distinct from r.command) then
      v_drifted := v_drifted+1;
      perform cron.alter_job(j.jobid,schedule=>r.schedule,command=>r.command,active=>true);
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('cron:'||r.jobname,'stale_cron_drift_repaired','active',jsonb_build_object('jobid',j.jobid,'prior_schedule',j.schedule,'desired_schedule',r.schedule,'prior_command_sha256',encode(extensions.digest(j.command,'sha256'),'hex'),'desired_command_sha256',encode(extensions.digest(r.command,'sha256'),'hex'),'stale_state_allowed_to_override',false),'PentaSELF/PentaTime');
    end if;
  end loop;

  if to_regclass('crm.penta_persona_execution_control_v1') is not null then
    update crm.penta_persona_execution_control_v1
       set active=true,automation_enabled=true,kill_switch=false,updated_at=now()
     where control_key='default' and certification_state='production'
       and (active is distinct from true or automation_enabled is distinct from true or kill_switch is distinct from false);
    if found then
      v_repaired := v_repaired+1;
      perform penta_self.record_permanent_repair_event_v1('control:penta-persona-execution-v1','verified_control_reasserted','production',jsonb_build_object('active',true,'automation_enabled',true,'kill_switch',false,'certification_required','production'),'PentaSELF/PentaAssure');
    end if;
  end if;

  v_event := jsonb_build_object('service','ct.penta.self.permanent-repair-fabric.v2','repaired',v_repaired,'missing',v_missing,'drifted',v_drifted,'observed_only',v_observed,'cron_mutation_api','cron.alter_job','direct_cron_table_write',false,'stale_snapshots_may_rollback',false,'automatic_rollback_allowed',false,'rollback_rule','newer independently verified failure plus explicit rollback handle only','observed_at',now());
  v_hash := encode(extensions.digest(v_event::text,'sha256'),'hex');
  return v_event || jsonb_build_object('evidence_sha256',v_hash);
end;
$function$;

-- PentaSELF recovery now re-enters factory work only through PentaTime and does not
-- label a contention deferral as a completed repair.
create or replace function penta_self.failed_job_recovery_v1(p_cycle_id uuid default gen_random_uuid())
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','integration_control','pentatime','public','cron'
as $function$
declare
  r record;
  v_result jsonb;
  v_recovered int:=0;
  v_failed int:=0;
  v_skipped int:=0;
  v_finding uuid;
  v_guarded boolean;
  v_guard_state text;
begin
  for r in
    select distinct on (j.jobid) j.jobid,j.jobname,j.active,d.status,d.start_time,d.return_message
    from penta_self.required_jobs_v1 q
    join cron.job j on j.jobname=q.jobname
    join cron.job_run_details d on d.jobid=j.jobid and d.start_time>now()-interval '30 minutes'
    where q.auto_repair
    order by j.jobid,d.start_time desc
  loop
    if r.status in('succeeded','running') then continue; end if;
    if exists(select 1 from penta_self.action_receipts_v1 a where a.action_key='recover_failed_required_job' and a.target_ref='cron:'||r.jobname and a.result_state='applied' and a.completed_at>=r.start_time) then continue; end if;

    insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence)
    values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'latest_required_job_failed',jsonb_build_object('failed_at',r.start_time,'return_message',left(coalesce(r.return_message,''),500),'jobid',r.jobid))
    returning finding_id into v_finding;

    begin
      v_result:=null;
      v_guarded:=false;
      case r.jobname
        when 'ct-phase3-self-discovery-v3' then v_result:=public.ct_phase3_self_discovery_tick_v3();
        when 'ct-penta-certify-v3' then v_result:=integration_control.penta_certify_cycle_v3(6);
        when 'ct-penta-provider-evidence-bridge-v1' then v_result:=integration_control.penta_certify_activate_control_evidence_v1();
        when 'ct-penta-build-quality-v1' then v_result:=integration_control.penta_build_quality_sweep_v1();
        when 'ct-penta-nurture-v1' then v_result:=public.penta_nurture_tick_v1();
        when 'ct-pentatime-reconcile-v1' then v_result:=pentatime.reconcile(true);
        when 'ct-pentaroute-autonomy-v3' then v_result:=integration_control.pentaroute_autonomy_cycle_v3();
        when 'ct-software-factory-continuity-v5' then v_result:=pentatime.execute_guarded_v3('factory_continuity'); v_guarded:=true;
        when 'ct-software-factory-dispatch-v3' then v_result:=pentatime.execute_guarded_v3('factory_dispatch'); v_guarded:=true;
        when 'thivebase_self_diagnostic_v1' then v_result:=public.thrivebase_safe_self_heal_run_v1();
        when 'ct-penta-self-v1' then v_result:=jsonb_build_object('state','current_cycle_proves_runtime_live','cycle_id',p_cycle_id);
        else v_result:=jsonb_build_object('state','no_allowlisted_recovery_handler');
      end case;

      v_guard_state:=upper(coalesce(v_result->>'state',''));
      if v_result->>'state'='no_allowlisted_recovery_handler' then
        update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('recovery_result',v_result) where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','recover_failed_required_job','cron:'||r.jobname,'skipped',true,'D1',jsonb_build_object('result',v_result));
        v_skipped:=v_skipped+1;
      elsif v_guarded and (v_guard_state like 'DEFERRED%' or v_guard_state='SKIPPED_LOCKED') then
        update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('recovery_result',v_result,'classification','bounded_contention_deferral_not_healed') where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','recover_failed_required_job','cron:'||r.jobname,'skipped',true,'D1',jsonb_build_object('result',v_result,'classification','bounded_contention_deferral_not_healed','original_failed_at',r.start_time));
        v_skipped:=v_skipped+1;
      elsif v_guarded and v_guard_state='FAILED' then
        update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('recovery_result',v_result,'classification','guarded_recovery_failed') where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','recover_failed_required_job','cron:'||r.jobname,'failed',true,'D1',jsonb_build_object('result',v_result,'classification','guarded_recovery_failed','original_failed_at',r.start_time));
        v_failed:=v_failed+1;
      else
        update penta_self.findings_v1 set state='healed',resolved_at=now(),evidence=evidence||jsonb_build_object('recovery_result',v_result,'guarded_by_pentatime',v_guarded) where finding_id=v_finding;
        insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
        values(p_cycle_id,v_finding,'self.recover','recover_failed_required_job','cron:'||r.jobname,'applied',true,'D1',jsonb_build_object('result',v_result,'original_failed_at',r.start_time,'guarded_by_pentatime',v_guarded));
        v_recovered:=v_recovered+1;
      end if;
    exception when others then
      update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('recovery_error',left(sqlerrm,300),'sqlstate',sqlstate) where finding_id=v_finding;
      insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
      values(p_cycle_id,v_finding,'self.recover','recover_failed_required_job','cron:'||r.jobname,'failed',true,'D1',jsonb_build_object('error',left(sqlerrm,300),'sqlstate',sqlstate,'original_failed_at',r.start_time));
      v_failed:=v_failed+1;
    end;
  end loop;

  return jsonb_build_object('service','ct.penta.self.failed-job-recovery.v2','recovered',v_recovered,'failed',v_failed,'skipped',v_skipped,'factory_recovery_path','pentatime.execute_guarded_v3','contention_deferral_is_not_healed',true,'D3_human_reserved',true,'at',now());
end;
$function$;

comment on function penta_self.failed_job_recovery_v1(uuid) is
'PentaSELF V2 semantics on the stable V1 entrypoint: factory recovery is PentaTime-guarded and contention deferrals are never mislabeled as healed.';

-- Installation receipt and DAIL lineage.
do $do$
declare
  v_cycle uuid:=gen_random_uuid();
  v_payload jsonb;
  v_sha text;
begin
  v_payload:=jsonb_build_object(
    'contract','ct.penta.factory-continuity.v6',
    'root_cause','overlapping unguarded factory mutation clocks produced PostgreSQL deadlocks',
    'canonical_domain','ct:production-governance-write-lane',
    'guarded_operations',jsonb_build_array('factory_continuity','factory_dispatch','factory_internal_generate'),
    'retired_duplicate_clocks',jsonb_build_array('ct-software-factory-tick-v2','ct-factory-surface-binding-sync-v4'),
    'pentaself_recovery_upgraded',true,
    'direct_cron_table_write_removed',true,
    'authority_class','D1',
    'D3_human_reserved',true,
    'provider_write',false,
    'credential_material',false,
    'installed_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into penta_self.action_receipts_v1(
    cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,before_sha256,after_sha256,evidence
  ) values (
    v_cycle,'self.recover','install_factory_continuity_v6','cron-family:ct-software-factory',
    'applied',true,'D1',null,v_sha,v_payload
  );
  perform chlom_runtime.append_dail_event(
    'pentaself.factory-continuity.v6.installed','self_healing','ct.penta.factory-continuity.v6',
    v_payload,'PentaSELF/PentaTime/PentaFactory/PentaNurture',null,'PentaSELF','3.0.0',v_sha,null,
    'founder-directive:2026-08-29:fix-upgrade-self-certify',null,'internal'
  );
end;
$do$;