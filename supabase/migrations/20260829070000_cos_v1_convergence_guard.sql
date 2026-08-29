-- CrownThrive COS V1.0.0 production convergence guard
--
-- The implementation is installed through the governed ThriveBase migrations
-- recorded in data/penta/cos-v1-convergence-core.v1.json. This source-controlled
-- guard refuses certification when typed truth, Census, Pentas, DAIL Trust,
-- repositories, schedulers, sites, factories, adapters or repair routing drift.

begin;

do $cos_guard$
declare
  v_status jsonb;
  v_pentas_canary jsonb;
  v_merkle jsonb;
  v_truth integer;
  v_kinds integer;
  v_populated integer;
  v_unresolved integer;
  v_repositories integer;
  v_repositories_federated integer;
  v_repositories_runtime integer;
  v_scheduler_unknown integer;
  v_site_unknown integer;
  v_site_unrouted integer;
  v_factory_count integer;
  v_factory_offline integer;
  v_factory_unroutable integer;
  v_factory_unrouted integer;
  v_pentaself_unrouted integer;
  v_checkpoint_count integer;
  v_signed_checkpoint_count integer;
  v_checkpoint_tail bigint;
  v_anchor_failures integer;
  v_wire_state text;
  v_provider_holds integer;
  v_tool_drift integer;
  v_ofac_pass boolean;
  v_mail_epoch text;
  v_cos_jobs integer;
  v_legacy_jobs integer;
