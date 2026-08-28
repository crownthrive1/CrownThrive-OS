-- CrownThrive OS Phase 3.5 convergence hardening
-- 1) Prevent PentaSELF aggregate health from masking failed/degraded substeps.
-- 2) Serialize commercial release materialization before relation-level writes.
-- No authority expansion, D3 bypass, credential creation, or money movement.

create or replace function penta_self.tick_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'penta_self', 'penta_runtime', 'integration_control', 'public'
as $function$
declare
  v_cycle uuid:=gen_random_uuid();
  v_started timestamptz:=clock_timestamp();
  v_scheduler jsonb;
  v_job_recovery jsonb;
  v_topology jsonb;
  v_discovery jsonb;
  v_legacy_heal jsonb;
  v_evidence jsonb;
  v_build jsonb;
  v_nurture jsonb;
  v_route jsonb;
  v_secure jsonb;
  v_health jsonb;
  v_actions jsonb;
  v_state text:='healthy';
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.self.v1',0)) then
    return jsonb_build_object('service','ct.penta.self.v1','state','SKIPPED_LOCKED','phase',3,'production',true,'at',now());
  end if;

  insert into penta_self.cycle_receipts_v1(cycle_id,state,started_at,summary,evidence)
  values(v_cycle,'running',v_started,'{}','{}');

  begin v_scheduler:=penta_self.scheduler_reconcile_v1(v_cycle);
  exception when others then v_scheduler:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin v_job_recovery:=penta_self.failed_job_recovery_v1(v_cycle);
  exception when others then v_job_recovery:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin v_topology:=penta_self.fabric_mesh_reconcile_v1(v_cycle);
  exception when others then v_topology:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_discovery:=public.ct_phase3_self_discovery_tick_v3();
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.discovery','phase3_self_discovery','phase3:provider-lanes','applied',true,'D1',v_discovery);
  exception when others then v_discovery:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_legacy_heal:=public.thrivebase_safe_self_heal_run_v1();
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.heal','bounded_legacy_self_heal','ThriveBase','applied',true,'D1',v_legacy_heal);
  exception when others then v_legacy_heal:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_evidence:=integration_control.penta_certify_activate_control_evidence_v1();
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.reconcile','activate_provider_evidence','PentaCertify','applied',true,'D2',v_evidence);
  exception when others then v_evidence:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_build:=integration_control.penta_build_quality_sweep_v1();
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.repair','penta_build_quality_sweep','PentaBuild','delegated',true,'D2',v_build);
  exception when others then v_build:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_nurture:=public.penta_nurture_tick_v1();
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.nurture','provider_runtime_nurture','PentaNurture','applied',true,'D2',v_nurture);
  exception when others then v_nurture:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_route:=integration_control.pentaroute_autonomy_cycle_v3();
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.route','route_autonomy_cycle','PentaRoute','delegated',true,'D1',v_route);
  exception when others then v_route:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  begin
    v_secure:=penta_runtime.pentasecure_cycle_v1(false);
    insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence)
    values(v_cycle,'self.secure','security_cycle','PentaSecure','delegated',true,'D2',v_secure);
  exception when others then v_secure:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;

  v_actions:=jsonb_build_object(
    'scheduler',v_scheduler,
    'failed_job_recovery',v_job_recovery,
    'topology',v_topology,
    'discovery',v_discovery,
    'legacy_heal',v_legacy_heal,
    'provider_evidence',v_evidence,
    'build_quality',v_build,
    'nurture',v_nurture,
    'route',v_route,
    'secure',v_secure
  );

  v_health:=penta_self.health_snapshot_v1();

  if coalesce((v_health->>'scheduler_gaps')::int,0)>0
     or coalesce((v_health->>'unrecovered_required_job_failures_30m')::int,0)>0
     or coalesce((v_health->>'failed_certification_tasks')::int,0)>0
     or coalesce(v_health->>'fabric_state','')<>'production'
     or coalesce(v_health->>'mesh_state','')<>'production' then
    v_state:='degraded';
  end if;

  if exists (
    select 1
    from jsonb_each(v_actions) as a(action_key,payload)
    where lower(coalesce(payload->>'state','')) in ('failed','failure','error')
       or lower(coalesce(payload->>'result_state','')) in ('failed','failure','error')
       or nullif(payload->>'error','') is not null
  ) then
    v_state:='failed';
  elsif exists (
    select 1
    from jsonb_each(v_actions) as a(action_key,payload)
    where lower(coalesce(payload->>'state','')) in ('degraded','blocked','hold','partial')
       or lower(coalesce(payload->>'result_state','')) in ('degraded','blocked','hold','partial')
  ) and v_state='healthy' then
    v_state:='degraded';
  end if;

  update penta_self.cycle_receipts_v1
  set state=v_state,
      completed_at=clock_timestamp(),
      summary=jsonb_build_object('state',v_state,'health',v_health),
      evidence=v_actions || jsonb_build_object('authority_manufacture',false,'d3_human_reserved',true,'aggregate_fail_closed',true)
  where cycle_id=v_cycle;

  update public.penta_system_registry
  set last_verified_at=now(),
      updated_at=now(),
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'last_self_cycle_id',v_cycle,
        'last_self_cycle_state',v_state,
        'last_self_cycle_at',now(),
        'aggregate_fail_closed',true
      )
  where system_key in('penta.fabrics','penta.self','penta.meshes');

  return jsonb_build_object(
    'service','ct.penta.self.v1',
    'phase',3,
    'production',true,
    'cycle_id',v_cycle,
    'state',upper(v_state),
    'health',v_health,
    'actions',v_actions,
    'aggregate_fail_closed',true,
    'authority_manufacture',false,
    'd3_human_reserved',true,
    'at',now()
  );
