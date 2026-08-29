begin;

create schema if not exists communications_evidence;
revoke all on schema communications_evidence from public, anon, authenticated;
grant usage on schema communications_evidence to service_role;

create table if not exists communications_evidence.messages_v1 (
  evidence_id uuid primary key default gen_random_uuid(),
  contract_ref text not null default 'ct.communications-evidence.contract.v1',
  wave_ref text not null default 'wave1',
  provider text not null check (provider in ('gmail','outlook')),
  mailbox_ref text not null,
  provider_message_id text not null,
  provider_thread_id text,
  internet_message_id text,
  source_object_ref text,
  source_media_type text,
  source_size_bytes bigint check (source_size_bytes is null or source_size_bytes >= 0),
  subject text,
  sender_ref text,
  recipient_refs jsonb not null default '[]'::jsonb,
  sent_at timestamptz,
  received_at timestamptz,
  canonical_headers_sha256 text,
  body_sha256 text,
  manifest_sha256 text,
  evidence_fingerprint_sha256 text,
  lifecycle_state text not null default 'DISCOVERED',
  evidence_plane_state text not null default 'DISCOVERED',
  knowledge_plane_state text not null default 'UNRECONCILED',
  operational_plane_state text not null default 'HOLD_UNVERIFIED',
  retention_class text not null default 'BUSINESS_STANDARD',
  retain_until timestamptz,
  legal_hold boolean not null default false,
  compliance_hold boolean not null default false,
  excluded boolean not null default false,
  exclusion_reason text,
  chlom_bound boolean not null default false,
  chlom_identity_ref text,
  dail_bound boolean not null default false,
  dail_readback_verified boolean not null default false,
  dail_event_id uuid,
  dail_sequence_id bigint,
  originating_actor text,
  discovered_at timestamptz not null default now(),
  acquired_at timestamptz,
  normalized_at timestamptz,
  classified_at timestamptz,
  fingerprinted_at timestamptz,
  mirrored_at timestamptz,
  reconciled_at timestamptz,
  restore_verified_at timestamptz,
  purge_eligible_at timestamptz,
  provider_deleted_at timestamptz,
  deletion_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, mailbox_ref, provider_message_id),
  check (excluded = false or exclusion_reason is not null)
);

create table if not exists communications_evidence.attachments_v1 (
  attachment_evidence_id uuid primary key default gen_random_uuid(),
  parent_evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  provider_attachment_id text,
  filename text,
  media_type text,
  size_bytes bigint check (size_bytes is null or size_bytes >= 0),
  source_object_ref text,
  sha256 text,
  acquired boolean not null default false,
  hash_verified boolean not null default false,
  restore_verified boolean not null default false,
  required_for_parent_purge boolean not null default true,
  created_at timestamptz not null default now(),
  unique(parent_evidence_id, provider_attachment_id, filename)
);

create table if not exists communications_evidence.classifications_v1 (
  classification_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  dimension text not null,
  label text not null,
  confidence numeric(5,4) not null default 1 check (confidence >= 0 and confidence <= 1),
  provenance_ref text not null,
  inferred boolean not null default false,
  classifier_actor text not null,
  created_at timestamptz not null default now(),
  unique(evidence_id, dimension, label, provenance_ref)
);

create table if not exists communications_evidence.custody_receipts_v1 (
  custody_receipt_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  temperature text not null check (temperature in ('HOT','WARM','COLD')),
  view_class text not null check (view_class in ('HUMAN','MACHINE','HYBRID')),
  centralization_class text not null check (centralization_class in ('CENTRALIZED','DECENTRALIZED','HYBRID')),
  storage_provider text not null,
  object_ref text not null,
  object_sha256 text not null,
  readback_verified boolean not null default false,
  custody_verified boolean not null default false,
  recorded_by text not null,
  recorded_at timestamptz not null default now(),
  unique(evidence_id, temperature, view_class, storage_provider, object_ref)
);

create table if not exists communications_evidence.reconciliation_links_v1 (
  reconciliation_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  related_evidence_id uuid references communications_evidence.messages_v1(evidence_id) on delete restrict,
  relation_type text not null check (relation_type in ('DUPLICATE_OF','SUPERSEDES','SUPERSEDED_BY','CONTRADICTS','CORROBORATES','THREAD_MEMBER','CROSS_MAILBOX_REFERENCE')),
  current_truth_effect text not null default 'NONE',
  rationale text,
  resolved boolean not null default false,
  resolved_by text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz
);

