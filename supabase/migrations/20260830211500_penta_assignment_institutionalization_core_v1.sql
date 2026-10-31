-- CrownThrive Penta Assignment Fulfillment & Institutionalization — core v1
create schema if not exists penta_docs;

create table if not exists integration_control.penta_assignment_policy_v1 (
  policy_key text primary key,
  version text not null,
  state text not null check (state in ('ACTIVE','HOLD','RETIRED')),
  applies_to text[] not null default array['D0','D1','D2']::text[],
  required_dail_lanes text[] not null default array['EVIDENCE','DECISION','EXECUTION']::text[],
  required_projections text[] not null default array['PENTADOCS','DRIVE_HUMAN','DRIVE_HYBRID','DRIVE_MACHINE_SHEET']::text[],
  independent_certification_from_risk text not null default 'D1',
  terminalization_rule text not null,
  d3_human_reserved boolean not null default true,
  authority_expansion boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into integration_control.penta_assignment_policy_v1(policy_key,version,state,terminalization_rule,metadata)
values(
  'ct.penta.change-institutionalization.rule.v1','1.0.0','ACTIVE',
  'A linked pull request may merge or close only after the exact-head assignment is completed, independently certified when required, bound to EVIDENCE/DECISION/EXECUTION DAIL events, projected through PentaDocs, mirrored to Drive Human/Hybrid/Machine, read back, and covered by a current DAIL chain PASS.',
  jsonb_build_object(
    'founder_directive','2026-08-30:all changes institutionalized and PRs terminalize only after task completion',
    'history_preserved',true,
    'provider_acceptance_not_institutional_truth',true,
    'originator_cannot_self_certify',true,
    'money_movement',false,
    'credential_change',false,
    'd3_execution',false
  )
) on conflict(policy_key) do update set
  version=excluded.version,state='ACTIVE',terminalization_rule=excluded.terminalization_rule,
  metadata=integration_control.penta_assignment_policy_v1.metadata||excluded.metadata,updated_at=now();

create table if not exists integration_control.penta_family_obligation_contracts_v1 (
  family_key text primary key,
  contract_version text not null default '1.0.0',
  canonical_name text not null,
  obligation text not null,
  required_capabilities text[] not null default '{}'::text[],
  default_owner_pentas jsonb not null default '[]'::jsonb,
  authority_ceiling text not null default 'D2' check (authority_ceiling in ('D0','D1','D2','D3')),
  d3_human_reserved boolean not null default true,
  state text not null default 'ACTIVE' check (state in ('ACTIVE','HOLD','RETIRED')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (jsonb_typeof(default_owner_pentas)='array')
);

insert into integration_control.penta_family_obligation_contracts_v1(family_key,canonical_name,obligation,required_capabilities,default_owner_pentas,authority_ceiling,metadata) values
('AUTOMATION_AGENTIC','Penta Automation & Agentic Family','Automate bounded work, monitor execution, reconcile retries and route unresolved dependencies without manufacturing authority.',array['automation','agentic execution','bounded retry'],jsonb_build_array('PentaMation','PentaSELF','PentaHelper','PentaNurture'),'D2',jsonb_build_object('constitutional_family',true)),
('BUILD_RELEASE','Penta Build, Certification & Release Family','Build, test, independently certify, release, project evidence and terminalize source changes only after institutional completion.',array['build','test','certify','release','pr terminalization'],jsonb_build_array('PentaBuild','PentaTest','PentaCertify','PentaRelease','PentaPR','PentaMerge','PentaCloser','PentaDocs'),'D2',jsonb_build_object('constitutional_family',true)),
('COMMERCE_ECONOMY','Penta Commerce & Economy Family','Maintain product, checkout, entitlement, ledger and economic evidence while preserving money-movement and D3 boundaries.',array['commerce','entitlement','economic evidence'],jsonb_build_array('PentaGreen','PentaPay','PentaCredits','PentaSettle','PentaCost'),'D2',jsonb_build_object('constitutional_family',true,'material_money_movement_human_reserved',true)),
('COMMUNICATIONS_SERVICE','Penta Communications & Service Family','Operate governed communications, delivery, service intake and customer lifecycle evidence with recipient and provider safety.',array['communications','service intake','delivery evidence'],jsonb_build_array('PentaMail','PentaMarketer','PentaFlow','PentaNotifs','PentaNurture'),'D2',jsonb_build_object('constitutional_family',true)),
('GOVERNANCE_LEGAL','Penta Governance, Legal & Institutional Controls Family','Maintain governance and institutional controls while leaving legal determinations, sovereign votes and D3 decisions human-reserved.',array['governance controls','institutional policy'],jsonb_build_array('PentaGovernance','PentaPolicy','PentaPolice','PentaBoard','PentaLegal'),'D2',jsonb_build_object('constitutional_family',true,'legal_determinations_human_reserved',true)),
('INTELLIGENCE_RESEARCH','Penta Intelligence, Research & Impact Family','Discover, census, research and bind evidence without converting discovery summaries into certification truth.',array['discovery','census','research','impact'],jsonb_build_array('PentaCrawler','PentaDiscovery','PentaCensus','PentaResearch','PentaImpact'),'D2',jsonb_build_object('constitutional_family',true)),
('KNOWLEDGE_DATA','Penta Knowledge, Semantics & Data Family','Maintain canonical knowledge, semantics, documentation, context, records and governed projections.',array['knowledge','semantics','documentation','data projection'],jsonb_build_array('PentaDocs','PentaContext','PentaScribe','PentaHistorian','PentaDrive','PentaSync'),'D2',jsonb_build_object('constitutional_family',true)),
('MEDIA_CREATIVE','Penta Media, Studio & Publishing Family','Create, govern, publish and archive media and creative assets with rights, provenance and evidence continuity.',array['media','creative','publishing','rights evidence'],jsonb_build_array('PentaStudios','PentaBooks','PentaPublisher','PentaMedia','PentaDocs'),'D2',jsonb_build_object('constitutional_family',true,'final_rights_grants_human_reserved',true)),
('OBSERVABILITY_ORGANIC','Penta Observability & Organic Systems Family','Observe system health, organic growth and operational drift; escalate verified anomalies to owning repair domains.',array['observability','health','organic systems'],jsonb_build_array('PentaHealth','PentaHeartbeat','PentaSignal','PentaPulse','PentaCrawler'),'D2',jsonb_build_object('constitutional_family',true)),
('RESILIENCE_CONTINUITY','Penta Resilience & Continuity Family','Maintain backup, restore, rollback, recovery and continuity evidence without inventing recovery credentials.',array['backup','restore','rollback','continuity'],jsonb_build_array('PentaBackup','PentaRestore','PentaSELF','PentaAssure','PentaCredentials'),'D2',jsonb_build_object('constitutional_family',true,'credential_creation_human_reserved',true)),
('ROUTING_INTEROP','Penta Routing & Interoperability Family','Route packets, provider work and cross-system dependencies through registered contracts and exact authority ceilings.',array['routing','interop','provider handoff'],jsonb_build_array('PentaRoute','PentaWire','PentaMesh','PentaFabric','PentaDND'),'D2',jsonb_build_object('constitutional_family',true)),
('SECURITY_TRUST','Penta Security, Identity & Trust Family','Enforce least privilege, identity, trust, policy and security evidence with fail-closed credential boundaries.',array['security','identity','trust','least privilege'],jsonb_build_array('PentaSecurity','PentaCredentials','PentaOFAC','PentaPolice','PentaAssure'),'D2',jsonb_build_object('constitutional_family',true)),
('SYSTEM_ARCHITECTURE','Penta System Architecture Family','Maintain canonical architecture, system registries, dependencies, runtime bindings and convergence without whole-system overclaim.',array['architecture','registry','runtime binding','convergence'],jsonb_build_array('PentaSELF','PentaSuper','PentaArchitect','PentaCensus','PentaWire'),'D2',jsonb_build_object('constitutional_family',true)),
('TRANSPORT_PRIMITIVES','Penta Transport & Capability Primitives Family','Provide bounded transport and capability primitives with SSRF, credential-forwarding and provider-write controls.',array['transport','capability primitives'],jsonb_build_array('PentaFetch','PentaGet','PentaPost','PentaPut','PentaPatch','PentaDelete'),'D2',jsonb_build_object('constitutional_family',true)),
('WORKFORCE_PEOPLE','Penta Workforce & People Family','Maintain workforce, role, assignment, manager, cohort and people records without manufacturing employment or legal authority.',array['workforce','roles','assignments','people'],jsonb_build_array('PentaWorkforce','PentaHR','PentaManagers','PentaCohorts','PentaAlumni'),'D2',jsonb_build_object('constitutional_family',true))
on conflict(family_key) do update set
 canonical_name=excluded.canonical_name,obligation=excluded.obligation,required_capabilities=excluded.required_capabilities,
 default_owner_pentas=excluded.default_owner_pentas,authority_ceiling=excluded.authority_ceiling,state='ACTIVE',
 metadata=integration_control.penta_family_obligation_contracts_v1.metadata||excluded.metadata,updated_at=now();

create table if not exists integration_control.penta_assignment_contracts_v1 (
  assignment_id uuid primary key default gen_random_uuid(),
  assignment_key text not null unique,
  contract_version text not null default '1.0.0',
  subject_kind text not null,
  subject_ref text not null,
  task_kind text not null,
  title text not null,
  summary text not null,
  owning_family_key text not null references integration_control.penta_family_obligation_contracts_v1(family_key),
  owner_pentas jsonb not null default '[]'::jsonb,
  certifier_penta text not null default 'PentaCertify',
  risk_class text not null check (risk_class in ('D0','D1','D2')),
  authority_ceiling text not null check (authority_ceiling in ('D0','D1','D2')),
  source_repo text,
  source_pr_number bigint,
  exact_head_sha text,
  exact_artifact_ref text not null,
  exact_artifact_sha256 text,
  acceptance_criteria jsonb not null default '[]'::jsonb,
  required_projections text[] not null default array['PENTADOCS','DRIVE_HUMAN','DRIVE_HYBRID','DRIVE_MACHINE_SHEET']::text[],
  independent_certification_required boolean not null default true,
  d3_human_reserved boolean not null default true,
  provider_write_allowed boolean not null default false,
  money_movement_allowed boolean not null default false,
  credential_change_allowed boolean not null default false,
  authority_expansion boolean not null default false,
  state text not null default 'DISCOVERED' check (state in ('DISCOVERED','ROUTED','IN_PROGRESS','AWAITING_PROJECTION','AWAITING_CERTIFICATION','CERTIFIED','COMPLETED','HOLD','FAILED','SUPERSEDED','RETIRED')),
  priority text not null default 'P2' check (priority in ('P0','P1','P2','P3')),
  predecessor_assignment_id uuid references integration_control.penta_assignment_contracts_v1(assignment_id),
  supersedes_assignment_id uuid references integration_control.penta_assignment_contracts_v1(assignment_id),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  terminalized_at timestamptz,
  check (jsonb_typeof(owner_pentas)='array'),
  check (not money_movement_allowed),
  check (not credential_change_allowed),
  check (not authority_expansion)
);

create table if not exists integration_control.penta_assignment_dispatches_v1 (
  dispatch_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  owner_penta text not null,
  family_key text not null,
  dispatch_kind text not null check (dispatch_kind in ('OS20_TASK','CENSUS_HANDOFF','PENTA_PACKET','HELP_ROUTE','CONTRACT_ONLY')),
  external_ref text,
  state text not null default 'ROUTED' check (state in ('ROUTED','ACCEPTED','IN_PROGRESS','COMPLETED','HOLD','FAILED','SUPERSEDED')),
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  unique(assignment_id,owner_penta,dispatch_kind)
);

create table if not exists integration_control.penta_assignment_owner_results_v1 (
  result_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  owner_penta text not null,
  result_state text not null check (result_state in ('PASS','HOLD','FAIL','SUPERSEDED')),
  exact_artifact_ref text not null,
  exact_artifact_sha256 text,
  exact_head_sha text,
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  dail_event_id uuid,
  dail_event_hash text,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(assignment_id,owner_penta,evidence_sha256)
);

create table if not exists integration_control.penta_assignment_institutionalization_v1 (
  assignment_id uuid primary key references integration_control.penta_assignment_contracts_v1(assignment_id),
  evidence_event_id uuid,evidence_event_hash text,evidence_readback boolean not null default false,
  decision_event_id uuid,decision_event_hash text,decision_readback boolean not null default false,
  execution_event_id uuid,execution_event_hash text,execution_readback boolean not null default false,
  pentadocs_record_id uuid,
  pentadocs_state text not null default 'PENDING' check (pentadocs_state in ('PENDING','PROJECTED','READBACK_PASS','HOLD','FAILED')),
  pentadocs_ref text,pentadocs_sha256 text,
  drive_folder_id text,
  drive_human_doc_id text,drive_human_doc_url text,drive_human_sha256 text,drive_human_readback boolean not null default false,
  drive_hybrid_doc_id text,drive_hybrid_doc_url text,drive_hybrid_sha256 text,drive_hybrid_readback boolean not null default false,
  drive_machine_sheet_id text,drive_machine_sheet_url text,drive_machine_sha256 text,drive_machine_readback boolean not null default false,
  provider_projection_state text not null default 'PENDING' check (provider_projection_state in ('PENDING','PARTIAL','READBACK_PASS','HOLD','FAILED')),
  certification_id text,
  certification_state text not null default 'PENDING' check (certification_state in ('PENDING','HOLD','CERTIFIED','ACTIVE','INVALIDATED','NOT_REQUIRED')),
  certifier_ref text,certification_event_id uuid,certification_event_hash text,
  os_projection_state text not null default 'PENDING' check (os_projection_state in ('PENDING','PROJECTED','READBACK_PASS','HOLD','FAILED')),
  os_projection_event_id uuid,
  chain_state text not null default 'PENDING' check (chain_state in ('PENDING','PASS','HOLD','FAIL')),
  chain_checked_at timestamptz,chain_head_hash text,chain_checked_events bigint,
  terminal_gate_state text not null default 'HOLD' check (terminal_gate_state in ('HOLD','PASS','TERMINALIZED')),
  institutionalized_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_assignment_pr_links_v1 (
  link_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  repo text not null,pr_number bigint not null,exact_head_sha text not null,
  terminal_action text not null check (terminal_action in ('MERGE','CLOSE','NONE')),
  classification text not null,
  state text not null default 'LINKED' check (state in ('LINKED','GATE_HOLD','GATE_PASS','DISPATCHED','TERMINALIZED','HEAD_MOVED','FAILED','SUPERSEDED')),
  terminal_request_id bigint,provider_state text,provider_merged boolean,provider_merge_commit_sha text,
  provider_readback jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),updated_at timestamptz not null default now(),terminalized_at timestamptz,
  unique(repo,pr_number,exact_head_sha,terminal_action)
);

create table if not exists integration_control.penta_assignment_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  event_type text not null,actor_ref text not null,state text not null,
  payload jsonb not null default '{}'::jsonb,payload_sha256 text not null,created_at timestamptz not null default now()
);

create table if not exists penta_docs.assignment_institutionalization_v1 (
  record_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null unique references integration_control.penta_assignment_contracts_v1(assignment_id),
  assignment_key text not null,title text not null,summary text not null,family_key text not null,
  owner_pentas jsonb not null,risk_class text not null,exact_artifact_ref text not null,
  exact_artifact_sha256 text,exact_head_sha text,lifecycle_state text not null,
  evidence_refs jsonb not null default '[]'::jsonb,drive_refs jsonb not null default '{}'::jsonb,
  certification_ref text,body jsonb not null default '{}'::jsonb,body_sha256 text not null,
  audience text not null default 'internal' check (audience in ('internal','public')),
  publication_state text not null default 'projected' check (publication_state in ('projected','published','superseded','hold')),
  docs_path text not null,projected_at timestamptz not null default now(),updated_at timestamptz not null default now()
);

create or replace function integration_control.penta_assignment_immutable_v1()
returns trigger language plpgsql as $$ begin raise exception 'append_only_history'; end $$;

drop trigger if exists penta_assignment_owner_results_immutable_v1 on integration_control.penta_assignment_owner_results_v1;
create trigger penta_assignment_owner_results_immutable_v1 before update or delete on integration_control.penta_assignment_owner_results_v1 for each row execute function integration_control.penta_assignment_immutable_v1();
drop trigger if exists penta_assignment_events_immutable_v1 on integration_control.penta_assignment_events_v1;
create trigger penta_assignment_events_immutable_v1 before update or delete on integration_control.penta_assignment_events_v1 for each row execute function integration_control.penta_assignment_immutable_v1();

revoke all on integration_control.penta_assignment_policy_v1 from public,anon,authenticated;
revoke all on integration_control.penta_family_obligation_contracts_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_contracts_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_dispatches_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_owner_results_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_institutionalization_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_pr_links_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_events_v1 from public,anon,authenticated;
revoke all on penta_docs.assignment_institutionalization_v1 from public,anon,authenticated;
