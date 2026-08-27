-- CrownThrive legacy A/B/C/D/S scheduler scaffolding archival v1
-- Canonical directive: Legacy A/B/C/D/S scheduling scaffolding: not reactivated.
-- Production execution remains owned by ThriveBase, CrownThrive OS, Software Factory,
-- Framework Factory, pg_cron, governed queues, provider-native workflows, and the
-- single connector-failure-domain relay ct.schedule.external-evidence-relay.hourly.v1.
--
-- This migration removes live dispatch aliases and isolated executable scheduler
-- entry points while preserving schedule identity, cadence, source references,
-- immutable Git history, and append-only archival evidence.
--
-- No provider write, money movement, rights/entitlement grant, vote/quorum effect,
-- authority expansion, credential access, force push, or D3 action is performed.

begin;

set local lock_timeout = '5s';
set local statement_timeout = '60s';

do $$
declare
  v_schedule_count integer;
  v_function_count integer;
begin
  select count(*)
  into v_schedule_count
  from chlom_runtime.agent_schedule_definitions
  where schedule_id = any(array[
    'ct.schedule.agent-a.portfolio-fallback.hourly',
    'ct.schedule.chlom-wallet.review.protocol.hourly.v1',
    'ct.schedule.chlom-wallet.review.quorum.hourly.v1',
    'ct.schedule.chlom-wallet.review.recovery.hourly.v1',
    'ct.schedule.chlom-wallet.review.release.hourly.v1',
    'ct.schedule.chlom-wallet.review.security.hourly.v1',
    'ct.schedule.chlom.document-recovery-continuity.hourly.v1'
  ]::text[]);

  if v_schedule_count <> 7 then
    raise exception 'legacy scheduler archival precondition failed: expected 7 schedule rows, found %', v_schedule_count;
  end if;

  if exists (
    select 1
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
      and execution_state not in ('superseded', 'retired')
  ) then
    raise exception 'legacy scheduler archival precondition failed: target schedule is not superseded/retired';
  end if;

  select count(*)
  into v_function_count
  from pg_proc p
  join pg_namespace n on n.oid = p.pronamespace
  where n.nspname = 'chlom_runtime'
    and p.proname in (
      'agent_a_emergency_portfolio_cycle_v2',
      'agent_a_portfolio_preflight',
      'agent_a_start_portfolio_cycle'
    );

  if v_function_count <> 3 then
    raise exception 'legacy scheduler archival precondition failed: expected 3 isolated Agent A functions, found %', v_function_count;
  end if;

  if not exists (
    select 1
    from chlom_runtime.agent_schedule_definitions
    where schedule_id = 'ct.schedule.external-evidence-relay.hourly.v1'
      and execution_state = 'active'
      and external_task_id = '6a8620e935cc8191bbd31075e12dd22a'
  ) then
    raise exception 'canonical external evidence relay is not active at its governed task identity';
  end if;
end
$$;

update chlom_runtime.agent_schedule_definitions as d
set execution_state = 'retired',
    external_task_id = null,
    metadata = jsonb_strip_nulls(
      (
        coalesce(d.metadata, '{}'::jsonb)
        - 'canonical_parent_external_relay'
        - 'legacy_external_task_id_retained_as_transport_alias'
        - 'external_scheduler_prompt_updated'
        - 'natural_external_scheduler_post_patch_run'
        - 'runtime_function'
        - 'preflight_function'
        - 'start_function'
      )
      || jsonb_build_object(
        'historical_reference_only', true,
        'archive_directive', 'Legacy A/B/C/D/S scheduling scaffolding: not reactivated.',
        'archived_at', now(),
        'archived_by', 'ct.scheduler-topology.production.v1',
        'archive_class', 'legacy_chatgpt_scheduler_scaffolding',
        'archive_version', '1.0.0',
        'archive_drive_folder_id', '1mJ5qTM9OHvsDoN45PnKVC0IW2rU1mXmA',
        'archive_drive_package_file_id', '1bwO8SM4cbgBl-kksVM8WMrjsQUYEbKSV',
        'archive_drive_manifest_file_id', '13t-UwppaMtduOJSZDRlpzvnQ5ZNcMfCA',
        'archive_package_sha256', 'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2',
        'archive_manifest_sha256', '461291678df8e772bd57559657265adea444c36a9026a8cdc39e73a426c13986',
        'archive_snapshot_sha256', '3bfda79fe0691cdad59939090e40e42586f123dc731cc69f5f8faf9f8df8807e',
        'docs_archive_path', 'knowledge/legacy-abcds-scheduler-scaffolding-archive',
        'successor_topology', 'ct.scheduler-topology.production.v1',
        'successor_execution_fabric', 'ThriveBase/CrownThrive-OS/Software-Factory/Framework-Factory/pg_cron/queues/provider-native-workflows',
        'dispatch_disabled', true,
        'external_task_binding_removed', true,
        'reactivation_forbidden', true,
        'legacy_clock_reactivation_allowed', false,
        'pre_archive_row_sha256', encode(digest(convert_to(to_jsonb(d)::text, 'UTF8'), 'sha256'), 'hex'),
        'historical_external_task_id_sha256',
          case
            when d.external_task_id is null then null
            else encode(digest(convert_to(d.external_task_id, 'UTF8'), 'sha256'), 'hex')
          end,
        'historical_removed_function_refs',
          case
            when d.schedule_id = 'ct.schedule.agent-a.portfolio-fallback.hourly'
              then jsonb_build_array(
                'chlom_runtime.agent_a_emergency_portfolio_cycle_v2',
                'chlom_runtime.agent_a_portfolio_preflight',
                'chlom_runtime.agent_a_start_portfolio_cycle'
              )
            else null
          end,
        'supersession_state', 'RETIRED_SCHEDULING_SCAFFOLDING',
        'history_policy', 'append_or_supersede_never_silent_delete',
        'authority_expansion', false,
        'provider_write_authority', false,
        'money_movement', false,
        'vote_effect', 'none',
        'quorum_effect', 'none',
        'd3_human_reserved', true
      )
    ),
    updated_at = now()
