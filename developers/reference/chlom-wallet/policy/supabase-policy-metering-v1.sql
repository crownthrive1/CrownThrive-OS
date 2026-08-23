-- CHLOM Wallet Policy, Metering & Assurance Engine v1
-- State: CONTROLLED_TEST
-- Boundary: no effective policy, billing, price, Stripe object, checkout,
-- provider write, production rights grant, credential activation, chain
-- broadcast, custody, token issuance, money movement, phase advancement,
-- or merge authorization.

create extension if not exists pgcrypto with schema extensions;

create table if not exists chlom_wallet.policy_algorithm_suites_v1 (
  suite_id text primary key,
  semantic_version text not null,
  canonical_agent_id text not null,
  state text not null check (state = 'CONTROLLED_TEST'),
  external_model_call_required boolean not null default false check (not external_model_call_required),
  auto_apply boolean not null default false check (not auto_apply),
  authority_effect text not null default 'none' check (authority_effect = 'none'),
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_algorithm_definitions_v1 (
  algorithm_id text primary key,
  suite_id text not null references chlom_wallet.policy_algorithm_suites_v1(suite_id) on delete restrict,
  short_name text not null unique,
  algorithm_name text not null,
  role text not null,
  input_contract jsonb not null,
  output_contract jsonb not null,
  required_invariants jsonb not null,
  prohibited_actions jsonb not null,
  deterministic boolean not null default true check (deterministic),
  external_model_call boolean not null default false check (not external_model_call),
  auto_apply boolean not null default false check (not auto_apply),
  authority_effect text not null default 'none' check (authority_effect = 'none'),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_packages_v1 (
  package_id uuid primary key default gen_random_uuid(),
  policy_id text not null,
  semantic_version text not null,
  tenant_ref text not null,
  package_state text not null check (package_state in ('SOURCE_REGISTERED','COMPILED_TEST','HOLD','RETIRED')),
  source_contract jsonb not null,
  source_digest_sha256 text not null check (source_digest_sha256 ~ '^[0-9a-f]{64}$'),
  source_ref text not null,
  effective_policy boolean not null default false check (not effective_policy),
  provider_write boolean not null default false check (not provider_write),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  credential_activation boolean not null default false check (not credential_activation),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  money_movement boolean not null default false check (not money_movement),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  created_at timestamptz not null default now(),
  unique (policy_id, semantic_version, source_digest_sha256)
);

create table if not exists chlom_wallet.policy_compiled_artifacts_v1 (
  artifact_id uuid primary key default gen_random_uuid(),
  package_id uuid not null references chlom_wallet.policy_packages_v1(package_id) on delete restrict,
  compiler_version text not null,
  compiled_contract jsonb not null,
  compiled_digest_sha256 text not null unique check (compiled_digest_sha256 ~ '^[0-9a-f]{64}$'),
  rule_count integer not null check (rule_count between 1 and 500),
  conflict_count integer not null default 0 check (conflict_count = 0),
  unknown_input_disposition text not null check (unknown_input_disposition = 'HOLD'),
  artifact_state text not null check (artifact_state in ('CONTROLLED_TEST','HOLD')),
  activated boolean not null default false check (not activated),
  provider_write boolean not null default false check (not provider_write),
  money_movement boolean not null default false check (not money_movement),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_simulation_runs_v1 (
  simulation_id uuid primary key default gen_random_uuid(),
  artifact_id uuid null references chlom_wallet.policy_compiled_artifacts_v1(artifact_id) on delete restrict,
  policy_id text not null,
  scenario_count integer not null check (scenario_count between 1 and 1000000),
  decision_counts jsonb not null,
  reason_counts jsonb not null,
  rule_coverage jsonb not null,
  simulation_digest_sha256 text not null unique check (simulation_digest_sha256 ~ '^[0-9a-f]{64}$'),
  deterministic_replay_verified boolean not null default true check (deterministic_replay_verified),
  provider_write boolean not null default false check (not provider_write),
  credential_activation boolean not null default false check (not credential_activation),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  money_movement boolean not null default false check (not money_movement),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.meter_definitions_v1 (
  meter_id text primary key,
  meter_name text not null,
  aggregation text not null check (aggregation = 'SUM'),
  window_type text not null check (window_type = 'CALENDAR_MONTH_UTC'),
  quantity_type text not null check (quantity_type = 'NONNEGATIVE_INTEGER'),
  semantics_version text not null check (semantics_version = 'ct.limit-semantics.founder-override.v1'),
  state text not null check (state = 'CONTROLLED_TEST'),
  price_calculation_enabled boolean not null default false check (not price_calculation_enabled),
  billing_enabled boolean not null default false check (not billing_enabled),
  provider_write boolean not null default false check (not provider_write),
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.license_package_candidates_v1 (
  license_id text primary key,
  semantic_version text not null,
  state text not null check (state = 'CONTROLLED_TEST'),
  pallets text[] not null check (cardinality(pallets) > 0),
  limits jsonb not null check (jsonb_typeof(limits) = 'object'),
  support_class text not null,
  license_digest_sha256 text not null unique check (license_digest_sha256 ~ '^[0-9a-f]{64}$'),
  effective_offer boolean not null default false check (not effective_offer),
  public_price_authorized boolean not null default false check (not public_price_authorized),
  stripe_objects_created boolean not null default false check (not stripe_objects_created),
  checkout_enabled boolean not null default false check (not checkout_enabled),
  money_movement boolean not null default false check (not money_movement),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.usage_event_receipts_v1 (
  usage_event_id uuid primary key default gen_random_uuid(),
  event_id text not null unique,
  idempotency_key text not null,
  tenant_ref text not null,
  wallet_stable_id text not null,
  meter_id text not null references chlom_wallet.meter_definitions_v1(meter_id) on delete restrict,
  quantity bigint not null check (quantity >= 0),
  occurred_at timestamptz not null,
  received_at timestamptz not null default now(),
  payload_digest_sha256 text not null check (payload_digest_sha256 ~ '^[0-9a-f]{64}$'),
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  provider_write boolean not null default false check (not provider_write),
  billing_charge_created boolean not null default false check (not billing_charge_created),
  money_movement boolean not null default false check (not money_movement),
  created_at timestamptz not null default now(),
  unique (tenant_ref, idempotency_key)
);

create index if not exists usage_event_receipts_rollup_idx
  on chlom_wallet.usage_event_receipts_v1(tenant_ref, wallet_stable_id, meter_id, occurred_at, event_id);

create table if not exists chlom_wallet.usage_rollup_snapshots_v1 (
  rollup_id uuid primary key default gen_random_uuid(),
  tenant_ref text not null,
  wallet_stable_id text not null,
  meter_id text not null references chlom_wallet.meter_definitions_v1(meter_id) on delete restrict,
  window_start timestamptz not null,
  window_end timestamptz not null check (window_end > window_start),
  event_count integer not null check (event_count >= 0),
  quantity bigint not null check (quantity >= 0),
  event_set_digest_sha256 text not null check (event_set_digest_sha256 ~ '^[0-9a-f]{64}$'),
  rollup_digest_sha256 text not null unique check (rollup_digest_sha256 ~ '^[0-9a-f]{64}$'),
  out_of_order_event_time_preserved boolean not null default true check (out_of_order_event_time_preserved),
  price_applied boolean not null default false check (not price_applied),
  bill_generated boolean not null default false check (not bill_generated),
  stripe_object_created boolean not null default false check (not stripe_object_created),
  provider_write boolean not null default false check (not provider_write),
  money_movement boolean not null default false check (not money_movement),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_advisor_proposals_v1 (
  proposal_id uuid primary key default gen_random_uuid(),
  algorithm_id text not null references chlom_wallet.policy_algorithm_definitions_v1(algorithm_id) on delete restrict,
  policy_id text not null,
  compiled_digest_sha256 text not null check (compiled_digest_sha256 ~ '^[0-9a-f]{64}$'),
  proposal_state text not null check (proposal_state = 'SUGGESTION_ONLY'),
  proposal_contract jsonb not null,
  proposal_digest_sha256 text not null unique check (proposal_digest_sha256 ~ '^[0-9a-f]{64}$'),
  external_model_call_performed boolean not null default false check (not external_model_call_performed),
  auto_apply boolean not null default false check (not auto_apply),
  policy_activation boolean not null default false check (not policy_activation),
  effective_offer_change boolean not null default false check (not effective_offer_change),
  provider_write boolean not null default false check (not provider_write),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  money_movement boolean not null default false check (not money_movement),
  phase_advancement boolean not null default false check (not phase_advancement),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_metering_canary_runs_v1 (
  canary_run_id uuid primary key default gen_random_uuid(),
  result text not null,
  algorithm_count integer not null,
  meter_count integer not null,
  policy_package_count integer not null,
  license_candidate_count integer not null,
  exact_limit_semantics_passed boolean not null,
  duplicate_replay_passed boolean not null,
  collision_rejected boolean not null,
  out_of_order_rollup_passed boolean not null,
  evidence jsonb not null,
  effective_offer boolean not null default false check (not effective_offer),
  public_price boolean not null default false check (not public_price),
  stripe_objects_created boolean not null default false check (not stripe_objects_created),
  checkout_enabled boolean not null default false check (not checkout_enabled),
  provider_write boolean not null default false check (not provider_write),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  credential_activation boolean not null default false check (not credential_activation),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  created_at timestamptz not null default now()
);

create or replace function chlom_wallet.reject_policy_metering_mutation_v1()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  raise exception 'append_or_version_policy_metering_record';
end;
$$;

do $$
declare t text;
begin
  foreach t in array array[
    'policy_algorithm_suites_v1',
    'policy_algorithm_definitions_v1',
    'policy_packages_v1',
    'policy_compiled_artifacts_v1',
    'policy_simulation_runs_v1',
    'meter_definitions_v1',
    'license_package_candidates_v1',
    'usage_event_receipts_v1',
    'usage_rollup_snapshots_v1',
    'policy_advisor_proposals_v1',
    'policy_metering_canary_runs_v1'
  ] loop
    execute format('drop trigger if exists reject_%I_mutation_v1 on chlom_wallet.%I', t, t);
    execute format('create trigger reject_%I_mutation_v1 before update or delete on chlom_wallet.%I for each row execute function chlom_wallet.reject_policy_metering_mutation_v1()', t, t);
    execute format('alter table chlom_wallet.%I enable row level security', t);
    execute format('drop policy if exists deny_all_%I on chlom_wallet.%I', t, t);
    execute format('create policy deny_all_%I on chlom_wallet.%I as restrictive for all to public using(false) with check(false)', t, t);
    execute format('revoke all on chlom_wallet.%I from public, anon, authenticated', t);
  end loop;
end;
$$;

insert into chlom_wallet.policy_algorithm_suites_v1(
  suite_id, semantic_version, canonical_agent_id, state, source_ref, metadata
) values (
  'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  '1.0.0',
  'ct.agent.chlom-wallet-settlement',
  'CONTROLLED_TEST',
  'developers/manifests/chlom-wallet-policy-metering-engine.v1.json',
  jsonb_build_object(
    'subsystem_id','ct.subsystem.chlom-wallet.policy-metering-assurance.v1',
    'phase','2.99'
  )
) on conflict (suite_id) do nothing;

insert into chlom_wallet.policy_algorithm_definitions_v1(
  algorithm_id, suite_id, short_name, algorithm_name, role,
  input_contract, output_contract, required_invariants, prohibited_actions, source_ref
) values
(
  'ct.algorithm.chlom-wallet.cwpx.v1',
  'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  'CWPX',
  'CHLOM Wallet Policy Compiler & eXecutor',
  'Normalize, compile, conflict-check, and deterministically evaluate wallet policy packages.',
  '["policy_package","evaluation_context"]',
  '["compiled_artifact","decision_receipt"]',
  '["deny_hold_allow_precedence","unknown_input_holds","deterministic_digests"]',
  '["auto_activation","provider_write","rights_grant","money_movement"]',
  'developers/reference/chlom-wallet/policy/policy-engine.mjs'
),
(
  'ct.algorithm.chlom-wallet.marc.v1',
  'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  'MARC',
  'Metered Activity Reconciliation Compiler',
  'Record idempotent usage evidence and preserve event time independently from append order.',
  '["usage_event","meter_definition"]',
  '["usage_receipt","rollup_candidate"]',
  '["exact_duplicate_idempotent","collision_rejected","out_of_order_time_preserved"]',
  '["billing","price_application","provider_write"]',
  'developers/reference/chlom-wallet/policy/metering-engine.mjs'
),
(
  'ct.algorithm.chlom-wallet.qera.v1',
  'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  'QERA',
  'Quota Enforcement & Reconciliation Algorithm',
  'Evaluate exact CrownThrive-local usage limits using founder-overridden semantics.',
  '["limit","used","requested"]',
  '["allow_hold_deny","remaining"]',
  '["negative_one_unlimited","zero_exactly_zero","positive_exact","null_hold"]',
  '["zero_as_unlimited","negative_two_acceptance","provider_limit_override"]',
  'developers/reference/chlom-wallet/policy/metering-engine.mjs'
),
(
  'ct.algorithm.chlom-wallet.sage.v1',
  'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  'SAGE',
  'Scenario Assurance & Governance Evaluator',
  'Run deterministic policy matrices, reason distributions, and rule-coverage analysis.',
  '["compiled_policy","scenario_matrix"]',
  '["simulation_summary","coverage","simulation_digest"]',
  '["deterministic_replay","scenario_count_conservation","no_live_side_effects"]',
  '["production_execution","policy_activation","evidence_mutation"]',
  'developers/reference/chlom-wallet/policy/policy-engine.mjs'
),
(
  'ct.algorithm.chlom-wallet.aura.v1',
  'ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  'AURA',
  'Algorithmic Usage & Risk Advisor',
  'Rank suggestion-only policy, capacity, and scenario gaps.',
  '["simulation_summary","meter_snapshots","risk_signals"]',
  '["ranked_proposals","proposal_digest"]',
  '["suggestion_only","external_model_optional","auto_apply_false"]',
  '["policy_activation","price_change","rights_grant","provider_write","chain_broadcast"]',
  'developers/reference/chlom-wallet/policy/policy-advisor.mjs'
) on conflict (algorithm_id) do nothing;

insert into chlom_wallet.meter_definitions_v1(
  meter_id, meter_name, aggregation, window_type, quantity_type,
  semantics_version, state, source_ref, metadata
) values
(
  'ct.meter.wallet.api.requests.monthly',
  'Wallet API requests',
  'SUM','CALENDAR_MONTH_UTC','NONNEGATIVE_INTEGER',
  'ct.limit-semantics.founder-override.v1','CONTROLLED_TEST',
  'developers/reference/chlom-wallet/policy/fixtures/walletkit-synthetic-license.v1.json',
  '{"commercial_offer":false}'::jsonb
),
(
  'ct.meter.wallet.chain.broadcast.monthly',
  'Wallet chain broadcast attempts',
  'SUM','CALENDAR_MONTH_UTC','NONNEGATIVE_INTEGER',
  'ct.limit-semantics.founder-override.v1','CONTROLLED_TEST',
  'developers/reference/chlom-wallet/policy/fixtures/walletkit-synthetic-license.v1.json',
  '{"broadcast_enabled":false}'::jsonb
),
(
  'ct.meter.wallet.proof.anchor.monthly',
  'Wallet proof anchor candidates',
  'SUM','CALENDAR_MONTH_UTC','NONNEGATIVE_INTEGER',
  'ct.limit-semantics.founder-override.v1','CONTROLLED_TEST',
  'developers/reference/chlom-wallet/policy/fixtures/walletkit-synthetic-license.v1.json',
  '{"anchor_broadcast":false}'::jsonb
),
(
  'ct.meter.wallet.internal.simulation.monthly',
  'Wallet internal simulations',
  'SUM','CALENDAR_MONTH_UTC','NONNEGATIVE_INTEGER',
  'ct.limit-semantics.founder-override.v1','CONTROLLED_TEST',
  'developers/reference/chlom-wallet/policy/fixtures/walletkit-synthetic-license.v1.json',
  '{"internal_controlled_test":true}'::jsonb
) on conflict (meter_id) do nothing;

insert into chlom_wallet.policy_packages_v1(
  policy_id, semantic_version, tenant_ref, package_state,
  source_contract, source_digest_sha256, source_ref
) values (
  'ct.policy.chlom-wallet.walletkit-controlled.v1',
  '1.0.0',
  'ct.tenant.crownthrive',
  'SOURCE_REGISTERED',
  jsonb_build_object(
    'schema_version','1.0.0',
    'policy_id','ct.policy.chlom-wallet.walletkit-controlled.v1',
    'semantic_version','1.0.0',
    'state','CONTROLLED_TEST',
    'source_path','developers/reference/chlom-wallet/policy/fixtures/walletkit-controlled-policy.v1.json',
    'compiler_path','developers/reference/chlom-wallet/policy/policy-engine.mjs',
    'unknown_input_disposition','HOLD',
    'decision_precedence',jsonb_build_array('DENY','HOLD','ALLOW')
  ),
  encode(extensions.digest(
    'ct.policy.chlom-wallet.walletkit-controlled.v1|1.0.0|developers/reference/chlom-wallet/policy/fixtures/walletkit-controlled-policy.v1.json',
    'sha256'
  ),'hex'),
  'developers/reference/chlom-wallet/policy/fixtures/walletkit-controlled-policy.v1.json'
) on conflict (policy_id, semantic_version, source_digest_sha256) do nothing;

insert into chlom_wallet.license_package_candidates_v1(
  license_id, semantic_version, state, pallets, limits, support_class,
  license_digest_sha256, source_ref
) values (
  'ct.license-candidate.chlom-wallet.synthetic.v1',
  '1.0.0',
  'CONTROLLED_TEST',
  array[
    'ct.pallet.chlom-wallet-core.v1',
    'ct.pallet.chlom-unified-value-receipt.v1',
    'ct.pallet.chlom-wallet-sdk-api.v1'
  ],
  jsonb_build_object(
    'ct.meter.wallet.api.requests.monthly',100,
    'ct.meter.wallet.chain.broadcast.monthly',0,
    'ct.meter.wallet.proof.anchor.monthly',null,
    'ct.meter.wallet.internal.simulation.monthly',-1
  ),
  'SYNTHETIC_TEST_ONLY',
  encode(extensions.digest(
    'ct.license-candidate.chlom-wallet.synthetic.v1|1.0.0|-1|0|100|null',
    'sha256'
  ),'hex'),
  'developers/reference/chlom-wallet/policy/fixtures/walletkit-synthetic-license.v1.json'
) on conflict (license_id) do nothing;

create or replace function chlom_wallet.evaluate_usage_budget_v1(
  p_limit bigint,
  p_used bigint,
  p_requested bigint
)
returns jsonb
language plpgsql
immutable
set search_path = pg_catalog
as $$
declare
  v_disposition text;
  v_reason text;
  v_remaining bigint;
  v_projected numeric;
begin
  if p_used is null or p_used < 0 then
    raise exception 'usage_used_invalid';
  end if;
  if p_requested is null or p_requested < 0 then
    raise exception 'usage_requested_invalid';
  end if;

  if p_limit is null then
    v_disposition := 'HOLD';
    v_reason := 'LIMIT_UNRESOLVED_FAIL_CLOSED';
    v_remaining := null;
  elsif p_limit = -1 then
    v_disposition := 'ALLOW';
    v_reason := 'UNLIMITED_LOCAL_LIMIT';
    v_remaining := null;
  elsif p_limit < -1 then
    v_disposition := 'DENY';
    v_reason := 'LIMIT_NEGATIVE_INVALID';
    v_remaining := null;
  elsif p_limit = 0 then
    v_remaining := 0;
    if p_requested = 0 then
      v_disposition := 'ALLOW';
      v_reason := 'ZERO_REQUEST_WITH_ZERO_LIMIT';
    else
      v_disposition := 'DENY';
      v_reason := 'ZERO_LIMIT_DENIES_USAGE';
    end if;
  else
    v_projected := p_used::numeric + p_requested::numeric;
    v_remaining := greatest(p_limit - p_used, 0);
    if v_projected <= p_limit then
      v_disposition := 'ALLOW';
      v_reason := 'WITHIN_EXACT_LIMIT';
      v_remaining := p_limit - v_projected::bigint;
    else
      v_disposition := 'DENY';
      v_reason := 'EXACT_LIMIT_EXCEEDED';
    end if;
  end if;

  return jsonb_build_object(
    'contract','ct.wallet.usage-budget-decision.v1',
    'semantics_version','ct.limit-semantics.founder-override.v1',
    'limit',p_limit,
    'used',p_used,
    'requested',p_requested,
    'disposition',v_disposition,
    'reason_code',v_reason,
    'remaining_after_request',v_remaining,
    'provider_limits_still_authoritative',true,
    'hard_boundaries',jsonb_build_object(
      'billing_charge_created',false,
      'stripe_object_created',false,
      'provider_write',false,
      'money_movement',false,
      'production_entitlement_grant',false
    )
  );
end;
$$;

create or replace function chlom_wallet.record_usage_event_v1(
  p_event_id text,
  p_idempotency_key text,
  p_tenant_ref text,
  p_wallet_stable_id text,
  p_meter_id text,
  p_quantity bigint,
  p_occurred_at timestamptz,
  p_payload_digest_sha256 text,
  p_source_ref text,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = chlom_wallet, pg_catalog, pg_temp
as $$
declare
  v_existing chlom_wallet.usage_event_receipts_v1%rowtype;
  v_id uuid;
begin
  if p_event_id !~ '^ctue_[A-Za-z0-9_-]{12,120}$' then
    raise exception 'usage_event_id_invalid';
  end if;
  if p_idempotency_key !~ '^ctik_[A-Za-z0-9_-]{12,160}$' then
    raise exception 'usage_idempotency_key_invalid';
  end if;
  if p_quantity is null or p_quantity < 0 then
    raise exception 'usage_quantity_invalid';
  end if;
  if p_payload_digest_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'usage_payload_digest_invalid';
  end if;
  if p_source_ref is null or length(p_source_ref) < 3 then
    raise exception 'usage_source_ref_invalid';
  end if;

  select * into v_existing
  from chlom_wallet.usage_event_receipts_v1
  where tenant_ref = p_tenant_ref
    and idempotency_key = p_idempotency_key;

  if found then
    if v_existing.payload_digest_sha256 <> p_payload_digest_sha256 then
      raise exception 'usage_idempotency_collision';
    end if;
    return jsonb_build_object(
      'state','DUPLICATE',
      'usage_event_id',v_existing.usage_event_id,
      'event_id',v_existing.event_id,
      'idempotency_key',v_existing.idempotency_key,
      'payload_digest_sha256',v_existing.payload_digest_sha256,
      'provider_write',false,
      'billing_charge_created',false,
      'money_movement',false
    );
  end if;

  insert into chlom_wallet.usage_event_receipts_v1(
    event_id, idempotency_key, tenant_ref, wallet_stable_id, meter_id,
    quantity, occurred_at, payload_digest_sha256, source_ref, metadata
  ) values (
    p_event_id, p_idempotency_key, p_tenant_ref, p_wallet_stable_id, p_meter_id,
    p_quantity, p_occurred_at, p_payload_digest_sha256, p_source_ref,
    coalesce(p_metadata,'{}'::jsonb)
  ) returning usage_event_id into v_id;

  return jsonb_build_object(
    'state','RECORDED_TEST',
    'usage_event_id',v_id,
    'event_id',p_event_id,
    'idempotency_key',p_idempotency_key,
    'payload_digest_sha256',p_payload_digest_sha256,
    'provider_write',false,
    'billing_charge_created',false,
    'money_movement',false
  );
end;
$$;

create or replace function public.chlom_wallet_policy_metering_status_v1()
returns jsonb
language sql
stable
security definer
set search_path = chlom_wallet, pg_catalog, pg_temp
as $$
select jsonb_build_object(
  'contract','ct.wallet.policy-metering-status.v1',
  'state','CONTROLLED_TEST',
  'phase','2.99',
  'canonical_agent_id','ct.agent.chlom-wallet-settlement',
  'algorithm_suite_id','ct.algorithm-suite.chlom-wallet-policy-metering.v1',
  'algorithm_count',(select count(*) from chlom_wallet.policy_algorithm_definitions_v1 where suite_id='ct.algorithm-suite.chlom-wallet-policy-metering.v1'),
  'meter_count',(select count(*) from chlom_wallet.meter_definitions_v1),
  'policy_package_count',(select count(*) from chlom_wallet.policy_packages_v1),
  'license_candidate_count',(select count(*) from chlom_wallet.license_package_candidates_v1),
  'usage_event_count',(select count(*) from chlom_wallet.usage_event_receipts_v1),
  'latest_canary',(
    select jsonb_build_object('result',result,'created_at',created_at,'evidence',evidence)
    from chlom_wallet.policy_metering_canary_runs_v1
    order by created_at desc
    limit 1
  ),
  'limit_semantics',jsonb_build_object(
    'unlimited',-1,
    'zero',0,
    'positive_integer','EXACT_LIMIT',
    'unresolved',null,
    'unresolved_disposition','HOLD_FAIL_CLOSED',
    'provider_limits_still_authoritative',true
  ),
  'monetization',jsonb_build_object(
    'metering_controlled_test',true,
    'price_calculation_enabled',false,
    'billing_enabled',false,
    'effective_offer',false,
    'public_price',false,
    'stripe_objects_created',false,
    'checkout_enabled',false
  ),
  'hard_boundaries',jsonb_build_object(
    'auto_policy_activation',false,
    'external_model_authority',false,
    'provider_write',false,
    'production_rights_grant',false,
    'credential_activation',false,
    'chain_broadcast',false,
    'custody',false,
    'token_issuance',false,
    'money_movement',false,
    'effective_price_publication',false,
    'checkout_activation',false,
    'phase_advancement',false,
    'merge_authorized',false
  ),
  'source_ref','github:crownthrive1/CrownThrive-Support:pull/230'
);
$$;

create or replace function chlom_wallet.run_policy_metering_canary_v1()
returns jsonb
language plpgsql
security definer
set search_path = chlom_wallet, extensions, pg_catalog, pg_temp
as $$
declare
  v_suffix text := replace(gen_random_uuid()::text,'-','');
  v_tenant text := 'ct.tenant.canary.' || substr(v_suffix,1,12);
  v_wallet text := 'ct.wallet.canary.' || substr(v_suffix,1,16);
  v_later_event text := 'ctue_later_' || substr(v_suffix,1,24);
  v_later_key text := 'ctik_later_' || substr(v_suffix,1,24);
  v_earlier_event text := 'ctue_earlier_' || substr(v_suffix,1,22);
  v_earlier_key text := 'ctik_earlier_' || substr(v_suffix,1,22);
  v_later_digest text := encode(digest('later|' || v_suffix,'sha256'),'hex');
  v_earlier_digest text := encode(digest('earlier|' || v_suffix,'sha256'),'hex');
  v_first jsonb;
  v_duplicate jsonb;
  v_collision boolean := false;
  v_exact boolean := false;
  v_rollup boolean := false;
  v_event_count integer;
  v_quantity bigint;
  v_event_set_digest text;
  v_rollup_digest text;
  v_run uuid;
  v_algorithm_count integer;
  v_meter_count integer;
  v_policy_count integer;
  v_license_count integer;
begin
  v_exact :=
    chlom_wallet.evaluate_usage_budget_v1(-1,999,999)->>'reason_code' = 'UNLIMITED_LOCAL_LIMIT'
    and chlom_wallet.evaluate_usage_budget_v1(0,0,1)->>'reason_code' = 'ZERO_LIMIT_DENIES_USAGE'
    and chlom_wallet.evaluate_usage_budget_v1(1,0,1)->>'reason_code' = 'WITHIN_EXACT_LIMIT'
    and chlom_wallet.evaluate_usage_budget_v1(1,1,1)->>'reason_code' = 'EXACT_LIMIT_EXCEEDED'
    and chlom_wallet.evaluate_usage_budget_v1(null,0,1)->>'reason_code' = 'LIMIT_UNRESOLVED_FAIL_CLOSED'
    and chlom_wallet.evaluate_usage_budget_v1(-2,0,1)->>'reason_code' = 'LIMIT_NEGATIVE_INVALID';

  v_first := chlom_wallet.record_usage_event_v1(
    v_later_event,v_later_key,v_tenant,v_wallet,
    'ct.meter.wallet.api.requests.monthly',2,
    '2026-08-22T12:00:00Z',v_later_digest,
    'synthetic:policy-metering-canary',jsonb_build_object('order','later')
  );
  v_duplicate := chlom_wallet.record_usage_event_v1(
    v_later_event,v_later_key,v_tenant,v_wallet,
    'ct.meter.wallet.api.requests.monthly',2,
    '2026-08-22T12:00:00Z',v_later_digest,
    'synthetic:policy-metering-canary',jsonb_build_object('order','later')
  );
  perform chlom_wallet.record_usage_event_v1(
    v_earlier_event,v_earlier_key,v_tenant,v_wallet,
    'ct.meter.wallet.api.requests.monthly',1,
    '2026-08-01T00:00:01Z',v_earlier_digest,
    'synthetic:policy-metering-canary',jsonb_build_object('order','earlier')
  );

  begin
    perform chlom_wallet.record_usage_event_v1(
      'ctue_collision_' || substr(v_suffix,1,20),
      v_later_key,v_tenant,v_wallet,
      'ct.meter.wallet.api.requests.monthly',3,
      '2026-08-22T12:00:00Z',
      encode(digest('collision|' || v_suffix,'sha256'),'hex'),
      'synthetic:policy-metering-canary','{}'::jsonb
    );
  exception when others then
    v_collision := position('usage_idempotency_collision' in sqlerrm) > 0;
  end;

  select
    count(*),
    coalesce(sum(quantity),0),
    encode(digest(string_agg(event_id || ':' || payload_digest_sha256,'|' order by occurred_at,event_id),'sha256'),'hex')
  into v_event_count,v_quantity,v_event_set_digest
  from chlom_wallet.usage_event_receipts_v1
  where tenant_ref = v_tenant
    and wallet_stable_id = v_wallet
    and meter_id = 'ct.meter.wallet.api.requests.monthly'
    and occurred_at >= '2026-08-01T00:00:00Z'
    and occurred_at < '2026-09-01T00:00:00Z';

  v_rollup := v_event_count = 2 and v_quantity = 3;
  v_rollup_digest := encode(digest(jsonb_build_object(
    'tenant_ref',v_tenant,
    'wallet_stable_id',v_wallet,
    'meter_id','ct.meter.wallet.api.requests.monthly',
    'window_start','2026-08-01T00:00:00Z',
    'window_end','2026-09-01T00:00:00Z',
    'event_count',v_event_count,
    'quantity',v_quantity,
    'event_set_digest_sha256',v_event_set_digest
  )::text,'sha256'),'hex');

  insert into chlom_wallet.usage_rollup_snapshots_v1(
    tenant_ref,wallet_stable_id,meter_id,window_start,window_end,
    event_count,quantity,event_set_digest_sha256,rollup_digest_sha256,source_ref
  ) values (
    v_tenant,v_wallet,'ct.meter.wallet.api.requests.monthly',
    '2026-08-01T00:00:00Z','2026-09-01T00:00:00Z',
    v_event_count,v_quantity,v_event_set_digest,v_rollup_digest,
    'synthetic:policy-metering-canary'
  );

  select count(*) into v_algorithm_count
  from chlom_wallet.policy_algorithm_definitions_v1
  where suite_id = 'ct.algorithm-suite.chlom-wallet-policy-metering.v1';
  select count(*) into v_meter_count from chlom_wallet.meter_definitions_v1;
  select count(*) into v_policy_count from chlom_wallet.policy_packages_v1;
  select count(*) into v_license_count from chlom_wallet.license_package_candidates_v1;

  if not v_exact
    or v_first->>'state' <> 'RECORDED_TEST'
    or v_duplicate->>'state' <> 'DUPLICATE'
    or not v_collision
    or not v_rollup
    or v_algorithm_count <> 5
    or v_meter_count <> 4
    or v_policy_count < 1
    or v_license_count < 1 then
    raise exception 'policy_metering_canary_failed';
  end if;

  insert into chlom_wallet.policy_metering_canary_runs_v1(
    result,algorithm_count,meter_count,policy_package_count,license_candidate_count,
    exact_limit_semantics_passed,duplicate_replay_passed,collision_rejected,
    out_of_order_rollup_passed,evidence
  ) values (
    'PASS_CHLOM_WALLET_POLICY_METERING_CANARY',
    v_algorithm_count,v_meter_count,v_policy_count,v_license_count,
    true,true,true,true,
    jsonb_build_object(
      'tenant_ref',v_tenant,
      'wallet_stable_id',v_wallet,
      'first_state',v_first->>'state',
      'duplicate_state',v_duplicate->>'state',
      'event_count',v_event_count,
      'quantity',v_quantity,
      'event_set_digest_sha256',v_event_set_digest,
      'rollup_digest_sha256',v_rollup_digest,
      'limit_semantics',jsonb_build_object('-1','unlimited','0','zero','positive','exact','null','hold_fail_closed'),
      'effective_offer',false,
      'public_price',false,
      'stripe_objects_created',false,
      'checkout_enabled',false,
      'provider_write',false,
      'production_rights_grant',false,
      'credential_activation',false,
      'chain_broadcast',false,
      'custody',false,
      'token_issuance',false,
      'money_movement',false,
      'phase_advancement',false,
      'merge_authorized',false
    )
  ) returning canary_run_id into v_run;

  return jsonb_build_object(
    'result','PASS_CHLOM_WALLET_POLICY_METERING_CANARY',
    'canary_run_id',v_run,
    'algorithms',v_algorithm_count,
    'meters',v_meter_count,
    'policies',v_policy_count,
    'license_candidates',v_license_count,
    'exact_limit_semantics_passed',true,
    'duplicate_replay_passed',true,
    'collision_rejected',true,
    'out_of_order_rollup_passed',true,
    'effective_offer',false,
    'public_price',false,
    'stripe_objects_created',false,
    'checkout_enabled',false,
    'provider_write',false,
    'production_rights_grant',false,
    'credential_activation',false,
    'chain_broadcast',false,
    'custody',false,
    'token_issuance',false,
    'money_movement',false,
    'phase_advancement',false,
    'merge_authorized',false
  );
end;
$$;

revoke all on function chlom_wallet.evaluate_usage_budget_v1(bigint,bigint,bigint) from public, anon, authenticated;
revoke all on function chlom_wallet.record_usage_event_v1(text,text,text,text,text,bigint,timestamptz,text,text,jsonb) from public, anon, authenticated;
revoke all on function chlom_wallet.run_policy_metering_canary_v1() from public, anon, authenticated;
grant execute on function chlom_wallet.evaluate_usage_budget_v1(bigint,bigint,bigint) to service_role;
grant execute on function chlom_wallet.record_usage_event_v1(text,text,text,text,text,bigint,timestamptz,text,text,jsonb) to service_role;
grant execute on function chlom_wallet.run_policy_metering_canary_v1() to service_role;

revoke all on function public.chlom_wallet_policy_metering_status_v1() from public;
grant execute on function public.chlom_wallet_policy_metering_status_v1() to anon, authenticated, service_role;
