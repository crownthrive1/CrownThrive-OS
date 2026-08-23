-- CHLOM Wallet Policy Assurance Engine v1 — ThriveBase institutional readback.
-- This script verifies policy, receipt, source-correction, deployment, and public-status controls.
-- It performs no provider write, custody, money movement, rights grant,
-- chain broadcast, pricing, checkout, phase, or merge action.

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
  v_deployments integer;
  v_corrections integer;
  v_runtime_canaries integer;
  v_canary text;
  v_deploy_canary text;
  v_status jsonb;
begin
  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1'),
    ('policy_runtime_deployments_v1'),
    ('policy_source_identity_corrections_v1'),
    ('policy_runtime_deployment_canary_runs_v1')
  )
  select count(*) into v_tables
  from expected e
  join information_schema.tables t
    on t.table_schema='chlom_wallet' and t.table_name=e.name;

  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1'),
    ('policy_runtime_deployments_v1'),
    ('policy_source_identity_corrections_v1'),
    ('policy_runtime_deployment_canary_runs_v1')
  )
  select count(*) into v_rls
  from expected e
  join pg_class c on c.relname=e.name and c.relrowsecurity
  join pg_namespace n on n.oid=c.relnamespace and n.nspname='chlom_wallet';

  with expected(name) as (values
    ('policy_algorithm_registry_v1'),
    ('policy_rulepacks_v1'),
    ('policy_decision_receipts_v1'),
    ('policy_assurance_canary_runs_v1'),
    ('policy_runtime_deployments_v1'),
    ('policy_source_identity_corrections_v1'),
    ('policy_runtime_deployment_canary_runs_v1')
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
    ('policy_assurance_canary_runs_v1'),
    ('policy_runtime_deployments_v1'),
    ('policy_source_identity_corrections_v1'),
    ('policy_runtime_deployment_canary_runs_v1')
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
    ('policy_assurance_canary_runs_v1'),
    ('policy_runtime_deployments_v1'),
    ('policy_source_identity_corrections_v1'),
    ('policy_runtime_deployment_canary_runs_v1')
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
      'run_policy_assurance_database_canary_v1',
      'run_policy_runtime_deployment_canary_v1'
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
  select count(*) into v_corrections
  from chlom_wallet.policy_source_identity_corrections_v1
  where correction_id='ct.correction.chlom-wallet-policy-engine-source-sha256.v1'
    and recorded_sha256='b29e31e5061e66dd24a7d1a399b31df453c54acbf6fbfd0516b499f038b4d6da'
    and corrected_sha256='1fc78917285351ac08b0d8bdc1d80a1c816485cd66b3d35291cb715f0379f70c'
    and git_blob_sha1='41edcecf931b6c653cda6b9f9118ea15b795c72a';
  select count(*) into v_deployments
  from chlom_wallet.policy_runtime_deployments_v1
  where deployment_receipt_id='ct.deploy.chlom-wallet-policy-assurance.v1.2'
    and supersedes_deployment_receipt_id='ct.deploy.chlom-wallet-policy-assurance.v1.1'
    and source_identity_correction_id='ct.correction.chlom-wallet-policy-engine-source-sha256.v1'
    and function_id='815335ae-2b15-467a-80ca-37ca1fe7b993'::uuid
    and function_slug='chlom-wallet-policy-assurance'
    and function_version=2
    and function_status='ACTIVE'
    and verify_jwt
    and deployment_bundle_sha256='00cedfe45163deeb3c71042f911eaedf3418189913a962c5daa1e838f820e9ac'
    and engine_source_sha256='1fc78917285351ac08b0d8bdc1d80a1c816485cd66b3d35291cb715f0379f70c'
    and source_head_sha='0261e0b4d3bfa5f041b59efd9bf78bc6e1f76591';
  select count(*) into v_runtime_canaries
  from chlom_wallet.policy_runtime_deployment_canary_runs_v1;
  select result into v_canary
  from chlom_wallet.policy_assurance_canary_runs_v1
  order by created_at desc limit 1;
  select result into v_deploy_canary
  from chlom_wallet.policy_runtime_deployment_canary_runs_v1
  order by created_at desc limit 1;
  v_status:=public.chlom_wallet_policy_assurance_status_v1();

  if v_tables<>7 or v_rls<>7 or v_policies<>7 or v_triggers<>7
     or v_private_table_access<>0 or v_private_function_access<>0
     or v_public_status_access<>1 or v_algorithms<>7 or v_rulepacks<>1
     or v_decisions<3 or v_corrections<>1 or v_deployments<>1 or v_runtime_canaries<2
     or v_canary<>'PASS_CHLOM_WALLET_POLICY_ASSURANCE_RUNTIME_CANARY'
     or v_deploy_canary<>'PASS_CHLOM_WALLET_POLICY_EDGE_DEPLOYMENT_METADATA_CANARY_V2'
     or v_status#>>'{runtime_surface,state}'<>'ACTIVE'
     or (v_status#>>'{runtime_surface,function_version}')::integer<>2
     or coalesce((v_status#>>'{runtime_surface,verify_jwt}')::boolean,false) is not true
     or v_status#>>'{runtime_surface,deployment_bundle_sha256}'<>'00cedfe45163deeb3c71042f911eaedf3418189913a962c5daa1e838f820e9ac'
     or v_status#>>'{runtime_surface,effective_engine_source_sha256}'<>'1fc78917285351ac08b0d8bdc1d80a1c816485cd66b3d35291cb715f0379f70c'
     or v_status#>>'{runtime_surface,source_identity_correction,correction_id}'<>'ct.correction.chlom-wallet-policy-engine-source-sha256.v1'
     or v_status#>>'{runtime_surface,authenticated_runtime_canary_state}'<>'NOT_EXECUTED'
     or exists (select 1 from jsonb_each(v_status->'hard_boundaries') e where e.value<>'false'::jsonb) then
    raise exception 'policy_assurance_readback_failed tables=% rls=% policies=% triggers=% private_tables=% private_functions=% public_status=% algorithms=% rulepacks=% decisions=% corrections=% deployments=% runtime_canaries=% canary=% deployment_canary=% status=%',
      v_tables,v_rls,v_policies,v_triggers,v_private_table_access,v_private_function_access,
      v_public_status_access,v_algorithms,v_rulepacks,v_decisions,v_corrections,v_deployments,
      v_runtime_canaries,v_canary,v_deploy_canary,v_status;
  end if;
end;
$$;

select jsonb_build_object(
  'result','PASS_CHLOM_WALLET_POLICY_ASSURANCE_THRIVEBASE_READBACK_V2',
  'algorithm_count',7,
  'rulepack_ref','ct.rulepack.chlom-wallet.policy-assurance.v1@1.0.0',
  'rulepack_compiled_sha256','c20767aaa8cce230d8b50af9c7a2b86e83bd7ffb65704c9af75f7d196da6a90b',
  'private_tables',7,
  'source_identity_correction_id','ct.correction.chlom-wallet-policy-engine-source-sha256.v1',
  'effective_engine_source_sha256','1fc78917285351ac08b0d8bdc1d80a1c816485cd66b3d35291cb715f0379f70c',
  'rls_deny_all',true,
  'append_only_guards',true,
  'private_table_public_access',false,
  'private_function_public_execution',false,
  'public_status_read_only',true,
  'database_replay_safe',true,
  'runtime_canary','PASS_CHLOM_WALLET_POLICY_ASSURANCE_RUNTIME_CANARY',
  'edge_function_state','ACTIVE',
  'edge_function_version',2,
  'deployment_receipt_id','ct.deploy.chlom-wallet-policy-assurance.v1.2',
  'supersedes_deployment_receipt_id','ct.deploy.chlom-wallet-policy-assurance.v1.1',
  'verify_jwt',true,
  'deployment_bundle_sha256','00cedfe45163deeb3c71042f911eaedf3418189913a962c5daa1e838f820e9ac',
  'deployment_metadata_canary','PASS_CHLOM_WALLET_POLICY_EDGE_DEPLOYMENT_METADATA_CANARY_V2',
  'authenticated_runtime_canary','NOT_EXECUTED',
  'unauthorized_request_canary','NOT_EXECUTED',
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