where d.schedule_id = any(array[
  'ct.schedule.agent-a.portfolio-fallback.hourly',
  'ct.schedule.chlom-wallet.review.protocol.hourly.v1',
  'ct.schedule.chlom-wallet.review.quorum.hourly.v1',
  'ct.schedule.chlom-wallet.review.recovery.hourly.v1',
  'ct.schedule.chlom-wallet.review.release.hourly.v1',
  'ct.schedule.chlom-wallet.review.security.hourly.v1',
  'ct.schedule.chlom.document-recovery-continuity.hourly.v1'
]::text[]);

-- These two bindings are already disabled and superseded. Their non-null
-- external_task_id columns are required by the table contract, so replace the
-- real provider task identities with unique, non-routable archival tombstones.
update chlom_runtime.automation_agent_bindings as b
set external_task_id = 'archived-historical-only:' || encode(digest(convert_to(b.external_task_id, 'UTF8'), 'sha256'), 'hex'),
    external_task_title = case
      when b.external_task_title like 'ARCHIVED HISTORICAL ONLY — %' then b.external_task_title
      else 'ARCHIVED HISTORICAL ONLY — ' || b.external_task_title
    end,
    task_enabled = false,
    architecture_state = 'retired',
    metadata = (
      coalesce(b.metadata, '{}'::jsonb)
      - 'legacy_ABCDS_scheduler_roles'
    ) || jsonb_build_object(
      'historical_reference_only', true,
      'archive_directive', 'Legacy A/B/C/D/S scheduling scaffolding: not reactivated.',
      'archived_at', now(),
      'archived_by', 'ct.scheduler-topology.production.v1',
      'archive_class', 'legacy_chatgpt_scheduler_scaffolding',
      'archive_drive_folder_id', '1mJ5qTM9OHvsDoN45PnKVC0IW2rU1mXmA',
      'archive_drive_package_file_id', '1bwO8SM4cbgBl-kksVM8WMrjsQUYEbKSV',
      'archive_drive_manifest_file_id', '13t-UwppaMtduOJSZDRlpzvnQ5ZNcMfCA',
      'archive_package_sha256', 'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2',
      'docs_archive_path', 'knowledge/legacy-abcds-scheduler-scaffolding-archive',
      'historical_external_task_id_sha256', encode(digest(convert_to(b.external_task_id, 'UTF8'), 'sha256'), 'hex'),
      'pre_archive_row_sha256', encode(digest(convert_to(to_jsonb(b)::text, 'UTF8'), 'sha256'), 'hex'),
      'dispatch_disabled', true,
      'provider_task_identity_removed', true,
      'reactivation_forbidden', true,
      'history_policy', 'append_or_supersede_never_silent_delete',
      'authority_expansion', false,
      'vote_effect', 'none',
      'quorum_effect', 'none'
    ),
    source_snapshot_at = now(),
    updated_at = now()
where b.binding_id in (
  'ct.automation.maintenance-coordinator.v1',
  'ct.automation.monthly-heartbeat.v1'
)
  and b.task_enabled = false
  and b.architecture_state = 'superseded';