begin
  if to_regclass('integration_control.cos_release_registry_v1') is null
     or to_regclass('integration_control.cos_truth_authority_registry_v1') is null
     or to_regclass('integration_control.cos_entity_kind_registry_v1') is null
     or to_regclass('integration_control.cos_identity_registry_v1') is null
     or to_regclass('integration_control.cos_identity_aliases_v1') is null
     or to_regclass('integration_control.cos_version_relationships_v1') is null
     or to_regclass('integration_control.cos_entities_v2') is null
     or to_regclass('integration_control.cos_entity_relationships_v2') is null
     or to_regclass('integration_control.cos_repository_census_v1') is null
     or to_regclass('integration_control.cos_scheduler_census_v1') is null
     or to_regclass('integration_control.cos_site_truth_freshness_v1') is null
     or to_regclass('integration_control.cos_certification_receipts_v1') is null
     or to_regclass('integration_control.pentas_network_epoch_policy_v3') is null
     or to_regclass('integration_control.pentas_cos_v1_canary_receipts_v1') is null
     or to_regclass('chlom_runtime.dail_epoch_checkpoints_v2') is null
     or to_regclass('chlom_runtime.dail_epoch_membership_v2') is null
     or to_regclass('chlom_runtime.dail_checkpoint_anchor_queue_v2') is null then
    raise exception 'COS_V1_REQUIRED_SCHEMA_INCOMPLETE';
  end if;

  if to_regprocedure('public.cos_v1_status_v2()') is null
     or to_regprocedure('public.cos_v1_convergence_cycle_v2()') is null
     or to_regprocedure('public.cos_v1_certify_v1(text,text,boolean)') is null
     or to_regprocedure('integration_control.cos_census_refresh_v2()') is null
     or to_regprocedure('integration_control.cos_census_extended_refresh_v2()') is null
     or to_regprocedure('integration_control.cos_repository_census_refresh_v1()') is null
     or to_regprocedure('integration_control.cos_scheduler_census_refresh_v1()') is null
     or to_regprocedure('integration_control.cos_site_truth_refresh_v1()') is null
     or to_regprocedure('integration_control.cos_plan_noncurrent_state_v1()') is null
     or to_regprocedure('integration_control.cos_hold_census_refresh_v2()') is null
     or to_regprocedure('public.pentas_cos_v1_end_to_end_canary_v1()') is null
     or to_regprocedure('chlom_runtime.create_dail_epoch_checkpoint_v2(integer)') is null
     or to_regprocedure('chlom_runtime.dail_verify_merkle_proof_v2(bigint)') is null then
    raise exception 'COS_V1_REQUIRED_FUNCTION_SET_INCOMPLETE';
  end if;

  if not exists(
    select 1
    from integration_control.cos_release_registry_v1
    where release_id='ct.cos.release.1.0.0'
      and semantic_version='1.0.0'
      and source_repository='crownthrive1/CrownThrive-OS'
      and state in ('converging','certification_pending','certified','released')
  ) then
    raise exception 'COS_V1_RELEASE_REGISTRY_DRIFT';
  end if;

  select count(*) into v_truth
  from integration_control.cos_truth_authority_registry_v1
  where active;
  if v_truth<>7 then
    raise exception 'COS_V1_TYPED_TRUTH_AUTHORITY_COUNT=%',v_truth;
  end if;

  if not exists(
    select 1
    from integration_control.cos_truth_authority_registry_v1
    where truth_type='institutional_history'
      and canonical_authority='DAIL'
      and conflict_action='history_is_immutable'
  ) or not exists(
    select 1
    from integration_control.cos_truth_authority_registry_v1
    where truth_type='rights_authority_identity'
      and canonical_authority='CHLOM'
      and conflict_action='fail_closed'
  ) or not exists(
    select 1
    from integration_control.cos_truth_authority_registry_v1
    where truth_type='provider_current_state'
      and canonical_authority='Direct provider readback'
      and direct_readback
      and conflict_action='provider_wins_current_state'
  ) then
    raise exception 'COS_V1_TYPED_TRUTH_PRECEDENCE_DRIFT';
  end if;

  select count(*) into v_kinds
  from integration_control.cos_entity_kind_registry_v1
  where active;
  select count(distinct entity_kind) into v_populated
  from integration_control.cos_entities_v2
  where current;
  select count(*) into v_unresolved
  from integration_control.cos_entities_v2
  where current and lifecycle_state='unresolved';
  if v_kinds<>34 or v_populated<>34 or v_unresolved<>0 then
    raise exception 'COS_V1_CENSUS_INCOMPLETE kinds=%,populated=%,unresolved=%',
      v_kinds,v_populated,v_unresolved;
  end if;

  if exists(
    select 1
    from integration_control.cos_entity_kind_registry_v1 k
    where k.active
      and not exists(
        select 1
        from integration_control.cos_entities_v2 e
        where e.current and e.entity_kind=k.entity_kind
      )
  ) then
    raise exception 'COS_V1_CENSUS_ENTITY_KIND_UNPOPULATED';
  end if;

  select count(*),
         count(*) filter(where in_federation_registry),
         count(*) filter(where in_runtime_registry)
  into v_repositories,v_repositories_federated,v_repositories_runtime
  from integration_control.cos_repository_census_v1
  where source_state='provider_observed';
  if v_repositories<>14 or v_repositories_federated<>14 or v_repositories_runtime<>14 then
    raise exception 'COS_V1_REPOSITORY_CONVERGENCE_FAILED provider=%,federation=%,runtime=%',
      v_repositories,v_repositories_federated,v_repositories_runtime;
  end if;

  if not exists(
    select 1
    from integration_control.cos_identity_aliases_v1
    where alias_namespace='github_repository'
      and alias_value='crownthrive1/CrownThrive-CIE'
      and alias_state='historic'
  ) or not exists(
    select 1
    from integration_control.cos_identity_aliases_v1
    where alias_namespace='penta_system'
      and alias_value='ThriveEvergreen'
      and alias_state='historic'
  ) then
    raise exception 'COS_V1_HISTORIC_IDENTITY_ALIAS_GAP';
  end if;

  select count(*) into v_scheduler_unknown
  from integration_control.cos_scheduler_census_v1
  where lifecycle_state='unresolved';
  if v_scheduler_unknown<>0 then
    raise exception 'COS_V1_SCHEDULER_UNKNOWN_COUNT=%',v_scheduler_unknown;
  end if;

  select count(*) into v_cos_jobs
  from cron.job
  where active
    and jobname in ('ct-dail-trust-checkpoint-v2','ct-cos-v1-convergence-v2');
  select count(*) into v_legacy_jobs
  from cron.job
  where jobname in (
    'ct-cos-v1-hourly-convergence-v1',
    'ct-dail-checkpoint-v1',
    'ct-pentas-mesh-router-v3'
  );
  if v_cos_jobs<>2 or v_legacy_jobs<>0 then
    raise exception 'COS_V1_CANONICAL_CLOCK_DRIFT canonical=%,legacy=%',v_cos_jobs,v_legacy_jobs;
  end if;

  if not exists(
    select 1 from cron.job
    where jobname='ct-dail-trust-checkpoint-v2'
      and active
      and schedule='7,22,37,52 * * * *'
      and command='select chlom_runtime.dail_checkpoint_catchup_v2(1,20000);'
  ) or not exists(
    select 1 from cron.job
    where jobname='ct-cos-v1-convergence-v2'
      and active
      and schedule='9,19,29,39,49,59 * * * *'
      and command='select public.cos_v1_convergence_cycle_v2();'
  ) then
    raise exception 'COS_V1_CANONICAL_CLOCK_CONTRACT_MISMATCH';
  end if;

  select count(*) into v_site_unknown
  from integration_control.cos_site_truth_freshness_v1
  where truth_state='unknown';
  select count(*) into v_site_unrouted
  from integration_control.cos_site_truth_freshness_v1 f
  where f.truth_state<>'current'
    and not exists(
      select 1
      from integration_control.penta_planner_candidates_v1 p
      where p.candidate_key='cos:site-truth:'||f.surface_id
        and p.state not in ('expired','suppressed')
    );
  if (select count(*) from integration_control.cos_site_truth_freshness_v1)<>22
     or v_site_unknown<>0
     or v_site_unrouted<>0 then
    raise exception 'COS_V1_SITE_TRUTH_GAP rows=%,unknown=%,unrouted=%',
      (select count(*) from integration_control.cos_site_truth_freshness_v1),
      v_site_unknown,v_site_unrouted;
  end if;

  select count(*),
         count(*) filter(where runtime_state in ('offline','failed','hold') or not production_enabled),
         count(*) filter(where repair_route is null or btrim(repair_route)='')
  into v_factory_count,v_factory_offline,v_factory_unroutable
  from integration_control.penta_factory_registry_v1;
  select count(*) into v_factory_unrouted
  from integration_control.penta_factory_registry_v1 f
  where (f.health_state not in ('healthy','pass') or f.hold_count>0 or f.failed_24h>0)
    and not exists(
      select 1
      from integration_control.penta_planner_candidates_v1 p
      where p.candidate_key='cos:factory-convergence:'||f.factory_key
        and p.state not in ('expired','suppressed')
    );
  if v_factory_count<>11 or v_factory_offline<>0
     or v_factory_unroutable<>0 or v_factory_unrouted<>0 then
    raise exception 'COS_V1_FACTORY_CONVERGENCE_FAILED count=%,offline=%,unroutable=%,unrouted=%',
      v_factory_count,v_factory_offline,v_factory_unroutable,v_factory_unrouted;
  end if;

  if public.pentas_current_epoch_v3()<>'cos-v1' then
    raise exception 'COS_V1_PENTAS_NETWORK_EPOCH_DRIFT';
  end if;
  select to_jsonb(c) into v_pentas_canary
  from integration_control.pentas_cos_v1_canary_receipts_v1 c
  order by created_at desc
  limit 1;
  if v_pentas_canary is null
     or coalesce((v_pentas_canary->>'signature_pass')::boolean,false) is not true
     or coalesce((v_pentas_canary->>'content_address_pass')::boolean,false) is not true
     or coalesce((v_pentas_canary->>'cookie_binding_pass')::boolean,false) is not true
     or coalesce((v_pentas_canary->>'origin_node_pass')::boolean,false) is not true
     or v_pentas_canary->>'final_packet_state'<>'delivered'
     or v_pentas_canary->>'final_delivery_state'<>'delivered' then
    raise exception 'COS_V1_PENTAS_END_TO_END_CANARY_FAILED:%',v_pentas_canary;
  end if;

  select count(*),count(*) filter(where signature_state='verified')
  into v_checkpoint_count,v_signed_checkpoint_count
  from chlom_runtime.dail_epoch_checkpoints_v2;
  select count(*) into v_checkpoint_tail
  from chlom_runtime.dail_events e
  where not exists(
    select 1
    from chlom_runtime.dail_epoch_membership_v2 m
    where m.sequence_id=e.sequence_id
  );
  select count(*) into v_anchor_failures
  from chlom_runtime.dail_checkpoint_anchor_queue_v2
  where anchor_state='failed';
  select chlom_runtime.dail_verify_merkle_proof_v2(min(sequence_id))
  into v_merkle
  from chlom_runtime.dail_epoch_membership_v2;
  if v_checkpoint_count<1
     or v_signed_checkpoint_count<>v_checkpoint_count
     or v_checkpoint_tail>50000
     or v_anchor_failures<>0
     or coalesce((v_merkle->>'ok')::boolean,false) is not true then
    raise exception 'COS_V1_DAIL_TRUST_FAILED checkpoints=%,signed=%,tail=%,anchor_failures=%,proof=%',
      v_checkpoint_count,v_signed_checkpoint_count,v_checkpoint_tail,v_anchor_failures,v_merkle;
  end if;

  if exists(
    select 1
    from chlom_runtime.dail_checkpoint_anchor_queue_v2
    where anchor_state='anchored_production'
      and nullif(transaction_hash,'') is null
  ) then
    raise exception 'COS_V1_DAIL_PRODUCTION_ANCHOR_WITHOUT_TRANSACTION_RECEIPT';
  end if;

  select result_state,provider_contract_holds,tool_contract_drift_services
  into v_wire_state,v_provider_holds,v_tool_drift
  from integration_control.penta_wire_scan_receipts_v1
  order by observed_at desc
  limit 1;
  if v_wire_state<>'pass' or v_provider_holds<>0 or v_tool_drift<>0 then
    raise exception 'COS_V1_PENTAWIRE_FAILED state=%,provider_holds=%,tool_drift=%',
      v_wire_state,v_provider_holds,v_tool_drift;
  end if;

  if coalesce((integration_control.penta_wire_openai_status_v1()->>'ready')::boolean,false) is not true then
    raise exception 'COS_V1_OPENAI_PENTA_INFERENCE_NOT_READY';
  end if;

  select exists(
    select 1
    from integration_control.pentaofac_refresh_receipts_v2
    where decision='pass'
      and http_status=200
      and source_count>0
      and source_count=source_pass_count
      and created_at>=clock_timestamp()-interval '2 hours'
    order by created_at desc
    limit 1
  ) into v_ofac_pass;
  if not v_ofac_pass then
    raise exception 'COS_V1_PENTAOFAC_CURRENT_PROVIDER_EVIDENCE_MISSING';
  end if;

  v_mail_epoch:=public.penta_mail_receipt_chain_epoch_status_v1()->>'state';
  if v_mail_epoch<>'verified' then
    raise exception 'COS_V1_PENTAMAIL_RECEIPT_EPOCH_STATE=%',v_mail_epoch;
  end if;

  if public.penta_planner_status_v1()->>'state'<>'production_active' then
    raise exception 'COS_V1_PENTAPLANNER_NOT_PRODUCTION_ACTIVE';
  end if;
  if public.penta_persona_factory_status_v1()->>'state'<>'production_active' then
    raise exception 'COS_V1_PERSONA_FACTORY_NOT_PRODUCTION_ACTIVE';
  end if;
  if public.penta_factory_fleet_status_v1()->>'state'<>'operational' then
    raise exception 'COS_V1_FACTORY_FLEET_NOT_OPERATIONAL';
  end if;
  if public.penta_self_status_v1()->>'state'<>'PRODUCTION' then
    raise exception 'COS_V1_PENTASELF_NOT_PRODUCTION';
  end if;

  select count(*) into v_pentaself_unrouted
  from penta_self.problem_ledger_v1 s
  where s.state not in ('resolved','closed','superseded')
    and not exists(
      select 1
      from integration_control.penta_planner_candidates_v1 p
      where p.candidate_key='cos:pentaself:'||s.problem_id::text
        and p.state not in ('expired','suppressed')
    );
  if v_pentaself_unrouted<>0 then
    raise exception 'COS_V1_PENTASELF_UNROUTED_CONDITION_COUNT=%',v_pentaself_unrouted;
  end if;

  if not exists(
    select 1
    from integration_control.penta_planner_candidates_v1
    where candidate_key='cos:dail-production-chain-anchor'
      and state='human_required'
      and requires_human
      and risk_class='D3'
  ) then
    raise exception 'COS_V1_DAIL_CHAIN_ANCHOR_D3_BOUNDARY_MISSING';
  end if;

  v_status:=public.cos_v1_status_v2();
  if v_status->>'state'<>'certifiable' then
    raise exception 'COS_V1_STATUS_NOT_CERTIFIABLE:%',left(v_status::text,6000);
  end if;
