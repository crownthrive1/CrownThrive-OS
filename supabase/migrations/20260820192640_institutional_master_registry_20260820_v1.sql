-- CrownThrive THIVEBASE Institutional Master Registry
-- Migration ID: ct.migration.institutional-master-registry.2026-08-20.v1
-- Classification: PRIVATE / GOVERNED DRAFT / NO SECRETS
-- State: DRAFT ONLY -- NOT APPLIED TO SUPABASE
-- Target project ref: tzajnzshmtzjenqulehq
-- Target schema: institutional_federation
--
-- Purpose
--   1. Add a cross-estate institutional master identity, immutable-version,
--      and source-binding layer without replacing domain registries.
--   2. Crosswalk the evidence-controlled Virality baseline of 14 assets and
--      16 versions without copying prices, checkout state, entitlements,
--      licensing terms, Drive file IDs, filenames, or Storage object paths.
--   3. Add the four foreign-key indexes identified by the Supabase advisor.
--   4. Register the institutional-memory steward only as a prospective,
--      non-voting, all-execution-disabled binding. A separate governed seed
--      is required to activate any capability after canonical GitHub evidence.
--
-- Canonical boundaries
--   * Google Drive remains authoritative for approved private master bytes.
--   * virality_control remains authoritative for Virality lifecycle details.
--   * CHLOM remains authoritative for rights, permissions, and licensing.
--   * institutional_federation owns cross-estate identity and provenance.
--
-- Expected additive seed counts at the controlled baseline
--   institutional_federation.master_registry:  +14 scoped rows
--   institutional_federation.master_versions:  +16 scoped rows
--   institutional_federation.master_bindings:  +30 scoped rows
--       14 domain-asset bindings + 16 domain-version bindings
--   institutional_federation.repository_agent_bindings: +1 prospective row
--   indexes: +7 when none already exist (3 new-table FK indexes and
--            4 advisor-remediation indexes). The master_versions master_id
--            FK is already covered by its leading-column unique constraint.

begin;

set local lock_timeout = '5s';
set local statement_timeout = '60s';

-- ---------------------------------------------------------------------------
-- 0. Evidence-controlled preflight
-- ---------------------------------------------------------------------------
-- This v1 migration is intentionally pinned to the inspected 14/16 Virality
-- baseline. If the source estate changes, fail closed and issue a reconciled
-- successor migration rather than silently widening this seed.

do $preflight$
declare
  v_asset_count integer;
  v_version_count integer;
  v_assets_with_versions integer;
  v_orphan_versions integer;
  v_invalid_digests integer;
  v_duplicate_digests integer;
  v_duplicate_version_roles integer;
begin
  if to_regclass('institutional_federation.repository_registry') is null then
    raise exception 'Missing required table institutional_federation.repository_registry';
  end if;

  if to_regclass('institutional_federation.repository_agent_bindings') is null then
    raise exception 'Missing required table institutional_federation.repository_agent_bindings';
  end if;

  if to_regclass('virality_control.asset_registry') is null
     or to_regclass('virality_control.asset_versions') is null then
    raise exception 'Missing required Virality source registry tables';
  end if;

  if not exists (
    select 1
    from institutional_federation.repository_registry
    where repo_id = 'ct.repo.crownthrive-support'
      and repo_role = 'canonical_parent'
  ) then
    raise exception 'Canonical parent repository is absent or not canonical_parent';
  end if;

  select count(*) into v_asset_count
  from virality_control.asset_registry;

  select count(*) into v_version_count
  from virality_control.asset_versions;

  select count(distinct asset_id) into v_assets_with_versions
  from virality_control.asset_versions;

  select count(*) into v_orphan_versions
  from virality_control.asset_versions v
  left join virality_control.asset_registry a on a.asset_id = v.asset_id
  where a.asset_id is null;

  select count(*) into v_invalid_digests
  from virality_control.asset_versions
  where sha256 is null or lower(sha256) !~ '^[0-9a-f]{64}$';

  select count(*) into v_duplicate_digests
  from (
    select lower(sha256)
    from virality_control.asset_versions
    group by lower(sha256)
    having count(*) > 1
  ) duplicates;

  select count(*) into v_duplicate_version_roles
  from (
    select asset_id, version_no, format_role
    from virality_control.asset_versions
    group by asset_id, version_no, format_role
    having count(*) > 1
  ) duplicates;

  if v_asset_count <> 14
     or v_version_count <> 16
     or v_assets_with_versions <> 14
     or v_orphan_versions <> 0
     or v_invalid_digests <> 0
     or v_duplicate_digests <> 0
     or v_duplicate_version_roles <> 0 then
    raise exception
      'Virality baseline drift: assets=%, versions=%, assets_with_versions=%, orphan_versions=%, invalid_digests=%, duplicate_digests=%, duplicate_version_roles=%',
      v_asset_count,
      v_version_count,
      v_assets_with_versions,
      v_orphan_versions,
      v_invalid_digests,
      v_duplicate_digests,
      v_duplicate_version_roles;
  end if;
