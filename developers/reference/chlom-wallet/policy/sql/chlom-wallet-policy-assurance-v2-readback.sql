-- CHLOM Wallet Policy Assurance v2 private readback.
-- Read-only verification; do not expose raw private evidence publicly.

select
  (select count(*) from chlom_wallet.policy_algorithm_registry_v2) as algorithm_count,
  (select count(*) from chlom_wallet.policy_rulepacks_v2) as rulepack_count,
  (select count(*) from chlom_wallet.policy_decision_receipts_v2) as decision_receipt_count,
  (select count(*) from chlom_wallet.policy_ai_advisory_receipts_v1) as ai_advisory_receipt_count,
  (select count(*) from chlom_wallet.policy_assurance_canary_runs_v2) as canary_run_count;

select
  c.relname,
  c.relrowsecurity as rls_enabled,
  c.relforcerowsecurity as force_rls
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'chlom_wallet'
  and c.relname in (
    'policy_algorithm_registry_v2',
    'policy_rulepacks_v2',
    'policy_decision_receipts_v2',
    'policy_ai_advisory_receipts_v1',
    'policy_assurance_canary_runs_v2'
  )
order by c.relname;

select
  grantee,
  table_name,
  privilege_type
from information_schema.role_table_grants
where table_schema = 'chlom_wallet'
  and table_name in (
    'policy_algorithm_registry_v2',
    'policy_rulepacks_v2',
    'policy_decision_receipts_v2',
    'policy_ai_advisory_receipts_v1',
    'policy_assurance_canary_runs_v2'
  )
order by table_name, grantee, privilege_type;

select
  result,
  source_head_sha,
  rulepack_ref,
  chaos_case_count,
  ecac_count,
  hold_count,
  deny_count,
  ai_advisory_attempts,
  invariant_failures,
  skills_mapped,
  pallets_mapped,
  deterministic,
  database_replay_safe,
  append_only_guard_verified,
  production_activation,
  provider_write,
  custody,
  token_issuance,
  money_movement,
  production_rights_grant,
  chain_broadcast,
  effective_price_publication,
  checkout_activation,
  phase_advancement,
  merge_authorized,
  ai_final_authority,
  created_at
from chlom_wallet.policy_assurance_canary_runs_v2
order by created_at desc
limit 5;
