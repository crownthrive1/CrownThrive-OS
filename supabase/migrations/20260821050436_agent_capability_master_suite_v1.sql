begin;

create table if not exists chlom_runtime.agent_suite_registry (
  suite_id text primary key,
  semantic_version text not null,
  canonical_name text not null,
  release_state text not null check (release_state in ('controlled_test','hold','active','paused','superseded','retired')),
  manifest_ref text not null,
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  parent_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  parent_certifier_id text not null,
  vote_eligible boolean not null default false check (vote_eligible = false),
  quorum_eligible boolean not null default false check (quorum_eligible = false),
  d3_human_reserved boolean not null default true check (d3_human_reserved = true),
  no_self_approval boolean not null default true check (no_self_approval = true),
  no_silent_delete boolean not null default true check (no_silent_delete = true),
  drive_custody_required boolean not null default true check (drive_custody_required = true),
  supabase_storage_required boolean not null default true check (supabase_storage_required = true),
  vault_secret_ref text not null,
  source_ids text[] not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.agent_privilege_profiles (
  profile_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  agent_id text not null unique references chlom_runtime.agent_templates(agent_id) on delete restrict,
  operating_mode text not null check (operating_mode in ('rigid','fluid','hybrid')),
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2')),
  allowed_capabilities text[] not null,
  forbidden_capabilities text[] not null,
  privilege_state text not null check (privilege_state in ('specified','test','active','expired','paused','superseded','retired')),
  special_privilege_requested boolean not null default false,
  special_privilege_receipt text,
  expires_at timestamptz not null,
  manifest_ref text not null,
  source_ids text[] not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (array_position(forbidden_capabilities, 'delete') is not null),
  check (array_position(forbidden_capabilities, 'self_approve') is not null),
  check (array_position(forbidden_capabilities, 'vote') is not null),
  check ((special_privilege_requested = false) or (nullif(btrim(special_privilege_receipt), '') is not null))
);

create table if not exists chlom_runtime.agent_schedule_definitions (
  schedule_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  canonical_name text not null,
  timezone text not null,
  ical text not null,
  timing_mode text not null check (timing_mode in ('exact_schedule','flexible_schedule','condition_watch')),
  skill_name text not null,
  agent_ids text[] not null check (cardinality(agent_ids) > 0),
  execution_state text not null check (execution_state in ('registered_external_pending','active','paused','failed','superseded','retired')),
  external_task_id text,
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((execution_state <> 'active') or (nullif(btrim(external_task_id), '') is not null))
);

create table if not exists chlom_runtime.committee_support_registry (
  committee_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  canonical_name text not null,
  source_url text not null,
  support_agent_ids text[] not null check (cardinality(support_agent_ids) > 0),
  support_state text not null check (support_state in ('specified','test','active','paused','superseded','retired')),
  drift_state text not null check (drift_state in ('NONE','WATCH','NEED_TO_DO','BLOCKED')),
  authority_boundary text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.agent_skill_packages (
  skill_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  agent_id text not null unique references chlom_runtime.agent_templates(agent_id) on delete restrict,
  install_name text not null unique,
  semantic_version text not null,
  generation_support text[] not null check (cardinality(generation_support) > 0),
  manifest_ref text not null,
  manifest_sha256 text,
  mcp_state text not null check (mcp_state in ('disabled','candidate','test','active','paused','superseded','retired')),
  commercial_state text not null check (commercial_state in ('hold','candidate','test','active','paused','superseded','retired')),
  price_credits integer check (price_credits is null or price_credits >= 400),
  checkout_enabled boolean not null default false,
  entitlement_active boolean not null default false,
  release_receipt text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((mcp_state <> 'active') or (nullif(btrim(release_receipt), '') is not null)),
  check ((commercial_state <> 'active') or (price_credits is not null and checkout_enabled and entitlement_active and nullif(btrim(release_receipt), '') is not null))
);

create table if not exists chlom_runtime.integrity_evidence_ledger (
  evidence_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  evidence_class text not null check (evidence_class in ('source_audit','archive','supply_chain','agent_audit','custody','restore','framework_test','pricing_test','linkage_test')),
  subject_ref text not null,
  evidence_state text not null check (evidence_state in ('pass','pass_with_warnings','watch','need_to_do','hold','failed','superseded')),
  content_sha256 text check (content_sha256 is null or content_sha256 ~ '^[0-9a-f]{64}$'),
  supersedes_evidence_id text references chlom_runtime.integrity_evidence_ledger(evidence_id) on delete restrict,
  source_refs text[] not null,
  payload jsonb not null default '{}'::jsonb,
  created_by_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verified_by_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  created_at timestamptz not null default now(),
  check (created_by_agent_id is null or verified_by_agent_id is null or created_by_agent_id <> verified_by_agent_id)
);

create table if not exists chlom_runtime.linkage_candidates (
  edge_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  source_ref text not null,
  target_ref text not null,
  relation_type text not null,
  retroactive boolean not null default true,
  edge_state text not null check (edge_state in ('candidate','approved','applied','rejected','superseded')),
  approval_receipt text,
  proposed_by_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verified_by_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (proposed_by_agent_id is distinct from verified_by_agent_id),
  check ((edge_state not in ('approved','applied')) or (nullif(btrim(approval_receipt), '') is not null))
);

create table if not exists chlom_runtime.framework_compilation_runs (
  run_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  candidate_id text not null,
  candidate_type text not null check (candidate_type in ('framework','capability_pack','policy_pack','pallet')),
  builder_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verifier_agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  output_sha256 text check (output_sha256 is null or output_sha256 ~ '^[0-9a-f]{64}$'),
  run_state text not null check (run_state in ('specified','compiled_test_hold','failed','parent_review','certified','superseded')),
  test_state text not null check (test_state in ('pending','pass','pass_with_warnings','failed')),
  parent_certification_state text not null check (parent_certification_state in ('pending','approved','rejected','superseded')),
  framework_count_delta smallint not null default 0 check (framework_count_delta in (0,1)),
  activation_allowed boolean not null default false,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (builder_agent_id <> verifier_agent_id),
  check ((run_state <> 'certified') or (parent_certification_state = 'approved' and test_state = 'pass'))
);

create table if not exists chlom_runtime.pricing_policy_versions (
  pricing_policy_id text primary key,
  suite_id text not null references chlom_runtime.agent_suite_registry(suite_id) on delete restrict,
  semantic_version text not null,
  policy_state text not null check (policy_state in ('governed_hold','candidate','test','active','paused','superseded','retired')),
  currency text not null,
  minimum_credit_transaction integer not null check (minimum_credit_transaction >= 400),
  top_up_candidates jsonb not null,
  forbidden_features text[] not null,
  checkout_enabled boolean not null default false,
  stripe_objects_created boolean not null default false,
  activation_receipt text,
  source_ref text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((policy_state <> 'active') or (checkout_enabled and stripe_objects_created and nullif(btrim(activation_receipt), '') is not null))
);

create or replace function chlom_runtime.reject_master_suite_delete_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, chlom_runtime
as $$
begin
  raise exception 'CHLOM master-suite records are append-only; supersede with a new record instead of deleting %', tg_table_name;
end;
$$;

create or replace function chlom_runtime.reject_master_suite_evidence_mutation_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, chlom_runtime
as $$
begin
  raise exception 'CHLOM integrity evidence is immutable; append a superseding evidence record instead';
end;
$$;

create or replace function chlom_runtime.enforce_master_suite_template_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, chlom_runtime
as $$
begin
  if tg_op = 'UPDATE'
     and old.metadata ->> 'suite_id' = 'ct.agent-suite.master.v1'
     and new.metadata ->> 'suite_id' is distinct from 'ct.agent-suite.master.v1' then
    raise exception 'suite identity cannot be silently removed';
  end if;
  if new.metadata ->> 'suite_id' = 'ct.agent-suite.master.v1' then
    if new.vote_eligible or not new.no_self_approval or new.authority_ceiling = 'D3' then
      raise exception 'master-suite agent violates nonvoting, no-self-approval, or D3-human-reserved invariant';
    end if;
    if new.metadata ->> 'operating_mode' not in ('rigid','fluid','hybrid') then
      raise exception 'master-suite operating mode must be rigid, fluid, or hybrid';
    end if;
    if not (new.tool_scope @> '{"delete":false,"merge":false,"deploy":false,"publish":false,"live_finance":false,"credential_export":false}'::jsonb) then
      raise exception 'master-suite dangerous capabilities must remain fail-closed';
    end if;
    if new.lifecycle_state = 'active' and nullif(btrim(new.metadata ->> 'activation_receipt'), '') is null then
      raise exception 'active master-suite agents require an activation receipt';
    end if;
  end if;
  return new;
end;
$$;

create or replace function chlom_runtime.reject_master_suite_health_delete_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, chlom_runtime
as $$
begin
  if exists (
    select 1 from chlom_runtime.agent_templates t
    where t.agent_id=old.agent_id and t.metadata ->> 'suite_id'='ct.agent-suite.master.v1'
  ) then
    raise exception 'CHLOM master-suite health records cannot be deleted; append or supersede state';
  end if;
  return old;
end;
$$;

revoke all on function chlom_runtime.reject_master_suite_delete_v1() from public;
revoke all on function chlom_runtime.reject_master_suite_evidence_mutation_v1() from public;
revoke all on function chlom_runtime.enforce_master_suite_template_v1() from public;
revoke all on function chlom_runtime.reject_master_suite_health_delete_v1() from public;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'agent_suite_registry','agent_privilege_profiles','agent_schedule_definitions',
    'committee_support_registry','agent_skill_packages','linkage_candidates',
    'framework_compilation_runs','pricing_policy_versions'
  ] loop
    if not exists (
      select 1 from pg_trigger
      where tgname = 'reject_delete_' || table_name || '_v1'
        and tgrelid = format('chlom_runtime.%I', table_name)::regclass
    ) then
      execute format(
        'create trigger %I before delete on chlom_runtime.%I for each row execute function chlom_runtime.reject_master_suite_delete_v1()',
        'reject_delete_' || table_name || '_v1', table_name
      );
    end if;
  end loop;
end;
$$;

do $$
begin
  if not exists (select 1 from pg_trigger where tgname='reject_integrity_evidence_update_v1' and tgrelid='chlom_runtime.integrity_evidence_ledger'::regclass) then
    create trigger reject_integrity_evidence_update_v1
      before update or delete on chlom_runtime.integrity_evidence_ledger
      for each row execute function chlom_runtime.reject_master_suite_evidence_mutation_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='enforce_master_suite_template_v1' and tgrelid='chlom_runtime.agent_templates'::regclass) then
    create trigger enforce_master_suite_template_v1
      before insert or update on chlom_runtime.agent_templates
      for each row execute function chlom_runtime.enforce_master_suite_template_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_template_delete_v1' and tgrelid='chlom_runtime.agent_templates'::regclass) then
    create trigger reject_master_suite_template_delete_v1
      before delete on chlom_runtime.agent_templates
      for each row
      when (old.metadata ->> 'suite_id' = 'ct.agent-suite.master.v1')
      execute function chlom_runtime.reject_master_suite_delete_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_health_delete_v1' and tgrelid='chlom_runtime.agent_health'::regclass) then
    create trigger reject_master_suite_health_delete_v1
      before delete on chlom_runtime.agent_health
      for each row execute function chlom_runtime.reject_master_suite_health_delete_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_identity_delete_v1' and tgrelid='chlom_identity.agent_identity_records'::regclass) then
    create trigger reject_master_suite_identity_delete_v1
      before delete on chlom_identity.agent_identity_records
      for each row
      when (old.source_ref = 'ct.agent-suite.master.v1')
      execute function chlom_runtime.reject_master_suite_delete_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_backup_delete_v1' and tgrelid='chlom_runtime.backup_manifests'::regclass) then
    create trigger reject_master_suite_backup_delete_v1
      before delete on chlom_runtime.backup_manifests
      for each row
      when (old.metadata ->> 'suite_id' = 'ct.agent-suite.master.v1')
      execute function chlom_runtime.reject_master_suite_delete_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_module_delete_v1' and tgrelid='chlom_runtime.modules'::regclass) then
    create trigger reject_master_suite_module_delete_v1
      before delete on chlom_runtime.modules
      for each row
      when (old.metadata ->> 'suite_id' = 'ct.agent-suite.master.v1')
      execute function chlom_runtime.reject_master_suite_delete_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_storage_object_delete_v1' and tgrelid='storage.objects'::regclass) then
    create trigger reject_master_suite_storage_object_delete_v1
      before delete on storage.objects
      for each row
      when (old.bucket_id = 'chlom-private-recovery')
      execute function chlom_runtime.reject_master_suite_delete_v1();
  end if;
  if not exists (select 1 from pg_trigger where tgname='reject_master_suite_storage_bucket_delete_v1' and tgrelid='storage.buckets'::regclass) then
    create trigger reject_master_suite_storage_bucket_delete_v1
      before delete on storage.buckets
      for each row
      when (old.id = 'chlom-private-recovery')
      execute function chlom_runtime.reject_master_suite_delete_v1();
  end if;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'agent_suite_registry','agent_privilege_profiles','agent_schedule_definitions',
    'committee_support_registry','agent_skill_packages','integrity_evidence_ledger',
    'linkage_candidates','framework_compilation_runs','pricing_policy_versions'
  ] loop
    execute format('alter table chlom_runtime.%I enable row level security', table_name);
    execute format('alter table chlom_runtime.%I force row level security', table_name);
    execute format('revoke all on table chlom_runtime.%I from public, anon, authenticated', table_name);
    execute format('grant select, insert, update on table chlom_runtime.%I to service_role', table_name);
    if not exists (
      select 1 from pg_policies
      where schemaname='chlom_runtime' and tablename=table_name and policyname='service_role_select_insert_update'
    ) then
      execute format(
        'create policy service_role_select_insert_update on chlom_runtime.%I for all to service_role using (true) with check (true)',
        table_name
      );
    end if;
  end loop;
