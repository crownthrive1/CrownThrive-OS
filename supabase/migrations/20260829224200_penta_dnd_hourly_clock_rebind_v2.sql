-- CrownThrive COS V1
-- Rebind the existing canonical hourly founder-report clock to PentaDND.
-- This migration does not create a duplicate clock and does not place the global OS in maintenance mode.

do $$
declare
  v_jobname constant text := 'penta-mail-state-architecture-hourly-v1';
  v_schedule constant text := '43 * * * *';
  v_command constant text := 'select public.penta_dnd_hourly_orchestrator_v1();';
  v_generation constant bigint := 202608292700;
  v_source_ref constant text := 'ct.penta.dnd.hourly-clock.v2';
  v_jobid bigint;
  v_prior jsonb := '{}'::jsonb;
  v_command_sha text;
  v_desired_sha text;
  v_state_sha text;
  v_event_sha text;
begin
  v_command_sha := encode(extensions.digest(v_command, 'sha256'), 'hex');
  v_desired_sha := encode(
    extensions.digest(concat_ws('|', v_jobname, v_schedule, v_command, current_database(), current_user, 'active', v_generation::text), 'sha256'),
    'hex'
  );
  v_state_sha := encode(
    extensions.digest(concat_ws('|', v_jobname, v_schedule, v_command, 'desired-version-2'), 'sha256'),
    'hex'
  );

  select j.jobid, to_jsonb(j)
    into v_jobid, v_prior
  from cron.job j
  where j.jobname = v_jobname
  limit 1;

  if v_jobid is null then
    v_jobid := cron.schedule(v_jobname, v_schedule, v_command);
  else
    perform cron.alter_job(v_jobid, v_schedule, v_command, null, null, true);
  end if;

  insert into integration_control.scheduler_desired_jobs_v2(
    jobname, schedule, command, database_name, username, active,
    generation, source_ref, desired_sha256, allow_auto_restore, metadata
  ) values (
    v_jobname, v_schedule, v_command, current_database(), current_user, true,
    v_generation, v_source_ref, v_desired_sha, true,
    jsonb_build_object(
      'owner','PentaDND/PentaCrons/PentaTime/PentaSELF/PentaAssure',
      'canonical_program','ct.program.cos-v1.hourly-convergence-dnd',
      'rebinds_existing_clock',true,
      'new_clock_created',false,
      'duplicate_clock_prohibited',true,
      'global_maintenance_required',false,
      'dnd_scope','ct.workstream.cos-v1.deep-discovery',
      'reasoning_workstream','ct.workstream.cos-v1.deep-discovery.pro-reasoning',
      'email_after_each_pass',true,
      'next_phase_required',true,
      'redundancy_profile','hot-warm-dual-cold-v1',
      'no_silent_delete',true,
      'd3_human_reserved',true,
      'authority_created',false,
      'prior_state',coalesce(v_prior,'{}'::jsonb),
      'bound_at',clock_timestamp()
    )
  )
  on conflict (jobname) do update
  set schedule = excluded.schedule,
      command = excluded.command,
      database_name = excluded.database_name,
      username = excluded.username,
      active = excluded.active,
      generation = excluded.generation,
      source_ref = excluded.source_ref,
      desired_sha256 = excluded.desired_sha256,
      allow_auto_restore = excluded.allow_auto_restore,
      metadata = integration_control.scheduler_desired_jobs_v2.metadata || excluded.metadata,
      updated_at = clock_timestamp()
  where excluded.generation >= integration_control.scheduler_desired_jobs_v2.generation;

  insert into penta_self.required_jobs_v1(
    jobname, expected_schedule, expected_command, auto_repair, risk_class, metadata
  ) values (
    v_jobname, v_schedule, v_command, true, 'D2',
    jsonb_build_object(
      'owner','PentaDND/PentaSELF/PentaCrons/PentaTime',
      'mandatory',true,
      'persistent',true,
      'source_ref',v_source_ref,
      'program_id','ct.program.cos-v1.hourly-convergence-dnd',
      'recipient','jones.usmc.kj@gmail.com',
      'single_founder_report_lane',true,
      'no_duplicate_external_clock',true,
      'scope_bounded_dnd',true,
      'global_maintenance_required',false,
      'hot_warm_dual_cold',true,
      'no_silent_delete',true,
      'd3_human_reserved',true,
      'desired_generation',v_generation,
      'updated_at',clock_timestamp()
    )
  )
  on conflict (jobname) do update
  set expected_schedule = excluded.expected_schedule,
      expected_command = excluded.expected_command,
      auto_repair = excluded.auto_repair,
      risk_class = excluded.risk_class,
      metadata = penta_self.required_jobs_v1.metadata || excluded.metadata,
      updated_at = clock_timestamp();

  insert into penta_self.permanent_cron_desired_state_v1(
    jobname, schedule, command, database_name, username_name,
    desired_active, enforcement_mode, verification_evidence,
    desired_sha256, verified_at, source_ref
  ) values (
    v_jobname, v_schedule, v_command, current_database(), current_user,
    true, 'exact',
    jsonb_build_object(
      'captured_from','canonical PentaDND migration',
      'pg_cron_jobid',v_jobid,
      'command_sha256',v_command_sha,
      'generation',v_generation,
      'forward_only',true,
      'duplicate_clock_prohibited',true,
      'global_maintenance_required',false,
      'verified_at',clock_timestamp()
    ),
    v_desired_sha, clock_timestamp(), v_source_ref
  )
  on conflict (jobname) do update
  set schedule = excluded.schedule,
      command = excluded.command,
      database_name = excluded.database_name,
      username_name = excluded.username_name,
      desired_active = excluded.desired_active,
      enforcement_mode = excluded.enforcement_mode,
      verification_evidence = penta_self.permanent_cron_desired_state_v1.verification_evidence || excluded.verification_evidence,
      desired_sha256 = excluded.desired_sha256,
      verified_at = excluded.verified_at,
      source_ref = excluded.source_ref,
      updated_at = clock_timestamp();

  insert into penta_self.critical_cron_state_v2(
    jobname, desired_schedule, desired_command, desired_version,
    state_sha256, enabled, reconciliation_mode, authority_ref, evidence
  ) values (
    v_jobname, v_schedule, v_command, 2,
    v_state_sha, true, 'restore_missing_or_inactive', v_source_ref,
    jsonb_build_object(
      'owner','PentaDND/PentaCrons/PentaTime/PentaSELF',
      'criticality','P0',
      'risk_class','D2',
      'program_id','ct.program.cos-v1.hourly-convergence-dnd',
      'reason','hourly scoped convergence, next-phase persistence, email and four-line continuity',
      'authority_created',false,
      'd3_human_reserved',true,
      'no_silent_delete',true,
      'bound_at',clock_timestamp()
    )
  )
  on conflict (jobname) do update
  set desired_schedule = excluded.desired_schedule,
      desired_command = excluded.desired_command,
      desired_version = greatest(penta_self.critical_cron_state_v2.desired_version, excluded.desired_version),
      state_sha256 = excluded.state_sha256,
      enabled = excluded.enabled,
      reconciliation_mode = excluded.reconciliation_mode,
      authority_ref = excluded.authority_ref,
      evidence = penta_self.critical_cron_state_v2.evidence || excluded.evidence,
      updated_at = clock_timestamp();

  insert into penta_runtime.crons_v1(
    schedule_id, job_name, cron_expression, timezone_name, purpose,
    strict_window_minutes, cron_jobid, state, metadata
  ) values (
    format('pgcron:%s',v_jobid), v_jobname, v_schedule, 'UTC',
    'PentaDND hourly COS V1 convergence, next phase, email and HOT/WARM/COLD-A/COLD-B readback',
    5, v_jobid, 'active',
    jsonb_build_object(
      'owner','PentaCrons',
      'execution_engine','PentaTime',
      'orchestrator','public.penta_dnd_hourly_orchestrator_v1',
      'command_sha256',v_command_sha,
      'program_id','ct.program.cos-v1.hourly-convergence-dnd',
      'global_maintenance_required',false,
      'no_duplicate_clock',true,
      'updated_at',clock_timestamp()
    )
  )
  on conflict (job_name) do update
  set cron_expression = excluded.cron_expression,
      timezone_name = excluded.timezone_name,
      purpose = excluded.purpose,
      strict_window_minutes = excluded.strict_window_minutes,
      cron_jobid = excluded.cron_jobid,
      state = excluded.state,
      metadata = penta_runtime.crons_v1.metadata || excluded.metadata,
      updated_at = clock_timestamp();

  insert into pentatime.scheduler_registry(
    scheduler_name, cron_job_name, owner_layer, criticality,
    desired_state, recovery_policy, notes
  ) values (
    'PentaDND Hourly COS V1 Convergence', v_jobname,
    'PentaTime/PentaCrons', 'critical', 'active', 'fail_closed',
    'Existing canonical hourly founder-report clock rebound to scoped PentaDND; no global maintenance and no duplicate clock.'
  )
  on conflict (cron_job_name) do update
  set owner_layer = excluded.owner_layer,
      criticality = excluded.criticality,
      desired_state = excluded.desired_state,
      recovery_policy = excluded.recovery_policy,
      notes = excluded.notes,
      updated_at = clock_timestamp();

  insert into pentatime.clock_registry_v1(
    clock_key, canonical_name, clock_class, timezone_name,
    cadence_seconds, owner_system_key, state, metadata
  ) values (
    'ct.clock.penta-dnd.hourly', 'PentaDND Hourly Convergence Clock',
    'institutional', 'UTC', 3600, 'penta.dnd', 'active',
    jsonb_build_object(
      'cron_job_name',v_jobname,
      'cron_jobid',v_jobid,
      'minute_offset',43,
      'reason','avoid scheduler stampede while maintaining one pass per hour',
      'no_duplicate_clock',true,
      'bound_at',clock_timestamp()
    )
  )
  on conflict (clock_key) do update
  set canonical_name = excluded.canonical_name,
      clock_class = excluded.clock_class,
      timezone_name = excluded.timezone_name,
      cadence_seconds = excluded.cadence_seconds,
      owner_system_key = excluded.owner_system_key,
      state = excluded.state,
      metadata = pentatime.clock_registry_v1.metadata || excluded.metadata,
      updated_at = clock_timestamp();

  insert into pentatime.dail_clock_bindings_v1(
    system_key, clock_key, sync_cadence_seconds, crossover_enabled,
    timezone_name, state, metadata
  ) values (
    'penta.dnd', 'ct.clock.penta-dnd.hourly', 3600, true, 'UTC', 'active',
    jsonb_build_object(
      'dail_event_per_pass',true,
      'next_phase_written_per_pass',true,
      'email_after_each_pass',true,
      'bound_at',clock_timestamp()
    )
  )
  on conflict (system_key) do update
  set clock_key = excluded.clock_key,
      sync_cadence_seconds = excluded.sync_cadence_seconds,
      crossover_enabled = excluded.crossover_enabled,
      timezone_name = excluded.timezone_name,
      state = excluded.state,
      metadata = pentatime.dail_clock_bindings_v1.metadata || excluded.metadata,
      updated_at = clock_timestamp();

  insert into integration_control.cos_scheduler_census_v1(
    jobname, jobid, schedule, command, command_sha256,
    objective, owner_system_key, canonical_clock_family, canonical,
    lifecycle_state, supersedes, failure_domain, database_name,
    username, evidence, observed_at, updated_at
  ) values (
    v_jobname, v_jobid, v_schedule, v_command, v_command_sha,
    'Run one scoped PentaDND COS V1 convergence pass, persist the next phase, verify four continuity lines and email the founder.',
    'penta.dnd', 'penta-dnd-hourly-convergence', true,
    'active', array[]::text[], 'cos_convergence', current_database(),
    current_user,
    jsonb_build_object(
      'program_id','ct.program.cos-v1.hourly-convergence-dnd',
      'scope_kind','workstream',
      'scope_ref','ct.workstream.cos-v1.deep-discovery',
      'global_maintenance_required',false,
      'no_duplicate_clock',true,
      'hot_warm_dual_cold',true,
      'desired_generation',v_generation,
      'source_ref',v_source_ref,
      'bound_at',clock_timestamp()
    ),
    clock_timestamp(), clock_timestamp()
  )
  on conflict (jobname) do update
  set jobid = excluded.jobid,
      schedule = excluded.schedule,
      command = excluded.command,
      command_sha256 = excluded.command_sha256,
      objective = excluded.objective,
      owner_system_key = excluded.owner_system_key,
      canonical_clock_family = excluded.canonical_clock_family,
      canonical = excluded.canonical,
      lifecycle_state = excluded.lifecycle_state,
      failure_domain = excluded.failure_domain,
      database_name = excluded.database_name,
      username = excluded.username,
      evidence = integration_control.cos_scheduler_census_v1.evidence || excluded.evidence,
      observed_at = excluded.observed_at,
      updated_at = excluded.updated_at;

  update penta_dnd.programs_v1
  set cron_expression = v_schedule,
      metadata = metadata || jsonb_build_object(
        'canonical_cron_jobname',v_jobname,
        'canonical_cron_jobid',v_jobid,
        'canonical_cron_command',v_command,
        'canonical_cron_command_sha256',v_command_sha,
        'canonical_cron_source_ref',v_source_ref,
        'canonical_cron_generation',v_generation,
        'clock_rebound_at',clock_timestamp(),
        'new_clock_created',false,
        'duplicate_clock_prohibited',true
      ),
      updated_at = clock_timestamp()
  where program_id = 'ct.program.cos-v1.hourly-convergence-dnd';

  v_event_sha := encode(
    extensions.digest(
      jsonb_build_object(
        'jobname',v_jobname,
        'jobid',v_jobid,
        'schedule',v_schedule,
        'command',v_command,
        'command_sha256',v_command_sha,
        'generation',v_generation,
        'prior',coalesce(v_prior,'{}'::jsonb),
        'source_ref',v_source_ref
      )::text,
      'sha256'
    ),
    'hex'
  );

  insert into integration_control.scheduler_reconcile_events_v2(
    jobname, generation, observed_state, desired_state,
    action, result_state, evidence_sha256
  ) values (
    v_jobname, v_generation, coalesce(v_prior,'{}'::jsonb),
    jsonb_build_object(
      'jobid',v_jobid,
      'schedule',v_schedule,
      'command',v_command,
      'active',true,
      'source_ref',v_source_ref
    ),
    'REBIND_EXISTING_CANONICAL_CLOCK_TO_PENTA_DND',
    'implemented', v_event_sha
  );

  perform penta_dnd.append_receipt_v1(
    'ct.program.cos-v1.hourly-convergence-dnd', null, null,
    'scheduler.clock.rebound', 'penta.dnd',
    jsonb_build_object(
      'jobname',v_jobname,
      'jobid',v_jobid,
      'schedule',v_schedule,
      'command',v_command,
      'command_sha256',v_command_sha,
      'generation',v_generation,
      'prior_state',coalesce(v_prior,'{}'::jsonb),
      'source_ref',v_source_ref,
      'global_maintenance_required',false,
      'new_clock_created',false,
      'no_silent_delete',true,
      'd3_human_reserved',true,
      'observed_at',clock_timestamp()
    )
  );
end
$$;
