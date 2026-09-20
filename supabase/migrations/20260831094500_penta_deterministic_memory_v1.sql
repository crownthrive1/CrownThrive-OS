-- CrownThrive Penta deterministic memory fabric v1
-- Effective: 2026-08-31
-- Authority invariant: durable memory and deterministic replay never create
-- credentials, provider permission, certification, financial authority, D3
-- authority, release authority, or permission to bypass CHLOM/DAIL/human/
-- provider/independent-certifier gates.

begin;

create schema if not exists penta_runtime;

comment on schema penta_runtime is
  'CrownThrive server-only Penta runtime state. Memory is durable evidence-backed state, never authority.';

create or replace function penta_runtime.penta_memory_classification_rank_v1(p_classification text)
returns integer
language sql
immutable
strict
set search_path = pg_catalog
as $$
  select case lower(btrim(p_classification))
    when 'public' then 0
    when 'internal' then 1
    when 'confidential' then 2
    when 'restricted' then 3
    else 99
  end;
$$;

create or replace function penta_runtime.penta_memory_namespace_key_v1(p_identity_key text)
returns text
language plpgsql
immutable
strict
set search_path = pg_catalog
as $$
declare
  v_identity text := lower(btrim(p_identity_key));
begin
  if v_identity !~ '^[a-z0-9]+([._-][a-z0-9]+)*$' then
    raise exception 'invalid Penta identity key for memory namespace: %', p_identity_key;
  end if;
  return 'ct.memory.' || v_identity || case when v_identity ~ '\.v[0-9]+$' then '' else '.v1' end;
end;
$$;

create or replace function penta_runtime.penta_memory_canonical_family_key_v1(p_family_key text)
returns text
language sql
immutable
strict
set search_path = pg_catalog
as $$
  select case upper(btrim(p_family_key))
    when 'KNOWLEDGE_DATA' then 'KNOWLEDGE_SEMANTICS_DATA'
    when 'ROUTING_INTEROP' then 'ROUTING_INTEROPERABILITY'
    else upper(btrim(p_family_key))
  end;
$$;

create or replace function penta_runtime.penta_memory_profile_v1(
  p_identity_key text,
  p_family_key text,
  p_maturity text
)
returns jsonb
language sql
immutable
strict
set search_path = pg_catalog
as $$
  select case
    when lower(p_identity_key) = 'penta.brain' then
      jsonb_build_object(
        'profile', 'brain-v1',
        'hard_quota_bytes', 1073741824,
        'working_set_bytes', 268435456,
        'retention_days', 2555,
        'classification_ceiling', 'restricted',
        'write_enabled', lower(p_maturity) in ('implemented','production'),
        'memory_state', case when lower(p_maturity) in ('implemented','production') then 'ACTIVE_FAIL_CLOSED' else 'COLD_RESERVED' end,
        'semantic_determinism', 'bounded-semantic-v1',
        'model_dependency', 'optional_replaceable',
        'model_version_required', true,
        'degraded_without_model', true,
        'brain_mesh_role', 'anchor'
      )
    when lower(p_maturity) not in ('implemented','production') then
      jsonb_build_object(
        'profile', 'cold-reserved-v1',
        'hard_quota_bytes', 8388608,
        'working_set_bytes', 2097152,
        'retention_days', 90,
        'classification_ceiling', 'internal',
        'write_enabled', false,
        'memory_state', 'COLD_RESERVED',
        'semantic_determinism', case when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','INTELLIGENCE_RESEARCH','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE') then 'bounded-semantic-v1' else 'strict-v1' end,
        'model_dependency', case when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','INTELLIGENCE_RESEARCH','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE') then 'optional_replaceable' else 'none' end,
        'model_version_required', penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','INTELLIGENCE_RESEARCH','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE'),
        'degraded_without_model', penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','INTELLIGENCE_RESEARCH','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE'),
        'brain_mesh_role', case penta_runtime.penta_memory_canonical_family_key_v1(p_family_key)
          when 'OBSERVABILITY_ORGANIC' then 'family_observation'
          when 'KNOWLEDGE_SEMANTICS_DATA' then 'verified_context_read'
          when 'SECURITY_TRUST' then 'policy_and_classification_guard'
          when 'ROUTING_INTEROPERABILITY' then 'governed_addressability'
          when 'RESILIENCE_CONTINUITY' then 'checkpoint_replay_recovery'
          when 'INTELLIGENCE_RESEARCH' then 'bounded_analysis'
          when 'AUTOMATION_AGENTIC' then 'bounded_orchestration'
          when 'SYSTEM_ARCHITECTURE' then 'topology_and_identity'
          when 'BUILD_RELEASE' then 'independent_verification_and_release_evidence'
          else null
        end
      )
    when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) = 'KNOWLEDGE_SEMANTICS_DATA' then
      jsonb_build_object('profile','knowledge-v1','hard_quota_bytes',268435456,'working_set_bytes',67108864,'retention_days',2555,'classification_ceiling','restricted','write_enabled',true,'memory_state','ACTIVE_FAIL_CLOSED','semantic_determinism','strict-v1','model_dependency','none','model_version_required',false,'degraded_without_model',false,'brain_mesh_role','verified_context_read')
    when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) = 'INTELLIGENCE_RESEARCH' then
      jsonb_build_object('profile','intelligence-v1','hard_quota_bytes',268435456,'working_set_bytes',67108864,'retention_days',1095,'classification_ceiling','confidential','write_enabled',true,'memory_state','ACTIVE_FAIL_CLOSED','semantic_determinism','bounded-semantic-v1','model_dependency','optional_replaceable','model_version_required',true,'degraded_without_model',true,'brain_mesh_role','bounded_analysis')
    when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) = 'OBSERVABILITY_ORGANIC' then
      jsonb_build_object('profile','observability-v1','hard_quota_bytes',134217728,'working_set_bytes',33554432,'retention_days',730,'classification_ceiling','confidential','write_enabled',true,'memory_state','ACTIVE_FAIL_CLOSED','semantic_determinism','strict-v1','model_dependency','none','model_version_required',false,'degraded_without_model',false,'brain_mesh_role','family_observation')
    when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('RESILIENCE_CONTINUITY','IMMUNE_SYSTEM','SURGICAL_CARE') then
      jsonb_build_object('profile','continuity-v1','hard_quota_bytes',134217728,'working_set_bytes',33554432,'retention_days',2555,'classification_ceiling','confidential','write_enabled',true,'memory_state','ACTIVE_FAIL_CLOSED','semantic_determinism','strict-v1','model_dependency','none','model_version_required',false,'degraded_without_model',false,'brain_mesh_role',case when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key)='RESILIENCE_CONTINUITY' then 'checkpoint_replay_recovery' else null end)
    when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('SECURITY_TRUST','GOVERNANCE_LEGAL') then
      jsonb_build_object('profile','security-v1','hard_quota_bytes',67108864,'working_set_bytes',16777216,'retention_days',2555,'classification_ceiling','restricted','write_enabled',true,'memory_state','ACTIVE_FAIL_CLOSED','semantic_determinism','strict-v1','model_dependency','none','model_version_required',false,'degraded_without_model',false,'brain_mesh_role',case when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key)='SECURITY_TRUST' then 'policy_and_classification_guard' else null end)
    else
      jsonb_build_object(
        'profile', 'standard-v1',
        'hard_quota_bytes', 67108864,
        'working_set_bytes', 16777216,
        'retention_days', 365,
        'classification_ceiling', 'confidential',
        'write_enabled', true,
        'memory_state', 'ACTIVE_FAIL_CLOSED',
        'semantic_determinism', case when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE') then 'bounded-semantic-v1' else 'strict-v1' end,
        'model_dependency', case when penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE') then 'optional_replaceable' else 'none' end,
        'model_version_required', penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE'),
        'degraded_without_model', penta_runtime.penta_memory_canonical_family_key_v1(p_family_key) in ('AUTOMATION_AGENTIC','COMMUNICATIONS_SERVICE','MEDIA_CREATIVE','WORKFORCE_PEOPLE'),
        'brain_mesh_role', case penta_runtime.penta_memory_canonical_family_key_v1(p_family_key)
          when 'ROUTING_INTEROPERABILITY' then 'governed_addressability'
          when 'AUTOMATION_AGENTIC' then 'bounded_orchestration'
          when 'SYSTEM_ARCHITECTURE' then 'topology_and_identity'
          when 'BUILD_RELEASE' then 'independent_verification_and_release_evidence'
          else null
        end
      )
  end;
$$;

