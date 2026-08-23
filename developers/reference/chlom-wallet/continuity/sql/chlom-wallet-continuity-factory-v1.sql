-- CHLOM Wallet Continuity Factory & Automation v1
-- Controlled-test only. No provider writes, money movement, rights grants, chain broadcast,
-- checkout activation, credential material, destructive recovery, merge authority, or phase advancement.
-- This runtime is append-only/versioned by exact source head. A continuity projection never advances
-- the proprietary-factory generation and never manufactures reviewer or heartbeat evidence.

create schema if not exists chlom_wallet;
create extension if not exists pgcrypto;
create extension if not exists pg_cron;

create table if not exists chlom_wallet.continuity_suite_versions_v1 (
  suite_ref text primary key,
  semantic_version text not null,
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  state text not null default 'CONTROLLED_TEST',
  factory_policy_ref text not null,
  factory_generation_binding integer not null,
  generated_asset_count integer not null default 0,
  direct_component_count integer not null default 0,
  production_activation boolean not null default false,
  authority_granted boolean not null default false,
  ai_final_authority boolean not null default false,
  created_at timestamptz not null default now(),
  unique (source_head_sha, semantic_version)
);

create table if not exists chlom_wallet.continuity_agent_bindings_v1 (
  binding_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  agent_id text not null,
  agent_did text not null,
  fingerprint_sha256 text not null check (fingerprint_sha256 ~ '^[a-f0-9]{64}$'),
  lane text not null,
  heartbeat_ttl_minutes integer not null check (heartbeat_ttl_minutes > 0),
  authority_ceiling text not null default 'A2',
  decision_ceiling text not null default 'D2',
  execution_mode text not null default 'CANDIDATE_ONLY',
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  created_at timestamptz not null default now(),
  unique (suite_ref, agent_id)
);

create table if not exists chlom_wallet.continuity_component_registry_v1 (
  component_record_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  component_id text not null,
  component_class text not null,
  semantic_version text not null default '1.0.0',
  lifecycle_state text not null default 'CONTROLLED_TEST',
  source_ref text not null,
  runtime_binding_state text not null default 'CONTROLLED_TEST',
  registration_sha256 text not null check (registration_sha256 ~ '^[a-f0-9]{64}$'),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (suite_ref, component_id)
);

