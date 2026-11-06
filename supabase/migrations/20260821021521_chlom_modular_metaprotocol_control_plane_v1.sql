create schema if not exists chlom_runtime;

create table if not exists chlom_runtime.modules (
  module_id text primary key,
  framework_id text not null default 'ct.framework.chlom',
  canonical_name text not null,
  module_class text not null check (module_class in ('kernel','identity','fingerprint','credentials','rights_graph','dla','dail','lex','dispute','ace','aie','zkx','oracle','ade','treasury','settlement','governance','agent_fabric','chain_adapter','api_mcp','observability','documentation','pallet','service','other')),
  semantic_version text not null default '0.1.0',
  lifecycle_state text not null default 'specified' check (lifecycle_state in ('source_recovered','reconciled','specified','prototype','test','staged','production','maintained','superseded','retired')),
  authority_ceiling text not null default 'D2' check (authority_ceiling in ('D0','D1','D2','D3')),
  self_healing_class text not null default 'observe_only' check (self_healing_class in ('observe_only','deterministic_repair','rollback_capable','quorum_required','human_reserved')),
  public_contract jsonb not null default '{}'::jsonb,
  restricted_contract_ref text,
  implementation_ref text,
  mcp_enabled boolean not null default false,
  api_enabled boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_runtime.module_dependencies (
  module_id text not null references chlom_runtime.modules(module_id) on delete cascade,
  depends_on_module_id text not null references chlom_runtime.modules(module_id) on delete restrict,
  dependency_type text not null default 'required' check (dependency_type in ('required','optional','runtime','evidence','governance','fallback')),
  metadata jsonb not null default '{}'::jsonb,
  primary key (module_id, depends_on_module_id, dependency_type)
);

create table if not exists chlom_runtime.dail_events (
  sequence_id bigint generated always as identity primary key,
  event_id uuid not null default gen_random_uuid() unique,
  event_type text not null,
  schema_version text not null default '1.0.0',
  actor_ref text,
  actor_did text,
  agent_id text,
  source_system text not null default 'chlom',
  entity_type text not null,
  entity_id text not null,
  entity_version text,
  correlation_id text,
  causation_id text,
  authority_basis text,
  approval_id text,
  visibility_class text not null default 'internal' check (visibility_class in ('public','internal','confidential','restricted','sealed')),
  payload jsonb not null default '{}'::jsonb,
  payload_sha256 text not null,
  previous_event_hash text,
  event_hash text not null unique,
  chain_anchor_state text not null default 'unanchored' check (chain_anchor_state in ('unanchored','queued','anchored_testnet','anchored_production','failed','not_applicable')),
  signature_ref text,
  created_at timestamptz not null default now()
);

create index if not exists idx_chlom_dail_entity on chlom_runtime.dail_events(entity_type, entity_id, sequence_id desc);
create index if not exists idx_chlom_dail_correlation on chlom_runtime.dail_events(correlation_id) where correlation_id is not null;
create index if not exists idx_chlom_dail_agent on chlom_runtime.dail_events(agent_id, sequence_id desc) where agent_id is not null;

create or replace function chlom_runtime.append_dail_event(
  p_event_type text,
  p_entity_type text,
  p_entity_id text,
  p_payload jsonb default '{}'::jsonb,
  p_actor_ref text default null,
  p_actor_did text default null,
  p_agent_id text default null,
  p_entity_version text default null,
  p_correlation_id text default null,
  p_causation_id text default null,
  p_authority_basis text default null,
  p_approval_id text default null,
  p_visibility_class text default 'internal'
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, chlom_runtime
as $$
declare
  v_event_id uuid := gen_random_uuid();
  v_prev text;
  v_payload_sha text;
  v_event_hash text;
  v_created timestamptz := clock_timestamp();
begin
  perform pg_advisory_xact_lock(hashtext('chlom_runtime.dail.global.v1'));
  select event_hash into v_prev from chlom_runtime.dail_events order by sequence_id desc limit 1;
  v_payload_sha := encode(extensions.digest(convert_to(coalesce(p_payload,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  v_event_hash := encode(extensions.digest(convert_to(
    coalesce(v_prev,'GENESIS') || '|' || v_event_id::text || '|' || p_event_type || '|' ||
    p_entity_type || '|' || p_entity_id || '|' || coalesce(p_entity_version,'') || '|' ||
    coalesce(p_actor_did,p_actor_ref,'') || '|' || v_payload_sha || '|' || v_created::text,
    'UTF8'),'sha256'),'hex');
  insert into chlom_runtime.dail_events(
    event_id,event_type,actor_ref,actor_did,agent_id,entity_type,entity_id,entity_version,
    correlation_id,causation_id,authority_basis,approval_id,visibility_class,payload,payload_sha256,
    previous_event_hash,event_hash,created_at
  ) values (
    v_event_id,p_event_type,p_actor_ref,p_actor_did,p_agent_id,p_entity_type,p_entity_id,p_entity_version,
    p_correlation_id,p_causation_id,p_authority_basis,p_approval_id,p_visibility_class,coalesce(p_payload,'{}'::jsonb),v_payload_sha,
    v_prev,v_event_hash,v_created
  );
  return jsonb_build_object('event_id',v_event_id,'event_hash',v_event_hash,'previous_event_hash',v_prev,'created_at',v_created);
end $$;

revoke all on function chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text) from public;
grant execute on function chlom_runtime.append_dail_event(text,text,text,jsonb,text,text,text,text,text,text,text,text,text) to service_role;

create table if not exists chlom_identity.public_identity_records (
  public_id text primary key check (public_id ~ '^ctid_[0-9a-f]{32}$'),
  subject_id text not null unique references chlom_identity.subjects(subject_id) on delete restrict,
  did_uri text not null unique check (did_uri ~ '^did:chlom:ctid_[0-9a-f]{32}$'),
  display_name text,
  resolver_state text not null default 'identifier_active_key_pending' check (resolver_state in ('identifier_active_key_pending','active','suspended','revoked','superseded')),
  public_metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists chlom_identity.key_registry (
  key_id text primary key,
  subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
  public_id text not null references chlom_identity.public_identity_records(public_id) on delete restrict,
  purpose text not null default 'authentication',
  algorithm text not null check (algorithm in ('Ed25519','P-256','secp256k1','RSA-PSS')),
  public_jwk jsonb not null,
  private_key_secret_name text not null,
  key_state text not null default 'active' check (key_state in ('active','rotated','revoked','compromised','destroyed')),
  created_at timestamptz not null default now(),
  rotated_at timestamptz,
  revoked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create unique index if not exists idx_chlom_identity_active_key_per_purpose
on chlom_identity.key_registry(subject_id,purpose)
where key_state='active';

create or replace function chlom_identity.ensure_public_identity(
  p_subject_id text,
  p_display_name text default null,
  p_public_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, extensions, chlom_identity
as $$
declare
  v_public_id text;
  v_did text;
  v_row chlom_identity.public_identity_records%rowtype;
begin
  if not exists(select 1 from chlom_identity.subjects where subject_id=p_subject_id) then
    raise exception 'unknown_subject';
  end if;
  select * into v_row from chlom_identity.public_identity_records where subject_id=p_subject_id;
  if found then
    return jsonb_build_object('public_id',v_row.public_id,'did_uri',v_row.did_uri,'resolver_state',v_row.resolver_state);
  end if;
  loop
    v_public_id := 'ctid_' || replace(gen_random_uuid()::text,'-','');
    exit when not exists(select 1 from chlom_identity.public_identity_records where public_id=v_public_id);
  end loop;
  v_did := 'did:chlom:' || v_public_id;
  insert into chlom_identity.public_identity_records(public_id,subject_id,did_uri,display_name,public_metadata)
  values(v_public_id,p_subject_id,v_did,p_display_name,coalesce(p_public_metadata,'{}'::jsonb));
  return jsonb_build_object('public_id',v_public_id,'did_uri',v_did,'resolver_state','identifier_active_key_pending');
end $$;

revoke all on function chlom_identity.ensure_public_identity(text,text,jsonb) from public;
grant execute on function chlom_identity.ensure_public_identity(text,text,jsonb) to service_role;

create or replace function public.chlom_resolve_public_identity(p_public_id text)
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, chlom_identity
as $$
  select case when r.public_id is null then null else jsonb_build_object(
    'public_id', r.public_id,
    'did', r.did_uri,
    'display_name', r.display_name,
    'state', r.resolver_state,
    'public_keys', coalesce((
      select jsonb_agg(jsonb_build_object(
        'key_id', k.key_id,
        'purpose', k.purpose,
        'algorithm', k.algorithm,
        'public_jwk', k.public_jwk,
        'state', k.key_state
      ) order by k.created_at)
      from chlom_identity.key_registry k
      where k.public_id=r.public_id and k.key_state in ('active','rotated')
    ), '[]'::jsonb),
    'metadata', r.public_metadata
  ) end
  from chlom_identity.public_identity_records r
  where r.public_id=p_public_id and r.resolver_state in ('identifier_active_key_pending','active','suspended');
$$;

grant execute on function public.chlom_resolve_public_identity(text) to anon, authenticated, service_role;

create or replace view public.ct_public_identity_directory as
select public_id, did_uri as did, display_name, resolver_state as state, public_metadata as metadata
from chlom_identity.public_identity_records
where resolver_state in ('identifier_active_key_pending','active','suspended');

grant select on public.ct_public_identity_directory to anon, authenticated, service_role;

create or replace function public.chlom_store_key_secret(
  p_secret_name text,
  p_secret_value text,
  p_description text default null
) returns uuid
language plpgsql
security definer
set search_path = pg_catalog, vault
as $$
declare
  v_id uuid;
begin
  if p_secret_name is null or p_secret_name !~ '^[A-Z0-9_\-\.]{8,128}$' then
    raise exception 'invalid_secret_name';
  end if;
  select id into v_id from vault.secrets where name=p_secret_name;
  if v_id is null then
    select vault.create_secret(p_secret_value,p_secret_name,p_description) into v_id;
  else
    perform vault.update_secret(v_id,p_secret_value,p_secret_name,p_description);
  end if;
  return v_id;
end $$;

revoke all on function public.chlom_store_key_secret(text,text,text) from public, anon, authenticated;
grant execute on function public.chlom_store_key_secret(text,text,text) to service_role;

create or replace function public.chlom_register_public_key(
  p_public_id text,
  p_key_id text,
  p_algorithm text,
  p_public_jwk jsonb,
  p_private_secret_name text,
  p_purpose text default 'authentication'
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, chlom_identity
as $$
declare
  v_subject_id text;
begin
  select subject_id into v_subject_id from chlom_identity.public_identity_records where public_id=p_public_id;
  if v_subject_id is null then raise exception 'unknown_public_id'; end if;
  if p_private_secret_name is null or p_private_secret_name ~* '(BEGIN|PRIVATE KEY|\{|\})' then
    raise exception 'private_key_value_not_allowed_use_vault_reference';
  end if;
  update chlom_identity.key_registry set key_state='rotated', rotated_at=now()
  where subject_id=v_subject_id and purpose=p_purpose and key_state='active';
  insert into chlom_identity.key_registry(key_id,subject_id,public_id,purpose,algorithm,public_jwk,private_key_secret_name)
  values(p_key_id,v_subject_id,p_public_id,p_purpose,p_algorithm,p_public_jwk,p_private_secret_name);
  update chlom_identity.public_identity_records set resolver_state='active', updated_at=now() where public_id=p_public_id;
  return jsonb_build_object('public_id',p_public_id,'key_id',p_key_id,'state','active');
end $$;

revoke all on function public.chlom_register_public_key(text,text,text,jsonb,text,text) from public, anon, authenticated;
grant execute on function public.chlom_register_public_key(text,text,text,jsonb,text,text) to service_role;

create table if not exists chlom_runtime.backup_manifests (
  backup_id uuid primary key default gen_random_uuid(),
  backup_class text not null,
  source_system text not null,
  destination_system text not null,
  destination_ref text,
  encryption_profile text not null,
  secret_reference text,
  content_sha256 text,
  manifest_sha256 text,
  backup_state text not null default 'planned' check (backup_state in ('planned','created','verified','failed','superseded')),
  contains_secrets boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  verified_at timestamptz
);

insert into chlom_runtime.modules(module_id,canonical_name,module_class,semantic_version,lifecycle_state,authority_ceiling,self_healing_class,public_contract,mcp_enabled,api_enabled,metadata)
values
('ct.chlom.kernel','CHLOM Kernel','kernel','0.1.0','prototype','D2','rollback_capable','{"role":"metaprotocol runtime router"}',true,true,'{}'),
('ct.chlom.identity','Identity / DID / Public ID','identity','0.1.0','prototype','D2','rollback_capable','{"did_method":"did:chlom","public_id_prefix":"ctid_"}',true,true,'{}'),
('ct.chlom.fingerprint','Fingerprint & Claims','fingerprint','0.1.0','test','D2','deterministic_repair','{"primary":"sha-256"}',true,true,'{}'),
('ct.chlom.rights','Rights Graph','rights_graph','0.1.0','specified','D3','human_reserved','{}',false,false,'{}'),
('ct.chlom.dla','Dynamic Licensing Asset','dla','0.1.0','specified','D3','human_reserved','{}',false,false,'{}'),
('ct.chlom.dail','Decentralized Autonomous Information Ledger','dail','0.1.0','prototype','D2','rollback_capable','{"storage":"append-only hash chain"}',true,true,'{}'),
('ct.chlom.lex','Licensing Exchange','lex','0.1.0','specified','D3','human_reserved','{}',false,false,'{}'),
('ct.chlom.disputes','Disputes / Arbitration / Remedies','dispute','0.1.0','specified','D3','human_reserved','{}',false,false,'{"historical_alias_note":"DAL meanings preserved in terminology lineage; not reused as canonical current machine acronym"}'),
('ct.chlom.ace','Adaptive Compliance Engine','ace','0.1.0','specified','D2','quorum_required','{}',false,false,'{}'),
('ct.chlom.aie','Anomaly Intelligence Engine','aie','0.1.0','specified','D2','quorum_required','{}',false,false,'{}'),
('ct.chlom.zkx','Zero-Knowledge Orchestration Layer','zkx','0.1.0','specified','D2','quorum_required','{}',false,false,'{}'),
('ct.chlom.oracle-fabric','Oracle Fabric','oracle','0.1.0','specified','D2','quorum_required','{}',false,false,'{}'),
('ct.chlom.agent-fabric','Agent Fabric','agent_fabric','0.1.0','prototype','D2','rollback_capable','{}',true,true,'{}'),
('ct.chlom.chain-adapters','Chain Adapter Fabric','chain_adapter','0.1.0','specified','D2','quorum_required','{}',false,false,'{}'),
('ct.chlom.api-mcp','API / MCP Surface','api_mcp','0.1.0','prototype','D2','rollback_capable','{}',true,true,'{}'),
('ct.chlom.observability','Observability / Self-Healing','observability','0.1.0','specified','D2','rollback_capable','{}',false,false,'{}')
on conflict(module_id) do update set canonical_name=excluded.canonical_name,module_class=excluded.module_class,semantic_version=excluded.semantic_version,lifecycle_state=excluded.lifecycle_state,authority_ceiling=excluded.authority_ceiling,self_healing_class=excluded.self_healing_class,public_contract=excluded.public_contract,mcp_enabled=excluded.mcp_enabled,api_enabled=excluded.api_enabled,metadata=chlom_runtime.modules.metadata||excluded.metadata,updated_at=now();

insert into chlom_identity.subjects(subject_id,subject_kind,canonical_name,source_ref,authority_state,visibility,metadata)
values('ct.secret.chlom.fallback-vault-password','other','CHLOM Fallback Vault Secret Reference','founder-directive-2026-08-20','institutional','machine_only','{"secret_value_never_public":true}'::jsonb)
on conflict(subject_id) do nothing;

with fp as (
  select chlom_identity.fingerprint_text('vault-secret-reference:CHLOM_FALLBACK_VAULT_PASSWORD:v1') as fingerprint_id
)
insert into chlom_identity.fingerprints(fingerprint_id,subject_id,profile_id,algorithm,digest_hex,source_ref,fingerprint_state)
select fingerprint_id,'ct.secret.chlom.fallback-vault-password','ct.profile.secret-reference.v1','sha-256',split_part(fingerprint_id,':',4),'founder-directive-2026-08-20','active'
from fp
on conflict(fingerprint_id) do nothing;

insert into integration_control.services(service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,write_gate,monthly_request_limit,timezone,metadata)
values('chlom_core','CHLOM Metaprotocol Control Plane','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/chlom-api-control','https://crown-thrive.mintlify.io/chlom/overview','supabase_jwt','supabase_auth','configured','configured',false,null,'UTC','{"framework_id":"ct.framework.chlom","platform_id":"ct.platform.chlom","private_runtime":true,"metaprotocol":true}'::jsonb)
on conflict(service_id) do update set display_name=excluded.display_name,base_url=excluded.base_url,docs_url=excluded.docs_url,auth_scheme=excluded.auth_scheme,credential_ref=excluded.credential_ref,credential_state=excluded.credential_state,integration_state=excluded.integration_state,metadata=integration_control.services.metadata||excluded.metadata,updated_at=now();

insert into integration_control.runtime_variable_registry(variable_key,service_id,value_class,public_value,secret_reference,canonical_source,recovery_source,runtime_consumers,notes)
values('CHLOM_FALLBACK_VAULT_PASSWORD','chlom_core','secret_reference',null,'CHLOM_FALLBACK_VAULT_PASSWORD','supabase_vault','google_drive_encrypted_fallback_vault','["chlom-backup-worker","chlom-recovery-agent"]'::jsonb,'Secret value intentionally absent from registry; resolve only server-side through Vault.')
on conflict(variable_key) do update set service_id=excluded.service_id,value_class=excluded.value_class,public_value=null,secret_reference=excluded.secret_reference,canonical_source=excluded.canonical_source,recovery_source=excluded.recovery_source,runtime_consumers=excluded.runtime_consumers,notes=excluded.notes,updated_at=now();

insert into integration_control.credential_continuity_registry(credential_id,service_id,credential_class,provider_system,provider_location_note,primary_vault_name,recovery_vault_name,primary_present,recovery_present,fingerprint_sha256,runtime_consumers,continuity_state,recovery_note,last_verified_at)
select 'cred.chlom.fallback-vault-password','chlom_core','archive_recovery_secret','supabase_vault','Encrypted Supabase Vault secret; value must never be placed in public docs, client code, logs, or public identifiers.','CHLOM_FALLBACK_VAULT_PASSWORD','google_drive_chlom_fallback_vault',true,false,split_part(chlom_identity.fingerprint_text('vault-secret-reference:CHLOM_FALLBACK_VAULT_PASSWORD:v1'),':',4),'["chlom-backup-worker","chlom-recovery-agent"]'::jsonb,'verified_primary_only','Google Drive encrypted fallback archive still requires independently verified creation/readback.',now()
on conflict(credential_id) do update set primary_vault_name=excluded.primary_vault_name,recovery_vault_name=excluded.recovery_vault_name,primary_present=excluded.primary_present,fingerprint_sha256=excluded.fingerprint_sha256,runtime_consumers=excluded.runtime_consumers,continuity_state=excluded.continuity_state,recovery_note=excluded.recovery_note,last_verified_at=excluded.last_verified_at,updated_at=now();

insert into integration_control.mcp_tools(tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval,input_schema,output_schema,notes)
values
('chlom.identity.resolve','chlom_core','identity.resolve','D0',true,false,'{"type":"object","properties":{"public_id":{"type":"string"}},"required":["public_id"],"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Resolve a CHLOM public identity to its DID and public verification keys. Never returns private key material.'),
('chlom.module.list','chlom_core','module.list','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'List canonical CHLOM modules and lifecycle states.'),
('chlom.dail.query','chlom_core','dail.query','D0',true,false,'{"type":"object","properties":{"entity_type":{"type":"string"},"entity_id":{"type":"string"},"limit":{"type":"integer","minimum":1,"maximum":100}},"required":["entity_type","entity_id"],"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Read DAIL lineage for one entity. Public-safe outputs only when caller is permitted.'),
('chlom.dail.append','chlom_core','dail.append','D2',true,false,'{"type":"object","properties":{"event_type":{"type":"string"},"entity_type":{"type":"string"},"entity_id":{"type":"string"},"entity_version":{"type":["string","null"]},"visibility_class":{"type":"string","enum":["public","internal","confidential","restricted","sealed"]},"payload":{"type":"object"}},"required":["event_type","entity_type","entity_id","payload"],"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Append-only DAIL event. Requires authenticated CHLOM administrative/service authority; cannot rewrite history.'),
('chlom.identity.ensure_public_id','chlom_core','identity.ensure_public_id','D2',true,true,'{"type":"object","properties":{"subject_id":{"type":"string"},"display_name":{"type":["string","null"]},"metadata":{"type":"object"}},"required":["subject_id"],"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Create an opaque CHLOM public identifier for an existing governed subject. Human approval remains required for publishing human identities.'),
('chlom.key.generate','chlom_core','key.generate','D2',true,true,'{"type":"object","properties":{"public_id":{"type":"string"},"purpose":{"type":"string"}},"required":["public_id"],"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Generate hosted asymmetric signing key material server-side; store private key only in Vault and expose public key through resolver.'),
('chlom.backup.status','chlom_core','backup.status','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Return fallback-vault manifest and continuity status without exposing recovery secrets.')
on conflict(tool_name) do update set service_id=excluded.service_id,operation_key=excluded.operation_key,risk_class=excluded.risk_class,enabled=excluded.enabled,requires_human_approval=excluded.requires_human_approval,input_schema=excluded.input_schema,output_schema=excluded.output_schema,notes=excluded.notes,updated_at=now();

insert into chlom_runtime.backup_manifests(backup_class,source_system,destination_system,destination_ref,encryption_profile,secret_reference,backup_state,contains_secrets,metadata)
values('institutional-fallback-vault','supabase','google_drive','pending','password-encrypted-archive-v1','CHLOM_FALLBACK_VAULT_PASSWORD','planned',true,'{"rule":"archive contents encrypted before Drive upload; Drive stores ciphertext only; password never written into archive or Drive metadata"}'::jsonb);

select chlom_runtime.append_dail_event(
  'chlom.control_plane.bootstrap',
  'framework',
  'ct.framework.chlom',
  jsonb_build_object('modules_seeded',true,'mcp_tools_registered',true,'public_identity_resolver',true,'fallback_secret_reference_registered',true,'private_value_exposed',false),
  'founder-directive-2026-08-20',null,'ct.agent.founder-orchestrator','0.1.0',null,null,'D2 founder authorized',null,'internal'
);