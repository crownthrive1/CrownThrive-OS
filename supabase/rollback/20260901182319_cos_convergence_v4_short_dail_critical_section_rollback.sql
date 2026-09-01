-- Rollback for 20260901182319_cos_convergence_v4_short_dail_critical_section.sql.
-- Restores the prior scheduler command and removes only convergence v4.

do $schedule$
declare v_jobid bigint;
begin
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-convergence-v2';
  if v_jobid is null then
    raise exception 'ct-cos-v1-convergence-v2 cron job not found';
  end if;
  perform cron.alter_job(v_jobid,null,'select public.cos_v1_convergence_cycle_v3();',null,null,true);
end
$schedule$;

drop function if exists public.cos_v1_convergence_cycle_v4();
