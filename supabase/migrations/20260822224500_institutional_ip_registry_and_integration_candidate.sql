-- CANDIDATE_NOT_APPLIED
-- Service-only institutional IP evidence and integration projection. No generic anon/authenticated policies.
begin;
create schema if not exists institutional_ip;
revoke all on schema institutional_ip from public, anon, authenticated;
grant usage on schema institutional_ip to service_role;

create table if not exists institutional_ip.assets (
 asset_id text primary key, canonical_name text not null, category text not null,
 lifecycle_state text not null, classification text not null,
 chain_of_title_state text not null default 'HOLD_UNVERIFIED',
 valuation_state text not null default 'UNVALUED_INPUT_REQUIRED',
 commercial_proof_state text not null default 'P0_HYPOTHESIS',
 public_projection jsonb not null default '{}'::jsonb,
 restricted_metadata jsonb not null default '{}'::jsonb,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists institutional_ip.invention_records (
 invention_record_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 record_version text not null, conception_state text not null, inventorship_state text not null,
 reduction_to_practice_state text not null, public_disclosure_state text not null,
 patentability_status text not null, protection_strategy text not null,
 evidence_refs jsonb not null default '[]'::jsonb, exact_digest text not null check (exact_digest ~ '^[0-9a-f]{64}$'),
 authoritative boolean not null default false, created_at timestamptz not null default now(), unique(asset_id,record_version)
);
create table if not exists institutional_ip.prior_art_searches (
 search_id text primary key, invention_record_id text not null references institutional_ip.invention_records(invention_record_id),
 search_state text not null, query_scope jsonb not null default '[]'::jsonb,
 result_refs jsonb not null default '[]'::jsonb, legal_opinion boolean not null default false,
 performed_at timestamptz, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.public_disclosures (
 disclosure_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 disclosure_date date, disclosure_type text not null, public_ref text,
 exact_digest text check (exact_digest is null or exact_digest ~ '^[0-9a-f]{64}$'),
 counsel_review_state text not null default 'PENDING', created_at timestamptz not null default now()
);
create table if not exists institutional_ip.contributors (
 contributor_id text primary key, private_identity_ref text, relationship_state text not null,
 assignment_state text not null, confidentiality_state text not null, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.title_events (
 title_event_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 event_type text not null, effective_state text not null, effective_date date,
 parties jsonb not null default '[]'::jsonb, scope jsonb not null default '[]'::jsonb,
 territory jsonb not null default '[]'::jsonb, restrictions jsonb not null default '[]'::jsonb,
 evidence_refs jsonb not null default '[]'::jsonb,
 supersedes_event_id text references institutional_ip.title_events(title_event_id),
 authoritative boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.chain_of_title_records (
 title_record_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 claimed_owner text not null, owner_basis text not null, assignment_status text not null,
 third_party_status text not null, ai_assistance_status text not null,
 public_disclosure_status text not null, rights_status text not null,
 evidence_refs jsonb not null default '[]'::jsonb, authoritative boolean not null default false,
 created_at timestamptz not null default now()
);
create table if not exists institutional_ip.third_party_materials (
 component_id text primary key, asset_id text references institutional_ip.assets(asset_id), name text not null,
 exact_version text, exact_digest text, relationship text not null, incorporation_state text not null,
 license_evidence_state text not null, notice_required boolean not null default false,
 release_block_if_unresolved boolean not null default true, evidence_refs jsonb not null default '[]'::jsonb,
 created_at timestamptz not null default now()
);
create table if not exists institutional_ip.valuation_inputs (
 valuation_input_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 input_class text not null, input_state text not null, currency text, numeric_value numeric,
 evidence_refs jsonb not null default '[]'::jsonb, private_source_ref text,
 verified_by_class text, verified_at timestamptz, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.valuation_scenarios (
 scenario_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 valuation_date date not null, currency text not null check(currency ~ '^[A-Z]{3}$'), method text not null,
 assumptions jsonb not null, method_result numeric, status text not null,
 scenario_only boolean not null default true, professional_appraisal_required boolean not null default true,
 authoritative boolean not null default false, evidence_refs jsonb not null default '[]'::jsonb,
 created_at timestamptz not null default now()
);
create table if not exists institutional_ip.supply_chain_releases (
 release_id text primary key, asset_id text references institutional_ip.assets(asset_id),
 repository text not null, source_revision text not null check(source_revision ~ '^[0-9a-f]{40}$'),
 artifact_digest text not null check(artifact_digest ~ '^[0-9a-f]{64}$'),
 spdx_digest text, cyclonedx_digest text, provenance_digest text,
 provenance_signed boolean not null default false, vulnerability_state text not null,
 release_state text not null, authoritative boolean not null default false,
 created_at timestamptz not null default now()
);
create table if not exists institutional_ip.commercial_proof_events (
 event_id text primary key, offer_id text not null, asset_id text references institutional_ip.assets(asset_id),
 evidence_type text not null, external_party boolean not null, evidence_date date not null,
 verified boolean not null default false, independent_verifier_class text, exact_evidence_ref text,
 evidence_digest text check(evidence_digest is null or evidence_digest ~ '^[0-9a-f]{64}$'),
 recognized_revenue numeric, currency text, creates_price boolean not null default false,
 creates_checkout boolean not null default false, customer_entitlement_created boolean not null default false,
 authoritative boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.evidence_links (
 evidence_link_id text primary key, subject_type text not null, subject_id text not null,
 evidence_class text not null, public_ref text, private_ref text,
 exact_digest text check(exact_digest is null or exact_digest ~ '^[0-9a-f]{64}$'),
 body_in_public_record boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.framework_factory_intakes (
 intake_id text primary key, packet_id text not null, framework_id text not null,
 source_repository text not null, source_head text not null check(source_head ~ '^[0-9a-f]{40}$'),
 artifact_digest text not null check(artifact_digest ~ '^[0-9a-f]{64}$'),
 lifecycle_state text not null, ip_classification text not null, title_state text not null,
 release_state text not null, commercial_state text not null,
 intake_state text not null default 'CANDIDATE_HOLD', authoritative boolean not null default false,
 created_at timestamptz not null default now(), unique(packet_id,source_head,artifact_digest)
);
create table if not exists institutional_ip.chlom_rights_links (
 link_id text primary key, asset_id text not null references institutional_ip.assets(asset_id),
 chlom_object_type text not null, chlom_object_id text not null, rights_decision text not null,
 decision_digest text not null check(decision_digest ~ '^[0-9a-f]{64}$'),
 decision_state text not null, rights_granted_by_this_record boolean not null default false,
 authoritative boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.thriveevergreen_gate_receipts (
 gate_receipt_id text primary key, offer_id text not null, asset_id text not null references institutional_ip.assets(asset_id),
 exact_offer_digest text not null check(exact_offer_digest ~ '^[0-9a-f]{64}$'),
 title_state text not null, chlom_rights_state text not null, ip_publication_state text not null,
 release_state text not null, commercial_proof_stage text not null, gate_state text not null,
 ecac_created boolean not null default false, price_created boolean not null default false,
 checkout_created boolean not null default false, entitlement_created boolean not null default false,
 authoritative boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.repository_release_links (
 link_id text primary key, repo_id text not null, repository text not null,
 source_head text not null check(source_head ~ '^[0-9a-f]{40}$'), release_id text,
 contract_digest text not null check(contract_digest ~ '^[0-9a-f]{64}$'),
 oidc_state text not null, certification_state text not null, non_voting boolean not null default true,
 authoritative boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.vault_binding_refs (
 binding_id text primary key, asset_id text references institutional_ip.assets(asset_id),
 alias_class text not null, vault_alias_ref text not null, binding_state text not null,
 secret_value_in_registry boolean not null default false, readback_state text not null,
 authoritative boolean not null default false, created_at timestamptz not null default now()
);
create table if not exists institutional_ip.audit_events (
 audit_event_id text primary key, subject_type text not null, subject_id text not null,
 event_type text not null, actor_class text not null, source_head text,
 details jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
);

create index if not exists institutional_ip_invention_asset_idx on institutional_ip.invention_records(asset_id);
create index if not exists institutional_ip_title_asset_idx on institutional_ip.chain_of_title_records(asset_id);
create index if not exists institutional_ip_framework_intake_idx on institutional_ip.framework_factory_intakes(framework_id,source_head);
create index if not exists institutional_ip_chlom_link_idx on institutional_ip.chlom_rights_links(asset_id,chlom_object_type,chlom_object_id);
create index if not exists institutional_ip_thriveevergreen_gate_idx on institutional_ip.thriveevergreen_gate_receipts(offer_id,created_at);
create index if not exists institutional_ip_repo_release_idx on institutional_ip.repository_release_links(repository,source_head);

DO $rls$
DECLARE r record;
BEGIN
 FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='institutional_ip' LOOP
  EXECUTE format('alter table institutional_ip.%I enable row level security',r.tablename);
  EXECUTE format('alter table institutional_ip.%I force row level security',r.tablename);
 END LOOP;
END $rls$;

revoke all on all tables in schema institutional_ip from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema institutional_ip to service_role;
alter default privileges in schema institutional_ip revoke all on tables from public, anon, authenticated;
alter default privileges in schema institutional_ip grant select, insert, update, delete on tables to service_role;
comment on schema institutional_ip is 'Restricted service-only institutional IP evidence and integration candidates. No generic anon/authenticated policies.';
comment on table institutional_ip.thriveevergreen_gate_receipts is 'Preflight evidence only; never ECAC, price, checkout or entitlement authority.';
comment on table institutional_ip.chlom_rights_links is 'CHLOM remains the rights authority; this table stores references/digests only.';
commit;