end
$preflight$;

-- ---------------------------------------------------------------------------
-- 1. Canonical institutional master identity
-- ---------------------------------------------------------------------------

create table if not exists institutional_federation.master_registry (
  master_id text primary key,
  canonical_key text not null unique,
  canonical_name text not null,
  master_kind text not null,
  institutional_scope text not null,
  owner_repo_id text not null,
  authority_state text not null default 'candidate',
  rights_state text not null default 'pending_validation',
  visibility text not null default 'restricted',
  source_of_truth_policy text not null default 'domain_binding',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint master_registry_id_check
    check (master_id ~ '^ct[.]master[.][a-z0-9.-]+$'),
  constraint master_registry_canonical_key_check
    check (length(btrim(canonical_key)) > 0),
  constraint master_registry_canonical_name_check
    check (length(btrim(canonical_name)) > 0),
  constraint master_registry_kind_check
    check (master_kind in (
      'memory',
      'source_master',
      'asset',
      'product_identity',
      'document',
      'policy',
      'code',
      'agent_contract',
      'dataset',
      'other'
    )),
  constraint master_registry_authority_state_check
    check (authority_state in (
      'candidate',
      'governed',
      'blocked',
      'disputed',
      'retired'
    )),
  constraint master_registry_rights_state_check
    check (rights_state in (
      'pending_validation',
      'cleared',
      'restricted',
      'disputed',
      'expired',
      'blocked',
      'not_applicable'
    )),
  constraint master_registry_visibility_check
    check (visibility in ('restricted', 'internal', 'publishable', 'public')),
  constraint master_registry_source_of_truth_policy_check
    check (source_of_truth_policy in (
      'domain_binding',
      'institutional',
      'external_authority'
    )),
  constraint master_registry_owner_repo_id_fkey
    foreign key (owner_repo_id)
    references institutional_federation.repository_registry(repo_id)
    on delete restrict
);

comment on table institutional_federation.master_registry is
  'Cross-estate canonical identity and governance header. Domain lifecycle, commerce, rights terms, and binary custody remain with their designated authorities.';

-- ---------------------------------------------------------------------------
-- 2. Immutable version evidence
-- ---------------------------------------------------------------------------

