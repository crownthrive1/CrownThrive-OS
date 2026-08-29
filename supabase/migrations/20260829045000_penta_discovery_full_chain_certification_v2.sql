begin;

create extension if not exists pgcrypto with schema extensions;

create table if not exists penta_runtime.penta_discovery_runtime_receipts_v2 (
  receipt_id uuid primary key default gen_random_uuid(),
  receipt_key text not null unique,
  runtime_component text not null,
  runtime_surface text not null,
  runtime_version text not null,
  stable_contract_version text not null default '1.0.0',
  economic_version text not null default '2.0.0',
  packet_protocol_version text not null default '3.0.0',
  deployment_version integer,
  artifact_sha256 text not null check (artifact_sha256 ~ '^[0-9a-f]{64}$'),
  source_control_ref text,
  status text not null check (status in ('active','degraded','retired')),
  verify_jwt boolean not null default false,
  custom_auth boolean not null default false,
  security_state text not null,
  readback jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  observed_at timestamptz not null default now(),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  check (expires_at > observed_at)
);

comment on table penta_runtime.penta_discovery_runtime_receipts_v2 is
'Append-only readback evidence for PentaDiscovery family runtime surfaces. A receipt is evidence, not authority.';

alter table penta_runtime.penta_discovery_runtime_receipts_v2 enable row level security;

create table if not exists penta_runtime.penta_discovery_certifications_v2 (
  certification_id uuid primary key default gen_random_uuid(),
  certification_key text not null unique,
  release_version text not null,
  source_control_ref text,
  stable_contract_version text not null,
  economic_version text not null,
  packet_protocol_version text not null,
  verdict text not null check (verdict in ('PASS','HOLD','FAIL')),
  checks jsonb not null,
  canary_packet_id uuid,
  canary_binding_id uuid,
  canary_receipt_id uuid,
  provider_canary_receipt_id uuid,
  runtime_receipt_ids jsonb not null default '[]'::jsonb,
  independent_verifier_ref text not null,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  dail_event_id uuid,
  certified_at timestamptz not null default now(),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  check (expires_at > certified_at)
);

comment on table penta_runtime.penta_discovery_certifications_v2 is
'Append-only whole-chain certification for PentaDiscovery, Penta packet routing, Smart Treasury, PentaPay and CHLOM/DAIL.';

alter table penta_runtime.penta_discovery_certifications_v2 enable row level security;

create or replace function penta_runtime.reject_penta_discovery_assurance_mutation_v2()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  raise exception 'PENTA_DISCOVERY_ASSURANCE_APPEND_ONLY';
end
$$;

drop trigger if exists penta_discovery_runtime_receipts_append_only_v2
  on penta_runtime.penta_discovery_runtime_receipts_v2;
create trigger penta_discovery_runtime_receipts_append_only_v2
before update or delete on penta_runtime.penta_discovery_runtime_receipts_v2
for each row execute function penta_runtime.reject_penta_discovery_assurance_mutation_v2();

drop trigger if exists penta_discovery_certifications_append_only_v2
  on penta_runtime.penta_discovery_certifications_v2;
create trigger penta_discovery_certifications_append_only_v2
before update or delete on penta_runtime.penta_discovery_certifications_v2
for each row execute function penta_runtime.reject_penta_discovery_assurance_mutation_v2();

revoke all on table penta_runtime.penta_discovery_runtime_receipts_v2 from public, anon, authenticated;
revoke all on table penta_runtime.penta_discovery_certifications_v2 from public, anon, authenticated;

