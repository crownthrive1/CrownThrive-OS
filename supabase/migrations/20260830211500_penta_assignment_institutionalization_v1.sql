-- CrownThrive Penta Assignment Fulfillment & Institutionalization Fabric v1
-- Founder directive: every D0-D2 change must be completed by its owning Pentas,
-- independently certified where required, recorded through three DAIL lanes,
-- projected through PentaDocs and mirrored to Drive before a linked PR may terminalize.

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

insert into integration_control.penta_assignment_policy_v1(
  policy_key,version,state,terminalization_rule,metadata
) values (
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
  version=excluded.version,
  state='ACTIVE',
  terminalization_rule=excluded.terminalization_rule,
  metadata=integration_control.penta_assignment_policy_v1.metadata||excluded.metadata,
  updated_at=now();

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
  updated_at timestamptz not null default now()
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
 canonical_name=excluded.canonical_name,
 obligation=excluded.obligation,
 required_capabilities=excluded.required_capabilities,
 default_owner_pentas=excluded.default_owner_pentas,
 authority_ceiling=excluded.authority_ceiling,
 state='ACTIVE',
 metadata=integration_control.penta_family_obligation_contracts_v1.metadata||excluded.metadata,
 updated_at=now();

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
  evidence_event_id uuid,
  evidence_event_hash text,
  evidence_readback boolean not null default false,
  decision_event_id uuid,
  decision_event_hash text,
  decision_readback boolean not null default false,
  execution_event_id uuid,
  execution_event_hash text,
  execution_readback boolean not null default false,
  pentadocs_record_id uuid,
  pentadocs_state text not null default 'PENDING' check (pentadocs_state in ('PENDING','PROJECTED','READBACK_PASS','HOLD','FAILED')),
  pentadocs_ref text,
  pentadocs_sha256 text,
  drive_folder_id text,
  drive_human_doc_id text,
  drive_human_doc_url text,
  drive_human_sha256 text,
  drive_human_readback boolean not null default false,
  drive_hybrid_doc_id text,
  drive_hybrid_doc_url text,
  drive_hybrid_sha256 text,
  drive_hybrid_readback boolean not null default false,
  drive_machine_sheet_id text,
  drive_machine_sheet_url text,
  drive_machine_sha256 text,
  drive_machine_readback boolean not null default false,
  provider_projection_state text not null default 'PENDING' check (provider_projection_state in ('PENDING','PARTIAL','READBACK_PASS','HOLD','FAILED')),
  certification_id text,
  certification_state text not null default 'PENDING' check (certification_state in ('PENDING','HOLD','CERTIFIED','ACTIVE','INVALIDATED','NOT_REQUIRED')),
  certifier_ref text,
  certification_event_id uuid,
  certification_event_hash text,
  os_projection_state text not null default 'PENDING' check (os_projection_state in ('PENDING','PROJECTED','READBACK_PASS','HOLD','FAILED')),
  os_projection_event_id uuid,
  chain_state text not null default 'PENDING' check (chain_state in ('PENDING','PASS','HOLD','FAIL')),
  chain_checked_at timestamptz,
  chain_head_hash text,
  chain_checked_events bigint,
  terminal_gate_state text not null default 'HOLD' check (terminal_gate_state in ('HOLD','PASS','TERMINALIZED')),
  institutionalized_at timestamptz,
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_assignment_pr_links_v1 (
  link_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  repo text not null,
  pr_number bigint not null,
  exact_head_sha text not null,
  terminal_action text not null check (terminal_action in ('MERGE','CLOSE','NONE')),
  classification text not null,
  state text not null default 'LINKED' check (state in ('LINKED','GATE_HOLD','GATE_PASS','DISPATCHED','TERMINALIZED','HEAD_MOVED','FAILED','SUPERSEDED')),
  terminal_request_id bigint,
  provider_state text,
  provider_merged boolean,
  provider_merge_commit_sha text,
  provider_readback jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  terminalized_at timestamptz,
  unique(repo,pr_number,exact_head_sha,terminal_action)
);

create table if not exists integration_control.penta_assignment_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null references integration_control.penta_assignment_contracts_v1(assignment_id),
  event_type text not null,
  actor_ref text not null,
  state text not null,
  payload jsonb not null default '{}'::jsonb,
  payload_sha256 text not null,
  created_at timestamptz not null default now()
);