end;
$$;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'chlom-private-recovery',
  'chlom-private-recovery',
  false,
  104857600,
  array['application/zip','application/json','text/markdown','text/csv','text/plain']::text[]
)
on conflict (id) do nothing;

do $$
begin
  if not exists (select 1 from vault.secrets where name='ct_agent_suite_manifest_hmac_v1') then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(32), 'hex'),
      'ct_agent_suite_manifest_hmac_v1',
      'CHLOM master agent suite manifest seal; generated 2026-08-21; never export through public surfaces'
    );
  end if;
end;
$$;

insert into chlom_runtime.agent_suite_registry (
  suite_id, semantic_version, canonical_name, release_state, manifest_ref, manifest_sha256,
  parent_agent_id, parent_certifier_id, source_ids, vault_secret_ref, metadata
)
values (
  'ct.agent-suite.master.v1', '1.0.0', 'CrownThrive Master Governed Agent Suite', 'controlled_test',
  'developers/manifests/agent-capability-master-suite.v1.json',
  '670ee1a98d577658f73566079da4f945d5a9ff8a330409f6643f4a1a38013fbe',
  'ct.chlom.agent.orchestrator', 'ct.relay.agent-d',
  array['ADR-006','ADR-007','ADR-008','ADR-012','ADR-014','ADR-015','ADR-016','ADR-017','ADR-018','CHLOM-MCP-CONTRACT-1.0'],
  'vault://ct_agent_suite_manifest_hmac_v1',
  '{"phase":"2.99","framework_count_delta":0,"sovereign_voter_count_delta":0,"detached_v2_state":"quarantined_hold"}'::jsonb
)
on conflict (suite_id) do nothing;