create table if not exists penta_runtime.penta_memory_namespaces_v1 (
  identity_key text primary key references integration_control.penta_identity_registry_v1(identity_key) on update cascade on delete restrict,
  namespace_key text not null unique,
  canonical_name text not null,
  family_key text not null,
  family_name text,
  identity_class text not null,
  registration_state text,
  maturity text not null,
  source_activation_state text not null,
  source_runtime_state text not null,
  memory_state text not null check (memory_state in ('ACTIVE_FAIL_CLOSED','COLD_RESERVED','RETIRED_HOLD','ROLLBACK_HOLD')),
  memory_profile text not null check (memory_profile in ('brain-v1','cold-reserved-v1','standard-v1','security-v1','continuity-v1','observability-v1','knowledge-v1','intelligence-v1')),
  hard_quota_bytes bigint not null check (hard_quota_bytes > 0),
  working_set_bytes bigint not null check (working_set_bytes > 0 and working_set_bytes <= hard_quota_bytes),
  retention_days integer not null check (retention_days > 0),
  classification_ceiling text not null check (classification_ceiling in ('public','internal','confidential','restricted')),
  write_enabled boolean not null,
  orchestration_determinism text not null default 'strict-v1' check (orchestration_determinism = 'strict-v1'),
  semantic_determinism text not null check (semantic_determinism in ('strict-v1','bounded-semantic-v1')),
  seed integer not null default 0 check (seed = 0),
  temperature numeric(4,3) not null default 0 check (temperature = 0),
  provider_version_required boolean not null default true check (provider_version_required),
  model_version_required boolean not null,
  model_dependency text not null check (model_dependency in ('none','optional_replaceable','required_replaceable')),
  degraded_without_model boolean not null,
  replaceable_model boolean not null default true check (replaceable_model),
  fail_closed boolean not null default true check (fail_closed),
  execution_eligible_by_registry boolean not null default false,
  determinism_warrant text not null,
  brain_mesh_role text,
  survival_contract jsonb not null,
  source_identity_sha256 text not null check (source_identity_sha256 ~ '^[0-9a-f]{64}$'),
  allocation_sha256 text not null check (allocation_sha256 ~ '^[0-9a-f]{64}$'),
  source_metadata jsonb not null default '{}'::jsonb,
  current boolean not null default true,
  authority_created boolean not null default false check (not authority_created),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (namespace_key ~ '^ct\.memory\.[a-z0-9]+([._-][a-z0-9]+)*\.v1$'),
  check (
    (memory_state='ACTIVE_FAIL_CLOSED' and current and write_enabled and lower(maturity) in ('implemented','production'))
    or (memory_state='COLD_RESERVED' and current and not write_enabled and lower(maturity) not in ('implemented','production'))
    or (memory_state in ('RETIRED_HOLD','ROLLBACK_HOLD') and not write_enabled)
  ),
  check (identity_key <> 'penta.brain' or (
    memory_profile='brain-v1'
    and hard_quota_bytes=1073741824
    and semantic_determinism='bounded-semantic-v1'
    and model_version_required
    and not execution_eligible_by_registry
    and ((memory_state='ACTIVE_FAIL_CLOSED' and current and write_enabled) or (memory_state='ROLLBACK_HOLD' and not write_enabled))
  ))
);

create table if not exists penta_runtime.penta_memory_records_v1 (
  memory_record_id uuid primary key,
  identity_key text not null references penta_runtime.penta_memory_namespaces_v1(identity_key) on update cascade on delete restrict,
  namespace_key text not null,
  operation text not null,
  idempotency_key text not null,
  context_id uuid references public.penta_context_records_v1(context_id) on update cascade on delete restrict,
  classification text not null check (classification in ('public','internal','confidential','restricted')),
  payload jsonb not null,
  payload_bytes bigint not null check (payload_bytes > 0),
  logical_bytes bigint not null check (logical_bytes >= payload_bytes),
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  source_sha256 text check (source_sha256 is null or source_sha256 ~ '^[0-9a-f]{64}$'),
  supersedes_record_id uuid references penta_runtime.penta_memory_records_v1(memory_record_id) on update cascade on delete restrict,
  previous_record_sha256 text check (previous_record_sha256 is null or previous_record_sha256 ~ '^[0-9a-f]{64}$'),
  record_sha256 text not null check (record_sha256 ~ '^[0-9a-f]{64}$'),
  provenance jsonb not null default '{}'::jsonb,
  expires_at timestamptz,
  authority_created boolean not null default false check (not authority_created),
  created_at timestamptz not null default now(),
  unique(identity_key, idempotency_key),
  unique(identity_key, record_sha256),
  check (operation ~ '^[a-z0-9][a-z0-9_.:-]{0,127}$'),
  check (length(idempotency_key) between 1 and 256)
);

create table if not exists penta_runtime.penta_execution_replays_v1 (
  replay_receipt_id uuid primary key,
  identity_key text not null references penta_runtime.penta_memory_namespaces_v1(identity_key) on update cascade on delete restrict,
  operation text not null,
  request_hash text not null check (request_hash ~ '^[0-9a-f]{64}$'),
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  manifest_sha256 text not null check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  database_request_sha256 text not null check (database_request_sha256 ~ '^[0-9a-f]{64}$'),
  result_sha256 text check (result_sha256 is null or result_sha256 ~ '^[0-9a-f]{64}$'),
  reference_result_sha256 text check (reference_result_sha256 is null or reference_result_sha256 ~ '^[0-9a-f]{64}$'),
  previous_hash text check (previous_hash is null or previous_hash ~ '^[0-9a-f]{64}$'),
  provider text,
  provider_version text,
  model text,
  model_version text,
  seed integer not null default 0 check (seed = 0),
  temperature numeric(4,3) not null default 0 check (temperature = 0),
  replay_state text not null check (replay_state in ('RECORDED','MATCH','MISMATCH','HOLD')),
  receipt jsonb not null default '{}'::jsonb,
  receipt_sha256 text not null check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  authority_created boolean not null default false check (not authority_created),
  created_at timestamptz not null default now(),
  unique(identity_key, request_hash, receipt_sha256),
  check (operation ~ '^[a-z0-9][a-z0-9_.:-]{0,127}$')
);

create table if not exists penta_runtime.penta_lifecycle_events_v1 (
  event_id uuid primary key,
  identity_key text not null references penta_runtime.penta_memory_namespaces_v1(identity_key) on update cascade on delete restrict,
  event_type text not null check (event_type in ('MEMORY_ALLOCATED','MEMORY_COLD_RESERVED','MEMORY_APPENDED','CONTEXT_REMEMBERED','QUOTA_HOLD','REPLAY_RECORDED','REPLAY_MATCH','REPLAY_MISMATCH','CHECKPOINT','RESTORED','RETIRED','ROLLBACK_HOLD')),
  state text not null,
  evidence jsonb not null default '{}'::jsonb,
  previous_event_sha256 text check (previous_event_sha256 is null or previous_event_sha256 ~ '^[0-9a-f]{64}$'),
  event_sha256 text not null unique check (event_sha256 ~ '^[0-9a-f]{64}$'),
  authority_created boolean not null default false check (not authority_created),
  created_at timestamptz not null default now()
);

create table if not exists penta_runtime.penta_memory_family_grants_v1 (
  subject_identity_key text not null references penta_runtime.penta_memory_namespaces_v1(identity_key) on update cascade on delete restrict,
  family_key text not null references integration_control.penta_family_runtime_v1(family_key) on update cascade on delete restrict,
  capability text not null,
  access_mode text not null default 'READ_ONLY' check (access_mode='READ_ONLY'),
  cross_family_write boolean not null default false check (not cross_family_write),
  authority_expansion boolean not null default false check (not authority_expansion),
  current boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(subject_identity_key, family_key)
);

