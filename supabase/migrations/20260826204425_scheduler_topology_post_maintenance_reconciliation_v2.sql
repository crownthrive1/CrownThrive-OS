-- CrownThrive scheduler topology post-maintenance reconciliation v2
-- Non-destructive: append/supersede only. No provider writes, money movement,
-- rights/entitlement grants, credential access, sovereign vote, quorum effect, or D3.

begin;

update chlom_runtime.scheduler_topology_v1
set semantic_version = '1.2.0',
    post_maintenance_external_clock_target = 2,
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'current_reconciliation_ref', 'founder-directive-2026-08-26-current-topology-reconciliation',
      'maintenance_state', 'CLOSED',
      'canonical_external_clock_target', 2,
      'canonical_external_clock_model', jsonb_build_array('external-evidence-relay','email-attention'),
      'backup_external_failure_domain', 'folded_into_external-evidence-relay',
      'dedicated_backup_external_clock', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'maintenance_coordinator_state', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'legacy_ABCDS_scheduler_topology', 'superseded_by_thrivebase_production_software_fabric',
      'wallet_pr230_scheduler_state', 'SUPERSEDED_RETIRED_SCHEDULING_SCAFFOLDING',
      'wallet_phase3_successor_pr', 476,
      'wallet_phase3_successor_merge_commit', 'e6466e7a56c27b05b2ed15eb4fa1ae34ea490018',
      'support_main_at_reconciliation_start', '92f69e40d4cb595b05d22167537d5af763d5dcba',
      'history_policy', 'append_or_supersede_never_silent_delete',
      'authority_expansion', false,
      'provider_write_from_scheduler', false,
      'money_movement_from_scheduler', false,
      'd3_human_reserved', true,
      'reconciled_at', now()
    )
where topology_id = 'ct.scheduler-topology.production.v1';

-- Legacy Agent-A external fallback is scheduling scaffolding under the current
-- production software fabric. Preserve the row and its evidence; stop dispatch.
update chlom_runtime.agent_schedule_definitions
set execution_state = 'superseded',
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'superseded_at', now(),
      'supersession_state', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'superseded_by', 'ThriveBase production OS / Software Factory / governed queues',
      'legacy_agent_identity_preserved', true,
      'external_scheduler_slot_delta', 0,
      'authority_expansion', false,
      'history_policy', 'append_or_supersede_never_silent_delete'
    ),
    updated_at = now()
where schedule_id = 'ct.schedule.agent-a.portfolio-fallback.hourly'
  and execution_state = 'active';

-- PR #230 is closed and unmerged; its five PR-specific independent-review
-- schedule rows cannot remain live dispatch targets. Preserve all v1/v2 lane,
-- heartbeat, receipt, and synthesis history, but supersede the external schedule
-- scaffolding in favor of the current Phase-3 Penta Wallet continuity ownership.
update chlom_runtime.agent_schedule_definitions
set execution_state = 'superseded',
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'superseded_at', now(),
      'supersession_state', 'SUPERSEDED_RETIRED_SCHEDULING_SCAFFOLDING',
      'supersession_reason', 'canonical PR 230 closed/unmerged and exact-head cohort stale',
      'legacy_pr', 230,
      'legacy_review_history_preserved', true,
      'current_phase3_successor_pr', 476,
      'current_phase3_successor_merge_commit', 'e6466e7a56c27b05b2ed15eb4fa1ae34ea490018',
      'current_owner_model', 'PentaNurture/PentaStatus/PentaCredentials/PentaCertify/PentaFactory/PentaBuild/PentaTriage with CHLOM authority boundary',
      'reviewer_heartbeat_fabricated', false,
      'review_receipt_fabricated', false,
      'synthesis_fabricated', false,
      'vote_effect', 'none',
      'external_scheduler_slot_delta', 0,
      'authority_expansion', false,
      'history_policy', 'append_or_supersede_never_silent_delete'
    ),
    updated_at = now()
where suite_id = 'ct.agent-suite.chlom-wallet-independent-review.v1'
  and execution_state = 'active';

