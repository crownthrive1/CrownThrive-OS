-- CrownThrive all-Pentas production-governed presence and PentaMocracy contract v1.
--
-- This migration institutionalizes the already deployed current-state model.
-- It never rewrites source maturity merely to manufacture specialist production.

create or replace function public.penta_all_production_contract_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog', 'integration_control', 'public', 'pentamocracy'
as $status$
select public.penta_all_production_status_v1()
  || jsonb_build_object(
    'contract_id', 'ct.penta.all-production-government.v1',
    'contract_version', '1.0.0',
    'source_evidence', (
      select coalesce(
        jsonb_agg(
          jsonb_build_object(
            'source_key', source_key,
            'source_type', source_type,
            'source_ref', source_ref,
            'precedence', precedence,
            'authority_scope', authority_scope,
            'observed_count', observed_count,
            'source_sha256', source_sha256,
            'evidence_sha256', evidence_sha256,
            'observed_at', observed_at
          )
          order by precedence desc
        ),
        '[]'::jsonb
      )
      from integration_control.penta_all_source_evidence_v1
      where current
    ),
    'canonical_scheduler', (
      select jsonb_build_object(
        'jobid', jobid,
        'jobname', jobname,
        'schedule', schedule,
        'command', command,
        'active', active
      )
      from cron.job
      where jobname = 'ct-penta-census-native-due-v1'
      order by jobid desc
      limit 1
    ),
    'source_maturity_preserved', true,
    'generic_presence_not_specialist_certification', true,
    'new_clock_created', false,
    'D3_human_reserved', true,
    'authority_created', false
  );
$status$;

grant execute on function public.penta_all_production_contract_status_v1()
  to anon, authenticated, service_role;

insert into public.penta_system_registry(
  system_key,
  canonical_name,
  category,
  purpose,
  authority_boundary,
  risk_ceiling,
  maturity,
  version,
  public_exposure,
  docs_ref,
  runtime_ref,
  metadata,
  last_verified_at,
  updated_at
) values
(
  'penta.government',
  'PentaMocracy Government',
  'governance',
  'Internal U.S.-federal-style branch, Congress, court, department, bureau, office, workforce, and membership model for all current Penta census entities.',
  'Internal D0-D2 coordination and representation only. Human ratification, CHLOM, provider, legal, rights, financial, and D3 authority remain independently required.',
  'D2',
  'production',
  '1.0.0',
  true,
  '/pentas/government',
  'public.penta_all_production_contract_status_v1()',
  jsonb_build_object(
    'branches', jsonb_build_array('executive', 'legislative', 'judicial'),
    'congress', jsonb_build_array('house-of-families', 'senate-of-systems'),
    'independent_establishments', true,
    'machine_votes_cannot_satisfy_human_ratification', true,
    'membership_creates_authority', false,
    'contract_ref', 'ct.penta.all-production-government.v1'
  ),
  now(),
  now()
),
(
  'penta.all-production',
  'All Pentas Production-Governed Presence',
  'institutional_runtime',
  'Maintains a real production citizen runtime, government assignment, records, help, documentation, readiness, and governed routing for every current registered Penta identity and system.',
  'Generic runtime has no dispatch authority. Specialist execution remains exact-runtime and evidence gated.',
  'D1',
  'production',
  '1.0.0',
  true,
  '/pentas/census/production-government-2026-08-30',
  'public.penta_citizen_runtime_v1(text,text,jsonb)',
  jsonb_build_object(
    'status_ref', 'public.penta_all_production_status_v1()',
    'generic_operations', jsonb_build_array(
      'status', 'describe', 'government', 'readiness', 'help', 'docs', 'route'
    ),
    'dispatch_authority', 'NONE',
    'source_maturity_preserved', true,
    'contract_ref', 'ct.penta.all-production-government.v1'
  ),
  now(),
  now()
)
on conflict(system_key) do update set
  canonical_name = excluded.canonical_name,
  category = excluded.category,
  purpose = excluded.purpose,
  authority_boundary = excluded.authority_boundary,
  risk_ceiling = excluded.risk_ceiling,
  maturity = excluded.maturity,
  version = excluded.version,
  public_exposure = excluded.public_exposure,
  docs_ref = excluded.docs_ref,
  runtime_ref = excluded.runtime_ref,
  metadata = public.penta_system_registry.metadata || excluded.metadata,
  last_verified_at = now(),
  updated_at = now();

