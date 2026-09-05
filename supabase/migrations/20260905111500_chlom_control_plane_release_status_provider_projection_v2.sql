-- CHLOM control-plane release projection v2
-- Repair: stop presenting hard-coded gateway/dispatcher identity as live release truth.
-- The status function now projects the latest governed gateway deployment receipt.

create or replace function public.chlom_control_plane_release_status_v1()
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, chlom_protocol, public
as $function$
declare
  v_canary chlom_protocol.api_idempotency_records_v1%rowtype;
  v_gateway chlom_protocol.gateway_deployment_versions_v1%rowtype;
  v_dail jsonb;
  v_protocol jsonb;
  v_active_operator_count bigint;
  v_dispatch_count bigint;
  v_idempotency_count bigint;
  v_dispatcher_contract text;
  v_database_dispatch text;
  v_projection_state text;
begin
  select r.* into v_canary
  from chlom_protocol.api_idempotency_records_v1 r
  where r.action = 'control_plane_canary'
  order by r.recorded_at desc
  limit 1;

  select g.* into v_gateway
  from chlom_protocol.gateway_deployment_versions_v1 g
  where g.gateway_subject_id = 'ct.gateway.chlom-authenticated-gateway-v1'
    and g.function_slug = 'chlom-control-plane-v1'
  order by g.version desc, g.recorded_at desc
  limit 1;

  select count(*) into v_active_operator_count
  from chlom_protocol.current_api_operators_v1 o
  where o.active;

  select count(*) into v_dispatch_count
  from chlom_protocol.api_dispatch_receipts_v1;

  select count(*) into v_idempotency_count
  from chlom_protocol.api_idempotency_records_v1;

  v_dail := public.chlom_dail_assurance_status_v4();
  v_protocol := public.chlom_protocol_status_v1();

  v_dispatcher_contract := nullif(v_gateway.evidence->>'dispatcher_contract', '');
  v_database_dispatch := case v_dispatcher_contract
    when 'ct.chlom.authenticated-control-plane-dispatch.v3'
      then 'public.chlom_api_dispatch_v3(text,jsonb,text)'
    when 'ct.chlom.authenticated-control-plane-dispatch.v2'
      then 'public.chlom_api_dispatch_v2(text,jsonb,text)'
    when 'ct.chlom.authenticated-control-plane-dispatch.v1'
      then 'public.chlom_api_dispatch_v1(text,jsonb)'
    else null
  end;

  v_projection_state := case
    when v_gateway.version is null then 'HOLD_NO_GATEWAY_DEPLOYMENT_RECORD'
    when v_gateway.provider_state is distinct from 'ACTIVE' then 'HOLD_PROVIDER_NOT_ACTIVE'
    when v_gateway.provider_readback is distinct from true then 'HOLD_PROVIDER_READBACK_REQUIRED'
    when v_gateway.verify_jwt is distinct from true then 'HOLD_PROVIDER_JWT_REQUIRED'
    when v_dispatcher_contract is null or v_database_dispatch is null then 'HOLD_DISPATCHER_IDENTITY_UNRESOLVED'
    when coalesce(v_gateway.source_sha256, '') = '' then 'HOLD_PROVIDER_SOURCE_DIGEST_REQUIRED'
    when coalesce(v_gateway.deployment_manifest_sha256, '') = '' then 'HOLD_DEPLOYMENT_MANIFEST_REQUIRED'
    else 'CURRENT_RECORDED_PROVIDER_RELEASE'
  end;

  return jsonb_build_object(
    'ok', v_projection_state = 'CURRENT_RECORDED_PROVIDER_RELEASE',
    'contract', 'ct.chlom.control-plane-release-status.v1',
    'projection_contract', 'ct.chlom.control-plane-release-provider-projection.v2',
    'projection_state', v_projection_state,
    'service', 'CHLOM authenticated control plane',
    'canonical_expansion', 'Compliance Hybrid Licensing and Ownership Model',
    'production_control_plane', true,
    'gateway', case
      when v_gateway.version is null then jsonb_build_object(
        'state', 'HOLD_NO_GATEWAY_DEPLOYMENT_RECORD',
        'slug', 'chlom-control-plane-v1'
      )
      else jsonb_build_object(
        'slug', v_gateway.function_slug,
        'version', coalesce(nullif(v_gateway.evidence->>'gateway_version', ''), v_gateway.version::text),
        'deployment_registry_version', v_gateway.version,
        'jwt_required', v_gateway.verify_jwt,
        'database_dispatch', v_database_dispatch,
        'database_capabilities', 'public.chlom_api_capabilities_v1()',
        'dispatcher_contract', v_dispatcher_contract,
        'provider', v_gateway.provider,
        'provider_state', v_gateway.provider_state,
        'provider_readback', v_gateway.provider_readback,
        'provider_function_id', v_gateway.evidence->>'provider_function_id',
        'provider_function_version', coalesce(
          nullif(v_gateway.evidence->>'provider_function_version', ''),
          nullif(v_gateway.evidence->>'provider_version', '')
        ),
        'source_sha256', v_gateway.source_sha256,
        'deployment_manifest_sha256', v_gateway.deployment_manifest_sha256,
        'signed_session_canary_state', v_gateway.signed_session_canary_state,
        'unauthenticated_boundary_state', v_gateway.unauthenticated_boundary_state,
        'recorded_at', v_gateway.recorded_at
      )
    end,
    'operator_registry', jsonb_build_object(
      'active_operator_count', v_active_operator_count,
      'append_only', true,
      'raw_credentials_recorded', false
    ),
    'dispatch', jsonb_build_object(
      'receipt_count', v_dispatch_count,
      'idempotency_record_count', v_idempotency_count,
      'idempotency_enforced_for_mutations', true,
      'conflicting_key_reuse_fails_closed', true
    ),
    'latest_control_plane_canary', case when v_canary.record_hash is null then
      jsonb_build_object('state', 'NOT_YET_RECORDED')
    else jsonb_build_object(
      'state', coalesce(v_canary.result->>'state', 'RECORDED'),
      'contract', v_canary.result->>'contract',
      'record_hash', v_canary.record_hash,
      'request_sha256', v_canary.request_sha256,
      'result_sha256', v_canary.result_sha256,
      'dispatch_receipt_id', v_canary.dispatch_receipt_id,
      'dail_sequence_id', v_canary.dail_sequence_id,
      'dail_event_hash', v_canary.dail_event_hash,
      'recorded_at', v_canary.recorded_at
    ) end,
    'dail', v_dail,
    'protocol', jsonb_build_object(
      'contract', v_protocol->>'contract',
      'production_control_plane', coalesce((v_protocol->>'production_control_plane')::boolean, false),
      'external_l1_state', v_protocol->>'external_l1_state',
      'money_movement_count', coalesce((v_protocol->>'money_movement_count')::bigint, 0),
      'external_production_mint_confirmed_count', coalesce((v_protocol->>'external_production_mint_confirmed_count')::bigint, 0)
    ),
    'explicitly_excluded_actions', jsonb_build_array(
      'external_money_movement',
      'production_token_mint_confirmation',
      'tokenomics_activation',
      'validator_activation',
      'public_chain_anchor_confirmation',
      'legal_title_adjudication'
    ),
    'external_execution_enabled', false,
    'observed_at', clock_timestamp()
  );
end
$function$;

comment on function public.chlom_control_plane_release_status_v1()
is 'Provider-grounded CHLOM control-plane release projection. Reads latest governed gateway deployment receipt; never treats a hard-coded semantic version or dispatcher as current provider truth.';
