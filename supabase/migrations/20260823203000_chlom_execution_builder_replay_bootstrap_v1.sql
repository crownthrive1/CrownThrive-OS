-- CHLOM execution-builder replay bootstrap v1
-- Purpose: make data-less historical replay deterministic before
-- 20260823203546_execution_builder_capability_contract_identity_v1.
-- This migration is intentionally idempotent. On an estate where the governed
-- objects already exist it preserves them; on a clean replay it creates only the
-- minimum contract-bearing structures required by the later identity migration.

create schema if not exists chlom_secrets;
create schema if not exists chlom_runtime;

create table if not exists chlom_secrets.trade_secret_assets (
  asset_id text primary key,
  asset_kind text not null,
  classification text not null check (
    classification = any (array[
      'TRADE_SECRET'::text,
      'TRADE_SECRET_CANDIDATE'::text,
      'RESTRICTED_INSTITUTIONAL'::text,
      'PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION'::text
    ])
  ),
  canonical_name text not null,
  version text not null,
  vault_secret_id uuid,
  vault_secret_name text,
  public_reference_digest text,
  public_body_allowed boolean not null default false,
  drive_archive_required boolean not null default true,
  lifecycle_state text not null default 'controlled_test'::text,
  source_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint trade_secret_assets_canonical_name_version_key unique (canonical_name, version)
);

alter table chlom_secrets.trade_secret_assets enable row level security;
alter table chlom_secrets.trade_secret_assets force row level security;

drop policy if exists client_deny_all on chlom_secrets.trade_secret_assets;
create policy client_deny_all
  on chlom_secrets.trade_secret_assets
  as permissive
  for all
  to anon, authenticated
  using (false)
  with check (false);

revoke all on table chlom_secrets.trade_secret_assets from anon, authenticated;
grant select, insert, update on table chlom_secrets.trade_secret_assets to service_role;

create table if not exists chlom_runtime.vaulted_capability_registry (
  capability_id text primary key,
  asset_id text not null references chlom_secrets.trade_secret_assets(asset_id),
  capability_kind text not null check (
    capability_kind = any (array[
      'sql_rpc'::text,
      'edge_function'::text,
      'provider_adapter'::text,
      'policy_bundle'::text,
      'oracle'::text,
      'non_executable'::text
    ])
  ),
  handler_ref text,
  authority_ceiling text not null check (
    authority_ceiling = any (array['D0'::text, 'D1'::text, 'D2'::text, 'D3'::text])
  ),
  allowed_agent_ids text[] not null default '{}'::text[],
  invocation_state text not null default 'disabled'::text check (
    invocation_state = any (array[
      'disabled'::text,
      'controlled_test'::text,
      'active'::text,
      'hold'::text,
      'revoked'::text
    ])
  ),
  requires_independent_verifier boolean not null default false,
  body_exposure_allowed boolean not null default false,
  output_class text not null default 'sanitized'::text,
  immutable_digest text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table chlom_runtime.vaulted_capability_registry enable row level security;
alter table chlom_runtime.vaulted_capability_registry force row level security;

drop policy if exists client_deny_all on chlom_runtime.vaulted_capability_registry;
create policy client_deny_all
  on chlom_runtime.vaulted_capability_registry
  as permissive
  for all
  to anon, authenticated
  using (false)
  with check (false);

revoke all on table chlom_runtime.vaulted_capability_registry from anon, authenticated;
grant select, insert, update on table chlom_runtime.vaulted_capability_registry to service_role;

create or replace view chlom_runtime.capability_contracts as
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

revoke all on chlom_runtime.capability_contracts from anon, authenticated;
grant select on chlom_runtime.capability_contracts to service_role;

comment on table chlom_runtime.vaulted_capability_registry is
  'Fail-closed registry for governed vaulted capabilities. Historical clean-replay bootstrap; capability bodies remain outside this table.';
comment on table chlom_secrets.trade_secret_assets is
  'Metadata-only trade-secret asset registry. No raw secret body is permitted in this table.';
comment on view chlom_runtime.capability_contracts is
  'Sanitized capability contract projection used by execution-builder identity migrations.';