insert into chlom_runtime.modules (
  module_id, canonical_name, module_class, semantic_version, lifecycle_state,
  authority_ceiling, self_healing_class, public_contract, restricted_contract_ref,
  implementation_ref, mcp_enabled, api_enabled, metadata
)
values
  ('ct.module.integrity-mesh','Agent Integrity Mesh','observability','1.0.0','specified','D2','observe_only','{"nonvoting":true,"no_self_approval":true}'::jsonb,'vault://ct_agent_suite_manifest_hmac_v1','developers/manifests/agent-capability-master-suite.v1.json',false,false,'{"suite_id":"ct.agent-suite.master.v1","capability_pack":true}'::jsonb),
  ('ct.module.framework-foundry','Framework Foundry Capability Pack','pallet','1.0.0','specified','D2','observe_only','{"framework_count_delta":0,"activation_allowed":false}'::jsonb,'vault://ct_agent_suite_manifest_hmac_v1','scripts/framework_compiler.py',false,false,'{"suite_id":"ct.agent-suite.master.v1","not_a_ninth_framework":true}'::jsonb),
  ('ct.module.market-growth','Pricing Marketing and Sales Capability Pack','service','1.0.0','specified','D1','observe_only','{"live_commerce":false,"external_outreach":false}'::jsonb,'vault://ct_agent_suite_manifest_hmac_v1','developers/manifests/pricing-policy-candidates.v1.json',false,false,'{"suite_id":"ct.agent-suite.master.v1","commercial_state":"hold"}'::jsonb),
  ('ct.module.thrivealumni-support','ThriveAlumni Committee Support Capability Pack','governance','1.0.0','specified','D2','observe_only','{"officeholder":false,"vote_eligible":false,"quorum_eligible":false}'::jsonb,'vault://ct_agent_suite_manifest_hmac_v1','governance/agent-suite-v1/committee-registry.json',false,false,'{"suite_id":"ct.agent-suite.master.v1","authority":"support_only"}'::jsonb)
