-- COS V1: move authoritative scheduler desired state from convergence v3 to v5.
-- This is a monotonic scheduler-generation supersession; it does not delete history.

do $repair$
declare
  v_jobid bigint;
  v_rows integer;
  v_generation bigint := 2026090118;
  v_schedule text := '9,19,29,39,49,59 * * * *';
  v_command text := 'select public.cos_v1_convergence_cycle_v5();';
  v_source_ref text := 'ct.cos.v1.current-truth-runtime.v5';
  v_hash text;
begin
  if not exists (
    select 1 from integration_control.scheduler_desired_jobs_v2
    where jobname='ct-cos-v1-convergence-v2'
      and generation=2026083006
      and command='select public.cos_v1_convergence_cycle_v3();'
      and schedule=v_schedule and active=true and allow_auto_restore=true
      and source_ref='ct.cos.v1.current-truth-runtime.v3'
  ) then raise exception 'scheduler_desired_prestate_changed'; end if;

  v_hash := encode(extensions.digest(convert_to(jsonb_build_object('jobname','ct-cos-v1-convergence-v2','schedule',v_schedule,'command',v_command,'generation',v_generation,'source_ref',v_source_ref,'allow_auto_restore',true)::text,'UTF8'),'sha256'),'hex');

  update integration_control.scheduler_desired_jobs_v2
     set schedule=v_schedule, command=v_command, active=true, generation=v_generation,
         source_ref=v_source_ref, desired_sha256=v_hash, allow_auto_restore=true,
         metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
           'canonical_function','public.cos_v1_convergence_cycle_v5',
           'previous_canonical_function','public.cos_v1_convergence_cycle_v3',
           'compatibility_function','public.cos_v1_convergence_cycle_v3',
           'status_function','public.cos_v1_status_v3',
           'heavy_projection_in_outer_transaction',false,
           'projection_clocks_decoupled',true,
           'dail_critical_section','final_append_only',
           'scheduler_authority_generation',v_generation,
           'authority_created',false,'D3_human_reserved',true),
         updated_at=clock_timestamp()
   where jobname='ct-cos-v1-convergence-v2' and generation=2026083006
     and command='select public.cos_v1_convergence_cycle_v3();'
     and source_ref='ct.cos.v1.current-truth-runtime.v3';
  get diagnostics v_rows = row_count;
  if v_rows <> 1 then raise exception 'scheduler_desired_cas_failed:%',v_rows; end if;

  select jobid into v_jobid from cron.job where jobname='ct-cos-v1-convergence-v2';
  if v_jobid is null then raise exception 'canonical_cos_convergence_job_missing'; end if;
  if not exists (select 1 from cron.job where jobid=v_jobid and active=true and schedule=v_schedule and command='select public.cos_v1_convergence_cycle_v3();') then raise exception 'live_scheduler_prestate_changed'; end if;
  perform cron.alter_job(v_jobid,null,v_command,null,null,true);

  if not exists (select 1 from integration_control.scheduler_desired_jobs_v2 where jobname='ct-cos-v1-convergence-v2' and generation=v_generation and command=v_command and schedule=v_schedule and active=true and source_ref=v_source_ref and desired_sha256=v_hash)
     or not exists (select 1 from cron.job where jobid=v_jobid and command=v_command and schedule=v_schedule and active=true) then
    raise exception 'scheduler_v5_postcondition_failed';
  end if;
end
$repair$;