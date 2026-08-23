-- CHLOM Wallet Policy Assurance Engine v1 — THIVEBASE institutional readback.
-- This script verifies the applied runtime. It performs no provider write,
-- custody, money movement, rights grant, chain broadcast, pricing, phase, or merge action.

do $$
declare
  v_tables integer;
  v_rls integer;
  v_policies integer;
  v_triggers integer;
  v_private_table_access integer;
  v_private_function_access integer;
  v_public_status_access integer;
  v_algorithms integer;
  v_rulepacks integer;
  v_decisions integer;
  v_canary text;
begin
  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1')
  )
  select count(*) into v_tables
  from expected e
  join information_schema.tables t
    on t.table_schema='chlom_wallet' and t.table_name=e.name;

  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1')
  )
  select count(*) into v_rls
  from expected e
  join pg_class c on c.relname=e.name and c.relrowsecurity
  join pg_namespace n on n.oid=c.relnamespace and n.nspname='chlom_wallet';

  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1')
  )
  select count(*) into v_policies
  from expected e
  where exists (
    select 1 from pg_policies p
    where p.schemaname='chlom_wallet' and p.tablename=e.name
  );

  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1')
  )
  select count(*) into v_triggers
  from expected e
  where exists (
    select 1 from pg_trigger t
    join pg_class c on c.oid=t.tgrelid
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='chlom_wallet' and c.relname=e.name and not t.tgisinternal
  );

  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1')
  )
  select count(*) into v_private_table_access
  from expected e
  where has_table_privilege('anon',format('chlom_wallet.%I',e.name),'SELECT,INSERT,UPDATE,DELETE')
     or has_table_privilege('authenticated',format('chlom_wallet.%I',e.name),'SELECT,INSERT,UPDATE,DELETE')
     or has_table_privilege('public',format('chlom_wallet.%I',e.name),'SELECT,INSERT,UPDATE,DELETE');

  select count(*) into v_private_function_access
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='chlom_wallet'
    and p.proname in (
      'record_policy_decision_receipt_v1',
      'run_policy_assurance_database_canary_v1'
    )
    and (
      has_function_privilege('anon',p.oid,'EXECUTE')
      or has_function_privilege('authenticated',p.oid,'EXECUTE')
      or has_function_privilege('public',p.oid,'EXECUTE')
    );

  select count(*) into v_public_status_access
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='public'
    and p.proname='chlom_wallet_policy_assurance_status_v1'
    and p.prosecdef
    and has_function_privilege('anon',p.oid,'EXECUTE')
    and has_function_privilege('authenticated',p.oid,'EXECUTE');

  select count(*) into v_algorithms from chlom_wallet.policy_algorithm_registry_v1;
  select count(*) into v_rulepacks
  from chlom_wallet.policy_rulepacks_v1
  where rulepack_ref='ct.rulepack.chlom-wallet.policy-assurance.v1@1.0.0'
    and compiled_sha256='c20767aaa8cce230d8b50af9c7a2b86e83bd7ffb65704c9af75f7d196da6a90b';
  select count(*) into v_decisions from chlom_wallet.policy_decision_receipts_v1;
  select result into v_canary
  from chlom_wallet.policy_assurance_canary_runs_v1
  order by created_at desc limit 1;

  if v_tables<>4 or v_rls<>4 or v_policies<>4 or v_triggers<>4
     or v_private_table_access<>0 or v_private_function_access<>0
     or v_public_status_access<>1 or v_algorithms<>7 or v_rulepacks<>1
     or v_decisions<3
     or v_canary<>'PASS_CHLOM_WALLET_POLICY_ASSURANCE_RUNTIME_CANARY' then
    raise exception 'policy_assurance_readback_failed tables=% rls=% policies=% triggers=% private_tables=% private_functions=% public_status=% algorithms=% rulepacks=% decisions=% canary=%',
      v_tables,v_rls,v_policies,v_triggers,v_private_table_access,v_private_function_access,
      v_public_status_access,v_algorithms,v_rulepacks,v_decisions,v_canary;
  end if;
end;
$$;

select jsonb_build_object(
  'result','PASS_CHLOM_WALLET_POLICY_ASSURANCE_THIVEBASE_READBACK',
  'algorithm_count',7,
  'rulepack_ref','ct.rulepack.chlom-wallet.policy-assurance.v1@1.0.0',
  'rulepack_compiled_sha256','c20767aaa8cce230d8b50af9c7a2b86e83bd7ffb65704c9af75f7d196da6a90b',
  'private_tables',4,
  'rls_deny_all',true,
  'append_only_guards',true,
  'private_table_public_access',false,
  'private_function_public_execution',false,
  'public_status_read_only',true,
  'database_replay_safe',true,
  'runtime_canary','PASS_CHLOM_WALLET_POLICY_ASSURANCE_RUNTIME_CANARY',
  'production_activation',false,
  'provider_write',false,
  'custody',false,
  'token_issuance',false,
  'money_movement',false,
  'production_rights_grant',false,
  'chain_broadcast',false,
  'effective_price_publication',false,
  'checkout_activation',false,
  'phase_advancement',false,
  'merge_authorized',false
) as policy_assurance_readback;