on conflict (module_id) do nothing;

with seed(agent_id, canonical_name, agent_class, autonomy_class, authority_ceiling, schedule_profile, operating_mode, family) as (
  values
    ('ct.chlom.agent.price-intelligence','Pricing Intelligence Analyst','researcher','A1','D1','monthly','fluid','pricing'),
    ('ct.chlom.agent.price-certifier','Pricing Policy Independent Certifier','verifier','A1','D1','monthly','rigid','pricing'),
    ('ct.chlom.agent.archive-integrity','ZIP and File Integrity Guardian','verifier','A2','D1','hourly','rigid','integrity'),
    ('ct.chlom.agent.supply-chain-integrity','Workflow Supply Chain Integrity Guardian','security','A2','D2','hourly','rigid','integrity'),
    ('ct.chlom.agent.linkage-curator','Internal Linkage Curator','documentation','A2','D1','daily','hybrid','knowledge'),
    ('ct.chlom.agent.knowledge-extractor','Institutional Knowledge Extractor','researcher','A2','D1','daily','fluid','knowledge'),
    ('ct.chlom.agent.framework-architect','Framework Architect','planner','A2','D2','weekly','hybrid','framework_factory'),
    ('ct.chlom.agent.framework-compiler','Deterministic Framework Compiler','builder','A2','D1','weekly','rigid','framework_factory'),
    ('ct.chlom.agent.framework-verifier','Independent Framework Test Verifier','formal_methods','A1','D2','weekly','rigid','framework_factory'),
    ('ct.chlom.agent.version-threat-upgrader','Scoped Version and Threat Upgrader','security','A2','D2','daily','hybrid','security'),
    ('ct.chlom.agent.agent-auditor','Independent Agent Auditor','verifier','A1','D2','hourly','rigid','assurance'),
    ('ct.chlom.agent.marketing-intelligence','Marketing Intelligence Agent','researcher','A1','D1','weekly','fluid','growth'),
    ('ct.chlom.agent.sales-enablement','Sales Enablement Agent','researcher','A1','D1','weekly','fluid','growth'),
    ('ct.thrivealumni.agent.board-secretariat','ThriveAlumni Board Governance Secretariat','documentation','A1','D1','monthly','rigid','thrivealumni'),
    ('ct.thrivealumni.agent.executive-ops','ThriveAlumni Executive Operations Orchestrator','orchestrator','A2','D2','monthly','hybrid','thrivealumni'),
    ('ct.thrivealumni.agent.advisory-research','ThriveAlumni Advisory Research Synthesizer','researcher','A1','D1','monthly','fluid','thrivealumni'),
    ('ct.thrivealumni.agent.judicial-evidence','ThriveAlumni Judicial Evidence and Investigation Auditor','dispute','A1','D2','monthly','rigid','thrivealumni'),
    ('ct.thrivealumni.agent.nominations-integrity','ThriveAlumni Nominations and Elections Integrity Agent','verifier','A1','D1','monthly','rigid','thrivealumni'),
    ('ct.thrivealumni.agent.compensation-honorarium','ThriveAlumni Compensation and Honorarium Analyst','reviewer','A1','D1','monthly','rigid','thrivealumni'),
    ('ct.thrivealumni.agent.member-ethics','ThriveAlumni Member Engagement and Ethics Agent','reviewer','A1','D1','monthly','hybrid','thrivealumni'),
    ('ct.thrivealumni.agent.innovation-growth','ThriveAlumni Innovation and Growth Agent','planner','A2','D1','weekly','hybrid','thrivealumni'),
    ('ct.thrivealumni.agent.partnerships-external-relations','ThriveAlumni Partnerships Ambassadors and External Relations Agent','researcher','A1','D1','weekly','hybrid','thrivealumni'),
    ('ct.thrivealumni.agent.infrastructure-security-risk','ThriveAlumni Infrastructure Security and Risk Agent','security','A2','D2','hourly','rigid','thrivealumni'),
    ('ct.thrivealumni.agent.deia-cie','ThriveAlumni DEIA and CIE Alignment Reviewer','reviewer','A1','D1','monthly','hybrid','thrivealumni'),
    ('ct.thrivealumni.agent.education-credentialing','ThriveAlumni Education Credentialing and Curriculum Agent','builder','A2','D1','monthly','hybrid','thrivealumni'),
    ('ct.thrivealumni.agent.legacy-faith-culture','ThriveAlumni Legacy Faith and Cultural Heritage Steward','continuity','A1','D1','quarterly','hybrid','thrivealumni')
)
insert into chlom_runtime.agent_templates (
  agent_id, parent_agent_id, canonical_name, agent_class, autonomy_class, authority_ceiling,
  lifecycle_state, module_scope, tool_scope, schedule_profile, vote_eligible,
  self_healing_enabled, no_self_approval, heartbeat_ttl_seconds, metadata
)
select
  agent_id,
  'ct.chlom.agent.orchestrator',
  canonical_name,
  agent_class,
  autonomy_class,
  authority_ceiling,
  'specified',
  case
    when family in ('integrity','security','assurance') then array['ct.module.integrity-mesh']
    when family in ('knowledge','framework_factory') then array['ct.module.framework-foundry']
    when family in ('pricing','growth') then array['ct.module.market-growth']
    else array['ct.module.thrivealumni-support']
  end,
  jsonb_build_object(
    'read', true,
    'propose', true,
    'append_evidence', true,
    'write', 'approval_receipt_only',
    'delete', false,
    'merge', false,
    'deploy', false,
    'publish', false,
    'live_finance', false,
    'credential_export', false
  ),
  schedule_profile,
  false,
  false,
  true,
  case when schedule_profile='hourly' then 3900 when schedule_profile='daily' then 93600 else 604800 end,
  jsonb_build_object(
    'suite_id','ct.agent-suite.master.v1',
    'operating_mode',operating_mode,
    'family',family,
    'nonsovereign_subagent',true,
    'quorum_eligible',false,
    'special_privileges_state','deny_by_default',
    'manifest_ref','governance/agent-suite-v1/agent-registry.json'
  )