-- Maintenance is closed. Normalize only the effective maintenance marker on
-- still-active relay subroutes; do not alter cadence, authority, or due logic.
update chlom_runtime.agent_schedule_definitions
set metadata = jsonb_set(
                 jsonb_set(
                   coalesce(metadata, '{}'::jsonb),
                   '{maintenance_execution_state}',
                   to_jsonb('closed_post_maintenance'::text),
                   true
                 ),
                 '{scheduler_topology_version}',
                 to_jsonb('1.2.0'::text),
                 true
               ) || jsonb_build_object(
                 'scheduler_topology_reconciled_at', now(),
                 'authority_expansion', false
               ),
    updated_at = now()
where execution_state = 'active'
  and metadata->>'maintenance_execution_state' = 'suspended'
  and (
    external_task_id = '6a8620e935cc8191bbd31075e12dd22a'
    or metadata->>'canonical_parent_external_relay' = 'ct.schedule.external-evidence-relay.hourly.v1'
  );

update chlom_runtime.agent_schedule_definitions
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'maintenance_suspended', false,
      'maintenance_state', 'CLOSED',
      'production_relay_state', 'ACTIVE_CONNECTOR_FAILURE_DOMAIN_ONLY',
      'scheduler_topology_version', '1.2.0',
      'direct_main_write', false,
      'provider_write_authority', false,
      'money_movement', false,
      'd3_human_reserved', true,
      'reconciled_at', now()
    ),
    updated_at = now()
where schedule_id = 'ct.schedule.external-evidence-relay.hourly.v1';

update chlom_runtime.agent_schedule_definitions
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'maintenance_state', 'CLOSED',
      'internal_clock', 'pg_cron',
      'connector_external_parent', 'ct.schedule.external-evidence-relay.hourly.v1',
      'dedicated_chatgpt_clock', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'scheduler_topology_version', '1.2.0',
      'reconciled_at', now()
    ),
    updated_at = now()
where schedule_id = 'ct.schedule.backup-continuity.midnight.v2';

update chlom_runtime.automation_agent_bindings
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'scheduler_topology_version', '1.2.0',
      'maintenance_state', 'CLOSED',
      'post_maintenance_state', 'ACTIVE_CONNECTOR_FAILURE_DOMAIN_ONLY',
      'legacy_ABCDS_scheduler_roles', 'superseded_by_thrivebase_production_software_fabric',
      'wallet_pr230_scheduler_state', 'SUPERSEDED_RETIRED_SCHEDULING_SCAFFOLDING',
      'wallet_phase3_successor_pr', 476,
      'no_authority_expansion', true,
      'reconciled_at', now()
    ),
    updated_at = now()
where binding_id = 'ct.automation.vendor-engine-watch.v1';

-- Fail closed if the intended supersessions did not take effect.
do $$
begin
  if exists (
    select 1 from chlom_runtime.agent_schedule_definitions
    where schedule_id = 'ct.schedule.agent-a.portfolio-fallback.hourly'
      and execution_state = 'active'
  ) then
    raise exception 'legacy Agent-A external fallback remains active';
  end if;

  if exists (
    select 1 from chlom_runtime.agent_schedule_definitions
    where suite_id = 'ct.agent-suite.chlom-wallet-independent-review.v1'
      and execution_state = 'active'
  ) then
    raise exception 'stale Wallet PR230 review schedules remain active';
  end if;

  if not exists (
    select 1 from chlom_runtime.agent_schedule_definitions
    where schedule_id = 'ct.schedule.external-evidence-relay.hourly.v1'
      and execution_state = 'active'
  ) then
    raise exception 'canonical external evidence relay is not active';
  end if;

  if not exists (
    select 1 from chlom_runtime.automation_agent_bindings
    where binding_id = 'ct.automation.maintenance-coordinator.v1'
      and task_enabled = false
      and architecture_state = 'superseded'
  ) then
    raise exception 'maintenance coordinator is not retired';
  end if;
end $$;

commit;