create table if not exists institutional_federation.master_versions (
  master_version_id text primary key,
  master_id text not null,
  version_number integer not null,
  format_role text not null,
  content_sha256 text not null unique,
  media_type text not null,
  byte_size bigint not null,
  page_count integer,
  qa_state text not null default 'pending',
  accessibility_state text not null default 'unverified',
  visual_state text not null default 'unverified',
  evidence_state text not null default 'observed',
  immutable boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  source_created_at timestamptz,
  created_at timestamptz not null default now(),

  constraint master_versions_id_check
    check (master_version_id ~ '^ct[.]master-version[.][a-z0-9.-]+$'),
  constraint master_versions_version_number_check
    check (version_number > 0),
  constraint master_versions_format_role_check
    check (length(btrim(format_role)) > 0),
  constraint master_versions_sha256_check
    check (content_sha256 ~ '^[0-9a-f]{64}$'),
  constraint master_versions_byte_size_check
    check (byte_size >= 0),
  constraint master_versions_page_count_check
    check (page_count is null or page_count > 0),
  constraint master_versions_qa_state_check
    check (qa_state in ('pending', 'verified', 'hold', 'quarantined', 'rejected')),
  constraint master_versions_accessibility_state_check
    check (accessibility_state in (
      'unverified',
      'tagging_required',
      'tagged_unverified_pdfua',
      'verified',
      'not_applicable'
    )),
  constraint master_versions_visual_state_check
    check (visual_state in (
      'unverified',
      'verified',
      'upgrade_recommended',
      'rejected'
    )),
  constraint master_versions_evidence_state_check
    check (evidence_state in (
      'observed',
      'readback_verified',
      'digest_verified',
      'stale',
      'blocked',
      'quarantined'
    )),
  constraint master_versions_immutable_check
    check (immutable),
  constraint master_versions_master_id_fkey
    foreign key (master_id)
    references institutional_federation.master_registry(master_id)
    on delete restrict,
  constraint master_versions_master_version_format_key
    unique (master_id, version_number, format_role),
  constraint master_versions_id_master_key
    unique (master_version_id, master_id)
);

comment on table institutional_federation.master_versions is
  'Immutable digest and format evidence only. No Drive IDs, filenames, Storage object paths, prices, entitlement state, or licensing terms.';

-- ---------------------------------------------------------------------------
-- 3. Cross-estate source bindings
-- ---------------------------------------------------------------------------

create table if not exists institutional_federation.master_bindings (
  binding_id text primary key,
  master_id text not null,
  master_version_id text,
  binding_scope text not null,
  source_system text not null,
  source_schema text not null,
  source_table text not null,
  source_record_key text not null,
  binding_role text not null,
  verification_state text not null default 'observed',
  authoritative boolean not null default false,
  evidence_ref text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  constraint master_bindings_id_check
    check (binding_id ~ '^ct[.]binding[.][a-z0-9.-]+$'),
  constraint master_bindings_scope_check
    check (binding_scope in ('master', 'version')),
  constraint master_bindings_scope_version_check
    check (
      (binding_scope = 'master' and master_version_id is null)
      or
      (binding_scope = 'version' and master_version_id is not null)
    ),
  constraint master_bindings_source_check
    check (
      length(btrim(source_system)) > 0
      and length(btrim(source_schema)) > 0
      and length(btrim(source_table)) > 0
      and length(btrim(source_record_key)) > 0
    ),
  constraint master_bindings_role_check
    check (binding_role in (
      'domain_asset',
      'domain_version',
      'source_reference',
      'custody_reference',
      'rights_reference',
      'repository_reference',
      'documentation_reference',
      'other'
    )),
  constraint master_bindings_verification_state_check
    check (verification_state in (
      'observed',
      'readback_verified',
      'digest_verified',
      'stale',
      'blocked',
      'superseded'
    )),
  constraint master_bindings_master_id_fkey
    foreign key (master_id)
    references institutional_federation.master_registry(master_id)
    on delete restrict,
  constraint master_bindings_version_master_fkey
    foreign key (master_version_id, master_id)
    references institutional_federation.master_versions(master_version_id, master_id)
    on delete restrict,
  constraint master_bindings_source_record_key
    unique (
      source_system,
      source_schema,
      source_table,
      source_record_key,
      binding_role
    )
);

comment on table institutional_federation.master_bindings is
  'Logical crosswalks to designated source authorities. A binding is not rights, release, commerce, or binary-parity certification.';

-- ---------------------------------------------------------------------------
-- 4. Private service-role-only access posture
-- ---------------------------------------------------------------------------

alter table institutional_federation.master_registry enable row level security;
alter table institutional_federation.master_versions enable row level security;
alter table institutional_federation.master_bindings enable row level security;

revoke all privileges on table institutional_federation.master_registry
  from public, anon, authenticated;
revoke all privileges on table institutional_federation.master_versions
  from public, anon, authenticated;
revoke all privileges on table institutional_federation.master_bindings
  from public, anon, authenticated;

grant select, insert, update, delete
  on table institutional_federation.master_registry
  to service_role;