end
$cos_guard$;

select chlom_runtime.append_dail_event(
  'cos.v1.source_convergence_guard.pass',
  'source_control_convergence',
  'ct.cos.release.1.0.0',
  jsonb_build_object(
    'manifest','data/penta/cos-v1-convergence-core.v1.json',
    'architecture','docs/COS_V1_CONVERGENCE_ARCHITECTURE.md',
    'typed_truth_authorities',7,
    'entity_kinds_registered',34,
    'entity_kinds_populated',34,
    'repositories_provider_observed',14,
    'repositories_federation_accounted',14,
    'repositories_runtime_accounted',14,
    'factory_count',11,
    'site_truth_unknown',0,
    'repair_routing_gaps',0,
    'pentas_network_epoch','cos-v1',
    'pentas_end_to_end_canary','pass',
    'dail_trust_checkpointing','pass',
    'external_chain_anchor_state','production_gated',
    'external_chain_transaction_claimed',false,
    'penta_wire_state','pass',
    'd3_human_reserved',true,
    'money_movement_created',false,
    'provider_authority_created',false,
    'raw_secret_material_committed',false,
    'verified_at',clock_timestamp()
  ),
  'COS/PentaTruth/PentaCensus/Pentas/DAIL/CHLOM/PentaPlanner/PentaFactory/PentaPersonaFactory/PentaWire/PentaCertify/PentaSELF',
  null,
  'PentaCertify',
  '1.0.0',
  'ctcorr:cos-v1-source-convergence-guard',
  null,
  'D2_FOUNDER_DIRECTIVE',
  null,
  'internal'
);

commit;
