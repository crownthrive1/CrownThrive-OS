-- COS V1 convergence v4: keep the global DAIL lock out of expensive/nested work.
-- DAIL-writing specialist functions remain on their own clocks/transactions.

create or replace function public.cos_v1_convergence_cycle_v4()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, public, penta_dnd, chlom_runtime, extensions
as $function$
declare
  v_started timestamptz := clock_timestamp();
  v_repo jsonb := '{}'::jsonb;
  v_scheduler jsonb := '{}'::jsonb;
  v_site jsonb := '{}'::jsonb;
  v_census jsonb := '{}'::jsonb;
  v_extended jsonb := '{}'::jsonb;
  v_plans jsonb := '{}'::jsonb;
  v_alias_plans jsonb := '{}'::jsonb;
  v_holds jsonb := '{}'::jsonb;
  v_wire_lifecycle jsonb := '{}'::jsonb;
  v_continuity jsonb := '{}'::jsonb;
  v_status jsonb := '{}'::jsonb;
  v_penta jsonb := '{}'::jsonb;
  v_chlom jsonb := '{}'::jsonb;
  v_dnd jsonb := '{}'::jsonb;
  v_event jsonb;
  v_delegated jsonb := '{}'::jsonb;
  v_step_failures jsonb := '[]'::jsonb;
  v_mode text;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:cos:v1:convergence-cycle:v4',0)) then
    return jsonb_build_object('ok',true,'state','skipped_concurrent_run','observed_at',clock_timestamp());
  end if;

  v_mode := case
    when extract(isodow from clock_timestamp() at time zone 'America/New_York') in (6,7)
      or (clock_timestamp() at time zone 'America/New_York')::time not between time '06:00' and time '21:00'
    then 'plan_and_prepare' else 'execute' end;

  -- These steps do not call append_dail_event. They may perform bounded local
  -- reconciliation but cannot acquire the global DAIL serialization lock.
  begin v_repo := integration_control.cos_repository_census_refresh_v1();
  exception when others then v_repo:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('repository_census'); end;
  begin v_scheduler := integration_control.cos_scheduler_census_refresh_v1();
  exception when others then v_scheduler:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('scheduler_census'); end;
  begin v_site := integration_control.cos_site_truth_refresh_v1();
  exception when others then v_site:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('site_truth'); end;
  begin v_census := integration_control.cos_census_refresh_v2();
  exception when others then v_census:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('census_v2'); end;
  begin v_extended := integration_control.cos_census_extended_refresh_v2();
  exception when others then v_extended:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('census_extended'); end;
  begin v_plans := integration_control.cos_plan_noncurrent_state_v1();
  exception when others then v_plans:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('planner_routes'); end;
  begin v_alias_plans := integration_control.cos_plan_identity_alias_gaps_v1();
  exception when others then v_alias_plans:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('identity_alias_routes'); end;
  begin v_holds := integration_control.cos_hold_census_refresh_v2();
  exception when others then v_holds:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('hold_census'); end;
  begin v_wire_lifecycle := integration_control.penta_wire_reconcile_tool_lifecycle_v2();
  exception when others then v_wire_lifecycle:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('wire_lifecycle'); end;
  begin v_continuity := public.ct_factory_reconcile_continuity();
  exception when others then v_continuity:=jsonb_build_object('ok',false,'error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('factory_continuity'); end;

  -- Read-only current-state observations. No certification or provider mutation.
  begin v_status := public.cos_v1_status_v3();
  exception when others then v_status:=jsonb_build_object('state','unknown','error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('cos_status'); end;
  begin v_penta := public.penta_convergence_status_v1();
  exception when others then v_penta:=jsonb_build_object('state','unknown','error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('penta_status'); end;
  begin v_chlom := integration_control.chlom_mesh_status_v1();
  exception when others then v_chlom:=jsonb_build_object('state','unknown','error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('chlom_status'); end;
  begin v_dnd := penta_dnd.scope_status_v1();
  exception when others then v_dnd:=jsonb_build_object('state','unknown','error_class',sqlstate); v_step_failures:=v_step_failures||jsonb_build_array('dnd_status'); end;

  -- Every nested function known to append DAIL is delegated to an independent
  -- transaction/clock so its xact-scoped DAIL advisory lock ends with that
  -- specialist call rather than being retained across this convergence cycle.
  v_delegated := jsonb_build_object(
    'factory_fleet',jsonb_build_object('job','ct-penta-factory-fleet-census-v3','active',exists(select 1 from cron.job where jobname='ct-penta-factory-fleet-census-v3' and active)),
    'adapter_convergence',jsonb_build_object('job','ct-penta-adapter-convergence-v2','active',exists(select 1 from cron.job where jobname='ct-penta-adapter-convergence-v2' and active)),
    'penta_convergence_certification',jsonb_build_object('job','ct-penta-convergence-certification-v1','active',exists(select 1 from cron.job where jobname='ct-penta-convergence-certification-v1' and active)),
    'pentaofac',jsonb_build_object('job','pentaofac-consolidated-v1','active',exists(select 1 from cron.job where jobname='pentaofac-consolidated-v1' and active)),
    'penta_self',jsonb_build_object('job','ct-penta-self-v1','active',exists(select 1 from cron.job where jobname='ct-penta-self-v1' and active)),
    'penta_treasury',jsonb_build_object('job','penta_os20_local_midnight_treasury_issue','active',exists(select 1 from cron.job where jobname='penta_os20_local_midnight_treasury_issue' and active)),
    'wire_scan_and_heal','observed_by_cos_status_and_specialist_pentawire_lanes',
    'duplicate_specialist_execution_created',false
  );

  -- FINAL DAIL SERIALIZATION SECTION. Nothing expensive follows this append.
  v_event := chlom_runtime.append_dail_event(
    'cos.v1.convergence_cycle.v4','institutional_convergence','ct.cos.release.1.0.0',
    jsonb_build_object(
      'cycle_mode',v_mode,
      'started_at',v_started,
      'completed_at',clock_timestamp(),
      'repository_census',v_repo,
      'scheduler_census',v_scheduler,
      'site_truth',v_site,
      'census_v2',v_census,
      'census_extended',v_extended,
      'planner_routes',v_plans,
      'identity_alias_routes',v_alias_plans,
      'hold_census',v_holds,
      'wire_lifecycle',v_wire_lifecycle,
      'factory_continuity',v_continuity,
      'cos_status_state',v_status->>'state',
      'penta_state',v_penta->>'state',
      'chlom_state',coalesce(v_chlom->>'state',v_chlom->>'status'),
      'dnd_state',coalesce(v_dnd->>'state',v_dnd->>'status'),
      'delegated_specialist_clocks',v_delegated,
      'step_failures',v_step_failures,
      'dail_critical_section','final_append_only',
      'history_preserved',true,
      'authority_expansion',false,
      'provider_write_created',false,
      'money_movement',false,
      'D3_execution',false
    ),
    'COS/PentaCensus/PentaTruth/PentaPlanner/PentaWire/PentaTime',
    null,'PentaCertify','4.0.0','ctcorr:cos-v1-convergence-cycle-v4',null,
    'D2_AUTONOMOUS',null,'internal'
  );

  return jsonb_build_object(
    'ok',jsonb_array_length(v_step_failures)=0 and v_status->>'state'='certifiable',
    'state',case when jsonb_array_length(v_step_failures)=0 then coalesce(v_status->>'state','unknown') else 'partial' end,
    'cycle_mode',v_mode,
    'started_at',v_started,
    'completed_at',clock_timestamp(),
    'step_failures',v_step_failures,
    'delegated_specialist_clocks',v_delegated,
    'status',v_status,
    'penta_status',v_penta,
    'chlom_status',v_chlom,
    'dnd_status',v_dnd,
    'dail',v_event
  );
end
$function$;

comment on function public.cos_v1_convergence_cycle_v4()
is 'COS V1 convergence orchestrator with expensive/non-DAIL work before one final DAIL append. DAIL-writing specialist functions run on independent clocks to prevent transaction-scoped global DAIL lock amplification.';

revoke all on function public.cos_v1_convergence_cycle_v4() from public;
grant execute on function public.cos_v1_convergence_cycle_v4() to service_role;

do $schedule$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-convergence-v2';
  if v_jobid is null then
    raise exception 'ct-cos-v1-convergence-v2 cron job not found';
  end if;
  perform cron.alter_job(v_jobid,null,'select public.cos_v1_convergence_cycle_v4();',null,null,true);
end
$schedule$;
