-- PentaHelp independent-gate exact-review node bootstrap v1.
--
-- Purpose: register bounded Penta v2 execution addresses for the existing independent
-- PentaSecurity / CHLOM / CIE review authorities and expose a deterministic packet preflight.
-- These nodes are transport/execution addresses only. They create NO disposition, authority,
-- provider write, credential operation, money movement, rights grant, vote/quorum effect or D3.
-- The independent authority remains the existing PentaSecurity / CHLOM / CIE owner.

create or replace function public.penta_help_independent_gate_review_preflight_v1(
  p_packet_id uuid,
  p_target_node_id text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_help','pentas'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  p pentas.packets_v2%rowtype;
  q penta_help.requests_v1%rowtype;
  v_verify jsonb;
  v_request_id uuid;
  v_owner text;
  v_expected_target text;
  v_state text:='READY_FOR_INDEPENDENT_REVIEW';
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  if p_target_node_id not in ('ct.penta.security','ct.penta.chlom-review','ct.penta.cie-review','ct.penta.certify') then
    return jsonb_build_object(
      'contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_TARGET_NODE_NOT_ALLOWED',
      'target_node_id',p_target_node_id,
      'gate_disposition_created',false,
      'authority_created',false);
  end if;

  select * into p from pentas.packets_v2 where packet_id=p_packet_id;
  if not found then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_PACKET_NOT_FOUND','packet_id',p_packet_id,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  v_verify:=pentas.verify_packet_v2(p_packet_id);
  if not coalesce((v_verify->>'ok')::boolean,false) or coalesce((v_verify->>'expired')::boolean,false) then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_PACKET_VERIFICATION_FAILED','packet_id',p_packet_id,
      'verification',v_verify,'gate_disposition_created',false,'authority_created',false);
  end if;

  if p.packet_type<>'institutional.independent-gate.review.request' then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_PACKET_TYPE_MISMATCH','packet_id',p_packet_id,
      'packet_type',p.packet_type,'gate_disposition_created',false,'authority_created',false);
  end if;

  if p.target_mode<>'direct' or p.target_ref<>p_target_node_id then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_PACKET_TARGET_MISMATCH','packet_id',p_packet_id,
      'target_mode',p.target_mode,'target_ref',p.target_ref,'expected_target',p_target_node_id,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  if p.risk_class not in ('D0','D1','D2') or p.authority_class not in ('D0','D1','D2') then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_AUTHORITY_CLASS_OUT_OF_SCOPE','packet_id',p_packet_id,
      'risk_class',p.risk_class,'authority_class',p.authority_class,
      'd3_execution',false,'gate_disposition_created',false,'authority_created',false);
  end if;

  begin
    v_request_id:=nullif(p.payload->>'request_id','')::uuid;
  exception when others then
    v_request_id:=null;
  end;
  if v_request_id is null then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_REQUEST_ID_INVALID','packet_id',p_packet_id,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  select * into q from penta_help.requests_v1 where request_id=v_request_id;
  if not found then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_REQUEST_NOT_FOUND','packet_id',p_packet_id,'request_id',v_request_id,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  if q.blocker_class<>'independent_gate' or q.risk_class not in ('D0','D1','D2') then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_REQUEST_SCOPE_MISMATCH','packet_id',p_packet_id,'request_id',v_request_id,
      'blocker_class',q.blocker_class,'risk_class',q.risk_class,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  if q.state in ('resolved','retired','expired','waiting_human') then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_REQUEST_NOT_REVIEWABLE','packet_id',p_packet_id,'request_id',v_request_id,
      'request_state',q.state,'gate_disposition_created',false,'authority_created',false);
  end if;

  if q.source_ref<>coalesce(p.payload->>'source_ref','') then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_EXACT_SUBJECT_MISMATCH','packet_id',p_packet_id,'request_id',v_request_id,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  if coalesce(q.context->>'exact_head_sha','')<>coalesce(p.payload->>'exact_head_sha','') then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_EXACT_HEAD_MISMATCH','packet_id',p_packet_id,'request_id',v_request_id,
      'request_head',q.context->>'exact_head_sha','packet_head',p.payload->>'exact_head_sha',
      'gate_disposition_created',false,'authority_created',false);
  end if;

  v_owner:=lower(coalesce(nullif(q.context->>'requested_owner',''),p.payload->>'requested_owner',''));
  v_expected_target:=case
    when v_owner in ('penta.certify','pentacertify','penta certifier','pentacertifier') then 'ct.penta.certify'
    when v_owner in ('penta.security','pentasecurity') then 'ct.penta.security'
    when v_owner in ('chlom','chlom_core','chlom core') then 'ct.penta.chlom-review'
    when v_owner in ('cie','ct.framework.cultural-imprint-engine','cultural imprint engine') then 'ct.penta.cie-review'
    else null
  end;
  if v_expected_target is null or v_expected_target<>p_target_node_id then
    return jsonb_build_object('contract','ct.penta.help.independent-gate-review-preflight.v1',
      'state','HOLD_INDEPENDENT_OWNER_TARGET_MISMATCH','packet_id',p_packet_id,'request_id',v_request_id,
      'requested_owner',v_owner,'expected_target',v_expected_target,'actual_target',p_target_node_id,
      'gate_disposition_created',false,'authority_created',false);
  end if;

  if coalesce(q.context->>'originator_system_key',q.requester_system_key,'') in
       ('penta.security','chlom','cie','penta.certify',p_target_node_id) then
    v_state:='HOLD_ORIGINATOR_INDEPENDENCE_UNPROVEN';
  end if;

  return jsonb_build_object(
    'contract','ct.penta.help.independent-gate-review-preflight.v1',
    'state',v_state,
    'packet_id',p_packet_id,
    'request_id',v_request_id,
    'target_node_id',p_target_node_id,
    'requested_owner',v_owner,
    'source_ref',q.source_ref,
    'exact_head_sha',q.context->>'exact_head_sha',
    'packet_verified',true,
    'independent_review_required',true,
    'gate_disposition_created',false,
    'authority_created',false,
    'provider_write',false,
    'credential_change',false,
    'money_movement',false,
    'rights_grant',false,
    'vote_effect',false,
    'quorum_effect',false,
    'd3_execution',false,
    'observed_at',clock_timestamp());
