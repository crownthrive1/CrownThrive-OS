-- ct.chlom.vault-capability-structural-replay-bridge.v1
-- Purpose: restore the minimum non-secret structural prerequisites immediately
-- before 20260823202950_execution_builder_capability_contract_identity_v1.sql on
-- a fresh replay/Preview database when historical provider-applied source is absent.
--
-- Structural only: no credentials, Vault secrets, trade-secret bodies, capability
-- grants, provider activation, D3 authority, money movement, rights grants, votes,
-- certificates or execution authority. Existing production objects are preserved.

begin;

-- Fresh Preview replay may reach this compatibility bridge before the historical
-- migrations that originally created these schemas. Restore namespace shape only;
-- no executable capability, secret material or provider authority is created here.
create schema if not exists chlom_runtime;
revoke all on schema chlom_runtime from public, anon, authenticated;
grant usage on schema chlom_runtime to service_role;

create schema if not exists chlom_secrets;
revoke all on schema chlom_secrets from public, anon, authenticated;
grant usage on schema chlom_secrets to service_role;

create table if not exists chlom_secrets.trade_secret_assets (
  asset_id text primary key,
  asset_kind text not null,
  classification text not null check (classification in (
    'TRADE_SECRET','TRADE_SECRET_CANDIDATE','RESTRICTED_INSTITUTIONAL',
    'PUBLIC_CONTRACT_RESTRICTED_IMPLEMENTATION'
  )),
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
  unique(canonical_name,version)
);

alter table chlom_secrets.trade_secret_assets enable row level security;
alter table chlom_secrets.trade_secret_assets force row level security;
revoke all on chlom_secrets.trade_secret_assets from public, anon, authenticated;
grant select, insert, update on chlom_secrets.trade_secret_assets to service_role;
drop policy if exists client_deny_all on chlom_secrets.trade_secret_assets;
create policy client_deny_all on chlom_secrets.trade_secret_assets
for all to anon, authenticated using (false) with check (false);

create table if not exists chlom_runtime.vaulted_capability_registry (
  capability_id text primary key,
  asset_id text not null references chlom_secrets.trade_secret_assets(asset_id),
  capability_kind text not null check (capability_kind in (
    'sql_rpc','edge_function','provider_adapter','policy_bundle','oracle','non_executable'
  )),
  handler_ref text,
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2','D3')),
  allowed_agent_ids text[] not null default '{}',
  invocation_state text not null default 'disabled' check (invocation_state in (
    'disabled','controlled_test','active','hold','revoked'
  )),
  requires_independent_verifier boolean not null default false,
  body_exposure_allowed boolean not null default false,
  output_class text not null default 'sanitized',
  immutable_digest text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table chlom_runtime.vaulted_capability_registry enable row level security;
alter table chlom_runtime.vaulted_capability_registry force row level security;
revoke all on chlom_runtime.vaulted_capability_registry from public, anon, authenticated;
grant select, insert, update on chlom_runtime.vaulted_capability_registry to service_role;
drop policy if exists client_deny_all on chlom_runtime.vaulted_capability_registry;
create policy client_deny_all on chlom_runtime.vaulted_capability_registry
for all to anon, authenticated using (false) with check (false);

create or replace view chlom_runtime.capability_contracts
with (security_invoker=true) as
select
  capability_id, asset_id, capability_kind, handler_ref, authority_ceiling,
  allowed_agent_ids, invocation_state, requires_independent_verifier,
  body_exposure_allowed, output_class, immutable_digest, metadata,
  created_at, updated_at
from chlom_runtime.vaulted_capability_registry;
revoke all on chlom_runtime.capability_contracts from public, anon, authenticated;
grant select on chlom_runtime.capability_contracts to service_role;

do $verify$
declare
  v_view text;
  v_pk integer;
begin
  if to_regnamespace('chlom_runtime') is null
     or to_regnamespace('chlom_secrets') is null
     or to_regclass('chlom_runtime.capability_contracts') is null
     or to_regclass('chlom_runtime.vaulted_capability_registry') is null
     or to_regclass('chlom_secrets.trade_secret_assets') is null
  then raise exception 'HOLD_CAPABILITY_STRUCTURAL_REPLAY_BRIDGE_INCOMPLETE'; end if;

  select pg_get_viewdef('chlom_runtime.capability_contracts'::regclass,true) into v_view;
  if v_view not ilike '%chlom_runtime.vaulted_capability_registry%' then
    raise exception 'HOLD_CAPABILITY_VIEW_STORAGE_DRIFT';
  end if;

  select count(*) into v_pk
  from pg_constraint c
  join pg_class t on t.oid=c.conrelid
  join pg_namespace n on n.oid=t.relnamespace
  where n.nspname='chlom_runtime'
    and t.relname='vaulted_capability_registry'
    and c.contype='p'
    and pg_get_constraintdef(c.oid) ilike '%capability_id%';
  if v_pk<>1 then raise exception 'HOLD_CAPABILITY_BASE_PRIMARY_KEY_MISSING'; end if;
end
$verify$;

commit;