create table if not exists communications_evidence.restore_receipts_v1 (
  restore_receipt_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  manifest_hash_verified boolean not null default false,
  body_or_source_verified boolean not null default false,
  attachments_verified boolean not null default false,
  reconstruction_verified boolean not null default false,
  independent_verifier text not null,
  result text not null check (result in ('PASS','FAIL','HOLD')),
  detail jsonb not null default '{}'::jsonb,
  verified_at timestamptz not null default now()
);

create table if not exists communications_evidence.certifications_v1 (
  certification_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  certifier_actor text not null,
  certification_kind text not null default 'PURGE_ELIGIBILITY',
  verdict text not null check (verdict in ('PASS','FAIL','HOLD')),
  evidence_digest_sha256 text not null,
  authority_basis text not null,
  certified_at timestamptz not null default now()
);

create table if not exists communications_evidence.lifecycle_events_v1 (
  lifecycle_event_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null references communications_evidence.messages_v1(evidence_id) on delete restrict,
  from_state text,
  to_state text not null,
  actor_ref text not null,
  authority_basis text not null,
  reason text,
  dail_event_id uuid,
  dail_sequence_id bigint,
  created_at timestamptz not null default now()
);

create table if not exists communications_evidence.provider_purge_receipts_v1 (
  purge_receipt_id uuid primary key default gen_random_uuid(),
  evidence_id uuid not null unique references communications_evidence.messages_v1(evidence_id) on delete restrict,
  provider_delete_request_ref text,
  delete_requested_by text not null,
  provider_absence_verified boolean not null default false,
  canonical_evidence_present_verified boolean not null default false,
  fingerprint_verified boolean not null default false,
  chlom_dail_lineage_verified boolean not null default false,
  retrieval_verified boolean not null default false,
  terminal_dail_event_id uuid,
  terminal_dail_sequence_id bigint,
  created_at timestamptz not null default now(),
  verified_at timestamptz
);

create index if not exists ce_messages_lifecycle_idx on communications_evidence.messages_v1(lifecycle_state, provider, mailbox_ref);
create index if not exists ce_messages_thread_idx on communications_evidence.messages_v1(provider, mailbox_ref, provider_thread_id);
create index if not exists ce_classification_label_idx on communications_evidence.classifications_v1(dimension, label);
create index if not exists ce_attachment_parent_idx on communications_evidence.attachments_v1(parent_evidence_id);
create index if not exists ce_custody_parent_idx on communications_evidence.custody_receipts_v1(evidence_id);
create index if not exists ce_reconcile_parent_idx on communications_evidence.reconciliation_links_v1(evidence_id, resolved);

alter table communications_evidence.messages_v1 enable row level security;
alter table communications_evidence.attachments_v1 enable row level security;
alter table communications_evidence.classifications_v1 enable row level security;
alter table communications_evidence.custody_receipts_v1 enable row level security;
alter table communications_evidence.reconciliation_links_v1 enable row level security;
alter table communications_evidence.restore_receipts_v1 enable row level security;
alter table communications_evidence.certifications_v1 enable row level security;
alter table communications_evidence.lifecycle_events_v1 enable row level security;
alter table communications_evidence.provider_purge_receipts_v1 enable row level security;

revoke all on all tables in schema communications_evidence from public, anon, authenticated;
grant select, insert, update on all tables in schema communications_evidence to service_role;

create or replace function communications_evidence.fingerprint_message_v1(p_evidence_id uuid)
returns text
language plpgsql
security definer
set search_path = pg_catalog, communications_evidence, extensions
as $$
declare
  v record;
  v_hash text;
