-- Keep PentaSELF scheduler repair aligned with the serialized commercial release wrapper.
-- This prevents scheduler_reconcile_v1 from restoring the superseded direct materializer command.
-- No schedule, authority, checkout, provider-write, or money-movement expansion.

update penta_self.required_jobs_v1
set expected_command = 'select integration_control.commercial_release_packager_serialized_v1();',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'serialization','commercial_release_packager_serialized_v1',
      'source_converged_at',now(),
      'supersedes_direct_materializer_command',true,
      'authority_expansion',false
    ),
    updated_at = now()
where jobname = 'crownthrive_commercial_release_packager_hourly';

do $block$
declare v_job_id bigint;
begin
  select jobid into v_job_id from cron.job
  where jobname='crownthrive_commercial_release_packager_hourly';
  if v_job_id is null then raise exception 'COMMERCIAL_RELEASE_PACKAGER_CRON_NOT_FOUND'; end if;
  perform cron.alter_job(
    v_job_id,
    null,
    'select integration_control.commercial_release_packager_serialized_v1();',
    null,
    null,
    null
  );
end
$block$;