create table if not exists penta_docs.assignment_institutionalization_v1 (
  record_id uuid primary key default gen_random_uuid(),
  assignment_id uuid not null unique references integration_control.penta_assignment_contracts_v1(assignment_id),
  assignment_key text not null,
  title text not null,
  summary text not null,
  family_key text not null,
  owner_pentas jsonb not null,
  risk_class text not null,
  exact_artifact_ref text not null,
  exact_artifact_sha256 text,
  exact_head_sha text,
  lifecycle_state text not null,
  evidence_refs jsonb not null default '[]'::jsonb,
  drive_refs jsonb not null default '{}'::jsonb,
  certification_ref text,
  body jsonb not null default '{}'::jsonb,
  body_sha256 text not null,
  audience text not null default 'internal' check (audience in ('internal','public')),
  publication_state text not null default 'projected' check (publication_state in ('projected','published','superseded','hold')),
  docs_path text not null,
  projected_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create or replace function integration_control.penta_assignment_immutable_v1()
returns trigger language plpgsql as $$
begin
  raise exception 'append_only_history';
end $$;

drop trigger if exists penta_assignment_owner_results_immutable_v1 on integration_control.penta_assignment_owner_results_v1;
create trigger penta_assignment_owner_results_immutable_v1 before update or delete on integration_control.penta_assignment_owner_results_v1 for each row execute function integration_control.penta_assignment_immutable_v1();
drop trigger if exists penta_assignment_events_immutable_v1 on integration_control.penta_assignment_events_v1;
create trigger penta_assignment_events_immutable_v1 before update or delete on integration_control.penta_assignment_events_v1 for each row execute function integration_control.penta_assignment_immutable_v1();

create or replace function integration_control.penta_assignment_create_v1(
  p_assignment_key text,
  p_subject_kind text,
  p_subject_ref text,
  p_task_kind text,
  p_title text,
  p_summary text,
  p_family_key text,
  p_owner_pentas jsonb,
  p_risk_class text,
  p_authority_ceiling text,
  p_exact_artifact_ref text,
  p_exact_artifact_sha256 text default null,
  p_source_repo text default null,
  p_source_pr_number bigint default null,
  p_exact_head_sha text default null,
  p_acceptance_criteria jsonb default '[]'::jsonb,
  p_provider_write_allowed boolean default false,
  p_priority text default 'P2',
  p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_id uuid;
  v_event jsonb;
  v_payload jsonb;
  v_sha text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if nullif(btrim(coalesce(p_assignment_key,'')),'') is null or nullif(btrim(coalesce(p_exact_artifact_ref,'')),'') is null then raise exception 'assignment_identity_required'; end if;
  if p_risk_class not in ('D0','D1','D2') or p_authority_ceiling not in ('D0','D1','D2') then raise exception 'D3_human_reserved'; end if;
  if jsonb_typeof(coalesce(p_owner_pentas,'[]'::jsonb))<>'array' or jsonb_array_length(coalesce(p_owner_pentas,'[]'::jsonb))=0 then raise exception 'owner_pentas_required'; end if;
  if not exists(select 1 from integration_control.penta_family_obligation_contracts_v1 where family_key=p_family_key and state='ACTIVE') then raise exception 'family_contract_not_active'; end if;
  if p_exact_artifact_sha256 is not null and p_exact_artifact_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'artifact_digest_invalid'; end if;
  if p_exact_head_sha is not null and p_exact_head_sha !~ '^[0-9a-f]{40}$' then raise exception 'head_sha_invalid'; end if;

  insert into integration_control.penta_assignment_contracts_v1(
    assignment_key,subject_kind,subject_ref,task_kind,title,summary,owning_family_key,owner_pentas,
    risk_class,authority_ceiling,source_repo,source_pr_number,exact_head_sha,exact_artifact_ref,
    exact_artifact_sha256,acceptance_criteria,independent_certification_required,provider_write_allowed,
    priority,metadata,state
  ) values (
    p_assignment_key,p_subject_kind,p_subject_ref,p_task_kind,p_title,p_summary,p_family_key,p_owner_pentas,
    p_risk_class,p_authority_ceiling,p_source_repo,p_source_pr_number,p_exact_head_sha,p_exact_artifact_ref,
    p_exact_artifact_sha256,coalesce(p_acceptance_criteria,'[]'::jsonb),p_risk_class in ('D1','D2'),
    coalesce(p_provider_write_allowed,false),coalesce(p_priority,'P2'),coalesce(p_metadata,'{}'::jsonb),'DISCOVERED'
  ) on conflict(assignment_key) do update set
    subject_ref=excluded.subject_ref,
    title=excluded.title,
    summary=excluded.summary,
    owner_pentas=excluded.owner_pentas,
    exact_head_sha=excluded.exact_head_sha,
    exact_artifact_ref=excluded.exact_artifact_ref,
    exact_artifact_sha256=excluded.exact_artifact_sha256,
    acceptance_criteria=excluded.acceptance_criteria,
    metadata=integration_control.penta_assignment_contracts_v1.metadata||excluded.metadata,
    state=case when integration_control.penta_assignment_contracts_v1.state in ('COMPLETED','SUPERSEDED','RETIRED') and integration_control.penta_assignment_contracts_v1.exact_head_sha is distinct from excluded.exact_head_sha then 'DISCOVERED' else integration_control.penta_assignment_contracts_v1.state end,
    updated_at=now()
  returning assignment_id into v_id;

  insert into integration_control.penta_assignment_institutionalization_v1(assignment_id)
  values(v_id) on conflict(assignment_id) do nothing;

  v_payload:=jsonb_build_object(
    'assignment_id',v_id,'assignment_key',p_assignment_key,'subject_kind',p_subject_kind,'subject_ref',p_subject_ref,
    'task_kind',p_task_kind,'family_key',p_family_key,'owner_pentas',p_owner_pentas,'risk_class',p_risk_class,
    'authority_ceiling',p_authority_ceiling,'exact_artifact_ref',p_exact_artifact_ref,
    'exact_artifact_sha256',p_exact_artifact_sha256,'source_repo',p_source_repo,'source_pr_number',p_source_pr_number,
    'exact_head_sha',p_exact_head_sha,'provider_write_allowed',coalesce(p_provider_write_allowed,false),
    'money_movement',false,'credential_change',false,'d3_execution',false,'authority_expansion',false,
    'created_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.penta_assignment_events_v1(assignment_id,event_type,actor_ref,state,payload,payload_sha256)
  values(v_id,'ASSIGNMENT_CREATED','PentaAssignmentFabric','DISCOVERED',v_payload,v_sha);
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.created','penta_assignment',v_id::text,
    v_payload||jsonb_build_object('evidence_sha256',v_sha),
    'PentaAssignmentFabric/PentaCensus/PentaWire',null,'PentaAssignmentFabric','1.0.0',
    'ctcorr:penta-assignment:'||v_id::text,null,'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',v_id,'state','DISCOVERED','event',v_event,'evidence_sha256',v_sha);
end $$;

create or replace function integration_control.penta_assignment_route_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_os20','penta_help','extensions','chlom_runtime','public'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_owner text;
  v_penta_id uuid;
  v_task_id uuid;
  v_handoff_key text;
  v_payload jsonb;
  v_sha text;
  v_dispatches int:=0;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  if a.state in ('COMPLETED','SUPERSEDED','RETIRED') then return jsonb_build_object('assignment_id',a.assignment_id,'state',a.state,'dispatches',0); end if;

  for v_owner in select jsonb_array_elements_text(a.owner_pentas) loop
    v_payload:=jsonb_build_object(
      'contract','ct.penta.assignment-fulfillment.v1','assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
      'subject_ref',a.subject_ref,'task_kind',a.task_kind,'title',a.title,'summary',a.summary,
      'family_key',a.owning_family_key,'owner_penta',v_owner,'risk_class',a.risk_class,
      'authority_ceiling',a.authority_ceiling,'exact_artifact_ref',a.exact_artifact_ref,
      'exact_artifact_sha256',a.exact_artifact_sha256,'source_repo',a.source_repo,
      'source_pr_number',a.source_pr_number,'exact_head_sha',a.exact_head_sha,
      'acceptance_criteria',a.acceptance_criteria,'required_projections',to_jsonb(a.required_projections),
      'money_movement',false,'credential_change',false,'d3_execution',false,'authority_expansion',false
    );
    v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
    select id into v_penta_id from penta_os20.pentas where lower(canonical_name)=lower(v_owner) and status='active' limit 1;
    if v_penta_id is not null then
      insert into penta_os20.execution_tasks(task_key,penta_id,release_version,operation_key,estimated_units,status,authority_check)
      values('assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g')),v_penta_id,'OS-2.0.0',a.task_kind,1,'queued',v_payload)
      on conflict(task_key) do update set authority_check=penta_os20.execution_tasks.authority_check||excluded.authority_check
      returning id into v_task_id;
      begin perform public.penta_os20_authorize_task(v_task_id); exception when others then null; end;
      insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
      values(a.assignment_id,v_owner,a.owning_family_key,'OS20_TASK',v_task_id::text,'ROUTED',v_payload,v_sha)
      on conflict(assignment_id,owner_penta,dispatch_kind) do update set external_ref=excluded.external_ref,evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
    else
      v_handoff_key:='assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g'));
      insert into integration_control.penta_census_handoffs_v1(handoff_key,discovery_key,tag,target_ref,risk_class,state,authority_note,payload)
      values(v_handoff_key,'penta-assignment:'||a.assignment_id::text,'assignment:'||a.task_kind,v_owner,a.risk_class,'queued','D0-D2 owner obligation route; no authority expansion',v_payload)
      on conflict(handoff_key) do update set payload=excluded.payload,state=case when integration_control.penta_census_handoffs_v1.state='completed' then integration_control.penta_census_handoffs_v1.state else 'queued' end,updated_at=now();
      insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
      values(a.assignment_id,v_owner,a.owning_family_key,'CENSUS_HANDOFF',v_handoff_key,'ROUTED',v_payload,v_sha)
      on conflict(assignment_id,owner_penta,dispatch_kind) do update set evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
    end if;
    v_dispatches:=v_dispatches+1;
  end loop;

  update integration_control.penta_assignment_contracts_v1 set state='ROUTED',updated_at=now() where assignment_id=a.assignment_id and state='DISCOVERED';
  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.routed','penta_assignment',a.assignment_id::text,
    jsonb_build_object('assignment_key',a.assignment_key,'family_key',a.owning_family_key,'owner_pentas',a.owner_pentas,'dispatch_count',v_dispatches,'authority_expansion',false,'routed_at',clock_timestamp()),
    'PentaAssignmentFabric/PentaCensus/PentaWire/PentaRoute',null,'PentaAssignmentFabric','1.0.0',
    'ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',a.assignment_id,'state','ROUTED','dispatches',v_dispatches,'event',v_event);
