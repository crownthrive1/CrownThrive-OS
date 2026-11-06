create table if not exists institutional_federation.framework_package_registry (
  package_id text primary key check (package_id ~ '^ct[.]framework-package[.][a-z0-9._-]+$'),
  framework_id text not null unique,
  canonical_name text not null,
  factory_order smallint not null unique check (factory_order between 1 and 999),
  framework_agent_id text not null,
  canonical_host_repo_id text not null references institutional_federation.repository_registry(repo_id),
  execution_slug text not null unique,
  package_state text not null check (package_state in ('source_discovery','scaffold_preview','building','controlled_test','parent_certification_pending','governed_accepted','public_package_candidate','maintained','hold','retired')),
  workflow_ref text,
  validator_ref text,
  engine_ref text,
  skill_ref text,
  tools_ref text,
  api_contract_ref text,
  mcp_contract_ref text,
  evals_ref text,
  commercial_manifest_ref text,
  authority_ceiling text not null default 'D2' check (authority_ceiling in ('D0','D1','D2','D3')),
  can_vote boolean not null default false check (can_vote = false),
  d3_human_reserved boolean not null default true check (d3_human_reserved = true),
  parent_certification_required boolean not null default true,
  parent_certification_agent text not null default 'ct.relay.agent-d' check (parent_certification_agent = 'ct.relay.agent-d'),
  parent_certification_state text not null default 'pending' check (parent_certification_state in ('pending','certified','denied','not_applicable')),
  operationally_enabled boolean not null default false,
  public_activation_allowed boolean not null default false,
  physical_repository_required boolean not null default false check (physical_repository_required = false),
  optional_repository_projection text,
  private_runtime_required boolean not null default false,
  private_runtime_state text not null default 'not_required' check (private_runtime_state in ('not_required','registered','available','hold')),
  api_state text not null default 'candidate' check (api_state in ('candidate','disabled','controlled_test','enabled','hold')),
  mcp_state text not null default 'candidate' check (mcp_state in ('candidate','disabled','controlled_test','enabled','hold')),
  commercial_state text not null default 'candidate' check (commercial_state in ('research_candidate','candidate','packaged','rights_cleared','pricing_authorized','fulfillment_certified','checkout_staged','live','hold')),
  exact_price_authorized boolean not null default false,
  checkout_enabled boolean not null default false,
  customer_entitlement_active boolean not null default false,
  public_contract_digest text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table institutional_federation.framework_package_registry enable row level security;
drop policy if exists framework_package_registry_service_role_all on institutional_federation.framework_package_registry;
create policy framework_package_registry_service_role_all on institutional_federation.framework_package_registry for all to service_role using (true) with check (true);
revoke all on institutional_federation.framework_package_registry from anon, authenticated;
grant select, insert, update, delete on institutional_federation.framework_package_registry to service_role;

alter table institutional_federation.algorithm_registry add column if not exists implementation_package_id text;

insert into institutional_federation.framework_package_registry (
  package_id, framework_id, canonical_name, factory_order, framework_agent_id, canonical_host_repo_id, execution_slug,
  package_state, workflow_ref, validator_ref, engine_ref, skill_ref, tools_ref, api_contract_ref, mcp_contract_ref, evals_ref,
  commercial_manifest_ref, private_runtime_required, private_runtime_state, api_state, mcp_state, commercial_state,
  optional_repository_projection, metadata
) values
('ct.framework-package.cie','ct.framework.cultural-imprint-engine','Cultural Imprint Engine',1,'ct.framework-agent.cie','ct.repo.crownthrive-support','cie','controlled_test','.github/workflows/cie-framework-governance.yml','scripts/validate_cie_framework_agent.py','institutional_federation.algorithm_registry:ct.algorithm.cie.v1','developers/templates/framework-child-repository/skills/framework/SKILL.md.tmpl','developers/templates/framework-child-repository/tools/tools.v1.json.tmpl','developers/templates/framework-child-repository/api/api-contract.v1.json.tmpl','developers/templates/framework-child-repository/mcp/mcp-tools.v1.json.tmpl','developers/templates/framework-child-repository/evals/evals.v1.json.tmpl','developers/templates/framework-child-repository/commercial/offer-manifest.v1.json.tmpl',true,'registered','candidate','disabled','candidate','crownthrive1/CrownThrive-CIE',jsonb_build_object('source_ref','PR #145 + PR #169 package-model correction','physical_repository_semantics','optional_distribution_projection_not_child_identity','materialization_state','existing_CIE_controlled_test_plus_factory_package_surfaces','runtime_mutation_state','HOLD_pending_workflow_ref_environment_agent_capability_binding','public_distribution_state','candidate_pending_131_and_governed_acceptance')),
('ct.framework-package.convergent-ecosystem','ct.framework.convergent-ecosystem','Convergent Ecosystem',2,'ct.framework-agent.convergent-ecosystem','ct.repo.crownthrive-support','convergent-ecosystem','source_discovery',null,null,null,null,null,null,null,null,null,false,'not_required','candidate','disabled','research_candidate','crownthrive1/CrownThrive-Convergent-Ecosystem',jsonb_build_object('source_ref','PR #169 package fleet','implementation_gate','blocked_by_CIE_governed_acceptance_and_parent_certification','scaffold_preview_allowed',true)),
('ct.framework-package.thrive-flywheel','ct.framework.thrive-flywheel','Thrive Flywheel',3,'ct.framework-agent.thrive-flywheel','ct.repo.crownthrive-support','thrive-flywheel','source_discovery',null,null,null,null,null,null,null,null,null,false,'not_required','candidate','disabled','research_candidate','crownthrive1/CrownThrive-Thrive-Flywheel',jsonb_build_object('source_ref','PR #169 package fleet')),
('ct.framework-package.chlom','ct.framework.chlom','CHLOM',4,'ct.framework-agent.chlom','ct.repo.crownthrive-support','chlom','source_discovery',null,null,null,null,null,null,null,null,null,true,'registered','candidate','disabled','research_candidate','crownthrive1/CrownThrive-CHLOM',jsonb_build_object('source_ref','PR #169 package fleet','special_rule','no_self_authorization_no_Agent_D_duplication_no_circular_governance')),
('ct.framework-package.corridor-architecture','ct.framework.corridor-architecture','Corridor Architecture',5,'ct.framework-agent.corridor-architecture','ct.repo.crownthrive-support','corridor-architecture','source_discovery',null,null,null,null,null,null,null,null,null,false,'not_required','candidate','disabled','research_candidate','crownthrive1/CrownThrive-Corridor-Architecture',jsonb_build_object('source_ref','PR #169 package fleet')),
('ct.framework-package.hybrid-incubator','ct.framework.hybrid-incubator','Hybrid Incubator',6,'ct.framework-agent.hybrid-incubator','ct.repo.crownthrive-support','hybrid-incubator','source_discovery',null,null,null,null,null,null,null,null,null,false,'not_required','candidate','disabled','research_candidate','crownthrive1/CrownThrive-Hybrid-Incubator',jsonb_build_object('source_ref','PR #169 package fleet')),
('ct.framework-package.mm-suites','ct.framework.mm-suites','MM Suites',7,'ct.framework-agent.mm-suites','ct.repo.crownthrive-support','mm-suites','source_discovery',null,null,null,null,null,null,null,null,null,false,'not_required','candidate','disabled','research_candidate','crownthrive1/CrownThrive-MM-Suites',jsonb_build_object('source_ref','PR #169 package fleet','special_rule','phygital_operator_regional_license_franchise_readiness_architecture')),
('ct.framework-package.one-seat','ct.framework.one-seat-multiple-industries','One Seat, Multiple Industries',8,'ct.framework-agent.one-seat-multiple-industries','ct.repo.crownthrive-support','one-seat','source_discovery',null,null,null,null,null,null,null,null,null,false,'not_required','candidate','disabled','research_candidate','crownthrive1/CrownThrive-One-Seat',jsonb_build_object('source_ref','PR #169 package fleet'))
on conflict (package_id) do update set
  framework_id=excluded.framework_id,
  canonical_name=excluded.canonical_name,
  factory_order=excluded.factory_order,
  framework_agent_id=excluded.framework_agent_id,
  canonical_host_repo_id=excluded.canonical_host_repo_id,
  execution_slug=excluded.execution_slug,
  package_state=excluded.package_state,
  workflow_ref=excluded.workflow_ref,
  validator_ref=excluded.validator_ref,
  engine_ref=excluded.engine_ref,
  skill_ref=excluded.skill_ref,
  tools_ref=excluded.tools_ref,
  api_contract_ref=excluded.api_contract_ref,
  mcp_contract_ref=excluded.mcp_contract_ref,
  evals_ref=excluded.evals_ref,
  commercial_manifest_ref=excluded.commercial_manifest_ref,
  private_runtime_required=excluded.private_runtime_required,
  private_runtime_state=excluded.private_runtime_state,
  api_state=excluded.api_state,
  mcp_state=excluded.mcp_state,
  commercial_state=excluded.commercial_state,
  optional_repository_projection=excluded.optional_repository_projection,
  metadata=excluded.metadata,
  updated_at=now();

update institutional_federation.algorithm_registry
set implementation_package_id='ct.framework-package.cie',
    metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object('physical_repository_required',false,'optional_repository_projection','crownthrive1/CrownThrive-CIE','implementation_identity','ct.framework-package.cie'),
    updated_at=now()
where algorithm_id='ct.algorithm.cie.v1';

update institutional_federation.repository_registry
set metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
  'semantic_role','optional_distribution_repository_projection',
  'physical_repository_required_for_framework_package',false,
  'framework_package_registry','institutional_federation.framework_package_registry',
  'not_an_activation_gate_by_itself',true,
  'supersedes_missing_repo_interpretation_at','2026-08-20T22:04:00Z'
), updated_at=now()
where repo_id in ('ct.repo.cie','ct.repo.convergent-ecosystem','ct.repo.thrive-flywheel','ct.repo.chlom','ct.repo.corridor-architecture','ct.repo.hybrid-incubator','ct.repo.mm-suites','ct.repo.one-seat');

update institutional_federation.repository_agent_bindings b
set metadata=coalesce(b.metadata,'{}'::jsonb) || jsonb_build_object(
  'framework_child_model','executable_framework_package_not_physical_repository',
  'physical_repository_required',false,
  'package_id',p.package_id,
  'canonical_package_host_repo_id','ct.repo.crownthrive-support',
  'optional_repository_projection',p.optional_repository_projection,
  'public_distribution_requires_ip_gate',true,
  'runtime_mutation_requires_workflow_ref_environment_agent_capability_binding',true
), updated_at=now()
from institutional_federation.framework_package_registry p
where b.framework_id=p.framework_id;