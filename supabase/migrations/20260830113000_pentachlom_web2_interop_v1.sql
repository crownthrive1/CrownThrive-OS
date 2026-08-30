-- CrownThrive PentaCHLOM Web2 interoperability runtime v1
--
-- PentaCHLOM is a governed translation/projection adapter over canonical CHLOM.
-- It does not inherit or manufacture CHLOM authority, grant rights, create credentials,
-- move money, issue token classes, perform provider writes, or perform D3 actions.
-- Canonical CHLOM/DAIL evidence remains authoritative; Web2 views are derived projections.

create or replace function penta_runtime.pentachlom_metadata_safe_v1(p_metadata jsonb)
returns boolean
language sql
immutable
set search_path = pg_catalog
as $$
  select coalesce(p_metadata, '{}'::jsonb)::text !~* '"(password|secret|token|api[_ -]?key|private[_ -]?key|credential|authorization)"[[:space:]]*:';
$$;

create table if not exists penta_runtime.pentachlom_identity_bindings_v1 (
  binding_id uuid primary key default gen_random_uuid(),
  provider_system text not null,
  provider_subject_digest text not null check (provider_subject_digest ~ '^[0-9a-f]{64}$'),
  tenant_ref text not null,
  purpose text not null,
  chlom_identity_ref text not null,
  identity_kind text not null default 'subject'
    check (identity_kind in ('subject','organization','service','workload','asset','agent')),
  supersedes_binding_id uuid references penta_runtime.pentachlom_identity_bindings_v1(binding_id) on delete restrict,
  source_evidence_ref text not null,
  source_evidence_digest text check (source_evidence_digest is null or source_evidence_digest ~ '^[0-9a-f]{64}$'),
  canonical_dail_event_id uuid not null,
  canonical_dail_event_hash text not null,
  dail_classification jsonb not null,
  metadata jsonb not null default '{}'::jsonb check (penta_runtime.pentachlom_metadata_safe_v1(metadata)),
  created_by text not null,
  created_at timestamptz not null default now(),
  unique(provider_system, provider_subject_digest, tenant_ref, purpose, chlom_identity_ref, source_evidence_ref)
);

create table if not exists penta_runtime.pentachlom_projection_requests_v1 (
  request_id uuid primary key default gen_random_uuid(),
  direction text not null check (direction in ('web2_to_chlom','chlom_to_web2')),
  object_kind text not null
    check (object_kind in ('identity','rights','authority','consent','license','provenance','evidence','audit','eligibility','split','expiration','waiver')),
  tenant_ref text not null,
  source_system text not null,
  source_object_ref text not null,
  source_digest text not null check (source_digest ~ '^[0-9a-f]{64}$'),
  target_system text not null,
  target_object_ref text,
  chlom_object_ref text,
  identity_binding_id uuid references penta_runtime.pentachlom_identity_bindings_v1(binding_id) on delete restrict,
  authority_inherited boolean not null default false check (authority_inherited = false),
  rights_granted boolean not null default false check (rights_granted = false),
  provider_write_performed boolean not null default false check (provider_write_performed = false),
  metadata jsonb not null default '{}'::jsonb check (penta_runtime.pentachlom_metadata_safe_v1(metadata)),
  opened_by text not null,
  created_at timestamptz not null default now(),
  unique(direction, source_system, source_object_ref, source_digest, target_system, tenant_ref)
);

create table if not exists penta_runtime.pentachlom_projection_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  request_id uuid not null references penta_runtime.pentachlom_projection_requests_v1(request_id) on delete restrict,
  from_state text,
  to_state text not null check (to_state in ('candidate','validated','projected','hold','rejected','superseded')),
  semantic_stage text not null check (semantic_stage in ('evidence','decision','execution')),
  actor_ref text not null,
  evidence_ref text not null,
  evidence_digest text check (evidence_digest is null or evidence_digest ~ '^[0-9a-f]{64}$'),
  chlom_authority_event_id uuid,
  canonical_dail_event_id uuid not null,
  canonical_dail_event_hash text not null,
  dail_classification jsonb not null,
  metadata jsonb not null default '{}'::jsonb check (penta_runtime.pentachlom_metadata_safe_v1(metadata)),
  created_at timestamptz not null default now(),
  unique(canonical_dail_event_id)
);