update public.penta_system_registry
set metadata = metadata || case system_key
  when 'penta.census' then jsonb_build_object(
    'all_pentas_campaign', 'ct.campaign.all-pentas-production-government.v1',
    'scheduler_runtime', 'integration_control.penta_census_scheduler_tick_v2()',
    'all_sources', true,
    'D3_human_reserved', true
  )
  when 'penta.self' then jsonb_build_object(
    'all_pentas_campaign_status', 'public.penta_all_production_status_v1()',
    'safe_handoff_retry_until_verified', true,
    'routed_is_not_completed', true
  )
  when 'penta.docs' then jsonb_build_object(
    'government_docs', '/pentas/government',
    'all_pentas_census_docs', '/pentas/census/production-government-2026-08-30'
  )
  when 'penta.scribe' then jsonb_build_object(
    'all_source_evidence_table', 'integration_control.penta_all_source_evidence_v1',
    'campaign_record', 'integration_control.penta_production_campaigns_v1'
  )
  when 'penta.build' then jsonb_build_object(
    'census_mobilization_target', 'ct.penta.factory.software',
    'completion_requires_exact_build_evidence', true
  )
  when 'penta.wire' then jsonb_build_object(
    'census_mobilization_target', 'ct.penta.wire',
    'completion_requires_exact_adapter_readback', true
  )
  when 'penta.certify' then jsonb_build_object(
    'census_mobilization_target', 'ct.penta.certify',
    'completion_requires_exact_case_evidence', true
  )
  when 'penta.release' then jsonb_build_object(
    'census_mobilization_target', 'ct.penta.release',
    'completion_requires_provider_readback', true
  )
  when 'penta.workforce' then jsonb_build_object(
    'government_assignment_table', 'integration_control.penta_government_assignments_v1',
    'membership_authority_effect', false
  )
  else '{}'::jsonb
end,
updated_at = now()
where system_key in (
  'penta.census',
  'penta.self',
  'penta.docs',
  'penta.scribe',
  'penta.build',
  'penta.wire',
  'penta.certify',
  'penta.release',
  'penta.workforce'
);

do $certification$
declare
  v_identities integer;
  v_systems integer;
  v_census integer;
  v_identity_presence integer;
  v_system_presence integer;
  v_assignments integer;
  v_memberships integer;
  v_d3_invalid integer;
  v_scheduler integer;
begin
  select count(*) into v_identities
  from integration_control.penta_identity_registry_v1
  where current;

  select count(*) into v_systems
  from public.penta_system_registry
  where system_key not in ('penta.government', 'penta.all-production');

  select count(*) into v_census
  from integration_control.penta_census_entities_v1
  where current;

  select count(*) into v_identity_presence
  from integration_control.penta_production_presence_v1
  where subject_kind = 'identity';

  select count(*) into v_system_presence
  from integration_control.penta_production_presence_v1
  where subject_kind = 'system';

  select count(*) into v_assignments
  from integration_control.penta_government_assignments_v1
  where state = 'active';

  select count(*) into v_memberships
  from public.penta_governance_memberships
  where (ends_at is null or ends_at > now())
    and voting_status in ('eligible', 'nonvoting');

  select count(*) into v_d3_invalid
  from integration_control.penta_census_handoffs_v1
  where risk_class = 'D3'
    and state <> 'approval_required';

  select count(*) into v_scheduler
  from cron.job
  where jobname = 'ct-penta-census-native-due-v1'
    and active
    and schedule = '3-58/5 * * * *'
    and command = 'select integration_control.penta_census_scheduler_tick_v2();';

  if v_identities < 462 then
    raise exception 'PENTA_IDENTITY_CENSUS_REGRESSED';
  end if;

  if v_systems < 473 then
    raise exception 'PENTA_SYSTEM_CENSUS_REGRESSED';
  end if;

  if v_census < 1024 then
    raise exception 'PENTA_CURRENT_CENSUS_REGRESSED';
  end if;

  if v_identity_presence <> v_identities then
    raise exception 'PENTA_IDENTITY_PRODUCTION_PRESENCE_INCOMPLETE';
  end if;

  if v_system_presence < v_systems then
    raise exception 'PENTA_SYSTEM_PRODUCTION_PRESENCE_INCOMPLETE';
  end if;

  if v_assignments <> v_census then
    raise exception 'PENTA_GOVERNMENT_ASSIGNMENT_INCOMPLETE';
  end if;

  if v_memberships < v_census * 2 then
    raise exception 'PENTA_GOVERNMENT_MEMBERSHIP_INCOMPLETE';
  end if;

  if v_d3_invalid <> 0 then
    raise exception 'PENTA_D3_HUMAN_RESERVED_BOUNDARY_VIOLATED';
  end if;

  if v_scheduler <> 1 then
    raise exception 'PENTA_CANONICAL_CENSUS_SCHEDULER_NOT_EXACT';
  end if;

  if exists (
    select 1
    from integration_control.penta_production_presence_v1
    where production_mode = 'candidate_fail_closed'
      and specialist_execution_eligible
  ) then
    raise exception 'PENTA_CANDIDATE_SPECIALIST_AUTHORITY_MANUFACTURED';
  end if;
end
$certification$;
