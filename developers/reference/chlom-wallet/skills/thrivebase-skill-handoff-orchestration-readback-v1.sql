-- CHLOM Wallet Skill & Handoff Orchestration — ThriveBase private readback
-- CONTROLLED_TEST. Run only through an authorized service or administrative lane.
-- Do not expose route_receipt bodies, identity snapshots, fingerprints, or restricted evidence publicly.

-- 1. Canonical algorithm identity and source hash.
select
  algorithm_id,
  algorithm_key,
  algorithm_name,
  semantic_version,
  state,
  deterministic,
  ai_advisory,
  final_authority,
  source_path,
  source_sha256
from chlom_wallet.skill_handoff_algorithm_registry_v1
order by algorithm_key;

-- Expected:
-- WISC  ai_advisory=true  final_authority=false
-- SCOPE ai_advisory=false final_authority=false
-- HARP  ai_advisory=false final_authority=false
-- All source_sha256 = 67c27180eefb81c0b3200f3fcd8afb3cdb3ff6ebff18b34d043ea33a55269c41

-- 2. Runtime object and RLS posture.
select
  p.schemaname,
  p.tablename,
  p.rowsecurity
from pg_tables p
where p.schemaname='chlom_wallet'
  and p.tablename in (
    'skill_handoff_algorithm_registry_v1',
    'skill_handoff_route_receipts_v1',
    'skill_handoff_route_canary_runs_v1'
  )
order by p.tablename;

select
  c.relname as table_name,
  c.relrowsecurity as rls_enabled,
  c.relforcerowsecurity as rls_forced
from pg_class c
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='chlom_wallet'
  and c.relname in (
    'skill_handoff_algorithm_registry_v1',
    'skill_handoff_route_receipts_v1',
    'skill_handoff_route_canary_runs_v1'
  )
order by c.relname;

-- No permissive public/anon/authenticated policies should exist.
select schemaname, tablename, policyname, roles, cmd
from pg_policies
where schemaname='chlom_wallet'
  and tablename in (
    'skill_handoff_algorithm_registry_v1',
    'skill_handoff_route_receipts_v1',
    'skill_handoff_route_canary_runs_v1'
  )
order by tablename, policyname;

-- 3. Append-only mutation triggers.
select
  c.relname as table_name,
  t.tgname as trigger_name,
  pg_get_triggerdef(t.oid, true) as trigger_definition
from pg_trigger t
join pg_class c on c.oid=t.tgrelid
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='chlom_wallet'
  and c.relname in (
    'skill_handoff_algorithm_registry_v1',
    'skill_handoff_route_receipts_v1',
    'skill_handoff_route_canary_runs_v1'
  )
  and not t.tgisinternal
order by c.relname, t.tgname;

-- 4. Controlled route evidence counts without exposing private receipt bodies.
select
  exact_head_sha,
  disposition,
  count(*) as receipt_count,
  min(created_at) as first_created_at,
  max(created_at) as last_created_at
from chlom_wallet.skill_handoff_route_receipts_v1
group by exact_head_sha, disposition
order by last_created_at desc, disposition;

-- 5. Latest canary result and hard-boundary readback.
select
  canary_run_id,
  result,
  exact_head_sha,
  algorithm_count,
  skill_count,
  verified_handoff_count,
  pending_alias_count,
  ready_receipt_result,
  hold_receipt_result,
  deny_receipt_result,
  execution_authorized,
  schedule_slot_created,
  capability_grant_created,
  authority_granted,
  certification_authority,
  credential_access,
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
  vote_effect,
  ai_final_authority,
  created_at
from chlom_wallet.skill_handoff_route_canary_runs_v1
order by created_at desc
limit 10;

-- 6. Authorized exact-head canary invocation example.
-- select chlom_wallet.run_skill_handoff_route_canary_v1('<40-character-exact-git-head>');
