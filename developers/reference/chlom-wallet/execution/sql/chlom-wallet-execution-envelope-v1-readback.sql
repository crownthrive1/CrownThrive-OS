-- CHLOM Wallet Execution Envelope v1 private readback.
-- Read-only verification. Do not expose raw handoff evidence publicly.

select
  (select count(*) from chlom_wallet.execution_envelope_profiles_v1) as profile_count,
  (select count(*) from chlom_wallet.handoff_evidence_observations_v1) as handoff_observation_count,
  (select count(*) from chlom_wallet.execution_envelope_receipts_v1) as envelope_receipt_count,
  (select count(*) from chlom_wallet.execution_envelope_canary_runs_v1) as canary_run_count;

select
  c.relname,
  c.relrowsecurity as rls_enabled,
  c.relforcerowsecurity as force_rls
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'chlom_wallet'
  and c.relname in (
    'execution_envelope_profiles_v1',
    'handoff_evidence_observations_v1',
    'execution_envelope_receipts_v1',
    'execution_envelope_canary_runs_v1'
  )
order by c.relname;

select
  grantee,
  table_name,
  privilege_type
from information_schema.role_table_grants
where table_schema = 'chlom_wallet'
  and table_name in (
    'execution_envelope_profiles_v1',
    'handoff_evidence_observations_v1',
    'execution_envelope_receipts_v1',
    'execution_envelope_canary_runs_v1'
  )
order by table_name, grantee, privilege_type;

select
  result,
  source_head_sha,
  registry_id,
  profile_count,
  pallet_count,
  valid_profile_ecac_count,
  chaos_case_count,
  chaos_ecac_count,
  chaos_hold_count,
  chaos_deny_count,
  invariant_failures,
  pending_aliases_executable,
  reviewer_receipts_fabricated,
  reviewer_heartbeats_fabricated,
  append_only_guard_verified,
  rls_force_verified,
  anon_access,
  authenticated_access,
  authority_granted,
  capability_grant_created,
  provider_write,
  custody,
  token_issuance,
  money_movement,
  rights_grant,
  chain_broadcast,
  effective_price_publication,
  checkout_activation,
  merge_authorized,
  phase_advancement,
  ai_final_authority,
  created_at
from chlom_wallet.execution_envelope_canary_runs_v1
order by created_at desc
limit 5;