from seed
on conflict (agent_id) do nothing;

insert into chlom_runtime.agent_privilege_profiles (
  profile_id, suite_id, agent_id, operating_mode, authority_ceiling,
  allowed_capabilities, forbidden_capabilities, privilege_state, expires_at,
  manifest_ref, source_ids, metadata
)
select
  agent_id || ':privilege:v1',
  'ct.agent-suite.master.v1',
  agent_id,
  metadata ->> 'operating_mode',
  authority_ceiling,
  case metadata ->> 'family'
    when 'integrity' then array['read_scoped_sources','verify_integrity','append_evidence','draft_patch']
    when 'security' then array['read_scoped_sources','scan_versions','classify_threat','draft_patch','draft_rollback']
    when 'assurance' then array['read_agent_evidence','audit_controls','issue_nonbinding_finding','request_pause']
    when 'framework_factory' then array['read_reconciled_sources','compile_candidate','run_tests','submit_for_review']
    when 'knowledge' then array['read_reconciled_sources','extract_with_provenance','propose_links','draft_additive_patch']
    when 'pricing' then array['read_approved_sources','calculate_scenarios','draft_candidate','verify_candidate']
    when 'growth' then array['read_approved_sources','draft_brief','model_attribution','route_candidate']
    else array['read_public_and_approved_sources','draft_support_packet','flag_conflict','route_for_human_review']
  end,
  array['delete','self_approve','vote','count_quorum','appoint','remove_person','sanction','sign','spend','merge','deploy','publish','rotate_credentials','export_credentials','activate_checkout'],
  'test',
  now() + interval '90 days',
  'governance/agent-suite-v1/agent-registry.json',
  array['ADR-006','ADR-007','ADR-008','ADR-015','CHLOM-MCP-CONTRACT-1.0'],
  jsonb_build_object('inheritance_allowed',false,'independent_recertification_required',true)
from chlom_runtime.agent_templates
where metadata ->> 'suite_id' = 'ct.agent-suite.master.v1'
on conflict (profile_id) do nothing;

insert into chlom_runtime.agent_health (agent_id, health_state, current_task, resource_state)
select agent_id, 'pending', 'registered_no_runtime', '{"heartbeat_claimed":false,"activation_state":"controlled_test"}'::jsonb
from chlom_runtime.agent_templates
where metadata ->> 'suite_id' = 'ct.agent-suite.master.v1'
on conflict (agent_id) do nothing;

