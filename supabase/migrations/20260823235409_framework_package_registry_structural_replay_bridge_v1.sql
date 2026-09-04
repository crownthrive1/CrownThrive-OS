-- ct.chlom.framework-package-registry-structural-replay-bridge.v1
-- Purpose: restore the minimum historical framework package relation required
-- immediately before 20260823235410_framework_production_promotion_and_cie_activation_v1
-- when earlier provider-applied source is absent from a blank replay database.
--
-- Production guard: current production already has this authoritative relation.
-- This bridge inserts no framework packages and creates no activation, vote,
-- certification, checkout, D3, money, rights or provider authority.

begin;
do $bridge$
begin
  if to_regclass('institutional_federation.framework_package_registry') is not null then
    return;
  end if;

  create schema if not exists institutional_federation;
  revoke all on schema institutional_federation from public, anon, authenticated;

  create table institutional_federation.framework_package_registry (
    package_id text primary key check (package_id ~ '^ct[.]framework-package[.][a-z0-9._-]+$'),
    framework_id text not null unique,
    canonical_name text not null,
    factory_order smallint not null unique check (factory_order between 1 and 999),
    framework_agent_id text not null,
    canonical_host_repo_id text not null,
    execution_slug text not null unique,
    package_state text not null check (package_state in ('source_discovery','scaffold_preview','building','controlled_test','parent_certification_pending','governed_accepted','public_package_candidate','maintained','hold','retired')),
    workflow_ref text,
    validator_ref text,
    engine_ref text,
    skill_ref text,
    tools_ref text,
    api_contract_ref text,
    mcp_contract_ref text,
    evals_ref text,
    commercial_manifest_ref text,
    authority_ceiling text not null default 'D2' check (authority_ceiling in ('D0','D1','D2')),
    can_vote boolean not null default false check (can_vote=false),
    d3_human_reserved boolean not null default true check (d3_human_reserved=true),
    parent_certification_required boolean not null default true,
    parent_certification_agent text not null default 'ct.relay.agent-d' check (parent_certification_agent='ct.relay.agent-d'),
    parent_certification_state text not null default 'pending' check (parent_certification_state in ('pending','certified','denied','not_applicable')),
    operationally_enabled boolean not null default false,
    public_activation_allowed boolean not null default false,
    physical_repository_required boolean not null default false check (physical_repository_required=false),
    optional_repository_projection text,
    private_runtime_required boolean not null default false,
    private_runtime_state text not null default 'not_required' check (private_runtime_state in ('not_required','registered','available','hold')),
    api_state text not null default 'candidate' check (api_state in ('candidate','disabled','controlled_test','enabled','hold')),
    mcp_state text not null default 'candidate' check (mcp_state in ('candidate','disabled','controlled_test','enabled','hold')),
    commercial_state text not null default 'candidate' check (commercial_state in ('research_candidate','candidate','packaged','rights_cleared','pricing_authorized','fulfillment_certified','checkout_staged','live','hold')),
    exact_price_authorized boolean not null default false,
    checkout_enabled boolean not null default false,
    customer_entitlement_active boolean not null default false,
    public_contract_digest text,
    metadata jsonb not null default jsonb_build_object('replay_only_structural_bridge',true,'authority_created',false),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  alter table institutional_federation.framework_package_registry enable row level security;
  alter table institutional_federation.framework_package_registry force row level security;
  revoke all on institutional_federation.framework_package_registry from public, anon, authenticated, service_role;
end
$bridge$;

do $verify$
begin
  if to_regclass('institutional_federation.framework_package_registry') is null then
    raise exception 'HOLD_FRAMEWORK_PACKAGE_REPLAY_BRIDGE_INCOMPLETE';
  end if;
  if exists(select 1 from institutional_federation.framework_package_registry) then
    raise exception 'HOLD_FRAMEWORK_PACKAGE_REPLAY_BRIDGE_MUST_BE_EMPTY';
  end if;
end
$verify$;
commit;
