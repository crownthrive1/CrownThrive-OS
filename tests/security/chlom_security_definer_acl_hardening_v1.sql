-- Transactional acceptance checks for
-- 20260830121000_chlom_security_definer_acl_hardening_v1.sql
--
-- Expected post-migration invariant for every bounded privileged RPC:
--   anon EXECUTE = false
--   authenticated EXECUTE = false
--   service_role EXECUTE = true
-- No function body, authority policy, provider state, rights state, credential,
-- money movement, D3 state, or canonical DAIL evidence is mutated by this test.

begin;

do $$
declare
  v_sig text;
  v_oid oid;
  v_required text[] := array[
    'chlom_runtime.cie_parent_certification_reconcile_v2(text,text,uuid,text,text)',
    'chlom_runtime.cie_production_source_integration_gate_v2(text,text,text)',
    'chlom_runtime.dail_backfill_lanes_v1(integer)',
    'chlom_runtime.dail_classify_event_lanes_v1(uuid)',
    'chlom_runtime.dail_lane_after_insert_v1()',
    'chlom_runtime.verify_dail_chain_checkpoint_v2()',
    'integration_control.penta_identity_refresh_v1(text)',
    'integration_control.penta_identity_source_custody_invoke_v1()',
    'integration_control.record_business_truth_observation_v1(text,text,text,text,jsonb,numeric,text,boolean,jsonb)',
    'integration_control.scheduler_desired_job_retire_v3(text,bigint,text,text,jsonb)',
    'public.google_api_keys_readback_invoke_v1(text,text)',
    'public.google_cloud_readback_invoke_v1(text,text)',
    'public.penta_pm_enqueue_remediation_execution_v1(uuid,integer,integer,text,text,text,text,jsonb)',
    'public.penta_remediation_execute_known_v3(uuid)',
    'public.penta_remediation_execution_claim_v1(integer)',
    'pentatime.executor_paypal_live_receipt_reconcile_v4()',
    'pentatime.pentadispatch_v1(integer)',
    'pentatime.pentatick_v1(integer)',
    'pentatime.request_wake_v1(text,text,text,text,text,jsonb,text,text,integer,boolean)',
    'pentatime.dail_crossover_sync_v1(integer)',
    'penta_treasury.enact_reconciliation_v1(uuid,bigint,text,bigint)',
    'pentamocracy.ratify_v1(text,text,boolean,boolean,boolean,boolean,boolean,text,text,text)'
  ];
begin
  foreach v_sig in array v_required loop
    v_oid := to_regprocedure(v_sig);
    if v_oid is null then
      raise exception 'missing required privileged RPC after ACL migration: %', v_sig;
    end if;

    if not (select p.prosecdef from pg_proc p where p.oid = v_oid) then
      raise exception 'expected SECURITY DEFINER function lost security-definer posture: %', v_sig;
    end if;

    if has_function_privilege('public', v_oid, 'EXECUTE') then
      raise exception 'PUBLIC still has EXECUTE on privileged RPC: %', v_sig;
    end if;

    if has_function_privilege('anon', v_oid, 'EXECUTE') then
      raise exception 'anon still has EXECUTE on privileged RPC: %', v_sig;
    end if;

    if has_function_privilege('authenticated', v_oid, 'EXECUTE') then
      raise exception 'authenticated still has EXECUTE on privileged RPC: %', v_sig;
    end if;

    if not has_function_privilege('service_role', v_oid, 'EXECUTE') then
      raise exception 'service_role lost required EXECUTE on privileged RPC: %', v_sig;
    end if;
  end loop;
end
$$;

-- Search-path hardening remains required for this bounded cohort. A null/mutable
-- search_path is a separate SECURITY DEFINER escalation risk even after ACL repair.
do $$
declare
  v_sig text;
  v_oid oid;
  v_config text[];
  v_required text[] := array[
    'chlom_runtime.cie_parent_certification_reconcile_v2(text,text,uuid,text,text)',
    'chlom_runtime.cie_production_source_integration_gate_v2(text,text,text)',
    'chlom_runtime.dail_backfill_lanes_v1(integer)',
    'chlom_runtime.dail_classify_event_lanes_v1(uuid)',
    'chlom_runtime.dail_lane_after_insert_v1()',
    'chlom_runtime.verify_dail_chain_checkpoint_v2()',
    'integration_control.penta_identity_refresh_v1(text)',
    'integration_control.penta_identity_source_custody_invoke_v1()',
    'integration_control.record_business_truth_observation_v1(text,text,text,text,jsonb,numeric,text,boolean,jsonb)',
    'integration_control.scheduler_desired_job_retire_v3(text,bigint,text,text,jsonb)',
    'public.google_api_keys_readback_invoke_v1(text,text)',
    'public.google_cloud_readback_invoke_v1(text,text)',
    'public.penta_pm_enqueue_remediation_execution_v1(uuid,integer,integer,text,text,text,text,jsonb)',
    'public.penta_remediation_execute_known_v3(uuid)',
    'public.penta_remediation_execution_claim_v1(integer)',
    'pentatime.executor_paypal_live_receipt_reconcile_v4()',
    'pentatime.pentadispatch_v1(integer)',
    'pentatime.pentatick_v1(integer)',
    'pentatime.request_wake_v1(text,text,text,text,text,jsonb,text,text,integer,boolean)',
    'pentatime.dail_crossover_sync_v1(integer)',
    'penta_treasury.enact_reconciliation_v1(uuid,bigint,text,bigint)',
    'pentamocracy.ratify_v1(text,text,boolean,boolean,boolean,boolean,boolean,text,text,text)'
  ];
begin
  foreach v_sig in array v_required loop
    v_oid := to_regprocedure(v_sig);
    select p.proconfig into v_config from pg_proc p where p.oid = v_oid;
    if v_config is null or not exists (
      select 1 from unnest(v_config) cfg where cfg like 'search_path=%'
    ) then
      raise exception 'privileged RPC lacks pinned search_path: %', v_sig;
    end if;
  end loop;
end
$$;

rollback;