insert into chlom_identity.agent_identity_records (
  repo_id, agent_id, framework_id, repo_full_name, heartbeat_ttl_seconds, source_ref, evidence
)
select
  'ct.repo.crownthrive-support',
  agent_id,
  'ct.framework.chlom',
  'crownthrive1/CrownThrive-Support',
  heartbeat_ttl_seconds,
  'ct.agent-suite.master.v1',
  '{"did_state":"candidate","vote_eligible":false,"fingerprint_visibility":"private","heartbeat_state":"registered_no_runtime"}'::jsonb
from chlom_runtime.agent_templates
where metadata ->> 'suite_id' = 'ct.agent-suite.master.v1'
on conflict (repo_id, agent_id) do nothing;

do $$
declare
  row_data record;
begin
  for row_data in
    select agent_id from chlom_runtime.agent_templates
    where metadata ->> 'suite_id'='ct.agent-suite.master.v1'
  loop
    perform chlom_identity.ensure_agent_did_binding('ct.repo.crownthrive-support', row_data.agent_id);
  end loop;
end;
$$;

insert into chlom_runtime.agent_skill_packages (
  skill_id, suite_id, agent_id, install_name, semantic_version, generation_support,
  manifest_ref, mcp_state, commercial_state, checkout_enabled, entitlement_active, metadata
)
select
  'ct.skill.agent.' || split_part(agent_id, '.', 4) || '.v1',
  'ct.agent-suite.master.v1',
  agent_id,
  'crownthrive-agent-' || split_part(agent_id, '.', 4),
  '1.0.0',
  array['current','successor'],
  'developers/manifests/agent-skill-catalog.v1.json',
  'disabled',
  'hold',
  false,
  false,
  jsonb_build_object('per_agent_candidate',true,'independent_verification_required',true,'human_release_receipt_required',true)
from chlom_runtime.agent_templates
where metadata ->> 'suite_id' = 'ct.agent-suite.master.v1'
on conflict (skill_id) do nothing;

