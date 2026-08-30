-- CrownThrive PentaSELF Surgical Care production contract v1
--
-- This migration is the forward-only institutional binding for the already
-- certified hard-repair substrate. It intentionally does not create another
-- scheduler. The existing canonical PentaSELF tick owns both surgery and
-- exact-head PR closure lanes.

create schema if not exists penta_scribe;
create schema if not exists penta_docs;

create or replace view public.penta_docs_hard_repair_reports_v1 as
select
  report_id,
  case_id,
  slug,
  title,
  summary,
  body,
  importance,
  body_sha256,
  docs_path,
  published_at,
  updated_at
from penta_docs.repair_reports_v1
where audience = 'public'
  and publication_state = 'published';

grant select on public.penta_docs_hard_repair_reports_v1
  to anon, authenticated, service_role;

do $contract$
declare
  v_case_id uuid;
  v_case_sha text;
  v_passes integer;
  v_source_ref constant text := 'ct.pentaself.surgical-care-family.production.v1';
begin
  if to_regclass('penta_self.hard_repair_handlers_v1') is null
     or to_regclass('penta_self.hard_repair_cases_v1') is null
     or to_regclass('penta_self.hard_repair_attempts_v1') is null
     or to_regclass('penta_self.hard_repair_certifications_v1') is null
     or to_regclass('penta_self.hard_repair_pr_links_v1') is null
     or to_regclass('penta_scribe.repair_charts_v1') is null
     or to_regclass('penta_docs.repair_reports_v1') is null then
    raise exception 'PENTASELF_HARD_REPAIR_SUBSTRATE_MISSING';
  end if;

  if to_regprocedure('penta_self.hard_repair_cycle_v1(uuid)') is null
     or to_regprocedure('penta_self.hard_repair_queue_tick_v1(integer)') is null
     or to_regprocedure('penta_self.hard_repair_pr_tick_v1(integer)') is null
     or to_regprocedure('penta_self.hard_repair_pr_merge_gate_v1(uuid)') is null
     or to_regprocedure('penta_dnd.hard_repair_contract_test_v1(uuid)') is null
     or to_regprocedure('penta_scribe.repair_chart_append_v1(uuid,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,text)') is null
     or to_regprocedure('penta_docs.repair_report_project_v1(uuid)') is null then
    raise exception 'PENTASELF_HARD_REPAIR_RUNTIME_MISSING';
  end if;

  select case_id
    into v_case_id
  from penta_self.hard_repair_cases_v1
  where case_key = 'ct.canary.pentaself.hard-repair.surgery.v1'
    and state = 'discharged';

  if v_case_id is null then
    raise exception 'PENTASELF_HARD_REPAIR_CANARY_NOT_DISCHARGED';
  end if;

  v_case_sha := penta_self.hard_repair_case_sha256_v1(v_case_id);

  select count(*)
    into v_passes
  from penta_self.hard_repair_certifications_v1
  where case_id = v_case_id
    and disposition = 'pass'
    and verifier_system_key in ('penta.dnd', 'penta.certify')
    and exact_case_sha256 = v_case_sha;

  if v_passes <> 2 then
    raise exception 'PENTASELF_HARD_REPAIR_INDEPENDENT_CERTIFICATION_MISSING';
  end if;

  if not exists (
    select 1
    from penta_self.hard_repair_cases_v1
    where case_id = v_case_id
      and rollback_count = 1
      and immediate_retry_count = 1
      and certification_state = 'pass'
  ) then
    raise exception 'PENTASELF_HARD_REPAIR_CANARY_SEQUENCE_INCOMPLETE';
  end if;

  insert into integration_control.penta_family_runtime_v1(
    family_key,
    canonical_name,
    job_role,
    member_count,
    runtime_state,
    activation_state,
    certification_state,
    labels,
    metadata,
    updated_at
  ) values (
    'SURGICAL_CARE',
    'Penta Surgical Care Family',
    'Coordinate bounded hard-repair surgery, structured operational charting, post-operation rounds, independent certification, documentation and exact-head release closure.',
    3,
    'PRODUCTION',
    'ACTIVE',
    'CERTIFIED_PRODUCTION',
    array[
      'penta:family',
      'family:surgical_care',
      'activation:active',
      'runtime:production',
      'certification:certified-production',
      'rollback:regression-only',
      'retry:bounded-one'
    ],
    jsonb_build_object(
      'members', jsonb_build_array('penta.surgeon', 'penta.chart', 'penta.rounds'),
      'collaborators', jsonb_build_array(
        'penta.self',
        'penta.scribe',
        'penta.docs',
        'penta.dnd',
        'penta.certify',
        'penta.pr',
        'penta.merge',
        'penta.closer'
      ),
      'runtime_ref', 'penta_self.hard_repair_queue_tick_v1(integer)',
      'pr_runtime_ref', 'penta_self.hard_repair_pr_tick_v1(integer)',
      'status_ref', 'public.penta_self_hard_repair_status_v1()',
      'canary_case_id', v_case_id,
      'canary_case_sha256', v_case_sha,
      'rollback_rule', 'surgery_caused_regression_only',
      'immediate_retry_limit', 1,
      'existing_pentaself_tick_extended', true,
      'new_clock_created', false,
      'originator_self_certification', false,
      'originator_self_vote_counted', false,
      'direct_main', false,
      'authority_created', false,
      'd3_human_reserved', true,
      'source_ref', v_source_ref
    ),
    now()
  )
  on conflict(family_key) do update set
    canonical_name = excluded.canonical_name,
    job_role = excluded.job_role,
    runtime_state = excluded.runtime_state,
    activation_state = excluded.activation_state,
    certification_state = excluded.certification_state,
    labels = excluded.labels,
    metadata = integration_control.penta_family_runtime_v1.metadata || excluded.metadata,
    updated_at = now();

  update integration_control.penta_family_runtime_v1
  set member_count = member_count,
      updated_at = now()
  where family_key = 'SURGICAL_CARE';

  update public.penta_system_registry
  set version = case when system_key = 'penta.self' then '1.1.0' else version end,
      metadata = metadata || case system_key
        when 'penta.self' then jsonb_build_object(
          'hard_repair_lifecycle', 'ct.penta.self.hard-repair.v1',
          'surgical_care_family', 'SURGICAL_CARE',
          'hard_repair_tick', 'penta_self.hard_repair_queue_tick_v1(integer)',
          'hard_repair_pr_tick', 'penta_self.hard_repair_pr_tick_v1(integer)',
          'rollback_rule', 'surgery_caused_regression_only',
          'immediate_retry_limit', 1,
          'originator_self_certification', false,
          'direct_main', false,
          'new_clock_created', false,
          'canary_case_sha256', v_case_sha
        )
        when 'penta.scribe' then jsonb_build_object(
          'repair_chart_runtime', 'penta_scribe.repair_chart_append_v1',
          'clinical_style_operational_not_medical', true,
          'canary_case_sha256', v_case_sha
        )
        when 'penta.docs' then jsonb_build_object(
          'hard_repair_internal_section', '/internal/pentaself/hard-repairs',
          'hard_repair_public_section', '/pentaself/hard-repairs',
          'public_view', 'public.penta_docs_hard_repair_reports_v1',
          'canary_case_sha256', v_case_sha
        )
        when 'penta.dnd' then jsonb_build_object(
          'hard_repair_program', 'ct.program.pentaself-hard-repair-dnd',
          'hard_repair_test', 'penta_dnd.hard_repair_contract_test_v1',
          'canary_case_sha256', v_case_sha
        )
        when 'penta.pr' then jsonb_build_object(
          'hard_repair_exact_head_gate', 'penta_self.hard_repair_pr_merge_gate_v1(uuid)',
          'hard_repair_promotion', 'penta_self.hard_repair_pr_promote_v1(uuid)',
          'originator_self_vote_counted', false
        )
        when 'penta.merge' then jsonb_build_object(
          'hard_repair_automerge_executor', true,
          'self_approval', false,
          'direct_main', false
        )
        when 'penta.closer' then jsonb_build_object(
          'hard_repair_close_requires', jsonb_build_array(
            'provider_readback',
            'docs_complete',
            'exact_head'
          )
        )
        else '{}'::jsonb
      end,
      updated_at = now()
  where system_key in (
    'penta.self',
    'penta.scribe',
    'penta.docs',
    'penta.dnd',
    'penta.pr',
    'penta.merge',
    'penta.closer'
  );