grant select, insert, update, delete
  on table institutional_federation.master_versions
  to service_role;
grant select, insert, update, delete
  on table institutional_federation.master_bindings
  to service_role;

do $policies$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'institutional_federation'
      and tablename = 'master_registry'
      and policyname = 'master_registry_service_role_all'
  ) then
    execute $policy$
      create policy master_registry_service_role_all
      on institutional_federation.master_registry
      for all to service_role
      using (true)
      with check (true)
    $policy$;
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'institutional_federation'
      and tablename = 'master_versions'
      and policyname = 'master_versions_service_role_all'
  ) then
    execute $policy$
      create policy master_versions_service_role_all
      on institutional_federation.master_versions
      for all to service_role
      using (true)
      with check (true)
    $policy$;
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'institutional_federation'
      and tablename = 'master_bindings'
      and policyname = 'master_bindings_service_role_all'
  ) then
    execute $policy$
      create policy master_bindings_service_role_all
      on institutional_federation.master_bindings
      for all to service_role
      using (true)
      with check (true)
    $policy$;
  end if;
end
$policies$;

-- New-table foreign-key indexes. These keep the additive registry clean under
-- the same advisor standard applied to the existing control plane.
create index if not exists master_registry_owner_repo_id_idx
  on institutional_federation.master_registry(owner_repo_id);

create index if not exists master_bindings_master_id_idx
  on institutional_federation.master_bindings(master_id);

create index if not exists master_bindings_version_master_idx
  on institutional_federation.master_bindings(master_version_id, master_id);

-- ---------------------------------------------------------------------------
-- 5. Deterministic Virality crosswalk seed
-- ---------------------------------------------------------------------------
-- IDs derive from existing source UUIDs. No new UUID values are hardcoded or
-- generated, so retries address the same logical records.

insert into institutional_federation.master_registry (
  master_id,
  canonical_key,
  canonical_name,
  master_kind,
  institutional_scope,
  owner_repo_id,
  authority_state,
  rights_state,
  visibility,
  source_of_truth_policy,
  metadata,
  created_at,
  updated_at
)
select
  'ct.master.virality.' || a.asset_id::text,
  'virality_music:' || a.canonical_key,
  a.title,
  'asset',
  'virality_music',
  'ct.repo.crownthrive-support',
  case a.canonicality_state
    when 'canonical' then 'governed'
    when 'retired' then 'retired'
    when 'disputed' then 'disputed'
    else 'candidate'
  end,
  a.rights_state,
  'restricted',
  'domain_binding',
  jsonb_strip_nulls(jsonb_build_object(
    'domain_asset_class', a.asset_class,
    'edition_label', a.edition_label,
    'governing_world', a.governing_world,
    'source_canonicality_state', a.canonicality_state,
    'source_release_state', a.release_state
  )),
  a.created_at,
  a.updated_at
from virality_control.asset_registry a
order by a.asset_id
on conflict (master_id) do nothing;

insert into institutional_federation.master_versions (
  master_version_id,
  master_id,
  version_number,
  format_role,
  content_sha256,
  media_type,
  byte_size,
  page_count,
  qa_state,
  accessibility_state,
  visual_state,
  evidence_state,
  immutable,
  metadata,
  source_created_at,
  created_at
)
select
  'ct.master-version.virality.' || v.version_id::text,
  'ct.master.virality.' || v.asset_id::text,
  v.version_no,
  v.format_role,
  lower(v.sha256),
  v.mime_type,
  v.byte_size,
  v.page_count,
  v.qa_state,
  v.accessibility_state,
  v.visual_state,
  case v.binary_state
    when 'dual_verified' then 'digest_verified'
    when 'drive_verified' then 'readback_verified'
    when 'quarantined' then 'quarantined'
    when 'rejected' then 'blocked'
    else 'observed'
  end,
  true,
  jsonb_build_object('source_binary_state', v.binary_state),
  v.created_at,
  now()
from virality_control.asset_versions v
order by v.version_id
on conflict (master_version_id) do nothing;