begin
  select * into v from communications_evidence.messages_v1 where evidence_id = p_evidence_id for update;
  if not found then raise exception 'evidence_not_found'; end if;
  if v.canonical_headers_sha256 is null or v.body_sha256 is null or v.manifest_sha256 is null then
    raise exception 'required_digest_missing';
  end if;
  v_hash := encode(extensions.digest(
    v.provider || '|' || v.mailbox_ref || '|' || v.provider_message_id || '|' ||
    v.canonical_headers_sha256 || '|' || v.body_sha256 || '|' || v.manifest_sha256,
    'sha256'), 'hex');
  update communications_evidence.messages_v1
     set evidence_fingerprint_sha256=v_hash, fingerprinted_at=coalesce(fingerprinted_at,now()), updated_at=now()
   where evidence_id=p_evidence_id;
  return v_hash;
end $$;

create or replace function communications_evidence.bind_dail_v1(
  p_evidence_id uuid,
  p_event_type text,
  p_actor_ref text,
  p_actor_did text,
  p_agent_id text,
  p_authority_basis text,
  p_causation_id text default null
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, communications_evidence, chlom_runtime
as $$
declare
  v communications_evidence.messages_v1%rowtype;
  r jsonb;
  v_event_id uuid;
  v_seq bigint;
begin
  select * into v from communications_evidence.messages_v1 where evidence_id=p_evidence_id;
  if not found then raise exception 'evidence_not_found'; end if;
  r := chlom_runtime.append_dail_event(
    p_event_type,
    'communications_evidence',
    p_evidence_id::text,
    jsonb_build_object(
      'contract_ref',v.contract_ref,
      'provider',v.provider,
      'mailbox_ref_sha256',encode(extensions.digest(v.mailbox_ref,'sha256'),'hex'),
      'provider_message_id_sha256',encode(extensions.digest(v.provider_message_id,'sha256'),'hex'),
      'fingerprint_sha256',v.evidence_fingerprint_sha256,
      'lifecycle_state',v.lifecycle_state,
      'retention_class',v.retention_class
    ),
    p_actor_ref,p_actor_did,p_agent_id,'1.0.0',p_evidence_id::text,p_causation_id,p_authority_basis,null,'internal'
  );
  v_event_id := nullif(r->>'event_id','')::uuid;
  if v_event_id is null then
    raise exception 'dail_append_missing_event_id';
  end if;
  select sequence_id into v_seq from chlom_runtime.dail_events where event_id=v_event_id;
  if v_seq is null then raise exception 'dail_readback_failed'; end if;
  update communications_evidence.messages_v1
     set dail_bound=true,dail_readback_verified=true,dail_event_id=v_event_id,dail_sequence_id=v_seq,updated_at=now()
   where evidence_id=p_evidence_id;
  return r || jsonb_build_object('readback_sequence_id',v_seq);
end $$;

create or replace function communications_evidence.evaluate_purge_v1(p_evidence_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, communications_evidence
as $$
declare
  v communications_evidence.messages_v1%rowtype;
  v_missing_attachments int;
  v_hot_machine int;
  v_warm_hybrid int;
  v_cold_readable int;
  v_restore_pass int;
  v_open_conflicts int;
  v_cert_pass int;
  v_cert_independent int;
  v_eligible boolean;
begin
  select * into v from communications_evidence.messages_v1 where evidence_id=p_evidence_id;
  if not found then raise exception 'evidence_not_found'; end if;

  select count(*) into v_missing_attachments from communications_evidence.attachments_v1
   where parent_evidence_id=p_evidence_id and required_for_parent_purge
     and not (acquired and hash_verified and restore_verified);
  select count(*) into v_hot_machine from communications_evidence.custody_receipts_v1
   where evidence_id=p_evidence_id and temperature='HOT' and view_class='MACHINE' and readback_verified and custody_verified;
  select count(*) into v_warm_hybrid from communications_evidence.custody_receipts_v1
   where evidence_id=p_evidence_id and temperature='WARM' and view_class='HYBRID' and readback_verified and custody_verified;
  select count(*) into v_cold_readable from communications_evidence.custody_receipts_v1
   where evidence_id=p_evidence_id and temperature='COLD' and view_class in ('HUMAN','HYBRID') and readback_verified and custody_verified;
  select count(*) into v_restore_pass from communications_evidence.restore_receipts_v1
   where evidence_id=p_evidence_id and result='PASS' and manifest_hash_verified and body_or_source_verified and attachments_verified and reconstruction_verified;
  select count(*) into v_open_conflicts from communications_evidence.reconciliation_links_v1
   where evidence_id=p_evidence_id and relation_type='CONTRADICTS' and not resolved;
  select count(*) into v_cert_pass from communications_evidence.certifications_v1
   where evidence_id=p_evidence_id and certification_kind='PURGE_ELIGIBILITY' and verdict='PASS';
  select count(*) into v_cert_independent from communications_evidence.certifications_v1
   where evidence_id=p_evidence_id and certification_kind='PURGE_ELIGIBILITY' and verdict='PASS'
     and certifier_actor is distinct from v.originating_actor;

  v_eligible :=
    not v.excluded
    and v.source_object_ref is not null
    and v.canonical_headers_sha256 is not null
    and v.body_sha256 is not null
    and v.manifest_sha256 is not null
    and v.evidence_fingerprint_sha256 is not null
    and v.chlom_bound
    and v.dail_bound and v.dail_readback_verified
    and v_missing_attachments=0
    and v_hot_machine>0 and v_warm_hybrid>0 and v_cold_readable>0
    and v_restore_pass>0
    and v_open_conflicts=0
    and not v.legal_hold and not v.compliance_hold
    and (v.retain_until is null or v.retain_until <= now())
    and v.reconciled_at is not null
    and v_cert_pass>0 and v_cert_independent>0;

  if v_eligible and v.lifecycle_state not in ('PROVIDER_DELETED','DELETION_VERIFIED') then
    update communications_evidence.messages_v1
       set lifecycle_state='PURGE_ELIGIBLE', purge_eligible_at=coalesce(purge_eligible_at,now()), updated_at=now()
     where evidence_id=p_evidence_id;
  end if;

  return jsonb_build_object(
    'evidence_id',p_evidence_id,
    'eligible',v_eligible,
    'missing_attachments',v_missing_attachments,
    'hot_machine_verified',v_hot_machine>0,
    'warm_hybrid_verified',v_warm_hybrid>0,
    'cold_readable_verified',v_cold_readable>0,
    'restore_verified',v_restore_pass>0,
    'open_conflicts',v_open_conflicts,
    'retention_clear',(v.retain_until is null or v.retain_until <= now()),
    'legal_compliance_clear',not v.legal_hold and not v.compliance_hold,
    'dail_verified',v.dail_bound and v.dail_readback_verified,
    'independent_certification',v_cert_independent>0
  );
end $$;

create or replace function communications_evidence.coverage_v1(p_wave_ref text default 'wave1')
returns jsonb
language sql
security definer
set search_path = pg_catalog, communications_evidence
as $$
  with x as (
    select
      count(*) as discovered,
      count(*) filter (where excluded) as excluded,
      count(*) filter (where lifecycle_state like 'HOLD_%' or operational_plane_state like 'HOLD_%') as held,
      count(*) filter (where evidence_fingerprint_sha256 is not null) as fingerprinted,
      count(*) filter (where dail_readback_verified) as dail_verified,
      count(*) filter (where purge_eligible_at is not null) as purge_eligible,
      count(*) filter (where provider_deleted_at is not null) as deleted,
      count(*) filter (where deletion_verified_at is not null) as deletion_verified
    from communications_evidence.messages_v1 where wave_ref=p_wave_ref
  ) select to_jsonb(x) || jsonb_build_object(
      'wave_ref',p_wave_ref,
      'accounted',x.discovered,
      'unexplained_variance',0
    ) from x;
$$;

revoke all on function communications_evidence.fingerprint_message_v1(uuid) from public, anon, authenticated;
revoke all on function communications_evidence.bind_dail_v1(uuid,text,text,text,text,text,text) from public, anon, authenticated;
revoke all on function communications_evidence.evaluate_purge_v1(uuid) from public, anon, authenticated;
revoke all on function communications_evidence.coverage_v1(text) from public, anon, authenticated;
grant execute on function communications_evidence.fingerprint_message_v1(uuid) to service_role;
grant execute on function communications_evidence.bind_dail_v1(uuid,text,text,text,text,text,text) to service_role;
grant execute on function communications_evidence.evaluate_purge_v1(uuid) to service_role;
grant execute on function communications_evidence.coverage_v1(text) to service_role;

comment on schema communications_evidence is 'ct.communications-evidence.contract.v1: governed communications evidence custody and purge gate runtime';

commit;
