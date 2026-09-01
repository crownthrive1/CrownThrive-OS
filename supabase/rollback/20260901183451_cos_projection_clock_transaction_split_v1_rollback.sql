-- Forward rollback for 20260901183451_cos_projection_clock_transaction_split_v1.sql.
-- Preserves desired-state history by advancing generation; no evidence rows are deleted.

do $rollback$
declare
  v_generation bigint := 2026090121;
  v_jobid bigint;
  v_name text;
begin
  if exists(select 1 from integration_control.scheduler_desired_jobs_v2 where jobname in ('ct-cos-v1-census-refresh-v2','ct-cos-v1-census-extended-v2','ct-cos-v1-planning-projection-v2') and generation<>2026090119) then raise exception 'projection_desired_prestate_changed'; end if;

  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-census-refresh-v2','2,17,32,47 * * * *','select integration_control.cos_repository_census_refresh_v1(); select integration_control.cos_scheduler_census_refresh_v1(); select integration_control.cos_site_truth_refresh_v1(); select integration_control.cos_census_refresh_v2();',v_generation,'ct.cos.v1.projection-clocks.rollback.v1',jsonb_build_object('rollback_of_generation',2026090119,'authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-census-extended-v2','6,21,36,51 * * * *','select integration_control.cos_census_extended_refresh_v2();',v_generation,'ct.cos.v1.projection-clocks.rollback.v1',jsonb_build_object('rollback_of_generation',2026090119,'authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-planning-projection-v2','11,26,41,56 * * * *','select integration_control.cos_plan_noncurrent_state_v1(); select integration_control.cos_plan_identity_alias_gaps_v1(); select integration_control.cos_hold_census_refresh_v2(); select integration_control.penta_wire_reconcile_tool_lifecycle_v2(); select public.ct_factory_reconcile_continuity();',v_generation,'ct.cos.v1.projection-clocks.rollback.v1',jsonb_build_object('rollback_of_generation',2026090119,'authority_created',false));

  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-census-refresh-v2'; perform cron.alter_job(v_jobid,'2,17,32,47 * * * *','select integration_control.cos_repository_census_refresh_v1(); select integration_control.cos_scheduler_census_refresh_v1(); select integration_control.cos_site_truth_refresh_v1(); select integration_control.cos_census_refresh_v2();',null,null,true);
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-census-extended-v2'; perform cron.alter_job(v_jobid,'6,21,36,51 * * * *','select integration_control.cos_census_extended_refresh_v2();',null,null,true);
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-planning-projection-v2'; perform cron.alter_job(v_jobid,'11,26,41,56 * * * *','select integration_control.cos_plan_noncurrent_state_v1(); select integration_control.cos_plan_identity_alias_gaps_v1(); select integration_control.cos_hold_census_refresh_v2(); select integration_control.penta_wire_reconcile_tool_lifecycle_v2(); select public.ct_factory_reconcile_continuity();',null,null,true);

  foreach v_name in array array['ct-cos-v1-census-scheduler-v1','ct-cos-v1-site-truth-v1','ct-cos-v1-census-core-v2','ct-cos-v1-identity-alias-plan-v1','ct-cos-v1-hold-census-v2','ct-cos-v1-wire-lifecycle-v2','ct-cos-v1-factory-continuity-v1'] loop
    if exists(select 1 from cron.job where jobname=v_name) then
      select jobid into v_jobid from cron.job where jobname=v_name;
      perform cron.unschedule(v_jobid);
    end if;
    update integration_control.scheduler_desired_jobs_v2 set active=false,generation=v_generation,source_ref='ct.cos.v1.projection-clocks.rollback.v1',metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('rollback_of_generation',2026090119,'authority_created',false),updated_at=clock_timestamp() where jobname=v_name and generation=2026090119;
  end loop;
end
$rollback$;