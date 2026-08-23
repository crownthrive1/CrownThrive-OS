-- CHLOM Wallet Execution Envelope v1
-- CONTROLLED TEST ONLY. Additive, append-only, service-role-only runtime evidence.
-- This migration does not create reviewer evidence, grant capabilities, activate providers,
-- move money, grant Rights, broadcast chain transactions, publish prices, enable checkout,
-- authorize merge, or advance the institutional phase.

create schema if not exists chlom_wallet;

create table if not exists chlom_wallet.execution_envelope_profiles_v1 (
  skill_id text primary key,
  registry_id text not null,
  semantic_version text not null check (semantic_version = '1.0.0'),
  state text not null check (state = 'CONTROLLED_TEST'),
  pallet_ids text[] not null check (cardinality(pallet_ids) > 0),
  action_types text[] not null check (cardinality(action_types) > 0),
  value_classes text[] not null check (cardinality(value_classes) > 0),
  required_handoffs text[] not null check (cardinality(required_handoffs) > 0),
  pending_role_aliases text[] not null default '{}'::text[],
  profile_sha256 text not null check (profile_sha256 ~ '^[0-9a-f]{64}$'),
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  source_ref text not null,
  authority_granted boolean not null default false check (not authority_granted),
  capability_grant_created boolean not null default false check (not capability_grant_created),
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.handoff_evidence_observations_v1 (
  observation_id uuid primary key default gen_random_uuid(),
  execution_intent_id text not null,
  required_reviewer_agent_id text not null,
  observed_receipt_id text,
  observed_receipt_sha256 text check (observed_receipt_sha256 is null or observed_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  observed_source_head_sha text check (observed_source_head_sha is null or observed_source_head_sha ~ '^[0-9a-f]{40}$'),
  observed_heartbeat_fresh boolean,
  observed_decision text check (observed_decision is null or observed_decision in ('PASS','HOLD','DENY')),
  routing_state text not null check (routing_state in ('SATISFIED','HOLD','DENY')),
  evidence_class text not null check (evidence_class in ('OBSERVED_EXTERNAL_RECEIPT','MISSING','STALE','HELD','DENIED','SYNTHETIC_CANARY')),
  source_ref text not null,
  reviewer_receipt_created_by_wallet boolean not null default false check (not reviewer_receipt_created_by_wallet),
  reviewer_heartbeat_created_by_wallet boolean not null default false check (not reviewer_heartbeat_created_by_wallet),
  authority_granted boolean not null default false check (not authority_granted),
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.execution_envelope_receipts_v1 (
  execution_envelope_id uuid primary key default gen_random_uuid(),
  intent_id text not null,
  correlation_id text not null,
  subject_ref text not null,
  skill_id text not null references chlom_wallet.execution_envelope_profiles_v1(skill_id),
  pallet_ids text[] not null,
  action_type text not null,
  value_class text not null,
  environment text not null,
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  disposition text not null check (disposition in ('ECAC','HOLD','DENY')),
  policy_disposition text not null check (policy_disposition in ('ECAC','HOLD','DENY')),
  handoff_state text not null check (handoff_state in ('SATISFIED','HOLD','DENY')),
  profile_disposition text not null check (profile_disposition in ('ECAC','HOLD','DENY')),
  required_handoffs text[] not null,
  accepted_handoffs text[] not null default '{}'::text[],
  pending_role_aliases text[] not null default '{}'::text[],
  reasons jsonb not null default '[]'::jsonb,
  policy_receipt_sha256 text not null check (policy_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  handoff_router_receipt_sha256 text not null check (handoff_router_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  execution_envelope_sha256 text not null unique check (execution_envelope_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_class text not null check (evidence_class in ('SYNTHETIC_CANARY','OBSERVED_CONTROLLED_TEST')),
  authority_granted boolean not null default false check (not authority_granted),
  capability_grant_created boolean not null default false check (not capability_grant_created),
  provider_write boolean not null default false check (not provider_write),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  merge_authorized boolean not null default false check (not merge_authorized),
  phase_advancement boolean not null default false check (not phase_advancement),
  ai_final_authority boolean not null default false check (not ai_final_authority),
  source_ref text not null,
  created_at timestamptz not null default now(),
  unique (intent_id, source_head_sha, execution_envelope_sha256)
);

create table if not exists chlom_wallet.execution_envelope_canary_runs_v1 (
  canary_run_id uuid primary key default gen_random_uuid(),
  result text not null,
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  registry_id text not null,
  profile_count integer not null check (profile_count = 23),
  pallet_count integer not null check (pallet_count = 12),
  valid_profile_ecac_count integer not null check (valid_profile_ecac_count = 23),
  chaos_case_count integer not null check (chaos_case_count >= 0),
  chaos_ecac_count integer not null check (chaos_ecac_count = 0),
  chaos_hold_count integer not null check (chaos_hold_count >= 0),
  chaos_deny_count integer not null check (chaos_deny_count >= 0),
  invariant_failures integer not null check (invariant_failures = 0),
  pending_aliases_executable boolean not null default false check (not pending_aliases_executable),
  reviewer_receipts_fabricated boolean not null default false check (not reviewer_receipts_fabricated),
  reviewer_heartbeats_fabricated boolean not null default false check (not reviewer_heartbeats_fabricated),
  append_only_guard_verified boolean not null check (append_only_guard_verified),
  rls_force_verified boolean not null check (rls_force_verified),
  anon_access boolean not null default false check (not anon_access),
  authenticated_access boolean not null default false check (not authenticated_access),
  authority_granted boolean not null default false check (not authority_granted),
  capability_grant_created boolean not null default false check (not capability_grant_created),
  provider_write boolean not null default false check (not provider_write),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  rights_grant boolean not null default false check (not rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  merge_authorized boolean not null default false check (not merge_authorized),
  phase_advancement boolean not null default false check (not phase_advancement),
  ai_final_authority boolean not null default false check (not ai_final_authority),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create or replace function chlom_wallet.reject_execution_envelope_mutation_v1()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
begin
  raise exception 'CHLOM Wallet execution-envelope evidence is append-only; mutation is prohibited';
end;
$$;

revoke all on function chlom_wallet.reject_execution_envelope_mutation_v1() from public, anon, authenticated;

create trigger execution_envelope_profiles_v1_append_only before update or delete on chlom_wallet.execution_envelope_profiles_v1 for each row execute function chlom_wallet.reject_execution_envelope_mutation_v1();
create trigger handoff_evidence_observations_v1_append_only before update or delete on chlom_wallet.handoff_evidence_observations_v1 for each row execute function chlom_wallet.reject_execution_envelope_mutation_v1();
create trigger execution_envelope_receipts_v1_append_only before update or delete on chlom_wallet.execution_envelope_receipts_v1 for each row execute function chlom_wallet.reject_execution_envelope_mutation_v1();
create trigger execution_envelope_canary_runs_v1_append_only before update or delete on chlom_wallet.execution_envelope_canary_runs_v1 for each row execute function chlom_wallet.reject_execution_envelope_mutation_v1();

alter table chlom_wallet.execution_envelope_profiles_v1 enable row level security;
alter table chlom_wallet.execution_envelope_profiles_v1 force row level security;
alter table chlom_wallet.handoff_evidence_observations_v1 enable row level security;
alter table chlom_wallet.handoff_evidence_observations_v1 force row level security;
alter table chlom_wallet.execution_envelope_receipts_v1 enable row level security;
alter table chlom_wallet.execution_envelope_receipts_v1 force row level security;
alter table chlom_wallet.execution_envelope_canary_runs_v1 enable row level security;
alter table chlom_wallet.execution_envelope_canary_runs_v1 force row level security;

revoke all on chlom_wallet.execution_envelope_profiles_v1 from public, anon, authenticated;
revoke all on chlom_wallet.handoff_evidence_observations_v1 from public, anon, authenticated;
revoke all on chlom_wallet.execution_envelope_receipts_v1 from public, anon, authenticated;
revoke all on chlom_wallet.execution_envelope_canary_runs_v1 from public, anon, authenticated;

grant select, insert on chlom_wallet.execution_envelope_profiles_v1 to service_role;
grant select, insert on chlom_wallet.handoff_evidence_observations_v1 to service_role;
grant select, insert on chlom_wallet.execution_envelope_receipts_v1 to service_role;
grant select, insert on chlom_wallet.execution_envelope_canary_runs_v1 to service_role;
