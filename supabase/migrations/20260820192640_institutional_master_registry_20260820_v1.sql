-- CrownThrive institutional-federation replay baseline v1.
-- This is a sanitized compatibility reconstruction for data-less Git replay.
-- Production received these prerequisite relations outside replayable source custody.
-- Version 20260820192640 is already applied in production; this source body is not
-- an instruction to rewrite production data or historical migration rows.

begin;

create schema if not exists institutional_federation;

revoke all on schema institutional_federation from public, anon, authenticated;
grant usage on schema institutional_federation to service_role;

create table if not exists institutional_federation.repository_registry (
  repo_id text primary key,
  repo_full_name text not null unique,
  github_repository_id bigint unique,
  repo_role text not null check (
    repo_role in ('canonical_parent','framework_child','service_child','research_child')
  ),
  parent_repo_id text references institutional_federation.repository_registry(repo_id),
  framework_id text,
  governance_state text not null check (
    governance_state in (
      'canonical_parent','pending_provisioning','provisioned_unlinked',
      'linked_governed','suspended','retired'
    )
  ),
  authority_ceiling text not null default 'D0' check (
    authority_ceiling in ('D0','D1','D2','D3')
  ),
  parent_governance_required boolean not null default true,
  child_self_activation_prohibited boolean not null default true,
  operationally_enabled boolean not null default false,
  can_vote boolean not null default false,
  voter_agent_id text,
  oidc_audience text not null default 'crownthrive-repository-federation',
  autonomous_scope jsonb not null default '[]'::jsonb,
  override_authority jsonb not null default '[]'::jsonb,
  parent_lock_keys jsonb not null default
    '["constitutional_governance","d3_human_authority","security_privacy","rights_legal","money_movement","repository_federation","vault_secret_policy","phase_hard_gates"]'::jsonb,
  required_parent_contract_version text not null default '1.0.0',
  public_contract_digest text,
  child_contract_digest text,
  last_parent_sha text,
  last_child_sha text,
  last_heartbeat_at timestamptz,
  heartbeat_ttl_seconds integer not null default 3900 check (
    heartbeat_ttl_seconds between 300 and 86400
  ),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (repo_role='canonical_parent' and parent_repo_id is null)
    or (repo_role<>'canonical_parent' and parent_repo_id is not null)
  ),
  check (not can_vote or voter_agent_id is not null),
  check (
    not operationally_enabled
    or governance_state in ('canonical_parent','linked_governed')
  )
);

create table if not exists institutional_federation.algorithm_registry (
  algorithm_id text primary key,
  framework_id text not null,
  canonical_name text not null,
  algorithm_version text not null,
  classification text not null default 'RESTRICTED_INSTITUTIONAL',
  public_contract_digest text not null,
  sealed_bundle_secret_name text not null,
  implementation_repo_id text references institutional_federation.repository_registry(repo_id),
  runtime_service_id text,
  runtime_entrypoint text,
  invocation_state text not null default 'controlled_test' check (
    invocation_state in (
      'disabled','controlled_test','production_limited',
      'production','suspended','retired'
    )
  ),
  authority_ceiling text not null default 'D2' check (
    authority_ceiling in ('D0','D1','D2','D3')
  ),
  agent_access_policy text not null default 'all_governed_agents',
  human_override_required boolean not null default true,
  public_spec_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  implementation_package_id text,
  unique (framework_id,algorithm_version)
);

create table if not exists institutional_federation.repository_agent_bindings (
  repo_id text not null references institutional_federation.repository_registry(repo_id) on delete cascade,
  agent_id text not null check (
    agent_id ~ '^ct[.](relay|agent|subagent|framework-agent)[.][a-z0-9._-]+$'
    or agent_id ~ '^ct[.]chlom[.]agent[.][a-z0-9._-]+$'
  ),
  agent_role text not null,
  framework_id text,
  parent_agent_id text,
  authority_ceiling text not null default 'D1' check (
    authority_ceiling in ('D0','D1','D2','D3')
  ),
  vote_eligible boolean not null default false,
  binding_state text not null default 'active' check (
    binding_state in ('prospective','active','suspended','retired')
  ),
  bootstrap_enabled boolean not null default false,
  heartbeat_enabled boolean not null default false,
  publish_enabled boolean not null default false,
  ack_enabled boolean not null default false,
  reference_enabled boolean not null default false,
  algorithm_enabled boolean not null default false,
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  certify_enabled boolean not null default false,
  sync_agents_enabled boolean not null default false,
  primary key (repo_id,agent_id)
);

alter table institutional_federation.repository_registry enable row level security;
alter table institutional_federation.algorithm_registry enable row level security;
alter table institutional_federation.repository_agent_bindings enable row level security;

revoke all on institutional_federation.repository_registry from public, anon, authenticated;
revoke all on institutional_federation.algorithm_registry from public, anon, authenticated;
revoke all on institutional_federation.repository_agent_bindings from public, anon, authenticated;

grant select, insert, update, delete on institutional_federation.repository_registry to service_role;
grant select, insert, update, delete on institutional_federation.algorithm_registry to service_role;
grant select, insert, update, delete on institutional_federation.repository_agent_bindings to service_role;

drop policy if exists repository_registry_service_role_all
  on institutional_federation.repository_registry;
create policy repository_registry_service_role_all
  on institutional_federation.repository_registry
  for all to service_role using (true) with check (true);

drop policy if exists algorithm_registry_service_role_all
  on institutional_federation.algorithm_registry;
create policy algorithm_registry_service_role_all
  on institutional_federation.algorithm_registry
  for all to service_role using (true) with check (true);

drop policy if exists repository_agent_bindings_service_role_all
  on institutional_federation.repository_agent_bindings;
create policy repository_agent_bindings_service_role_all
  on institutional_federation.repository_agent_bindings
  for all to service_role using (true) with check (true);

insert into institutional_federation.repository_registry (
  repo_id,
  repo_full_name,
  repo_role,
  governance_state,
  authority_ceiling,
  parent_governance_required,
  child_self_activation_prohibited,
  operationally_enabled,
  can_vote,
  oidc_audience,
  autonomous_scope,
  override_authority,
  parent_lock_keys,
  required_parent_contract_version,
  metadata
) values (
  'ct.repo.crownthrive-support',
  'crownthrive1/CrownThrive-OS',
  'canonical_parent',
  'canonical_parent',
  'D2',
  false,
  false,
  false,
  false,
  'crownthrive-repository-federation',
  '[]'::jsonb,
  '[]'::jsonb,
  '["constitutional_governance","d3_human_authority","security_privacy","rights_legal","money_movement","repository_federation","vault_secret_policy","phase_hard_gates"]'::jsonb,
  '1.0.0',
  jsonb_build_object(
    'replay_seed',true,
    'operational_authority',false,
    'production_data_copied',false,
    'source','sanitized_institutional_federation_replay_baseline_v1'
  )
)
on conflict (repo_id) do nothing;

comment on schema institutional_federation is
  'CrownThrive institutional registry namespace; replay baseline contains no production operational data.';
comment on table institutional_federation.repository_registry is
  'Sanitized replay-compatible repository identity registry. Production operational state is not copied.';
comment on table institutional_federation.algorithm_registry is
  'Restricted institutional algorithm contract registry; no secret bodies are stored here.';
comment on table institutional_federation.repository_agent_bindings is
  'Fail-closed repository-to-agent bindings; replay baseline grants no operational authority.';

commit;