end
$function$;

revoke all on function public.penta_help_independent_gate_review_preflight_v1(uuid,text)
  from public,anon,authenticated;
grant execute on function public.penta_help_independent_gate_review_preflight_v1(uuid,text)
  to service_role;

-- Register only missing packet execution addresses. Never overwrite a native node that a
-- canonical owner has already registered. The metadata marker makes rollback collision-safe.
insert into pentas.nodes_v2(
  node_id,display_name,node_class,authority_ceiling,capabilities,topics,endpoint_kind,endpoint_ref,
  health_state,lifecycle_state,queue_depth,metadata)
select
  'ct.penta.security','PentaSecurity Exact-Review Transport','governance','D2',
  array['institutional.independent-gate.review','security.review.transport']::text[],
  array['security','independent-review']::text[],
  'internal_sql','public.penta_help_independent_gate_review_preflight_v1(uuid,text)',
  'healthy','active',0,
  jsonb_build_object(
    'contract','ct.penta.help.independent-gate-review-nodes.v1',
    'introduced_by','ct.penta.help.independent-gate-review-nodes.v1',
    'canonical_owner','penta.security','transport_only',true,'disposition_authority',false,
    'authority_created',false,'d3_human_reserved',true)
where not exists(select 1 from pentas.nodes_v2 where node_id='ct.penta.security');

insert into pentas.nodes_v2(
  node_id,display_name,node_class,authority_ceiling,capabilities,topics,endpoint_kind,endpoint_ref,
  health_state,lifecycle_state,queue_depth,metadata)
select
  'ct.penta.chlom-review','CHLOM Exact-Review Transport','governance','D2',
  array['institutional.independent-gate.review','chlom.authority-rights.review.transport']::text[],
  array['chlom','rights','authority','independent-review']::text[],
  'internal_sql','public.penta_help_independent_gate_review_preflight_v1(uuid,text)',
  'healthy','active',0,
  jsonb_build_object(
    'contract','ct.penta.help.independent-gate-review-nodes.v1',
    'introduced_by','ct.penta.help.independent-gate-review-nodes.v1',
    'canonical_owner','CHLOM','transport_only',true,'disposition_authority',false,
    'authority_created',false,'d3_human_reserved',true)
where not exists(select 1 from pentas.nodes_v2 where node_id='ct.penta.chlom-review');

insert into pentas.nodes_v2(
  node_id,display_name,node_class,authority_ceiling,capabilities,topics,endpoint_kind,endpoint_ref,
  health_state,lifecycle_state,queue_depth,metadata)
select
  'ct.penta.cie-review','CIE Exact-Review Transport','governance','D2',
  array['institutional.independent-gate.review','cie.applicability.review.transport']::text[],
  array['cie','cultural-imprint','independent-review']::text[],
  'internal_sql','public.penta_help_independent_gate_review_preflight_v1(uuid,text)',
  'healthy','active',0,
  jsonb_build_object(
    'contract','ct.penta.help.independent-gate-review-nodes.v1',
    'introduced_by','ct.penta.help.independent-gate-review-nodes.v1',
    'canonical_owner','CIE','transport_only',true,'disposition_authority',false,
    'authority_created',false,'d3_human_reserved',true)
where not exists(select 1 from pentas.nodes_v2 where node_id='ct.penta.cie-review');

comment on function public.penta_help_independent_gate_review_preflight_v1(uuid,text) is
'Validates exact PentaHelp independent-gate packets for native review-node consumption. READY_FOR_INDEPENDENT_REVIEW is transport readiness only and never PASS/certification.';
