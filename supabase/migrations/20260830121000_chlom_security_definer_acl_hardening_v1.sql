-- CrownThrive CHLOM / PentaSecurity privileged RPC ACL hardening v1
--
-- Fresh ThriveBase security readback on 2026-08-30 found a bounded cohort of
-- SECURITY DEFINER functions with EXECUTE inherited by anon/authenticated via
-- PUBLIC or explicit grants. Several functions also enforce service_role inside
-- the body, but the API surface itself must still be least-privilege / fail-closed.
-- This migration changes ACLs only. It does not change function bodies, create
-- D3 authority, rotate credentials, move money, grant rights, or expand provider writes.

begin;

-- Fail closed if the exact production functions we are hardening are not present
-- in the source-replay target. Missing functions indicate source/runtime drift and
-- must be reconciled instead of silently skipping the control.
do $$
declare
  v_sig text;
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
    'pentatime.request_wake_v1(text,text,text,text,text,jsonb,text,text,integer,boolean)'
  ];
begin
  foreach v_sig in array v_required loop
    if to_regprocedure(v_sig) is null then
      raise exception 'CHLOM/PentaSecurity ACL hardening source/runtime drift: required function missing: %', v_sig;
    end if;
  end loop;
end
$$;

-- CHLOM / DAIL authority and chronology surfaces.
revoke execute on function chlom_runtime.cie_parent_certification_reconcile_v2(text,text,uuid,text,text) from public, anon, authenticated;
revoke execute on function chlom_runtime.cie_production_source_integration_gate_v2(text,text,text) from public, anon, authenticated;
revoke execute on function chlom_runtime.dail_backfill_lanes_v1(integer) from public, anon, authenticated;
revoke execute on function chlom_runtime.dail_classify_event_lanes_v1(uuid) from public, anon, authenticated;
revoke execute on function chlom_runtime.dail_lane_after_insert_v1() from public, anon, authenticated;
revoke execute on function chlom_runtime.verify_dail_chain_checkpoint_v2() from public, anon, authenticated;

grant execute on function chlom_runtime.cie_parent_certification_reconcile_v2(text,text,uuid,text,text) to service_role;
grant execute on function chlom_runtime.cie_production_source_integration_gate_v2(text,text,text) to service_role;
grant execute on function chlom_runtime.dail_backfill_lanes_v1(integer) to service_role;
grant execute on function chlom_runtime.dail_classify_event_lanes_v1(uuid) to service_role;
grant execute on function chlom_runtime.dail_lane_after_insert_v1() to service_role;
grant execute on function chlom_runtime.verify_dail_chain_checkpoint_v2() to service_role;

-- Penta identity / scheduler / institutional-truth mutation surfaces.
revoke execute on function integration_control.penta_identity_refresh_v1(text) from public, anon, authenticated;
revoke execute on function integration_control.penta_identity_source_custody_invoke_v1() from public, anon, authenticated;
revoke execute on function integration_control.record_business_truth_observation_v1(text,text,text,text,jsonb,numeric,text,boolean,jsonb) from public, anon, authenticated;
revoke execute on function integration_control.scheduler_desired_job_retire_v3(text,bigint,text,text,jsonb) from public, anon, authenticated;

grant execute on function integration_control.penta_identity_refresh_v1(text) to service_role;
grant execute on function integration_control.penta_identity_source_custody_invoke_v1() to service_role;
grant execute on function integration_control.record_business_truth_observation_v1(text,text,text,text,jsonb,numeric,text,boolean,jsonb) to service_role;
grant execute on function integration_control.scheduler_desired_job_retire_v3(text,bigint,text,text,jsonb) to service_role;

-- Provider readback and Penta remediation execution surfaces.
revoke execute on function public.google_api_keys_readback_invoke_v1(text,text) from public, anon, authenticated;
revoke execute on function public.google_cloud_readback_invoke_v1(text,text) from public, anon, authenticated;
revoke execute on function public.penta_pm_enqueue_remediation_execution_v1(uuid,integer,integer,text,text,text,text,jsonb) from public, anon, authenticated;
revoke execute on function public.penta_remediation_execute_known_v3(uuid) from public, anon, authenticated;
revoke execute on function public.penta_remediation_execution_claim_v1(integer) from public, anon, authenticated;

grant execute on function public.google_api_keys_readback_invoke_v1(text,text) to service_role;
grant execute on function public.google_cloud_readback_invoke_v1(text,text) to service_role;
grant execute on function public.penta_pm_enqueue_remediation_execution_v1(uuid,integer,integer,text,text,text,text,jsonb) to service_role;
grant execute on function public.penta_remediation_execute_known_v3(uuid) to service_role;
grant execute on function public.penta_remediation_execution_claim_v1(integer) to service_role;

-- PentaTime dispatch / wake / provider-receipt orchestration surfaces.
revoke execute on function pentatime.executor_paypal_live_receipt_reconcile_v4() from public, anon, authenticated;
revoke execute on function pentatime.pentadispatch_v1(integer) from public, anon, authenticated;
revoke execute on function pentatime.pentatick_v1(integer) from public, anon, authenticated;
revoke execute on function pentatime.request_wake_v1(text,text,text,text,text,jsonb,text,text,integer,boolean) from public, anon, authenticated;

grant execute on function pentatime.executor_paypal_live_receipt_reconcile_v4() to service_role;
grant execute on function pentatime.pentadispatch_v1(integer) to service_role;
grant execute on function pentatime.pentatick_v1(integer) to service_role;
grant execute on function pentatime.request_wake_v1(text,text,text,text,text,jsonb,text,text,integer,boolean) to service_role;

commit;