-- Asset-level domain bindings: 14 expected.
insert into institutional_federation.master_bindings (
  binding_id,
  master_id,
  master_version_id,
  binding_scope,
  source_system,
  source_schema,
  source_table,
  source_record_key,
  binding_role,
  verification_state,
  authoritative,
  evidence_ref,
  metadata,
  created_at,
  updated_at
)
select
  'ct.binding.virality.asset.' || a.asset_id::text,
  'ct.master.virality.' || a.asset_id::text,
  null,
  'master',
  'supabase',
  'virality_control',
  'asset_registry',
  a.asset_id::text,
  'domain_asset',
  'observed',
  true,
  'ct.migration.institutional-master-registry.2026-08-20.v1',
  '{}'::jsonb,
  now(),
  now()
from virality_control.asset_registry a
order by a.asset_id
on conflict (binding_id) do nothing;

-- Version-level domain bindings: 16 expected.
insert into institutional_federation.master_bindings (
  binding_id,
  master_id,
  master_version_id,
  binding_scope,
  source_system,
  source_schema,
  source_table,
  source_record_key,
  binding_role,
  verification_state,
  authoritative,
  evidence_ref,
  metadata,
  created_at,
  updated_at
)
select
  'ct.binding.virality.version.' || v.version_id::text,
  'ct.master.virality.' || v.asset_id::text,
  'ct.master-version.virality.' || v.version_id::text,
  'version',
  'supabase',
  'virality_control',
  'asset_versions',
  v.version_id::text,
  'domain_version',
  'observed',
  true,
  'ct.migration.institutional-master-registry.2026-08-20.v1',
  '{}'::jsonb,
  now(),
  now()
from virality_control.asset_versions v
order by v.version_id
on conflict (binding_id) do nothing;

-- ---------------------------------------------------------------------------
-- 6. Prospective steward binding
-- ---------------------------------------------------------------------------
-- This is safe before a draft GitHub PR exists because the binding is
-- prospective, non-voting, and every execution/capability flag is false.
-- The D1 value is only a ceiling aligned to the private charter; it grants no
-- runtime capability. Any activation requires a separately reviewed seed tied
-- to canonical GitHub evidence, quorum, rollback, and readback verification.

insert into institutional_federation.repository_agent_bindings (
  repo_id,
  agent_id,
  agent_role,
  framework_id,
  parent_agent_id,
  authority_ceiling,
  vote_eligible,
  binding_state,
  bootstrap_enabled,
  heartbeat_enabled,
  publish_enabled,
  ack_enabled,
  reference_enabled,
  algorithm_enabled,
  source_ref,
  metadata,
  created_at,
  updated_at,
  certify_enabled,
  sync_agents_enabled
)
values (
  'ct.repo.crownthrive-support',
  'ct.agent.institutional-memory-asset-steward',
  'institutional_memory_asset_steward',
  null,
  null,
  'D1',
  false,
  'prospective',
  false,
  false,
  false,
  false,
  false,
  false,
  'ct.charter.institutional-memory-control-plane.v1',
  jsonb_build_object(
    'default_autonomy', 'A1',
    'execution_disabled', true,
    'draft_pr_exists_at_seed', false,
    'activation_gate', 'separate_governed_seed_after_canonical_github_evidence',
    'd2_rule', 'independent_review_quorum_rollback_readback_required',
    'd3_rule', 'human_reserved'
  ),
  now(),
  now(),
  false,
  false
)
on conflict (repo_id, agent_id) do nothing;

-- ---------------------------------------------------------------------------
-- 7. Existing advisor remediation: additive covering indexes
-- ---------------------------------------------------------------------------

create index if not exists creative_asset_routes_surface_id_idx
  on integration_control.creative_asset_routes(surface_id);

create index if not exists site_interaction_check_results_check_id_idx
  on integration_control.site_interaction_check_results(check_id);

create index if not exists site_update_queue_source_result_id_idx
  on integration_control.site_update_queue(source_result_id);

create index if not exists site_update_queue_surface_id_idx
  on integration_control.site_update_queue(surface_id);

-- ---------------------------------------------------------------------------
-- 8. Fail-closed post-seed validation
-- ---------------------------------------------------------------------------

