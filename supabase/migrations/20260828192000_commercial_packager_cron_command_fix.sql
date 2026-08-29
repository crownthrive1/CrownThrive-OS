-- Source-custody convergence for the production-proven pg_cron command.
-- The prior migration used named arguments; the production adapter required the positional call.
-- No schedule, authority, money-movement, or release-gate semantics are changed.

do $block$
declare
  v_job_id bigint;
begin
  select jobid into v_job_id
  from cron.job
  where jobname = 'crownthrive_commercial_release_packager_hourly';

  if v_job_id is null then
    raise exception 'COMMERCIAL_RELEASE_PACKAGER_CRON_NOT_FOUND';
  end if;

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
