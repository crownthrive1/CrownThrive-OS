-- Read-only regression assertions for ct.penta.factory-continuity.v6.
-- This test intentionally does not call the certifier because certification writes
-- a new action receipt and DAIL event.

do $test$
declare
  v_count integer;
  v_dispatch_command constant text := $cmd$select pentatime.execute_guarded_v3('factory_dispatch');$cmd$;
  v_continuity_command constant text := $cmd$select pentatime.execute_guarded_v3('factory_continuity');$cmd$;
  v_generator_command constant text := $cmd$select pentatime.execute_guarded_v3('factory_internal_generate');$cmd$;
begin
  select count(*) into v_count
  from cron.job
  where jobname='ct-software-factory-continuity-v5'
    and active
    and command=v_continuity_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: expected exactly one guarded continuity clock, observed %',v_count;
  end if;

  select count(*) into v_count
  from cron.job
  where jobname='ct-software-factory-dispatch-v3'
    and active
    and command=v_dispatch_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: expected exactly one guarded dispatch clock, observed %',v_count;
  end if;

  select count(*) into v_count
  from cron.job
  where jobname='ct-factory-internal-openai-generate-v1'
    and active
    and command=v_generator_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: expected exactly one guarded generator clock, observed %',v_count;
  end if;

  select count(*) into v_count
  from cron.job
  where jobname in ('ct-software-factory-tick-v2','ct-factory-surface-binding-sync-v4')
    and active;
  if v_count<>0 then
    raise exception 'factory_continuity_v6: retired duplicate clocks are active: %',v_count;
  end if;

  select count(*) into v_count
  from cron.job
  where active
    and jobname in (
      'ct-software-factory-continuity-v5',
      'ct-software-factory-dispatch-v3',
      'ct-factory-internal-openai-generate-v1'
    )
    and command not like 'select pentatime.execute_guarded_v3(%';
  if v_count<>0 then
    raise exception 'factory_continuity_v6: active raw factory clocks observed: %',v_count;
  end if;

  select count(*) into v_count
  from pentatime.operation_registry_v2
  where operation_key in (
      'factory_continuity',
      'factory_dispatch',
      'factory_internal_generate',
      'factory_surface_binding_sync'
    )
    and enabled
    and domain_key='ct:production-governance-write-lane';
  if v_count<>4 then
    raise exception 'factory_continuity_v6: expected four operations in the shared write lane, observed %',v_count;
  end if;

  select count(*) into v_count
  from pentatime.operation_executors_v3
  where operation_key='factory_dispatch'
    and enabled
    and executor_regprocedure='pentatime.executor_factory_dispatch_v3()'::regprocedure;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: dispatch executor is missing or drifted';
  end if;

  select count(*) into v_count
  from integration_control.scheduler_desired_jobs_v2
  where jobname='ct-software-factory-dispatch-v3'
    and active
    and allow_auto_restore
    and generation>=2026082912
    and command=v_dispatch_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: institutional scheduler desired state is stale';
  end if;

  select count(*) into v_count
  from penta_self.required_jobs_v1
  where jobname='ct-software-factory-dispatch-v3'
    and auto_repair
    and expected_command=v_dispatch_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: PentaSELF required-job state is stale';
  end if;

  select count(*) into v_count
  from penta_self.critical_cron_state_v2
  where jobname='ct-software-factory-dispatch-v3'
    and enabled
    and desired_version>=2
    and desired_command=v_dispatch_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: PentaSELF critical-cron state is stale';
  end if;

  select count(*) into v_count
  from penta_self.permanent_cron_desired_state_v1
  where jobname='ct-software-factory-dispatch-v3'
    and desired_active
    and enforcement_mode='exact'
    and command=v_dispatch_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: PentaSELF permanent-cron state is stale';
  end if;

  select count(*) into v_count
  from penta_self.desired_state_contracts_v1 c
  where c.contract_key='ct.pentaself.job.factory-dispatch'
    and c.generation=(
      select max(x.generation)
      from penta_self.desired_state_contracts_v1 x
      where x.contract_key=c.contract_key
    )
    and c.generation>=2
    and c.desired_state->>'command'=v_dispatch_command;
  if v_count<>1 then
    raise exception 'factory_continuity_v6: highest-generation monotonic dispatch contract is stale';
  end if;

  if to_regprocedure('penta_self.evaluate_permanent_repair_v4(text,text,jsonb)') is null
     or to_regprocedure('penta_self.permanent_repair_tick_v4()') is null
     or to_regprocedure('penta_self.surgical_orchestrator_v4()') is null
     or to_regprocedure('penta_self.reconcile_factory_continuity_v6()') is null
     or to_regprocedure('penta_self.certify_factory_continuity_v6()') is null then
    raise exception 'factory_continuity_v6: required PentaSELF V4 function is missing';
  end if;

  select count(*) into v_count
  from penta_self.permanent_repairs_v2
  where repair_key in (
      'ct.penta-self.repair.factory-continuity-overlap-surgery.v1',
      'ct.penta-self.repair.factory-generator-recursion-surgery.v1'
    )
    and enabled
    and last_state='verified';
  if v_count<>2 then
    raise exception 'factory_continuity_v6: expected two verified permanent factory repairs, observed %',v_count;
  end if;

  select count(*) into v_count
  from pg_trigger
  where tgname='trg_scheduler_desired_generation_v3'
    and tgenabled<>'D';
  if v_count<>1 then
    raise exception 'factory_continuity_v6: scheduler generation fence is missing or disabled';
  end if;
end;
$test$;

select jsonb_build_object(
  'contract','ct.penta.factory-continuity.v6',
  'state','PASS',
  'read_only',true,
  'tested_at',clock_timestamp()
) as factory_continuity_v6_regression_result;
