-- CrownThrive COS V1 sprint performance repair.
-- cos_scheduler_census_refresh_v1 previously performed one backward PK scan of
-- cron.job_run_details per scheduler, filtering ~23K unrelated rows each time.
-- This rewrite computes latest runid once per job in a single grouped scan,
-- then joins the exact rows by the existing runid PK. No cron-owned index DDL.
-- Rollback: restore predecessor function digest below from source history.

do $repair$
declare
  v_definition text;
  v_pre_sha text;
  v_post_sha text;
  v_old constant text := $$    from cron.job j
    left join lateral (
      select status,start_time,end_time,return_message
      from cron.job_run_details x
      where x.jobid=j.jobid
      order by x.runid desc limit 1
    ) d on true$$;
  v_new constant text := $$    from cron.job j
    left join (
      select d1.jobid,d1.status,d1.start_time,d1.end_time,d1.return_message
      from cron.job_run_details d1
      join (
        select jobid,max(runid) as runid
        from cron.job_run_details
        group by jobid
      ) latest on latest.jobid=d1.jobid and latest.runid=d1.runid
    ) d on d.jobid=j.jobid$$;
begin
  select pg_get_functiondef('integration_control.cos_scheduler_census_refresh_v1()'::regprocedure)
    into v_definition;
  v_pre_sha := encode(extensions.digest(v_definition,'sha256'),'hex');
  if v_pre_sha <> '3dc88d924b55b414c297bd4b0f1e102a09589f9b4def6ef6890df3fe33f9601c' then
    raise exception 'cos_scheduler_census_refresh_v1 predecessor drift: expected %, found %',
      '3dc88d924b55b414c297bd4b0f1e102a09589f9b4def6ef6890df3fe33f9601c', v_pre_sha;
  end if;
  if position(v_old in v_definition)=0 then
    raise exception 'expected per-job latest-run lateral fragment absent';
  end if;
  v_definition := replace(v_definition,v_old,v_new);
  execute v_definition;
  select encode(extensions.digest(pg_get_functiondef('integration_control.cos_scheduler_census_refresh_v1()'::regprocedure),'sha256'),'hex')
    into v_post_sha;
  if v_post_sha=v_pre_sha then
    raise exception 'scheduler census fast-path digest did not change';
  end if;
end
$repair$;

comment on function integration_control.cos_scheduler_census_refresh_v1() is
  'COS scheduler census refresh v1. Latest pg_cron run lookup is batched by jobid/max(runid) to avoid per-job full-history scans; sprint convergence repair.';