end
$contract$;

create or replace function public.penta_self_hard_repair_contract_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog', 'penta_self', 'penta_scribe', 'penta_docs', 'integration_control', 'public'
as $status$
select jsonb_build_object(
  'contract_id', 'ct.penta.self.hard-repair.v1',
  'version', '1.0.0',
  'state', case
    when to_regprocedure('penta_self.hard_repair_cycle_v1(uuid)') is not null
      and to_regprocedure('penta_self.hard_repair_pr_merge_gate_v1(uuid)') is not null
      and exists (
        select 1
        from integration_control.penta_family_runtime_v1
        where family_key = 'SURGICAL_CARE'
          and runtime_state = 'PRODUCTION'
          and activation_state = 'ACTIVE'
          and certification_state = 'CERTIFIED_PRODUCTION'
      )
    then 'PASS'
    else 'HOLD'
  end,
  'family', 'SURGICAL_CARE',
  'members', jsonb_build_array('PentaSurgeon', 'PentaChart', 'PentaRounds'),
  'active_handlers', (
    select count(*)
    from penta_self.hard_repair_handlers_v1
    where state = 'active'
  ),
  'case_states', (
    select coalesce(jsonb_object_agg(state, n), '{}'::jsonb)
    from (
      select state, count(*) as n
      from penta_self.hard_repair_cases_v1
      group by state
    ) s
  ),
  'charts', (select count(*) from penta_scribe.repair_charts_v1),
  'internal_reports', (
    select count(*)
    from penta_docs.repair_reports_v1
    where audience = 'internal'
      and publication_state = 'published'
  ),
  'public_reports', (
    select count(*)
    from penta_docs.repair_reports_v1
    where audience = 'public'
      and publication_state = 'published'
  ),
  'maximum_risk_class', 'D2',
  'd3_human_reserved', true,
  'rollback_rule', 'surgery_caused_regression_only',
  'immediate_retry_limit', 1,
  'originator_self_certification', false,
  'originator_self_vote_counted', false,
  'direct_main', false,
  'new_clock_created', false,
  'observed_at', clock_timestamp()
);
$status$;

grant execute on function public.penta_self_hard_repair_contract_status_v1()
  to anon, authenticated, service_role;
