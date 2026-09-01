-- Forward rollback for 20260901183154_cos_v1_convergence_v5_scheduler_authority.sql.
-- Preserve monotonic scheduler generations and append-only evidence.

do $rollback$
declare
  v_jobid bigint;
  v_generation bigint := 2026090120;
  v_schedule text := '9,19,29,39,49,59 * * * *';
  v_command text := 'select public.cos_v1_convergence_cycle_v4();';
  v_source_ref text := 'ct.cos.v1.current-truth-runtime.v5.rollback.v1';
  v_hash text;
begin
  if not exists(select 1 from integration_control.scheduler_desired_jobs_v2 where jobname='ct-cos-v1-convergence-v2' and generation=2026090118 and command='select public.cos_v1_convergence_cycle_v5();' and source_ref='ct.cos.v1.current-truth-runtime.v5') then raise exception 'scheduler_v5_prestate_changed'; end if;
  if not exists(select 1 from cron.job where jobname='ct-cos-v1-convergence-v2' and active and schedule=v_schedule and command='select public.cos_v1_convergence_cycle_v5();') then raise exception 'live_v5_prestate_changed'; end if;
  v_hash := encode(extensions.digest(convert_to(jsonb_build_object('jobname','ct-cos-v1-convergence-v2','schedule',v_schedule,'command',v_command,'generation',v_generation,'source_ref',v_source_ref,'allow_auto_restore',true)::text,'UTF8'),'sha256'),'hex');
  update integration_control.scheduler_desired_jobs_v2 set command=v_command,generation=v_generation,source_ref=v_source_ref,desired_sha256=v_hash,metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('rollback_of_generation',2026090118,'canonical_function','public.cos_v1_convergence_cycle_v4','authority_created',false),updated_at=clock_timestamp() where jobname='ct-cos-v1-convergence-v2' and generation=2026090118 and command='select public.cos_v1_convergence_cycle_v5();';
  if not found then raise exception 'scheduler_v5_rollback_cas_failed'; end if;
  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-convergence-v2';
  perform cron.alter_job(v_jobid,null,v_command,null,null,true);
end
$rollback$;