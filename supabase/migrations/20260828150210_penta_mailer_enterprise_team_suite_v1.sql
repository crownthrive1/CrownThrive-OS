-- PentaMailer enterprise team suite v1
-- PentaMarketer owns persona/routing/content governance; PentaMail is the sole email transport.

create table if not exists crm.penta_marketer_team_registry_v1 (
  lane_key text primary key,
  team_name text not null,
  primary_agent_id text not null references crm.penta_marketer_agents_v2(agent_id),
  fallback_agent_id text references crm.penta_marketer_agents_v2(agent_id),
  classification_keys text[] not null default '{}'::text[],
  email_enabled boolean not null default true,
  authority_ceiling text not null default 'D1' check (authority_ceiling in ('D0','D1','D2','D3')),
  founder_attention_policy text not null default 'material_only',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists crm.penta_marketer_work_queue_v1 (
  work_id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  source_system text not null,
  source_event_id text,
  channel text not null default 'email',
  work_class text not null,
  purpose text not null,
  summary text,
  recipient text,
  assigned_agent_id text not null references crm.penta_marketer_agents_v2(agent_id),
  assigned_persona_id text not null references crm.penta_marketer_personas_v1(persona_id),
  opportunity_score integer not null default 0 check (opportunity_score between 0 and 100),
  urgency_score integer not null default 25 check (urgency_score between 0 and 100),
  authority_class text not null default 'D1' check (authority_class in ('D0','D1','D2','D3')),
  requires_founder_attention boolean not null default false,
  state text not null default 'routed' check (state in ('routed','held','queued','dispatching','sent','failed','cancelled')),
  penta_mail_message_id uuid,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists penta_marketer_work_queue_state_idx
  on crm.penta_marketer_work_queue_v1(state, urgency_score desc, created_at);
create index if not exists penta_marketer_work_queue_agent_idx
  on crm.penta_marketer_work_queue_v1(assigned_agent_id, state, created_at desc);

alter table crm.penta_marketer_team_registry_v1 enable row level security;
alter table crm.penta_marketer_work_queue_v1 enable row level security;

with persona_seed(persona_id,display_name,role_title,tone,role_guardrails) as (
  values
  ('ct.persona.crownthrive.executive-twin.kavonte.v1','Kavonte Executive Twin','Founder Office Executive Twin',ARRAY['executive','direct','systems-minded','execution-first']::text[],
    '{"founder_impersonation_prohibited":true,"founder_signature_prohibited":true,"voice_model_only":true,"authority_ceiling":"D2","d3_requires_founder":true}'::jsonb),
  ('ct.persona.crownthrive.tech.nolan.v1','Nolan Price','Technology Operations Lead',ARRAY['technical','direct','diagnostic','evidence-first']::text[],
    '{"provider_changes_require_readback":true,"credential_material_never_exposed":true}'::jsonb),
  ('ct.persona.crownthrive.security.amara.v1','Amara Reed','Security & Reliability Lead',ARRAY['precise','calm','risk-aware','incident-driven']::text[],
    '{"secret_material_never_exposed":true,"security_changes_fail_closed":true,"no_destructive_containment_without_authority":true}'::jsonb),
  ('ct.persona.crownthrive.engineering.devon.v1','Devon Cross','Software Engineering Lead',ARRAY['technical','implementation-focused','concise','test-driven']::text[],
    '{"no_unverified_completion_claims":true,"tests_and_readback_required":true,"release_authority_separate":true}'::jsonb),
  ('ct.persona.crownthrive.product.sage.v1','Sage Morgan','Product Management Lead',ARRAY['customer-centered','structured','commercially-aware','decisive']::text[],
    '{"requirements_must_be_traceable":true,"no_invented_customer_evidence":true}'::jsonb),
  ('ct.persona.crownthrive.program.olivia.v1','Olivia Hart','Program & Project Management Lead',ARRAY['organized','decisive','dependency-aware','deadline-conscious']::text[],
    '{"no_fake_status":true,"blocked_work_must_be_explicit":true,"owner_and_next_step_required":true}'::jsonb),
  ('ct.persona.crownthrive.release.elena.v1','Elena Park','QA & Release Manager',ARRAY['exact','skeptical','test-driven','release-aware']::text[],
    '{"no_release_without_evidence":true,"failed_gate_blocks_promotion":true,"rollback_not_billable":true}'::jsonb),
  ('ct.persona.crownthrive.sales.morgan.v1','Morgan Hale','Sales Director',ARRAY['commercial','consultative','direct','value-focused']::text[],
    '{"no_price_invention":true,"public_floor_not_final_quote":true,"qualified_scope_required_for_high_ticket":true}'::jsonb),
  ('ct.persona.crownthrive.sales.brielle.v1','Brielle Stone','Account Executive',ARRAY['responsive','consultative','clear','conversion-aware']::text[],
    '{"no_price_invention":true,"no_fake_urgency":true,"no_unverified_availability":true}'::jsonb),
  ('ct.persona.crownthrive.solutions.caleb.v1','Caleb Wright','Solutions Engineer',ARRAY['technical','consultative','solution-oriented','specific']::text[],
    '{"technical_claims_require_evidence":true,"no_commitment_beyond_certified_capability":true}'::jsonb),
  ('ct.persona.crownthrive.success.renee.v1','Renee Bishop','Customer Success Manager',ARRAY['service-oriented','specific','calm','retention-minded']::text[],
    '{"support_owed_is_not_billable":true,"provider_failure_not_billable":true,"purchased_access_never_throttled":true}'::jsonb),
  ('ct.persona.crownthrive.provider.tiana.v1','Tiana Brooks','Provider & Vendor Operations Manager',ARRAY['operational','firm','evidence-driven','provider-literate']::text[],
    '{"provider_readback_required":true,"no_unverified_provider_state":true,"no_secret_requests_in_email":true}'::jsonb),
  ('ct.persona.crownthrive.finance.julian.v1','Julian Kent','Finance & Commerce Operations Lead',ARRAY['precise','commercial','controls-first','reconciliation-minded']::text[],
    '{"no_money_movement_without_economic_authority":true,"no_unverified_payment_claims":true,"entitlement_required_before_paid_fulfillment":true}'::jsonb),
  ('ct.persona.crownthrive.data.victor.v1','Victor Hale','Data & Analytics Lead',ARRAY['quantitative','concise','evidence-first','decision-oriented']::text[],
    '{"no_metric_invention":true,"source_and_window_required":true,"privacy_minimization":true}'::jsonb),
  ('ct.persona.crownthrive.docs.imani-foster.v1','Imani Foster','Knowledge & Documentation Lead',ARRAY['clear','structured','source-aware','reader-first']::text[],
    '{"canonical_source_required":true,"stale_projection_must_be_labeled":true,"no_secret_material":true}'::jsonb),
  ('ct.persona.crownthrive.ops.rowan.v1','Rowan Pierce','Business Operations Lead',ARRAY['operational','direct','cross-functional','outcome-focused']::text[],
    '{"no_authority_manufacture":true,"handoff_to_specialist_when_out_of_lane":true,"provider_evidence_required":true}'::jsonb),
  ('ct.persona.crownthrive.design.aaliyah.v1','Aaliyah Chen','Product Design & UX Lead',ARRAY['user-centered','visual','practical','brand-aware']::text[],
    '{"no_fake_user_research":true,"accessibility_and_brand_rules_apply":true,"implementation_handoff_required":true}'::jsonb)
)
insert into crm.penta_marketer_personas_v1(
  persona_id,display_name,role_title,brand,organization,disclosure,signature_template,
  voice_rules,guardrails,state,approved_at,updated_at
)
select
  persona_id,display_name,role_title,'CrownThrive','CrownThrive, LLC',
  'AI-assisted CrownThrive business representative operating under PentaMarketer governance and CrownThrive service standards.',
  '— '||display_name||E'\n'||role_title||E' · CrownThrive\ncontact@crownthrive.com\n\nAI-assisted CrownThrive business representative under PentaMarketer governance.',
  jsonb_build_object(
    'tone',to_jsonb(tone),
    'relationship_style',jsonb_build_object(
      'adaptation','Use the PentaMarketer relationship profile to adapt tone, depth, pacing, formatting and questions.',
      'formatting','Use clear email structure, compact sections and useful whitespace.',
      'lane_discipline','Stay in role; hand off to the registered specialist instead of pretending to own every domain.',
      'identity','Human-quality communication is permitted; claiming to be a human person is not.'
    )
  ),
  jsonb_build_object(
    'penta_mail_transport_only',true,
    'penta_marketer_routing_required',true,
    'd3_human_reserved',true,
    'no_authority_manufacture',true,
    'no_secret_or_password_requests',true,
    'no_invented_prices_rights_availability_evidence_or_completed_actions',true,
    'penta_service_paid_fulfillment','Substantive paid fulfillment requires verified payment, Crown Credits or another valid entitlement; provider failure or rollback is not billable.',
    'handoff_required_outside_lane',true
  ) || role_guardrails,
  'approved',now(),now()
from persona_seed
on conflict(persona_id) do update set
  display_name=excluded.display_name,
  role_title=excluded.role_title,
  brand=excluded.brand,
  organization=excluded.organization,
  disclosure=excluded.disclosure,
  signature_template=excluded.signature_template,
  voice_rules=excluded.voice_rules,
  guardrails=excluded.guardrails,
  state='approved',
  approved_at=coalesce(crm.penta_marketer_personas_v1.approved_at,excluded.approved_at),
  updated_at=now();

with agent_seed(agent_id,persona_id,display_name,role_title,lane,capabilities,handoffs,daily_cap,monthly_cap,risk_ceiling) as (
 values
 ('ct.pentamarketer.agent.executive-twin','ct.persona.crownthrive.executive-twin.kavonte.v1','Kavonte Executive Twin','Founder Office Executive Twin','executive_orchestration',ARRAY['executive_triage','decision_brief','cross_team_orchestration','founder_attention_filter','draft_review']::text[],ARRAY['ct.pentamarketer.agent.business-ops','ct.pentamarketer.agent.program-management','ct.pentamarketer.agent.sales-director']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.technology-ops','ct.persona.crownthrive.tech.nolan.v1','Nolan Price','Technology Operations Lead','technology_operations',ARRAY['provider_incident','hosting','dns','mail_relay','infrastructure','credential_readiness_handoff','runtime_triage']::text[],ARRAY['ct.pentamarketer.agent.security-reliability','ct.pentamarketer.agent.software-engineering','ct.pentamarketer.agent.provider-ops','ct.pentamarketer.agent.executive-twin']::text[],20,400,'D2'),
 ('ct.pentamarketer.agent.security-reliability','ct.persona.crownthrive.security.amara.v1','Amara Reed','Security & Reliability Lead','security_reliability',ARRAY['security_incident','abuse','auth_risk','secret_exposure_triage','reliability','containment_plan']::text[],ARRAY['ct.pentamarketer.agent.technology-ops','ct.pentamarketer.agent.executive-twin']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.software-engineering','ct.persona.crownthrive.engineering.devon.v1','Devon Cross','Software Engineering Lead','software_development',ARRAY['implementation','debugging','integration_build','adapter_build','code_review','test_handoff']::text[],ARRAY['ct.pentamarketer.agent.qa-release','ct.pentamarketer.agent.product-management','ct.pentamarketer.agent.technology-ops']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.product-management','ct.persona.crownthrive.product.sage.v1','Sage Morgan','Product Management Lead','product_management',ARRAY['requirements','roadmap','acceptance_criteria','commercial_fit','product_scope']::text[],ARRAY['ct.pentamarketer.agent.software-engineering','ct.pentamarketer.agent.product-design','ct.pentamarketer.agent.program-management']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.program-management','ct.persona.crownthrive.program.olivia.v1','Olivia Hart','Program & Project Management Lead','project_management',ARRAY['project_plan','dependency_tracking','status','risk_register','owner_assignment','delivery_coordination']::text[],ARRAY['ct.pentamarketer.agent.business-ops','ct.pentamarketer.agent.executive-twin']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.qa-release','ct.persona.crownthrive.release.elena.v1','Elena Park','QA & Release Manager','qa_release',ARRAY['qa','regression','release_gate','deployment_readiness','rollback_verification','evidence_check']::text[],ARRAY['ct.pentamarketer.agent.software-engineering','ct.pentamarketer.agent.technology-ops','ct.pentamarketer.agent.executive-twin']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.sales-director','ct.persona.crownthrive.sales.morgan.v1','Morgan Hale','Sales Director','sales_leadership',ARRAY['enterprise_qualification','deal_strategy','material_quote','proposal_handoff','cross_sell','pipeline_review']::text[],ARRAY['ct.pentamarketer.agent.account-executive','ct.pentamarketer.agent.solutions-engineering','ct.pentamarketer.agent.executive-twin']::text[],25,500,'D2'),
 ('ct.pentamarketer.agent.account-executive','ct.persona.crownthrive.sales.brielle.v1','Brielle Stone','Account Executive','sales_closing',ARRAY['lead_qualification','discovery','offer_match','follow_up','proposal_intake','conversion_handoff']::text[],ARRAY['ct.pentamarketer.agent.sales-director','ct.pentamarketer.agent.solutions-engineering','ct.pentamarketer.agent.customer-success']::text[],25,500,'D1'),
 ('ct.pentamarketer.agent.solutions-engineering','ct.persona.crownthrive.solutions.caleb.v1','Caleb Wright','Solutions Engineer','sales_engineering',ARRAY['technical_discovery','integration_fit','solution_scope','demo_readiness','technical_risk']::text[],ARRAY['ct.pentamarketer.agent.account-executive','ct.pentamarketer.agent.software-engineering','ct.pentamarketer.agent.sales-director']::text[],20,400,'D1'),
 ('ct.pentamarketer.agent.customer-success','ct.persona.crownthrive.success.renee.v1','Renee Bishop','Customer Success Manager','customer_success',ARRAY['support_triage','onboarding','adoption','retention','entitlement_access','escalation']::text[],ARRAY['ct.pentamarketer.agent.business-ops','ct.pentamarketer.agent.account-executive','ct.pentamarketer.agent.technology-ops']::text[],25,500,'D1'),
 ('ct.pentamarketer.agent.provider-ops','ct.persona.crownthrive.provider.tiana.v1','Tiana Brooks','Provider & Vendor Operations Manager','provider_operations',ARRAY['provider_ticket','vendor_notice','capacity_pressure','account_state','provider_readback','renewal_handoff']::text[],ARRAY['ct.pentamarketer.agent.technology-ops','ct.pentamarketer.agent.finance-commerce','ct.pentamarketer.agent.executive-twin']::text[],20,400,'D2'),
 ('ct.pentamarketer.agent.finance-commerce','ct.persona.crownthrive.finance.julian.v1','Julian Kent','Finance & Commerce Operations Lead','finance_commerce',ARRAY['billing','subscription','payment_evidence','commerce_ops','reconciliation','entitlement_handoff']::text[],ARRAY['ct.pentamarketer.agent.revenue','ct.pentamarketer.agent.executive-twin','ct.pentamarketer.agent.customer-success']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.data-analytics','ct.persona.crownthrive.data.victor.v1','Victor Hale','Data & Analytics Lead','data_analytics',ARRAY['metric_analysis','system_analytics','forecast_inputs','data_quality','decision_support']::text[],ARRAY['ct.pentamarketer.agent.business-ops','ct.pentamarketer.agent.product-management','ct.pentamarketer.agent.sales-director']::text[],5,100,'D1'),
 ('ct.pentamarketer.agent.knowledge-docs','ct.persona.crownthrive.docs.imani-foster.v1','Imani Foster','Knowledge & Documentation Lead','documentation_knowledge',ARRAY['documentation','help_center','runbook','knowledge_base','change_projection','source_alignment']::text[],ARRAY['ct.pentamarketer.agent.product-management','ct.pentamarketer.agent.qa-release','ct.pentamarketer.agent.business-ops']::text[],5,100,'D1'),
 ('ct.pentamarketer.agent.business-ops','ct.persona.crownthrive.ops.rowan.v1','Rowan Pierce','Business Operations Lead','business_operations',ARRAY['cross_functional_ops','vendor_coordination','process_design','work_intake','operating_rhythm','escalation']::text[],ARRAY['ct.pentamarketer.agent.program-management','ct.pentamarketer.agent.executive-twin','ct.pentamarketer.agent.provider-ops']::text[],10,200,'D2'),
 ('ct.pentamarketer.agent.product-design','ct.persona.crownthrive.design.aaliyah.v1','Aaliyah Chen','Product Design & UX Lead','product_design',ARRAY['ux','information_architecture','interaction_design','accessibility','design_qa','implementation_handoff']::text[],ARRAY['ct.pentamarketer.agent.product-management','ct.pentamarketer.agent.software-engineering','ct.pentamarketer.agent.qa-release']::text[],5,100,'D1')
)
insert into crm.penta_marketer_agents_v2(
 agent_id,persona_id,display_name,role_title,lane,brand_scope,primary_channel,capabilities,handoff_targets,
 activation_rules,deactivation_rules,daily_contact_cap,monthly_contact_cap,risk_ceiling,autonomous,enabled,state,metadata,updated_at
)
select agent_id,persona_id,display_name,role_title,lane,ARRAY['CrownThrive','Cross-Ecosystem']::text[],'penta_mail',capabilities,handoffs,
 jsonb_build_object('route_via','crm.penta_marketer_route_work_v1','email_via','crm.penta_marketer_email_enqueue_v1'),
 jsonb_build_object('stop_on','authority_conflict, evidence_conflict, suppression, explicit handoff, failed provider gate'),
 daily_cap,monthly_cap,risk_ceiling,true,true,'active',
 jsonb_build_object('suite','ct.pentamarketer.enterprise-team.v1','email_transport','PentaMail','control_plane','PentaMarketer','founder_directive','2026-08-28'),now()
from agent_seed
on conflict(agent_id) do update set
 persona_id=excluded.persona_id,display_name=excluded.display_name,role_title=excluded.role_title,lane=excluded.lane,
 brand_scope=excluded.brand_scope,primary_channel=excluded.primary_channel,capabilities=excluded.capabilities,handoff_targets=excluded.handoff_targets,
 activation_rules=excluded.activation_rules,deactivation_rules=excluded.deactivation_rules,daily_contact_cap=excluded.daily_contact_cap,
 monthly_contact_cap=excluded.monthly_contact_cap,risk_ceiling=excluded.risk_ceiling,autonomous=true,enabled=true,state='active',
 metadata=crm.penta_marketer_agents_v2.metadata||excluded.metadata,updated_at=now();

insert into crm.penta_marketer_team_registry_v1(lane_key,team_name,primary_agent_id,fallback_agent_id,classification_keys,email_enabled,authority_ceiling,founder_attention_policy,metadata)
values
 ('executive_orchestration','Founder Office','ct.pentamarketer.agent.executive-twin','ct.pentamarketer.agent.business-ops',ARRAY['executive','founder_office','strategy','founder_attention']::text[],true,'D2','explicit_or_d3','{}'),
 ('technology_operations','Technology Operations','ct.pentamarketer.agent.technology-ops','ct.pentamarketer.agent.provider-ops',ARRAY['technology_operations','hosting','dns','mail_relay','infrastructure','penta_self_report']::text[],true,'D2','critical_or_material','{}'),
 ('security_reliability','Security & Reliability','ct.pentamarketer.agent.security-reliability','ct.pentamarketer.agent.technology-ops',ARRAY['security','abuse','auth','credential_incident','reliability']::text[],true,'D2','critical_or_material','{}'),
 ('software_development','Software Engineering','ct.pentamarketer.agent.software-engineering','ct.pentamarketer.agent.technology-ops',ARRAY['software_development','bug','feature','integration_build','adapter_build']::text[],true,'D2','release_or_blocker','{}'),
 ('product_management','Product','ct.pentamarketer.agent.product-management','ct.pentamarketer.agent.program-management',ARRAY['product','product_management','requirements','roadmap']::text[],true,'D2','material_scope','{}'),
 ('project_management','Program & Project Management','ct.pentamarketer.agent.program-management','ct.pentamarketer.agent.business-ops',ARRAY['project','program','project_management','deadline','dependency']::text[],true,'D2','blocked_material_work','{}'),
 ('qa_release','QA & Release','ct.pentamarketer.agent.qa-release','ct.pentamarketer.agent.software-engineering',ARRAY['qa','release','deployment','regression','rollback']::text[],true,'D2','failed_release_gate','{}'),
 ('sales_leadership','Sales Leadership','ct.pentamarketer.agent.sales-director','ct.pentamarketer.agent.account-executive',ARRAY['enterprise_sales','material_quote','high_value_opportunity']::text[],true,'D2','material_quote_or_exception','{}'),
 ('sales_closing','Sales','ct.pentamarketer.agent.account-executive','ct.pentamarketer.agent.sales-director',ARRAY['lead','sales_inquiry','sales','purchase_intent','paid_service_intent']::text[],true,'D1','high_value_or_exception','{}'),
 ('sales_engineering','Solutions Engineering','ct.pentamarketer.agent.solutions-engineering','ct.pentamarketer.agent.software-engineering',ARRAY['sales_engineering','technical_sales','integration_fit']::text[],true,'D1','material_technical_commitment','{}'),
 ('customer_success','Customer Success','ct.pentamarketer.agent.customer-success','ct.pentamarketer.agent.member-success',ARRAY['customer_success','account_management','support','onboarding']::text[],true,'D1','urgent_support','{}'),
 ('provider_operations','Provider & Vendor Operations','ct.pentamarketer.agent.provider-ops','ct.pentamarketer.agent.technology-ops',ARRAY['provider_ops','vendor','provider_ticket','capacity_pressure','provider_notice']::text[],true,'D2','capacity_or_account_risk','{}'),
 ('finance_commerce','Finance & Commerce Operations','ct.pentamarketer.agent.finance-commerce','ct.pentamarketer.agent.revenue',ARRAY['finance_commerce','billing','payment','subscription','commerce']::text[],true,'D2','money_authority_or_material_billing','{}'),
 ('data_analytics','Data & Analytics','ct.pentamarketer.agent.data-analytics','ct.pentamarketer.agent.analytics',ARRAY['data','analytics','metrics','reporting']::text[],true,'D1','material_variance','{}'),
 ('documentation_knowledge','Knowledge & Documentation','ct.pentamarketer.agent.knowledge-docs','ct.pentamarketer.agent.product-management',ARRAY['documentation','knowledge','help_center','runbook']::text[],true,'D1','canonical_conflict','{}'),
 ('business_operations','Business Operations','ct.pentamarketer.agent.business-ops','ct.pentamarketer.agent.executive-twin',ARRAY['business_operations','operations','other_business']::text[],true,'D2','material_only','{}'),
 ('product_design','Product Design & UX','ct.pentamarketer.agent.product-design','ct.pentamarketer.agent.product-management',ARRAY['design','ux','product_design','accessibility']::text[],true,'D1','material_brand_or_accessibility_risk','{}')
on conflict(lane_key) do update set
 team_name=excluded.team_name,primary_agent_id=excluded.primary_agent_id,fallback_agent_id=excluded.fallback_agent_id,
 classification_keys=excluded.classification_keys,email_enabled=excluded.email_enabled,authority_ceiling=excluded.authority_ceiling,
 founder_attention_policy=excluded.founder_attention_policy,metadata=crm.penta_marketer_team_registry_v1.metadata||excluded.metadata,updated_at=now();

create or replace function crm.penta_marketer_route_work_v1(
  p_work_class text,
  p_source_system text default null,
  p_urgency integer default 25,
  p_opportunity integer default 0,
  p_payload jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','crm','public'
as $function$
declare
  v_class text:=trim(both '_' from regexp_replace(lower(coalesce(p_work_class,'other_business')),'[^a-z0-9]+','_','g'));
  v_agent_id text;
  v_agent crm.penta_marketer_agents_v2%rowtype;
  v_founder_attention boolean:=false;
begin
  if coalesce(p_urgency,25) not between 0 and 100 or coalesce(p_opportunity,0) not between 0 and 100 then
    raise exception 'score_out_of_bounds';
  end if;

  v_founder_attention :=
    lower(coalesce(p_payload->>'requires_founder_attention','false')) in ('true','1','yes')
    or v_class in ('founder_attention','executive','founder_office')
    or coalesce(p_urgency,25)>=98;

  v_agent_id:=case
    when v_class in ('member_support','listing_correction','claim_request') then 'ct.pentamarketer.agent.member-success'
    when v_class in ('complaint','unsubscribe') then 'ct.pentamarketer.agent.compliance'
    when v_class in ('partnership','sponsorship') then 'ct.pentamarketer.agent.collab'
    when v_class in ('content_media','community_editorial') then 'ct.pentamarketer.agent.community-editor'
    when v_class in ('newsletter_marketing','newsletter') then 'ct.pentamarketer.agent.newsletter'
    when v_class in ('backroad_artist_submission','artist_submission') then 'ct.pentamarketer.agent.backroad.artist-relations'
    when v_class in ('backroad_programming','programming_sponsorship') then 'ct.pentamarketer.agent.backroad.programming'
    when v_class in ('licensing','licensing_sync','sync') then 'ct.pentamarketer.agent.virality.licensing'
    when v_class in ('publishing_ip_adaptation','ip_adaptation','publishing_rights','adaptation') then 'ct.pentamarketer.agent.virality.ip'
    when v_class in ('custom_music','custom_music_services','creative_services') then 'ct.pentamarketer.agent.virality.commissions'
    when v_class in ('technology_operations','hosting','dns','mail_relay','infrastructure','penta_self_report') then 'ct.pentamarketer.agent.technology-ops'
    when v_class in ('security','abuse','auth','credential_incident','security_reliability','reliability') then 'ct.pentamarketer.agent.security-reliability'
    when v_class in ('software_development','bug','feature','integration_build','adapter_build','development') then 'ct.pentamarketer.agent.software-engineering'
    when v_class in ('qa','release','deployment','regression','rollback','qa_release') then 'ct.pentamarketer.agent.qa-release'
    when v_class in ('product','product_management','requirements','roadmap') then 'ct.pentamarketer.agent.product-management'
    when v_class in ('project','program','project_management','deadline','dependency') then 'ct.pentamarketer.agent.program-management'
    when v_class in ('design','ux','product_design','accessibility') then 'ct.pentamarketer.agent.product-design'
    when v_class in ('sales_engineering','technical_sales','integration_fit') then 'ct.pentamarketer.agent.solutions-engineering'
    when v_class in ('customer_success','account_management','support','onboarding') then 'ct.pentamarketer.agent.customer-success'
    when v_class in ('provider_ops','vendor','provider_ticket','capacity_pressure','provider_notice') then 'ct.pentamarketer.agent.provider-ops'
    when v_class in ('finance_commerce','billing','payment','subscription','commerce') then 'ct.pentamarketer.agent.finance-commerce'
    when v_class in ('data','analytics','metrics','reporting') then 'ct.pentamarketer.agent.data-analytics'
    when v_class in ('documentation','knowledge','help_center','runbook') then 'ct.pentamarketer.agent.knowledge-docs'
    when v_class in ('lead','sales_inquiry','sales','purchase_intent','paid_service_intent') and coalesce(p_opportunity,0)>=85 then 'ct.pentamarketer.agent.sales-director'
    when v_class in ('lead','sales_inquiry','sales','purchase_intent','paid_service_intent') then 'ct.pentamarketer.agent.account-executive'
    when v_class in ('enterprise_sales','material_quote','high_value_opportunity') then 'ct.pentamarketer.agent.sales-director'
    when v_class in ('executive','founder_office','strategy','founder_attention') then 'ct.pentamarketer.agent.executive-twin'
    else 'ct.pentamarketer.agent.business-ops'
  end;

  select * into v_agent from crm.penta_marketer_agents_v2 where agent_id=v_agent_id and enabled and state='active';
  if not found then
    select * into v_agent from crm.penta_marketer_agents_v2 where agent_id='ct.pentamarketer.agent.business-ops' and enabled and state='active';
  end if;
  if not found then raise exception 'PENTAMARKETER_NO_ACTIVE_ROUTE'; end if;

  return jsonb_build_object(
    'work_class',v_class,
    'source_system',p_source_system,
    'agent_id',v_agent.agent_id,
    'persona_id',v_agent.persona_id,
    'display_name',v_agent.display_name,
    'role_title',v_agent.role_title,
    'lane',v_agent.lane,
    'risk_ceiling',v_agent.risk_ceiling,
    'requires_founder_attention',v_founder_attention,
    'email_transport','PentaMail',
    'control_plane','PentaMarketer'
  );
end
$function$;

create or replace function crm.penta_marketer_email_enqueue_v1(
  p_source_system text,
  p_source_event_id text,
  p_work_class text,
  p_purpose text,
  p_recipient text,
  p_subject text,
  p_body_text text,
  p_message_type text default 'penta_marketer',
  p_severity text default 'INFO',
  p_urgency integer default 25,
  p_opportunity integer default 0,
  p_authority_class text default 'D1',
  p_metadata jsonb default '{}'::jsonb,
  p_dedupe_key text default null
) returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','crm','public','integration_control'
as $function$
declare
  v_route jsonb;
  v_work crm.penta_marketer_work_queue_v1%rowtype;
  v_dedupe text;
  v_message uuid;
  v_mail_state text;
  v_required_level integer;
  v_ceiling_level integer;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if coalesce(btrim(p_source_system),'')='' or coalesce(btrim(p_purpose),'')='' then raise exception 'source_and_purpose_required'; end if;
  if coalesce(btrim(p_recipient),'')='' or coalesce(btrim(p_subject),'')='' or coalesce(p_body_text,'')='' then raise exception 'recipient_subject_body_required'; end if;
  if p_authority_class not in ('D0','D1','D2','D3') then raise exception 'invalid_authority_class'; end if;

  v_route:=crm.penta_marketer_route_work_v1(p_work_class,p_source_system,p_urgency,p_opportunity,p_metadata);
  v_dedupe:=left(coalesce(nullif(btrim(p_dedupe_key),''),
    'pentamarketer:'||lower(p_source_system)||':'||coalesce(nullif(btrim(p_source_event_id),''),md5(p_subject||'|'||p_recipient||'|'||p_body_text))||':'||lower(p_purpose)),240);

  select * into v_work from crm.penta_marketer_work_queue_v1 where dedupe_key=v_dedupe;
  if found then
    return jsonb_build_object(
      'ok',v_work.state not in ('failed','cancelled'),
      'idempotent_replay',true,
      'work_id',v_work.work_id,
      'state',v_work.state,
      'message_id',v_work.penta_mail_message_id,
      'agent_id',v_work.assigned_agent_id,
      'persona_id',v_work.assigned_persona_id,
      'requires_founder_attention',v_work.requires_founder_attention
    );
  end if;

  insert into crm.penta_marketer_work_queue_v1(
    dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,recipient,
    assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,authority_class,
    requires_founder_attention,state,payload
  ) values(
    v_dedupe,p_source_system,p_source_event_id,'email',lower(coalesce(p_work_class,'other_business')),p_purpose,
    left(coalesce(p_metadata->>'summary',p_subject),1000),lower(p_recipient),
    v_route->>'agent_id',v_route->>'persona_id',coalesce(p_opportunity,0),coalesce(p_urgency,25),p_authority_class,
    coalesce((v_route->>'requires_founder_attention')::boolean,false),'routed',
    coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('route',v_route,'subject',p_subject,'message_type',p_message_type,'severity',p_severity)
  ) returning * into v_work;

  v_required_level:=substring(p_authority_class from 2)::integer;
  v_ceiling_level:=substring(coalesce(v_route->>'risk_ceiling','D0') from 2)::integer;
  if p_authority_class='D3' or v_required_level>v_ceiling_level then
    update crm.penta_marketer_work_queue_v1
      set state='held',requires_founder_attention=true,
          payload=payload||jsonb_build_object('hold_reason',case when p_authority_class='D3' then 'D3_HUMAN_RESERVED' else 'AGENT_AUTHORITY_CEILING' end),updated_at=now()
      where work_id=v_work.work_id;
    return jsonb_build_object('ok',true,'state','held','work_id',v_work.work_id,'message_id',null,
      'agent_id',v_route->>'agent_id','persona_id',v_route->>'persona_id','requires_founder_attention',true,
      'hold_reason',case when p_authority_class='D3' then 'D3_HUMAN_RESERVED' else 'AGENT_AUTHORITY_CEILING' end);
  end if;

  begin
    v_message:=public.penta_mail_enqueue_v1(
      lower(coalesce(p_message_type,'penta_marketer')),
      upper(coalesce(p_severity,'INFO')),
      p_subject,
      p_body_text,
      v_dedupe,
      coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object(
        'trigger_ref',left('penta-marketer:'||lower(coalesce(p_source_system,'system'))||':'||lower(coalesce(p_purpose,'email')),190),
        'source_system',p_source_system,
        'source_event_id',p_source_event_id,
        'origin_penta','PentaMarketer',
        'delivery_penta','PentaMail',
        'assigned_agent_id',v_route->>'agent_id',
        'assigned_persona_id',v_route->>'persona_id',
        'assigned_display_name',v_route->>'display_name',
        'assigned_role_title',v_route->>'role_title',
        'work_id',v_work.work_id,
        'authority_class',p_authority_class,
        'requires_founder_attention',coalesce((v_route->>'requires_founder_attention')::boolean,false)
      ),
      lower(p_recipient)
    );
    select state into v_mail_state from public.penta_mail_outbox_v1 where message_id=v_message;
    update crm.penta_marketer_work_queue_v1
      set penta_mail_message_id=v_message,
          state=case when v_mail_state in ('dispatching','sent') then v_mail_state when v_mail_state='failed' then 'failed' when v_mail_state='held' then 'held' else 'queued' end,
          updated_at=now()
      where work_id=v_work.work_id;
    return jsonb_build_object('ok',true,'state',case when v_mail_state='held' then 'held' else coalesce(v_mail_state,'queued') end,
      'work_id',v_work.work_id,'message_id',v_message,'agent_id',v_route->>'agent_id','persona_id',v_route->>'persona_id',
      'display_name',v_route->>'display_name','role_title',v_route->>'role_title',
      'requires_founder_attention',coalesce((v_route->>'requires_founder_attention')::boolean,false),'email_transport','PentaMail');
  exception when others then
    update crm.penta_marketer_work_queue_v1
      set state='held',payload=payload||jsonb_build_object('mail_enqueue_error',left(sqlerrm,300),'mail_enqueue_sqlstate',sqlstate),updated_at=now()
      where work_id=v_work.work_id;
    return jsonb_build_object('ok',false,'state','held','work_id',v_work.work_id,'message_id',null,
      'agent_id',v_route->>'agent_id','persona_id',v_route->>'persona_id','requires_founder_attention',
      coalesce((v_route->>'requires_founder_attention')::boolean,false),'hold_reason','PENTAMAIL_ENQUEUE_FAILED');
  end;
end
$function$;

create or replace function crm.penta_marketer_external_persona_v1(p_classification text)
returns text
language sql
immutable
set search_path='pg_catalog'
as $function$
select case p_classification
  when 'member_support' then 'ct.persona.locticians.member-success.avery.v1'
  when 'listing_correction' then 'ct.persona.locticians.member-success.avery.v1'
  when 'claim_request' then 'ct.persona.locticians.member-success.avery.v1'
  when 'lead' then 'ct.persona.crownthrive.sales.brielle.v1'
  when 'sales_inquiry' then 'ct.persona.crownthrive.sales.brielle.v1'
  when 'partnership' then 'ct.persona.locticians.collab.cameron.v1'
  when 'sponsorship' then 'ct.persona.locticians.collab.cameron.v1'
  when 'content_media' then 'ct.persona.locticians.community-editor.jordan.v1'
  when 'newsletter_marketing' then 'ct.persona.locticians.campaign.talia.v1'
  when 'provider_ops' then 'ct.persona.crownthrive.provider.tiana.v1'
  when 'complaint' then 'ct.persona.locticians.compliance.naomi.v1'
  when 'unsubscribe' then 'ct.persona.locticians.compliance.naomi.v1'
  else 'ct.persona.crownthrive.ops.rowan.v1'
end;
$function$;

create or replace function public.penta_self_hourly_report_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','penta_self','crm','integration_control','extensions'
as $function$
declare
  v_recipient text;
  v_status jsonb;
  v_open int;
  v_p0 int;
  v_p1 int;
  v_resolved int;
  v_attempts int;
  v_messages bigint;
  v_problem_candidates bigint;
  v_top text;
  v_subject text;
  v_body text;
  v_message uuid;
  v_report_id uuid;
  v_report jsonb;
  v_sha text;
  v_severity text;
  v_mail_route jsonb;
begin
  select recipient into v_recipient from integration_control.penta_hourly_update_policy_v1 where enabled order by effective_at desc,created_at desc limit 1;
  v_recipient:=coalesce(v_recipient,'jones.usmc.kj@gmail.com');
  v_status:=penta_self.continuous_status_v1();
  v_open:=coalesce((v_status->>'open_problems')::int,0);
  v_p0:=coalesce((v_status->'priorities'->>'P0')::int,0);
  v_p1:=coalesce((v_status->'priorities'->>'P1')::int,0);
  select count(*) into v_resolved from penta_self.problem_ledger_v1 where state='resolved' and resolved_at>=now()-interval '1 hour';
  select count(*) into v_attempts from penta_self.problem_attempts_v1 where completed_at>=now()-interval '1 hour';
  select coalesce(sum(message_count),0),coalesce(sum(problem_count),0) into v_messages,v_problem_candidates from penta_self.message_scan_receipts_v1 where created_at>=now()-interval '1 hour';
  select string_agg(format('%s | %s | %s | owner=%s | attempts=%s | next=%s',priority,state,left(title,110),left(owner_penta,80),attempt_count,to_char(next_attempt_at at time zone 'America/New_York','HH24:MI:SS')),E'\n' order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,first_seen_at)
    into v_top from (select * from penta_self.problem_ledger_v1 where state not in ('resolved','false_positive','retired') order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,first_seen_at limit 20)x;
  v_severity:=case when v_p0>0 then 'CRITICAL' when v_open>0 then 'WARNING' else 'INFO' end;
  v_subject:=format('[PentaSELF Hourly Healing] %s open | %s resolved | %s messages inspected',v_open,v_resolved,v_messages);
  v_body:=format(E'CROWNTHRIVE OS — PENTASELF CONTINUOUS HEALING\n================================================\nObserved: %s ET\nCanonical phase: Phase 3 — Execute\nFounder operating label: Phase 3.5 — convergence and hardening\n\nHEALING STATE\n• Open problems: %s\n• P0: %s\n• P1: %s\n• Repair/verification attempts this hour: %s\n• Independently verified resolutions this hour: %s\n• Institutional messages inspected this hour: %s\n• Problem candidates routed this hour: %s\n\nTOP OWNED PROBLEMS\n%s\n\nCONTINUITY CONTRACT\n• Every message entering the CrownThrive institutional event fabric is inspected.\n• Every detected problem remains owned until verified resolution or explicit D3 disposition.\n• PentaSELF retries, repairs, verifies, quarantines, delegates, and escalates persistently.\n• “By force” means no silent abandonment: it does not bypass CHLOM, DAIL, provider permissions, credentials, release gates, or fail-closed economic controls.\n• D3 remains human-reserved. PentaSELF does not manufacture authority, credentials, provider evidence, or money-movement permission.\n\nThis report is an operational projection. ThriveBase, CHLOM, DAIL, GitHub, and independent provider readback retain their canonical roles.\n',
    to_char(now() at time zone 'America/New_York','YYYY-MM-DD HH24:MI:SS'),v_open,v_p0,v_p1,v_attempts,v_resolved,v_messages,v_problem_candidates,coalesce(v_top,'(none)'));
  v_report:=jsonb_build_object('contract','ct.penta.self.hourly-healing-report.v1','observed_at',now(),'recipient',v_recipient,'status',v_status,
    'messages_inspected_1h',v_messages,'problem_candidates_1h',v_problem_candidates,'attempts_1h',v_attempts,'resolved_1h',v_resolved,'d3_human_reserved',true,'authority_manufactured',false,
    'email_control_plane','PentaMarketer','email_transport','PentaMail');
  v_sha:=encode(extensions.digest(convert_to(v_report::text,'UTF8'),'sha256'),'hex');
  insert into public.penta_reports_v1(report_type,system_key,priority,title,body,body_sha256,state)
  values('hourly_healing','penta.self',case when v_p0>0 then 'P0' when v_p1>0 then 'P1' else 'P2' end,v_subject,v_report,v_sha,'final') returning report_id into v_report_id;

  v_mail_route:=crm.penta_marketer_email_enqueue_v1(
    'PentaSELF',
    'hourly-healing:'||to_char(now() at time zone 'UTC','YYYYMMDDHH24'),
    'penta_self_report',
    'hourly_healing_report',
    v_recipient,
    v_subject,
    v_body,
    'penta_self_hourly_healing',
    v_severity,
    case when v_p0>0 then 100 when v_p1>0 then 90 when v_open>0 then 75 else 25 end,
    0,
    'D1',
    jsonb_build_object('summary','PentaSELF hourly healing report','report_id',v_report_id,'report_sha256',v_sha,'source_penta','PentaSELF','d3_human_reserved',true,'authority_expansion',false),
    'penta-self-hourly-healing-'||to_char(now() at time zone 'UTC','YYYYMMDDHH24')
  );
  begin v_message:=nullif(v_mail_route->>'message_id','')::uuid; exception when others then v_message:=null; end;
  if v_message is not null then
    perform public.penta_mail_outbox_dispatch_v1();
    update public.penta_reports_v1 set sent_at=now() where report_id=v_report_id;
  end if;

  return jsonb_build_object('ok',coalesce((v_mail_route->>'ok')::boolean,false),'state',coalesce(v_mail_route->>'state','held'),'recipient',v_recipient,
    'message_id',v_message,'report_id',v_report_id,'report_sha256',v_sha,'status',v_status,
    'penta_marketer_route',v_mail_route,'email_control_plane','PentaMarketer','email_transport','PentaMail');
end
$function$;

revoke all on function crm.penta_marketer_route_work_v1(text,text,integer,integer,jsonb) from public,anon,authenticated;
revoke all on function crm.penta_marketer_email_enqueue_v1(text,text,text,text,text,text,text,text,text,integer,integer,text,jsonb,text) from public,anon,authenticated;
grant execute on function crm.penta_marketer_route_work_v1(text,text,integer,integer,jsonb) to service_role;
grant execute on function crm.penta_marketer_email_enqueue_v1(text,text,text,text,text,text,text,text,text,integer,integer,text,jsonb,text) to service_role;
