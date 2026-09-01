-- Guarded rollback for 20260901182711_cos_convergence_v5_decoupled_projection_clocks.sql.
-- This is a historical compatibility rollback. Later scheduler-authority and
-- singleton-clock migrations supersede the scheduler topology and must be
-- rolled back first. Candidate/DAIL/history rows are never deleted.

do $rollback$
declare v_jobid bigint;
begin
  if exists(select 1 from integration_control.scheduler_desired_jobs_v2 where jobname='ct-cos-v1-convergence-v2' and generation>=2026090118) then
    raise exception 'later_scheduler_authority_present; rollback successor topology first';
  end if;
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-convergence-v2';
  if v_jobid is null then raise exception 'canonical_cos_convergence_job_missing'; end if;
  if exists(select 1 from cron.job where jobid=v_jobid and command='select public.cos_v1_convergence_cycle_v5();') then
    perform cron.alter_job(v_jobid,null,'select public.cos_v1_convergence_cycle_v4();',null,null,true);
  end if;
  if exists(select 1 from cron.job where command='select public.cos_v1_convergence_cycle_v5();') then
    raise exception 'v5_still_referenced_by_scheduler';
  end if;
  drop function if exists public.cos_v1_convergence_cycle_v5();
end
$rollback$;