do $validation$
declare
  v_master_count integer;
  v_version_count integer;
  v_binding_count integer;
  v_asset_binding_count integer;
  v_version_binding_count integer;
  v_orphan_master_versions integer;
  v_invalid_binding_pairs integer;
  v_steward_count integer;
begin
  select count(*) into v_master_count
  from institutional_federation.master_registry
  where master_id like 'ct.master.virality.%';

  select count(*) into v_version_count
  from institutional_federation.master_versions
  where master_version_id like 'ct.master-version.virality.%';

  select count(*) into v_binding_count
  from institutional_federation.master_bindings
  where binding_id like 'ct.binding.virality.%';

  select count(*) into v_asset_binding_count
  from institutional_federation.master_bindings
  where binding_id like 'ct.binding.virality.asset.%'
    and binding_scope = 'master'
    and master_version_id is null;

  select count(*) into v_version_binding_count
  from institutional_federation.master_bindings
  where binding_id like 'ct.binding.virality.version.%'
    and binding_scope = 'version'
    and master_version_id is not null;

  select count(*) into v_orphan_master_versions
  from institutional_federation.master_versions v
  left join institutional_federation.master_registry m
    on m.master_id = v.master_id
  where v.master_version_id like 'ct.master-version.virality.%'
    and m.master_id is null;

  select count(*) into v_invalid_binding_pairs
  from institutional_federation.master_bindings b
  left join institutional_federation.master_versions v
    on v.master_version_id = b.master_version_id
   and v.master_id = b.master_id
  where b.binding_id like 'ct.binding.virality.version.%'
    and v.master_version_id is null;

  select count(*) into v_steward_count
  from institutional_federation.repository_agent_bindings
  where repo_id = 'ct.repo.crownthrive-support'
    and agent_id = 'ct.agent.institutional-memory-asset-steward'
    and binding_state = 'prospective'
    and vote_eligible = false
    and bootstrap_enabled = false
    and heartbeat_enabled = false
    and publish_enabled = false
    and ack_enabled = false
    and reference_enabled = false
    and algorithm_enabled = false
    and certify_enabled = false
    and sync_agents_enabled = false;

  if v_master_count <> 14
     or v_version_count <> 16
     or v_binding_count <> 30
     or v_asset_binding_count <> 14
     or v_version_binding_count <> 16
     or v_orphan_master_versions <> 0
     or v_invalid_binding_pairs <> 0
     or v_steward_count <> 1 then
    raise exception
      'Institutional master validation failed: masters=%, versions=%, bindings=%, asset_bindings=%, version_bindings=%, orphan_versions=%, invalid_binding_pairs=%, safe_steward_bindings=%',
      v_master_count,
      v_version_count,
      v_binding_count,
      v_asset_binding_count,
      v_version_binding_count,
      v_orphan_master_versions,
      v_invalid_binding_pairs,
      v_steward_count;
  end if;

  if exists (
    select 1
    from information_schema.role_table_grants
    where table_schema = 'institutional_federation'
      and table_name in ('master_registry', 'master_versions', 'master_bindings')
      and grantee in ('anon', 'authenticated')
  ) then
    raise exception 'Unexpected anon/authenticated grant on institutional master tables';
  end if;

  if exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'institutional_federation'
      and c.relname in ('master_registry', 'master_versions', 'master_bindings')
      and c.relkind in ('r', 'p')
      and not c.relrowsecurity
  ) then
    raise exception 'RLS is not enabled on every institutional master table';
  end if;

  if (
    select count(*)
    from pg_policies
    where schemaname = 'institutional_federation'
      and tablename in ('master_registry', 'master_versions', 'master_bindings')
      and roles = array['service_role']::name[]
  ) <> 3 then
    raise exception 'Expected exactly three service-role policies on institutional master tables';
  end if;
end
$validation$;

-- Applying this migration does not prove Drive byte parity, Storage upload,
-- rights clearance, accessibility, product readiness, checkout, publication,
-- Mintlify acceptance, GitHub merge, Phase 2.99 exit, or Phase 3 entry.

commit;