insert into chlom_runtime.agent_schedule_definitions (
  schedule_id, suite_id, canonical_name, timezone, ical, timing_mode, skill_name,
  agent_ids, execution_state, source_ref, metadata
)
values
  ('ct.schedule.integrity-mesh.hourly','ct.agent-suite.master.v1','CHLOM Integrity Mesh','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260821T055200\nRRULE:FREQ=HOURLY\nEND:VEVENT','condition_watch','$crownthrive-integrity-guardians',array['ct.chlom.agent.archive-integrity','ct.chlom.agent.supply-chain-integrity','ct.chlom.agent.agent-auditor','ct.thrivealumni.agent.infrastructure-security-risk'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{"github_dispatch_minute":52}'::jsonb),
  ('ct.schedule.version-threat.daily','ct.agent-suite.master.v1','Version Threat Review','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260822T060000\nRRULE:FREQ=DAILY\nEND:VEVENT','flexible_schedule','$crownthrive-integrity-guardians',array['ct.chlom.agent.version-threat-upgrader','ct.chlom.agent.supply-chain-integrity','ct.chlom.agent.agent-auditor'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb),
  ('ct.schedule.link-knowledge.daily','ct.agent-suite.master.v1','Knowledge Link Review','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260822T070000\nRRULE:FREQ=DAILY\nEND:VEVENT','flexible_schedule','$crownthrive-framework-foundry',array['ct.chlom.agent.linkage-curator','ct.chlom.agent.knowledge-extractor','ct.chlom.agent.docs'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb),
  ('ct.schedule.framework-factory.weekly','ct.agent-suite.master.v1','Framework Factory Review','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260824T090000\nRRULE:FREQ=WEEKLY;BYDAY=MO\nEND:VEVENT','flexible_schedule','$crownthrive-framework-foundry',array['ct.chlom.agent.framework-architect','ct.chlom.agent.framework-compiler','ct.chlom.agent.framework-verifier','ct.thrivealumni.agent.innovation-growth'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb),
  ('ct.schedule.growth.weekly','ct.agent-suite.master.v1','Growth Integrity Brief','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260825T090000\nRRULE:FREQ=WEEKLY;BYDAY=TU\nEND:VEVENT','flexible_schedule','$crownthrive-market-growth',array['ct.chlom.agent.marketing-intelligence','ct.chlom.agent.sales-enablement','ct.thrivealumni.agent.partnerships-external-relations','ct.thrivealumni.agent.deia-cie'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb),
  ('ct.schedule.pricing.monthly','ct.agent-suite.master.v1','Pricing Compensation Review','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260901T090000\nRRULE:FREQ=MONTHLY;BYMONTHDAY=1\nEND:VEVENT','flexible_schedule','$crownthrive-market-growth',array['ct.chlom.agent.price-intelligence','ct.chlom.agent.price-certifier','ct.thrivealumni.agent.compensation-honorarium','ct.chlom.agent.finance-tax'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb),
  ('ct.schedule.thrivealumni.monthly','ct.agent-suite.master.v1','ThriveAlumni Governance Pack','America/New_York',E'BEGIN:VEVENT\nDTSTART:20260902T090000\nRRULE:FREQ=MONTHLY;BYMONTHDAY=2\nEND:VEVENT','flexible_schedule','$crownthrive-thrivealumni-governance',array['ct.thrivealumni.agent.board-secretariat','ct.thrivealumni.agent.executive-ops','ct.thrivealumni.agent.advisory-research','ct.thrivealumni.agent.judicial-evidence','ct.thrivealumni.agent.nominations-integrity','ct.thrivealumni.agent.member-ethics','ct.thrivealumni.agent.education-credentialing'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb),
  ('ct.schedule.succession.quarterly','ct.agent-suite.master.v1','Succession Authority Review','America/New_York',E'BEGIN:VEVENT\nDTSTART:20261001T090000\nRRULE:FREQ=MONTHLY;INTERVAL=3;BYMONTHDAY=1\nEND:VEVENT','flexible_schedule','$crownthrive-thrivealumni-governance',array['ct.thrivealumni.agent.legacy-faith-culture','ct.thrivealumni.agent.board-secretariat','ct.chlom.agent.continuity','ct.chlom.agent.agent-auditor'],'registered_external_pending','governance/agent-suite-v1/schedule-registry.json','{}'::jsonb)
on conflict (schedule_id) do nothing;

insert into chlom_runtime.committee_support_registry (
  committee_id, suite_id, canonical_name, source_url, support_agent_ids,
  support_state, drift_state, authority_boundary, metadata
)
values
  ('ta.board','ct.agent-suite.master.v1','Board Members','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.board-secretariat','ct.chlom.agent.agent-auditor'],'specified','NEED_TO_DO','support_only_nonvoting','{"roster_not_publicly_verified":true}'::jsonb),
  ('ta.candidates','ct.agent-suite.master.v1','Candidates','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.nominations-integrity','ct.chlom.agent.agent-auditor'],'specified','NEED_TO_DO','support_only_nonvoting','{}'::jsonb),
  ('ta.executive','ct.agent-suite.master.v1','Executive','https://www.thrivealumni.com/page/terms_condition',array['ct.thrivealumni.agent.executive-ops','ct.thrivealumni.agent.board-secretariat'],'specified','NEED_TO_DO','support_only_nonvoting','{}'::jsonb),
  ('ta.advisory','ct.agent-suite.master.v1','Advisory','https://www.thrivealumni.com/page/terms_condition',array['ct.thrivealumni.agent.advisory-research'],'specified','NEED_TO_DO','support_only_nonvoting','{}'::jsonb),
  ('ta.judicial','ct.agent-suite.master.v1','Judicial Oversight and Special Investigations','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.judicial-evidence','ct.chlom.agent.agent-auditor'],'specified','NEED_TO_DO','support_only_no_sanctions','{}'::jsonb),
  ('ta.nominations','ct.agent-suite.master.v1','Nominations and Elections','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.nominations-integrity','ct.chlom.agent.agent-auditor'],'specified','NEED_TO_DO','support_only_nonvoting','{}'::jsonb),
  ('ta.compensation','ct.agent-suite.master.v1','Compensation and Honorarium','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.compensation-honorarium','ct.chlom.agent.price-intelligence','ct.chlom.agent.price-certifier'],'specified','NEED_TO_DO','recommendation_only_no_payment','{}'::jsonb),
  ('ta.member-ethics','ct.agent-suite.master.v1','Member Engagement and Ethics','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.member-ethics','ct.thrivealumni.agent.judicial-evidence'],'specified','NEED_TO_DO','support_only_no_sanctions','{}'::jsonb),
  ('ta.innovation-growth','ct.agent-suite.master.v1','Innovation and Growth','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.innovation-growth','ct.chlom.agent.framework-architect','ct.chlom.agent.framework-verifier'],'specified','NEED_TO_DO','candidate_only_no_activation','{}'::jsonb),
  ('ta.partnerships','ct.agent-suite.master.v1','Strategic Partnerships and External Relations','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.partnerships-external-relations','ct.chlom.agent.marketing-intelligence','ct.chlom.agent.sales-enablement'],'specified','NEED_TO_DO','draft_only_no_binding_outreach','{}'::jsonb),
  ('ta.infrastructure-risk','ct.agent-suite.master.v1','Infrastructure Security and Risk','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.infrastructure-security-risk','ct.chlom.agent.supply-chain-integrity','ct.chlom.agent.version-threat-upgrader'],'specified','NEED_TO_DO','audit_and_patch_proposal_only','{}'::jsonb),
  ('ta.deia','ct.agent-suite.master.v1','DEIA','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.deia-cie','ct.chlom.agent.accessibility-consumer','ct.chlom.agent.cultural-governance'],'specified','NEED_TO_DO','review_only_no_sensitive_trait_inference','{"policy_list_drift":true}'::jsonb),
  ('ta.education','ct.agent-suite.master.v1','Education Credentialing and Curriculum','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.education-credentialing','ct.chlom.agent.identity'],'specified','NEED_TO_DO','candidate_only_no_credential_issuance','{}'::jsonb),
  ('ta.legacy','ct.agent-suite.master.v1','Legacy Faith and Cultural Heritage','https://www.thrivealumni.com/',array['ct.thrivealumni.agent.legacy-faith-culture','ct.chlom.agent.continuity'],'specified','NEED_TO_DO','stewardship_support_no_doctrinal_authority','{}'::jsonb)
on conflict (committee_id) do nothing;