-- Preserve the active canonical connector relay itself. Remove only the obsolete
-- scheduler-role key and replace it with a historical archive pointer.
update chlom_runtime.automation_agent_bindings
set metadata = (
      coalesce(metadata, '{}'::jsonb)
      - 'legacy_ABCDS_scheduler_roles'
    ) || jsonb_build_object(
      'legacy_scheduler_scaffolding_archive', jsonb_build_object(
        'state', 'ARCHIVED_HISTORICAL_REFERENCE_ONLY',
        'directive', 'Legacy A/B/C/D/S scheduling scaffolding: not reactivated.',
        'drive_folder_id', '1mJ5qTM9OHvsDoN45PnKVC0IW2rU1mXmA',
        'drive_package_file_id', '1bwO8SM4cbgBl-kksVM8WMrjsQUYEbKSV',
        'drive_manifest_file_id', '13t-UwppaMtduOJSZDRlpzvnQ5ZNcMfCA',
        'package_sha256', 'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2',
        'docs_path', 'knowledge/legacy-abcds-scheduler-scaffolding-archive',
        'runtime_code_paths_removed', true,
        'dispatch_aliases_removed', true,
        'archived_at', now()
      ),
      'legacy_scheduler_role_dispatch_allowed', false,
      'no_new_external_scheduler_slot', true,
      'external_scheduler_slots_added', 0,
      'authority_expansion', false,
      'history_policy', 'append_or_supersede_never_silent_delete'
    ),
    updated_at = now()
where binding_id = 'ct.automation.vendor-engine-watch.v1'
  and task_enabled = true
  and architecture_state = 'bound';

drop function chlom_runtime.agent_a_emergency_portfolio_cycle_v2(text, text, boolean);
drop function chlom_runtime.agent_a_portfolio_preflight(text, integer, integer, boolean, text);
drop function chlom_runtime.agent_a_start_portfolio_cycle(text, text, boolean);

update chlom_runtime.scheduler_topology_v1
set metadata = (
      coalesce(metadata, '{}'::jsonb)
      - 'legacy_ABCDS_scheduler_topology'
    ) || jsonb_build_object(
      'historical_scheduler_archive_ref', jsonb_build_object(
        'state', 'ARCHIVED_HISTORICAL_REFERENCE_ONLY',
        'directive', 'Legacy A/B/C/D/S scheduling scaffolding: not reactivated.',
        'drive_folder_id', '1mJ5qTM9OHvsDoN45PnKVC0IW2rU1mXmA',
        'drive_package_file_id', '1bwO8SM4cbgBl-kksVM8WMrjsQUYEbKSV',
        'drive_manifest_file_id', '13t-UwppaMtduOJSZDRlpzvnQ5ZNcMfCA',
        'package_sha256', 'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2',
        'manifest_sha256', '461291678df8e772bd57559657265adea444c36a9026a8cdc39e73a426c13986',
        'snapshot_sha256', '3bfda79fe0691cdad59939090e40e42586f123dc731cc69f5f8faf9f8df8807e',
        'docs_path', 'knowledge/legacy-abcds-scheduler-scaffolding-archive',
        'schedule_rows_archived', 7,
        'automation_bindings_tombstoned', 2,
        'executable_functions_removed', 3,
        'dispatch_aliases_removed', true,
        'runtime_code_paths_removed', true,
        'archived_at', now()
      ),
      'legacy_scheduler_reactivation_allowed', false,
      'history_policy', 'append_or_supersede_never_silent_delete',
      'authority_expansion', false,
      'provider_write_from_scheduler', false,
      'money_movement_from_scheduler', false,
      'd3_human_reserved', true
    ),
    updated_at = now()
where topology_id = 'ct.scheduler-topology.production.v1';

