-- COS V1 convergence v5: decouple heavy projection refresh from the top-level
-- convergence/status transaction. The convergence cycle is observation-first and
-- performs one final DAIL append. Projection refreshes run on independent cron
-- transactions so they cannot amplify the global DAIL xact lock.

create or replace function public.cos_v1_convergence_cycle_v5()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control, public, penta_dnd, chlom_runtime, extensions
as $function$
declare
  v_started timestamptz := clock_timestamp();
  v_status jsonb := '{}'::jsonb;
  v_penta jsonb := '{}'::jsonb;
  v_chlom jsonb := '{}'::jsonb;
  v_dnd jsonb := '{}'::jsonb;
  v_event jsonb;
  v_clocks jsonb := '{}'::jsonb;
  v_failures jsonb := '[]'::jsonb;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:cos:v1:convergence-cycle:v5',0)) then
    return jsonb_build_object('ok',true,'state','skipped_concurrent_run','observed_at',clock_timestamp());
  end if;

  begin v_status := public.cos_v1_status_v3(); exception when others then v_status:=jsonb_build_object('state','unknown','error_class',sqlstate); v_failures:=v_failures||jsonb_build_array('cos_status'); end;
  begin v_penta := public.penta_convergence_status_v1(); exception when others then v_penta:=jsonb_build_object('state','unknown','error_class',sqlstate); v_failures:=v_failures||jsonb_build_array('penta_status'); end;
  begin v_chlom := integration_control.chlom_mesh_status_v1(); exception when others then v_chlom:=jsonb_build_object('state','unknown','error_class',sqlstate); v_failures:=v_failures||jsonb_build_array('chlom_status'); end;
  begin v_dnd := penta_dnd.scope_status_v1(); exception when others then v_dnd:=jsonb_build_object('state','unknown','error_class',sqlstate); v_failures:=v_failures||jsonb_build_array('dnd_status'); end;

  v_clocks := jsonb_build_object(
    'census_refresh',jsonb_build_object('job','ct-cos-v1-census-refresh-v2','active',exists(select 1 from cron.job where jobname='ct-cos-v1-census-refresh-v2' and active)),
    'census_extended',jsonb_build_object('job','ct-cos-v1-census-extended-v2','active',exists(select 1 from cron.job where jobname='ct-cos-v1-census-extended-v2' and active)),
    'planning_projection',jsonb_build_object('job','ct-cos-v1-planning-projection-v2','active',exists(select 1 from cron.job where jobname='ct-cos-v1-planning-projection-v2' and active)),
    'factory_fleet',jsonb_build_object('job','ct-penta-factory-fleet-census-v3','active',exists(select 1 from cron.job where jobname='ct-penta-factory-fleet-census-v3' and active)),
    'adapter_convergence',jsonb_build_object('job','ct-penta-adapter-convergence-v2','active',exists(select 1 from cron.job where jobname='ct-penta-adapter-convergence-v2' and active)),
    'penta_convergence_certification',jsonb_build_object('job','ct-penta-convergence-certification-v1','active',exists(select 1 from cron.job where jobname='ct-penta-convergence-certification-v1' and active)),
    'pentaofac',jsonb_build_object('job','pentaofac-consolidated-v1','active',exists(select 1 from cron.job where jobname='pentaofac-consolidated-v1' and active)),
    'penta_self',jsonb_build_object('job','ct-penta-self-v1','active',exists(select 1 from cron.job where jobname='ct-penta-self-v1' and active)),
    'duplicate_specialist_execution_created',false
  );

  v_event := chlom_runtime.append_dail_event(
    'cos.v1.convergence_cycle.v5','institutional_convergence','ct.cos.release.1.0.0',
    jsonb_build_object('started_at',v_started,'completed_at',clock_timestamp(),'cos_status_state',v_status->>'state','penta_state',v_penta->>'state','chlom_state',coalesce(v_chlom->>'state',v_chlom->>'status'),'dnd_state',coalesce(v_dnd->>'state',v_dnd->>'status'),'projection_and_specialist_clocks',v_clocks,'step_failures',v_failures,'dail_critical_section','final_append_only','heavy_projection_in_outer_transaction',false,'history_preserved',true,'authority_expansion',false,'provider_write_created',false,'money_movement',false,'D3_execution',false),
    'COS/PentaContext/PentaCensus/PentaTruth/PentaTime',null,'PentaCertify','5.0.0','ctcorr:cos-v1-convergence-cycle-v5',null,'D2_AUTONOMOUS',null,'internal'
  );

  return jsonb_build_object('ok',jsonb_array_length(v_failures)=0 and v_status->>'state'='certifiable','state',case when jsonb_array_length(v_failures)=0 then coalesce(v_status->>'state','unknown') else 'partial' end,'started_at',v_started,'completed_at',clock_timestamp(),'step_failures',v_failures,'projection_and_specialist_clocks',v_clocks,'status',v_status,'penta_status',v_penta,'chlom_status',v_chlom,'dnd_status',v_dnd,'dail',v_event);
