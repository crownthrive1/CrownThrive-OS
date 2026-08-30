-- Evidence-preserving rollback for ct.penta.assignment-fulfillment.v1
-- This rollback never drops assignment, owner-result, PentaDocs, Drive or DAIL history.

begin;

update integration_control.penta_assignment_policy_v1
set state='HOLD',
    metadata=metadata||jsonb_build_object(
      'rollback_state','HOLD_FAIL_CLOSED',
      'rollback_at',clock_timestamp(),
      'history_preserved',true,
      'provider_mutation_enabled',false,
      'independent_recertification_required',true,
      'authority_expansion',false
    ),
    updated_at=now()
where policy_key='ct.penta.change-institutionalization.rule.v1';

create or replace function public.penta_self_tick_v1()
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','penta_self','integration_control','public'
as $$
declare
  v_scheduler jsonb;
  v_failed_jobs jsonb;
  v_registry jsonb;
  v_pr_handoff jsonb;
  v_hard_repair jsonb;
  v_hard_repair_pr jsonb;
begin
  v_scheduler:=penta_self.scheduler_reconcile_v1();
  v_failed_jobs:=penta_self.failed_job_recovery_v2();
  v_registry:=public.penta_self_registry_refresh_v1();
  v_pr_handoff:=public.penta_self_pr_handoff_tick_v1();
  v_hard_repair:=penta_self.hard_repair_queue_tick_v1(3);
  v_hard_repair_pr:=penta_self.hard_repair_pr_tick_v1(10);
  return jsonb_build_object(
    'service','ct.penta.self.tick.v2',
    'state',case when coalesce((v_hard_repair->>'held')::integer,0)>0 or coalesce((v_hard_repair_pr->>'held')::integer,0)>0 then 'degraded' else 'completed' end,
    'scheduler',v_scheduler,'failed_jobs',v_failed_jobs,'registry',v_registry,
    'pr_handoff',v_pr_handoff,'hard_repair',v_hard_repair,'hard_repair_pr',v_hard_repair_pr,
    'surgical_care_family','SURGICAL_CARE','rollback_rule','surgery_caused_regression_only',
    'immediate_retry_limit',1,'originator_self_certification',false,'direct_main',false,
    'authority_created',false,'at',clock_timestamp()
  );
end $$;

update public.penta_system_registry
set metadata=metadata||jsonb_build_object(
      'rollback_state','HOLD_FAIL_CLOSED',
      'provider_mutation_enabled',false,
      'history_preserved',true,
      'independent_recertification_required',true,
      'authority_expansion',false
    ),
    maturity='implemented',
    updated_at=now()
where system_key in (
  'penta.assignment-fabric',
  'penta.docs.institutionalization',
  'penta.pr-terminalization-v4'
);

update integration_control.penta_family_runtime_v1
set metadata=metadata||jsonb_build_object(
      'assignment_contract_state','HOLD_FAIL_CLOSED',
      'member_runtime_authority_unchanged',true,
      'history_preserved',true,
      'authority_expansion',false
    ),
    updated_at=now();

select chlom_runtime.append_dail_event(
  'penta.assignment-fabric.rollback.applied.v1',
  'control_plane_rollback',
  'ct.penta.assignment-fulfillment.v1',
  jsonb_build_object(
    'state','HOLD_FAIL_CLOSED',
    'provider_terminal_mutation_enabled',false,
    'penta_self_assignment_tick_removed',true,
    'tables_dropped',false,
    'history_preserved',true,
    'drive_evidence_preserved',true,
    'pentadocs_preserved',true,
    'dail_preserved',true,
    'independent_recertification_required',true,
    'authority_expansion',false,
    'rolled_back_at',clock_timestamp()
  ),
  'PentaBuild/PentaSELF/PentaRestore',null,'PentaRestore','1.0.0',
  'ctcorr:penta-assignment-fabric-rollback',null,
  'ct.penta.assignment-fulfillment.v1',null,'internal'
);

commit;

-- After this SQL transaction, deploy
-- supabase/rollback/penta-assignment-institutionalization-v1/penta-pr-terminal-provider-fail-closed.ts
-- with verify_jwt=true. Do not redeploy a prior terminal provider that lacks the institutional gate.
