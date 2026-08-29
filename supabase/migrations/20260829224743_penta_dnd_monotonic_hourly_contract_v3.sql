-- CrownThrive COS V1
-- Append-only supersession of the legacy COS hourly cron contract.
-- Historical generation 2 remains preserved; generation 3 points the existing clock to PentaDND.

do $$
declare
  v_contract_key constant text := 'ct.pentaself.job.cos-hourly-audit';
  v_target_key constant text := 'penta-mail-state-architecture-hourly-v1';
  v_schedule constant text := '43 * * * *';
  v_command constant text := 'select public.penta_dnd_hourly_orchestrator_v1();';
  v_source_ref constant text := 'ct.penta.dnd.hourly-clock.monotonic.v3';
  v_authority_ref constant text := 'ct.penta.dnd.hourly-clock.v2';
  v_generation bigint;
  v_desired jsonb;
  v_sha text;
begin
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-dnd:hourly-monotonic-contract',0)) then
    raise exception 'penta_dnd_monotonic_contract_contention';
  end if;

  select coalesce(max(generation),0)+1
    into v_generation
  from penta_self.desired_state_contracts_v1
  where contract_key=v_contract_key;

  v_desired:=jsonb_build_object(
    'active',true,
    'schedule',v_schedule,
    'command',v_command,
    'risk_class','D2',
    'timing_class','hourly_scoped_convergence',
    'program_id','ct.program.cos-v1.hourly-convergence-dnd',
    'scope_kind','workstream',
    'scope_ref','ct.workstream.cos-v1.deep-discovery',
    'reasoning_workstream','ct.workstream.cos-v1.deep-discovery.pro-reasoning',
    'next_phase_required',true,
    'email_after_each_pass',true,
    'redundancy_profile','hot-warm-dual-cold-v1',
    'global_maintenance_required',false,
    'duplicate_clock_prohibited',true,
    'no_silent_delete',true,
    'D3_human_reserved',true,
    'authority_created',false,
    'supersedes_generation',v_generation-1,
    'rollback_rule','higher_generation_supersession_only'
  );

  v_sha:=encode(
    extensions.digest(
      convert_to(
        jsonb_build_object(
          'contract_key',v_contract_key,
          'generation',v_generation,
          'contract_kind','cron_job',
          'target_key',v_target_key,
          'desired_state',v_desired,
          'source_ref',v_source_ref,
          'authority_ref',v_authority_ref,
          'actor_ref','PentaDND/PentaCrons/PentaTime/PentaSELF/PentaAssure'
        )::text,
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  if not exists(
    select 1
    from penta_self.desired_state_contracts_v1
    where contract_key=v_contract_key
      and desired_state->>'command'=v_command
      and desired_state->>'schedule'=v_schedule
      and coalesce((desired_state->>'active')::boolean,false)
  ) then
    insert into penta_self.desired_state_contracts_v1(
      contract_key,generation,contract_kind,target_key,desired_state,
      source_ref,authority_ref,actor_ref,evidence_sha256
    ) values (
      v_contract_key,v_generation,'cron_job',v_target_key,v_desired,
      v_source_ref,v_authority_ref,
      'PentaDND/PentaCrons/PentaTime/PentaSELF/PentaAssure',v_sha
    );
  else
    select max(generation) into v_generation
    from penta_self.desired_state_contracts_v1
    where contract_key=v_contract_key
      and desired_state->>'command'=v_command
      and desired_state->>'schedule'=v_schedule
      and coalesce((desired_state->>'active')::boolean,false);
  end if;

  update penta_self.required_jobs_v1
  set expected_schedule=v_schedule,
      expected_command=v_command,
      auto_repair=true,
      risk_class='D2',
      metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
        'monotonic_contract_key',v_contract_key,
        'monotonic_generation',v_generation,
        'monotonic_source_ref',v_source_ref,
        'scheduler_authority','integration_control.scheduler_desired_jobs_v2',
        'program_id','ct.program.cos-v1.hourly-convergence-dnd',
        'scope_bounded_dnd',true,
        'hot_warm_dual_cold',true,
        'global_maintenance_required',false,
        'rollback_rule','higher_generation_supersession_only',
        'projection_synced_at',clock_timestamp()
      ),
      updated_at=clock_timestamp()
  where jobname=v_target_key;

  update penta_dnd.programs_v1
  set metadata=metadata||jsonb_build_object(
        'monotonic_contract_key',v_contract_key,
        'monotonic_contract_generation',v_generation,
        'monotonic_contract_sha256',v_sha,
        'legacy_contract_preserved',true,
        'rollback_vector_closed_at',clock_timestamp()
      ),
      updated_at=clock_timestamp()
  where program_id='ct.program.cos-v1.hourly-convergence-dnd';

  perform penta_dnd.append_receipt_v1(
    'ct.program.cos-v1.hourly-convergence-dnd',null,null,
    'scheduler.monotonic-contract.superseded','penta.dnd',
    jsonb_build_object(
      'contract_key',v_contract_key,
      'generation',v_generation,
      'target_key',v_target_key,
      'schedule',v_schedule,
      'command',v_command,
      'evidence_sha256',v_sha,
      'legacy_generation_preserved',true,
      'source_ref',v_source_ref,
      'authority_ref',v_authority_ref,
      'authority_created',false,
      'D3_human_reserved',true,
      'observed_at',clock_timestamp()
    )
  );
end
$$;