create table if not exists penta_runtime.penta_memory_census_receipts_v1 (
  receipt_id uuid primary key,
  snapshot_sha256 text not null unique check (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  identity_count bigint not null check (identity_count >= 0),
  namespace_count bigint not null check (namespace_count >= 0),
  hot_writable_count bigint not null check (hot_writable_count >= 0),
  cold_reserved_count bigint not null check (cold_reserved_count >= 0),
  census_projection_count bigint not null check (census_projection_count >= 0),
  universal_projection_count bigint not null check (universal_projection_count >= 0),
  brain_ready boolean not null,
  supporting_family_count integer not null check (supporting_family_count >= 0),
  evidence jsonb not null,
  production_certified boolean not null default false check (not production_certified),
  authority_created boolean not null default false check (not authority_created),
  created_at timestamptz not null default now()
);

create index if not exists penta_memory_records_identity_created_idx on penta_runtime.penta_memory_records_v1(identity_key, created_at desc, memory_record_id desc);
create index if not exists penta_memory_records_context_idx on penta_runtime.penta_memory_records_v1(context_id) where context_id is not null;
create index if not exists penta_memory_records_supersedes_idx on penta_runtime.penta_memory_records_v1(supersedes_record_id) where supersedes_record_id is not null;
create index if not exists penta_execution_replays_request_idx on penta_runtime.penta_execution_replays_v1(identity_key, request_hash, created_at);
create index if not exists penta_lifecycle_events_identity_idx on penta_runtime.penta_lifecycle_events_v1(identity_key, created_at desc, event_id desc);
create index if not exists penta_memory_family_grants_family_idx on penta_runtime.penta_memory_family_grants_v1(family_key) where current;

create or replace function penta_runtime.penta_memory_touch_updated_at_v1()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create or replace function penta_runtime.penta_memory_append_only_guard_v1()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  raise exception '% is append-only; append a superseding record/event instead', tg_table_schema || '.' || tg_table_name;
end;
$$;

drop trigger if exists penta_memory_namespaces_touch_v1 on penta_runtime.penta_memory_namespaces_v1;
create trigger penta_memory_namespaces_touch_v1 before update on penta_runtime.penta_memory_namespaces_v1 for each row execute function penta_runtime.penta_memory_touch_updated_at_v1();

drop trigger if exists penta_memory_family_grants_touch_v1 on penta_runtime.penta_memory_family_grants_v1;
create trigger penta_memory_family_grants_touch_v1 before update on penta_runtime.penta_memory_family_grants_v1 for each row execute function penta_runtime.penta_memory_touch_updated_at_v1();

drop trigger if exists penta_memory_records_immutable_v1 on penta_runtime.penta_memory_records_v1;
create trigger penta_memory_records_immutable_v1 before update or delete on penta_runtime.penta_memory_records_v1 for each row execute function penta_runtime.penta_memory_append_only_guard_v1();

drop trigger if exists penta_execution_replays_immutable_v1 on penta_runtime.penta_execution_replays_v1;
create trigger penta_execution_replays_immutable_v1 before update or delete on penta_runtime.penta_execution_replays_v1 for each row execute function penta_runtime.penta_memory_append_only_guard_v1();

drop trigger if exists penta_lifecycle_events_immutable_v1 on penta_runtime.penta_lifecycle_events_v1;
create trigger penta_lifecycle_events_immutable_v1 before update or delete on penta_runtime.penta_lifecycle_events_v1 for each row execute function penta_runtime.penta_memory_append_only_guard_v1();

drop trigger if exists penta_memory_census_receipts_immutable_v1 on penta_runtime.penta_memory_census_receipts_v1;
create trigger penta_memory_census_receipts_immutable_v1 before update or delete on penta_runtime.penta_memory_census_receipts_v1 for each row execute function penta_runtime.penta_memory_append_only_guard_v1();

create or replace function penta_runtime.penta_memory_lifecycle_append_v1(
  p_identity_key text,
  p_event_type text,
  p_state text,
  p_evidence jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, extensions
as $$
declare
  v_previous text;
  v_sha text;
  v_id uuid;
begin
  if p_event_type not in ('MEMORY_ALLOCATED','MEMORY_COLD_RESERVED','MEMORY_APPENDED','CONTEXT_REMEMBERED','QUOTA_HOLD','REPLAY_RECORDED','REPLAY_MATCH','REPLAY_MISMATCH','CHECKPOINT','RESTORED','RETIRED','ROLLBACK_HOLD') then
    raise exception 'invalid lifecycle event type';
  end if;

  select event_sha256 into v_previous
  from penta_runtime.penta_lifecycle_events_v1
  where identity_key=p_identity_key
  order by created_at desc, event_id desc
  limit 1;

  v_sha := encode(extensions.digest(concat_ws(E'\x1f', p_identity_key, p_event_type, p_state, coalesce(p_evidence,'{}'::jsonb)::text, coalesce(v_previous,'')), 'sha256'), 'hex');
  v_id := extensions.uuid_generate_v5(extensions.uuid_ns_url(), 'ct.penta.memory.lifecycle:' || v_sha);

  insert into penta_runtime.penta_lifecycle_events_v1(event_id,identity_key,event_type,state,evidence,previous_event_sha256,event_sha256)
  values(v_id,p_identity_key,p_event_type,p_state,coalesce(p_evidence,'{}'::jsonb),v_previous,v_sha)
  on conflict(event_id) do nothing;

  return jsonb_build_object('event_id',v_id,'event_sha256',v_sha,'previous_event_sha256',v_previous,'authority_created',false);
end;
$$;

create or replace view penta_runtime.penta_memory_status_v1
with (security_invoker=true)
as
select
  n.identity_key,
  n.canonical_name,
  n.family_key,
  n.maturity,
  n.memory_state,
  n.memory_profile,
  n.hard_quota_bytes,
  n.working_set_bytes,
  coalesce(r.used_bytes,0)::bigint as used_bytes,
  greatest(n.hard_quota_bytes-coalesce(r.used_bytes,0),0)::bigint as remaining_bytes,
  coalesce(r.record_count,0)::bigint as record_count,
  n.write_enabled,
  n.orchestration_determinism,
  n.semantic_determinism,
  n.brain_mesh_role,
  n.allocation_sha256,
  n.current,
  n.authority_created,
  n.updated_at
from penta_runtime.penta_memory_namespaces_v1 n
left join lateral (
  select count(*)::bigint as record_count, coalesce(sum(logical_bytes),0)::bigint as used_bytes
  from penta_runtime.penta_memory_records_v1 x
  where x.identity_key=n.identity_key
) r on true;

create or replace view penta_runtime.penta_brain_memory_mesh_status_v1
with (security_invoker=true)
as
select
  g.subject_identity_key,
  b.memory_state as brain_memory_state,
  b.memory_profile as brain_memory_profile,
  b.hard_quota_bytes as brain_hard_quota_bytes,
  b.write_enabled as brain_write_enabled,
  g.family_key,
  f.canonical_name as family_name,
  f.activation_state as family_activation_state,
  f.runtime_state as family_runtime_state,
  f.certification_state as family_certification_state,
  g.capability,
  g.access_mode,
  g.cross_family_write,
  g.authority_expansion,
  g.current
from penta_runtime.penta_memory_family_grants_v1 g
join penta_runtime.penta_memory_namespaces_v1 b on b.identity_key=g.subject_identity_key
join integration_control.penta_family_runtime_v1 f on f.family_key=g.family_key
where g.subject_identity_key='penta.brain';

create or replace function penta_runtime.penta_memory_health_v1()
returns jsonb
language plpgsql
security definer
stable
set search_path = pg_catalog, penta_runtime, integration_control, pentamocracy, extensions
as $$
declare
  v_identities bigint;
  v_namespaces bigint;
  v_hot bigint;
  v_cold bigint;
  v_uncovered bigint;
  v_quota_violations bigint;
  v_brain integer;
  v_grants integer;
  v_family_holds bigint;
  v_census bigint;
  v_universal bigint;
  v_snapshot text;
  v_status text;
begin
  select count(*) into v_identities from integration_control.penta_identity_registry_v1 where current;
  select count(*), count(*) filter(where write_enabled), count(*) filter(where not write_enabled)
    into v_namespaces,v_hot,v_cold
  from penta_runtime.penta_memory_namespaces_v1 where current;
  select count(*) into v_uncovered
  from integration_control.penta_identity_registry_v1 r
  where r.current and not exists(select 1 from penta_runtime.penta_memory_namespaces_v1 n where n.identity_key=r.identity_key and n.current);
  select count(*) into v_quota_violations
  from penta_runtime.penta_memory_status_v1 where used_bytes > hard_quota_bytes;
  select count(*) into v_brain
  from penta_runtime.penta_memory_namespaces_v1
  where identity_key='penta.brain' and current and write_enabled and memory_state='ACTIVE_FAIL_CLOSED' and memory_profile='brain-v1' and not execution_eligible_by_registry;
  select count(*) into v_grants
  from penta_runtime.penta_memory_family_grants_v1 where subject_identity_key='penta.brain' and current and access_mode='READ_ONLY' and not cross_family_write and not authority_expansion;
  select count(*) into v_family_holds
  from penta_runtime.penta_memory_family_grants_v1 g
  left join integration_control.penta_family_runtime_v1 f on f.family_key=g.family_key
  where g.subject_identity_key='penta.brain' and g.current and (f.family_key is null or f.activation_state not in ('ACTIVE','ACTIVE_FAIL_CLOSED'));
  select count(*) into v_census from integration_control.penta_census_entities_v1 where entity_kind='PENTA_MEMORY_NAMESPACE' and current;
  select count(*) into v_universal from pentamocracy.universal_penta_census_v1 where source_kind='penta_memory_namespace' and lifecycle_state in ('ACTIVE_FAIL_CLOSED','COLD_RESERVED');
  select encode(extensions.digest(coalesce(string_agg(identity_key || ':' || allocation_sha256, '' order by identity_key),''), 'sha256'),'hex')
    into v_snapshot from penta_runtime.penta_memory_namespaces_v1 where current;

  v_status := case when v_identities=v_namespaces and v_uncovered=0 and v_quota_violations=0 and v_brain=1 and v_grants=9 and v_family_holds=0 and v_census=v_namespaces and v_universal=v_namespaces then 'PASS' else 'HOLD' end;

  return jsonb_build_object(
    'system_key','penta.deterministic-memory',
    'contract_version','1.0.0',
    'status',v_status,
    'current_identity_count',v_identities,
    'current_namespace_count',v_namespaces,
    'hot_writable_count',v_hot,
    'cold_reserved_count',v_cold,
    'uncovered_identity_count',v_uncovered,
    'quota_violation_count',v_quota_violations,
    'penta_brain_ready',v_brain=1,
    'penta_brain_supporting_family_count',v_grants,
    'supporting_family_hold_count',v_family_holds,
    'census_projection_count',v_census,
    'universal_census_projection_count',v_universal,
    'snapshot_sha256',v_snapshot,
    'production_certified',false,
    'independent_certification_required',true,
    'authority_created',false
  );
end;
$$;

create or replace function penta_runtime.penta_memory_reconcile_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, integration_control, pentamocracy, public, extensions
as $$
declare
  v_missing_families integer;
  v_snapshot text;
  v_identity_count bigint;
  v_namespace_count bigint;
  v_hot bigint;
  v_cold bigint;
  v_census bigint;
  v_universal bigint;
  v_brain_ready boolean;
  v_support integer;
  v_receipt uuid;
begin
  perform pg_advisory_xact_lock(pg_catalog.hashtextextended('ct.penta.deterministic-memory.v1',0));

  if exists(
    select 1 from integration_control.penta_identity_registry_v1
    where current and (maturity is null or btrim(maturity)='' or family_key is null or btrim(family_key)='' or canonical_name is null or btrim(canonical_name)='')
  ) then
    raise exception 'current Penta identity lacks maturity, family, or canonical name; deterministic memory reconciliation is fail-closed';
  end if;

  if not exists(
    select 1 from integration_control.penta_identity_registry_v1
    where identity_key='penta.brain' and current and active and lower(maturity) in ('implemented','production')
  ) then
    raise exception 'PentaBrain is not a current active implemented/production identity; deterministic memory reconciliation is fail-closed';
  end if;

  if exists(
    select 1
    from integration_control.penta_identity_registry_v1 r
    left join integration_control.penta_family_runtime_v1 f on f.family_key=r.family_key
    where r.current and lower(r.maturity) in ('implemented','production')
      and (r.family_key='PROVISIONAL_UNASSIGNED' or f.family_key is null)
  ) then
    raise exception 'hot Penta identity lacks a live canonical family; deterministic memory reconciliation is fail-closed';
  end if;

  select count(*) into v_missing_families
  from (values
    ('OBSERVABILITY_ORGANIC'),('KNOWLEDGE_DATA'),('SECURITY_TRUST'),('ROUTING_INTEROP'),('RESILIENCE_CONTINUITY'),
    ('INTELLIGENCE_RESEARCH'),('AUTOMATION_AGENTIC'),('SYSTEM_ARCHITECTURE'),('BUILD_RELEASE')
  ) required(family_key)
  left join integration_control.penta_family_runtime_v1 f on f.family_key=required.family_key
  where f.family_key is null or f.activation_state not in ('ACTIVE','ACTIVE_FAIL_CLOSED');

  if v_missing_families > 0 then
    raise exception 'PentaBrain supporting family topology is incomplete or inactive: % family rows', v_missing_families;
  end if;

  insert into penta_runtime.penta_memory_namespaces_v1(
    identity_key,namespace_key,canonical_name,family_key,family_name,identity_class,registration_state,maturity,
    source_activation_state,source_runtime_state,memory_state,memory_profile,hard_quota_bytes,working_set_bytes,
    retention_days,classification_ceiling,write_enabled,orchestration_determinism,semantic_determinism,seed,
    temperature,provider_version_required,model_version_required,model_dependency,degraded_without_model,
    replaceable_model,fail_closed,execution_eligible_by_registry,determinism_warrant,brain_mesh_role,
    survival_contract,source_identity_sha256,allocation_sha256,source_metadata,current,authority_created
  )
  select
    r.identity_key,
    penta_runtime.penta_memory_namespace_key_v1(r.identity_key),
    r.canonical_name,
    r.family_key,
    r.family_name,
    r.identity_class,
    r.registration_state,
    lower(r.maturity),
    r.activation_state,
    r.runtime_state,
    p.profile->>'memory_state',
    p.profile->>'profile',
    (p.profile->>'hard_quota_bytes')::bigint,
    (p.profile->>'working_set_bytes')::bigint,
    (p.profile->>'retention_days')::integer,
    p.profile->>'classification_ceiling',
    (p.profile->>'write_enabled')::boolean,
    'strict-v1',
    p.profile->>'semantic_determinism',
    0,
    0,
    true,
    (p.profile->>'model_version_required')::boolean,
    p.profile->>'model_dependency',
    (p.profile->>'degraded_without_model')::boolean,
    true,
    true,
    lower(coalesce(r.metadata->>'pm_execution_eligible','false'))='true',
    case when r.identity_key='penta.brain' then
      'PentaBrain coordinates bounded institutional health, learning trends, and dispositions. Identity, retrieval scope, evidence ordering, thresholds, receipts, and routing replay exactly; semantic synthesis never self-authorizes.'
    when p.profile->>'semantic_determinism'='bounded-semantic-v1' then
      'Identity, routing, authority inputs, state transitions, retries, receipts, and recovery replay exactly. Model output is provider-bounded, version-pinned, and independently verified before consequential release.'
    else
      'Identity, canonical inputs, state transitions, routing, retries, evidence, and recovery replay exactly for the same contract version.' end,
    nullif(p.profile->>'brain_mesh_role',''),
    jsonb_build_object(
      'contract_id','ct.penta.survival.v1',
      'persistent_identity',r.identity_key,
      'persistent_state',penta_runtime.penta_memory_namespace_key_v1(r.identity_key),
      'deterministic_functions',jsonb_build_array('canonical_input_hash','deterministic_request_key','hash_bound_receipt','replay_verification'),
      'queues','governed_existing_penta_queue',
      'leases','bounded_expiring_owner_scoped',
      'recovery','verified_checkpoint_then_exact_source_replay',
      'evidence','hash_bound_receipt_plus_DAIL_handoff',
      'authority_enforcement','CHLOM_provider_human_independent_certifier',
      'health_check','quota_chain_family_provider_readback',
      'model_dependency',p.profile->>'model_dependency',
      'degraded_without_model',(p.profile->>'degraded_without_model')::boolean,
      'replaceable_model',true,
      'restart_behavior','rebuild_from_verified_persistent_state'
    ),
    s.source_identity_sha256,
    encode(extensions.digest(concat_ws(E'\x1f',
      r.identity_key,r.canonical_name,r.family_key,lower(r.maturity),p.profile->>'profile',p.profile->>'hard_quota_bytes',
      p.profile->>'working_set_bytes',p.profile->>'retention_days',p.profile->>'classification_ceiling',
      p.profile->>'write_enabled',p.profile->>'memory_state',p.profile->>'semantic_determinism',
      p.profile->>'model_dependency',p.profile->>'model_version_required',p.profile->>'degraded_without_model',
      coalesce(p.profile->>'brain_mesh_role',''),(lower(coalesce(r.metadata->>'pm_execution_eligible','false'))='true')::text,
      s.source_identity_sha256,'ct.penta.deterministic-memory.v1.0.0'
    ), 'sha256'),'hex'),
    jsonb_build_object(
      'docs_path',r.docs_path,'docs_namespace',r.docs_namespace,'source_refs',coalesce(r.source_refs,'{}'::jsonb),
      'source_registry_version',r.metadata->>'source_registry_version','authority_expansion',false
    ),
    true,
    false
  from integration_control.penta_identity_registry_v1 r
  cross join lateral (select penta_runtime.penta_memory_profile_v1(r.identity_key,r.family_key,r.maturity) as profile) p
  cross join lateral (
    select case
      when coalesce(r.source_sha256,'') ~ '^[0-9a-f]{64}$' then r.source_sha256
      else encode(extensions.digest(concat_ws(E'\x1f',r.identity_key,r.canonical_name,coalesce(r.docs_path,''),coalesce(r.docs_namespace,''),coalesce(r.source_refs,'{}'::jsonb)::text), 'sha256'),'hex')
    end as source_identity_sha256
  ) s
  where r.current
  on conflict(identity_key) do update set
    namespace_key=excluded.namespace_key,
    canonical_name=excluded.canonical_name,
    family_key=excluded.family_key,
    family_name=excluded.family_name,
    identity_class=excluded.identity_class,
    registration_state=excluded.registration_state,
    maturity=excluded.maturity,
    source_activation_state=excluded.source_activation_state,
    source_runtime_state=excluded.source_runtime_state,
    memory_state=excluded.memory_state,
    memory_profile=excluded.memory_profile,
    hard_quota_bytes=excluded.hard_quota_bytes,
    working_set_bytes=excluded.working_set_bytes,
    retention_days=excluded.retention_days,
    classification_ceiling=excluded.classification_ceiling,
    write_enabled=excluded.write_enabled,
    orchestration_determinism=excluded.orchestration_determinism,
    semantic_determinism=excluded.semantic_determinism,
    provider_version_required=excluded.provider_version_required,
    model_version_required=excluded.model_version_required,
    model_dependency=excluded.model_dependency,
    degraded_without_model=excluded.degraded_without_model,
    replaceable_model=excluded.replaceable_model,
    fail_closed=excluded.fail_closed,
    execution_eligible_by_registry=excluded.execution_eligible_by_registry,
    determinism_warrant=excluded.determinism_warrant,
    brain_mesh_role=excluded.brain_mesh_role,
    survival_contract=excluded.survival_contract,
    source_identity_sha256=excluded.source_identity_sha256,
    allocation_sha256=excluded.allocation_sha256,
    source_metadata=excluded.source_metadata,
    current=true,
    authority_created=false;

  perform penta_runtime.penta_memory_lifecycle_append_v1(
    n.identity_key,'RETIRED','RETIRED_HOLD',jsonb_build_object('namespace_key',n.namespace_key,'allocation_sha256',n.allocation_sha256,'reason','identity_not_current','authority_created',false)
  )
  from penta_runtime.penta_memory_namespaces_v1 n
  where n.current
    and not exists(select 1 from integration_control.penta_identity_registry_v1 r where r.identity_key=n.identity_key and r.current)
    and not exists(select 1 from penta_runtime.penta_lifecycle_events_v1 e where e.identity_key=n.identity_key and e.event_type='RETIRED' and e.evidence->>'allocation_sha256'=n.allocation_sha256);

  update penta_runtime.penta_memory_namespaces_v1 n
  set current=false,memory_state='RETIRED_HOLD',write_enabled=false
  where n.current and not exists(select 1 from integration_control.penta_identity_registry_v1 r where r.identity_key=n.identity_key and r.current);

  insert into penta_runtime.penta_memory_family_grants_v1(subject_identity_key,family_key,capability,metadata)
  values
    ('penta.brain','OBSERVABILITY_ORGANIC','family_observation',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','KNOWLEDGE_DATA','verified_context_read',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','SECURITY_TRUST','policy_and_classification_guard',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','ROUTING_INTEROP','governed_addressability',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','RESILIENCE_CONTINUITY','checkpoint_replay_recovery',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','INTELLIGENCE_RESEARCH','bounded_analysis',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','AUTOMATION_AGENTIC','bounded_orchestration',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','SYSTEM_ARCHITECTURE','topology_and_identity',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none')),
    ('penta.brain','BUILD_RELEASE','independent_verification_and_release_evidence',jsonb_build_object('contract','ct.penta.deterministic-memory.v1','write_scope','none'))
  on conflict(subject_identity_key,family_key) do update set capability=excluded.capability,access_mode='READ_ONLY',cross_family_write=false,authority_expansion=false,current=true,metadata=excluded.metadata || jsonb_build_object('canonical_family_key',penta_runtime.penta_memory_canonical_family_key_v1(excluded.family_key));

  update penta_runtime.penta_memory_family_grants_v1
  set current=false
  where subject_identity_key='penta.brain' and family_key not in ('OBSERVABILITY_ORGANIC','KNOWLEDGE_DATA','SECURITY_TRUST','ROUTING_INTEROP','RESILIENCE_CONTINUITY','INTELLIGENCE_RESEARCH','AUTOMATION_AGENTIC','SYSTEM_ARCHITECTURE','BUILD_RELEASE');

  update integration_control.penta_identity_registry_v1 r
  set metadata=coalesce(r.metadata,'{}'::jsonb) || jsonb_build_object(
      'deterministic_memory_bound',true,
      'memory_contract','ct.penta.deterministic-memory.v1',
      'memory_namespace',n.namespace_key,
      'memory_profile',n.memory_profile,
      'memory_write_enabled',n.write_enabled,
      'memory_allocation_sha256',n.allocation_sha256,
      'memory_authority_expansion',false
    )
  from penta_runtime.penta_memory_namespaces_v1 n
  where r.identity_key=n.identity_key and r.current and n.current;

  update integration_control.penta_family_runtime_v1 f
  set metadata=coalesce(f.metadata,'{}'::jsonb) || jsonb_build_object(
      'deterministic_memory_bound',true,
      'canonical_family_key',penta_runtime.penta_memory_canonical_family_key_v1(f.family_key),
      'memory_contract','ct.penta.deterministic-memory.v1',
      'memory_mesh_role',case f.family_key
        when 'OBSERVABILITY_ORGANIC' then 'anchor_family'
        when 'KNOWLEDGE_DATA' then 'verified_context_read'
        when 'SECURITY_TRUST' then 'policy_and_classification_guard'
        when 'ROUTING_INTEROP' then 'governed_addressability'
        when 'RESILIENCE_CONTINUITY' then 'checkpoint_replay_recovery'
        when 'INTELLIGENCE_RESEARCH' then 'bounded_analysis'
        when 'AUTOMATION_AGENTIC' then 'bounded_orchestration'
        when 'SYSTEM_ARCHITECTURE' then 'topology_and_identity'
        when 'BUILD_RELEASE' then 'independent_verification_and_release_evidence' end,
      'memory_cross_family_write',false,
      'memory_authority_expansion',false
    )
  where f.family_key in ('OBSERVABILITY_ORGANIC','KNOWLEDGE_DATA','SECURITY_TRUST','ROUTING_INTEROP','RESILIENCE_CONTINUITY','INTELLIGENCE_RESEARCH','AUTOMATION_AGENTIC','SYSTEM_ARCHITECTURE','BUILD_RELEASE');

  update public.penta_runtime_activations a
  set metadata=coalesce(a.metadata,'{}'::jsonb) || jsonb_build_object(
      'deterministic_memory_bound',true,
      'memory_namespace',penta_runtime.penta_memory_namespace_key_v1('penta.brain'),
      'memory_profile','brain-v1',
      'memory_contract','ct.penta.deterministic-memory.v1',
      'specialist_execution_eligible',false,
      'authority_created',false
    ),
    updated_at=now()
  where a.penta='penta.brain' and a.state='active';

  if not found then
    raise exception 'PentaBrain must already be active in the runtime activation ledger; memory reconciliation cannot manufacture activation';
  end if;

  insert into integration_control.penta_census_entities_v1(entity_kind,entity_key,canonical_name,source_ref,lifecycle_state,risk_class,first_seen_at,last_seen_at,current,attributes)
  select
    'PENTA_MEMORY_NAMESPACE',n.namespace_key,n.canonical_name || ' Memory Namespace',
    'penta_runtime.penta_memory_namespaces_v1:' || n.identity_key,n.memory_state,null,now(),now(),n.current,
    jsonb_build_object(
      'identity_key',n.identity_key,'family_key',n.family_key,'maturity',n.maturity,'memory_profile',n.memory_profile,
      'hard_quota_bytes',n.hard_quota_bytes,'working_set_bytes',n.working_set_bytes,'write_enabled',n.write_enabled,
      'orchestration_determinism',n.orchestration_determinism,'semantic_determinism',n.semantic_determinism,
      'brain_mesh_role',n.brain_mesh_role,'allocation_sha256',n.allocation_sha256,'survival_contract',n.survival_contract,
      'authority_created',false
    )
  from penta_runtime.penta_memory_namespaces_v1 n
  on conflict(entity_kind,entity_key) do update set canonical_name=excluded.canonical_name,source_ref=excluded.source_ref,lifecycle_state=excluded.lifecycle_state,last_seen_at=excluded.last_seen_at,current=excluded.current,attributes=excluded.attributes;

  update integration_control.penta_census_entities_v1 c
  set current=false,last_seen_at=now(),lifecycle_state='RETIRED_HOLD'
  where c.entity_kind='PENTA_MEMORY_NAMESPACE' and c.current and not exists(select 1 from penta_runtime.penta_memory_namespaces_v1 n where n.namespace_key=c.entity_key and n.current);

  insert into pentamocracy.universal_penta_census_v1(
    census_identity,canonical_name,source_kind,source_ref,lifecycle_state,constitutional_status,
    family_key,source_digest,first_accounted_at,last_accounted_at
  )
  select
    'memory:' || n.identity_key,
    n.canonical_name || ' Memory Namespace',
    'penta_memory_namespace',
    'penta_runtime.penta_memory_namespaces_v1:' || n.identity_key,
    n.memory_state,
    'NONCITIZEN_PENTA_ENTITY',
    n.family_key,
    n.allocation_sha256,
    now(),
    now()
  from penta_runtime.penta_memory_namespaces_v1 n
  on conflict(census_identity) do update set
    canonical_name=excluded.canonical_name,
    source_kind=excluded.source_kind,
    source_ref=excluded.source_ref,
    lifecycle_state=excluded.lifecycle_state,
    constitutional_status=excluded.constitutional_status,
    family_key=excluded.family_key,
    source_digest=excluded.source_digest,
    last_accounted_at=excluded.last_accounted_at;


  perform penta_runtime.penta_memory_lifecycle_append_v1(
    n.identity_key,
    case when n.write_enabled then 'MEMORY_ALLOCATED' else 'MEMORY_COLD_RESERVED' end,
    n.memory_state,
    jsonb_build_object('namespace_key',n.namespace_key,'memory_profile',n.memory_profile,'hard_quota_bytes',n.hard_quota_bytes,'working_set_bytes',n.working_set_bytes,'allocation_sha256',n.allocation_sha256,'authority_created',false)
  )
  from penta_runtime.penta_memory_namespaces_v1 n
  where not exists(
    select 1 from penta_runtime.penta_lifecycle_events_v1 e
    where e.identity_key=n.identity_key
      and e.event_type=case when n.write_enabled then 'MEMORY_ALLOCATED' else 'MEMORY_COLD_RESERVED' end
      and e.evidence->>'allocation_sha256'=n.allocation_sha256
  );


  select encode(extensions.digest(coalesce(string_agg(identity_key || ':' || allocation_sha256, '' order by identity_key),''),'sha256'),'hex') into v_snapshot
  from penta_runtime.penta_memory_namespaces_v1 where current;
  select count(*) into v_identity_count from integration_control.penta_identity_registry_v1 where current;
  select count(*),count(*) filter(where write_enabled),count(*) filter(where not write_enabled) into v_namespace_count,v_hot,v_cold from penta_runtime.penta_memory_namespaces_v1 where current;
  select count(*) into v_census from integration_control.penta_census_entities_v1 where entity_kind='PENTA_MEMORY_NAMESPACE' and current;
  select count(*) into v_universal from pentamocracy.universal_penta_census_v1 where source_kind='penta_memory_namespace' and lifecycle_state in ('ACTIVE_FAIL_CLOSED','COLD_RESERVED');
  select exists(select 1 from penta_runtime.penta_memory_namespaces_v1 where identity_key='penta.brain' and current and write_enabled and memory_profile='brain-v1' and memory_state='ACTIVE_FAIL_CLOSED' and not execution_eligible_by_registry) into v_brain_ready;
  select count(*) into v_support from penta_runtime.penta_memory_family_grants_v1 where subject_identity_key='penta.brain' and current;
  v_receipt := extensions.uuid_generate_v5(extensions.uuid_ns_url(),'ct.penta.memory.census:' || v_snapshot);

  insert into penta_runtime.penta_memory_census_receipts_v1(
    receipt_id,snapshot_sha256,identity_count,namespace_count,hot_writable_count,cold_reserved_count,
    census_projection_count,universal_projection_count,brain_ready,supporting_family_count,evidence
  ) values(
    v_receipt,v_snapshot,v_identity_count,v_namespace_count,v_hot,v_cold,v_census,v_universal,v_brain_ready,v_support,
    jsonb_build_object('contract','ct.penta.deterministic-memory.v1','identity_source','integration_control.penta_identity_registry_v1','census_source','integration_control.penta_census_entities_v1','universal_source','pentamocracy.universal_penta_census_v1','authority_created',false)
  ) on conflict(receipt_id) do nothing;

  return penta_runtime.penta_memory_health_v1();
end;
$$;

create or replace function penta_runtime.penta_memory_append_core_v1(
  p_actor_identity_key text,
  p_target_identity_key text,
  p_operation text,
  p_idempotency_key text,
  p_payload jsonb,
  p_classification text,
  p_context_id uuid,
  p_source_sha256 text,
  p_provenance jsonb,
  p_supersedes_record_id uuid,
  p_logical_bytes bigint default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, public, extensions
as $$
declare
  v_namespace penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_existing penta_runtime.penta_memory_records_v1%rowtype;
  v_payload_bytes bigint;
  v_logical_bytes bigint;
  v_used bigint;
  v_payload_sha text;
  v_provenance jsonb;
  v_previous text;
  v_record_sha text;
  v_record_id uuid;
  v_lifecycle jsonb;
begin
  if lower(btrim(p_actor_identity_key)) <> lower(btrim(p_target_identity_key)) then
    raise exception 'cross-identity memory write denied';
  end if;
  if p_operation is null or p_operation !~ '^[a-z0-9][a-z0-9_.:-]{0,127}$' then raise exception 'invalid operation'; end if;
  if p_idempotency_key is null or length(p_idempotency_key) not between 1 and 256 then raise exception 'invalid idempotency key'; end if;
  if p_payload is null then raise exception 'payload is required'; end if;
  if lower(coalesce(p_classification,'')) not in ('public','internal','confidential','restricted') then raise exception 'invalid classification'; end if;
  if p_source_sha256 is not null and p_source_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid source sha256'; end if;

  perform pg_advisory_xact_lock(pg_catalog.hashtextextended('ct.penta.memory:' || lower(p_target_identity_key),0));

  select * into v_namespace from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_target_identity_key) and current for update;
  if not found then raise exception 'unknown or inactive Penta memory namespace'; end if;
  if not v_namespace.write_enabled or v_namespace.memory_state <> 'ACTIVE_FAIL_CLOSED' then raise exception 'Penta memory namespace is not writable'; end if;
  if penta_runtime.penta_memory_classification_rank_v1(p_classification) > penta_runtime.penta_memory_classification_rank_v1(v_namespace.classification_ceiling) then raise exception 'classification exceeds namespace ceiling'; end if;

  v_payload_bytes := octet_length(convert_to(p_payload::text,'UTF8'));
  v_logical_bytes := greatest(coalesce(p_logical_bytes,v_payload_bytes),v_payload_bytes);
  if v_logical_bytes > v_namespace.working_set_bytes then raise exception 'single memory record exceeds working-set budget'; end if;
  v_payload_sha := encode(extensions.digest(p_payload::text,'sha256'),'hex');
  v_provenance := coalesce(p_provenance,'{}'::jsonb);

  select * into v_existing from penta_runtime.penta_memory_records_v1 where identity_key=v_namespace.identity_key and idempotency_key=p_idempotency_key;
  if found then
    if v_existing.payload_sha256 <> v_payload_sha
      or v_existing.operation <> p_operation
      or v_existing.logical_bytes <> v_logical_bytes
      or v_existing.classification <> lower(p_classification)
      or v_existing.context_id is distinct from p_context_id
      or v_existing.source_sha256 is distinct from p_source_sha256
      or v_existing.supersedes_record_id is distinct from p_supersedes_record_id
      or v_existing.provenance is distinct from v_provenance then
      raise exception 'idempotency collision with different governed memory envelope';
    end if;
    return jsonb_build_object('state','IDEMPOTENT_REPLAY','memory_record_id',v_existing.memory_record_id,'record_sha256',v_existing.record_sha256,'payload_sha256',v_existing.payload_sha256,'logical_bytes',v_existing.logical_bytes,'authority_created',false);
  end if;

  if p_context_id is not null and not exists(select 1 from public.penta_context_records_v1 c where c.context_id=p_context_id and c.scope_key=v_namespace.namespace_key) then
    raise exception 'PentaContext record is absent or outside the exact memory namespace';
  end if;
  if p_supersedes_record_id is not null and not exists(select 1 from penta_runtime.penta_memory_records_v1 r where r.memory_record_id=p_supersedes_record_id and r.identity_key=v_namespace.identity_key) then
    raise exception 'superseded record is absent or belongs to another Penta';
  end if;

  select coalesce(sum(logical_bytes),0)::bigint into v_used from penta_runtime.penta_memory_records_v1 where identity_key=v_namespace.identity_key;
  if v_used + v_logical_bytes > v_namespace.hard_quota_bytes then
    v_lifecycle := penta_runtime.penta_memory_lifecycle_append_v1(v_namespace.identity_key,'QUOTA_HOLD','HOLD_QUOTA',jsonb_build_object('idempotency_key',p_idempotency_key,'used_bytes',v_used,'requested_bytes',v_logical_bytes,'hard_quota_bytes',v_namespace.hard_quota_bytes,'authority_created',false));
    return jsonb_build_object('state','HOLD_QUOTA','used_bytes',v_used,'requested_bytes',v_logical_bytes,'hard_quota_bytes',v_namespace.hard_quota_bytes,'lifecycle',v_lifecycle,'authority_created',false);
  end if;

  select record_sha256 into v_previous from penta_runtime.penta_memory_records_v1 where identity_key=v_namespace.identity_key order by created_at desc,memory_record_id desc limit 1;
  v_record_sha := encode(extensions.digest(concat_ws(E'\x1f',v_namespace.identity_key,p_operation,p_idempotency_key,lower(p_classification),v_payload_sha,encode(extensions.digest(v_provenance::text,'sha256'),'hex'),coalesce(p_context_id::text,''),coalesce(p_source_sha256,''),coalesce(p_supersedes_record_id::text,''),coalesce(v_previous,''),v_logical_bytes::text),'sha256'),'hex');
  v_record_id := extensions.uuid_generate_v5(extensions.uuid_ns_url(),v_namespace.namespace_key || ':' || v_record_sha);

  insert into penta_runtime.penta_memory_records_v1(
    memory_record_id,identity_key,namespace_key,operation,idempotency_key,context_id,classification,payload,payload_bytes,
    logical_bytes,payload_sha256,source_sha256,supersedes_record_id,previous_record_sha256,record_sha256,provenance,expires_at
  ) values(
    v_record_id,v_namespace.identity_key,v_namespace.namespace_key,p_operation,p_idempotency_key,p_context_id,lower(p_classification),p_payload,
    v_payload_bytes,v_logical_bytes,v_payload_sha,p_source_sha256,p_supersedes_record_id,v_previous,v_record_sha,v_provenance,
    now()+make_interval(days=>v_namespace.retention_days)
  );

  v_lifecycle := penta_runtime.penta_memory_lifecycle_append_v1(v_namespace.identity_key,'MEMORY_APPENDED','APPENDED',jsonb_build_object('memory_record_id',v_record_id,'record_sha256',v_record_sha,'logical_bytes',v_logical_bytes,'used_bytes_after',v_used+v_logical_bytes,'hard_quota_bytes',v_namespace.hard_quota_bytes,'authority_created',false));

  return jsonb_build_object('state','APPENDED','memory_record_id',v_record_id,'record_sha256',v_record_sha,'payload_sha256',v_payload_sha,'logical_bytes',v_logical_bytes,'used_bytes_after',v_used+v_logical_bytes,'hard_quota_bytes',v_namespace.hard_quota_bytes,'lifecycle',v_lifecycle,'authority_created',false);
end;
$$;

create or replace function penta_runtime.penta_memory_append_v1(
  p_actor_identity_key text,
  p_target_identity_key text,
  p_operation text,
  p_idempotency_key text,
  p_payload jsonb,
  p_classification text default 'internal',
  p_context_id uuid default null,
  p_source_sha256 text default null,
  p_provenance jsonb default '{}'::jsonb,
  p_supersedes_record_id uuid default null
)
returns jsonb
language sql
security definer
set search_path = pg_catalog, penta_runtime
as $$
  select penta_runtime.penta_memory_append_core_v1(
    p_actor_identity_key,p_target_identity_key,p_operation,p_idempotency_key,p_payload,p_classification,
    p_context_id,p_source_sha256,p_provenance,p_supersedes_record_id,null
  );
$$;

create or replace function penta_runtime.penta_memory_remember_v1(
  p_actor_identity_key text,
  p_target_identity_key text,
  p_idempotency_key text,
  p_source_type text,
  p_source_ref text,
  p_content text,
  p_title text default null,
  p_summary text default null,
  p_tags text[] default '{}'::text[],
  p_metadata jsonb default '{}'::jsonb,
  p_classification text default 'internal',
  p_importance numeric default 0.5,
  p_confidence numeric default 0.7,
  p_observed_at timestamptz default now(),
  p_expires_at timestamptz default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, public, extensions
as $$
declare
  v_namespace penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_context jsonb;
  v_payload jsonb;
  v_append jsonb;
  v_content_bytes bigint;
  v_source_sha text;
begin
  if lower(btrim(p_actor_identity_key)) <> lower(btrim(p_target_identity_key)) then raise exception 'cross-identity memory write denied'; end if;
  perform pg_advisory_xact_lock(pg_catalog.hashtextextended('ct.penta.memory:' || lower(p_target_identity_key),0));
  select * into v_namespace from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_target_identity_key) and current for update;
  if not found or not v_namespace.write_enabled or v_namespace.memory_state <> 'ACTIVE_FAIL_CLOSED' then raise exception 'Penta memory namespace is not writable'; end if;
  v_content_bytes := octet_length(convert_to(coalesce(p_content,''),'UTF8'));
  if v_content_bytes <= 0 or v_content_bytes > v_namespace.working_set_bytes then raise exception 'content is empty or exceeds working-set budget'; end if;
  v_source_sha := encode(extensions.digest(p_content,'sha256'),'hex');

  v_context := public.penta_context_ingest_v1(
    v_namespace.namespace_key,p_source_type,p_source_ref,p_content,p_title,p_summary,p_tags,
    coalesce(p_metadata,'{}'::jsonb) || jsonb_build_object('system_ref',v_namespace.identity_key,'memory_contract','ct.penta.deterministic-memory.v1','memory_namespace',v_namespace.namespace_key,'authority_created',false),
    p_classification,p_importance,p_confidence,p_observed_at,p_expires_at,v_namespace.identity_key
  );

  v_payload := jsonb_build_object(
    'kind','penta_context_memory','context_id',v_context->>'context_id','fingerprint_sha256',v_context->>'fingerprint_sha256',
    'title',p_title,'summary',p_summary,'tags',coalesce(to_jsonb(p_tags),'[]'::jsonb),'source_type',p_source_type,'source_ref',p_source_ref,
    'content_sha256',v_source_sha,'authority_created',false
  );

  v_append := penta_runtime.penta_memory_append_core_v1(
    v_namespace.identity_key,v_namespace.identity_key,'memory.remember',p_idempotency_key,v_payload,p_classification,
    (v_context->>'context_id')::uuid,v_source_sha,jsonb_build_object('penta_context',v_context,'authority_created',false),null,
    v_content_bytes + octet_length(convert_to(v_payload::text,'UTF8'))
  );

  if v_append->>'state'='HOLD_QUOTA' then
    raise exception 'memory quota exceeded; PentaContext write rolled back';
  end if;

  if v_append->>'state'='APPENDED' then
    perform penta_runtime.penta_memory_lifecycle_append_v1(v_namespace.identity_key,'CONTEXT_REMEMBERED','REMEMBERED',jsonb_build_object('context_id',v_context->>'context_id','memory_record_id',v_append->>'memory_record_id','fingerprint_sha256',v_context->>'fingerprint_sha256','authority_created',false));
  end if;
  return jsonb_build_object('state',case when v_append->>'state'='APPENDED' then 'REMEMBERED' else v_append->>'state' end,'context',v_context,'memory',v_append,'authority_created',false);
end;
$$;

create or replace function penta_runtime.penta_memory_read_v1(
  p_actor_identity_key text,
  p_target_identity_key text,
  p_limit integer default 50,
  p_classification_ceiling text default null
)
returns jsonb
language plpgsql
security definer
stable
set search_path = pg_catalog, penta_runtime
as $$
declare
  v_actor penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_target penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_ceiling text;
  v_limit integer := greatest(1,least(coalesce(p_limit,50),200));
  v_records jsonb;
begin
  select * into v_actor from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_actor_identity_key) and current;
  select * into v_target from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_target_identity_key) and current;
  if v_actor.identity_key is null or v_target.identity_key is null then raise exception 'unknown Penta memory identity'; end if;
  if v_actor.identity_key <> v_target.identity_key and not (
    v_actor.identity_key='penta.brain' and exists(select 1 from penta_runtime.penta_memory_family_grants_v1 g where g.subject_identity_key='penta.brain' and g.family_key=v_target.family_key and g.current and g.access_mode='READ_ONLY' and not g.cross_family_write and not g.authority_expansion)
  ) then raise exception 'cross-identity memory read denied'; end if;
  v_ceiling := lower(coalesce(p_classification_ceiling,v_actor.classification_ceiling));
  if penta_runtime.penta_memory_classification_rank_v1(v_ceiling) > penta_runtime.penta_memory_classification_rank_v1(v_actor.classification_ceiling) then raise exception 'requested classification ceiling exceeds actor ceiling'; end if;

  select coalesce(jsonb_agg(to_jsonb(x) order by x.created_at desc,x.memory_record_id desc),'[]'::jsonb) into v_records
  from (
    select memory_record_id,identity_key,namespace_key,operation,idempotency_key,context_id,classification,payload,payload_bytes,logical_bytes,payload_sha256,source_sha256,supersedes_record_id,previous_record_sha256,record_sha256,provenance,expires_at,created_at
    from penta_runtime.penta_memory_records_v1
    where identity_key=v_target.identity_key and penta_runtime.penta_memory_classification_rank_v1(classification) <= penta_runtime.penta_memory_classification_rank_v1(v_ceiling)
      and (expires_at is null or expires_at>now())
    order by created_at desc,memory_record_id desc
    limit v_limit
  ) x;

  return jsonb_build_object('actor_identity_key',v_actor.identity_key,'target_identity_key',v_target.identity_key,'classification_ceiling',v_ceiling,'record_count',jsonb_array_length(v_records),'records',v_records,'authority_created',false);
