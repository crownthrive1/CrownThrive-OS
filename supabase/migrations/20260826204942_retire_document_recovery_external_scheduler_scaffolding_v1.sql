-- Retire duplicate CHLOM document-recovery external scheduler scaffolding.
-- The production-native pg_cron job ct-chlom-document-recovery-dispatch-15m
-- already owns this duty. Preserve the historical schedule/task references.

begin;

do $$
begin
  if not exists (
    select 1
    from cron.job
    where jobid = 145
      and jobname = 'ct-chlom-document-recovery-dispatch-15m'
      and active = true
      and command like '%chlom_runtime.chlom_document_recovery_dispatch_tick%'
  ) then
    raise exception 'canonical internal document-recovery executor is not active';
  end if;
end $$;

update chlom_runtime.agent_schedule_definitions
set execution_state = 'superseded',
    metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'superseded_at', now(),
      'supersession_state', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'supersession_reason', 'production-native pg_cron executor already owns document recovery continuity',
      'superseded_by', 'pg_cron:ct-chlom-document-recovery-dispatch-15m',
      'internal_jobid', 145,
      'internal_function', 'chlom_runtime.chlom_document_recovery_dispatch_tick',
      'legacy_external_task_id', external_task_id,
      'legacy_external_task_enabled', false,
      'legacy_schedule_identity_preserved', true,
      'authority_expansion', false,
      'history_policy', 'append_or_supersede_never_silent_delete'
    ),
    updated_at = now()
where schedule_id = 'ct.schedule.chlom.document-recovery-continuity.hourly.v1'
  and execution_state = 'active';

update chlom_runtime.scheduler_topology_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'document_recovery_external_scaffolding', 'RETIRED_SCHEDULING_SCAFFOLDING',
      'document_recovery_internal_executor', 'pg_cron:ct-chlom-document-recovery-dispatch-15m',
      'document_recovery_internal_jobid', 145,
      'document_recovery_reconciled_at', now(),
      'authority_expansion', false,
      'history_policy', 'append_or_supersede_never_silent_delete'
    )
where topology_id = 'ct.scheduler-topology.production.v1';

do $$
begin
  if exists (
    select 1
    from chlom_runtime.agent_schedule_definitions
    where schedule_id = 'ct.schedule.chlom.document-recovery-continuity.hourly.v1'
      and execution_state = 'active'
  ) then
    raise exception 'document-recovery external scheduler scaffolding remains active';
  end if;
end $$;

commit;
