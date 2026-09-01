-- COS V1 projection transaction split.
-- Each projection/refresher function gets its own pg_cron transaction. This
-- prevents a DAIL/xact lock acquired by one projection from being retained while
-- later heavy projections execute in the same multi-statement cron command.

do $split$
declare
  v_generation bigint := 2026090119;
  v_jobid bigint;
  v_count integer;
begin
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-census-refresh-v2' and active and schedule='2,17,32,47 * * * *' and command='select integration_control.cos_repository_census_refresh_v1(); select integration_control.cos_scheduler_census_refresh_v1(); select integration_control.cos_site_truth_refresh_v1(); select integration_control.cos_census_refresh_v2();') then raise exception 'census_group_prestate_changed'; end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-census-extended-v2' and active and schedule='6,21,36,51 * * * *' and command='select integration_control.cos_census_extended_refresh_v2();') then raise exception 'extended_prestate_changed'; end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-planning-projection-v2' and active and schedule='11,26,41,56 * * * *' and command='select integration_control.cos_plan_noncurrent_state_v1(); select integration_control.cos_plan_identity_alias_gaps_v1(); select integration_control.cos_hold_census_refresh_v2(); select integration_control.penta_wire_reconcile_tool_lifecycle_v2(); select public.ct_factory_reconcile_continuity();') then raise exception 'planning_group_prestate_changed'; end if;

  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-census-refresh-v2','0,20,40 * * * *','select integration_control.cos_repository_census_refresh_v1();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','repository_census','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-census-scheduler-v1','1,21,41 * * * *','select integration_control.cos_scheduler_census_refresh_v1();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','scheduler_census','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-site-truth-v1','2,22,42 * * * *','select integration_control.cos_site_truth_refresh_v1();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','site_truth','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-census-core-v2','3,23,43 * * * *','select integration_control.cos_census_refresh_v2();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','census_core','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-census-extended-v2','4,24,44 * * * *','select integration_control.cos_census_extended_refresh_v2();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','census_extended','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-planning-projection-v2','5,25,45 * * * *','select integration_control.cos_plan_noncurrent_state_v1();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','plan_noncurrent','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-identity-alias-plan-v1','6,26,46 * * * *','select integration_control.cos_plan_identity_alias_gaps_v1();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','identity_alias_plan','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-hold-census-v2','7,27,47 * * * *','select integration_control.cos_hold_census_refresh_v2();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','hold_census','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-wire-lifecycle-v2','8,28,48 * * * *','select integration_control.penta_wire_reconcile_tool_lifecycle_v2();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','wire_lifecycle','transaction_scope','singleton','authority_created',false));
  perform integration_control.scheduler_desired_job_upsert_v2('ct-cos-v1-factory-continuity-v1','10,30,50 * * * *','select public.ct_factory_reconcile_continuity();',v_generation,'ct.cos.v1.projection-clocks.singleton.v1',jsonb_build_object('cos_projection_role','factory_continuity','transaction_scope','singleton','authority_created',false));

  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-census-refresh-v2'; perform cron.alter_job(v_jobid,'0,20,40 * * * *','select integration_control.cos_repository_census_refresh_v1();',null,null,true);
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-census-extended-v2'; perform cron.alter_job(v_jobid,'4,24,44 * * * *','select integration_control.cos_census_extended_refresh_v2();',null,null,true);
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-planning-projection-v2'; perform cron.alter_job(v_jobid,'5,25,45 * * * *','select integration_control.cos_plan_noncurrent_state_v1();',null,null,true);

  if not exists(select 1 from cron.job where jobname='ct-cos-v1-census-scheduler-v1') then perform cron.schedule('ct-cos-v1-census-scheduler-v1','1,21,41 * * * *','select integration_control.cos_scheduler_census_refresh_v1();'); end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-site-truth-v1') then perform cron.schedule('ct-cos-v1-site-truth-v1','2,22,42 * * * *','select integration_control.cos_site_truth_refresh_v1();'); end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-census-core-v2') then perform cron.schedule('ct-cos-v1-census-core-v2','3,23,43 * * * *','select integration_control.cos_census_refresh_v2();'); end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-identity-alias-plan-v1') then perform cron.schedule('ct-cos-v1-identity-alias-plan-v1','6,26,46 * * * *','select integration_control.cos_plan_identity_alias_gaps_v1();'); end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-hold-census-v2') then perform cron.schedule('ct-cos-v1-hold-census-v2','7,27,47 * * * *','select integration_control.cos_hold_census_refresh_v2();'); end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-wire-lifecycle-v2') then perform cron.schedule('ct-cos-v1-wire-lifecycle-v2','8,28,48 * * * *','select integration_control.penta_wire_reconcile_tool_lifecycle_v2();'); end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-factory-continuity-v1') then perform cron.schedule('ct-cos-v1-factory-continuity-v1','10,30,50 * * * *','select public.ct_factory_reconcile_continuity();'); end if;

  select count(*) into v_count from cron.job where active and jobname in ('ct-cos-v1-census-refresh-v2','ct-cos-v1-census-scheduler-v1','ct-cos-v1-site-truth-v1','ct-cos-v1-census-core-v2','ct-cos-v1-census-extended-v2','ct-cos-v1-planning-projection-v2','ct-cos-v1-identity-alias-plan-v1','ct-cos-v1-hold-census-v2','ct-cos-v1-wire-lifecycle-v2','ct-cos-v1-factory-continuity-v1');
  if v_count <> 10 then raise exception 'singleton_projection_job_count_mismatch:%',v_count; end if;
  if exists(select 1 from cron.job where jobname in ('ct-cos-v1-census-refresh-v2','ct-cos-v1-planning-projection-v2') and command like '%; select %') then raise exception 'multi_statement_projection_clock_remains'; end if;
end
$split$;