end;
$$;

create or replace function penta_runtime.penta_memory_context_query_v1(
  p_actor_identity_key text,
  p_target_identity_key text,
  p_query text default '',
  p_limit integer default 8,
  p_max_chars integer default 12000,
  p_tags text[] default null,
  p_classification_ceiling text default null
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, public
as $$
declare
  v_actor penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_target penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_ceiling text;
  v_result jsonb;
begin
  select * into v_actor from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_actor_identity_key) and current;
  select * into v_target from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_target_identity_key) and current;
  if v_actor.identity_key is null or v_target.identity_key is null then raise exception 'unknown Penta memory identity'; end if;
  if v_actor.identity_key <> v_target.identity_key and not (
    v_actor.identity_key='penta.brain' and exists(select 1 from penta_runtime.penta_memory_family_grants_v1 g where g.subject_identity_key='penta.brain' and g.family_key=v_target.family_key and g.current and g.access_mode='READ_ONLY' and not g.cross_family_write and not g.authority_expansion)
  ) then raise exception 'cross-identity context read denied'; end if;
  v_ceiling := lower(coalesce(p_classification_ceiling,v_actor.classification_ceiling));
  if penta_runtime.penta_memory_classification_rank_v1(v_ceiling) > penta_runtime.penta_memory_classification_rank_v1(v_actor.classification_ceiling) then raise exception 'requested classification ceiling exceeds actor ceiling'; end if;

  v_result := public.penta_context_query_v1(v_target.namespace_key,p_query,p_limit,p_max_chars,p_tags,v_ceiling,v_actor.identity_key);
  return jsonb_build_object('actor_identity_key',v_actor.identity_key,'target_identity_key',v_target.identity_key,'memory_namespace',v_target.namespace_key,'context',v_result,'authority_created',false);
