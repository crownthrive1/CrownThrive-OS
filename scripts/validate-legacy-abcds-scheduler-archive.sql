-- Read-only validation for CrownThrive legacy A/B/C/D/S scheduler archive v1.
-- Expected result: all checks return PASS and zero live legacy dispatch aliases/functions.

with target_schedules as (
  select *
  from chlom_runtime.agent_schedule_definitions
  where schedule_id = any(array[
    'ct.schedule.agent-a.portfolio-fallback.hourly',
    'ct.schedule.chlom-wallet.review.protocol.hourly.v1',
    'ct.schedule.chlom-wallet.review.quorum.hourly.v1',
    'ct.schedule.chlom-wallet.review.recovery.hourly.v1',
    'ct.schedule.chlom-wallet.review.release.hourly.v1',
    'ct.schedule.chlom-wallet.review.security.hourly.v1',
    'ct.schedule.chlom.document-recovery-continuity.hourly.v1'
  ]::text[])
),
legacy_functions as (
  select n.nspname || '.' || p.proname as function_name
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'chlom_runtime'
    and p.proname in (
      'agent_a_emergency_portfolio_cycle_v2',
      'agent_a_portfolio_preflight',
      'agent_a_start_portfolio_cycle'
    )
)
select jsonb_build_object(
  'schema', 'crownthrive.legacy-abcds-scheduler-archive-validation.v1',
  'checked_at', now(),
  'schedule_rows', (select count(*) from target_schedules),
  'schedule_rows_retired', (select count(*) from target_schedules where execution_state='retired'),
  'schedule_rows_with_provider_task_id', (select count(*) from target_schedules where external_task_id is not null),
  'schedule_rows_with_parent_relay_alias', (select count(*) from target_schedules where metadata ? 'canonical_parent_external_relay'),
  'schedule_rows_historical_only', (select count(*) from target_schedules where metadata->>'historical_reference_only'='true'),
  'legacy_functions_remaining', (select count(*) from legacy_functions),
  'retired_binding_tombstones', (
    select count(*)
    from chlom_runtime.automation_agent_bindings
    where binding_id in ('ct.automation.maintenance-coordinator.v1','ct.automation.monthly-heartbeat.v1')
      and task_enabled=false
      and architecture_state='retired'
      and external_task_id like 'archived-historical-only:%'
  ),
  'canonical_relay_active', exists (
    select 1
    from chlom_runtime.agent_schedule_definitions
    where schedule_id='ct.schedule.external-evidence-relay.hourly.v1'
      and execution_state='active'
      and external_task_id='6a8620e935cc8191bbd31075e12dd22a'
  ),
  'archive_evidence_present', exists (
    select 1
    from chlom_runtime.integrity_evidence_ledger
    where evidence_id='ct.evidence.legacy-abcds-scheduler-archive.2026-08-27.v1'
      and evidence_state='pass'
      and content_sha256='e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2'
  ),
  'topology', public.crownthrive_scheduler_topology_status_v1(),
  'backup_connector_due', public.crownthrive_backup_connector_due_v2(10)
) as validation;