end
$function$;

comment on function public.cos_v1_convergence_cycle_v5()
is 'Observation-first COS V1 convergence status cycle. Heavy projection refresh and DAIL-writing specialist work execute on independent cron transactions; this function performs one terminal DAIL append.';
revoke all on function public.cos_v1_convergence_cycle_v5() from public;
grant execute on function public.cos_v1_convergence_cycle_v5() to service_role;

do $schedule$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-convergence-v2';
  if v_jobid is null then raise exception 'ct-cos-v1-convergence-v2 cron job not found'; end if;
  perform cron.alter_job(v_jobid,null,'select public.cos_v1_convergence_cycle_v5();',null,null,true);
  if exists(select 1 from cron.job where jobname='ct-cos-v1-census-refresh-v2') then select jobid into v_jobid from cron.job where jobname='ct-cos-v1-census-refresh-v2'; perform cron.alter_job(v_jobid,'2,17,32,47 * * * *','select integration_control.cos_repository_census_refresh_v1(); select integration_control.cos_scheduler_census_refresh_v1(); select integration_control.cos_site_truth_refresh_v1(); select integration_control.cos_census_refresh_v2();',null,null,true); else perform cron.schedule('ct-cos-v1-census-refresh-v2','2,17,32,47 * * * *','select integration_control.cos_repository_census_refresh_v1(); select integration_control.cos_scheduler_census_refresh_v1(); select integration_control.cos_site_truth_refresh_v1(); select integration_control.cos_census_refresh_v2();'); end if;
  if exists(select 1 from cron.job where jobname='ct-cos-v1-census-extended-v2') then select jobid into v_jobid from cron.job where jobname='ct-cos-v1-census-extended-v2'; perform cron.alter_job(v_jobid,'6,21,36,51 * * * *','select integration_control.cos_census_extended_refresh_v2();',null,null,true); else perform cron.schedule('ct-cos-v1-census-extended-v2','6,21,36,51 * * * *','select integration_control.cos_census_extended_refresh_v2();'); end if;
  if exists(select 1 from cron.job where jobname='ct-cos-v1-planning-projection-v2') then select jobid into v_jobid from cron.job where jobname='ct-cos-v1-planning-projection-v2'; perform cron.alter_job(v_jobid,'11,26,41,56 * * * *','select integration_control.cos_plan_noncurrent_state_v1(); select integration_control.cos_plan_identity_alias_gaps_v1(); select integration_control.cos_hold_census_refresh_v2(); select integration_control.penta_wire_reconcile_tool_lifecycle_v2(); select public.ct_factory_reconcile_continuity();',null,null,true); else perform cron.schedule('ct-cos-v1-planning-projection-v2','11,26,41,56 * * * *','select integration_control.cos_plan_noncurrent_state_v1(); select integration_control.cos_plan_identity_alias_gaps_v1(); select integration_control.cos_hold_census_refresh_v2(); select integration_control.penta_wire_reconcile_tool_lifecycle_v2(); select public.ct_factory_reconcile_continuity();'); end if;
end
$schedule$;