end;
$$;

create or replace function penta_runtime.penta_deterministic_replay_record_v1(
  p_actor_identity_key text,
  p_operation text,
  p_request_hash text,
  p_input_sha256 text,
  p_manifest_sha256 text,
  p_result_sha256 text default null,
  p_previous_hash text default null,
  p_provider text default null,
  p_provider_version text default null,
  p_model text default null,
  p_model_version text default null,
  p_receipt jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, penta_runtime, extensions
as $$
declare
  v_namespace penta_runtime.penta_memory_namespaces_v1%rowtype;
  v_reference_row penta_runtime.penta_execution_replays_v1%rowtype;
  v_reference text;
  v_state text;
  v_db_sha text;
  v_receipt_sha text;
  v_id uuid;
  v_inserted integer;
begin
  if p_operation is null or p_operation !~ '^[a-z0-9][a-z0-9_.:-]{0,127}$' then raise exception 'invalid operation'; end if;
  if p_request_hash !~ '^[0-9a-f]{64}$' or p_input_sha256 !~ '^[0-9a-f]{64}$' or p_manifest_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid deterministic request hash'; end if;
  if p_result_sha256 is not null and p_result_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'invalid result sha256'; end if;
  if p_previous_hash is not null and p_previous_hash !~ '^[0-9a-f]{64}$' then raise exception 'invalid previous hash'; end if;

  perform pg_advisory_xact_lock(pg_catalog.hashtextextended('ct.penta.replay:' || p_request_hash,0));
  select * into v_namespace from penta_runtime.penta_memory_namespaces_v1 where identity_key=lower(p_actor_identity_key) and current;
  if not found or not v_namespace.write_enabled or v_namespace.memory_state <> 'ACTIVE_FAIL_CLOSED' then raise exception 'Penta replay identity is not writable'; end if;
  if p_provider is not null and p_provider_version is null then raise exception 'provider replay requires a pinned provider version'; end if;
  if p_model is not null and (p_provider is null or p_provider_version is null or p_model_version is null) then raise exception 'model replay requires pinned provider, provider version, and model version'; end if;

  select * into v_reference_row
  from penta_runtime.penta_execution_replays_v1
  where identity_key=v_namespace.identity_key and request_hash=p_request_hash and replay_state in ('RECORDED','MATCH')
  order by created_at,replay_receipt_id
  limit 1;

  if not found then
    v_state := 'RECORDED';
    v_reference := null;
  else
    if v_reference_row.operation <> p_operation
      or v_reference_row.input_sha256 <> p_input_sha256
      or v_reference_row.manifest_sha256 <> p_manifest_sha256
      or v_reference_row.previous_hash is distinct from p_previous_hash
      or v_reference_row.provider is distinct from p_provider
      or v_reference_row.provider_version is distinct from p_provider_version
      or v_reference_row.model is distinct from p_model
      or v_reference_row.model_version is distinct from p_model_version then
      raise exception 'request hash collision with different deterministic execution envelope';
    end if;
    v_reference := v_reference_row.result_sha256;
    if v_reference is not distinct from p_result_sha256 then v_state := 'MATCH';
    else v_state := 'MISMATCH'; end if;
  end if;

  v_db_sha := encode(extensions.digest(concat_ws(E'\x1f',v_namespace.identity_key,p_operation,p_request_hash,p_input_sha256,p_manifest_sha256,coalesce(p_result_sha256,''),coalesce(p_previous_hash,''),coalesce(p_provider,''),coalesce(p_provider_version,''),coalesce(p_model,''),coalesce(p_model_version,''),'0','0'),'sha256'),'hex');
  v_receipt_sha := encode(extensions.digest(concat_ws(E'\x1f',v_db_sha,v_state,coalesce(v_reference,''),coalesce(p_receipt,'{}'::jsonb)::text),'sha256'),'hex');
  v_id := extensions.uuid_generate_v5(extensions.uuid_ns_url(),'ct.penta.replay:' || v_receipt_sha);

  insert into penta_runtime.penta_execution_replays_v1(
    replay_receipt_id,identity_key,operation,request_hash,input_sha256,manifest_sha256,database_request_sha256,
    result_sha256,reference_result_sha256,previous_hash,provider,provider_version,model,model_version,replay_state,receipt,receipt_sha256
  ) values(
    v_id,v_namespace.identity_key,p_operation,p_request_hash,p_input_sha256,p_manifest_sha256,v_db_sha,p_result_sha256,
    v_reference,p_previous_hash,p_provider,p_provider_version,p_model,p_model_version,v_state,coalesce(p_receipt,'{}'::jsonb),v_receipt_sha
  ) on conflict(replay_receipt_id) do nothing;
  get diagnostics v_inserted = row_count;

  if v_inserted > 0 then
    perform penta_runtime.penta_memory_lifecycle_append_v1(v_namespace.identity_key,case v_state when 'RECORDED' then 'REPLAY_RECORDED' when 'MATCH' then 'REPLAY_MATCH' else 'REPLAY_MISMATCH' end,v_state,jsonb_build_object('replay_receipt_id',v_id,'request_hash',p_request_hash,'result_sha256',p_result_sha256,'reference_result_sha256',v_reference,'receipt_sha256',v_receipt_sha,'authority_created',false));
  end if;

  return jsonb_build_object('replay_receipt_id',v_id,'replay_state',v_state,'passed',v_state in ('RECORDED','MATCH'),'request_hash',p_request_hash,'database_request_sha256',v_db_sha,'result_sha256',p_result_sha256,'reference_result_sha256',v_reference,'receipt_sha256',v_receipt_sha,'authority_created',false);
end;
$$;

alter table penta_runtime.penta_memory_namespaces_v1 enable row level security;
alter table penta_runtime.penta_memory_records_v1 enable row level security;
alter table penta_runtime.penta_execution_replays_v1 enable row level security;
alter table penta_runtime.penta_lifecycle_events_v1 enable row level security;
alter table penta_runtime.penta_memory_family_grants_v1 enable row level security;
alter table penta_runtime.penta_memory_census_receipts_v1 enable row level security;

drop policy if exists penta_memory_namespaces_explicit_client_deny_v1 on penta_runtime.penta_memory_namespaces_v1;
create policy penta_memory_namespaces_explicit_client_deny_v1 on penta_runtime.penta_memory_namespaces_v1 for all to anon,authenticated using(false) with check(false);
drop policy if exists penta_memory_records_explicit_client_deny_v1 on penta_runtime.penta_memory_records_v1;
create policy penta_memory_records_explicit_client_deny_v1 on penta_runtime.penta_memory_records_v1 for all to anon,authenticated using(false) with check(false);
drop policy if exists penta_execution_replays_explicit_client_deny_v1 on penta_runtime.penta_execution_replays_v1;
create policy penta_execution_replays_explicit_client_deny_v1 on penta_runtime.penta_execution_replays_v1 for all to anon,authenticated using(false) with check(false);
drop policy if exists penta_lifecycle_events_explicit_client_deny_v1 on penta_runtime.penta_lifecycle_events_v1;
create policy penta_lifecycle_events_explicit_client_deny_v1 on penta_runtime.penta_lifecycle_events_v1 for all to anon,authenticated using(false) with check(false);
drop policy if exists penta_memory_family_grants_explicit_client_deny_v1 on penta_runtime.penta_memory_family_grants_v1;
create policy penta_memory_family_grants_explicit_client_deny_v1 on penta_runtime.penta_memory_family_grants_v1 for all to anon,authenticated using(false) with check(false);
drop policy if exists penta_memory_census_receipts_explicit_client_deny_v1 on penta_runtime.penta_memory_census_receipts_v1;
create policy penta_memory_census_receipts_explicit_client_deny_v1 on penta_runtime.penta_memory_census_receipts_v1 for all to anon,authenticated using(false) with check(false);

revoke all on table penta_runtime.penta_memory_namespaces_v1,penta_runtime.penta_memory_records_v1,penta_runtime.penta_execution_replays_v1,penta_runtime.penta_lifecycle_events_v1,penta_runtime.penta_memory_family_grants_v1,penta_runtime.penta_memory_census_receipts_v1 from public,anon,authenticated,service_role;
revoke all on table penta_runtime.penta_memory_status_v1,penta_runtime.penta_brain_memory_mesh_status_v1 from public,anon,authenticated,service_role;
grant usage on schema penta_runtime to service_role;
grant select on table penta_runtime.penta_memory_namespaces_v1,penta_runtime.penta_memory_records_v1,penta_runtime.penta_execution_replays_v1,penta_runtime.penta_lifecycle_events_v1,penta_runtime.penta_memory_family_grants_v1,penta_runtime.penta_memory_census_receipts_v1 to service_role;
grant select on table penta_runtime.penta_memory_status_v1,penta_runtime.penta_brain_memory_mesh_status_v1 to service_role;

revoke all on function penta_runtime.penta_memory_classification_rank_v1(text) from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_namespace_key_v1(text) from public,anon,authenticated,service_role;
revoke all on function penta_runtime.penta_memory_profile_v1(text,text,text) from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_touch_updated_at_v1() from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_append_only_guard_v1() from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_lifecycle_append_v1(text,text,text,jsonb) from public,anon,authenticated,service_role;
revoke all on function penta_runtime.penta_memory_append_core_v1(text,text,text,text,jsonb,text,uuid,text,jsonb,uuid,bigint) from public,anon,authenticated,service_role;
revoke all on function penta_runtime.penta_memory_health_v1() from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_reconcile_v1() from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_append_v1(text,text,text,text,jsonb,text,uuid,text,jsonb,uuid) from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_remember_v1(text,text,text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz) from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_read_v1(text,text,integer,text) from public,anon,authenticated;
revoke all on function penta_runtime.penta_memory_context_query_v1(text,text,text,integer,integer,text[],text) from public,anon,authenticated;
revoke all on function penta_runtime.penta_deterministic_replay_record_v1(text,text,text,text,text,text,text,text,text,text,text,jsonb) from public,anon,authenticated;

grant execute on function penta_runtime.penta_memory_health_v1() to service_role;
grant execute on function penta_runtime.penta_memory_reconcile_v1() to service_role;
grant execute on function penta_runtime.penta_memory_append_v1(text,text,text,text,jsonb,text,uuid,text,jsonb,uuid) to service_role;
grant execute on function penta_runtime.penta_memory_remember_v1(text,text,text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz) to service_role;
grant execute on function penta_runtime.penta_memory_read_v1(text,text,integer,text) to service_role;
grant execute on function penta_runtime.penta_memory_context_query_v1(text,text,text,integer,integer,text[],text) to service_role;
grant execute on function penta_runtime.penta_deterministic_replay_record_v1(text,text,text,text,text,text,text,text,text,text,text,jsonb) to service_role;

comment on table penta_runtime.penta_memory_namespaces_v1 is 'One literal durable memory allocation per current Penta identity. Quotas are logical persistent bytes, not a claim of dedicated physical RAM.';
comment on table penta_runtime.penta_memory_records_v1 is 'Append-only, hash-chained Penta memory index and payload records; PentaContext remains the canonical evidence-backed semantic content store.';
comment on table penta_runtime.penta_execution_replays_v1 is 'Append-only deterministic execution replay receipts. MISMATCH is preserved and fails consequential release closed.';
comment on function penta_runtime.penta_memory_canonical_family_key_v1(text) is 'Maps authoritative ThriveBase provider family aliases to the canonical repository family identity without rewriting provider primary keys.';
comment on function penta_runtime.penta_memory_reconcile_v1() is 'Idempotently assigns memory to every current Penta, verifies PentaBrain supporting families, and projects allocations into PentaCensus without creating authority.';
comment on function penta_runtime.penta_memory_remember_v1(text,text,text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz) is 'Atomically scopes durable PentaContext content to a Penta memory namespace and adds a quota-counted memory index record.';

select penta_runtime.penta_memory_reconcile_v1();

commit;
