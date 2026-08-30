-- CrownThrive COS V1 phase/certification control plane
-- Phase 00 constitutional baseline infrastructure.
-- Additive only. No provider writes, money movement, rights grants, scheduler activation, or D3 authority.

begin;

create table if not exists integration_control.cos_phase_registry_v1 (
  phase_id text primary key check (phase_id ~ '^(0[0-9]|1[0-5])$'),
  ordinal smallint not null unique check (ordinal between 0 and 15),
  slug text not null unique,
  canonical_name text not null,
  objective text not null,
  predecessor_phase_id text null references integration_control.cos_phase_registry_v1(phase_id) on update restrict on delete restrict,
  state text not null default 'planned' check (state in ('planned','active','hold','certified','production_certified','retired','superseded')),
  authority_ceiling text not null default 'D2' check (authority_ceiling in ('D0','D1','D2','D3')),
  requires_d3 boolean not null default false,
  release_blocking boolean not null default true,
  source_ref text not null,
  source_sha text null check (source_sha is null or source_sha ~ '^[0-9a-f]{40,64}$'),
  rollback_ref text null,
  latest_execution_id uuid null,
  latest_dail_event_id text null,
  entry_criteria jsonb not null default '{}'::jsonb,
  exit_criteria jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.cos_phase_executions_v1 (
  execution_id uuid primary key default gen_random_uuid(),
  execution_seq bigint generated always as identity unique,
  release_id text not null references integration_control.cos_release_registry_v1(release_id) on update restrict on delete restrict,
  phase_id text not null references integration_control.cos_phase_registry_v1(phase_id) on update restrict on delete restrict,
  state text not null default 'running' check (state in ('running','testing','readback','certifying','hold','passed','failed','rolled_back')),
  originator_actor text not null check (nullif(btrim(originator_actor),'') is not null),
  source_sha text not null check (source_sha ~ '^[0-9a-f]{40,64}$'),
  pre_state jsonb not null,
  rollback_point jsonb not null,
  mutation_scope jsonb not null default '{}'::jsonb,
  test_matrix jsonb not null default '{}'::jsonb,
  provider_readback jsonb not null default '{}'::jsonb,
  cleanup_receipt jsonb not null default '{}'::jsonb,
  penta_context_ref text null,
  chlom_ref text null,
  drive_ref text null,
  dail_event_id text null,
  evidence_sha256 text null check (evidence_sha256 is null or evidence_sha256 ~ '^[0-9a-f]{64}$'),
  started_at timestamptz not null default now(),
  ended_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table integration_control.cos_phase_registry_v1
  drop constraint if exists cos_phase_registry_latest_execution_fk;
alter table integration_control.cos_phase_registry_v1
  add constraint cos_phase_registry_latest_execution_fk
  foreign key (latest_execution_id)
  references integration_control.cos_phase_executions_v1(execution_id)
  on update restrict on delete set null;

create table if not exists integration_control.cos_phase_gate_requirements_v1 (
  phase_id text not null references integration_control.cos_phase_registry_v1(phase_id) on update restrict on delete cascade,
  gate_name text not null,
  gate_order smallint not null,
  required boolean not null default true,
  independent_required boolean not null default false,
  provider_readback_required boolean not null default false,
  description text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (phase_id,gate_name),
  unique (phase_id,gate_order)
);

create table if not exists integration_control.cos_phase_gate_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  execution_id uuid not null references integration_control.cos_phase_executions_v1(execution_id) on update restrict on delete restrict,
  phase_id text not null references integration_control.cos_phase_registry_v1(phase_id) on update restrict on delete restrict,
  gate_name text not null,
  gate_state text not null check (gate_state in ('PASS','HOLD','FAIL','UNKNOWN')),
  verifier_actor text not null check (nullif(btrim(verifier_actor),'') is not null),
  evidence_refs jsonb not null default '[]'::jsonb,
  evidence_sha256 text not null check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  notes text null,
  observed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists cos_phase_gate_receipts_execution_gate_idx
  on integration_control.cos_phase_gate_receipts_v1(execution_id,gate_name,observed_at desc,created_at desc);

create index if not exists cos_phase_executions_release_phase_idx
  on integration_control.cos_phase_executions_v1(release_id,phase_id,execution_seq desc);

insert into integration_control.cos_phase_registry_v1(
  phase_id,ordinal,slug,canonical_name,objective,predecessor_phase_id,state,authority_ceiling,requires_d3,release_blocking,source_ref,entry_criteria,exit_criteria,metadata
) values
  ('00',0,'constitutional-baseline','Constitutional Baseline','Freeze COS laws, typed truth, namespaces, authority levels, security model, release contract, rollback baseline, and acceptance gates.',null,'active','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor_required":false}'::jsonb,'{"all_required_gates_pass":true,"dail_terminal_receipt":true}'::jsonb,'{"program":"COS V1","frozen":true}'::jsonb),
  ('01',1,'universal-census','Universal Census','Discover and UUID every CrownThrive-owned or operated entity with zero unexplained institutional objects.','00','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"00"}'::jsonb,'{"unknown_institutional_state":0}'::jsonb,'{}'::jsonb),
  ('02',2,'identity-knowledge-graph','Identity + Knowledge Graph','Build aliases, relationships, dependency graph, object model, and historical identity resolution.','01','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"01"}'::jsonb,'{"identity_graph_complete":true}'::jsonb,'{}'::jsonb),
  ('03',3,'dail-trust-v2','DAIL Trust V2','Add signed epochs, Merkle checkpoints, inclusion proofs, and governed CHLOM anchoring while preserving the current ledger.','02','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"02"}'::jsonb,'{"dail_integrity_verified":true}'::jsonb,'{}'::jsonb),
  ('04',4,'pentas-cos-epoch','Pentas COS Epoch','Require signed packets, origin identity, cookies, causation, idempotency, TTL/hops, policy decision, and receipt lineage.','03','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"03"}'::jsonb,'{"packet_contract_verified":true}'::jsonb,'{}'::jsonb),
  ('05',5,'pentawire-mcp-a2a','PentaWire / MCP / A2A Fabric','Converge capability-first provider and agent access with MCP vertically, A2A horizontally, and explicit authority gates.','04','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"04"}'::jsonb,'{"capability_fabric_verified":true}'::jsonb,'{}'::jsonb),
  ('06',6,'routing-temporal-fabric','Routing + Temporal Fabric','Converge routing, queue, retry, load, balancing, time, tick, dispatch, and scheduler ownership; eliminate duplicate clocks.','05','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"05"}'::jsonb,'{"duplicate_authoritative_clocks":0}'::jsonb,'{}'::jsonb),
  ('07',7,'autonomous-operations','Autonomous Operations','Harden Planner, SELF, Health, Heartbeat, OD, Nurture, Discovery, Census, and bounded repair loops.','06','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"06"}'::jsonb,'{"bounded_autonomy_verified":true}'::jsonb,'{}'::jsonb),
  ('08',8,'software-factory','Software Factory','Harden build-test-certify-PR-merge-release-deploy-readback-rollback as one governed production path.','07','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"07"}'::jsonb,'{"factory_end_to_end_verified":true}'::jsonb,'{}'::jsonb),
  ('09',9,'repository-deployment-fabric','Repository + Deployment Fabric','Reconcile repositories, branches, releases, deployments, schemas, and production SHAs into Census.','08','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"08"}'::jsonb,'{"source_to_production_lineage_verified":true}'::jsonb,'{}'::jsonb),
  ('10',10,'provider-credential-fabric','Provider + Credential Fabric','Certify provider capabilities independently, prefer OIDC/workload identity, and keep raw secrets out of Pentas/DAIL.','09','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"09"}'::jsonb,'{"provider_capabilities_verified":true,"raw_secret_leakage":0}'::jsonb,'{}'::jsonb),
  ('11',11,'economic-commerce-fabric','Economic + Commerce Fabric','Converge PentaPay, PentaCosts, PentaGreen, payment providers, entitlements, products, commissions, and economic reconciliation.','10','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"10"}'::jsonb,'{"economic_reconciliation_verified":true}'::jsonb,'{}'::jsonb),
  ('12',12,'experience-growth-fabric','Experience + Growth Fabric','Converge sites, Crown Affiliates, CrownThrive IO, CrownLytics, CrownPulse, ThrivePush, forms, content, media, and the Thrive Flywheel.','11','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"11"}'::jsonb,'{"experience_growth_fabric_verified":true}'::jsonb,'{}'::jsonb),
  ('13',13,'continuity-security','Continuity + Security','Verify HOT/WARM/COLD continuity, recovery, isolation, failover, attack testing, and disaster drills.','12','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"12"}'::jsonb,'{"restore_drill_verified":true,"critical_security_defects":0}'::jsonb,'{}'::jsonb),
  ('14',14,'command-center','COS Command Center','Deliver full operational UI, ontology/object views, graph explorer, governance queue, incidents, certifications, and system control.','13','planned','D2',false,true,'ct.package.cos-v1.production-constitution','{"predecessor":"13"}'::jsonb,'{"command_center_e2e_verified":true}'::jsonb,'{}'::jsonb),
  ('15',15,'production-certification','Production Certification','Run full-system load, security, failure, regression, recovery, provider readback, evidence packaging, signing, and COS V1.0.0 release certification.','14','planned','D3',true,true,'ct.package.cos-v1.production-constitution','{"predecessor":"14","human_reserved_release_authority":true}'::jsonb,'{"production_sha_bound":true,"released_at_bound":true,"known_release_blocking_defects":0}'::jsonb,'{"final_phase":true}'::jsonb)
on conflict (phase_id) do update set
  ordinal=excluded.ordinal,
  slug=excluded.slug,
  canonical_name=excluded.canonical_name,
  objective=excluded.objective,
  predecessor_phase_id=excluded.predecessor_phase_id,
  authority_ceiling=excluded.authority_ceiling,
  requires_d3=excluded.requires_d3,
  release_blocking=excluded.release_blocking,
  source_ref=excluded.source_ref,
  entry_criteria=excluded.entry_criteria,
  exit_criteria=excluded.exit_criteria,
  metadata=integration_control.cos_phase_registry_v1.metadata || excluded.metadata,
  updated_at=now();

with gates(gate_order,gate_name,independent_required,provider_readback_required,description) as (
  values
    (1,'pre_state',false,false,'Exact pre-state captured before mutation.'),
    (2,'census_dependency_read',false,false,'Current Census and dependency state read and bound.'),
    (3,'r1_rollback',false,false,'R1 rollback point is explicit and independently reconstructable.'),
    (4,'static_unit_test',false,false,'Static and unit tests pass for the exact candidate.'),
    (5,'contract_test',false,false,'Interface and contract tests pass for the exact candidate.'),
    (6,'integration_test',false,false,'Integration tests pass across affected dependencies.'),
    (7,'security_test',true,false,'Independent security/least-privilege/adversarial checks pass.'),
    (8,'failure_retry_test',false,false,'Failure, retry, idempotency, and replay tests pass.'),
    (9,'canary',false,false,'Bounded canary passes without unexplained side effects.'),
    (10,'provider_production_readback',true,true,'Independent provider/production readback matches exact candidate state.'),
    (11,'independent_certification',true,false,'Non-originating verifier independently certifies the phase evidence.'),
    (12,'regression_test',true,false,'Independent regression verification passes.'),
    (13,'cleanup_retire_superseded',false,false,'Superseded state is intentionally retired or preserved without authority drift.'),
    (14,'dail_binding',false,false,'Material outcomes are appended and read back through canonical DAIL.'),
    (15,'penta_context_census_binding',false,false,'Current institutional state is reconciled into PentaContext and Census.'),
    (16,'chlom_binding',false,false,'Identity, rights, authority, and provenance are bound through CHLOM where applicable.'),
    (17,'governed_docs_projection',false,false,'Human/machine/hybrid documentation projection is current and public/private boundaries hold.')
)
insert into integration_control.cos_phase_gate_requirements_v1(
  phase_id,gate_name,gate_order,required,independent_required,provider_readback_required,description
)
select p.phase_id,g.gate_name,g.gate_order,true,g.independent_required,g.provider_readback_required,g.description
from integration_control.cos_phase_registry_v1 p cross join gates g
on conflict (phase_id,gate_name) do update set
  gate_order=excluded.gate_order,
  required=excluded.required,
  independent_required=excluded.independent_required,
  provider_readback_required=excluded.provider_readback_required,
  description=excluded.description,
  updated_at=now();

create or replace function integration_control.cos_phase_begin_v1(
  p_release_id text,
  p_phase_id text,
  p_originator_actor text,
  p_source_sha text,
  p_pre_state jsonb,
  p_rollback_point jsonb,
  p_mutation_scope jsonb default '{}'::jsonb
) returns uuid
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_execution_id uuid;
  v_predecessor text;
  v_predecessor_state text;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;
  if p_source_sha is null or p_source_sha !~ '^[0-9a-f]{40,64}$' then
    raise exception 'invalid_source_sha';
  end if;
  if p_pre_state is null or p_pre_state='{}'::jsonb then
    raise exception 'pre_state_required';
  end if;
  if p_rollback_point is null or p_rollback_point='{}'::jsonb then
    raise exception 'r1_rollback_required';
  end if;
  select predecessor_phase_id into v_predecessor
  from integration_control.cos_phase_registry_v1 where phase_id=p_phase_id for update;
  if not found then raise exception 'unknown_phase:%',p_phase_id; end if;
  if v_predecessor is not null then
    select state into v_predecessor_state from integration_control.cos_phase_registry_v1 where phase_id=v_predecessor;
    if v_predecessor_state not in ('certified','production_certified') then
      raise exception 'predecessor_not_certified:%:%',v_predecessor,v_predecessor_state;
    end if;
  end if;
  if exists(select 1 from integration_control.cos_phase_executions_v1 where release_id=p_release_id and phase_id=p_phase_id and state in ('running','testing','readback','certifying')) then
    raise exception 'phase_execution_already_active:%',p_phase_id;
  end if;
  insert into integration_control.cos_phase_executions_v1(
    release_id,phase_id,state,originator_actor,source_sha,pre_state,rollback_point,mutation_scope
  ) values (
    p_release_id,p_phase_id,'running',p_originator_actor,p_source_sha,p_pre_state,p_rollback_point,coalesce(p_mutation_scope,'{}'::jsonb)
  ) returning execution_id into v_execution_id;
  update integration_control.cos_phase_registry_v1
  set state='active',latest_execution_id=v_execution_id,source_sha=p_source_sha,updated_at=now()
  where phase_id=p_phase_id;
  return v_execution_id;
end
$$;

create or replace function integration_control.cos_phase_record_gate_v1(
  p_execution_id uuid,
  p_gate_name text,
  p_gate_state text,
  p_verifier_actor text,
  p_evidence_refs jsonb,
  p_evidence_sha256 text,
  p_notes text default null
) returns uuid
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
declare
  v_receipt_id uuid;
  v_phase_id text;
  v_originator_actor text;
  v_independent_required boolean;
begin
  if current_user not in ('postgres','service_role') then
    raise exception 'service_role_required';
  end if;
  if p_gate_state not in ('PASS','HOLD','FAIL','UNKNOWN') then raise exception 'invalid_gate_state'; end if;
  if p_evidence_sha256 is null or p_evidence_sha256 !~ '^[0-9a-f]{64}$' then raise exception 'evidence_sha256_required'; end if;
  select e.phase_id,e.originator_actor,r.independent_required
    into v_phase_id,v_originator_actor,v_independent_required
  from integration_control.cos_phase_executions_v1 e
  join integration_control.cos_phase_gate_requirements_v1 r on r.phase_id=e.phase_id and r.gate_name=p_gate_name
  where e.execution_id=p_execution_id;
  if not found then raise exception 'unknown_execution_or_gate'; end if;
  if v_independent_required and p_verifier_actor=v_originator_actor then
    raise exception 'originator_cannot_verify_independent_gate:%',p_gate_name;
  end if;
  insert into integration_control.cos_phase_gate_receipts_v1(
    execution_id,phase_id,gate_name,gate_state,verifier_actor,evidence_refs,evidence_sha256,notes
  ) values (
    p_execution_id,v_phase_id,p_gate_name,p_gate_state,p_verifier_actor,coalesce(p_evidence_refs,'[]'::jsonb),p_evidence_sha256,p_notes
  ) returning receipt_id into v_receipt_id;
  update integration_control.cos_phase_executions_v1
  set state=case when p_gate_state in ('FAIL','HOLD') then 'hold' else state end,updated_at=now()
  where execution_id=p_execution_id;
  return v_receipt_id;
end
$$;

create or replace function integration_control.cos_phase_evaluate_v1(p_execution_id uuid)
returns jsonb
language sql
security definer
set search_path to pg_catalog,integration_control
as $$
with execution as (
  select * from integration_control.cos_phase_executions_v1 where execution_id=p_execution_id
), req as (
  select r.* from integration_control.cos_phase_gate_requirements_v1 r join execution e on e.phase_id=r.phase_id where r.required
), latest as (
  select distinct on (g.gate_name) g.gate_name,g.gate_state,g.verifier_actor,g.evidence_sha256,g.observed_at
  from integration_control.cos_phase_gate_receipts_v1 g
  where g.execution_id=p_execution_id
  order by g.gate_name,g.observed_at desc,g.created_at desc
), joined as (
  select r.gate_name,r.independent_required,r.provider_readback_required,l.gate_state,l.verifier_actor,l.evidence_sha256,l.observed_at,
         e.originator_actor
  from req r cross join execution e left join latest l using(gate_name)
), summary as (
  select count(*) required_count,
         count(*) filter(where gate_state='PASS') pass_count,
         count(*) filter(where gate_state is null) missing_count,
         count(*) filter(where gate_state in ('HOLD','FAIL','UNKNOWN')) nonpass_count,
         count(*) filter(where independent_required and gate_state='PASS' and verifier_actor=originator_actor) independence_violations,
         count(*) filter(where provider_readback_required and gate_state='PASS') provider_readback_pass_count
  from joined
)
select jsonb_build_object(
  'execution_id',p_execution_id,
  'phase_id',(select phase_id from execution),
  'release_id',(select release_id from execution),
  'state',(select state from execution),
  'source_sha',(select source_sha from execution),
  'required_gate_count',required_count,
  'pass_count',pass_count,
  'missing_count',missing_count,
  'nonpass_count',nonpass_count,
  'independence_violations',independence_violations,
  'provider_readback_pass_count',provider_readback_pass_count,
  'ready',required_count>0 and pass_count=required_count and missing_count=0 and nonpass_count=0 and independence_violations=0,
  'gates',(select coalesce(jsonb_object_agg(gate_name,jsonb_build_object('state',coalesce(gate_state,'MISSING'),'verifier',verifier_actor,'evidence_sha256',evidence_sha256,'observed_at',observed_at)),'{}'::jsonb) from joined)
) from summary;
$$;

create or replace function integration_control.cos_phase_finalize_v1(
  p_execution_id uuid,
  p_actor text
) returns jsonb
language plpgsql
security definer
set search_path to pg_catalog,integration_control,chlom_runtime
as $$
declare
  v_eval jsonb;
  v_phase_id text;
  v_release_id text;
  v_source_sha text;
  v_dail jsonb;
  v_phase_state text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  v_eval:=integration_control.cos_phase_evaluate_v1(p_execution_id);
  if coalesce((v_eval->>'ready')::boolean,false) is not true then
    raise exception 'phase_not_ready:%',v_eval::text;
  end if;
  select phase_id,release_id,source_sha into v_phase_id,v_release_id,v_source_sha
  from integration_control.cos_phase_executions_v1 where execution_id=p_execution_id for update;
  if not found then raise exception 'unknown_execution'; end if;
  v_phase_state:=case when v_phase_id='15' then 'production_certified' else 'certified' end;
  v_dail:=chlom_runtime.append_dail_event(
    'cos.phase.certified','cos_phase',v_phase_id,
    jsonb_build_object('release_id',v_release_id,'execution_id',p_execution_id,'source_sha',v_source_sha,'evaluation',v_eval,'phase_state',v_phase_state),
    p_actor,null,'ct.penta.certifier','cos-v1-phase-'||v_phase_id,v_release_id,p_execution_id::text,
    case when v_phase_id='15' then 'D3 human-reserved final release authority plus independently satisfied technical gates' else 'COS V1 immutable phase protocol' end,
    null,'restricted'
  );
  update integration_control.cos_phase_executions_v1
  set state='passed',ended_at=now(),dail_event_id=v_dail->>'event_id',updated_at=now()
  where execution_id=p_execution_id;
  update integration_control.cos_phase_registry_v1
  set state=v_phase_state,latest_dail_event_id=v_dail->>'event_id',source_sha=v_source_sha,updated_at=now()
  where phase_id=v_phase_id;
  if v_phase_id='15' then
    update integration_control.cos_release_registry_v1
    set state='released',production_sha=v_source_sha,released_at=now(),updated_at=now(),
        metadata=metadata || jsonb_build_object('cos_phase_15_execution_id',p_execution_id,'cos_phase_15_dail_event_id',v_dail->>'event_id','production_certification',true)
    where release_id=v_release_id;
  end if;
  return jsonb_build_object('ok',true,'phase_id',v_phase_id,'phase_state',v_phase_state,'dail_receipt',v_dail,'evaluation',v_eval);
end
$$;

create or replace function integration_control.cos_phase_status_v1(p_phase_id text default null)
returns jsonb
language sql
security definer
set search_path to pg_catalog,integration_control
as $$
select jsonb_build_object(
  'release',(select jsonb_build_object('release_id',release_id,'semantic_version',semantic_version,'state',state,'source_sha',source_sha,'production_sha',production_sha,'certified_at',certified_at,'released_at',released_at) from integration_control.cos_release_registry_v1 where release_id='ct.cos.release.1.0.0'),
  'phases',coalesce((select jsonb_agg(jsonb_build_object('phase_id',p.phase_id,'ordinal',p.ordinal,'slug',p.slug,'canonical_name',p.canonical_name,'state',p.state,'predecessor_phase_id',p.predecessor_phase_id,'latest_execution_id',p.latest_execution_id,'latest_dail_event_id',p.latest_dail_event_id,'updated_at',p.updated_at) order by p.ordinal) from integration_control.cos_phase_registry_v1 p where p_phase_id is null or p.phase_id=p_phase_id),'[]'::jsonb)
);
$$;

create or replace function integration_control.cos_reject_gate_receipt_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,integration_control
as $$
begin
  raise exception 'cos_phase_gate_receipts_are_append_only';
end
$$;

drop trigger if exists cos_phase_gate_receipts_immutable_v1 on integration_control.cos_phase_gate_receipts_v1;
create trigger cos_phase_gate_receipts_immutable_v1
before update or delete on integration_control.cos_phase_gate_receipts_v1
for each row execute function integration_control.cos_reject_gate_receipt_mutation_v1();

alter table integration_control.cos_phase_registry_v1 enable row level security;
alter table integration_control.cos_phase_registry_v1 force row level security;
alter table integration_control.cos_phase_executions_v1 enable row level security;
alter table integration_control.cos_phase_executions_v1 force row level security;
alter table integration_control.cos_phase_gate_requirements_v1 enable row level security;
alter table integration_control.cos_phase_gate_requirements_v1 force row level security;
alter table integration_control.cos_phase_gate_receipts_v1 enable row level security;
alter table integration_control.cos_phase_gate_receipts_v1 force row level security;

revoke all on table integration_control.cos_phase_registry_v1 from public,anon,authenticated;
revoke all on table integration_control.cos_phase_executions_v1 from public,anon,authenticated;
revoke all on table integration_control.cos_phase_gate_requirements_v1 from public,anon,authenticated;
revoke all on table integration_control.cos_phase_gate_receipts_v1 from public,anon,authenticated;
grant select on table integration_control.cos_phase_registry_v1 to authenticated;
grant all on table integration_control.cos_phase_registry_v1 to service_role;
grant all on table integration_control.cos_phase_executions_v1 to service_role;
grant all on table integration_control.cos_phase_gate_requirements_v1 to service_role;
grant all on table integration_control.cos_phase_gate_receipts_v1 to service_role;

revoke all on function integration_control.cos_phase_begin_v1(text,text,text,text,jsonb,jsonb,jsonb) from public,anon,authenticated;
revoke all on function integration_control.cos_phase_record_gate_v1(uuid,text,text,text,jsonb,text,text) from public,anon,authenticated;
revoke all on function integration_control.cos_phase_evaluate_v1(uuid) from public,anon,authenticated;
revoke all on function integration_control.cos_phase_finalize_v1(uuid,text) from public,anon,authenticated;
revoke all on function integration_control.cos_phase_status_v1(text) from public,anon;
revoke all on function integration_control.cos_reject_gate_receipt_mutation_v1() from public,anon,authenticated;
grant execute on function integration_control.cos_phase_begin_v1(text,text,text,text,jsonb,jsonb,jsonb) to service_role;
grant execute on function integration_control.cos_phase_record_gate_v1(uuid,text,text,text,jsonb,text,text) to service_role;
grant execute on function integration_control.cos_phase_evaluate_v1(uuid) to service_role;
grant execute on function integration_control.cos_phase_finalize_v1(uuid,text) to service_role;
grant execute on function integration_control.cos_phase_status_v1(text) to service_role,authenticated;

commit;