exception when others then
  update penta_self.cycle_receipts_v1
  set state='failed',completed_at=clock_timestamp(),summary=jsonb_build_object('error',left(sqlerrm,300)),evidence=jsonb_build_object('sqlstate',sqlstate,'aggregate_fail_closed',true)
  where cycle_id=v_cycle;
  return jsonb_build_object('service','ct.penta.self.v1','phase',3,'production',true,'cycle_id',v_cycle,'state','FAILED','error',left(sqlerrm,300),'aggregate_fail_closed',true,'authority_manufacture',false,'d3_human_reserved',true,'at',now());
end
$function$;

create or replace function integration_control.commercial_release_packager_serialized_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'integration_control', 'developer_commerce', 'public'
as $function$
declare
  v_result jsonb;
  v_started timestamptz:=clock_timestamp();
begin
  -- One transaction-scoped lane for the release-policy foreign-key/read-write hotspot.
  perform pg_advisory_xact_lock(hashtextextended('ct:production-governance-write-lane',0));
  lock table integration_control.release_policies in share row exclusive mode;

  v_result:=integration_control.materialize_commercial_credit_release_packages_current_v3(
    'current',
    'ct.agent.commercial-release-packager'
  );

  return jsonb_build_object(
    'state','completed',
    'serialization','advisory_xact_plus_release_policies_table_lock',
    'started_at',v_started,
    'completed_at',clock_timestamp(),
    'result',v_result,
    'authority_effect','none_beyond_existing_authority'
  );
end
$function$;

revoke all on function integration_control.commercial_release_packager_serialized_v1() from public;
grant execute on function integration_control.commercial_release_packager_serialized_v1() to service_role;

-- Replace the current hourly command by stable job name, never by a generated job id.
do $block$
declare
  v_job_id bigint;
begin
  select jobid into v_job_id
  from cron.job
  where jobname='crownthrive_commercial_release_packager_hourly';

  if v_job_id is null then
    raise exception 'COMMERCIAL_RELEASE_PACKAGER_CRON_NOT_FOUND';
  end if;

  perform cron.alter_job(
    job_id := v_job_id,
    command := 'select integration_control.commercial_release_packager_serialized_v1();'
  );
end
$block$;
