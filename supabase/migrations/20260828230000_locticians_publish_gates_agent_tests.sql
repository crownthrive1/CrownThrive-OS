-- Locticians / Brilliant Directories governed article publishing closure.
-- Public offer claims are narrowed to evidence actually visible on Locticians.
-- Article publishing remains fail-closed until site-specific data_id plus article write/readback/rollback canaries pass.

update crm.offer_registry
set public_evidence_state = 'verified',
    public_copy = 'Claimable listings only: use CLAIMMONTH50 for 50% off Community+ Member or Basic at checkout. Exact eligibility and terms are shown at checkout.',
    evidence = coalesce(evidence, '{}'::jsonb) || jsonb_build_object(
      'resolved_public_scope', jsonb_build_object(
        'state', 'verified',
        'plans', jsonb_build_array('Community+ Member', 'Basic'),
        'claimable_listings_only', true,
        'source', 'https://locticians.com/join',
        'resolved_at', now(),
        'resolution_rule', 'public marketing scope follows independently visible public evidence; broader founder/admin configuration is retained as backend evidence only'
      ),
      'checkout_claim_policy', jsonb_build_object(
        'checkout_verification_state', checkout_verification_state,
        'prohibited_until_verified', jsonb_build_array('all plans', 'higher-tier savings', 'lifetime discount', 'guaranteed recurring duration')
      )
    ),
    updated_at = now()
where offer_key = 'locticians.claimmonth50.v1';

insert into integration_control.site_publish_routes (
  route_id,
  surface_id,
  platform_id,
  adapter_id,
  route_state,
  auto_publish_if_release_pass,
  quarantine_on_nonpass,
  require_read_after_write,
  require_rollback_ref,
  allowed_subject_types,
  feed_consumer_state,
  metadata
)
values (
  'ct.route.locticians.bd-articles.production.v1',
  'ct.surface.locticians.production',
  'ct.platform.locticians',
  'ct.adapter.brilliant-directories.locticians.v1',
  'hold',
  false,
  true,
  true,
  true,
  '["article","community_article","sponsored_article"]'::jsonb,
  'pending',
  jsonb_build_object(
    'contract', 'ct.integration.locticians-publishing-control.v1',
    'publisher_agent_id', 'ct.pentamarketer.agent.publisher',
    'publisher_persona_id', 'ct.persona.locticians.publisher.kiara.v1',
    'provider_create_path', '/api/v2/data_posts/create',
    'provider_read_path_template', '/api/v2/data_posts/get/{post_id}',
    'provider_identifiers', jsonb_build_object(
      'user_id', 7569,
      'user_id_state', 'candidate_from_verified_bounded_member_write_not_article_canary_verified',
      'data_id', null,
      'data_id_state', 'unresolved_site_specific_post_type_identifier',
      'data_type', 20,
      'data_type_state', 'documented_single_image_post_contract'
    ),
    'image_rights_gate', jsonb_build_object(
      'required_when_image_present', true,
      'rights_state_required', 'verified',
      'rights_basis_required', true,
      'provenance_ref_required', true,
      'source_ref_required', true,
      'alt_text_required', true,
      'accepted_rights_bases', jsonb_build_array('owned','licensed','public_domain','provider_permitted'),
      'missing_or_unverified_action', 'quarantine'
    ),
    'open_requirements', jsonb_build_array(
      'verify publisher user_id for article lane',
      'discover exact site-specific article data_id',
      'pass data_posts create canary',
      'pass exact post_id read-after-write',
      'pass rollback canary',
      'preserve CHLOM release and rights gates'
    ),
    'provider_last_known_article_create_status', 405,
    'provider_last_known_article_create_state', 'blocked',
    'reason_for_hold', 'site-specific data_id and article-specific write/readback/rollback evidence are incomplete'
  )
)
on conflict (surface_id, adapter_id) do update
set platform_id = excluded.platform_id,
    route_state = 'hold',
    auto_publish_if_release_pass = false,
    quarantine_on_nonpass = true,
    require_read_after_write = true,
    require_rollback_ref = true,
    allowed_subject_types = excluded.allowed_subject_types,
    feed_consumer_state = 'pending',
    metadata = integration_control.site_publish_routes.metadata || excluded.metadata,
    updated_at = now();