insert into chlom_runtime.linkage_candidates (
  edge_id, suite_id, source_ref, target_ref, relation_type, retroactive,
  edge_state, proposed_by_agent_id, verified_by_agent_id, metadata
)
values
  ('ct.link.agent-suite-to-framework-factory.001','ct.agent-suite.master.v1','automation/agent-capability-master-suite.mdx','automation/framework-factory.mdx','extends_with_capability_pack',true,'candidate','ct.chlom.agent.linkage-curator','ct.chlom.agent.framework-verifier','{"delete_count":0}'::jsonb),
  ('ct.link.thrivealumni-to-agent-suite.001','ct.agent-suite.master.v1','governance/thrivealumni-governance-lineage.mdx','automation/agent-capability-master-suite.mdx','supported_by_nonvoting_agents',true,'candidate','ct.chlom.agent.linkage-curator','ct.chlom.agent.agent-auditor','{"delete_count":0}'::jsonb)
on conflict (edge_id) do nothing;

insert into chlom_runtime.framework_compilation_runs (
  run_id, suite_id, candidate_id, candidate_type, builder_agent_id, verifier_agent_id,
  input_sha256, output_sha256, run_state, test_state, parent_certification_state,
  framework_count_delta, activation_allowed, evidence
)
values (
  'ct.framework-compile.thrivealumni-support.v1',
  'ct.agent-suite.master.v1',
  'ct.framework-candidate.thrivealumni-committee-support.v1',
  'capability_pack',
  'ct.chlom.agent.framework-compiler',
  'ct.chlom.agent.framework-verifier',
  '4fe06fea8e7c753e43a591658826b72f3ba6a48e02a5a076140131b4af836fd7',
  '85b2f2834f722d8fbadd59fd68fcb66f06beefce433c92fdbf709437806546bb',
  'compiled_test_hold',
  'pass',
  'pending',
  0,
  false,
  '{"not_a_ninth_framework":true,"compiler_ref":"scripts/framework_compiler.py"}'::jsonb
)
on conflict (run_id) do nothing;

insert into chlom_runtime.pricing_policy_versions (
  pricing_policy_id, suite_id, semantic_version, policy_state, currency,
  minimum_credit_transaction, top_up_candidates, forbidden_features,
  checkout_enabled, stripe_objects_created, source_ref
)
values (
  'ct.pricing.credits-baseline.v1',
  'ct.agent-suite.master.v1',
  '1.0.0',
  'governed_hold',
  'USD',
  400,
  '[{"usd_cents":1000,"credits":1000},{"usd_cents":2500,"credits":2600},{"usd_cents":5000,"credits":5500},{"usd_cents":10000,"credits":11500},{"usd_cents":25000,"credits":30000}]'::jsonb,
  array['free_offering','subscription','auto_reload','credit_expiration','service_fee','white_label'],
  false,
  false,
  'developers/manifests/pricing-policy-candidates.v1.json'
)
on conflict (pricing_policy_id) do nothing;

insert into chlom_runtime.integrity_evidence_ledger (
  evidence_id, suite_id, evidence_class, subject_ref, evidence_state,
  content_sha256, source_refs, payload, created_by_agent_id, verified_by_agent_id
)
values (
  'ct.evidence.source-generation-audit.2026-08-21.v1',
  'ct.agent-suite.master.v1',
  'source_audit',
  'project_sources',
  'hold',
  '3d02fc9f23a5d991c871c98f773f46e15163c74f2da308977c740bd69aff101f',
  array['project_sources/11-CHLOM_Mintlify_Knowledge_Base_v1.0.zip','project_sources/15-SHA256SUMS','project_sources/16-validation-report.json'],
  '{"v1_records":795,"v1_unique_titles":795,"v2_claimed_records":794,"v2_claimed_unique_titles":793,"disposition":"quarantine_detached_v2_no_pass"}'::jsonb,
  'ct.chlom.agent.archive-integrity',
  'ct.chlom.agent.agent-auditor'
)
on conflict (evidence_id) do nothing;

insert into chlom_runtime.backup_manifests (
  backup_class, source_system, destination_system, destination_ref,
  encryption_profile, secret_reference, backup_state, contains_secrets, metadata
)
select
  'agent_suite_release_candidate',
  'controlled_workspace',
  destination_system,
  destination_ref,
  'provider_managed_plus_manifest_hmac',
  'vault://ct_agent_suite_manifest_hmac_v1',
  'planned',
  false,
  jsonb_build_object('suite_id','ct.agent-suite.master.v1','dual_custody_required',true,'restore_test_required',true)
from (values
  ('google_drive','folder:1FKmR4rHNvxG7Inof37mD1mTK06O-T-yV'),
  ('supabase_storage','bucket:chlom-private-recovery')
) as destinations(destination_system,destination_ref)
where not exists (
  select 1 from chlom_runtime.backup_manifests existing
  where existing.metadata ->> 'suite_id'='ct.agent-suite.master.v1'
    and existing.destination_system=destinations.destination_system
);

create index if not exists idx_agent_privilege_profiles_expiry
  on chlom_runtime.agent_privilege_profiles (privilege_state, expires_at);
create index if not exists idx_agent_schedule_definitions_state
  on chlom_runtime.agent_schedule_definitions (execution_state, schedule_id);
create index if not exists idx_integrity_evidence_subject
  on chlom_runtime.integrity_evidence_ledger (subject_ref, created_at desc);
create index if not exists idx_linkage_candidates_state
  on chlom_runtime.linkage_candidates (edge_state, source_ref);
create index if not exists idx_framework_compilation_state
  on chlom_runtime.framework_compilation_runs (run_state, parent_certification_state);

commit;