create table if not exists chlom_wallet.continuity_asset_registry_v1 (
  asset_record_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  asset_id text not null,
  asset_type text not null,
  canonical_name text not null,
  semantic_version text not null default '1.0.0',
  lifecycle_state text not null default 'CONTROLLED_TEST',
  factory_domain_slug text not null,
  factory_generation_binding integer not null,
  public_contract boolean not null default false,
  candidate_only boolean not null default true,
  authority_granted boolean not null default false,
  production_activation boolean not null default false,
  provider_write boolean not null default false,
  money_movement boolean not null default false,
  rights_grant boolean not null default false,
  chain_broadcast boolean not null default false,
  checkout_enabled boolean not null default false,
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  asset_sha256 text not null check (asset_sha256 ~ '^[a-f0-9]{64}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (suite_ref, asset_id)
);

create table if not exists chlom_wallet.continuity_dependency_edges_v1 (
  edge_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  source_ref text not null,
  target_ref text not null,
  dependency_class text not null,
  required boolean not null default true,
  fail_closed boolean not null default true,
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  created_at timestamptz not null default now(),
  unique (suite_ref, source_ref, target_ref, dependency_class)
);

create table if not exists chlom_wallet.continuity_oracle_connections_v1 (
  connection_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  oracle_id text not null,
  canonical_name text not null,
  oracle_class text not null,
  connection_state text not null,
  read_only boolean not null default true check (read_only),
  freshness_ttl_seconds integer not null check (freshness_ttl_seconds > 0),
  source_policy text not null,
  credential_ref text,
  endpoint_ref text,
  authority_ceiling text not null default 'A1',
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (suite_ref, oracle_id)
);

create table if not exists chlom_wallet.continuity_oracle_observations_v1 (
  observation_id uuid primary key default gen_random_uuid(),
  connection_ref text not null references chlom_wallet.continuity_oracle_connections_v1(connection_ref),
  observed_at timestamptz not null,
  payload_digest text not null check (payload_digest ~ '^[a-f0-9]{64}$'),
  source_confidence numeric(5,4) not null check (source_confidence between 0 and 1),
  disposition text not null check (disposition in ('ECAC','HOLD','DENY')),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.continuity_automation_definitions_v1 (
  definition_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  job_id text not null,
  lane text not null,
  cadence_minutes integer not null check (cadence_minutes >= 60),
  owner_agent_id text not null,
  verifier_agent_id text not null check (owner_agent_id <> verifier_agent_id),
  enabled boolean not null default true,
  candidate_only boolean not null default true check (candidate_only),
  fail_closed boolean not null default true check (fail_closed),
  production_activation boolean not null default false check (not production_activation),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (suite_ref, job_id)
);

create table if not exists chlom_wallet.continuity_automation_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  definition_ref text not null references chlom_wallet.continuity_automation_definitions_v1(definition_ref),
  job_id text not null,
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  started_at timestamptz not null default now(),
  completed_at timestamptz not null default now(),
  disposition text not null check (disposition in ('ECAC','HOLD','DENY')),
  stale_heartbeats integer not null default 0,
  mismatched_source_heads integer not null default 0,
  unresolved_dependencies integer not null default 0,
  details jsonb not null default '{}'::jsonb,
  receipt_sha256 text not null check (receipt_sha256 ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.continuity_truth_snapshots_v1 (
  snapshot_id uuid primary key default gen_random_uuid(),
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  factory_policy_ref text not null,
  factory_generation integer not null,
  asset_count integer not null,
  direct_component_count integer not null,
  agent_binding_count integer not null,
  stale_agent_count integer not null,
  oracle_connection_count integer not null,
  dependency_edge_count integer not null,
  disposition text not null check (disposition in ('ECAC','HOLD','DENY')),
  truth_sha256 text not null check (truth_sha256 ~ '^[a-f0-9]{64}$'),
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.continuity_recovery_plans_v1 (
  plan_id uuid primary key default gen_random_uuid(),
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  incident_ref text not null,
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  backup_verified boolean not null default false,
  rollback_verified boolean not null default false,
  independent_review_state text not null default 'HOLD',
  plan_state text not null default 'HOLD' check (plan_state in ('ECAC','HOLD','DENY')),
  automatic_destructive_action boolean not null default false check (not automatic_destructive_action),
  provider_write boolean not null default false check (not provider_write),
  money_movement boolean not null default false check (not money_movement),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  plan jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.continuity_ml_models_v1 (
  model_ref text primary key,
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  model_id text not null,
  semantic_version text not null,
  model_class text not null,
  state text not null default 'CONTROLLED_TEST',
  advisory_only boolean not null default true check (advisory_only),
  final_authority boolean not null default false check (not final_authority),
  feature_contract jsonb not null,
  weights_digest text not null check (weights_digest ~ '^[a-f0-9]{64}$'),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  created_at timestamptz not null default now(),
  unique (suite_ref, model_id)
);

create table if not exists chlom_wallet.continuity_canary_runs_v1 (
  canary_id uuid primary key default gen_random_uuid(),
  suite_ref text not null references chlom_wallet.continuity_suite_versions_v1(suite_ref),
  source_head_sha text not null check (source_head_sha ~ '^[a-f0-9]{40}$'),
  result text not null,
  generated_assets integer not null,
  direct_components integer not null,
  agent_bindings integer not null,
  automation_jobs integer not null,
  oracle_connections integer not null,
  stale_agents integer not null,
  budget_semantics_correct boolean not null,
  public_access boolean not null default false check (not public_access),
  production_activation boolean not null default false check (not production_activation),
  invariant_failures integer not null default 0,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists continuity_assets_suite_idx on chlom_wallet.continuity_asset_registry_v1(suite_ref);
create index if not exists continuity_components_suite_idx on chlom_wallet.continuity_component_registry_v1(suite_ref);
create index if not exists continuity_agent_suite_idx on chlom_wallet.continuity_agent_bindings_v1(suite_ref);
create index if not exists continuity_oracles_suite_idx on chlom_wallet.continuity_oracle_connections_v1(suite_ref);
create index if not exists continuity_jobs_suite_idx on chlom_wallet.continuity_automation_definitions_v1(suite_ref);
create index if not exists continuity_receipts_definition_idx on chlom_wallet.continuity_automation_receipts_v1(definition_ref);
create index if not exists continuity_truth_suite_created_idx on chlom_wallet.continuity_truth_snapshots_v1(suite_ref,created_at desc);

create or replace function chlom_wallet.reject_continuity_history_mutation_v1()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
begin
  raise exception 'continuity_history_is_append_only';
end;
$$;

revoke all on function chlom_wallet.reject_continuity_history_mutation_v1() from public;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'continuity_suite_versions_v1','continuity_agent_bindings_v1','continuity_component_registry_v1',
    'continuity_asset_registry_v1','continuity_dependency_edges_v1','continuity_oracle_connections_v1',
    'continuity_oracle_observations_v1','continuity_automation_definitions_v1','continuity_automation_receipts_v1',
    'continuity_truth_snapshots_v1','continuity_recovery_plans_v1','continuity_ml_models_v1','continuity_canary_runs_v1'
  ] LOOP
    EXECUTE format('alter table chlom_wallet.%I enable row level security', t);
    EXECUTE format('alter table chlom_wallet.%I force row level security', t);
    EXECUTE format('revoke all on chlom_wallet.%I from public, anon, authenticated', t);
    EXECUTE format('drop trigger if exists continuity_append_only_guard on chlom_wallet.%I', t);
    EXECUTE format('create trigger continuity_append_only_guard before update or delete on chlom_wallet.%I for each row execute function chlom_wallet.reject_continuity_history_mutation_v1()', t);
  END LOOP;
END $$;

-- Private service-role access only. Definitions are read-only; evidence is append-only.
grant select on chlom_wallet.continuity_suite_versions_v1,
  chlom_wallet.continuity_agent_bindings_v1,
  chlom_wallet.continuity_component_registry_v1,
  chlom_wallet.continuity_asset_registry_v1,
  chlom_wallet.continuity_dependency_edges_v1,
  chlom_wallet.continuity_oracle_connections_v1,
  chlom_wallet.continuity_automation_definitions_v1,
  chlom_wallet.continuity_ml_models_v1 to service_role;

grant select, insert on chlom_wallet.continuity_oracle_observations_v1,
  chlom_wallet.continuity_automation_receipts_v1,
  chlom_wallet.continuity_truth_snapshots_v1,
  chlom_wallet.continuity_recovery_plans_v1,
  chlom_wallet.continuity_canary_runs_v1 to service_role;

create or replace function chlom_wallet.register_continuity_suite_v1(p_source_head_sha text)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, chlom_wallet, chlom_runtime, integration_control
as $$
declare
  v_suite_ref text := 'ct.suite.chlom-wallet.continuity-factory-automation.v1@1.0.0:' || p_source_head_sha;
  v_policy_ref text := 'ct.policy.chlom-proprietary-factory-100k-plus-continuity-v4';
  v_generation integer;
  v_domain_count integer;
  v_assets integer;
  v_components integer;
  v_agents integer;
  v_stale integer;
  v_jobs integer;
  v_oracles integer;
  v_canary uuid;
begin
  if p_source_head_sha !~ '^[a-f0-9]{40}$' then raise exception 'invalid_source_head_sha'; end if;
  if exists (select 1 from chlom_wallet.continuity_suite_versions_v1 where source_head_sha=p_source_head_sha and semantic_version='1.0.0') then
    return jsonb_build_object('result','ALREADY_REGISTERED','suite_ref',v_suite_ref,'source_head_sha',p_source_head_sha);
  end if;

  select current_generation into v_generation
    from chlom_runtime.proprietary_factory_fleet_policy
   where policy_id='ct.policy.chlom-proprietary-factory-100k-plus'
   order by updated_at desc limit 1;
  if v_generation is null then v_generation := 48; end if;
  if v_generation <> 48 then raise exception 'factory_generation_drift_expected_48_got_%', v_generation; end if;

  select count(*) into v_domain_count from chlom_runtime.proprietary_factory_domains where active=true;

  -- Supersede the tainted active factory-policy metadata without deleting history.
  update chlom_runtime.proprietary_factory_fleet_policy
     set policy_state='retired', updated_at=now(),
         metadata=metadata || jsonb_build_object('superseded_by',v_policy_ref,'retired_at',now())
   where policy_id='ct.policy.chlom-proprietary-factory-100k-plus' and policy_state='active';

  insert into chlom_runtime.proprietary_factory_fleet_policy(
    policy_id,policy_version,policy_state,baseline_generation,current_generation,target_multiplier,
    achieved_multiplier,auto_expand_enabled,auto_expand_mode,next_generation,maximum_generation,cadence_days,
    next_run_not_before,max_active_runs,max_assets_per_run,d3_human_reserved,no_self_approval,no_silent_delete,
    public_contract_only,founder_authority_ref,metadata
  ) values (
    v_policy_ref,'4.0.0','active',1,v_generation,60,v_generation,true,'candidate_only',v_generation+1,60,30,
    greatest(now(),'2026-09-21T21:30:00Z'::timestamptz),1,2100,true,true,true,true,
    'Founder-governed CrownThrive request-budget semantics',
    jsonb_build_object(
      'supersedes','ct.policy.chlom-proprietary-factory-100k-plus',
      'source_head_sha',p_source_head_sha,
      'local_budget_semantics','-1=unlimited_local_ceiling;0=zero_requests;positive=exact_local_monthly_ceiling;null=unresolved_fail_closed',
      'legacy_zero_unlimited_semantics_prohibited',true,
      'candidate_only',true,'factory_generation_advanced',false,
      'production_activation',false,'checkout_enabled',false
    )
  ) on conflict (policy_id) do update set
    policy_state='active',
    metadata=excluded.metadata,
    updated_at=now();

  insert into chlom_wallet.continuity_suite_versions_v1(
    suite_ref,semantic_version,source_head_sha,state,factory_policy_ref,factory_generation_binding,
    generated_asset_count,direct_component_count,production_activation,authority_granted,ai_final_authority
  ) values (
    v_suite_ref,'1.0.0',p_source_head_sha,'CONTROLLED_TEST',v_policy_ref,v_generation,
    v_domain_count*24,48,false,false,false
  );

  insert into chlom_wallet.continuity_agent_bindings_v1(
    binding_ref,suite_ref,agent_id,agent_did,fingerprint_sha256,lane,heartbeat_ttl_minutes,
    authority_ceiling,decision_ceiling,execution_mode,source_head_sha
  )
  select 'ct.binding.wallet.continuity.'||b.lane_slug||'.v1:'||p_source_head_sha,
         v_suite_ref,b.agent_id,b.agent_did,b.fingerprint_sha256,b.lane_slug,b.heartbeat_minutes,
         b.authority_ceiling,b.decision_ceiling,b.execution_mode,p_source_head_sha
    from chlom_runtime.proprietary_factory_agent_blueprints b
   where b.agent_id in (
     'ct.agent.gen6.factory.continuity-recovery.assurance',
     'ct.agent.gen6.factory.continuity-recovery.culture',
     'ct.agent.gen6.factory.continuity-recovery.data',
     'ct.agent.gen6.factory.continuity-recovery.platform'
   );

  -- Actual direct implementation components. These are versioned exact-head registrations,
  -- distinct from the 600 per-domain factory projections.
  with components(component_id,component_class,source_ref,runtime_binding_state) as (values
    ('ct.pallet.chlom-wallet.continuity-core.v1','PALLET','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.pallet.chlom-wallet.truth-lineage.v1','PALLET','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.pallet.chlom-wallet.oracle-reconciliation.v1','PALLET','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.pallet.chlom-wallet.recovery-control.v1','PALLET','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.chlom.wallet-continuity-core','MODULE','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST'),
    ('ct.chlom.wallet-truth-lineage','MODULE','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST'),
    ('ct.chlom.wallet-oracle-router','MODULE','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST'),
    ('ct.chlom.wallet-evidence-expiry','MODULE','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST'),
    ('ct.chlom.wallet-recovery-orchestrator','MODULE','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST'),
    ('ct.chlom.wallet-factory-bridge','MODULE','developers/reference/chlom-wallet/continuity/continuity-factory-asset-catalog.v1.json','CONTROLLED_TEST'),
    ('ct.plugin.chlom-wallet-continuity-core','PLUGIN','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.plugin.chlom-wallet-oracle-router','PLUGIN','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.plugin.chlom-wallet-recovery','PLUGIN','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('ct.plugin.chlom-wallet-culture-continuity','PLUGIN','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','CONTROLLED_TEST'),
    ('chlom_wallet_continuity_status_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_assets_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_dependencies_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_expiry_evaluate_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_oracle_observe_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_recovery_plan_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_truth_snapshot_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('chlom_wallet_continuity_factory_projection_v1','MCP_CONTRACT','developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json','HOLD_UNBOUND_MCP_SERVER'),
    ('ct.api.chlom-wallet.continuity.v1','API_CONTRACT','developers/reference/chlom-wallet/continuity/chlom-wallet-continuity-openapi-v1.yaml','HOLD_UNBOUND_SERVER'),
    ('ct.ip.chlom.continuity.evidence-expiry-downgrade-protocol.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.deterministic-continuity-graph.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.oracle-integrity-reconciliation-protocol.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.factory-continuity-projection-protocol.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.recovery-without-authority-manufacture.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.institutional-truth-closure-protocol.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.continuity-risk-advisory-firewall.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.ip.chlom.continuity.provider-portable-continuity-envelope.v1','METAPROTOCOL_IP','developers/reference/chlom-wallet/continuity/continuity-metaprotocol-ip.v1.json','RESEARCH_CANDIDATE'),
    ('ct.prompt.wallet.continuity.tick.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.exact-head.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.expiry.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.heartbeat.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.oracle.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.dependencies.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.factory.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.recovery.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.security.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.docs.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.interfaces.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.prompt.wallet.continuity.truth.v1','PROMPT','developers/reference/chlom-wallet/continuity/continuity-agent-prompt-suite.v1.json','CONTROLLED_TEST'),
    ('ct.code.chlom-wallet.continuity-core.v1','CODE','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST'),
    ('ct.script.chlom-wallet.continuity-test.v1','SCRIPT','developers/reference/chlom-wallet/continuity/test-continuity-suite-v1.mjs','CONTROLLED_TEST'),
    ('ct.script.chlom-wallet.continuity-chaos.v1','SCRIPT','developers/reference/chlom-wallet/continuity/continuity-chaos-v1.mjs','CONTROLLED_TEST'),
    ('ct.sql.chlom-wallet.continuity-runtime.v1','SQL_RUNTIME','developers/reference/chlom-wallet/continuity/sql/chlom-wallet-continuity-factory-v1.sql','CONTROLLED_TEST'),
    ('ct.ml.chlom-wallet.continuity-risk-advisory.v1','ML_ADVISORY','developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs','CONTROLLED_TEST')
  )
  insert into chlom_wallet.continuity_component_registry_v1(
    component_record_ref,suite_ref,component_id,component_class,semantic_version,lifecycle_state,
    source_ref,runtime_binding_state,registration_sha256,source_head_sha,metadata
  )
  select component_id||':'||substr(p_source_head_sha,1,12),v_suite_ref,component_id,component_class,'1.0.0','CONTROLLED_TEST',
         source_ref,runtime_binding_state,
         encode(digest(component_id||'|'||p_source_head_sha||'|'||source_ref,'sha256'),'hex'),
         p_source_head_sha,jsonb_build_object('candidate_only',true,'authority_granted',false,'production_activation',false)
    from components;

  with blueprints(slug,asset_type,label,public_contract) as (values
    ('pallet','PALLET','Continuity Pallet',true),
    ('module','MODULE','Continuity Module',true),
    ('plugin','PLUGIN','Continuity Plugin',true),
    ('api-contract','API_CONTRACT','Continuity API Contract',true),
    ('mcp-toolset','MCP_TOOLSET','Continuity MCP Toolset',true),
    ('code-library','CODE_LIBRARY','Continuity Code Library',false),
    ('script-runner','SCRIPT_RUNNER','Continuity Script Runner',false),
    ('metaprotocol-ip','METAPROTOCOL_IP','Continuity Metaprotocol IP',true),
    ('prompt-pack','PROMPT_PACK','Continuity Prompt Pack',false),
    ('agent-contract','AGENT_CONTRACT','Continuity Agent Contract',true),
    ('ml-feature-pipeline','ML_FEATURE_PIPELINE','Continuity ML Feature Pipeline',false),
    ('ml-advisory-model','ML_ADVISORY_MODEL','Continuity ML Advisory Model',false),
    ('oracle-connector','ORACLE_CONNECTOR','Continuity Oracle Connector',true),
    ('truth-snapshot','TRUTH_SNAPSHOT','Continuity Truth Snapshot',true),
    ('heartbeat-rule','HEARTBEAT_RULE','Continuity Heartbeat Rule',true),
    ('identity-pin','IDENTITY_PIN','Continuity Identity Pin',true),
    ('dependency-graph','DEPENDENCY_GRAPH','Continuity Dependency Graph',true),
    ('scheduler','SCHEDULER','Continuity Scheduler',true),
    ('recovery-plan','RECOVERY_PLAN','Continuity Recovery Plan',true),
    ('rollback-script','ROLLBACK_SCRIPT','Continuity Rollback Script',false),
    ('observability-probe','OBSERVABILITY_PROBE','Continuity Observability Probe',true),
    ('chaos-scenario','CHAOS_SCENARIO','Continuity Chaos Scenario',true),
    ('ci-gate','CI_GATE','Continuity CI Gate',true),
    ('documentation-artifact','DOCUMENTATION_ARTIFACT','Continuity Documentation Artifact',true)
  ), generated as (
    select 'ct.asset.chlom-wallet.continuity.'||d.domain_slug||'.'||b.slug||'.v1' asset_id,
           b.asset_type,d.domain_name||' — '||b.label canonical_name,d.domain_slug,b.public_contract,
           encode(digest('ct.asset.chlom-wallet.continuity.'||d.domain_slug||'.'||b.slug||'.v1|'||p_source_head_sha,'sha256'),'hex') asset_sha256
      from chlom_runtime.proprietary_factory_domains d cross join blueprints b
     where d.active=true
  )
  insert into chlom_wallet.continuity_asset_registry_v1(
    asset_record_ref,suite_ref,asset_id,asset_type,canonical_name,factory_domain_slug,factory_generation_binding,
    public_contract,candidate_only,authority_granted,production_activation,provider_write,money_movement,
    rights_grant,chain_broadcast,checkout_enabled,source_head_sha,asset_sha256,metadata
  )
  select asset_id||':'||substr(p_source_head_sha,1,12),v_suite_ref,asset_id,asset_type,canonical_name,domain_slug,v_generation,
         public_contract,true,false,false,false,false,false,false,false,p_source_head_sha,asset_sha256,
         jsonb_build_object('factory_policy_ref',v_policy_ref,'projection_only',true,'factory_generation_advanced',false)
    from generated;

  insert into chlom_wallet.continuity_dependency_edges_v1(edge_ref,suite_ref,source_ref,target_ref,dependency_class,required,fail_closed,source_head_sha)
  values
    ('ct.edge.wallet.continuity.execution-envelope.v1:'||p_source_head_sha,v_suite_ref,'ct.suite.chlom-wallet.continuity-factory-automation.v1','ct.contract.chlom-wallet.execution-envelope.v1','AUTHORITY_INPUT',true,true,p_source_head_sha),
    ('ct.edge.wallet.continuity.policy-assurance.v2:'||p_source_head_sha,v_suite_ref,'ct.suite.chlom-wallet.continuity-factory-automation.v1','ct.rulepack.chlom-wallet.policy-assurance.v2@2.0.0','POLICY_INPUT',true,true,p_source_head_sha),
    ('ct.edge.wallet.continuity.backup-recovery.v1:'||p_source_head_sha,v_suite_ref,'ct.suite.chlom-wallet.continuity-factory-automation.v1','ct.chlom.backup-recovery','RECOVERY_INPUT',true,true,p_source_head_sha),
    ('ct.edge.wallet.continuity.drive-plugin.v1:'||p_source_head_sha,v_suite_ref,'ct.suite.chlom-wallet.continuity-factory-automation.v1','ct.plugin.google-drive-continuity','PROVIDER_PORTABILITY_INPUT',false,true,p_source_head_sha);

  insert into chlom_wallet.continuity_oracle_connections_v1(
    connection_ref,suite_ref,oracle_id,canonical_name,oracle_class,connection_state,read_only,freshness_ttl_seconds,source_policy,
    credential_ref,endpoint_ref,authority_ceiling,source_head_sha,metadata
  ) values
    ('ct.oracle.wallet.source-head.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.oracle.wallet.source-head.v1','GitHub Exact Source Head','SOURCE_CONTROL','BOUND_CONTROLLED_TEST',true,3600,'exact_commit_sha',null,'CrownThrive-Support','A1',p_source_head_sha,'{"provider_write":false}'::jsonb),
    ('ct.oracle.wallet.thrivebase.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.oracle.wallet.thrivebase.v1','ThriveBase Runtime Evidence','DATABASE','BOUND_CONTROLLED_TEST',true,3600,'signed_private_readback',null,'chlom_wallet','A1',p_source_head_sha,'{"public_access":false}'::jsonb),
    ('ct.oracle.wallet.dail.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.oracle.wallet.dail.v1','DAIL Evidence Lineage','EVIDENCE_LEDGER','BOUND_CONTROLLED_TEST',true,3600,'append_only_lineage',null,'chlom_runtime.dail_events','A1',p_source_head_sha,'{}'::jsonb),
    ('ct.oracle.wallet.identity.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.oracle.wallet.identity.v1','CHLOM Identity Pins','IDENTITY','BOUND_CONTROLLED_TEST',true,3600,'did_fingerprint_match',null,'chlom_identity','A1',p_source_head_sha,'{}'::jsonb),
    ('ct.oracle.wallet.mintlify.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.oracle.wallet.mintlify.v1','Mintlify Documentation Projection','DOCUMENTATION','HOLD_NEEDS_RUNTIME_BINDING',true,21600,'source_control_projection',null,'Mintlify','A0',p_source_head_sha,'{}'::jsonb),
    ('ct.oracle.wallet.chain-readback.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.oracle.wallet.chain-readback.v1','Read-Only Chain Observation','BLOCKCHAIN','HOLD_NEEDS_RUNTIME_BINDING',true,900,'read_only_chain_rpc',null,null,'A1',p_source_head_sha,'{"chain_broadcast":false}'::jsonb);

  insert into chlom_wallet.continuity_automation_definitions_v1(
    definition_ref,suite_ref,job_id,lane,cadence_minutes,owner_agent_id,verifier_agent_id,enabled,candidate_only,fail_closed,production_activation,source_head_sha,metadata
  ) values
    ('ct.job.wallet.continuity.heartbeat-invalidation.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.heartbeat-invalidation.v1','heartbeat_invalidation',60,'ct.agent.gen6.factory.continuity-recovery.platform','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.exact-head.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.exact-head.v1','exact_head_reconcile',60,'ct.agent.gen6.factory.continuity-recovery.data','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.expiry.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.expiry.v1','evidence_expiry',60,'ct.agent.gen6.factory.continuity-recovery.assurance','ct.agent.gen6.factory.continuity-recovery.data',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.oracle.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.oracle.v1','oracle_reconciliation',60,'ct.agent.gen6.factory.continuity-recovery.data','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.dependency.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.dependency.v1','dependency_drift',360,'ct.agent.gen6.factory.continuity-recovery.platform','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.truth.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.truth.v1','truth_snapshot',60,'ct.agent.gen6.factory.continuity-recovery.data','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.recovery-drill.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.recovery-drill.v1','recovery_drill',1440,'ct.agent.gen6.factory.continuity-recovery.platform','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.culture.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.culture.v1','cultural_continuity',1440,'ct.agent.gen6.factory.continuity-recovery.culture','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{}'::jsonb),
    ('ct.job.wallet.continuity.factory-projection.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.factory-projection.v1','factory_projection',1440,'ct.agent.gen6.factory.continuity-recovery.data','ct.agent.gen6.factory.continuity-recovery.assurance',true,true,true,false,p_source_head_sha,'{"advance_generation":false}'::jsonb),
    ('ct.job.wallet.continuity.docs.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,'ct.job.wallet.continuity.docs.v1','documentation_sync',1440,'ct.agent.gen6.factory.continuity-recovery.assurance','ct.agent.gen6.factory.continuity-recovery.culture',true,true,true,false,p_source_head_sha,'{}'::jsonb);

  insert into chlom_wallet.continuity_ml_models_v1(
    model_ref,suite_ref,model_id,semantic_version,model_class,state,advisory_only,final_authority,feature_contract,weights_digest,source_head_sha
  ) values (
    'ct.ml.chlom-wallet.continuity-risk-advisory.v1:'||substr(p_source_head_sha,1,12),v_suite_ref,
    'ct.ml.chlom-wallet.continuity-risk-advisory.v1','1.0.0','fixed_logistic_advisory','CONTROLLED_TEST',true,false,
    '{"features":["stale_fraction","dependency_drift","oracle_disagreement","rollback_gap","source_head_drift","heartbeat_miss_rate","security_findings","unresolved_handoffs"]}'::jsonb,
    encode(digest('1.7,1.3,1.5,2.0,2.2,1.4,0.35,0.25|-2.4','sha256'),'hex'),p_source_head_sha
  );

  -- Shared canonical service/module/plugin/MCP registries. These are controlled-test capability declarations,
  -- not live public API/MCP activation.
  insert into integration_control.services(
    service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,
    write_gate,monthly_request_limit,timezone,metadata
  ) values (
    'chlom_wallet_continuity','CHLOM Wallet Continuity Control Plane',null,null,'private_internal',null,'unverified','configured',
    false,-1,'UTC',jsonb_build_object('source_head_sha',p_source_head_sha,'mcp_runtime_binding','HOLD_UNBOUND_MCP_SERVER','api_runtime_binding','HOLD_UNBOUND_SERVER','production_activation',false)
  ) on conflict (service_id) do update set
    display_name=excluded.display_name,
    write_gate=false,
    monthly_request_limit=-1,
    integration_state='configured',
    metadata=excluded.metadata,
    updated_at=now();

  insert into chlom_runtime.modules(module_id,canonical_name,module_class,semantic_version,lifecycle_state,authority_ceiling,self_healing_class,public_contract,implementation_ref,mcp_enabled,api_enabled,metadata)
  values
    ('ct.chlom.wallet-continuity-core','CHLOM Wallet Continuity Core','service','1.0.0','test','D2','rollback_capable','{"production_activation":false}'::jsonb,'developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs',true,true,jsonb_build_object('source_head_sha',p_source_head_sha)),
    ('ct.chlom.wallet-truth-lineage','CHLOM Wallet Truth & Lineage','service','1.0.0','test','D2','observe_only','{"provider_evidence_is_not_truth":true}'::jsonb,'developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs',true,true,jsonb_build_object('source_head_sha',p_source_head_sha)),
    ('ct.chlom.wallet-oracle-router','CHLOM Wallet Oracle Router','service','1.0.0','test','D2','observe_only','{"read_only":true}'::jsonb,'developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs',true,true,jsonb_build_object('source_head_sha',p_source_head_sha)),
    ('ct.chlom.wallet-evidence-expiry','CHLOM Wallet Evidence Expiry Engine','service','1.0.0','test','D2','rollback_capable','{"downgrade_only":true}'::jsonb,'developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs',true,true,jsonb_build_object('source_head_sha',p_source_head_sha)),
    ('ct.chlom.wallet-recovery-orchestrator','CHLOM Wallet Recovery Orchestrator','service','1.0.0','test','D2','rollback_capable','{"destructive_recovery":false}'::jsonb,'developers/reference/chlom-wallet/continuity/continuity-core-v1.mjs',true,true,jsonb_build_object('source_head_sha',p_source_head_sha)),
    ('ct.chlom.wallet-factory-bridge','CHLOM Wallet Proprietary Factory Bridge','service','1.0.0','test','D2','observe_only','{"advance_generation":false}'::jsonb,'developers/reference/chlom-wallet/continuity/continuity-factory-asset-catalog.v1.json',true,true,jsonb_build_object('source_head_sha',p_source_head_sha))
  on conflict (module_id) do nothing;

  insert into chlom_runtime.plugin_packages(
    plugin_id,canonical_name,semantic_version,plugin_kind,archetype,lifecycle_state,public_state,auth_mode,owner_agent_id,verifier_agent_id,
    install_name,capabilities,contract_versions,source_ref,public_contract_digest,package_sha256,monetization_state,checkout_enabled,entitlement_active,metadata
  )
  select x.plugin_id,x.canonical_name,'1.0.0',x.plugin_kind,x.archetype,'controlled_test','internal',x.auth_mode,x.owner_agent_id,x.verifier_agent_id,
         x.plugin_id,jsonb_build_array('continuity','read_only','private_append_only'),'{"continuity":"1.0.0"}'::jsonb,
         'developers/reference/chlom-wallet/continuity/continuity-interface-pack.v1.json',
         encode(digest(x.plugin_id||'|public-contract|1.0.0','sha256'),'hex'),
         encode(digest(x.plugin_id||'|'||p_source_head_sha,'sha256'),'hex'),'candidate',false,false,jsonb_build_object('source_head_sha',p_source_head_sha,'runtime_binding_state','CONTROLLED_TEST')
    from (values
      ('ct.plugin.chlom-wallet-continuity-core','CHLOM Wallet Continuity Core Pack','adapter_pack','tool_only','none_private_runtime','ct.agent.gen6.factory.continuity-recovery.platform','ct.agent.gen6.factory.continuity-recovery.assurance'),
      ('ct.plugin.chlom-wallet-oracle-router','CHLOM Wallet Oracle Router Pack','adapter_pack','tool_only','vault_reference_only','ct.agent.gen6.factory.continuity-recovery.data','ct.agent.gen6.factory.continuity-recovery.assurance'),
      ('ct.plugin.chlom-wallet-recovery','CHLOM Wallet Recovery Pack','adapter_pack','tool_only','none_private_runtime','ct.agent.gen6.factory.continuity-recovery.platform','ct.agent.gen6.factory.continuity-recovery.assurance'),
      ('ct.plugin.chlom-wallet-culture-continuity','CHLOM Wallet Cultural Continuity Pack','skill_pack','interactive_decoupled','none_private_runtime','ct.agent.gen6.factory.continuity-recovery.culture','ct.agent.gen6.factory.continuity-recovery.assurance')
    ) as x(plugin_id,canonical_name,plugin_kind,archetype,auth_mode,owner_agent_id,verifier_agent_id)
  on conflict (plugin_id) do nothing;

  insert into integration_control.mcp_tools(tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval,input_schema,output_schema,notes)
  select tool_name,'chlom_wallet_continuity',operation_key,risk_class,false,false,'{}'::jsonb,'{}'::jsonb,
         'Registered controlled-test contract. HOLD_UNBOUND_MCP_SERVER. No provider write, money movement, Rights grant, chain broadcast, credential material, destructive recovery, checkout or phase advancement.'
    from (values
      ('chlom_wallet_continuity_status_v1','continuity.status','D0'),
      ('chlom_wallet_continuity_assets_v1','continuity.assets.list','D0'),
      ('chlom_wallet_continuity_dependencies_v1','continuity.dependencies.list','D0'),
      ('chlom_wallet_continuity_expiry_evaluate_v1','continuity.expiry.evaluate','D1'),
      ('chlom_wallet_continuity_oracle_observe_v1','continuity.oracle.observe','D1'),
      ('chlom_wallet_continuity_recovery_plan_v1','continuity.recovery.plan','D2'),
      ('chlom_wallet_continuity_truth_snapshot_v1','continuity.truth.snapshot','D1'),
      ('chlom_wallet_continuity_factory_projection_v1','continuity.factory.project','D1')
    ) as m(tool_name,operation_key,risk_class)
  on conflict (tool_name) do nothing;

  select count(*) into v_assets from chlom_wallet.continuity_asset_registry_v1 where suite_ref=v_suite_ref;
  select count(*) into v_components from chlom_wallet.continuity_component_registry_v1 where suite_ref=v_suite_ref;
  select count(*) into v_agents from chlom_wallet.continuity_agent_bindings_v1 where suite_ref=v_suite_ref;
  select count(*) into v_jobs from chlom_wallet.continuity_automation_definitions_v1 where suite_ref=v_suite_ref;
  select count(*) into v_oracles from chlom_wallet.continuity_oracle_connections_v1 where suite_ref=v_suite_ref;
  select count(*) into v_stale
    from chlom_runtime.proprietary_factory_agent_heartbeats h
   where h.agent_id in (select agent_id from chlom_wallet.continuity_agent_bindings_v1 where suite_ref=v_suite_ref)
     and (h.next_heartbeat_due_at is null or h.next_heartbeat_due_at < now());

  insert into chlom_wallet.continuity_canary_runs_v1(
    suite_ref,source_head_sha,result,generated_assets,direct_components,agent_bindings,automation_jobs,oracle_connections,stale_agents,
    budget_semantics_correct,public_access,production_activation,invariant_failures,details
  ) values (
    v_suite_ref,p_source_head_sha,
    case when v_domain_count=25 and v_assets=600 and v_components=48 and v_agents=4 and v_jobs=10 and v_oracles=6
         then 'PASS_CHLOM_WALLET_CONTINUITY_FACTORY_REGISTRATION_V1'
         else 'HOLD_CHLOM_WALLET_CONTINUITY_FACTORY_REGISTRATION_MISMATCH' end,
    v_assets,v_components,v_agents,v_jobs,v_oracles,v_stale,true,false,false,
    case when v_domain_count=25 and v_assets=600 and v_components=48 and v_agents=4 and v_jobs=10 and v_oracles=6 then 0 else 1 end,
    jsonb_build_object(
      'active_factory_domains',v_domain_count,
      'factory_generation_advanced',false,
      'reviewer_evidence_fabricated',false,
      'heartbeat_fabricated',false,
      'mcp_runtime_binding','HOLD_UNBOUND_MCP_SERVER',
      'api_runtime_binding','HOLD_UNBOUND_SERVER'
    )
  ) returning canary_id into v_canary;

  return jsonb_build_object(
    'result','REGISTERED_CHLOM_WALLET_CONTINUITY_SUITE_V1',
    'suite_ref',v_suite_ref,'source_head_sha',p_source_head_sha,'generated_assets',v_assets,
    'direct_components',v_components,'agent_bindings',v_agents,'automation_jobs',v_jobs,
    'oracle_connections',v_oracles,'stale_agents',v_stale,'canary_id',v_canary
  );
end;
$$;

revoke all on function chlom_wallet.register_continuity_suite_v1(text) from public, anon, authenticated;
grant execute on function chlom_wallet.register_continuity_suite_v1(text) to service_role;

create or replace function chlom_wallet.continuity_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, chlom_wallet, chlom_runtime
as $$
declare
  v_suite chlom_wallet.continuity_suite_versions_v1%rowtype;
  v_stale integer := 0;
  v_head_mismatch integer := 0;
  v_unresolved integer := 0;
  v_dependency_hold integer := 0;
  v_truth uuid;
  v_disposition text;
  d record;
  v_receipt_digest text;
begin
  select * into v_suite from chlom_wallet.continuity_suite_versions_v1 order by created_at desc limit 1;
  if v_suite.suite_ref is null then return jsonb_build_object('result','HOLD_NO_CONTINUITY_SUITE'); end if;

  -- Derived downgrade only. This mutates the current-state heartbeat label to STALE but never creates
  -- or refreshes a heartbeat receipt.
  update chlom_runtime.proprietary_factory_agent_heartbeats h
     set heartbeat_state='STALE',updated_at=now()
   where h.agent_id in (select agent_id from chlom_wallet.continuity_agent_bindings_v1 where suite_ref=v_suite.suite_ref)
     and (h.next_heartbeat_due_at is null or h.next_heartbeat_due_at < now())
     and h.heartbeat_state not in ('STALE','REVOKED','DENY');

  select count(*) into v_stale
    from chlom_runtime.proprietary_factory_agent_heartbeats h
   where h.agent_id in (select agent_id from chlom_wallet.continuity_agent_bindings_v1 where suite_ref=v_suite.suite_ref)
     and (h.next_heartbeat_due_at is null or h.next_heartbeat_due_at < now() or h.heartbeat_state='STALE');

  select count(*) into v_head_mismatch
    from (
      select source_head_sha from chlom_wallet.continuity_asset_registry_v1 where suite_ref=v_suite.suite_ref
      union all select source_head_sha from chlom_wallet.continuity_component_registry_v1 where suite_ref=v_suite.suite_ref
      union all select source_head_sha from chlom_wallet.continuity_agent_bindings_v1 where suite_ref=v_suite.suite_ref
      union all select source_head_sha from chlom_wallet.continuity_oracle_connections_v1 where suite_ref=v_suite.suite_ref
      union all select source_head_sha from chlom_wallet.continuity_automation_definitions_v1 where suite_ref=v_suite.suite_ref
    ) q where q.source_head_sha<>v_suite.source_head_sha;

  select count(*) into v_unresolved
    from chlom_wallet.continuity_oracle_connections_v1 o
   where o.suite_ref=v_suite.suite_ref and o.connection_state like 'HOLD%';

  select count(*) into v_dependency_hold
    from chlom_wallet.continuity_dependency_edges_v1 e
   where e.suite_ref=v_suite.suite_ref and e.required=true and e.fail_closed=true
     and e.target_ref is null;

  v_disposition := case
    when v_head_mismatch>0 then 'HOLD'
    when v_stale>0 then 'HOLD'
    when v_unresolved>0 then 'HOLD'
    when v_dependency_hold>0 then 'HOLD'
    else 'ECAC' end;

  for d in
    select j.* from chlom_wallet.continuity_automation_definitions_v1 j
     where j.suite_ref=v_suite.suite_ref and j.enabled=true
       and not exists (
         select 1 from chlom_wallet.continuity_automation_receipts_v1 r
          where r.definition_ref=j.definition_ref
            and r.created_at > now() - make_interval(mins=>j.cadence_minutes)
       )
  loop
    v_receipt_digest := encode(digest(
      d.definition_ref||'|'||v_suite.source_head_sha||'|'||now()::text||'|'||v_disposition||'|'||
      v_stale::text||'|'||v_head_mismatch::text||'|'||v_unresolved::text,'sha256'),'hex');
    insert into chlom_wallet.continuity_automation_receipts_v1(
      definition_ref,job_id,source_head_sha,disposition,stale_heartbeats,mismatched_source_heads,unresolved_dependencies,details,receipt_sha256
    ) values (
      d.definition_ref,d.job_id,v_suite.source_head_sha,v_disposition,v_stale,v_head_mismatch,v_unresolved+v_dependency_hold,
      jsonb_build_object('candidate_only',true,'production_activation',false,'heartbeat_fabricated',false,'reviewer_receipt_fabricated',false),
      v_receipt_digest
    );
  end loop;

  insert into chlom_wallet.continuity_truth_snapshots_v1(
    suite_ref,source_head_sha,factory_policy_ref,factory_generation,asset_count,direct_component_count,agent_binding_count,stale_agent_count,
    oracle_connection_count,dependency_edge_count,disposition,truth_sha256,details
  ) values (
    v_suite.suite_ref,v_suite.source_head_sha,v_suite.factory_policy_ref,v_suite.factory_generation_binding,
    (select count(*) from chlom_wallet.continuity_asset_registry_v1 where suite_ref=v_suite.suite_ref),
    (select count(*) from chlom_wallet.continuity_component_registry_v1 where suite_ref=v_suite.suite_ref),
    (select count(*) from chlom_wallet.continuity_agent_bindings_v1 where suite_ref=v_suite.suite_ref),
    v_stale,
    (select count(*) from chlom_wallet.continuity_oracle_connections_v1 where suite_ref=v_suite.suite_ref),
    (select count(*) from chlom_wallet.continuity_dependency_edges_v1 where suite_ref=v_suite.suite_ref),
    v_disposition,
    encode(digest(v_suite.suite_ref||'|'||v_suite.source_head_sha||'|'||v_stale::text||'|'||v_head_mismatch::text||'|'||v_unresolved::text||'|'||v_disposition,'sha256'),'hex'),
    jsonb_build_object(
      'provider_evidence_is_truth',false,'ai_final_authority',false,'factory_generation_advanced',false,
      'unresolved_oracles',v_unresolved,'source_head_mismatches',v_head_mismatch,'required_dependency_holds',v_dependency_hold
    )
  ) returning snapshot_id into v_truth;

  return jsonb_build_object(
    'result','PASS_CHLOM_WALLET_CONTINUITY_TICK_V1',
    'suite_ref',v_suite.suite_ref,'source_head_sha',v_suite.source_head_sha,'disposition',v_disposition,
    'stale_agents',v_stale,'source_head_mismatches',v_head_mismatch,'unresolved_oracles',v_unresolved,
    'required_dependency_holds',v_dependency_hold,'truth_snapshot_id',v_truth
  );
end;
$$;

revoke all on function chlom_wallet.continuity_tick_v1() from public, anon, authenticated;
grant execute on function chlom_wallet.continuity_tick_v1() to service_role;

create or replace function chlom_wallet.continuity_status_v1()
returns jsonb
language sql
stable
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
  select jsonb_build_object(
    'suite_ref',s.suite_ref,
    'source_head_sha',s.source_head_sha,
    'state',s.state,
    'factory_policy_ref',s.factory_policy_ref,
    'factory_generation_binding',s.factory_generation_binding,
    'generated_assets',(select count(*) from chlom_wallet.continuity_asset_registry_v1 a where a.suite_ref=s.suite_ref),
    'direct_components',(select count(*) from chlom_wallet.continuity_component_registry_v1 c where c.suite_ref=s.suite_ref),
    'agent_bindings',(select count(*) from chlom_wallet.continuity_agent_bindings_v1 a where a.suite_ref=s.suite_ref),
    'automation_jobs',(select count(*) from chlom_wallet.continuity_automation_definitions_v1 j where j.suite_ref=s.suite_ref),
    'oracle_connections',(select count(*) from chlom_wallet.continuity_oracle_connections_v1 o where o.suite_ref=s.suite_ref),
    'latest_truth',(select to_jsonb(t) from chlom_wallet.continuity_truth_snapshots_v1 t where t.suite_ref=s.suite_ref order by t.created_at desc limit 1),
    'latest_canary',(select to_jsonb(c) from chlom_wallet.continuity_canary_runs_v1 c where c.suite_ref=s.suite_ref order by c.created_at desc limit 1),
    'production_activation',false,
    'authority_granted',false,
    'ai_final_authority',false
  )
  from chlom_wallet.continuity_suite_versions_v1 s
  order by s.created_at desc limit 1;
$$;

revoke all on function chlom_wallet.continuity_status_v1() from public, anon, authenticated;
grant execute on function chlom_wallet.continuity_status_v1() to service_role;

-- One private hourly scheduler drives all cadence-aware continuity jobs. It performs only internal
-- fail-closed reconciliation and append-only evidence writes. It is not a provider executor.
DO $$
DECLARE existing_job bigint;
BEGIN
  select jobid into existing_job from cron.job where jobname='chlom-wallet-continuity-controlled-test-hourly-v1' limit 1;
  if existing_job is not null then perform cron.unschedule(existing_job); end if;
  perform cron.schedule('chlom-wallet-continuity-controlled-test-hourly-v1','17 * * * *','select chlom_wallet.continuity_tick_v1();');
END $$;