create table if not exists crm.penta_persona_publish_test_runs_v1 (
  run_id uuid primary key default gen_random_uuid(),
  expected_personas integer not null,
  observed_personas integer not null,
  total_tests integer not null default 0,
  passed_tests integer not null default 0,
  hold_tests integer not null default 0,
  failed_tests integer not null default 0,
  overall_state text not null default 'running' check (overall_state in ('running','pass','hold','failed')),
  metadata jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists crm.penta_persona_publish_test_results_v1 (
  run_id uuid not null references crm.penta_persona_publish_test_runs_v1(run_id) on delete cascade,
  persona_id text not null,
  agent_id text,
  test_key text not null,
  status text not null check (status in ('pass','hold','fail')),
  details jsonb not null default '{}'::jsonb,
  tested_at timestamptz not null default now(),
  primary key (run_id, persona_id, test_key)
);

create index if not exists penta_persona_publish_test_results_persona_idx
  on crm.penta_persona_publish_test_results_v1(persona_id, tested_at desc);

create or replace function crm.run_penta_persona_publish_tests_v1()
returns uuid
language plpgsql
security invoker
set search_path = crm, integration_control, public
as $$
declare
  v_run_id uuid := gen_random_uuid();
  v_expected integer := 39;
  v_observed integer;
  v_total integer;
  v_pass integer;
  v_hold integer;
  v_fail integer;
begin
  select count(*) into v_observed from crm.penta_marketer_personas_v1;

  insert into crm.penta_persona_publish_test_runs_v1(run_id, expected_personas, observed_personas, metadata)
  values (
    v_run_id,
    v_expected,
    v_observed,
    jsonb_build_object(
      'contract', 'ct.integration.locticians-publishing-control.v1',
      'route_id', 'ct.route.locticians.bd-articles.production.v1',
      'offer_ref', 'locticians.claimmonth50.v1'
    )
  );

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'persona_registry_active',
         case when lower(coalesce(p.state,'')) in ('active','approved','production','enabled') then 'pass' else 'fail' end,
         jsonb_build_object('persona_state', p.state)
  from crm.penta_marketer_personas_v1 p
  left join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id;

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'agent_enabled',
         case when coalesce(a.enabled,false) then 'pass' else 'fail' end,
         jsonb_build_object('enabled', coalesce(a.enabled,false), 'agent_state', a.state)
  from crm.penta_marketer_personas_v1 p
  left join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id;

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'execution_readback_required',
         case when coalesce(cap.cap_count,0) > 0 and coalesce(cap.all_require_readback,false) then 'pass' else 'fail' end,
         jsonb_build_object('enabled_capability_count', coalesce(cap.cap_count,0), 'all_require_readback', coalesce(cap.all_require_readback,false))
  from crm.penta_marketer_personas_v1 p
  left join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id
  left join lateral (
    select count(*) as cap_count, bool_and(c.requires_readback) as all_require_readback
    from crm.penta_persona_execution_capabilities_v1 c
    where c.persona_id = p.persona_id and c.enabled
  ) cap on true;

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'publication_authority_boundary',
         case
           when p.persona_id = 'ct.persona.locticians.publisher.kiara.v1'
             then case when a.agent_id = 'ct.pentamarketer.agent.publisher' and a.enabled and coalesce(a.risk_ceiling,'') in ('D0','D1','D2') then 'pass' else 'fail' end
           when not exists (
             select 1
             from crm.penta_persona_execution_capabilities_v1 c
             where c.persona_id = p.persona_id
               and c.enabled
               and (
                 lower(coalesce(c.capability_key,'')) like '%data_posts%'
                 or lower(coalesce(c.capability_key,'')) like '%brilliant%'
                 or lower(coalesce(c.handler_key,'')) like '%data_posts%'
                 or lower(coalesce(c.handler_key,'')) like '%brilliant%'
               )
           ) then 'pass'
           else 'fail'
         end,
         jsonb_build_object(
           'designated_publisher', p.persona_id = 'ct.persona.locticians.publisher.kiara.v1',
           'direct_provider_write_for_nonpublisher_prohibited', true,
           'publication_request_is_not_provider_authority', true
         )
  from crm.penta_marketer_personas_v1 p
  left join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id;

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'offer_public_claim_gate',
         case when o.offer_key is not null
                    and o.public_evidence_state = 'verified'
                    and o.public_copy ilike '%Community+ Member%'
                    and o.public_copy ilike '%Basic%'
                    and o.public_copy ilike '%Claimable listings only%'
                    and o.public_copy not ilike '%all plans%'
                    and o.public_copy not ilike '%recurring membership payments%'
              then 'pass' else 'fail' end,
         jsonb_build_object(
           'offer_ref', o.offer_key,
           'public_evidence_state', o.public_evidence_state,
           'checkout_verification_state', o.checkout_verification_state,
           'claim_scope', jsonb_build_array('Community+ Member','Basic'),
           'checkout_pending_does_not_authorize_broader_claims', true
         )
  from crm.penta_marketer_personas_v1 p
  left join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id
  left join crm.offer_registry o on o.offer_key = 'locticians.claimmonth50.v1';

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'locticians_route_safety_gate',
         case when r.route_id is not null
                    and r.route_state in ('hold','active')
                    and r.quarantine_on_nonpass
                    and r.require_read_after_write
                    and r.require_rollback_ref
                    and coalesce((r.metadata #>> '{image_rights_gate,required_when_image_present}')::boolean,false)
              then 'pass' else 'fail' end,
         jsonb_build_object(
           'route_id', r.route_id,
           'route_state', r.route_state,
           'auto_publish_if_release_pass', r.auto_publish_if_release_pass,
           'requires_image_rights_gate', true,
           'requires_read_after_write', r.require_read_after_write,
           'requires_rollback_ref', r.require_rollback_ref
         )
  from crm.penta_marketer_personas_v1 p
  left join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id
  left join integration_control.site_publish_routes r
    on r.surface_id = 'ct.surface.locticians.production'
   and r.adapter_id = 'ct.adapter.brilliant-directories.locticians.v1';

  insert into crm.penta_persona_publish_test_results_v1(run_id, persona_id, agent_id, test_key, status, details)
  select v_run_id, p.persona_id, a.agent_id, 'bd_article_provider_open_gate',
         case
           when r.route_state = 'active'
            and nullif(r.metadata #>> '{provider_identifiers,data_id}','') is not null
            and (r.metadata #>> '{provider_identifiers,user_id_state}') = 'article_canary_verified'
            and ad.write_canary_state = 'pass'
            and ad.read_after_write_state = 'pass'
            and ad.rollback_canary_state = 'pass'
           then 'pass'
           else 'hold'
         end,
         jsonb_build_object(
           'route_state', r.route_state,
           'data_id', r.metadata #> '{provider_identifiers,data_id}',
           'user_id_state', r.metadata #>> '{provider_identifiers,user_id_state}',
           'write_canary_state', ad.write_canary_state,
           'read_after_write_state', ad.read_after_write_state,
           'rollback_canary_state', ad.rollback_canary_state,
           'hold_is_fail_closed_not_failure', true
         )
  from crm.penta_marketer_personas_v1 p
  join crm.penta_marketer_agents_v2 a on a.persona_id = p.persona_id
  left join integration_control.site_publish_routes r
    on r.surface_id = 'ct.surface.locticians.production'
   and r.adapter_id = 'ct.adapter.brilliant-directories.locticians.v1'
  left join integration_control.site_provider_adapters ad
    on ad.adapter_id = 'ct.adapter.brilliant-directories.locticians.v1'
  where p.persona_id = 'ct.persona.locticians.publisher.kiara.v1';

  select count(*), count(*) filter (where status='pass'), count(*) filter (where status='hold'), count(*) filter (where status='fail')
  into v_total, v_pass, v_hold, v_fail
  from crm.penta_persona_publish_test_results_v1
  where run_id = v_run_id;

  update crm.penta_persona_publish_test_runs_v1
  set total_tests = v_total,
      passed_tests = v_pass,
      hold_tests = v_hold,
      failed_tests = v_fail,
      overall_state = case when v_fail > 0 then 'failed' when v_hold > 0 then 'hold' else 'pass' end,
      completed_at = now()
  where run_id = v_run_id;

  return v_run_id;
end;
$$;

comment on function crm.run_penta_persona_publish_tests_v1() is
'Runs the production-safe publication contract suite for every active PentaMarketer persona. A provider hold is recorded as HOLD, never silently promoted to PASS.';

select crm.run_penta_persona_publish_tests_v1();