create or replace function penta_runtime.pentachlom_reject_mutation_v1()
returns trigger
language plpgsql
set search_path = pg_catalog, penta_runtime
as $$
begin
  raise exception 'PentaCHLOM source records and chronology are append-only; supersede through governed functions';
end
$$;

drop trigger if exists pentachlom_identity_bindings_immutable_v1 on penta_runtime.pentachlom_identity_bindings_v1;
create trigger pentachlom_identity_bindings_immutable_v1
before update or delete on penta_runtime.pentachlom_identity_bindings_v1
for each row execute function penta_runtime.pentachlom_reject_mutation_v1();

drop trigger if exists pentachlom_projection_requests_immutable_v1 on penta_runtime.pentachlom_projection_requests_v1;
create trigger pentachlom_projection_requests_immutable_v1
before update or delete on penta_runtime.pentachlom_projection_requests_v1
for each row execute function penta_runtime.pentachlom_reject_mutation_v1();

drop trigger if exists pentachlom_projection_events_immutable_v1 on penta_runtime.pentachlom_projection_events_v1;
create trigger pentachlom_projection_events_immutable_v1
before update or delete on penta_runtime.pentachlom_projection_events_v1
for each row execute function penta_runtime.pentachlom_reject_mutation_v1();

alter table penta_runtime.pentachlom_identity_bindings_v1 enable row level security;
alter table penta_runtime.pentachlom_projection_requests_v1 enable row level security;
alter table penta_runtime.pentachlom_projection_events_v1 enable row level security;

revoke all on penta_runtime.pentachlom_identity_bindings_v1 from public, anon, authenticated;
revoke all on penta_runtime.pentachlom_projection_requests_v1 from public, anon, authenticated;
revoke all on penta_runtime.pentachlom_projection_events_v1 from public, anon, authenticated;
grant select on penta_runtime.pentachlom_identity_bindings_v1 to service_role;
grant select on penta_runtime.pentachlom_projection_requests_v1 to service_role;
grant select on penta_runtime.pentachlom_projection_events_v1 to service_role;

