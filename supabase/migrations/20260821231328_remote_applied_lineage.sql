-- remote_applied_version: 20260821231328
-- CrownThrive CHLOM sanitized replay baseline v1
-- Purpose: reconstruct only the public-safe capability custody topology required by later
-- fail-closed assertions. This is not a verbatim publication of protected historical SQL.
-- Production already records this version as applied; this body is for data-less Git-based replay.

begin;

create schema if not exists chlom_secrets;
create schema if not exists chlom_runtime;

revoke all on schema chlom_secrets from public, anon, authenticated;
revoke all on schema chlom_runtime from public, anon, authenticated;
grant usage on schema chlom_secrets to service_role;
grant usage on schema chlom_runtime to service_role;

create table if not exists chlom_secrets.trade_secret_assets (
  asset_id text primary key,
  asset_kind text not null,
  classification text not null check (
    classification in (
      'TRADE_SECRET',
      'TRADE_SECRET_CANDIDATE',
      'RESTRICTED_INSTITUTIONAL',
      'PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION'
    )
  ),
  canonical_name text not null,
  version text not null,
  vault_secret_id uuid,
  vault_secret_name text,
  public_reference_digest text,
  public_body_allowed boolean not null default false,
  drive_archive_required boolean not null default true,
  lifecycle_state text not null default 'controlled_test',
  source_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (canonical_name, version)
);

create table if not exists chlom_runtime.vaulted_capability_registry (
  capability_id text primary key,
  asset_id text not null references chlom_secrets.trade_secret_assets(asset_id),
  capability_kind text not null check (
    capability_kind in (
      'sql_rpc',
      'edge_function',
      'provider_adapter',
      'policy_bundle',
      'oracle',
      'non_executable'
    )
  ),
  handler_ref text,
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2','D3')),
  allowed_agent_ids text[] not null default '{}',
  invocation_state text not null default 'disabled' check (
    invocation_state in ('disabled','controlled_test','active','hold','revoked')
  ),
  requires_independent_verifier boolean not null default false,
  body_exposure_allowed boolean not null default false,
  output_class text not null default 'sanitized',
  immutable_digest text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace view chlom_runtime.capability_contracts
with (security_invoker=true) as
select
  capability_id,
  asset_id,
  capability_kind,
  handler_ref,
  authority_ceiling,
  allowed_agent_ids,
  invocation_state,
  requires_independent_verifier,
  body_exposure_allowed,
  output_class,
  immutable_digest,
  metadata,
  created_at,
  updated_at
from chlom_runtime.vaulted_capability_registry;

alter table chlom_secrets.trade_secret_assets enable row level security;
alter table chlom_secrets.trade_secret_assets force row level security;
alter table chlom_runtime.vaulted_capability_registry enable row level security;
alter table chlom_runtime.vaulted_capability_registry force row level security;

revoke all on chlom_secrets.trade_secret_assets from public, anon, authenticated;
revoke all on chlom_runtime.vaulted_capability_registry from public, anon, authenticated;
revoke all on chlom_runtime.capability_contracts from public, anon, authenticated;

grant select, insert, update on chlom_secrets.trade_secret_assets to service_role;
grant select, insert, update on chlom_runtime.vaulted_capability_registry to service_role;
grant select on chlom_runtime.capability_contracts to service_role;

comment on table chlom_secrets.trade_secret_assets is
  'CHLOM protected-asset metadata only; secret bodies are not stored by this replay baseline.';
comment on table chlom_runtime.vaulted_capability_registry is
  'CHLOM governed capability contracts with fail-closed authority and exposure metadata.';
comment on view chlom_runtime.capability_contracts is
  'Public-safe compatibility projection over the governed vaulted capability registry.';

commit;