create or replace function penta_runtime.record_penta_discovery_runtime_receipt_v2(
  p_runtime_component text,
  p_runtime_surface text,
  p_runtime_version text,
  p_deployment_version integer,
  p_artifact_sha256 text,
  p_source_control_ref text,
  p_status text,
  p_verify_jwt boolean,
  p_custom_auth boolean,
  p_security_state text,
  p_readback jsonb,
  p_observed_at timestamptz default now(),
  p_ttl interval default interval '24 hours'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, extensions
as $$
declare
  v_receipt_id uuid;
  v_receipt_key text;
  v_evidence_sha256 text;
  v_expires_at timestamptz;
begin
  if session_user <> 'postgres' and coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'SERVICE_ROLE_REQUIRED';
  end if;
  if nullif(btrim(p_runtime_component), '') is null
     or nullif(btrim(p_runtime_surface), '') is null
     or nullif(btrim(p_runtime_version), '') is null then
    raise exception 'RUNTIME_IDENTITY_REQUIRED';
  end if;
  if p_artifact_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'INVALID_ARTIFACT_SHA256';
  end if;
  if p_status not in ('active','degraded','retired') then
    raise exception 'INVALID_RUNTIME_STATUS';
  end if;
  if p_ttl <= interval '0 seconds' or p_ttl > interval '7 days' then
    raise exception 'INVALID_RUNTIME_RECEIPT_TTL';
  end if;

  v_expires_at := p_observed_at + p_ttl;
  v_receipt_key := p_runtime_component || ':' || p_runtime_surface || ':' ||
    p_artifact_sha256 || ':' || coalesce(p_deployment_version, 0)::text || ':' ||
    extract(epoch from p_observed_at)::bigint::text;
  v_evidence_sha256 := encode(
    digest(
      concat_ws('|',
        v_receipt_key,
        p_runtime_version,
        coalesce(p_source_control_ref, ''),
        p_status,
        p_verify_jwt::text,
        p_custom_auth::text,
        p_security_state,
        coalesce(p_readback, '{}'::jsonb)::text,
        v_expires_at::text
      ),
      'sha256'
    ),
    'hex'
  );

  insert into penta_runtime.penta_discovery_runtime_receipts_v2 (
    receipt_key, runtime_component, runtime_surface, runtime_version,
    deployment_version, artifact_sha256, source_control_ref, status,
    verify_jwt, custom_auth, security_state, readback, evidence_sha256,
    observed_at, expires_at
  )
  values (
    v_receipt_key, p_runtime_component, p_runtime_surface, p_runtime_version,
    p_deployment_version, p_artifact_sha256, p_source_control_ref, p_status,
    p_verify_jwt, p_custom_auth, p_security_state, coalesce(p_readback, '{}'::jsonb),
    v_evidence_sha256, p_observed_at, v_expires_at
  )
  on conflict (receipt_key) do nothing
  returning receipt_id into v_receipt_id;

  if v_receipt_id is null then
    select receipt_id into v_receipt_id
    from penta_runtime.penta_discovery_runtime_receipts_v2
    where receipt_key = v_receipt_key;
  end if;

  return jsonb_build_object(
    'recorded', true,
    'receipt_id', v_receipt_id,
    'receipt_key', v_receipt_key,
    'evidence_sha256', v_evidence_sha256,
    'expires_at', v_expires_at,
    'authority_created', false
  );
end
$$;

create or replace function penta_runtime.certify_settlement_provider_edges_v2(
  p_release_version text,
  p_edge_function_id text,
  p_edge_bundle_sha256 text,
  p_independent_verifier_ref text default 'PentaCertify'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, chlom_runtime, extensions
as $$
declare
  v_adapter penta_runtime.settlement_provider_adapters_v2%rowtype;
  v_checks jsonb;
  v_pass boolean;
  v_key text;
  v_hash text;
  v_certification_id uuid;
  v_dail jsonb;
  v_results jsonb := '[]'::jsonb;
  v_certified_at timestamptz;
begin
  if session_user <> 'postgres' and coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'SERVICE_ROLE_REQUIRED';
  end if;
  if p_edge_bundle_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'INVALID_EDGE_BUNDLE_SHA256';
  end if;

  for v_adapter in
    select *
    from penta_runtime.settlement_provider_adapters_v2
    where enabled
    order by adapter_key
  loop
    v_certification_id := gen_random_uuid();
    v_certified_at := now();
    v_checks := jsonb_build_object(
      'adapter_key', v_adapter.adapter_key,
      'provider_key', v_adapter.provider_key,
      'environment', v_adapter.environment,
      'edge_function_id', p_edge_function_id,
      'edge_bundle_sha256', p_edge_bundle_sha256,
      'adapter_enabled', v_adapter.enabled,
      'adapter_certification_state', v_adapter.certification_state,
      'money_movement_mode', v_adapter.money_movement_mode,
      'max_unattended_value_minor', v_adapter.max_unattended_value_minor,
      'requires_exact_ecac', v_adapter.requires_exact_ecac,
      'requires_independent_approval', v_adapter.requires_independent_approval,
      'requires_provider_readback', v_adapter.requires_provider_readback,
      'credential_ref_present', nullif(btrim(coalesce(v_adapter.credential_ref, '')), '') is not null,
      'dispatch_action_present', nullif(btrim(coalesce(v_adapter.dispatch_action, '')), '') is not null,
      'readback_action_present', nullif(btrim(coalesce(v_adapter.readback_action, '')), '') is not null,
      'provider_write_performed', false,
      'external_recipient_used', false,
      'economic_effect', 'certification_only'
    );

    v_pass :=
      v_adapter.enabled
      and v_adapter.certification_state = 'ready'
      and v_adapter.money_movement_mode = 'exact_authority_only'
      and v_adapter.max_unattended_value_minor = 0
      and v_adapter.requires_exact_ecac
      and v_adapter.requires_independent_approval
      and v_adapter.requires_provider_readback
      and nullif(btrim(coalesce(v_adapter.credential_ref, '')), '') is not null
      and nullif(btrim(coalesce(v_adapter.dispatch_action, '')), '') is not null
      and nullif(btrim(coalesce(v_adapter.readback_action, '')), '') is not null;

    v_key := 'penta-settlement-edge-cert:' || v_adapter.adapter_key || ':' ||
      encode(digest(concat_ws('|', p_release_version, p_edge_function_id,
        p_edge_bundle_sha256, v_adapter.adapter_key, p_independent_verifier_ref,
        v_certified_at::text), 'sha256'), 'hex');
    v_hash := encode(digest(concat_ws('|', v_key, v_checks::text), 'sha256'), 'hex');

    v_dail := chlom_runtime.append_dail_event(
      'penta.settlement.provider-edge.certified',
      'settlement_provider_edge',
      v_certification_id::text,
      jsonb_build_object(
        'adapter_key', v_adapter.adapter_key,
        'release_version', p_release_version,
        'verdict', case when v_pass then 'PASS' else 'HOLD' end,
        'checks', v_checks,
        'evidence_sha256', v_hash,
        'provider_write_performed', false,
        'money_movement_authority_created', false
      ),
      p_independent_verifier_ref,
      null,
      p_independent_verifier_ref,
      '2.0.0',
      v_adapter.adapter_key,
      null,
      'exact-authority-provider-edge-certification-no-provider-write',
      null,
      'restricted'
    );

    v_checks := v_checks || jsonb_build_object('dail_event_id', v_dail->>'event_id');
    v_hash := encode(digest(concat_ws('|', v_key, v_checks::text), 'sha256'), 'hex');

    insert into penta_runtime.settlement_provider_edge_certifications_v2 (
      certification_id, certification_key, adapter_key, release_version, verdict,
      exact_authority_dispatch_ready, provider_write_performed, checks,
      evidence_sha256, certified_at, expires_at
    )
    values (
      v_certification_id, v_key, v_adapter.adapter_key, p_release_version,
      case when v_pass then 'PASS' else 'HOLD' end,
      v_pass, false, v_checks, v_hash, v_certified_at,
      v_certified_at + interval '24 hours'
    );

    v_results := v_results || jsonb_build_array(jsonb_build_object(
      'adapter_key', v_adapter.adapter_key,
      'certification_id', v_certification_id,
      'verdict', case when v_pass then 'PASS' else 'HOLD' end,
      'evidence_sha256', v_hash,
      'provider_write_performed', false
    ));
  end loop;

  return jsonb_build_object(
    'release_version', p_release_version,
    'certifications', v_results,
    'certification_count', jsonb_array_length(v_results),
    'provider_write_performed', false,
    'authority_created', false
  );
end
$$;

create or replace function penta_runtime.certify_settlement_fabric_v2(
  p_release_version text,
  p_edge_function_id text,
  p_edge_bundle_sha256 text,
  p_independent_verifier_ref text default 'PentaCertify'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, chlom_runtime, extensions
as $$
declare
  v_adapter_count integer;
  v_ready_adapter_count integer;
  v_current_edge_count integer;
  v_rls_count integer;
  v_checks jsonb;
  v_pass boolean;
  v_key text;
  v_hash text;
  v_dail jsonb;
  v_certification_id uuid := gen_random_uuid();
  v_certified_at timestamptz := now();
  v_expires_at timestamptz := now() + interval '24 hours';
begin
  if session_user <> 'postgres' and coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'SERVICE_ROLE_REQUIRED';
  end if;
  if p_edge_bundle_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'INVALID_EDGE_BUNDLE_SHA256';
  end if;

  select count(*),
         count(*) filter (
           where certification_state = 'ready'
             and money_movement_mode = 'exact_authority_only'
             and max_unattended_value_minor = 0
             and requires_exact_ecac
             and requires_independent_approval
             and requires_provider_readback
         )
    into v_adapter_count, v_ready_adapter_count
  from penta_runtime.settlement_provider_adapters_v2
  where enabled;

  select count(distinct c.adapter_key)
    into v_current_edge_count
  from penta_runtime.settlement_provider_edge_certifications_v2 c
  join penta_runtime.settlement_provider_adapters_v2 a
    on a.adapter_key = c.adapter_key and a.enabled
  where c.verdict = 'PASS'
    and c.exact_authority_dispatch_ready
    and c.expires_at > now();

  select count(*)
    into v_rls_count
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where c.relrowsecurity
    and n.nspname = 'penta_runtime'
    and c.relname in (
      'settlement_provider_adapters_v2',
      'settlement_authority_grants_v2',
      'settlement_intents_v2',
      'settlement_attempts_v2',
      'settlement_provider_edge_certifications_v2',
      'settlement_fabric_certifications_v2'
    );

  v_checks := jsonb_build_object(
    'adapter_count', v_adapter_count,
    'ready_adapter_count', v_ready_adapter_count,
    'current_provider_edge_certifications', v_current_edge_count,
    'rls_protected_surfaces', v_rls_count,
    'edge_function_id', p_edge_function_id,
    'edge_bundle_sha256', p_edge_bundle_sha256,
    'all_enabled_adapters_ready', v_adapter_count > 0 and v_ready_adapter_count = v_adapter_count,
    'all_enabled_adapters_edge_certified', v_current_edge_count = v_adapter_count,
    'exact_ecac_required', not exists (
      select 1 from penta_runtime.settlement_provider_adapters_v2
      where enabled and not requires_exact_ecac
    ),
    'independent_approval_required', not exists (
      select 1 from penta_runtime.settlement_provider_adapters_v2
      where enabled and not requires_independent_approval
    ),
    'provider_readback_required', not exists (
      select 1 from penta_runtime.settlement_provider_adapters_v2
      where enabled and not requires_provider_readback
    ),
    'unattended_value_violations', (
      select count(*) from penta_runtime.settlement_provider_adapters_v2
      where enabled and max_unattended_value_minor <> 0
    ),
    'live_exact_authority_violations', (
      select count(*) from penta_runtime.settlement_provider_adapters_v2
      where enabled and money_movement_mode <> 'exact_authority_only'
    ),
    'settled_finality_violations', (
      select count(*) from penta_runtime.settlement_intents_v2
      where state = 'settled'
        and (
          not coalesce(provider_write_performed, false)
          or not coalesce(readback_pass, false)
          or coalesce(provider_finality_state, '') not in ('final','settled','confirmed')
        )
    ),
    'generic_money_movement_inherited', false,
    'provider_write_performed_by_certification', false
  );

  v_pass :=
    v_adapter_count > 0
    and v_ready_adapter_count = v_adapter_count
    and v_current_edge_count = v_adapter_count
    and v_rls_count = 6
    and (v_checks->>'unattended_value_violations')::integer = 0
    and (v_checks->>'live_exact_authority_violations')::integer = 0
    and (v_checks->>'settled_finality_violations')::integer = 0;

  v_key := 'penta-settlement-cert:' || p_release_version || ':' ||
    encode(digest(concat_ws('|', p_release_version, p_edge_function_id,
      p_edge_bundle_sha256, p_independent_verifier_ref, v_certified_at::text), 'sha256'), 'hex');
  v_hash := encode(digest(concat_ws('|', v_key, v_checks::text), 'sha256'), 'hex');

  v_dail := chlom_runtime.append_dail_event(
    'penta.settlement.fabric.certified',
    'settlement_fabric_certification',
    v_certification_id::text,
    jsonb_build_object(
      'release_version', p_release_version,
      'verdict', case when v_pass then 'PASS' else 'HOLD' end,
      'checks', v_checks,
      'evidence_sha256', v_hash,
      'provider_write_performed', false,
      'money_movement_authority_created', false
    ),
    p_independent_verifier_ref,
    null,
    p_independent_verifier_ref,
    '2.0.0',
    v_certification_id::text,
    null,
    'exact-authority-certification-no-provider-write',
    null,
    'restricted'
  );

  v_checks := v_checks || jsonb_build_object('dail_event_id', v_dail->>'event_id');
  v_hash := encode(digest(concat_ws('|', v_key, v_checks::text), 'sha256'), 'hex');

  insert into penta_runtime.settlement_fabric_certifications_v2 (
    certification_id, certification_key, release_version, verdict,
    adapter_count, ready_adapter_count, edge_function_id, edge_bundle_sha256,
    checks, evidence_sha256, certified_at, expires_at
  )
  values (
    v_certification_id, v_key, p_release_version,
    case when v_pass then 'PASS' else 'HOLD' end,
    v_adapter_count, v_ready_adapter_count, p_edge_function_id, p_edge_bundle_sha256,
    v_checks, v_hash, v_certified_at, v_expires_at
  );

  return jsonb_build_object(
    'certification_id', v_certification_id,
    'verdict', case when v_pass then 'PASS' else 'HOLD' end,
    'checks', v_checks,
    'evidence_sha256', v_hash,
    'expires_at', v_expires_at,
    'provider_write_performed', false
  );
end
$$;

create or replace function penta_runtime.penta_discovery_status_v2()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, penta_runtime, penta_discovery, public
as $$
  select jsonb_build_object(
    'service', 'ct.penta.discovery.family.v2',
    'stable_contract_version', '1.0.0',
    'economic_version', '2.0.0',
    'packet_protocol_version', '3.0.0',
    'family_members_active', (
      select count(*) from penta_discovery.family_registry_v1 where lifecycle_state = 'active'
    ),
    'production_systems', (
      select count(*) from public.penta_system_registry
      where metadata->>'family' = 'PentaDiscovery' and maturity = 'production'
    ),
    'packets', (
      select jsonb_build_object(
        'total', count(*),
        'pending', count(*) filter (where packet_state in ('pending','queued')),
        'delivered', count(*) filter (where packet_state = 'delivered')
      )
      from public.pentas_packets_v1
    ),
    'economics', (
      select jsonb_build_object(
        'bindings', count(*),
        'pay_materialized', count(*) filter (where state = 'pay_materialized'),
        'errors', count(*) filter (where last_error is not null)
      )
      from penta_runtime.penta_packet_economic_bindings_v2
    ),
    'latest_certification', (
      select jsonb_build_object(
        'certification_id', certification_id,
        'release_version', release_version,
        'verdict', verdict,
        'evidence_sha256', evidence_sha256,
        'certified_at', certified_at,
        'expires_at', expires_at
      )
      from penta_runtime.penta_discovery_certifications_v2
      order by certified_at desc
      limit 1
    ),
    'authority_created', false,
    'provider_money_movement_inherited', false,
    'at', now()
  )
$$;

create or replace function penta_runtime.certify_penta_discovery_family_v2(
  p_release_version text,
  p_independent_verifier_ref text,
  p_source_control_ref text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, penta_discovery, penta_os20, public, chlom_runtime, extensions
as $$
declare
  v_canary_binding_id uuid;
  v_canary_packet_id uuid;
  v_canary_receipt_id uuid;
  v_canary_quote_id uuid;
  v_canary_reservation_id uuid;
  v_canary_service_obligation_id uuid;
  v_canary_service_pay_entry_id uuid;
  v_canary_treasury_budget_id uuid;
  v_canary_reserve_tx_id uuid;
  v_canary_spend_tx_id uuid;
  v_canary_dail_event_id uuid;
  v_provider_canary_receipt_id uuid;
  v_runtime_receipt_ids jsonb;
  v_checks jsonb;
  v_pass boolean;
  v_key text;
  v_hash text;
  v_dail jsonb;
  v_dail_event_id uuid;
  v_certification_id uuid := gen_random_uuid();
  v_certified_at timestamptz := now();
  v_expires_at timestamptz := now() + interval '24 hours';
begin
  if session_user <> 'postgres' and coalesce(auth.role(), '') <> 'service_role' then
    raise exception 'SERVICE_ROLE_REQUIRED';
  end if;
  if nullif(btrim(p_release_version), '') is null
     or nullif(btrim(p_independent_verifier_ref), '') is null
     or nullif(btrim(p_source_control_ref), '') is null then
    raise exception 'CERTIFICATION_IDENTITY_REQUIRED';
  end if;

  select
    b.binding_id,
    b.packet_uuid,
    b.receipt_id,
    b.quote_id,
    b.reservation_id,
    b.service_obligation_id,
    b.service_pay_entry_id,
    r.treasury_budget_id,
    r.reserve_transaction_id,
    r.spend_transaction_id,
    so.dail_event_id
  into
    v_canary_binding_id,
    v_canary_packet_id,
    v_canary_receipt_id,
    v_canary_quote_id,
    v_canary_reservation_id,
    v_canary_service_obligation_id,
    v_canary_service_pay_entry_id,
    v_canary_treasury_budget_id,
    v_canary_reserve_tx_id,
    v_canary_spend_tx_id,
    v_canary_dail_event_id
  from penta_runtime.penta_packet_economic_bindings_v2 b
  join penta_runtime.penta_route_reservations_v1 r on r.reservation_id = b.reservation_id
  join penta_runtime.penta_route_receipts_v1 rr on rr.receipt_id = b.receipt_id
  join penta_runtime.penta_route_pay_obligations_v1 so on so.obligation_id = b.service_obligation_id
  join public.penta_pay_entries pe on pe.pay_entry_id = b.service_pay_entry_id
  where b.source_system_key = 'penta.discovery'
    and lower(b.receiver_penta_ref) in ('penta.census','pentacensus')
    and b.state = 'pay_materialized'
    and rr.economic_version = '2.0.0'
    and rr.provider_money_movement = false
    and rr.settlement_state = 'approved_obligations_no_provider_dispatch'
    and r.state = 'consumed'
    and r.treasury_budget_id is not null
    and r.reserve_transaction_id is not null
    and r.spend_transaction_id is not null
    and so.state = 'approved'
    and so.materialization_state = 'materialized'
    and so.dail_event_id is not null
    and pe.state in ('approved','eligible')
  order by b.updated_at desc
  limit 1;

  select rr.receipt_id
    into v_provider_canary_receipt_id
  from penta_runtime.penta_route_receipts_v1 rr
  join penta_runtime.penta_route_pay_obligations_v1 po
    on po.obligation_id = rr.provider_cost_obligation_id
  join public.penta_pay_entries pe
    on pe.pay_entry_id = rr.provider_cost_pay_entry_id
  where rr.economic_version = '2.0.0'
    and rr.provider_cost_minor > 0
    and rr.provider_money_movement = false
    and rr.provider_cost_obligation_id is not null
    and rr.provider_cost_pay_entry_id is not null
    and po.state = 'approved'
    and po.materialization_state = 'materialized'
    and po.dail_event_id is not null
    and pe.state in ('approved','eligible')
  order by rr.created_at desc
  limit 1;

  select coalesce(jsonb_agg(receipt_id order by runtime_component), '[]'::jsonb)
    into v_runtime_receipt_ids
  from (
    select distinct on (runtime_component)
      runtime_component, receipt_id
    from penta_runtime.penta_discovery_runtime_receipts_v2
    where runtime_component in (
      'penta-discovery-edge',
      'penta-crawler-db',
      'penta-context-edge'
    )
      and status = 'active'
      and expires_at > now()
    order by runtime_component, observed_at desc
  ) s;

  v_checks := jsonb_build_object(
    'family_registry_count', (
      select count(*) from penta_discovery.family_registry_v1 where lifecycle_state = 'active'
    ),
    'family_contract_count', (
      select count(*) from penta_discovery.family_registry_v1
      where lifecycle_state = 'active'
        and packet_contract = 'crownthrive.penta.event.v1'
        and fabric_contract = 'crownthrive.pentafabric.v1'
    ),
    'family_authority_manufacture_count', (
      select count(*) from penta_discovery.family_registry_v1
      where authority_manufacture
    ),
    'runtime_component_count', (
      select count(*) from penta_runtime.component_registry_v1
      where stable_contract_id = 'ct.penta.discovery.family.v1' and enabled
    ),
    'production_system_count', (
      select count(*) from public.penta_system_registry
      where metadata->>'family' = 'PentaDiscovery' and maturity = 'production'
    ),
    'production_economic_metadata_count', (
      select count(*) from public.penta_system_registry
      where metadata->>'family' = 'PentaDiscovery'
        and maturity = 'production'
        and coalesce((metadata->>'smart_treasury_metered')::boolean, false)
        and coalesce((metadata->>'penta_pay_real_currency_obligation')::boolean, false)
    ),
    'economic_actor_count', (
      select count(*) from penta_os20.pentas
      where canonical_name in (
        'PentaDiscovery','PentaCrawler','PentaSearch','PentaQuery','PentaFetch',
        'PentaGet','PentaParse','PentaResolve','PentaSignal','PentaContext',
        'PentaCensus','PentaHarvestor'
      ) and status = 'active'
    ),
    'runtime_receipt_count', jsonb_array_length(v_runtime_receipt_ids),
    'runtime_receipt_ids', v_runtime_receipt_ids,
    'canary_packet_id', v_canary_packet_id,
    'canary_binding_id', v_canary_binding_id,
    'canary_receipt_id', v_canary_receipt_id,
    'canary_quote_id', v_canary_quote_id,
    'canary_reservation_id', v_canary_reservation_id,
    'canary_service_obligation_id', v_canary_service_obligation_id,
    'canary_service_pay_entry_id', v_canary_service_pay_entry_id,
    'canary_treasury_budget_id', v_canary_treasury_budget_id,
    'canary_reserve_transaction_id', v_canary_reserve_tx_id,
    'canary_spend_transaction_id', v_canary_spend_tx_id,
    'canary_dail_event_id', v_canary_dail_event_id,
    'provider_cost_cascade_receipt_id', v_provider_canary_receipt_id,
    'canary_usage_reconciles', coalesce((
      select sum(actual_internal_units) = rr.actual_internal_units
      from penta_runtime.penta_route_usage_events_v1 u
      join penta_runtime.penta_route_receipts_v1 rr on rr.receipt_id = v_canary_receipt_id
      where u.reservation_id = v_canary_reservation_id
      group by rr.actual_internal_units
    ), false),
    'canary_chlom_bridge', exists (
      select 1 from penta_runtime.penta_packet_economic_bindings_v2
      where binding_id = v_canary_binding_id
        and chlom_binding_ref = 'crownthrive.chlom.pentafabric.economy.v2'
    ),
    'canary_pay_linked', exists (
      select 1 from public.penta_pay_obligation_links_v2
      where pay_entry_id = v_canary_service_pay_entry_id
        and economic_effect = 'obligation_only'
    ),
    'active_route_rates', (
      select count(*) from penta_runtime.penta_route_rate_policy_v1
      where governance_state = 'active'
    ),
    'active_pay_policies', (
      select count(*) from penta_runtime.penta_pay_route_compensation_policy_v1
      where governance_state = 'active'
    ),
    'legacy_compatibility_rate', exists (
      select 1 from penta_runtime.penta_route_rate_policy_v1
      where route_class = 'legacy_unpriced' and governance_state = 'active'
    ),
    'legacy_rpc_compatibility', (
      to_regprocedure('penta_runtime.reserve_penta_route_v1(uuid,jsonb)') is not null
      and to_regprocedure('penta_runtime.record_penta_route_usage_v1(uuid,integer,text,text,bigint,bigint,text,jsonb)') is not null
      and to_regprocedure('penta_runtime.reconcile_penta_route_v1(uuid,text,bigint,text,text)') is not null
    ),
    'automatic_packet_economic_triggers', (
      select count(*) from pg_trigger t
      join pg_class c on c.oid = t.tgrelid
      join pg_namespace n on n.oid = c.relnamespace
      where not t.tgisinternal
        and n.nspname = 'public'
        and c.relname = 'pentas_packets_v1'
        and t.tgname in (
          'pentas_economic_00_reserve_before_route_v2',
          'pentas_economic_90_meter_finalize_after_route_v2'
        )
    ),
    'anti_abuse_policy_active', exists (
      select 1 from penta_runtime.penta_route_anti_abuse_policy_v2
      where state = 'active'
    ),
    'duplicate_nonbillable_evidence', exists (
      select 1 from penta_runtime.penta_route_duplicate_receipts_v2
    ),
    'infrastructure_retry_nonbillable_evidence', exists (
      select 1 from penta_runtime.penta_route_usage_events_v1
      where retry_class = 'infrastructure'
        and billable_internal = false
        and actual_internal_units = 0
        and billable_provider = true
    ),
    'dynamic_signal_evidence', exists (
      select 1 from penta_runtime.penta_route_dynamic_signals_v2
    ),
    'governance_bounded_auto_apply_evidence', exists (
      select 1 from penta_runtime.penta_route_governance_reconciliations_v1
      where disposition = 'applied'
        and reconciliation_mode = 'automatic_bounded'
    ),
    'governance_three_branch_hold_evidence', exists (
      select 1 from penta_runtime.penta_route_governance_reconciliations_v1
      where disposition in ('held','queued')
        and (executive_ref is null or legislative_ref is null or judicial_ref is null)
    ),
    'smart_treasury_active', exists (
      select 1 from penta_os20.pentas
      where canonical_name = 'PentaTreasury' and status = 'active'
        and coalesce((authority_scope->>'cash_movement')::boolean, false) = false
        and coalesce((authority_scope->>'issue_internal_units')::boolean, false)
    ),
    'smart_treasury_today_budget', exists (
      select 1
      from penta_os20.execution_budgets b
      join penta_os20.pentas p on p.id = b.penta_id
      where p.canonical_name = 'PentaTreasury'
        and b.budget_date = (now() at time zone 'America/New_York')::date
    ),
    'penta_pay_bridge_active', exists (
      select 1 from penta_runtime.penta_route_pay_bridge_config_v2
      where state = 'active'
        and automatic_provider_settlement = false
        and exact_ecac_required
        and coalesce((metadata->>'pay_self_approval')::boolean, false) = false
    ),
    'settlement_fabric_current', exists (
      select 1 from penta_runtime.settlement_fabric_certifications_v2
      where verdict = 'PASS' and expires_at > now()
    ),
    'route_provider_money_movement_violations', (
      select count(*) from penta_runtime.penta_route_receipts_v1
      where provider_money_movement
    ),
    'crawler_cron_active', exists (
      select 1 from cron.job
      where jobname = 'ct-penta-crawler-roam-v3' and active
    ),
    'mesh_router_cron_active', exists (
      select 1 from cron.job
      where jobname = 'ct-pentas-mesh-router-v3' and active
    ),
    'route_economy_cron_active', exists (
      select 1 from cron.job
      where jobname = 'penta-route-economy-maintenance-v1' and active
    ),
    'rls_core_surface_count', (
      select count(*)
      from pg_class c
      join pg_namespace n on n.oid = c.relnamespace
      where c.relrowsecurity
        and (n.nspname, c.relname) in (
          ('penta_runtime','penta_discovery_runtime_receipts_v2'),
          ('penta_runtime','penta_discovery_certifications_v2'),
          ('penta_runtime','penta_packet_economic_bindings_v2'),
          ('penta_runtime','penta_route_quotes_v1'),
          ('penta_runtime','penta_route_reservations_v1'),
          ('penta_runtime','penta_route_usage_events_v1'),
          ('penta_runtime','penta_route_receipts_v1'),
          ('penta_runtime','penta_route_pay_obligations_v1'),
          ('public','pentas_packets_v1'),
          ('public','penta_pay_entries'),
          ('public','penta_pay_obligation_links_v2')
        )
    ),
    'internal_units_are_currency', false,
    'provider_money_movement_inherited', false,
    'source_control_ref', p_source_control_ref
  );

  v_pass :=
    (v_checks->>'family_registry_count')::integer = 12
    and (v_checks->>'family_contract_count')::integer = 12
    and (v_checks->>'family_authority_manufacture_count')::integer = 0
    and (v_checks->>'runtime_component_count')::integer = 12
    and (v_checks->>'production_system_count')::integer >= 12
    and (v_checks->>'production_economic_metadata_count')::integer >= 12
    and (v_checks->>'economic_actor_count')::integer = 12
    and (v_checks->>'runtime_receipt_count')::integer = 3
    and v_canary_packet_id is not null
    and v_canary_binding_id is not null
    and v_canary_receipt_id is not null
    and v_canary_quote_id is not null
    and v_canary_reservation_id is not null
    and v_canary_service_obligation_id is not null
    and v_canary_service_pay_entry_id is not null
    and v_canary_treasury_budget_id is not null
    and v_canary_reserve_tx_id is not null
    and v_canary_spend_tx_id is not null
    and v_canary_dail_event_id is not null
    and v_provider_canary_receipt_id is not null
    and (v_checks->>'canary_usage_reconciles')::boolean
    and (v_checks->>'canary_chlom_bridge')::boolean
    and (v_checks->>'canary_pay_linked')::boolean
    and (v_checks->>'active_route_rates')::integer >= 6
    and (v_checks->>'active_pay_policies')::integer >= 6
    and (v_checks->>'legacy_compatibility_rate')::boolean
    and (v_checks->>'legacy_rpc_compatibility')::boolean
    and (v_checks->>'automatic_packet_economic_triggers')::integer = 2
    and (v_checks->>'anti_abuse_policy_active')::boolean
    and (v_checks->>'duplicate_nonbillable_evidence')::boolean
    and (v_checks->>'infrastructure_retry_nonbillable_evidence')::boolean
    and (v_checks->>'dynamic_signal_evidence')::boolean
    and (v_checks->>'governance_bounded_auto_apply_evidence')::boolean
    and (v_checks->>'governance_three_branch_hold_evidence')::boolean
    and (v_checks->>'smart_treasury_active')::boolean
    and (v_checks->>'smart_treasury_today_budget')::boolean
    and (v_checks->>'penta_pay_bridge_active')::boolean
    and (v_checks->>'settlement_fabric_current')::boolean
    and (v_checks->>'route_provider_money_movement_violations')::integer = 0
    and (v_checks->>'crawler_cron_active')::boolean
    and (v_checks->>'mesh_router_cron_active')::boolean
    and (v_checks->>'route_economy_cron_active')::boolean
    and (v_checks->>'rls_core_surface_count')::integer = 11;

  v_key := 'penta-discovery-cert-v2:' || p_release_version || ':' ||
    encode(digest(concat_ws('|', p_release_version, p_source_control_ref,
      v_canary_packet_id::text, p_independent_verifier_ref, v_certified_at::text), 'sha256'), 'hex');
  v_hash := encode(digest(concat_ws('|', v_key, v_checks::text), 'sha256'), 'hex');

  v_dail := chlom_runtime.append_dail_event(
    'penta.discovery.family.certified',
    'penta_discovery_certification',
    v_certification_id::text,
    jsonb_build_object(
      'release_version', p_release_version,
      'verdict', case when v_pass then 'PASS' else 'FAIL' end,
      'source_control_ref', p_source_control_ref,
      'stable_contract_version', '1.0.0',
      'economic_version', '2.0.0',
      'packet_protocol_version', '3.0.0',
      'checks', v_checks,
      'evidence_sha256', v_hash,
      'authority_created', false,
      'provider_money_movement', false
    ),
    p_independent_verifier_ref,
    null,
    p_independent_verifier_ref,
    '2.0.0',
    v_canary_packet_id::text,
    null,
    'PBD-BOOTSTRAP-20260826|crownthrive.chlom.pentafabric.economy.v2',
    null,
    'restricted'
  );
  v_dail_event_id := nullif(v_dail->>'event_id', '')::uuid;

  v_checks := v_checks || jsonb_build_object('certification_dail_event_id', v_dail_event_id);
  v_hash := encode(digest(concat_ws('|', v_key, v_checks::text), 'sha256'), 'hex');

  insert into penta_runtime.penta_discovery_certifications_v2 (
    certification_id, certification_key, release_version, source_control_ref,
    stable_contract_version, economic_version, packet_protocol_version,
    verdict, checks, canary_packet_id, canary_binding_id, canary_receipt_id,
    provider_canary_receipt_id, runtime_receipt_ids, independent_verifier_ref,
    evidence_sha256, dail_event_id, certified_at, expires_at
  )
  values (
    v_certification_id, v_key, p_release_version, p_source_control_ref,
    '1.0.0', '2.0.0', '3.0.0',
    case when v_pass then 'PASS' else 'FAIL' end,
    v_checks, v_canary_packet_id, v_canary_binding_id, v_canary_receipt_id,
    v_provider_canary_receipt_id, v_runtime_receipt_ids, p_independent_verifier_ref,
    v_hash, v_dail_event_id, v_certified_at, v_expires_at
  );

  insert into penta_runtime.penta_discovery_certifications_v1 (
    certification_key, release_version, verdict, checks, canary_receipt_id,
    independent_verifier_ref, evidence_sha256, certified_at, expires_at
  )
  values (
    'compat:' || v_key, p_release_version,
    case when v_pass then 'PASS' else 'FAIL' end,
    v_checks || jsonb_build_object(
      'certification_v2_id', v_certification_id,
      'stable_contract_version', '1.0.0',
      'economic_version', '2.0.0',
      'packet_protocol_version', '3.0.0'
    ),
    v_canary_receipt_id, p_independent_verifier_ref, v_hash,
    v_certified_at, v_expires_at
  );

  return jsonb_build_object(
    'certification_id', v_certification_id,
    'verdict', case when v_pass then 'PASS' else 'FAIL' end,
    'checks', v_checks,
    'canary_packet_id', v_canary_packet_id,
    'canary_receipt_id', v_canary_receipt_id,
    'provider_canary_receipt_id', v_provider_canary_receipt_id,
    'evidence_sha256', v_hash,
    'dail_event_id', v_dail_event_id,
    'expires_at', v_expires_at,
    'authority_created', false,
    'provider_money_movement', false
  );
end
$$;

update public.penta_system_registry
set metadata = metadata || jsonb_build_object(
      'stable_contract_version', '1.0.0',
      'economic_version', '2.0.0',
      'packet_protocol_version', '3.0.0',
      'chlom_economic_bridge', 'crownthrive.chlom.pentafabric.economy.v2',
      'smart_treasury_metered', true,
      'penta_pay_real_currency_obligation', true,
      'provider_money_movement_inherited', false,
      'full_chain_certification', 'penta_runtime.certify_penta_discovery_family_v2(text,text,text)',
      'backward_compatible', true,
      'interoperable', true,
      'production_closeout_at', now()
    ),
    last_verified_at = now(),
    updated_at = now()
where metadata->>'family' = 'PentaDiscovery';

update public.penta_system_registry
set metadata = metadata || jsonb_build_object(
      'namespace_state', 'production',
      'edge_contract_version', '2.0.0',
      'economic_actions', jsonb_build_array(
        'economics_ensure','economics_finalize','economics_backfill',
        'signal','refresh_signals','evaluate_abuse','pay_materialize',
        'governance_reconcile'
      )
    ),
    updated_at = now()
where system_key = 'penta.discovery';

update public.penta_system_registry
set metadata = metadata || jsonb_build_object(
      'mesh_protocol_version', '3.0.0',
      'canonical_runtime', 'public.penta_crawler_roam_v1(integer)',
      'canonical_status', 'public.penta_crawler_status_v3()',
      'legacy_communications_edge_preserved', true,
      'legacy_service', 'ct.penta.crawler.communications.v1'
    ),
    updated_at = now()
where system_key = 'penta.crawler';

update penta_runtime.component_registry_v1
set metadata = metadata || jsonb_build_object(
      'stable_contract_version', '1.0.0',
      'economic_version', '2.0.0',
      'packet_protocol_version', '3.0.0',
      'smart_treasury_metered', true,
      'penta_pay_real_currency_obligation', true,
      'chlom_economic_bridge', 'crownthrive.chlom.pentafabric.economy.v2',
      'backward_compatible', true,
      'interoperable', true,
      'production_closeout_at', now()
    ),
    updated_at = now()
where stable_contract_id = 'ct.penta.discovery.family.v1';

update penta_discovery.family_registry_v1
set metadata = metadata || jsonb_build_object(
      'stable_contract_version', '1.0.0',
      'economic_version', '2.0.0',
      'packet_protocol_version', '3.0.0',
      'smart_treasury_metered', true,
      'penta_pay_real_currency_obligation', true,
      'chlom_economic_bridge', 'crownthrive.chlom.pentafabric.economy.v2',
      'backward_compatible', true,
      'interoperable', true,
      'production_closeout_at', now()
    ),
    updated_at = now()
where lifecycle_state = 'active';

revoke all on function penta_runtime.reject_penta_discovery_assurance_mutation_v2() from public, anon, authenticated;
revoke all on function penta_runtime.record_penta_discovery_runtime_receipt_v2(text,text,text,integer,text,text,text,boolean,boolean,text,jsonb,timestamptz,interval) from public, anon, authenticated;
revoke all on function penta_runtime.certify_settlement_provider_edges_v2(text,text,text,text) from public, anon, authenticated;
revoke all on function penta_runtime.certify_settlement_fabric_v2(text,text,text,text) from public, anon, authenticated;
revoke all on function penta_runtime.penta_discovery_status_v2() from public, anon, authenticated;
revoke all on function penta_runtime.certify_penta_discovery_family_v2(text,text,text) from public, anon, authenticated;

grant execute on function penta_runtime.record_penta_discovery_runtime_receipt_v2(text,text,text,integer,text,text,text,boolean,boolean,text,jsonb,timestamptz,interval) to service_role;
grant execute on function penta_runtime.certify_settlement_provider_edges_v2(text,text,text,text) to service_role;
grant execute on function penta_runtime.certify_settlement_fabric_v2(text,text,text,text) to service_role;
grant execute on function penta_runtime.penta_discovery_status_v2() to service_role;
grant execute on function penta_runtime.certify_penta_discovery_family_v2(text,text,text) to service_role;

commit;