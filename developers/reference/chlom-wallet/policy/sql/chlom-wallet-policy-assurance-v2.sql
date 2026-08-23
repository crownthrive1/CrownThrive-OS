-- CHLOM Wallet Policy Assurance v2
-- CONTROLLED TEST ONLY. Additive, service-role-only runtime evidence.
-- This migration creates no endpoint, no provider write, no money movement,
-- no rights grant, no chain broadcast, no price/checkout, no merge authority,
-- and no phase advancement.

create schema if not exists chlom_wallet;

create table if not exists chlom_wallet.policy_algorithm_registry_v2 (
  algorithm_id text primary key,
  algorithm_key text not null,
  algorithm_name text not null,
  semantic_version text not null check (semantic_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
  purpose text not null,
  input_contract jsonb not null default '{}'::jsonb,
  output_contract jsonb not null default '{}'::jsonb,
  invariants jsonb not null default '[]'::jsonb,
  state text not null check (state = 'CONTROLLED_TEST'),
  deterministic boolean not null check (deterministic),
  final_authority boolean not null default false check (not final_authority),
  ai_advisory boolean not null default false,
  source_path text not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  source_ref text not null,
  created_at timestamptz not null default now(),
  unique (algorithm_key, semantic_version)
);

create table if not exists chlom_wallet.policy_rulepacks_v2 (
  rulepack_ref text primary key,
  rulepack_id text not null,
  semantic_version text not null check (semantic_version ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
  state text not null check (state = 'CONTROLLED_TEST'),
  source_rulepack jsonb not null,
  source_sha256 text not null check (source_sha256 ~ '^[0-9a-f]{64}$'),
  compiled_sha256 text not null check (compiled_sha256 ~ '^[0-9a-f]{64}$'),
  compiler_algorithm_id text not null references chlom_wallet.policy_algorithm_registry_v2(algorithm_id),
  authority_autonomy_ceiling text not null check (authority_autonomy_ceiling = 'A2'),
  authority_decision_ceiling text not null check (authority_decision_ceiling = 'D2'),
  allowed_environments text[] not null,
  production_activation boolean not null default false check (not production_activation),
  provider_write boolean not null default false check (not provider_write),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  ai_final_authority boolean not null default false check (not ai_final_authority),
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_decision_receipts_v2 (
  decision_id uuid primary key default gen_random_uuid(),
  subject_ref text not null,
  correlation_id text not null,
  intent_id text not null,
  intent_sha256 text not null check (intent_sha256 ~ '^[0-9a-f]{64}$'),
  rulepack_ref text not null references chlom_wallet.policy_rulepacks_v2(rulepack_ref),
  rulepack_sha256 text not null check (rulepack_sha256 ~ '^[0-9a-f]{64}$'),
  disposition text not null check (disposition in ('ECAC','HOLD','DENY')),
  risk_score integer not null check (risk_score between 0 and 999),
  risk_band text not null check (risk_band in ('LOW','MEDIUM','HIGH','CRITICAL')),
  action_type text not null,
  value_class text not null,
  environment text not null,
  decision_receipt jsonb not null,
  receipt_sha256 text not null check (receipt_sha256 ~ '^[0-9a-f]{64}$'),
  source_ref text not null,
  controlled_test_only boolean not null default true check (controlled_test_only),
  production_activation boolean not null default false check (not production_activation),
  provider_write boolean not null default false check (not provider_write),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  ai_final_authority boolean not null default false check (not ai_final_authority),
  created_at timestamptz not null default now(),
  unique (intent_id, rulepack_ref, receipt_sha256)
);

create table if not exists chlom_wallet.policy_ai_advisory_receipts_v1 (
  advisory_receipt_id uuid primary key default gen_random_uuid(),
  deterministic_decision_receipt_sha256 text not null check (deterministic_decision_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  advisory_id text not null,
  model_ref text not null,
  proposed_disposition text not null check (proposed_disposition in ('ECAC','HOLD','DENY')),
  deterministic_disposition text not null check (deterministic_disposition in ('ECAC','HOLD','DENY')),
  effective_disposition text not null check (effective_disposition = deterministic_disposition),
  attempted_upgrade boolean not null,
  conflict boolean not null,
  accepted_as_final boolean not null default false check (not accepted_as_final),
  ai_final_authority boolean not null default false check (not ai_final_authority),
  advisory_digest_sha256 text not null check (advisory_digest_sha256 ~ '^[0-9a-f]{64}$'),
  firewall_receipt_sha256 text not null unique check (firewall_receipt_sha256 ~ '^[0-9a-f]{64}$'),
  source_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists chlom_wallet.policy_assurance_canary_runs_v2 (
  canary_run_id uuid primary key default gen_random_uuid(),
  result text not null,
  source_head_sha text not null check (source_head_sha ~ '^[0-9a-f]{40}$'),
  rulepack_ref text not null references chlom_wallet.policy_rulepacks_v2(rulepack_ref),
  rulepack_source_sha256 text not null check (rulepack_source_sha256 ~ '^[0-9a-f]{64}$'),
  rulepack_compiled_sha256 text not null check (rulepack_compiled_sha256 ~ '^[0-9a-f]{64}$'),
  source_scenario_count integer not null check (source_scenario_count >= 0),
  chaos_case_count integer not null check (chaos_case_count >= 0),
  ecac_count integer not null check (ecac_count >= 0),
  hold_count integer not null check (hold_count >= 0),
  deny_count integer not null check (deny_count >= 0),
  ai_advisory_attempts integer not null check (ai_advisory_attempts >= 0),
  invariant_failures integer not null check (invariant_failures = 0),
  skills_mapped integer not null check (skills_mapped >= 0),
  pallets_mapped integer not null check (pallets_mapped >= 0),
  deterministic boolean not null check (deterministic),
  database_replay_safe boolean not null check (database_replay_safe),
  append_only_guard_verified boolean not null check (append_only_guard_verified),
  evidence jsonb not null default '{}'::jsonb,
  production_activation boolean not null default false check (not production_activation),
  provider_write boolean not null default false check (not provider_write),
  custody boolean not null default false check (not custody),
  token_issuance boolean not null default false check (not token_issuance),
  money_movement boolean not null default false check (not money_movement),
  production_rights_grant boolean not null default false check (not production_rights_grant),
  chain_broadcast boolean not null default false check (not chain_broadcast),
  effective_price_publication boolean not null default false check (not effective_price_publication),
  checkout_activation boolean not null default false check (not checkout_activation),
  phase_advancement boolean not null default false check (not phase_advancement),
  merge_authorized boolean not null default false check (not merge_authorized),
  ai_final_authority boolean not null default false check (not ai_final_authority),
  created_at timestamptz not null default now()
);

create or replace function chlom_wallet.reject_policy_assurance_mutation_v2()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog, chlom_wallet
as $$
begin
  raise exception 'CHLOM Wallet policy assurance evidence is append-only; mutation is prohibited';
end;
$$;

revoke all on function chlom_wallet.reject_policy_assurance_mutation_v2() from public;
revoke all on function chlom_wallet.reject_policy_assurance_mutation_v2() from anon;
revoke all on function chlom_wallet.reject_policy_assurance_mutation_v2() from authenticated;

create trigger policy_algorithm_registry_v2_append_only
before update or delete on chlom_wallet.policy_algorithm_registry_v2
for each row execute function chlom_wallet.reject_policy_assurance_mutation_v2();
create trigger policy_rulepacks_v2_append_only
before update or delete on chlom_wallet.policy_rulepacks_v2
for each row execute function chlom_wallet.reject_policy_assurance_mutation_v2();
create trigger policy_decision_receipts_v2_append_only
before update or delete on chlom_wallet.policy_decision_receipts_v2
for each row execute function chlom_wallet.reject_policy_assurance_mutation_v2();
create trigger policy_ai_advisory_receipts_v1_append_only
before update or delete on chlom_wallet.policy_ai_advisory_receipts_v1
for each row execute function chlom_wallet.reject_policy_assurance_mutation_v2();
create trigger policy_assurance_canary_runs_v2_append_only
before update or delete on chlom_wallet.policy_assurance_canary_runs_v2
for each row execute function chlom_wallet.reject_policy_assurance_mutation_v2();

alter table chlom_wallet.policy_algorithm_registry_v2 enable row level security;
alter table chlom_wallet.policy_algorithm_registry_v2 force row level security;
alter table chlom_wallet.policy_rulepacks_v2 enable row level security;
alter table chlom_wallet.policy_rulepacks_v2 force row level security;
alter table chlom_wallet.policy_decision_receipts_v2 enable row level security;
alter table chlom_wallet.policy_decision_receipts_v2 force row level security;
alter table chlom_wallet.policy_ai_advisory_receipts_v1 enable row level security;
alter table chlom_wallet.policy_ai_advisory_receipts_v1 force row level security;
alter table chlom_wallet.policy_assurance_canary_runs_v2 enable row level security;
alter table chlom_wallet.policy_assurance_canary_runs_v2 force row level security;

revoke all on chlom_wallet.policy_algorithm_registry_v2 from public, anon, authenticated;
revoke all on chlom_wallet.policy_rulepacks_v2 from public, anon, authenticated;
revoke all on chlom_wallet.policy_decision_receipts_v2 from public, anon, authenticated;
revoke all on chlom_wallet.policy_ai_advisory_receipts_v1 from public, anon, authenticated;
revoke all on chlom_wallet.policy_assurance_canary_runs_v2 from public, anon, authenticated;

grant select, insert on chlom_wallet.policy_algorithm_registry_v2 to service_role;
grant select, insert on chlom_wallet.policy_rulepacks_v2 to service_role;
grant select, insert on chlom_wallet.policy_decision_receipts_v2 to service_role;
grant select, insert on chlom_wallet.policy_ai_advisory_receipts_v1 to service_role;
grant select, insert on chlom_wallet.policy_assurance_canary_runs_v2 to service_role;
