-- CrownThrive COS — Continuous Factory Build, Heal, Verify, and Locticians Feed
--
-- The production runtime is installed in ThriveBase. This migration is a
-- fail-closed source guard: it blocks release when the permanent supervision
-- loop, all-factory canary, Locticians editorial feed, commerce clocks,
-- independent certification, or authority boundaries drift.

begin;

do $guard$
declare
  v_status jsonb;
  v_fleet jsonb;
  v_canary integration_control.penta_factory_production_canary_batches_v1%rowtype;
  v_factory_count integer;
  v_ready_count integer;
  v_jobs integer;
  v_desired integer;
  v_invalid_packets integer;
  v_d3_packets integer;
  v_latest_cycle integration_control.penta_factory_continuous_build_heal_runs_v1%rowtype;
begin
  if to_regclass('integration_control.penta_factory_continuous_build_heal_runs_v1') is null
     or to_regclass('integration_control.penta_factory_production_canary_batches_v1') is null
     or to_regclass('integration_control.penta_factory_registry_v3') is null
     or to_regclass('integration_control.scheduler_desired_jobs_v2') is null then
    raise exception 'FACTORY_CONTINUOUS_HEAL_SCHEMA_INCOMPLETE';
  end if;

  if to_regprocedure('public.penta_factory_continuous_build_heal_cycle_v1()') is null
     or to_regprocedure('public.penta_factory_continuous_build_heal_status_v1()') is null
     or to_regprocedure('public.locticians_editorial_heal_tick_v2(integer)') is null
     or to_regprocedure('integration_control.locticians_editorial_content_normalize_v2(uuid)') is null
     or to_regprocedure('integration_control.locticians_editorial_revision_authorize_v1(uuid)') is null
     or to_regprocedure('public.penta_factory_production_canary_batch_v1(text)') is null
     or to_regprocedure('public.penta_factory_fleet_status_v3()') is null
     or to_regprocedure('public.penta_convergence_certify_v2()') is null
     or to_regprocedure('public.locticians_digital_product_status_v1()') is null then
    raise exception 'FACTORY_CONTINUOUS_HEAL_RUNTIME_INCOMPLETE';
  end if;

  v_status:=public.penta_factory_continuous_build_heal_status_v1();
  v_fleet:=public.penta_factory_fleet_status_v3();

  select count(*),count(*) filter(
    where enabled and production_state='production_active' and function_available
  ) into v_factory_count,v_ready_count
  from integration_control.penta_factory_registry_v3;
  if v_factory_count<>16 or v_ready_count<>16
     or v_fleet->>'state'<>'production_ready' then
    raise exception 'FACTORY_CONTINUOUS_HEAL_FLEET_NOT_READY factories=% ready=% status=%',
      v_factory_count,v_ready_count,left(v_fleet::text,6000);
  end if;

  select * into v_canary
  from integration_control.penta_factory_production_canary_batches_v1
  order by completed_at desc nulls last,started_at desc limit 1;
  if not found or v_canary.state<>'pass'
     or v_canary.expected_factory_count<>16
     or v_canary.produced_count<>16
     or v_canary.self_attested_count<>16
     or v_canary.independently_certified_count<>16
     or v_canary.hold_count<>0 then
    raise exception 'FACTORY_CONTINUOUS_HEAL_CANARY_NOT_PASS:%',to_jsonb(v_canary);
  end if;

  select * into v_latest_cycle
  from integration_control.penta_factory_continuous_build_heal_runs_v1
  order by started_at desc limit 1;
  if not found or v_latest_cycle.state not in ('pass','partial')
     or v_latest_cycle.factory_count<>16
     or v_latest_cycle.production_factory_count<>16
     or v_latest_cycle.factory_canary_state<>'pass'
     or v_latest_cycle.evidence_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'FACTORY_CONTINUOUS_HEAL_LATEST_CYCLE_INVALID:%',to_jsonb(v_latest_cycle);
  end if;

  select count(*) into v_jobs
  from cron.job
  where active and (
    (jobname='ct-penta-factory-continuous-build-heal-locticians-v1'
      and schedule='25,55 * * * *')
    or (jobname='ct-penta-factory-production-canary-v1'
      and schedule='17 */6 * * *')
    or (jobname='ct-stripe-payment-link-sync-v4'
      and schedule='1 */6 * * *')
    or (jobname='ct-locticians-digital-products-checkout-v1'
      and schedule='7 */2 * * *')
    or (jobname='ct-locticians-digital-products-orchestration-v1'
      and schedule='9,19,29,39,49,59 * * * *')
    or (jobname='ct-locticians-digital-products-nurture-v1'
      and schedule='11,26,41,56 * * * *')
  );
  if v_jobs<>6 then raise exception 'FACTORY_CONTINUOUS_HEAL_JOB_COUNT:%',v_jobs; end if;

  select count(*) into v_desired
  from integration_control.scheduler_desired_jobs_v2
  where jobname in (
    'ct-penta-factory-continuous-build-heal-locticians-v1',
    'ct-stripe-payment-link-sync-v4',
    'ct-locticians-digital-products-checkout-v1',
    'ct-locticians-digital-products-orchestration-v1',
    'ct-locticians-digital-products-nurture-v1'
  ) and active and allow_auto_restore;
  if v_desired<>5 then
    raise exception 'FACTORY_CONTINUOUS_HEAL_DESIRED_JOB_COUNT:%',v_desired;
  end if;

  select count(*) into v_invalid_packets
  from pentas.packets_v2 where signature_state<>'signed';
  if v_invalid_packets<>0 then
    raise exception 'FACTORY_CONTINUOUS_HEAL_INVALID_PACKET_SIGNATURES:%',v_invalid_packets;
  end if;

  select count(*) into v_d3_packets
  from pentas.packets_v2 where authority_class='D3' or risk_class='D3';
  if v_d3_packets<>0 then
    raise exception 'FACTORY_CONTINUOUS_HEAL_D3_PACKET_VIOLATIONS:%',v_d3_packets;
  end if;

  if coalesce((v_status#>>'{latest_run,component_results,authority_boundaries,D3_human_reserved}')::boolean,false) is not true
     or coalesce((v_status#>>'{latest_run,component_results,authority_boundaries,money_movement}')::boolean,true)
     or coalesce((v_status#>>'{latest_run,component_results,authority_boundaries,credential_export}')::boolean,true)
     or coalesce((v_status#>>'{latest_run,component_results,authority_boundaries,provider_delete}')::boolean,true)
     or coalesce((v_status#>>'{latest_run,component_results,authority_boundaries,blind_provider_retry}')::boolean,true) then
    raise exception 'FACTORY_CONTINUOUS_HEAL_AUTHORITY_BOUNDARY_DRIFT:%',left(v_status::text,6000);
  end if;
end
$guard$;

select chlom_runtime.append_dail_event(
  'penta.factory.continuous_build_heal.source_guard.pass',
  'source_control_convergence',
  'ct.penta.factory-continuous-build-heal.v1',
  jsonb_build_object(
    'manifest','data/penta/factory-continuous-build-heal-locticians.v1.json',
    'architecture','docs/architecture/factory-continuous-build-heal-locticians-v1.md',
    'continuous_job','ct-penta-factory-continuous-build-heal-locticians-v1',
    'continuous_schedule','25,55 * * * *',
    'factory_canary_job','ct-penta-factory-production-canary-v1',
    'factory_canary_schedule','17 */6 * * *',
    'expected_factory_count',16,
    'locticians_editorial_feed',true,
    'locticians_digital_product_feed',true,
    'D3_human_reserved',true,
    'money_movement',false,
    'credential_export',false,
    'provider_delete',false,
    'verified_at',clock_timestamp()
  ),
  'PentaFactory/PentaSELF/PentaPlanner/PentaPersonaFactory/PentaCertify/Locticians',
  null,'PentaCertify','1.0.0',
  'ctcorr:factory-continuous-heal-source-guard',null,
  'D2_FOUNDER_DIRECTIVE',null,'internal'
);

commit;
