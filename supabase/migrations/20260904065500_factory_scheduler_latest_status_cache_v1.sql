create table if not exists integration_control.cron_job_latest_status_v1(
  jobid bigint primary key,
  runid bigint not null,
  status text,
  refreshed_at timestamptz not null default clock_timestamp()
);

create table if not exists integration_control.cron_job_latest_status_cursor_v1(
  singleton boolean primary key default true check(singleton),
  last_runid bigint not null default 0,
  updated_at timestamptz not null default clock_timestamp()
);
insert into integration_control.cron_job_latest_status_cursor_v1(singleton,last_runid)
values(true,greatest((select coalesce(max(runid),0)-50000 from cron.job_run_details),0))
on conflict(singleton) do nothing;

create or replace function integration_control.cron_job_latest_status_refresh_v1(p_limit integer default 10000)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','cron'
as $$
declare
  v_last bigint;
  v_max bigint;
  v_rows integer:=0;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if p_limit is null or p_limit<1 or p_limit>100000 then raise exception 'limit_out_of_range'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:cron-job-latest-status-refresh:v1',0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION');
  end if;
  select last_runid into v_last from integration_control.cron_job_latest_status_cursor_v1 where singleton for update;
  with batch as materialized (
    select runid,jobid,status
    from cron.job_run_details
    where runid>v_last
    order by runid
    limit p_limit
  ), latest as (
    select distinct on(jobid) jobid,runid,status
    from batch
    order by jobid,runid desc
  ), up as (
    insert into integration_control.cron_job_latest_status_v1(jobid,runid,status,refreshed_at)
    select jobid,runid,status,clock_timestamp() from latest
    on conflict(jobid) do update
      set runid=excluded.runid,status=excluded.status,refreshed_at=excluded.refreshed_at
      where excluded.runid>integration_control.cron_job_latest_status_v1.runid
    returning 1
  )
  select (select max(runid) from batch),coalesce((select count(*) from batch),0)::integer into v_max,v_rows;
  if v_max is not null then
    update integration_control.cron_job_latest_status_cursor_v1 set last_runid=v_max,updated_at=clock_timestamp() where singleton;
  end if;
  return jsonb_build_object('state','PASS','rows_scanned',v_rows,'last_runid',coalesce(v_max,v_last),'observed_at',clock_timestamp());
end;
$$;

select integration_control.cron_job_latest_status_refresh_v1(50000);

DO $$
declare
  v_def text;
  v_old text := E'left join lateral(\n    select status from cron.job_run_details x\n    where x.jobid=j.jobid order by runid desc limit 1\n  ) d on true';
  v_new text := E'left join integration_control.cron_job_latest_status_v1 d on d.jobid=j.jobid';
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control' and p.proname='penta_factory_drive_snapshot_v2'
    and pg_get_function_identity_arguments(p.oid)='p_factory_key text';
  if v_def is null then raise exception 'snapshot_function_not_found'; end if;
  if position(v_old in v_def)=0 then raise exception 'snapshot_scheduler_fragment_not_found'; end if;
  execute replace(v_def,v_old,v_new);
end $$;

select cron.schedule('ct-cron-job-latest-status-refresh-v1','*/2 * * * *','select integration_control.cron_job_latest_status_refresh_v1(10000);')
where not exists(select 1 from cron.job where jobname='ct-cron-job-latest-status-refresh-v1');