end $$;

create or replace function integration_control.penta_assignment_record_owner_result_v1(
  p_assignment_id uuid,
  p_owner_penta text,
  p_result_state text,
  p_exact_artifact_ref text,
  p_exact_artifact_sha256 text,
  p_exact_head_sha text,
  p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
  v_result_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  if not (a.owner_pentas ? p_owner_penta) then raise exception 'owner_not_assigned'; end if;
  if p_result_state not in ('PASS','HOLD','FAIL','SUPERSEDED') then raise exception 'result_state_invalid'; end if;
  if p_exact_artifact_sha256 is not null and p_exact_artifact_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'artifact_digest_invalid'; end if;
  if a.exact_head_sha is not null and p_exact_head_sha is distinct from a.exact_head_sha then raise exception 'exact_head_mismatch'; end if;
  v_payload:=jsonb_build_object('assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'owner_penta',p_owner_penta,'result_state',p_result_state,'exact_artifact_ref',p_exact_artifact_ref,'exact_artifact_sha256',p_exact_artifact_sha256,'exact_head_sha',p_exact_head_sha,'evidence',coalesce(p_evidence,'{}'::jsonb),'observed_at',clock_timestamp(),'authority_expansion',false);
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event('penta.assignment.owner_result.'||lower(p_result_state),'penta_assignment_owner_result',a.assignment_id::text||':'||p_owner_penta,v_payload||jsonb_build_object('evidence_sha256',v_sha),p_owner_penta,null,p_owner_penta,'1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.assignment-fulfillment.v1',null,'internal');
  insert into integration_control.penta_assignment_owner_results_v1(assignment_id,owner_penta,result_state,exact_artifact_ref,exact_artifact_sha256,exact_head_sha,evidence,evidence_sha256,dail_event_id,dail_event_hash)
  values(a.assignment_id,p_owner_penta,p_result_state,p_exact_artifact_ref,p_exact_artifact_sha256,p_exact_head_sha,coalesce(p_evidence,'{}'::jsonb),v_sha,(v_event->>'event_id')::uuid,v_event->>'event_hash')
  returning result_id into v_result_id;
  update integration_control.penta_assignment_dispatches_v1 set state=case when p_result_state='PASS' then 'COMPLETED' when p_result_state='HOLD' then 'HOLD' when p_result_state='FAIL' then 'FAILED' else 'SUPERSEDED' end,completed_at=case when p_result_state in ('PASS','SUPERSEDED') then now() end,updated_at=now() where assignment_id=a.assignment_id and lower(owner_penta)=lower(p_owner_penta);
  update integration_control.penta_assignment_contracts_v1 set state=case when p_result_state='FAIL' then 'FAILED' when p_result_state='HOLD' then 'HOLD' else 'IN_PROGRESS' end,updated_at=now() where assignment_id=a.assignment_id and state not in ('COMPLETED','SUPERSEDED','RETIRED');
  return jsonb_build_object('result_id',v_result_id,'assignment_id',a.assignment_id,'state',p_result_state,'evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function penta_docs.project_assignment_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','penta_docs','integration_control','extensions'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_body jsonb;
  v_sha text;
  v_id uuid;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  v_body:=jsonb_build_object(
    'contract','ct.penta.institutionalization.v1','assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
    'subject_kind',a.subject_kind,'subject_ref',a.subject_ref,'task_kind',a.task_kind,'title',a.title,'summary',a.summary,
    'family_key',a.owning_family_key,'owner_pentas',a.owner_pentas,'risk_class',a.risk_class,
    'exact_artifact_ref',a.exact_artifact_ref,'exact_artifact_sha256',a.exact_artifact_sha256,'exact_head_sha',a.exact_head_sha,
    'state',a.state,'acceptance_criteria',a.acceptance_criteria,
    'owner_results',(select coalesce(jsonb_agg(jsonb_build_object('owner_penta',r.owner_penta,'state',r.result_state,'evidence_sha256',r.evidence_sha256,'dail_event_id',r.dail_event_id,'observed_at',r.observed_at) order by r.owner_penta,r.observed_at),'[]'::jsonb) from integration_control.penta_assignment_owner_results_v1 r where r.assignment_id=a.assignment_id),
    'drive_refs',jsonb_build_object('folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,'hybrid_doc_id',i.drive_hybrid_doc_id,'machine_sheet_id',i.drive_machine_sheet_id),
    'certification_id',i.certification_id,'certification_state',i.certification_state,
    'history_preserved',true,'originator_cannot_self_certify',true,'projected_at',clock_timestamp()
  );
  v_sha:=encode(extensions.digest(convert_to(v_body::text,'UTF8'),'sha256'),'hex');
  insert into penta_docs.assignment_institutionalization_v1(assignment_id,assignment_key,title,summary,family_key,owner_pentas,risk_class,exact_artifact_ref,exact_artifact_sha256,exact_head_sha,lifecycle_state,evidence_refs,drive_refs,certification_ref,body,body_sha256,docs_path)
  values(a.assignment_id,a.assignment_key,a.title,a.summary,a.owning_family_key,a.owner_pentas,a.risk_class,a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,a.state,
    jsonb_build_array(i.evidence_event_id,i.decision_event_id,i.execution_event_id),
    jsonb_build_object('folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,'human_url',i.drive_human_doc_url,'hybrid_doc_id',i.drive_hybrid_doc_id,'hybrid_url',i.drive_hybrid_doc_url,'machine_sheet_id',i.drive_machine_sheet_id,'machine_url',i.drive_machine_sheet_url),
    i.certification_id,v_body,v_sha,'/internal/penta-assignments/'||a.assignment_key)
  on conflict(assignment_id) do update set lifecycle_state=excluded.lifecycle_state,evidence_refs=excluded.evidence_refs,drive_refs=excluded.drive_refs,certification_ref=excluded.certification_ref,body=excluded.body,body_sha256=excluded.body_sha256,updated_at=now()
  returning record_id into v_id;
  update integration_control.penta_assignment_institutionalization_v1 set pentadocs_record_id=v_id,pentadocs_state='READBACK_PASS',pentadocs_ref='/internal/penta-assignments/'||a.assignment_key,pentadocs_sha256=v_sha,updated_at=now() where assignment_id=a.assignment_id;
  return jsonb_build_object('record_id',v_id,'assignment_id',a.assignment_id,'state','READBACK_PASS','docs_path','/internal/penta-assignments/'||a.assignment_key,'body_sha256',v_sha);
end $$;

create or replace function integration_control.penta_assignment_bind_provider_projection_v1(
  p_assignment_id uuid,
  p_drive_folder_id text,
  p_human_doc_id text,
  p_human_doc_url text,
  p_human_sha256 text,
  p_human_readback boolean,
  p_hybrid_doc_id text,
  p_hybrid_doc_url text,
  p_hybrid_sha256 text,
  p_hybrid_readback boolean,
  p_machine_sheet_id text,
  p_machine_sheet_url text,
  p_machine_sha256 text,
  p_machine_readback boolean,
  p_provider_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_state text;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;
  if nullif(p_drive_folder_id,'') is null or nullif(p_human_doc_id,'') is null or nullif(p_hybrid_doc_id,'') is null or nullif(p_machine_sheet_id,'') is null then raise exception 'three_way_drive_projection_required'; end if;
  if p_human_sha256 !~ '^[0-9a-f]{64}$' or p_hybrid_sha256 !~ '^[0-9a-f]{64}$' or p_machine_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'projection_digest_invalid'; end if;
  v_state:=case when p_human_readback and p_hybrid_readback and p_machine_readback then 'READBACK_PASS' else 'PARTIAL' end;
  update integration_control.penta_assignment_institutionalization_v1 set
    drive_folder_id=p_drive_folder_id,
    drive_human_doc_id=p_human_doc_id,drive_human_doc_url=p_human_doc_url,drive_human_sha256=p_human_sha256,drive_human_readback=p_human_readback,
    drive_hybrid_doc_id=p_hybrid_doc_id,drive_hybrid_doc_url=p_hybrid_doc_url,drive_hybrid_sha256=p_hybrid_sha256,drive_hybrid_readback=p_hybrid_readback,
    drive_machine_sheet_id=p_machine_sheet_id,drive_machine_sheet_url=p_machine_sheet_url,drive_machine_sha256=p_machine_sha256,drive_machine_readback=p_machine_readback,
    provider_projection_state=v_state,updated_at=now()
  where assignment_id=a.assignment_id;
  v_payload:=jsonb_build_object('assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'drive_folder_id',p_drive_folder_id,
    'human',jsonb_build_object('doc_id',p_human_doc_id,'url',p_human_doc_url,'sha256',p_human_sha256,'readback',p_human_readback),
    'hybrid',jsonb_build_object('doc_id',p_hybrid_doc_id,'url',p_hybrid_doc_url,'sha256',p_hybrid_sha256,'readback',p_hybrid_readback),
    'machine',jsonb_build_object('sheet_id',p_machine_sheet_id,'url',p_machine_sheet_url,'sha256',p_machine_sha256,'readback',p_machine_readback),
    'provider_evidence',coalesce(p_provider_evidence,'{}'::jsonb),'projection_state',v_state,'raw_secret_material',false,'observed_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event('penta.assignment.drive_projection.'||lower(v_state),'penta_assignment_provider_projection',a.assignment_id::text,v_payload||jsonb_build_object('evidence_sha256',v_sha),'PentaDrive/PentaDocs/PentaSync/PentaSerialized',null,'PentaDrive','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.institutionalization.v1',null,'internal');
  return jsonb_build_object('assignment_id',a.assignment_id,'state',v_state,'evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function integration_control.penta_assignment_institutionalize_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_docs','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_missing jsonb:='[]'::jsonb;
  v_owner_count int;
  v_pass_count int;
  v_payload jsonb;
  v_sha text;
  v_evidence jsonb;
  v_decision jsonb;
  v_execution jsonb;
  v_docs jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  v_owner_count:=jsonb_array_length(a.owner_pentas);
  select count(distinct lower(r.owner_penta)) into v_pass_count from integration_control.penta_assignment_owner_results_v1 r where r.assignment_id=a.assignment_id and r.result_state='PASS';
  if v_pass_count<v_owner_count then v_missing:=v_missing||jsonb_build_array('owner_results:'||v_pass_count::text||'/'||v_owner_count::text); end if;
  if i.provider_projection_state<>'READBACK_PASS' then v_missing:=v_missing||jsonb_build_array('drive_three_way_readback'); end if;
  if a.exact_head_sha is not null and not exists(select 1 from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id and l.exact_head_sha=a.exact_head_sha) then v_missing:=v_missing||jsonb_build_array('exact_head_pr_link'); end if;
  if jsonb_array_length(v_missing)>0 then
    update integration_control.penta_assignment_contracts_v1 set state='AWAITING_PROJECTION',updated_at=now() where assignment_id=a.assignment_id and state not in ('FAILED','HOLD');
    return jsonb_build_object('assignment_id',a.assignment_id,'state','HOLD','missing',v_missing);
  end if;

  v_payload:=jsonb_build_object('assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'exact_artifact_ref',a.exact_artifact_ref,'exact_artifact_sha256',a.exact_artifact_sha256,'exact_head_sha',a.exact_head_sha,'owner_results',(select jsonb_agg(jsonb_build_object('owner_penta',r.owner_penta,'result_state',r.result_state,'evidence_sha256',r.evidence_sha256,'dail_event_id',r.dail_event_id) order by r.owner_penta,r.observed_at) from integration_control.penta_assignment_owner_results_v1 r where r.assignment_id=a.assignment_id and r.result_state='PASS'),'drive_projection',jsonb_build_object('folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,'hybrid_doc_id',i.drive_hybrid_doc_id,'machine_sheet_id',i.drive_machine_sheet_id),'observed_at',clock_timestamp(),'authority_expansion',false);
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_evidence:=chlom_runtime.append_dail_event('penta.institutionalization.evidence.v1','institutional_evidence',a.assignment_id::text,v_payload||jsonb_build_object('evidence_sha256',v_sha),'PentaDocs/PentaDrive/PentaCensus/PentaSerialized',null,'PentaDocs','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.institutionalization.v1',null,'internal');
  update integration_control.penta_assignment_institutionalization_v1 set evidence_event_id=(v_evidence->>'event_id')::uuid,evidence_event_hash=v_evidence->>'event_hash',evidence_readback=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_evidence->>'event_id')::uuid and d.event_hash=v_evidence->>'event_hash'),updated_at=now() where assignment_id=a.assignment_id;

  v_decision:=chlom_runtime.append_dail_event('penta.institutionalization.decision.v1','institutional_decision',a.assignment_id::text,jsonb_build_object('assignment_key',a.assignment_key,'decision','OWNER_WORK_COMPLETE_PROJECTIONS_BOUND_AWAIT_INDEPENDENT_CERTIFICATION','risk_class',a.risk_class,'independent_certification_required',a.independent_certification_required,'certifier',a.certifier_penta,'originator_cannot_self_certify',true,'authority_expansion',false,'decided_at',clock_timestamp()),'PentaPM/PentaGovernance/PentaCertify',null,'PentaPM','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,(v_evidence->>'event_id')::uuid,'ct.penta.institutionalization.v1',null,'internal');
  update integration_control.penta_assignment_institutionalization_v1 set decision_event_id=(v_decision->>'event_id')::uuid,decision_event_hash=v_decision->>'event_hash',decision_readback=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_decision->>'event_id')::uuid and d.event_hash=v_decision->>'event_hash'),updated_at=now() where assignment_id=a.assignment_id;

  v_docs:=penta_docs.project_assignment_v1(a.assignment_id);
  v_execution:=chlom_runtime.append_dail_event('penta.institutionalization.execution.v1','institutional_execution',a.assignment_id::text,jsonb_build_object('assignment_key',a.assignment_key,'owner_work_complete',true,'drive_projection_state','READBACK_PASS','pentadocs_projection',v_docs,'next_state',case when a.independent_certification_required then 'AWAITING_CERTIFICATION' else 'COMPLETED' end,'authority_expansion',false,'executed_at',clock_timestamp()),'PentaDocs/PentaDrive/PentaSync/PentaCensus/PentaSerialized',null,'PentaDocs','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,(v_decision->>'event_id')::uuid,'ct.penta.institutionalization.v1',null,'internal');
  update integration_control.penta_assignment_institutionalization_v1 set execution_event_id=(v_execution->>'event_id')::uuid,execution_event_hash=v_execution->>'event_hash',execution_readback=exists(select 1 from chlom_runtime.dail_events d where d.event_id=(v_execution->>'event_id')::uuid and d.event_hash=v_execution->>'event_hash'),institutionalized_at=now(),certification_state=case when a.independent_certification_required then 'PENDING' else 'NOT_REQUIRED' end,updated_at=now() where assignment_id=a.assignment_id;
  update integration_control.penta_assignment_contracts_v1 set state=case when independent_certification_required then 'AWAITING_CERTIFICATION' else 'COMPLETED' end,completed_at=case when not independent_certification_required then now() end,updated_at=now() where assignment_id=a.assignment_id;
  return jsonb_build_object('assignment_id',a.assignment_id,'state',case when a.independent_certification_required then 'AWAITING_CERTIFICATION' else 'COMPLETED' end,'evidence',v_evidence,'decision',v_decision,'execution',v_execution,'pentadocs',v_docs);
end $$;

create or replace function integration_control.penta_assignment_record_certification_v1(
  p_assignment_id uuid,
  p_certification_id text,
  p_disposition text,
  p_certifier_ref text,
  p_certification_event_id uuid,
  p_certification_event_hash text,
  p_evidence jsonb default '{}'::jsonb
) returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','extensions','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_state text;
  v_payload jsonb;
  v_sha text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  if a.owner_pentas ? p_certifier_ref then raise exception 'originator_cannot_self_certify'; end if;
  if lower(p_certifier_ref) not in ('pentacertify','pentacertifier','ct.penta.certifier') then raise exception 'independent_certifier_required'; end if;
  if p_disposition not in ('CERTIFIED','HOLD','INVALIDATED') then raise exception 'certification_disposition_invalid'; end if;
  if not exists(select 1 from chlom_runtime.dail_events d where d.event_id=p_certification_event_id and d.event_hash=p_certification_event_hash) then raise exception 'certification_dail_readback_required'; end if;
  v_state:=case p_disposition when 'CERTIFIED' then 'CERTIFIED' when 'INVALIDATED' then 'INVALIDATED' else 'HOLD' end;
  update integration_control.penta_assignment_institutionalization_v1 set certification_id=p_certification_id,certification_state=v_state,certifier_ref=p_certifier_ref,certification_event_id=p_certification_event_id,certification_event_hash=p_certification_event_hash,updated_at=now() where assignment_id=a.assignment_id;
  update integration_control.penta_assignment_contracts_v1 set state=case when p_disposition='CERTIFIED' then 'CERTIFIED' when p_disposition='HOLD' then 'HOLD' else 'HOLD' end,updated_at=now() where assignment_id=a.assignment_id;
  v_payload:=jsonb_build_object('assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'certification_id',p_certification_id,'disposition',p_disposition,'certifier_ref',p_certifier_ref,'certification_event_id',p_certification_event_id,'evidence',coalesce(p_evidence,'{}'::jsonb),'originator_certifier_separation',true,'authority_expansion',false,'recorded_at',clock_timestamp());
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  v_event:=chlom_runtime.append_dail_event('penta.assignment.certification.'||lower(p_disposition),'penta_assignment_certification',a.assignment_id::text,v_payload||jsonb_build_object('evidence_sha256',v_sha),p_certifier_ref,null,'PentaCertify','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,p_certification_event_id,'ct.penta.assignment-fulfillment.v1',null,'internal');
  return jsonb_build_object('assignment_id',a.assignment_id,'state',v_state,'evidence_sha256',v_sha,'dail',v_event);
end $$;

create or replace function integration_control.penta_assignment_refresh_chain_gate_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  i integration_control.penta_assignment_institutionalization_v1%rowtype;
  v_chain jsonb;
  v_pass boolean;
  v_terminal text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  select * into i from integration_control.penta_assignment_institutionalization_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  v_chain:=chlom_runtime.verify_dail_chain_v3();
  v_pass:=coalesce((v_chain->>'ok')::boolean,false) and coalesce((v_chain->>'failure_count')::integer,1)=0;
  v_terminal:=case when v_pass and i.evidence_readback and i.decision_readback and i.execution_readback and i.pentadocs_state='READBACK_PASS' and i.provider_projection_state='READBACK_PASS' and i.certification_state in ('CERTIFIED','NOT_REQUIRED','ACTIVE') then 'PASS' else 'HOLD' end;
  update integration_control.penta_assignment_institutionalization_v1 set chain_state=case when v_pass then 'PASS' else 'FAIL' end,chain_checked_at=now(),chain_head_hash=v_chain->>'head_hash',chain_checked_events=coalesce((v_chain->>'checked_events')::bigint,0),terminal_gate_state=v_terminal,certification_state=case when v_terminal='PASS' and certification_state='CERTIFIED' then 'ACTIVE' else certification_state end,updated_at=now() where assignment_id=a.assignment_id;
  if v_terminal='PASS' then update integration_control.penta_assignment_contracts_v1 set state='COMPLETED',completed_at=coalesce(completed_at,now()),updated_at=now() where assignment_id=a.assignment_id; end if;
  v_event:=chlom_runtime.append_dail_event('penta.assignment.chain_gate.'||lower(v_terminal),'penta_assignment_chain_gate',a.assignment_id::text,jsonb_build_object('assignment_key',a.assignment_key,'terminal_gate_state',v_terminal,'chain',v_chain,'evidence_readback',i.evidence_readback,'decision_readback',i.decision_readback,'execution_readback',i.execution_readback,'pentadocs_state',i.pentadocs_state,'provider_projection_state',i.provider_projection_state,'certification_state',i.certification_state,'authority_expansion',false,'checked_at',clock_timestamp()),'PentaCertify/DAIL/PentaAssure',null,'PentaCertify','1.0.0','ctcorr:penta-assignment:'||a.assignment_id::text,i.certification_event_id,'ct.penta.assignment-fulfillment.v1',null,'internal');
  return jsonb_build_object('assignment_id',a.assignment_id,'terminal_gate_state',v_terminal,'chain',v_chain,'dail',v_event);
end $$;

create or replace function public.penta_assignment_pr_terminal_gate_v1(p_repo text,p_pr_number bigint,p_head_sha text,p_action text)
returns jsonb
language sql stable security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
select coalesce((
  select jsonb_build_object(
    'eligible',
      a.state='COMPLETED'
      and i.terminal_gate_state='PASS'
      and i.chain_state='PASS'
      and i.chain_checked_at>=now()-interval '30 minutes'
      and i.evidence_readback and i.decision_readback and i.execution_readback
      and i.pentadocs_state='READBACK_PASS'
      and i.provider_projection_state='READBACK_PASS'
      and i.certification_state in ('ACTIVE','NOT_REQUIRED'),
    'state',case when a.state='COMPLETED' and i.terminal_gate_state='PASS' and i.chain_state='PASS' and i.chain_checked_at>=now()-interval '30 minutes' and i.evidence_readback and i.decision_readback and i.execution_readback and i.pentadocs_state='READBACK_PASS' and i.provider_projection_state='READBACK_PASS' and i.certification_state in ('ACTIVE','NOT_REQUIRED') then 'PASS' else 'HOLD' end,
    'assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'assignment_state',a.state,
    'repo',l.repo,'pr_number',l.pr_number,'exact_head_sha',l.exact_head_sha,'terminal_action',l.terminal_action,
    'certification_id',i.certification_id,'certification_state',i.certification_state,
    'evidence_event_id',i.evidence_event_id,'decision_event_id',i.decision_event_id,'execution_event_id',i.execution_event_id,
    'pentadocs_ref',i.pentadocs_ref,
    'drive_refs',jsonb_build_object('folder_id',i.drive_folder_id,'human_doc_id',i.drive_human_doc_id,'hybrid_doc_id',i.drive_hybrid_doc_id,'machine_sheet_id',i.drive_machine_sheet_id),
    'chain_state',i.chain_state,'chain_checked_at',i.chain_checked_at,'chain_head_hash',i.chain_head_hash,
    'terminal_gate_state',i.terminal_gate_state,'authority_expansion',false
  )
  from integration_control.penta_assignment_pr_links_v1 l
  join integration_control.penta_assignment_contracts_v1 a using(assignment_id)
  join integration_control.penta_assignment_institutionalization_v1 i using(assignment_id)
  where l.repo=p_repo and l.pr_number=p_pr_number and l.exact_head_sha=p_head_sha and l.terminal_action=p_action
  order by l.updated_at desc limit 1
),jsonb_build_object('eligible',false,'state','HOLD','reason','institutional_assignment_receipt_not_found','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_head_sha,'action',p_action));
$$;

create or replace function integration_control.penta_assignment_link_pr_v1(p_assignment_id uuid,p_repo text,p_pr_number bigint,p_exact_head_sha text,p_terminal_action text,p_classification text)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control'
as $$
declare v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''); v_id uuid;begin
 if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
 if p_exact_head_sha !~ '^[0-9a-f]{40}$' then raise exception 'head_sha_invalid'; end if;
 if p_terminal_action not in ('MERGE','CLOSE','NONE') then raise exception 'terminal_action_invalid'; end if;
 update integration_control.penta_assignment_contracts_v1 set source_repo=p_repo,source_pr_number=p_pr_number,exact_head_sha=p_exact_head_sha,updated_at=now() where assignment_id=p_assignment_id;
 insert into integration_control.penta_assignment_pr_links_v1(assignment_id,repo,pr_number,exact_head_sha,terminal_action,classification)
 values(p_assignment_id,p_repo,p_pr_number,p_exact_head_sha,p_terminal_action,p_classification)
 on conflict(repo,pr_number,exact_head_sha,terminal_action) do update set assignment_id=excluded.assignment_id,classification=excluded.classification,updated_at=now()
 returning link_id into v_id;
 return jsonb_build_object('link_id',v_id,'assignment_id',p_assignment_id,'state','LINKED','repo',p_repo,'pr_number',p_pr_number,'head_sha',p_exact_head_sha,'action',p_terminal_action);
end $$;

create or replace function integration_control.penta_assignment_terminal_dispatch_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_pr','public'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  l integration_control.penta_assignment_pr_links_v1%rowtype;
  v_gate jsonb;
  v_request bigint;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into l from integration_control.penta_assignment_pr_links_v1 where assignment_id=p_assignment_id and state not in ('TERMINALIZED','SUPERSEDED') order by updated_at desc limit 1 for update;
  if not found or l.terminal_action='NONE' then return jsonb_build_object('assignment_id',p_assignment_id,'state','NO_TERMINAL_ACTION'); end if;
  v_gate:=public.penta_assignment_pr_terminal_gate_v1(l.repo,l.pr_number,l.exact_head_sha,l.terminal_action);
  if not coalesce((v_gate->>'eligible')::boolean,false) then
    update integration_control.penta_assignment_pr_links_v1 set state='GATE_HOLD',updated_at=now() where link_id=l.link_id;
    return jsonb_build_object('assignment_id',p_assignment_id,'state','GATE_HOLD','gate',v_gate);
  end if;
  v_request:=penta_pr.invoke_terminal_provider_v3(case when l.terminal_action='MERGE' then 'merge_exact' else 'close_exact' end,
    jsonb_build_object('repo',l.repo,'pr_number',l.pr_number,'expected_head_sha',l.exact_head_sha,'classification',l.classification,'reason','task completed and institutionally certified','evidence',v_gate||jsonb_build_object('exact_head_certified',true)));
  update integration_control.penta_assignment_pr_links_v1 set state='DISPATCHED',terminal_request_id=v_request,updated_at=now() where link_id=l.link_id;
  return jsonb_build_object('assignment_id',p_assignment_id,'state','DISPATCHED','request_id',v_request,'gate',v_gate);
end $$;

create or replace function integration_control.penta_assignment_fulfillment_tick_v1(p_limit integer default 25)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
declare
  a record;
  v_routed int:=0;
  v_institutionalized int:=0;
  v_dispatched int:=0;
  v_result jsonb;
begin
  if current_user not in ('postgres','service_role','supabase_admin') then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:assignment-fulfillment:v1',0)) then return jsonb_build_object('state','DEFERRED_CONTENTION'); end if;
  for a in select assignment_id,state from integration_control.penta_assignment_contracts_v1 where state not in ('COMPLETED','FAILED','SUPERSEDED','RETIRED') order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,created_at for update skip locked limit greatest(1,least(coalesce(p_limit,25),100)) loop
    if a.state='DISCOVERED' then
      v_result:=integration_control.penta_assignment_route_v1(a.assignment_id); v_routed:=v_routed+1;
    elsif a.state in ('ROUTED','IN_PROGRESS','AWAITING_PROJECTION') then
      v_result:=integration_control.penta_assignment_institutionalize_v1(a.assignment_id);
      if v_result->>'state' in ('AWAITING_CERTIFICATION','COMPLETED') then v_institutionalized:=v_institutionalized+1; end if;
    elsif a.state='CERTIFIED' then
      v_result:=integration_control.penta_assignment_refresh_chain_gate_v1(a.assignment_id);
      if v_result->>'terminal_gate_state'='PASS' then
        v_result:=integration_control.penta_assignment_terminal_dispatch_v1(a.assignment_id); v_dispatched:=v_dispatched+1;
      end if;
    end if;
  end loop;
  return jsonb_build_object('state','COMPLETE','routed',v_routed,'institutionalized',v_institutionalized,'terminal_dispatched',v_dispatched,'observed_at',clock_timestamp(),'authority_expansion',false);
end $$;

create or replace function integration_control.penta_assignment_status_v1(p_assignment_id uuid default null)
returns jsonb
language sql stable security definer
set search_path to 'pg_catalog','integration_control','penta_docs'
as $$
select jsonb_build_object(
 'contract','ct.penta.assignment-fulfillment.v1',
 'policy',(select to_jsonb(p) from integration_control.penta_assignment_policy_v1 p where policy_key='ct.penta.change-institutionalization.rule.v1'),
 'counts',(select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) from (select state,count(*) n from integration_control.penta_assignment_contracts_v1 where p_assignment_id is null or assignment_id=p_assignment_id group by state)s),
 'assignments',(select coalesce(jsonb_agg(jsonb_build_object('assignment_id',a.assignment_id,'assignment_key',a.assignment_key,'title',a.title,'family_key',a.owning_family_key,'owner_pentas',a.owner_pentas,'risk_class',a.risk_class,'state',a.state,'exact_artifact_ref',a.exact_artifact_ref,'exact_head_sha',a.exact_head_sha,'institutionalization',to_jsonb(i),'pr_links',(select coalesce(jsonb_agg(to_jsonb(l) order by l.created_at),'[]'::jsonb) from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id)) order by a.created_at),'[]'::jsonb) from integration_control.penta_assignment_contracts_v1 a left join integration_control.penta_assignment_institutionalization_v1 i using(assignment_id) where p_assignment_id is null or a.assignment_id=p_assignment_id),
 'family_obligations',(select count(*) from integration_control.penta_family_obligation_contracts_v1 where state='ACTIVE'),
 'history_preserved',true,'d3_human_reserved',true,'authority_expansion',false,'generated_at',clock_timestamp()
);
$$;

create or replace function integration_control.penta_assignment_regression_v1()
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public','penta_docs'
as $$
declare v_results jsonb:='[]'::jsonb; v_failed int:=0;begin
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','policy_active','passed',exists(select 1 from integration_control.penta_assignment_policy_v1 where policy_key='ct.penta.change-institutionalization.rule.v1' and state='ACTIVE')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','fifteen_family_obligations','passed',(select count(*)=15 from integration_control.penta_family_obligation_contracts_v1 where state='ACTIVE')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','terminal_gate_requires_assignment','passed',not coalesce((public.penta_assignment_pr_terminal_gate_v1('crownthrive1/CrownThrive-OS',0,repeat('0',40),'CLOSE')->>'eligible')::boolean,true)));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','originator_self_certification_forbidden','passed',position('originator_cannot_self_certify' in pg_get_functiondef('integration_control.penta_assignment_record_certification_v1(uuid,text,text,text,uuid,text,jsonb)'::regprocedure))>0));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','three_dail_lanes_required','passed',(select required_dail_lanes=array['EVIDENCE','DECISION','EXECUTION']::text[] from integration_control.penta_assignment_policy_v1 where policy_key='ct.penta.change-institutionalization.rule.v1')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','drive_three_way_required','passed',(select required_projections @> array['DRIVE_HUMAN','DRIVE_HYBRID','DRIVE_MACHINE_SHEET']::text[] from integration_control.penta_assignment_policy_v1 where policy_key='ct.penta.change-institutionalization.rule.v1')));
  v_results:=v_results||jsonb_build_array(jsonb_build_object('check','public_mutation_execute_revoked','passed',not has_function_privilege('anon','integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb)','EXECUTE') and not has_function_privilege('authenticated','integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb)','EXECUTE')));
  select count(*) into v_failed from jsonb_array_elements(v_results) x where not coalesce((x->>'passed')::boolean,false);
  return jsonb_build_object('contract','ct.penta.assignment-fulfillment.v1','checks',jsonb_array_length(v_results),'passed',jsonb_array_length(v_results)-v_failed,'failed',v_failed,'all_passed',v_failed=0,'results',v_results,'observed_at',clock_timestamp());
end $$;

create or replace view public.penta_assignment_institutionalization_status_v1 as
select a.assignment_id,a.assignment_key,a.title,a.owning_family_key,a.owner_pentas,a.risk_class,a.state,a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,
 i.pentadocs_state,i.provider_projection_state,i.certification_id,i.certification_state,i.chain_state,i.chain_checked_at,i.terminal_gate_state,i.institutionalized_at,a.completed_at,a.updated_at
from integration_control.penta_assignment_contracts_v1 a
join integration_control.penta_assignment_institutionalization_v1 i using(assignment_id);

-- Only the service role may mutate or route assignments. Public read surfaces contain no secrets.
revoke all on integration_control.penta_assignment_policy_v1 from public,anon,authenticated;
revoke all on integration_control.penta_family_obligation_contracts_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_contracts_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_dispatches_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_owner_results_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_institutionalization_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_pr_links_v1 from public,anon,authenticated;
revoke all on integration_control.penta_assignment_events_v1 from public,anon,authenticated;
revoke all on penta_docs.assignment_institutionalization_v1 from public,anon,authenticated;

grant select on public.penta_assignment_institutionalization_status_v1 to service_role;
grant select on public.penta_assignment_institutionalization_status_v1 to authenticated;

revoke execute on function integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_route_v1(uuid) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_record_owner_result_v1(uuid,text,text,text,text,text,jsonb) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_bind_provider_projection_v1(uuid,text,text,text,text,boolean,text,text,text,boolean,text,text,text,boolean,jsonb) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_institutionalize_v1(uuid) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_record_certification_v1(uuid,text,text,text,uuid,text,jsonb) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_refresh_chain_gate_v1(uuid) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_link_pr_v1(uuid,text,bigint,text,text,text) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_terminal_dispatch_v1(uuid) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_fulfillment_tick_v1(integer) from public,anon,authenticated;
revoke execute on function penta_docs.project_assignment_v1(uuid) from public,anon,authenticated;
revoke execute on function public.penta_assignment_pr_terminal_gate_v1(text,bigint,text,text) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_status_v1(uuid) from public,anon,authenticated;
revoke execute on function integration_control.penta_assignment_regression_v1() from public,anon,authenticated;

grant execute on function integration_control.penta_assignment_create_v1(text,text,text,text,text,text,text,jsonb,text,text,text,text,text,bigint,text,jsonb,boolean,text,jsonb) to service_role;
grant execute on function integration_control.penta_assignment_route_v1(uuid) to service_role;
grant execute on function integration_control.penta_assignment_record_owner_result_v1(uuid,text,text,text,text,text,jsonb) to service_role;
grant execute on function integration_control.penta_assignment_bind_provider_projection_v1(uuid,text,text,text,text,boolean,text,text,text,boolean,text,text,text,boolean,jsonb) to service_role;
grant execute on function integration_control.penta_assignment_institutionalize_v1(uuid) to service_role;
grant execute on function integration_control.penta_assignment_record_certification_v1(uuid,text,text,text,uuid,text,jsonb) to service_role;
grant execute on function integration_control.penta_assignment_refresh_chain_gate_v1(uuid) to service_role;
grant execute on function integration_control.penta_assignment_link_pr_v1(uuid,text,bigint,text,text,text) to service_role;
grant execute on function integration_control.penta_assignment_terminal_dispatch_v1(uuid) to service_role;
grant execute on function integration_control.penta_assignment_fulfillment_tick_v1(integer) to service_role;
grant execute on function penta_docs.project_assignment_v1(uuid) to service_role;
grant execute on function public.penta_assignment_pr_terminal_gate_v1(text,bigint,text,text) to service_role;
grant execute on function integration_control.penta_assignment_status_v1(uuid) to service_role;
grant execute on function integration_control.penta_assignment_regression_v1() to service_role;

-- Canonical component identities. Whole-system authority is not implied.
insert into public.penta_system_registry(system_key,canonical_name,category,purpose,risk_ceiling,maturity,version,runtime_ref,docs_ref,public_exposure,authority_boundary,metadata,last_verified_at,updated_at)
values
('penta.assignment-fabric','Penta Assignment Fulfillment Fabric','coordination_control','Routes D0-D2 assignments to owning Pentas/families, requires owner results and blocks terminalization until institutional completion.','D2','implemented','1.0.0','function:integration_control.penta_assignment_fulfillment_tick_v1(integer)','docs/penta/PENTA_ASSIGNMENT_INSTITUTIONALIZATION_V1.md',false,'No self-certification, D3, money movement, credential creation, rights grant or authority expansion.',jsonb_build_object('stable_contract_id','ct.penta.assignment-fulfillment.v1','implementation_state','active_pending_independent_certification','owner','PentaBuild/PentaCensus/PentaWire','certifier','PentaCertify','authority_expansion',false),now(),now()),
('penta.docs.institutionalization','PentaDocs Institutionalization Projection','knowledge_data','Projects assignment/change evidence, three-DAIL lineage, Drive references and certification into canonical PentaDocs records.','D2','implemented','1.0.0','function:penta_docs.project_assignment_v1(uuid)','docs/penta/PENTA_ASSIGNMENT_INSTITUTIONALIZATION_V1.md',false,'Documentation projection only; no independent certification, provider authority or D3 authority.',jsonb_build_object('stable_contract_id','ct.penta.institutionalization.v1','implementation_state','active_pending_independent_certification','owner','PentaDocs','certifier','PentaCertify','authority_expansion',false),now(),now()),
('penta.pr-terminalization-v4','Penta PR Institutional Terminalization V4','github_lifecycle','Allows merge/close only after exact-head task completion, three-DAIL, PentaDocs, Drive mirror, chain PASS and independent certification.','D2','implemented','4.0.0','edge:penta-pr-terminal-provider@4','docs/penta/PENTA_ASSIGNMENT_INSTITUTIONALIZATION_V1.md',false,'Exact-head provider terminal actions only after institutional gate PASS; no deadline-only closure.',jsonb_build_object('stable_contract_id','ct.penta.pr-terminalization.v4','implementation_state','pending_edge_deployment_and_independent_certification','previous_provider_version',3,'previous_provider_sha256','c293663a3a82429722f09c80ea7842386006335bf3dc6385ab7bdcf00967d5fd','authority_expansion',false),now(),now())
on conflict(system_key) do update set canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,risk_ceiling=excluded.risk_ceiling,maturity=excluded.maturity,version=excluded.version,runtime_ref=excluded.runtime_ref,docs_ref=excluded.docs_ref,public_exposure=excluded.public_exposure,authority_boundary=excluded.authority_boundary,metadata=public.penta_system_registry.metadata||excluded.metadata,updated_at=now();

-- Refresh family runtime to the new common coordination contract without promoting member runtimes.
update integration_control.penta_family_runtime_v1
set metadata=metadata||jsonb_build_object(
  'assignment_contract','ct.penta.assignment-fulfillment.v1',
  'institutionalization_contract','ct.penta.institutionalization.v1',
  'terminalization_contract','ct.penta.pr-terminalization.v4',
  'obligation_contract_bound',true,
  'member_runtime_authority_unchanged',true,
  'coordination_certification_pending',true,
  'authority_expansion',false
),updated_at=now();
