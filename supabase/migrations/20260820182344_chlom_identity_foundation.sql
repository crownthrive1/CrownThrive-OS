create schema if not exists chlom_identity;

revoke all on schema chlom_identity from public;
revoke all on schema chlom_identity from anon;
revoke all on schema chlom_identity from authenticated;
grant usage on schema chlom_identity to service_role;

create table if not exists chlom_identity.subjects (
    subject_id text primary key,
    subject_kind text not null check (subject_kind in (
        'actor','organization','platform','framework','domain','asset','work','license',
        'agent','paper','schema','override','source_record','event','other'
    )),
    canonical_name text not null,
    source_ref text,
    authority_state text not null check (authority_state in (
        'source_record','institutional','research_candidate','unresolved','historical'
    )),
    visibility text not null default 'restricted' check (visibility in (
        'public','internal','restricted','strategic','machine_only'
    )),
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists chlom_identity.fingerprints (
    fingerprint_id text primary key check (
        fingerprint_id ~ '^ctfp:v1:sha256:[0-9a-f]{64}$'
    ),
    subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    profile_id text not null default 'ct-json-c14n-v1',
    algorithm text not null default 'sha-256' check (algorithm = 'sha-256'),
    digest_hex text not null check (digest_hex ~ '^[0-9a-f]{64}$'),
    source_ref text,
    fingerprint_state text not null default 'active' check (fingerprint_state in (
        'active','superseded','revoked','historical'
    )),
    created_at timestamptz not null default now(),
    unique(subject_id, profile_id, algorithm, digest_hex)
);

create table if not exists chlom_identity.did_bindings (
    binding_id text primary key,
    subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    did_uri text not null unique check (did_uri like 'did:%'),
    did_method text not null,
    controller_subject_id text references chlom_identity.subjects(subject_id) on delete restrict,
    verification_method_ref text,
    key_ref text,
    proof_suite text,
    binding_state text not null default 'candidate' check (binding_state in (
        'candidate','test','active','suspended','revoked','superseded'
    )),
    source_ref text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (key_ref is null or key_ref !~* '(private|secret|seed|mnemonic)')
);

create table if not exists chlom_identity.credential_records (
    credential_id text primary key,
    subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    issuer_subject_id text references chlom_identity.subjects(subject_id) on delete restrict,
    credential_type text not null,
    credential_hash text check (credential_hash is null or credential_hash ~ '^[0-9a-f]{64}$'),
    credential_uri text,
    credential_state text not null default 'candidate' check (credential_state in (
        'candidate','issued','suspended','revoked','expired','superseded'
    )),
    valid_from timestamptz,
    valid_until timestamptz,
    source_ref text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists chlom_identity.attestations (
    attestation_id text primary key,
    subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    signer_subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    signer_name text not null check (length(trim(signer_name)) > 0),
    attestation_kind text not null check (attestation_kind in (
        'founder_override','owner_attestation','operator_attestation','cryptographic_attestation','other'
    )),
    signature_type text not null check (signature_type in (
        'typed_name_attestation','cryptographic_signature','vc_data_integrity','did_proof'
    )),
    statement_fingerprint_id text not null references chlom_identity.fingerprints(fingerprint_id) on delete restrict,
    signer_did text,
    public_key_ref text,
    signature_algorithm text,
    signature_value text,
    authority_scope text not null,
    source_ref text not null,
    attestation_state text not null default 'active' check (attestation_state in (
        'active','superseded','revoked','historical'
    )),
    signed_at timestamptz not null,
    metadata jsonb not null default '{}'::jsonb,
    check (
        signature_type = 'typed_name_attestation'
        or (
            signature_algorithm is not null
            and signature_value is not null
            and (signer_did is not null or public_key_ref is not null)
        )
    ),
    check (public_key_ref is null or public_key_ref !~* '(private|secret|seed|mnemonic)')
);

create table if not exists chlom_identity.subject_relationships (
    relationship_id text primary key,
    source_subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    relationship_type text not null,
    target_subject_id text not null references chlom_identity.subjects(subject_id) on delete restrict,
    relationship_state text not null default 'active' check (relationship_state in (
        'candidate','active','historical','superseded','revoked'
    )),
    evidence_ref text,
    created_at timestamptz not null default now(),
    unique(source_subject_id, relationship_type, target_subject_id, relationship_state)
);

create table if not exists chlom_identity.proof_anchors (
    anchor_id text primary key,
    fingerprint_id text not null references chlom_identity.fingerprints(fingerprint_id) on delete restrict,
    anchor_type text not null check (anchor_type in (
        'transparency_log','notary','blockchain','oracle','other'
    )),
    network text,
    external_ref text,
    anchor_state text not null default 'candidate' check (anchor_state in (
        'candidate','submitted','confirmed','failed','revoked','superseded'
    )),
    anchored_at timestamptz,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create or replace function chlom_identity.fingerprint_text(p_canonical_text text)
returns text
language sql
immutable
strict
as $$
  select 'ctfp:v1:sha256:' ||
         encode(extensions.digest(convert_to(p_canonical_text, 'UTF8'), 'sha256'), 'hex')
$$;

revoke all on function chlom_identity.fingerprint_text(text) from public;
revoke all on function chlom_identity.fingerprint_text(text) from anon;
revoke all on function chlom_identity.fingerprint_text(text) from authenticated;
grant execute on function chlom_identity.fingerprint_text(text) to service_role;

alter table chlom_identity.subjects enable row level security;
alter table chlom_identity.fingerprints enable row level security;
alter table chlom_identity.did_bindings enable row level security;
alter table chlom_identity.credential_records enable row level security;
alter table chlom_identity.attestations enable row level security;
alter table chlom_identity.subject_relationships enable row level security;
alter table chlom_identity.proof_anchors enable row level security;

alter table chlom_identity.subjects force row level security;
alter table chlom_identity.fingerprints force row level security;
alter table chlom_identity.did_bindings force row level security;
alter table chlom_identity.credential_records force row level security;
alter table chlom_identity.attestations force row level security;
alter table chlom_identity.subject_relationships force row level security;
alter table chlom_identity.proof_anchors force row level security;

revoke all on all tables in schema chlom_identity from public;
revoke all on all tables in schema chlom_identity from anon;
revoke all on all tables in schema chlom_identity from authenticated;
grant select, insert, update, delete on all tables in schema chlom_identity to service_role;

alter default privileges in schema chlom_identity revoke all on tables from public;
alter default privileges in schema chlom_identity revoke all on tables from anon;
alter default privileges in schema chlom_identity revoke all on tables from authenticated;
alter default privileges in schema chlom_identity grant select, insert, update, delete on tables to service_role;

drop policy if exists chlom_identity_subjects_service_role_all on chlom_identity.subjects;
create policy chlom_identity_subjects_service_role_all
on chlom_identity.subjects for all to service_role using (true) with check (true);

drop policy if exists chlom_identity_fingerprints_service_role_all on chlom_identity.fingerprints;
create policy chlom_identity_fingerprints_service_role_all
on chlom_identity.fingerprints for all to service_role using (true) with check (true);

drop policy if exists chlom_identity_did_bindings_service_role_all on chlom_identity.did_bindings;
create policy chlom_identity_did_bindings_service_role_all
on chlom_identity.did_bindings for all to service_role using (true) with check (true);

drop policy if exists chlom_identity_credential_records_service_role_all on chlom_identity.credential_records;
create policy chlom_identity_credential_records_service_role_all
on chlom_identity.credential_records for all to service_role using (true) with check (true);

drop policy if exists chlom_identity_attestations_service_role_all on chlom_identity.attestations;
create policy chlom_identity_attestations_service_role_all
on chlom_identity.attestations for all to service_role using (true) with check (true);

drop policy if exists chlom_identity_subject_relationships_service_role_all on chlom_identity.subject_relationships;
create policy chlom_identity_subject_relationships_service_role_all
on chlom_identity.subject_relationships for all to service_role using (true) with check (true);

drop policy if exists chlom_identity_proof_anchors_service_role_all on chlom_identity.proof_anchors;
create policy chlom_identity_proof_anchors_service_role_all
on chlom_identity.proof_anchors for all to service_role using (true) with check (true);