-- CrownThrive COS V1 sprint performance/concurrency repair.
-- The scheduler census previously executed one target-table UPSERT per cron job.
-- Because the census table has a statement-level DAIL routing trigger, that
-- produced hundreds of target statements and avoidable concurrent row/index
-- contention. Stage rows locally, then perform one canonical target UPSERT.
-- A try-advisory lock makes overlapping refreshes reuse the current snapshot.
-- Rollback: restore predecessor function digest from source history.

do $repair$
declare
  v_definition text;
  v_pre_sha text;
  v_post_sha text;
  v_auth_old constant text := $$  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;$$;
  v_auth_new constant text := $$  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct.cos.scheduler-census-refresh.v1',0)) then
    return jsonb_build_object('ok',true,'contract','ct.cos.scheduler-authoritative-lifecycle.v1',
      'state','SKIPPED_LOCKED','snapshot_reused',true,'observed_at',clock_timestamp());
  end if;
  create temporary table if not exists cos_scheduler_census_stage_v1
    (like integration_control.cos_scheduler_census_v1 including defaults)
    on commit drop;
  truncate table cos_scheduler_census_stage_v1;$$;
  v_target_old constant text := $$    insert into integration_control.cos_scheduler_census_v1($$;
  v_target_new constant text := $$    insert into cos_scheduler_census_stage_v1($$;
  v_conflict_old constant text := $$    on conflict(jobname) do update set
      jobid=excluded.jobid,schedule=excluded.schedule,command=excluded.command,
      command_sha256=excluded.command_sha256,objective=excluded.objective,
      owner_system_key=excluded.owner_system_key,
      canonical_clock_family=excluded.canonical_clock_family,canonical=excluded.canonical,
      lifecycle_state=excluded.lifecycle_state,supersedes=excluded.supersedes,
      superseded_by=excluded.superseded_by,failure_domain=excluded.failure_domain,
      database_name=excluded.database_name,username=excluded.username,
      latest_run_status=excluded.latest_run_status,
      latest_run_started_at=excluded.latest_run_started_at,
      latest_run_ended_at=excluded.latest_run_ended_at,
      next_execution_hint=excluded.next_execution_hint,evidence=excluded.evidence,
      observed_at=clock_timestamp(),updated_at=clock_timestamp();$$;
  v_loop_old constant text := $$  end loop;

  return jsonb_build_object($$;
  v_loop_new constant text := $$  end loop;

  insert into integration_control.cos_scheduler_census_v1(
    jobname,jobid,schedule,command,command_sha256,objective,owner_system_key,
    canonical_clock_family,canonical,lifecycle_state,supersedes,superseded_by,
    failure_domain,database_name,username,latest_run_status,latest_run_started_at,
    latest_run_ended_at,next_execution_hint,evidence,observed_at,updated_at
  )
  select jobname,jobid,schedule,command,command_sha256,objective,owner_system_key,
    canonical_clock_family,canonical,lifecycle_state,supersedes,superseded_by,
    failure_domain,database_name,username,latest_run_status,latest_run_started_at,
    latest_run_ended_at,next_execution_hint,evidence,observed_at,updated_at
  from cos_scheduler_census_stage_v1
  on conflict(jobname) do update set
    jobid=excluded.jobid,schedule=excluded.schedule,command=excluded.command,
    command_sha256=excluded.command_sha256,objective=excluded.objective,
    owner_system_key=excluded.owner_system_key,
    canonical_clock_family=excluded.canonical_clock_family,canonical=excluded.canonical,
    lifecycle_state=excluded.lifecycle_state,supersedes=excluded.supersedes,
    superseded_by=excluded.superseded_by,failure_domain=excluded.failure_domain,
    database_name=excluded.database_name,username=excluded.username,
    latest_run_status=excluded.latest_run_status,
    latest_run_started_at=excluded.latest_run_started_at,
    latest_run_ended_at=excluded.latest_run_ended_at,
    next_execution_hint=excluded.next_execution_hint,evidence=excluded.evidence,
    observed_at=excluded.observed_at,updated_at=excluded.updated_at;

  return jsonb_build_object($$;
begin
  select pg_get_functiondef('integration_control.cos_scheduler_census_refresh_v1()'::regprocedure)
    into v_definition;
  v_pre_sha := encode(extensions.digest(v_definition,'sha256'),'hex');
  if v_pre_sha <> 'a5025939287d377ad82180e6d7c2ea0e2c16c512bc0cc1865ce13602a30b8bd2' then
    raise exception 'scheduler census predecessor drift: expected %, found %',
      'a5025939287d377ad82180e6d7c2ea0e2c16c512bc0cc1865ce13602a30b8bd2', v_pre_sha;
  end if;
  if position(v_auth_old in v_definition)=0 or position(v_target_old in v_definition)=0
     or position(v_conflict_old in v_definition)=0 or position(v_loop_old in v_definition)=0 then
    raise exception 'scheduler census expected rewrite fragment absent';
  end if;
  v_definition := replace(v_definition,v_auth_old,v_auth_new);
  v_definition := replace(v_definition,v_target_old,v_target_new);
  v_definition := replace(v_definition,v_conflict_old,';');
  v_definition := replace(v_definition,v_loop_old,v_loop_new);
  execute v_definition;
  select encode(extensions.digest(pg_get_functiondef('integration_control.cos_scheduler_census_refresh_v1()'::regprocedure),'sha256'),'hex')
    into v_post_sha;
  if v_post_sha=v_pre_sha then raise exception 'scheduler census single-write repair made no change'; end if;
end
$repair$;

comment on function integration_control.cos_scheduler_census_refresh_v1() is
  'COS scheduler census refresh v1. Batches latest-run reads, stages scheduler rows, performs one target UPSERT/DAIL statement, and skips overlapping refreshes via try-advisory lock.';