create or replace function penta_runtime.pentachlom_bind_identity_v1(
  p_provider_system text,
  p_provider_subject_digest text,
  p_tenant_ref text,
  p_purpose text,
  p_chlom_identity_ref text,
  p_source_evidence_ref text,
  p_actor_ref text,
  p_identity_kind text default 'subject',
  p_supersedes_binding_id uuid default null,
  p_source_evidence_digest text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, penta_runtime, chlom_runtime
as $$
declare
  v_binding_id uuid := gen_random_uuid();
  v_dail jsonb;
  v_classification jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_readback_hash text;
begin
  if coalesce(btrim(p_provider_system),'') = ''
     or coalesce(btrim(p_provider_subject_digest),'') !~ '^[0-9a-f]{64}$'
     or coalesce(btrim(p_tenant_ref),'') = ''
     or coalesce(btrim(p_purpose),'') = ''
     or coalesce(btrim(p_chlom_identity_ref),'') = ''
     or coalesce(btrim(p_source_evidence_ref),'') = ''
     or coalesce(btrim(p_actor_ref),'') = '' then
    raise exception 'provider, hashed subject, tenant, purpose, CHLOM identity, evidence and actor are required';
  end if;
  if p_identity_kind not in ('subject','organization','service','workload','asset','agent') then
    raise exception 'unsupported identity kind';
  end if;
  if not penta_runtime.pentachlom_metadata_safe_v1(p_metadata) then
    raise exception 'metadata contains prohibited secret/credential-like keys';
  end if;
  if p_source_evidence_digest is not null and p_source_evidence_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'source evidence digest must be lowercase SHA-256 hex';
  end if;
  if p_supersedes_binding_id is not null and not exists (
    select 1 from penta_runtime.pentachlom_identity_bindings_v1 where binding_id=p_supersedes_binding_id
  ) then
    raise exception 'superseded binding not found';
  end if;

  v_dail := chlom_runtime.append_dail_event(
    'pentachlom_identity_binding_evidence',
    'pentachlom_identity_binding',
    v_binding_id::text,
    jsonb_build_object(
      'provider_system', p_provider_system,
      'provider_subject_digest', p_provider_subject_digest,
      'tenant_ref', p_tenant_ref,
      'purpose', p_purpose,
      'chlom_identity_ref', p_chlom_identity_ref,
      'identity_kind', p_identity_kind,
      'source_evidence_ref', p_source_evidence_ref,
      'source_evidence_digest', p_source_evidence_digest,
      'supersedes_binding_id', p_supersedes_binding_id,
      'authority_inherited', false,
      'rights_granted', false,
      'provider_write_performed', false,
      'semantic_stage', 'evidence'
    ),
    p_actor_ref,
    p_actor_did,
    p_agent_id,
    '1.0.0',
    v_binding_id::text,
    p_supersedes_binding_id::text,
    'ct.pentachlom.identity-bind.v1',
    null,
    'internal'
  );

  v_dail_event_id := (v_dail->>'event_id')::uuid;
  v_dail_event_hash := v_dail->>'event_hash';
  v_classification := chlom_runtime.dail_classify_event_lanes_v1(v_dail_event_id);

  select event_hash into v_readback_hash
  from chlom_runtime.dail_events
  where event_id=v_dail_event_id;

  if v_readback_hash is null or v_readback_hash <> v_dail_event_hash then
    raise exception 'canonical DAIL append/readback mismatch during PentaCHLOM identity binding';
  end if;

  insert into penta_runtime.pentachlom_identity_bindings_v1(
    binding_id, provider_system, provider_subject_digest, tenant_ref, purpose,
    chlom_identity_ref, identity_kind, supersedes_binding_id, source_evidence_ref,
    source_evidence_digest, canonical_dail_event_id, canonical_dail_event_hash,
    dail_classification, metadata, created_by
  ) values (
    v_binding_id, p_provider_system, p_provider_subject_digest, p_tenant_ref, p_purpose,
    p_chlom_identity_ref, p_identity_kind, p_supersedes_binding_id, p_source_evidence_ref,
    p_source_evidence_digest, v_dail_event_id, v_dail_event_hash,
    v_classification, coalesce(p_metadata,'{}'::jsonb), p_actor_ref
  );

  return jsonb_build_object(
    'binding_id', v_binding_id,
    'chlom_identity_ref', p_chlom_identity_ref,
    'canonical_dail_event_id', v_dail_event_id,
    'canonical_dail_event_hash', v_dail_event_hash,
    'authority_inherited', false,
    'rights_granted', false,
    'provider_write_performed', false
  );
end
$$;

create or replace function penta_runtime.pentachlom_open_projection_v1(
  p_direction text,
  p_object_kind text,
  p_tenant_ref text,
  p_source_system text,
  p_source_object_ref text,
  p_source_digest text,
  p_target_system text,
  p_actor_ref text,
  p_evidence_ref text,
  p_target_object_ref text default null,
  p_chlom_object_ref text default null,
  p_identity_binding_id uuid default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, penta_runtime, chlom_runtime
as $$
declare
  v_request_id uuid := gen_random_uuid();
  v_dail jsonb;
  v_classification jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_readback_hash text;
begin
  if p_direction not in ('web2_to_chlom','chlom_to_web2') then
    raise exception 'unsupported projection direction';
  end if;
  if p_object_kind not in ('identity','rights','authority','consent','license','provenance','evidence','audit','eligibility','split','expiration','waiver') then
    raise exception 'unsupported projection object kind';
  end if;
  if coalesce(btrim(p_tenant_ref),'') = ''
     or coalesce(btrim(p_source_system),'') = ''
     or coalesce(btrim(p_source_object_ref),'') = ''
     or coalesce(btrim(p_source_digest),'') !~ '^[0-9a-f]{64}$'
     or coalesce(btrim(p_target_system),'') = ''
     or coalesce(btrim(p_actor_ref),'') = ''
     or coalesce(btrim(p_evidence_ref),'') = '' then
    raise exception 'tenant/source/digest/target/actor/evidence are required';
  end if;
  if not penta_runtime.pentachlom_metadata_safe_v1(p_metadata) then
    raise exception 'metadata contains prohibited secret/credential-like keys';
  end if;
  if p_identity_binding_id is not null and not exists (
    select 1 from penta_runtime.pentachlom_identity_bindings_v1 where binding_id=p_identity_binding_id
  ) then
    raise exception 'identity binding not found';
  end if;

  insert into penta_runtime.pentachlom_projection_requests_v1(
    request_id, direction, object_kind, tenant_ref, source_system, source_object_ref,
    source_digest, target_system, target_object_ref, chlom_object_ref,
    identity_binding_id, metadata, opened_by
  ) values (
    v_request_id, p_direction, p_object_kind, p_tenant_ref, p_source_system, p_source_object_ref,
    p_source_digest, p_target_system, p_target_object_ref, p_chlom_object_ref,
    p_identity_binding_id, coalesce(p_metadata,'{}'::jsonb), p_actor_ref
  );

  v_dail := chlom_runtime.append_dail_event(
    'pentachlom_projection_evidence',
    'pentachlom_projection',
    v_request_id::text,
    jsonb_build_object(
      'direction', p_direction,
      'object_kind', p_object_kind,
      'tenant_ref', p_tenant_ref,
      'source_system', p_source_system,
      'source_object_ref', p_source_object_ref,
      'source_digest', p_source_digest,
      'target_system', p_target_system,
      'target_object_ref', p_target_object_ref,
      'chlom_object_ref', p_chlom_object_ref,
      'identity_binding_id', p_identity_binding_id,
      'state', 'candidate',
      'semantic_stage', 'evidence',
      'evidence_ref', p_evidence_ref,
      'authority_inherited', false,
      'rights_granted', false,
      'provider_write_performed', false
    ),
    p_actor_ref,
    p_actor_did,
    p_agent_id,
    '1.0.0',
    v_request_id::text,
    null,
    'ct.pentachlom.projection.open.v1',
    null,
    'internal'
  );

  v_dail_event_id := (v_dail->>'event_id')::uuid;
  v_dail_event_hash := v_dail->>'event_hash';
  v_classification := chlom_runtime.dail_classify_event_lanes_v1(v_dail_event_id);

  select event_hash into v_readback_hash
  from chlom_runtime.dail_events where event_id=v_dail_event_id;
  if v_readback_hash is null or v_readback_hash <> v_dail_event_hash then
    raise exception 'canonical DAIL append/readback mismatch while opening PentaCHLOM projection';
  end if;

  insert into penta_runtime.pentachlom_projection_events_v1(
    request_id, from_state, to_state, semantic_stage, actor_ref, evidence_ref,
    canonical_dail_event_id, canonical_dail_event_hash, dail_classification, metadata
  ) values (
    v_request_id, null, 'candidate', 'evidence', p_actor_ref, p_evidence_ref,
    v_dail_event_id, v_dail_event_hash, v_classification, coalesce(p_metadata,'{}'::jsonb)
  );

  return jsonb_build_object(
    'request_id', v_request_id,
    'state', 'candidate',
    'canonical_dail_event_id', v_dail_event_id,
    'canonical_dail_event_hash', v_dail_event_hash,
    'authority_inherited', false,
    'rights_granted', false,
    'provider_write_performed', false
  );
end
$$;

create or replace function penta_runtime.pentachlom_record_projection_event_v1(
  p_request_id uuid,
  p_to_state text,
  p_actor_ref text,
  p_evidence_ref text,
  p_semantic_stage text,
  p_evidence_digest text default null,
  p_chlom_authority_event_id uuid default null,
  p_authority_basis text default 'ct.pentachlom.projection.transition.v1',
  p_approval_id text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, penta_runtime, chlom_runtime
as $$
declare
  v_req penta_runtime.pentachlom_projection_requests_v1%rowtype;
  v_from_state text;
  v_last_event_id uuid;
  v_ok boolean := false;
  v_dail jsonb;
  v_classification jsonb;
  v_dail_event_id uuid;
  v_dail_event_hash text;
  v_readback_hash text;
  v_event_type text;
begin
  select * into v_req
  from penta_runtime.pentachlom_projection_requests_v1
  where request_id=p_request_id;
  if not found then raise exception 'unknown PentaCHLOM projection request'; end if;

  select event_id, to_state into v_last_event_id, v_from_state
  from penta_runtime.pentachlom_projection_events_v1
  where request_id=p_request_id
  order by created_at desc, event_id desc
  limit 1;

  if coalesce(btrim(p_actor_ref),'') = '' or coalesce(btrim(p_evidence_ref),'') = '' then
    raise exception 'actor and evidence are required';
  end if;
  if p_to_state not in ('validated','projected','hold','rejected','superseded') then
    raise exception 'unsupported target state';
  end if;
  if p_semantic_stage not in ('evidence','decision','execution') then
    raise exception 'unsupported semantic stage';
  end if;
  if not penta_runtime.pentachlom_metadata_safe_v1(p_metadata) then
    raise exception 'metadata contains prohibited secret/credential-like keys';
  end if;
  if p_evidence_digest is not null and p_evidence_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'evidence digest must be lowercase SHA-256 hex';
  end if;

  if p_to_state in ('validated','hold','rejected','superseded') and p_semantic_stage <> 'decision' then
    raise exception 'validation/HOLD/rejection/supersession are decision-stage events';
  end if;
  if p_to_state='projected' and p_semantic_stage <> 'execution' then
    raise exception 'projection materialization is an execution-stage event';
  end if;

  if p_to_state='validated' and p_actor_ref=v_req.opened_by then
    raise exception 'projection originator cannot independently validate own projection';
  end if;

  if p_chlom_authority_event_id is not null and not exists (
    select 1 from chlom_runtime.dail_events where event_id=p_chlom_authority_event_id
  ) then
    raise exception 'referenced CHLOM authority evidence event does not exist';
  end if;

  if p_to_state='projected'
     and v_req.object_kind in ('rights','authority','consent','license','eligibility','split','expiration','waiver')
     and p_chlom_authority_event_id is null then
    raise exception 'governance-bearing projections require an exact CHLOM authority evidence event reference';
  end if;

  v_ok :=
    (v_from_state='candidate' and p_to_state in ('validated','hold','rejected')) or
    (v_from_state='validated' and p_to_state in ('projected','hold','rejected')) or
    (v_from_state='projected' and p_to_state in ('superseded','hold')) or
    (v_from_state='hold' and p_to_state in ('validated','rejected'));
  if not v_ok then
    raise exception 'invalid PentaCHLOM projection transition % -> %', v_from_state, p_to_state;
  end if;

  v_event_type := case p_semantic_stage
    when 'execution' then 'pentachlom_projection_execution'
    when 'decision' then 'pentachlom_projection_decision'
    else 'pentachlom_projection_evidence'
  end;

  v_dail := chlom_runtime.append_dail_event(
    v_event_type,
    'pentachlom_projection',
    p_request_id::text,
    coalesce(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'direction', v_req.direction,
      'object_kind', v_req.object_kind,
      'tenant_ref', v_req.tenant_ref,
      'source_system', v_req.source_system,
      'source_object_ref', v_req.source_object_ref,
      'source_digest', v_req.source_digest,
      'target_system', v_req.target_system,
      'target_object_ref', v_req.target_object_ref,
      'chlom_object_ref', v_req.chlom_object_ref,
      'from_state', v_from_state,
      'to_state', p_to_state,
      'semantic_stage', p_semantic_stage,
      'evidence_ref', p_evidence_ref,
      'evidence_digest', p_evidence_digest,
      'chlom_authority_event_id', p_chlom_authority_event_id,
      'authority_inherited', false,
      'rights_granted', false,
      'provider_write_performed', false
    ),
    p_actor_ref,
    p_actor_did,
    p_agent_id,
    '1.0.0',
    p_request_id::text,
    v_last_event_id::text,
    coalesce(nullif(btrim(p_authority_basis),''),'ct.pentachlom.projection.transition.v1'),
    p_approval_id,
    'internal'
  );

  v_dail_event_id := (v_dail->>'event_id')::uuid;
  v_dail_event_hash := v_dail->>'event_hash';
  v_classification := chlom_runtime.dail_classify_event_lanes_v1(v_dail_event_id);

  select event_hash into v_readback_hash
  from chlom_runtime.dail_events where event_id=v_dail_event_id;
  if v_readback_hash is null or v_readback_hash <> v_dail_event_hash then
    raise exception 'canonical DAIL append/readback mismatch during PentaCHLOM transition';
  end if;

  insert into penta_runtime.pentachlom_projection_events_v1(
    request_id, from_state, to_state, semantic_stage, actor_ref, evidence_ref,
    evidence_digest, chlom_authority_event_id, canonical_dail_event_id,
    canonical_dail_event_hash, dail_classification, metadata
  ) values (
    p_request_id, v_from_state, p_to_state, p_semantic_stage, p_actor_ref, p_evidence_ref,
    p_evidence_digest, p_chlom_authority_event_id, v_dail_event_id,
    v_dail_event_hash, v_classification, coalesce(p_metadata,'{}'::jsonb)
  );

  return jsonb_build_object(
    'request_id', p_request_id,
    'from_state', v_from_state,
    'to_state', p_to_state,
    'canonical_dail_event_id', v_dail_event_id,
    'canonical_dail_event_hash', v_dail_event_hash,
    'chlom_authority_event_id', p_chlom_authority_event_id,
    'authority_inherited', false,
    'rights_granted', false,
    'provider_write_performed', false
  );
end
$$;

create or replace view penta_runtime.pentachlom_projection_status_v1 as
select
  r.request_id,
  r.direction,
  r.object_kind,
  r.tenant_ref,
  r.source_system,
  r.source_object_ref,
  r.source_digest,
  r.target_system,
  r.target_object_ref,
  r.chlom_object_ref,
  r.identity_binding_id,
  r.authority_inherited,
  r.rights_granted,
  r.provider_write_performed,
  e.to_state as current_state,
  e.semantic_stage as latest_semantic_stage,
  e.actor_ref as latest_actor_ref,
  e.evidence_ref as latest_evidence_ref,
  e.chlom_authority_event_id,
  e.canonical_dail_event_id,
  e.canonical_dail_event_hash,
  e.created_at as latest_event_at,
  r.created_at
from penta_runtime.pentachlom_projection_requests_v1 r
join lateral (
  select x.*
  from penta_runtime.pentachlom_projection_events_v1 x
  where x.request_id=r.request_id
  order by x.created_at desc, x.event_id desc
  limit 1
) e on true;

revoke all on penta_runtime.pentachlom_projection_status_v1 from public, anon, authenticated;
grant select on penta_runtime.pentachlom_projection_status_v1 to service_role;

create or replace function penta_runtime.pentachlom_render_projection_v1(p_request_id uuid)
returns jsonb
language plpgsql
security definer
stable
set search_path = pg_catalog, penta_runtime
as $$
declare
  v record;
begin
  select * into v
  from penta_runtime.pentachlom_projection_status_v1
  where request_id=p_request_id;
  if not found then raise exception 'unknown PentaCHLOM projection request'; end if;
  if v.current_state not in ('validated','projected') then
    raise exception 'projection is not validated for derived-view rendering';
  end if;

  return jsonb_build_object(
    'schema','ct.pentachlom.web2-projection/v1',
    'request_id',v.request_id,
    'direction',v.direction,
    'object_kind',v.object_kind,
    'tenant_ref',v.tenant_ref,
    'source',jsonb_build_object(
      'system',v.source_system,
      'object_ref',v.source_object_ref,
      'digest',v.source_digest
    ),
    'target',jsonb_build_object(
      'system',v.target_system,
      'object_ref',v.target_object_ref
    ),
    'chlom_object_ref',v.chlom_object_ref,
    'identity_binding_id',v.identity_binding_id,
    'current_state',v.current_state,
    'canonical_dail_event_id',v.canonical_dail_event_id,
    'canonical_dail_event_hash',v.canonical_dail_event_hash,
    'chlom_authority_event_id',v.chlom_authority_event_id,
    'authority_inherited',false,
    'rights_granted',false,
    'provider_write_performed',false,
    'derived_view',true,
    'canonical_authority','CHLOM'
  );
end
$$;

create or replace function penta_runtime.pentachlom_status_v1()
returns jsonb
language sql
security definer
stable
set search_path = pg_catalog, penta_runtime
as $$
  select jsonb_build_object(
    'system','PentaCHLOM',
    'contract','ct.pentachlom.web2-interop.v1',
    'role','governed Web2/interop translation and projection adapter over canonical CHLOM',
    'canonical_authority','CHLOM',
    'authority_created',false,
    'authority_inherited',false,
    'rights_grant_capability',false,
    'credential_capability',false,
    'provider_write_capability',false,
    'money_movement_capability',false,
    'token_class_authority',false,
    'd3_capability',false,
    'canonical_dail_topology',jsonb_build_array('HUMAN','HYBRID','MACHINE'),
    'semantic_stages',jsonb_build_array('evidence','decision','execution'),
    'identity_bindings',(select count(*) from penta_runtime.pentachlom_identity_bindings_v1),
    'projection_requests',(select count(*) from penta_runtime.pentachlom_projection_requests_v1),
    'projection_events',(select count(*) from penta_runtime.pentachlom_projection_events_v1),
    'current_states',coalesce((
      select jsonb_object_agg(current_state,n)
      from (select current_state,count(*) n from penta_runtime.pentachlom_projection_status_v1 group by current_state) s
    ),'{}'::jsonb),
    'production_certified',false,
    'certification_state','PENDING_INDEPENDENT_CERTIFICATION'
  );
$$;

revoke all on function penta_runtime.pentachlom_metadata_safe_v1(jsonb) from public, anon, authenticated;
revoke all on function penta_runtime.pentachlom_bind_identity_v1(text,text,text,text,text,text,text,text,uuid,text,text,text,jsonb) from public, anon, authenticated;
revoke all on function penta_runtime.pentachlom_open_projection_v1(text,text,text,text,text,text,text,text,text,text,text,uuid,text,text,jsonb) from public, anon, authenticated;
revoke all on function penta_runtime.pentachlom_record_projection_event_v1(uuid,text,text,text,text,text,text,uuid,text,text,text,text,jsonb) from public, anon, authenticated;
revoke all on function penta_runtime.pentachlom_render_projection_v1(uuid) from public, anon, authenticated;
revoke all on function penta_runtime.pentachlom_status_v1() from public, anon, authenticated;

grant execute on function penta_runtime.pentachlom_metadata_safe_v1(jsonb) to service_role;
grant execute on function penta_runtime.pentachlom_bind_identity_v1(text,text,text,text,text,text,text,text,uuid,text,text,text,jsonb) to service_role;
grant execute on function penta_runtime.pentachlom_open_projection_v1(text,text,text,text,text,text,text,text,text,text,text,uuid,text,text,jsonb) to service_role;
grant execute on function penta_runtime.pentachlom_record_projection_event_v1(uuid,text,text,text,text,text,text,uuid,text,text,text,text,jsonb) to service_role;
grant execute on function penta_runtime.pentachlom_render_projection_v1(uuid) to service_role;
grant execute on function penta_runtime.pentachlom_status_v1() to service_role;

-- Register PentaCHLOM only when this migration is actually applied. The row is an
-- implemented/candidate runtime identity, not a production certification or CHLOM authority grant.
insert into public.penta_system_registry(
  system_key, canonical_name, category, purpose, authority_boundary, risk_ceiling,
  maturity, version, public_exposure, docs_ref, runtime_ref, metadata
) values (
  'penta.chlom.web2-interop',
  'PentaCHLOM',
  'system',
  'Governed Web2/interoperability translation and projection adapter over canonical CHLOM rights, authority and evidence objects.',
  'Translation/projection only. CHLOM remains canonical authority; PentaCHLOM cannot grant rights, inherit authority, create credentials, write providers, move money, create token classes or perform D3.',
  'D2',
  'implemented',
  '1.0.0',
  false,
  '/pentas/canonical/penta-chlom',
  'function:penta_runtime.pentachlom_status_v1',
  jsonb_build_object(
    'canonical_family_key','ROUTING_INTEROP',
    'canonical_family_name','Penta Routing & Interoperability Family',
    'canonical_authority','ct.chlom.protocol.v1',
    'authority_created',false,
    'authority_inherited',false,
    'rights_grant_capability',false,
    'provider_write_capability',false,
    'd3_capability',false,
    'production_certified',false,
    'certification_state','PENDING_INDEPENDENT_CERTIFICATION',
    'source_migration','20260830113000_pentachlom_web2_interop_v1'
  )
)
on conflict (system_key) do nothing;

-- Reconcile the source candidate created in the preceding PentaSecurity migration without
-- inventing a second identity or claiming independent certification.
insert into penta_runtime.security_capability_bindings_v1(
  capability_key, canonical_name, canonical_identity_key, family_key,
  implementation_state, alias_of, authority_ceiling, source_ref, evidence
) values (
  'pentachlom','PentaCHLOM','penta.chlom.web2-interop','ROUTING_INTEROP',
  'certification_hold',null,'D2',
  'migration:20260830113000_pentachlom_web2_interop_v1',
  jsonb_build_object(
    'runtime_ref','function:penta_runtime.pentachlom_status_v1',
    'canonical_authority','ct.chlom.protocol.v1',
    'authority_created',false,
    'provider_write_capability',false,
    'production_certified',false,
    'requires','PentaCensus identity refresh + independent security review + PentaCertifier + production readback'
  )
)
on conflict (capability_key) do update
set canonical_name=excluded.canonical_name,
    canonical_identity_key=excluded.canonical_identity_key,
    family_key=excluded.family_key,
    implementation_state='certification_hold',
    alias_of=null,
    authority_ceiling='D2',
    source_ref=excluded.source_ref,
    evidence=penta_runtime.security_capability_bindings_v1.evidence || excluded.evidence,
    updated_at=now();