insert into chlom_runtime.integrity_evidence_ledger (
  evidence_id,
  suite_id,
  evidence_class,
  subject_ref,
  evidence_state,
  content_sha256,
  source_refs,
  payload
)
values (
  'ct.evidence.legacy-abcds-scheduler-archive.2026-08-27.v1',
  'ct.agent-suite.master.v1',
  'archive',
  'ct.scheduler-topology.production.v1/legacy-abcds-scheduler-scaffolding',
  'pass',
  'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2',
  array[
    'drive:folder:1mJ5qTM9OHvsDoN45PnKVC0IW2rU1mXmA',
    'drive:file:1bwO8SM4cbgBl-kksVM8WMrjsQUYEbKSV',
    'drive:file:13t-UwppaMtduOJSZDRlpzvnQ5ZNcMfCA',
    'github:crownthrive1/CrownThrive-OS@97f9d9b993e8d80f29b0ec73f290aef44960f3ab',
    'docs:knowledge/legacy-abcds-scheduler-scaffolding-archive',
    'topology:ct.scheduler-topology.production.v1'
  ]::text[],
  jsonb_build_object(
    'directive', 'Legacy A/B/C/D/S scheduling scaffolding: not reactivated.',
    'archive_state', 'ARCHIVED_HISTORICAL_REFERENCE_ONLY',
    'archive_package_sha256', 'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2',
    'archive_manifest_sha256', '461291678df8e772bd57559657265adea444c36a9026a8cdc39e73a426c13986',
    'archive_snapshot_sha256', '3bfda79fe0691cdad59939090e40e42586f123dc731cc69f5f8faf9f8df8807e',
    'drive_readback_verified', true,
    'bounded_restore_verified', true,
    'schedule_rows_archived', 7,
    'automation_bindings_tombstoned', 2,
    'executable_functions_removed', 3,
    'immutable_git_history_retained', true,
    'prior_migrations_retained', true,
    'secret_material_exported', false,
    'protected_algorithm_bodies_exported', false,
    'private_identity_mappings_exported', false,
    'authority_effect', 'none',
    'money_movement', false,
    'rights_or_entitlements_granted', false,
    'vote_or_quorum_effect', false,
    'd3_performed', false
  )
);

do $$
declare
  v_status jsonb;
begin
  if (
    select count(*)
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
      and execution_state = 'retired'
      and external_task_id is null
      and metadata->>'historical_reference_only' = 'true'
      and metadata->>'dispatch_disabled' = 'true'
      and not (metadata ? 'canonical_parent_external_relay')
      and not (metadata ? 'legacy_external_task_id_retained_as_transport_alias')
      and not (metadata ? 'runtime_function')
      and not (metadata ? 'preflight_function')
      and not (metadata ? 'start_function')
  ) <> 7 then
    raise exception 'legacy scheduler archival verification failed: schedule rows are not fully historical-only';
  end if;

  if exists (
    select 1
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'chlom_runtime'
      and p.proname in (
        'agent_a_emergency_portfolio_cycle_v2',
        'agent_a_portfolio_preflight',
        'agent_a_start_portfolio_cycle'
      )
  ) then
    raise exception 'legacy scheduler archival verification failed: executable Agent A function remains';
  end if;

  if (
    select count(*)
    from chlom_runtime.automation_agent_bindings
    where binding_id in (
      'ct.automation.maintenance-coordinator.v1',
      'ct.automation.monthly-heartbeat.v1'
    )
      and task_enabled = false
      and architecture_state = 'retired'
      and external_task_id like 'archived-historical-only:%'
      and metadata->>'historical_reference_only' = 'true'
      and metadata->>'provider_task_identity_removed' = 'true'
  ) <> 2 then
    raise exception 'legacy scheduler archival verification failed: retired automation binding tombstones are incomplete';
  end if;

  if not exists (
    select 1
    from chlom_runtime.automation_agent_bindings
    where binding_id = 'ct.automation.vendor-engine-watch.v1'
      and task_enabled = true
      and architecture_state = 'bound'
      and external_task_id = '6a8620e935cc8191bbd31075e12dd22a'
      and not (metadata ? 'legacy_ABCDS_scheduler_roles')
      and metadata->'legacy_scheduler_scaffolding_archive'->>'state' = 'ARCHIVED_HISTORICAL_REFERENCE_ONLY'
  ) then
    raise exception 'legacy scheduler archival verification failed: canonical relay archive pointer is invalid';
  end if;

  if not exists (
    select 1
    from chlom_runtime.integrity_evidence_ledger
    where evidence_id = 'ct.evidence.legacy-abcds-scheduler-archive.2026-08-27.v1'
      and evidence_state = 'pass'
      and content_sha256 = 'e10160726509184aecce7f7e257c2deb9386d46962dcf66bdb6254fc11afa1d2'
  ) then
    raise exception 'legacy scheduler archival verification failed: append-only archive evidence is absent';
  end if;

  select public.crownthrive_scheduler_topology_status_v1()
  into v_status;

  if coalesce((v_status->>'production_topology_ready')::boolean, false) is not true then
    raise exception 'legacy scheduler archival verification failed: topology is not production-ready';
  end if;

  if coalesce((v_status->>'no_duplicate_clocks')::boolean, false) is not true then
    raise exception 'legacy scheduler archival verification failed: duplicate clock detected';
  end if;

  if not exists (
    select 1
    from chlom_runtime.agent_schedule_definitions
    where schedule_id = 'ct.schedule.external-evidence-relay.hourly.v1'
      and execution_state = 'active'
      and external_task_id = '6a8620e935cc8191bbd31075e12dd22a'
  ) then
    raise exception 'legacy scheduler archival verification failed: canonical external relay changed';
  end if;
end
$$;

commit;
