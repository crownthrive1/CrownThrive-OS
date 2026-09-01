-- Portable semantic clock reconciliation for PentaGreen Stripe autowire.
-- Ensures one clock without relying on an environment-specific pg_cron job id.

do $do$
declare r record;
begin
  for r in
    select jobid
    from cron.job
    where active=true
      and (
        jobname='ct-pentagreen-commerce-mesh-cycle-v1'
        or lower(command) like '%thriveevergreen_commerce_mesh_cycle_v1%'
      )
  loop
    perform cron.unschedule(r.jobid);
  end loop;
end
$do$;

select cron.schedule(
  'ct-pentagreen-commerce-mesh-cycle-v1',
  '5-50/15 * * * *',
  'select integration_control.thriveevergreen_commerce_mesh_cycle_v1();'
);

create or replace function integration_control.pentagreen_stripe_clock_status_v1()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','cron'
as $fn$
select jsonb_build_object(
  'state',case when count(*)=1 and bool_and(active) then 'PASS' else 'HOLD' end,
  'matching_jobs',count(*),
  'active_jobs',count(*) filter(where active),
  'job_ids',coalesce(jsonb_agg(jobid order by jobid),'[]'::jsonb),
  'schedule',max(schedule),
  'command',max(command),
  'duplicate_clock',count(*)<>1,
  'observed_at',now()
)
from cron.job
where jobname='ct-pentagreen-commerce-mesh-cycle-v1'
   or lower(command) like '%thriveevergreen_commerce_mesh_cycle_v1%'
$fn$;

revoke all on function integration_control.pentagreen_stripe_clock_status_v1() from public,anon,authenticated;
grant execute on function integration_control.pentagreen_stripe_clock_status_v1() to service_role;
