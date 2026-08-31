-- CrownThrive PentaWire / PentaAssignment
-- Native bounded owner-review transport for existing PentaWire assignment handoffs.
--
-- This continues PR #2078 / #1899. It creates no new Penta, scheduler, certifier,
-- security authority, CHLOM authority or provider executor. The existing guarded
-- PentaWire clock consumes already-routed D0-D2 PentaWire assignment packets and may
-- record only a bounded PentaWire owner result after exact provider/runtime evidence.
-- PentaSecurity, CHLOM, CIE, independent PentaCertifier and release remain separate.

create or replace function integration_control.penta_wire_assignment_owner_review_v1(
  p_assignment_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','pentas','public','extensions'
as $fn$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  d integration_control.penta_assignment_dispatches_v1%rowtype;
  h integration_control.penta_census_handoffs_v1%rowtype;
  m integration_control.penta_production_mobilization_v1%rowtype;
  p pentas.packets_v2%rowtype;
  dl pentas.deliveries_v2%rowtype;
  o integration_control.penta_census_provider_observations_v1%rowtype;
  s integration_control.penta_wire_scan_receipts_v1%rowtype;
  b_main integration_control.penta_wire_service_bindings_v1%rowtype;
  b_repo integration_control.penta_wire_service_bindings_v1%rowtype;
  v_packet_verify jsonb;
  v_result jsonb;
  v_ack jsonb;
  v_evidence jsonb;
  v_existing boolean:=false;
  v_receipt_chain boolean:=false;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:wire:assignment-review:'||coalesce(p_assignment_id::text,''),0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','assignment_id',p_assignment_id,'authority_created',false);
  end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id;
  if not found then
    return jsonb_build_object('state','HOLD','reason','ASSIGNMENT_NOT_FOUND','assignment_id',p_assignment_id,'authority_created',false);
  end if;

  if not (a.owner_pentas ? 'PentaWire') then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_NOT_ASSIGNED_OWNER','assignment_id',a.assignment_id,'authority_created',false);
  end if;
  if a.risk_class not in ('D0','D1','D2') or a.authority_ceiling not in ('D0','D1','D2') or a.d3_human_reserved is not true
     or a.provider_write_allowed or a.money_movement_allowed or a.credential_change_allowed or a.authority_expansion then
    return jsonb_build_object('state','HOLD','reason','ASSIGNMENT_AUTHORITY_BOUNDARY','assignment_id',a.assignment_id,'authority_created',false);
  end if;
  if coalesce(a.exact_head_sha,'') !~ '^[0-9a-f]{40}$' or coalesce(a.exact_artifact_sha256,'') !~ '^[0-9a-f]{64}$' or a.source_pr_number is null then
    return jsonb_build_object('state','HOLD','reason','EXACT_SUBJECT_REQUIRED','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  select exists(
    select 1 from integration_control.penta_assignment_owner_results_v1 r
    where r.assignment_id=a.assignment_id and r.owner_penta='PentaWire' and r.result_state='PASS'
      and r.exact_head_sha=a.exact_head_sha and r.exact_artifact_sha256=a.exact_artifact_sha256
  ) into v_existing;
  if v_existing then
    return jsonb_build_object('state','PASS_DEDUPED','assignment_id',a.assignment_id,'exact_head_sha',a.exact_head_sha,'authority_created',false);
  end if;

  select * into d
  from integration_control.penta_assignment_dispatches_v1
  where assignment_id=a.assignment_id and owner_penta='PentaWire'
  order by created_at desc limit 1;
  if not found or d.dispatch_kind<>'CENSUS_HANDOFF' or d.state not in ('ROUTED','IN_PROGRESS') then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_DISPATCH_NOT_ROUTED','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  select * into h
  from integration_control.penta_census_handoffs_v1
  where handoff_key=d.external_ref;
  if not found or h.state not in ('acknowledged','in_progress') then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_HANDOFF_NOT_ACTIVE','assignment_id',a.assignment_id,'authority_created',false);
  end if;
  if h.payload->>'assignment_id' is distinct from a.assignment_id::text
     or h.payload->>'exact_head_sha' is distinct from a.exact_head_sha
     or h.payload->>'exact_artifact_sha256' is distinct from a.exact_artifact_sha256 then
    return jsonb_build_object('state','HOLD','reason','HANDOFF_EXACT_SUBJECT_MISMATCH','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  select * into m
  from integration_control.penta_production_mobilization_v1
  where handoff_key=h.handoff_key and packet_id is not null
  order by updated_at desc limit 1;
  if not found then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_PACKET_MISSING','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  select * into p from pentas.packets_v2 where packet_id=m.packet_id;
  select * into dl from pentas.deliveries_v2 where packet_id=m.packet_id and target_node_id='ct.penta.wire' order by routed_at desc limit 1;
  if p.packet_id is null or dl.delivery_id is null then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_PACKET_DELIVERY_MISSING','assignment_id',a.assignment_id,'authority_created',false);
  end if;
  if p.packet_type<>'institutional.production-reconciliation.request' or p.route_lane<>'penta.production.reconciliation'
     or p.target_ref<>'ct.penta.wire' or p.authority_class not in ('D0','D1','D2') or p.risk_class not in ('D0','D1','D2')
     or p.payload->>'handoff_key' is distinct from h.handoff_key or p.payload->>'entity_key' is distinct from a.assignment_key then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_PACKET_CONTRACT_MISMATCH','assignment_id',a.assignment_id,'packet_id',p.packet_id,'authority_created',false);
  end if;

  v_packet_verify:=pentas.verify_packet_v2(p.packet_id);
  if not coalesce((v_packet_verify->>'ok')::boolean,false) or coalesce((v_packet_verify->>'expired')::boolean,true)
     or not coalesce((v_packet_verify->>'signature_match')::boolean,false)
     or not coalesce((v_packet_verify->>'payload_hash_match')::boolean,false) then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_PACKET_VERIFICATION_FAILED','assignment_id',a.assignment_id,'packet_id',p.packet_id,'packet_verify',v_packet_verify,'authority_created',false);
  end if;

  select exists(
    select 1
    from pentas.receipts_v2 routed
    join pentas.receipts_v2 emitted on emitted.receipt_id=routed.previous_receipt_id and emitted.packet_id=routed.packet_id
    where routed.packet_id=p.packet_id
      and emitted.node_id='ct.penta.census' and emitted.receipt_type='emitted' and emitted.decision='accept'
      and routed.node_id='ct.penta.wire' and routed.receipt_type='routed' and routed.decision='pass'
      and emitted.evidence_sha256 ~ '^[0-9a-f]{64}$' and emitted.chain_sha256 ~ '^[0-9a-f]{64}$' and nullif(emitted.signature,'') is not null
      and routed.evidence_sha256 ~ '^[0-9a-f]{64}$' and routed.chain_sha256 ~ '^[0-9a-f]{64}$' and nullif(routed.signature,'') is not null
  ) into v_receipt_chain;
  if not v_receipt_chain then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_PACKET_RECEIPT_CHAIN_MISSING','assignment_id',a.assignment_id,'packet_id',p.packet_id,'authority_created',false);
  end if;

  select * into o
  from integration_control.penta_census_provider_observations_v1
  where lower(provider_system)='github' and resource_type='pull_request' and resource_id=a.source_pr_number::text
  order by observed_at desc limit 1;
  if not found or o.observed_at<now()-interval '2 hours' or o.evidence_sha256 !~ '^[0-9a-f]{64}$'
     or o.source_ref is distinct from ('github:'||a.source_repo||'#'||a.source_pr_number::text||'@'||a.exact_head_sha)
     or o.attributes->>'head_sha' is distinct from a.exact_head_sha
     or lower(coalesce(o.attributes->>'governed_merge_gate',''))<>'success'
     or lower(coalesce(o.attributes->>'security_governance',''))<>'success'
     or not coalesce((o.attributes->>'mergeable')::boolean,false)
     or coalesce((o.attributes->>'authority_created')::boolean,true)
     or coalesce((o.attributes->>'release_authority')::boolean,true) then
    return jsonb_build_object('state','HOLD','reason','GITHUB_EXACT_HEAD_PROVIDER_EVIDENCE_MISSING','assignment_id',a.assignment_id,'exact_head_sha',a.exact_head_sha,'authority_created',false);
  end if;

  select * into b_main from integration_control.penta_wire_service_bindings_v1 where service_id='github_main_perimeter';
  select * into b_repo from integration_control.penta_wire_service_bindings_v1 where service_id='github_repository_control';
  if b_main.service_id is null or b_main.gap_state<>'complete' or b_main.current_integration_state<>'read_verified'
     or b_main.last_probe_state<>'pass' or b_main.last_observed_at<now()-interval '2 hours'
     or b_repo.service_id is null or b_repo.gap_state<>'complete' or b_repo.current_integration_state<>'read_verified' then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_GITHUB_BINDING_NOT_VERIFIED','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  select * into s
  from integration_control.penta_wire_scan_receipts_v1
  where recorded_by_agent_id='ct.agent.penta-wire'
  order by observed_at desc,receipt_id desc limit 1;
  if not found or s.observed_at<now()-interval '30 minutes' or s.evidence_sha256 !~ '^[0-9a-f]{64}$' or s.tool_contract_drift_services<>0 then
    return jsonb_build_object('state','HOLD','reason','PENTAWIRE_FRESH_SCAN_REQUIRED','assignment_id',a.assignment_id,'authority_created',false);
  end if;

  v_evidence:=jsonb_build_object(
    'contract','ct.penta.wire.assignment-owner-review.v1',
    'assignment_id',a.assignment_id,
    'assignment_key',a.assignment_key,
    'source_repo',a.source_repo,
    'source_pr_number',a.source_pr_number,
    'exact_head_sha',a.exact_head_sha,
    'exact_artifact_ref',a.exact_artifact_ref,
    'exact_artifact_sha256',a.exact_artifact_sha256,
    'github_observation_key',o.observation_key,
    'github_evidence_sha256',o.evidence_sha256,
    'github_observed_at',o.observed_at,
    'github_main_perimeter_evidence_sha256',b_main.evidence_sha256,
    'github_repository_control_evidence_sha256',b_repo.evidence_sha256,
    'penta_wire_scan_receipt_id',s.receipt_id,
    'penta_wire_scan_evidence_sha256',s.evidence_sha256,
    'penta_wire_scan_state',s.result_state,
    'unrelated_provider_contract_holds',s.provider_contract_holds,
    'tool_contract_drift_services',s.tool_contract_drift_services,
    'packet_id',p.packet_id,
    'packet_verify',v_packet_verify,
    'receipt_chain_bound',v_receipt_chain,
    'review_scope','transport_and_exact-provider-readback-only',
    'security_decision',false,
    'chlom_rights_decision',false,
    'cie_decision',false,
    'independent_certification',false,
    'provider_write',false,
    'credential_change',false,
    'money_movement',false,
    'd3_execution',false,
    'authority_expansion',false,
    'reviewed_at',clock_timestamp()
  );

  v_result:=integration_control.penta_assignment_record_owner_result_v1(
    a.assignment_id,'PentaWire','PASS',a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,v_evidence
  );

  v_ack:=pentas.ack_v2(
    p.packet_id,'ct.penta.wire','complete',
    jsonb_build_object(
      'assignment_id',a.assignment_id,
      'owner_result_evidence_sha256',v_result->>'evidence_sha256',
      'exact_head_sha',a.exact_head_sha,
      'exact_artifact_sha256',a.exact_artifact_sha256,
      'authority_created',false
    ),true
  );

  perform integration_control.penta_census_mobilization_reconcile_v1(250);

  return jsonb_build_object(
    'state','PASS','assignment_id',a.assignment_id,'exact_head_sha',a.exact_head_sha,
    'owner_result',v_result,'packet_ack',v_ack,
    'security_decision',false,'independent_certification',false,'authority_created',false
  );
end
$fn$;

create or replace function integration_control.penta_wire_assignment_owner_review_tick_v1(p_limit integer default 5)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $fn$
declare
  r record;
  v_limit integer:=greatest(1,least(coalesce(p_limit,5),25));
  v_result jsonb;
  v_results jsonb:='[]'::jsonb;
  v_pass integer:=0;
  v_hold integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role' then
    raise exception 'service_role_required';
  end if;
  for r in
    select distinct d.assignment_id
    from integration_control.penta_assignment_dispatches_v1 d
    join integration_control.penta_assignment_contracts_v1 a on a.assignment_id=d.assignment_id
    where d.owner_penta='PentaWire' and d.dispatch_kind='CENSUS_HANDOFF' and d.state in ('ROUTED','IN_PROGRESS')
      and a.state not in ('COMPLETED','SUPERSEDED','RETIRED','FAILED')
    order by d.assignment_id
    limit v_limit
  loop
    begin
      v_result:=integration_control.penta_wire_assignment_owner_review_v1(r.assignment_id);
    exception when others then
      v_result:=jsonb_build_object('state','HOLD','reason','PENTAWIRE_REVIEW_RUNTIME_ERROR','error_class',sqlstate,'authority_created',false);
    end;
    if v_result->>'state' in ('PASS','PASS_DEDUPED') then v_pass:=v_pass+1; else v_hold:=v_hold+1; end if;
    v_results:=v_results||jsonb_build_array(v_result);
  end loop;
  return jsonb_build_object('contract','ct.penta.wire.assignment-owner-review.tick.v1','processed',jsonb_array_length(v_results),'pass',v_pass,'hold',v_hold,'results',v_results,'authority_created',false,'observed_at',clock_timestamp());
end
$fn$;

-- Reuse the existing guarded PentaWire Pentatime slot; no new clock is introduced.
create or replace function pentatime.executor_penta_wire_v3()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control'
as $fn$
declare
  v_healer jsonb;
  v_assignment_review jsonb;
begin
  v_healer:=public.penta_wire_autonomous_gap_healer_v1();
  v_assignment_review:=integration_control.penta_wire_assignment_owner_review_tick_v1(5);
  return jsonb_build_object(
    'service','ct.penta.wire.executor.v3',
    'healer',v_healer,
    'assignment_owner_review',v_assignment_review,
    'new_clock_created',false,
    'security_decision',false,
    'independent_certification',false,
    'authority_created',false,
    'observed_at',clock_timestamp()
  );
end
$fn$;

revoke all on function integration_control.penta_wire_assignment_owner_review_v1(uuid) from public,anon,authenticated;
revoke all on function integration_control.penta_wire_assignment_owner_review_tick_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.penta_wire_assignment_owner_review_v1(uuid) to service_role;
grant execute on function integration_control.penta_wire_assignment_owner_review_tick_v1(integer) to service_role;

comment on function integration_control.penta_wire_assignment_owner_review_v1(uuid)
is 'Bounded PentaWire owner review of an existing D0-D2 assignment transport using exact GitHub provider evidence, signed Penta packet evidence and current PentaWire readback. It does not issue PentaSecurity, CHLOM, CIE, certification or release authority.';
