-- Keep provider evidence activation and build-quality reconciliation autonomous.
do $$
declare v_job bigint;
begin
  if to_regclass('cron.job') is null then return; end if;
  select jobid into v_job from cron.job where jobname='ct-penta-provider-evidence-bridge-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule('ct-penta-provider-evidence-bridge-v1','*/2 * * * *','select integration_control.penta_certify_activate_control_evidence_v1();');

  v_job:=null;
  select jobid into v_job from cron.job where jobname='ct-penta-build-quality-v1' limit 1;
  if v_job is not null then perform cron.unschedule(v_job); end if;
  perform cron.schedule('ct-penta-build-quality-v1','*/5 * * * *','select integration_control.penta_build_quality_sweep_v1();');
end $$;
