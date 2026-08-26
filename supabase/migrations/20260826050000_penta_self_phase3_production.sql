-- PentaSELF™ / PentaFabrics™ / PentaMeshes™
-- CrownThrive Phase 3 production autonomy and resilience convergence.
-- This migration is intentionally fail-closed: no D3 auto-promotion, credential
-- manufacture, uncertified provider writes, money movement, rights grants, or
-- universal delete are introduced here.

create schema if not exists penta_self;
revoke all on schema penta_self from public, anon, authenticated;
grant usage on schema penta_self to service_role;

alter table penta_runtime.fabrics_v1 drop constraint if exists fabrics_v1_lifecycle_state_check;
alter table penta_runtime.fabrics_v1 add constraint fabrics_v1_lifecycle_state_check
  check (lifecycle_state = any (array['candidate'::text,'controlled_test'::text,'active'::text,'production'::text,'hold'::text,'retired'::text]));

update penta_runtime.fabrics_v1
set lifecycle_state='production',
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true,'self_healing_plane','PentaSELF','authority_manufacture',false),
    updated_at=now()
where fabric_id in ('ct.fabric.penta.v1','ct.mesh.penta.v1');

update penta_runtime.fabrics_v1 set canonical_name='PentaFabric', aliases=array(select distinct x from unnest(coalesce(aliases,'{}'::text[])||array['PentaFabrics']) x), description='Production orchestration fabric coordinating identity, authority, work, schedules, PentaSELF autonomy, mesh routing, maintenance, security, custody, release, and continuity across CrownThrive.' where fabric_id='ct.fabric.penta.v1';
update penta_runtime.fabrics_v1 set canonical_name='PentaMesh', aliases=array(select distinct x from unnest(coalesce(aliases,'{}'::text[])||array['PentaMeshes']) x), description='Production redundant interoperability, routing, federation, and provider-edge mesh for CrownThrive institutional systems and repositories.' where fabric_id='ct.mesh.penta.v1';

-- Conflict-safe canonical layer order. Move known rows out of the target ordinal
-- range first so this migration can be replayed without ordinal collisions.
update penta_runtime.fabric_layers_v1
set ordinal=ordinal+100
where fabric_id='ct.fabric.penta.v1'
  and layer_id in ('ct.penta.layer.2','ct.penta.layer.self','ct.penta.layer.3','ct.penta.layer.4','ct.penta.layer.5','ct.penta.layer.6','ct.penta.layer.7','ct.penta.layer.8','ct.penta.layer.9');

insert into penta_runtime.fabric_layers_v1(layer_id,fabric_id,ordinal,canonical_name,purpose,authority_boundary,component_ids,metadata,created_at,updated_at)
values('ct.penta.layer.self','ct.fabric.penta.v1',3,'PentaSELF Autonomy and Resilience','Production self-awareness, self-discovery, self-diagnosis, self-healing, self-repair routing, self-recovery, self-reconciliation, self-testing, self-verification, self-routing, self-nurturing, self-security, self-quarantine, and continuity orchestration between PentaFabric and PentaMesh.','D2_MAX',array['PentaSELF','PentaTime','PentaNurture','PentaBuild','PentaCertify','PentaCredentials','PentaSecure','PentaVergence','PentaRoute'],jsonb_build_object('phase',3,'production',true,'position','below_pentafabric_above_pentamesh','d3_human_reserved',true,'authority_manufacture',false),now(),now())
on conflict(layer_id) do update set canonical_name=excluded.canonical_name,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,component_ids=excluded.component_ids,metadata=penta_runtime.fabric_layers_v1.metadata||excluded.metadata,updated_at=now();

update penta_runtime.fabric_layers_v1
set ordinal=case layer_id
  when 'ct.penta.layer.2' then 2
  when 'ct.penta.layer.self' then 3
  when 'ct.penta.layer.4' then 4
  when 'ct.penta.layer.3' then 5
  when 'ct.penta.layer.5' then 6
  when 'ct.penta.layer.6' then 7
  when 'ct.penta.layer.7' then 8
  when 'ct.penta.layer.8' then 9
  when 'ct.penta.layer.9' then 10
end
where fabric_id='ct.fabric.penta.v1'
  and layer_id in ('ct.penta.layer.2','ct.penta.layer.self','ct.penta.layer.3','ct.penta.layer.4','ct.penta.layer.5','ct.penta.layer.6','ct.penta.layer.7','ct.penta.layer.8','ct.penta.layer.9');

update penta_runtime.fabric_layers_v1 set canonical_name='PentaFabric Orchestration',purpose='Production canonical orchestration and policy composition across Penta subsystems; delegates bounded resilience to PentaSELF before mesh execution.',component_ids=array['PentaFabric','PentaAgentic','PentaSELF'],metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true) where layer_id='ct.penta.layer.2';
update penta_runtime.fabric_layers_v1 set canonical_name='PentaMesh, PentaEdge, and PentaFederation',purpose='Production typed routing, redundancy, least-data flow, identity holds, federation, and bounded provider edges after PentaSELF health/authority checks.',component_ids=array['PentaMesh','PentaEdge','PentaFederation'],metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true,'preceded_by','PentaSELF') where layer_id='ct.penta.layer.4';

insert into penta_runtime.component_registry_v1(component_key,canonical_name,role,primary_axis,stable_contract_id,implementation_state,aliases,backing_refs,metadata,enabled,created_at,updated_at)
values
('penta.self','PentaSELF','Production self-* autonomy, resilience and self-healing control plane between PentaFabric and PentaMesh.','continuity','ct.penta.self.v1','active',array['Penta Self','self-healing plane'],jsonb_build_object('schema','penta_self','tick','public.penta_self_tick_v1','status','public.penta_self_status_v1'),jsonb_build_object('phase',3,'maturity','production','max_auto_risk','D2','d3_human_reserved',true,'authority_manufacture',false,'provider_write_requires_certification',true),true,now(),now()),
('penta.mesh','PentaMesh','Production routing, federation, redundancy and bounded provider-edge mesh.','interoperation','ct.penta.mesh.v1','active',array['PentaMeshes','Penta Mesh'],jsonb_build_object('fabric_id','ct.mesh.penta.v1','route_selector','penta_runtime.penta_mesh_select_route_v1'),jsonb_build_object('phase',3,'maturity','production','preceded_by','penta.self'),true,now(),now())
on conflict(component_key) do update set canonical_name=excluded.canonical_name,role=excluded.role,primary_axis=excluded.primary_axis,stable_contract_id=excluded.stable_contract_id,implementation_state='active',aliases=excluded.aliases,backing_refs=penta_runtime.component_registry_v1.backing_refs||excluded.backing_refs,metadata=penta_runtime.component_registry_v1.metadata||excluded.metadata,enabled=true,updated_at=now();
update penta_runtime.component_registry_v1 set aliases=array(select distinct x from unnest(coalesce(aliases,'{}'::text[])||array['PentaFabrics']) x),metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'maturity','production','self_plane_below','penta.self'),implementation_state='active',enabled=true,updated_at=now() where component_key='penta.fabric';

insert into public.penta_system_registry(system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,version,public_exposure,runtime_ref,metadata,last_verified_at,updated_at)
values
('penta.fabrics','PentaFabrics','production_fabric_plane','Production orchestration fabric plane for CrownThrive. PentaFabrics composes policy, authority, execution and continuity but delegates bounded self-healing to PentaSELF before mesh routing.','May orchestrate within inherited certified authority through D2. Cannot manufacture D3 authority, credentials, rights, money movement, or uncertified provider writes.','D2','production','1.0.0',false,'function:public.penta_fabric_cycle_v1()',jsonb_build_object('phase',3,'production',true,'fabric_id','ct.fabric.penta.v1','next_plane','penta.self','execution_api','penta-fabric','mark','TM'),now(),now()),
('penta.self','PentaSELF','self_autonomy_resilience_plane','Production self-* control plane for awareness, observation, discovery, diagnosis, healing, repair routing, recovery, reconciliation, testing, verification, routing, nurturing, security, quarantine, optimization within authority, release continuity and preservation.','May automatically repair reversible D0-D2 system state using pre-authorized handlers and certified provider paths. Must delegate certification, credentials, rights, money, legal/governance and D3 decisions. It may never manufacture authority.','D2','production','1.0.0',false,'function:public.penta_self_tick_v1()',jsonb_build_object('phase',3,'production',true,'position','between_penta_fabrics_and_penta_meshes','mark','TM','d3_human_reserved',true,'authority_manufacture',false),now(),now()),
('penta.meshes','PentaMeshes','production_mesh_plane','Production routing, redundancy, federation, provider-edge and interoperation mesh plane downstream of PentaSELF health and authority checks.','May route only over resolved, certified and policy-compatible paths through D2. It may not manufacture provider authority, bypass identity holds, or promote D3 actions.','D2','production','1.0.0',false,'function:public.penta_mesh_select_route_v1(jsonb)',jsonb_build_object('phase',3,'production',true,'fabric_id','ct.mesh.penta.v1','previous_plane','penta.self','execution_api','penta-mesh','mark','TM'),now(),now())
on conflict(system_key) do update set canonical_name=excluded.canonical_name,category=excluded.category,purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,maturity='production',version=excluded.version,public_exposure=excluded.public_exposure,runtime_ref=excluded.runtime_ref,metadata=public.penta_system_registry.metadata||excluded.metadata,last_verified_at=now(),updated_at=now();

create table if not exists penta_self.capability_registry_v1(
 capability_key text primary key, canonical_name text not null unique, purpose text not null, handler_ref text, action_mode text not null check(action_mode in ('direct_bounded','delegated','observational','human_reserved')), max_risk_class text not null check(max_risk_class in ('D0','D1','D2','D3')), reversible_required boolean not null default true, verification_required boolean not null default true, enabled boolean not null default true, metadata jsonb not null default '{}'::jsonb, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists penta_self.required_jobs_v1(
 jobname text primary key, expected_schedule text not null, expected_command text not null, auto_repair boolean not null default true, risk_class text not null default 'D1' check(risk_class in ('D0','D1','D2','D3')), metadata jsonb not null default '{}'::jsonb, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists penta_self.findings_v1(
 finding_id uuid primary key default gen_random_uuid(), cycle_id uuid, capability_key text references penta_self.capability_registry_v1(capability_key), severity text not null check(severity in ('info','watch','degraded','critical')), state text not null check(state in ('open','healed','delegated','blocked','observed')), target_ref text not null, symptom text not null, evidence jsonb not null default '{}'::jsonb, detected_at timestamptz not null default now(), resolved_at timestamptz
);
create table if not exists penta_self.action_receipts_v1(
 receipt_id uuid primary key default gen_random_uuid(), cycle_id uuid not null, finding_id uuid references penta_self.findings_v1(finding_id) on delete set null, capability_key text references penta_self.capability_registry_v1(capability_key), action_key text not null, target_ref text not null, result_state text not null check(result_state in ('applied','no_change','delegated','blocked','failed','skipped')), reversible boolean not null default true, authority_class text not null default 'D1', before_sha256 text, after_sha256 text, evidence jsonb not null default '{}'::jsonb, started_at timestamptz not null default now(), completed_at timestamptz not null default now()
);
create table if not exists penta_self.cycle_receipts_v1(
 cycle_id uuid primary key, state text not null check(state in ('running','healthy','degraded','blocked','failed','skipped_locked')), started_at timestamptz not null default now(), completed_at timestamptz, summary jsonb not null default '{}'::jsonb, evidence jsonb not null default '{}'::jsonb
);
create index if not exists penta_self_findings_state_time_idx on penta_self.findings_v1(state,detected_at desc);
create index if not exists penta_self_actions_cycle_idx on penta_self.action_receipts_v1(cycle_id,completed_at desc);
alter table penta_self.capability_registry_v1 enable row level security;
alter table penta_self.required_jobs_v1 enable row level security;
alter table penta_self.findings_v1 enable row level security;
alter table penta_self.action_receipts_v1 enable row level security;
alter table penta_self.cycle_receipts_v1 enable row level security;
revoke all on all tables in schema penta_self from public,anon,authenticated;
grant select,insert,update,delete on all tables in schema penta_self to service_role;

-- The self-* registry is typed and extensible. A self capability never implies
-- additional authority; its action mode and risk ceiling determine delegation.
insert into penta_self.capability_registry_v1(capability_key,canonical_name,purpose,handler_ref,action_mode,max_risk_class,reversible_required,verification_required,metadata)
select capability_key,canonical_name,purpose,handler_ref,action_mode,max_risk_class,reversible_required,verification_required,metadata from (values
('self.awareness','SelfAwareness','Maintain current architecture and runtime awareness.','chlom_runtime.run_architecture_self_awareness_subroute_v1','direct_bounded','D1',true,true,'{"owner":"PentaSELF"}'::jsonb),
('self.observe','SelfObserve','Observe runtime, provider, fabric, mesh, scheduler and agent state.','PentaNurture/PentaOverseer','delegated','D1',true,true,'{}'::jsonb),
('self.monitor','SelfMonitor','Maintain bounded production monitors, heartbeats and drift detection.','PentaNurture/PentaTime','delegated','D1',true,true,'{}'::jsonb),
('self.discovery','SelfDiscovery','Discover capability, provider, topology, scheduler and execution gaps.','public.ct_phase3_self_discovery_tick_v3','direct_bounded','D1',true,true,'{}'::jsonb),
('self.diagnose','SelfDiagnose','Diagnose runtime, agent, provider and continuity health.','public.thrivebase_self_diagnostic_run_v1','direct_bounded','D1',true,true,'{}'::jsonb),
('self.heal','SelfHeal','Apply bounded reversible repairs where a repair contract exists.','public.thrivebase_safe_self_heal_run_v1','direct_bounded','D2',true,true,'{}'::jsonb),
('self.repair','SelfRepair','Route missing or defective software into PentaBuild.','PentaBuild','delegated','D2',true,true,'{}'::jsonb),
('self.reconcile','SelfReconcile','Reconcile stale provider, fabric, mesh and runtime evidence.','PentaVergence/PentaCertify','delegated','D2',true,true,'{}'::jsonb),
('self.recover','SelfRecover','Recover scheduler and bounded runtime state from known-safe drift.','PentaTime/PentaSELF','direct_bounded','D2',true,true,'{}'::jsonb),
('self.rollback','SelfRollback','Invoke only predeclared rollback or compensation contracts.','PentaCompensate','delegated','D2',true,true,'{"arbitrary_rollback":false}'::jsonb),
('self.restart','SelfRestart','Restore known scheduler/runtime liveness without arbitrary process termination.','PentaSELF','direct_bounded','D1',true,true,'{"process_kill":false}'::jsonb),
('self.rebind','SelfRebind','Re-establish explicit bindings after identity, credential and certification checks.','PentaBind','delegated','D2',true,true,'{}'::jsonb),
('self.route','SelfRoute','Select and restore bounded healthy routes across PentaMesh.','PentaRoute','delegated','D2',true,true,'{}'::jsonb),
('self.test','SelfTest','Generate and execute bounded software/runtime tests.','PentaFactory/PentaCertify','delegated','D2',true,true,'{}'::jsonb),
('self.verify','SelfVerify','Verify repair and provider evidence before accepting healthy state.','PentaCertify','delegated','D2',true,true,'{}'::jsonb),
('self.certify','SelfCertify','Initiate certification workflows but never self-grant authority.','PentaCertify','delegated','D2',true,true,'{"self_grant":false}'::jsonb),
('self.nurture','SelfNurture','Continuously nurse provider, credential, adapter and software health.','PentaNurture','direct_bounded','D2',true,true,'{}'::jsonb),
('self.secure','SelfSecure','Assess security posture and route bounded corrective work.','PentaSecure','delegated','D2',true,true,'{}'::jsonb),
('self.quarantine','SelfQuarantine','Fail closed and quarantine unhealthy or uncertified paths without deleting evidence.','PentaHold','delegated','D2',true,true,'{"delete":false}'::jsonb),
('self.close','SelfClose','Close verified gaps after evidence, merge and production readback.','PentaCloser','delegated','D2',true,true,'{}'::jsonb),
('self.refresh','SelfRefresh','Refresh projections, caches, self-models and non-secret runtime state.','PentaTime/PentaVergence','delegated','D1',true,true,'{}'::jsonb),
('self.sync','SelfSync','Synchronize governed fabric, federation and mesh state.','PentaWire/PentaFederation','delegated','D2',true,true,'{}'::jsonb),
('self.scale','SelfScale','Adjust internal software concurrency within cost and authority ceilings.','PentaCost/PentaFactory','delegated','D2',true,true,'{"provider_spend_without_authority":false}'::jsonb),
('self.optimize','SelfOptimize','Optimize software and routes within existing policy and authority.','PentaMCL/PentaGreen','delegated','D2',true,true,'{"authority_manufacture":false}'::jsonb),
('self.prioritize','SelfPrioritize','Prioritize software remediation under declared risk, impact and cost ceilings.','PentaPrioritize/PentaCost','delegated','D1',true,true,'{}'::jsonb),
('self.schedule','SelfSchedule','Reconcile and schedule declared autonomous jobs through PentaTime.','PentaTime','delegated','D1',true,true,'{}'::jsonb),
('self.balance','SelfBalance','Balance workload, concurrency, cost and route pressure within ceilings.','PentaCost/PentaTime/PentaRoute','delegated','D1',true,true,'{}'::jsonb),
('self.audit','SelfAudit','Audit receipts, invariants, software state and evidence.','PentaLedger/PentaScorecard','delegated','D2',true,true,'{}'::jsonb),
('self.learn','SelfLearn','Learn from non-secret operational evidence without changing authority.','PentaMCL/PentaContext','delegated','D1',true,true,'{"authority_change":false}'::jsonb),
('self.adapt','SelfAdapt','Adapt bounded software and routing through governed rebuild/re-certification.','PentaMCL/PentaBuild/PentaCertify','delegated','D2',true,true,'{}'::jsonb),
('self.clean','SelfClean','Clean stale non-authoritative state without deleting protected evidence.','PentaClean/PentaVault','delegated','D2',true,true,'{"protected_evidence_delete":false}'::jsonb),
('self.archive','SelfArchive','Archive superseded/historical artifacts while preserving lineage.','PentaDocs/PentaVault/PentaScribe','delegated','D1',true,true,'{"historical_authority":false}'::jsonb),
('self.backup','SelfBackup','Create governed backups/checkpoints of software and institutional state.','PentaVault/PentaGeneration','delegated','D2',true,true,'{"secret_export":false}'::jsonb),
('self.restore','SelfRestore','Restore from verified checkpoints through bounded contracts.','PentaVault/PentaHydrate/PentaCompensate','delegated','D2',true,true,'{"arbitrary_restore":false}'::jsonb),
('self.migrate','SelfMigrate','Build and execute reversible schema/software migrations through certified paths.','PentaBuild/PentaRelease/PentaCertify','delegated','D2',true,true,'{"d3_auto_migration":false}'::jsonb),
('self.version','SelfVersion','Maintain canonical software, contract, schema and documentation versions.','PentaVersion/PentaScribe','delegated','D1',true,true,'{}'::jsonb),
('self.deploy','SelfDeploy','Deploy only tested/certified bounded software to declared production targets.','PentaRelease/PentaCertify','delegated','D2',true,true,'{"uncertified_deploy":false}'::jsonb),
('self.release','SelfRelease','Package and release verified software with rollback/provenance.','PentaRelease/PentaVersion','delegated','D2',true,true,'{"d3_auto_release":false}'::jsonb),
('self.update','SelfUpdate','Build and stage governed software updates.','PentaBuild/PentaRelease','delegated','D2',true,true,'{"auto_d3_release":false}'::jsonb),
('self.document','SelfDocument','Project verified current-state changes into institutional documentation.','PentaScribe/PentaDocs','delegated','D1',true,true,'{}'::jsonb),
('self.preserve','SelfPreserve','Preserve evidence, continuity, lineage and seven-generation handoff state.','PentaGeneration/PentaVault','delegated','D2',true,true,'{}'::jsonb),
('self.failclose','SelfFailClose','Fail closed unhealthy, ambiguous, expired or uncertified paths.','PentaHold/PentaCertify','delegated','D2',true,true,'{"default_on_uncertain_authority":"hold"}'::jsonb),
('self.escalate','SelfEscalate','Escalate unresolved D2 and all D3 requirements to governance/human lanes.','PentaRoute/CHLOM/Founder','delegated','D2',true,true,'{"d3_automatic_resolution":false}'::jsonb),
('self.resume','SelfResume','Resume bounded execution only after health/certification/authority reverification.','PentaTime/PentaCertify/PentaRoute','delegated','D2',true,true,'{"resume_requires_reverification":true}'::jsonb),
('self.degrade','SelfDegrade','Reduce capability/route scope when full operation is unsafe.','PentaNurture/PentaHold/PentaRoute','delegated','D2',true,true,'{"graceful_degradation":true}'::jsonb),
('self.govern','SelfGovern','D3 governance, rights, legal, money and irreversible authority remain human-reserved.','Founder/CHLOM','human_reserved','D3',false,true,'{"automatic":false,"d3_human_reserved":true}'::jsonb)
) v(capability_key,canonical_name,purpose,handler_ref,action_mode,max_risk_class,reversible_required,verification_required,metadata)
on conflict(capability_key) do update set canonical_name=excluded.canonical_name,purpose=excluded.purpose,handler_ref=excluded.handler_ref,action_mode=excluded.action_mode,max_risk_class=excluded.max_risk_class,reversible_required=excluded.reversible_required,verification_required=excluded.verification_required,enabled=true,metadata=penta_self.capability_registry_v1.metadata||excluded.metadata,updated_at=now();

insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata) values
('ct-penta-self-v1','*/2 * * * *','select public.penta_self_tick_v1();',true,'D1','{"owner":"PentaSELF"}'::jsonb),
('ct-phase3-self-discovery-v3','*/5 * * * *','select public.ct_phase3_self_discovery_tick_v3();',true,'D1','{"owner":"PentaSELF"}'::jsonb),
('thivebase_self_diagnostic_v1','3-58/5 * * * *','select public.thrivebase_safe_self_heal_run_v1();',true,'D1','{"owner":"PentaSELF","legacy_job_name_preserved":true}'::jsonb),
('ct-penta-certify-v3','*/2 * * * *','select integration_control.penta_certify_cycle_v3(6);',true,'D2','{"owner":"PentaCertify"}'::jsonb),
('ct-penta-provider-evidence-bridge-v1','*/2 * * * *','select integration_control.penta_certify_activate_control_evidence_v1();',true,'D2','{"owner":"PentaCertify"}'::jsonb),
('ct-penta-build-quality-v1','*/5 * * * *','select integration_control.penta_build_quality_sweep_v1();',true,'D1','{"owner":"PentaBuild"}'::jsonb),
('ct-penta-nurture-v1','*/5 * * * *','select public.penta_nurture_tick_v1();',true,'D1','{"owner":"PentaNurture"}'::jsonb),
('ct-pentatime-reconcile-v1','*/5 * * * *','select pentatime.reconcile(true);',true,'D1','{"owner":"PentaTime"}'::jsonb),
('ct-pentaroute-autonomy-v3','*/5 * * * *','select integration_control.pentaroute_autonomy_cycle_v3();',true,'D1','{"owner":"PentaRoute"}'::jsonb),
('ct-software-factory-continuity-v5','*/2 * * * *','select public.ct_factory_continuity_cycle(1);',true,'D2','{"owner":"PentaFactory"}'::jsonb),
('ct-software-factory-dispatch-v3','* * * * *','select public.ct_factory_dispatch_tick();',true,'D2','{"owner":"PentaFactory"}'::jsonb)
on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=excluded.auto_repair,risk_class=excluded.risk_class,metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();

create or replace function penta_runtime.penta_fabrics_status_v1()
returns jsonb language sql stable security definer set search_path='pg_catalog','penta_runtime' as $$
select jsonb_build_object('service','ct.penta.fabrics.v1','phase',3,'state',case when f.lifecycle_state='production' then 'PRODUCTION' else upper(f.lifecycle_state) end,'fabric',to_jsonb(f),'layers',coalesce((select jsonb_agg(to_jsonb(l) order by l.ordinal) from penta_runtime.fabric_layers_v1 l where l.fabric_id='ct.fabric.penta.v1'),'[]'::jsonb),'self_plane',(select to_jsonb(l) from penta_runtime.fabric_layers_v1 l where l.layer_id='ct.penta.layer.self'),'generated_at',now()) from penta_runtime.fabrics_v1 f where f.fabric_id='ct.fabric.penta.v1';
$$;

create or replace function penta_runtime.penta_meshes_status_v1()
returns jsonb language plpgsql stable security definer set search_path='pg_catalog','penta_runtime','integration_control' as $$
declare v_f jsonb; v_control jsonb; v_bindings bigint:=0; v_peers bigint:=0;
begin
 select to_jsonb(f) into v_f from penta_runtime.fabrics_v1 f where f.fabric_id='ct.mesh.penta.v1';
 begin v_control:=integration_control.chlom_mesh_status_v1(); exception when others then v_control:=jsonb_build_object('state','unavailable','error',left(sqlerrm,240)); end;
 select count(*) into v_bindings from integration_control.site_mesh_bindings;
 select count(*) into v_peers from integration_control.site_mesh_peer_links;
 return jsonb_build_object('service','ct.penta.meshes.v1','phase',3,'state',case when v_f->>'lifecycle_state'='production' then 'PRODUCTION' else upper(coalesce(v_f->>'lifecycle_state','unknown')) end,'mesh',v_f,'fabric_layer',(select to_jsonb(l) from penta_runtime.fabric_layers_v1 l where l.layer_id='ct.penta.layer.4'),'control_plane',v_control,'site_mesh_bindings',v_bindings,'site_mesh_peer_links',v_peers,'generated_at',now());
end $$;

create or replace function penta_self.scheduler_reconcile_v1(p_cycle_id uuid default gen_random_uuid())
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_self','cron','extensions' as $$
declare r record; v_jobid bigint; v_schedule text; v_command text; v_active boolean; v_checked int:=0; v_healed int:=0; v_missing int:=0; v_drift int:=0; v_finding uuid;
begin
 for r in select * from penta_self.required_jobs_v1 where auto_repair=true order by jobname loop
  v_checked:=v_checked+1; v_jobid:=null; v_schedule:=null; v_command:=null; v_active:=null;
  select jobid,schedule,command,active into v_jobid,v_schedule,v_command,v_active from cron.job where jobname=r.jobname limit 1;
  if v_jobid is null then
    v_missing:=v_missing+1;
    insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence) values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'required_scheduler_missing',jsonb_build_object('expected_schedule',r.expected_schedule,'risk_class',r.risk_class)) returning finding_id into v_finding;
    begin
      perform cron.schedule(r.jobname,r.expected_schedule,r.expected_command);
      update penta_self.findings_v1 set state='healed',resolved_at=now() where target_ref='cron:'||r.jobname and state in('open','delegated');
      insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(p_cycle_id,v_finding,'self.recover','schedule_missing_job','cron:'||r.jobname,'applied',true,r.risk_class,jsonb_build_object('schedule',r.expected_schedule,'command_sha256',encode(extensions.digest(convert_to(r.expected_command,'UTF8'),'sha256'),'hex')));
      v_healed:=v_healed+1;
    exception when others then
      update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('repair_error',left(sqlerrm,240)) where finding_id=v_finding;
    end;
  elsif coalesce(v_active,false)=false or v_schedule is distinct from r.expected_schedule or v_command is distinct from r.expected_command then
    v_drift:=v_drift+1;
    insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence) values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'scheduler_drift_or_inactive',jsonb_build_object('actual_schedule',v_schedule,'expected_schedule',r.expected_schedule,'active',v_active)) returning finding_id into v_finding;
    begin
      perform cron.alter_job(v_jobid,schedule=>r.expected_schedule,command=>r.expected_command,active=>true);
      update penta_self.findings_v1 set state='healed',resolved_at=now() where target_ref='cron:'||r.jobname and state in('open','delegated');
      insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(p_cycle_id,v_finding,'self.recover','repair_scheduler_drift','cron:'||r.jobname,'applied',true,r.risk_class,jsonb_build_object('jobid',v_jobid,'schedule',r.expected_schedule,'active',true));
      v_healed:=v_healed+1;
    exception when others then
      update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('repair_error',left(sqlerrm,240)) where finding_id=v_finding;
    end;
  end if;
 end loop;
 return jsonb_build_object('service','ct.penta.self.scheduler-reconcile.v1','checked',v_checked,'missing',v_missing,'drifted_or_inactive',v_drift,'healed',v_healed,'at',now());
end $$;

create or replace function penta_self.failed_job_recovery_v1(p_cycle_id uuid default gen_random_uuid())
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_self','integration_control','pentatime','public','cron' as $$
declare r record; v_result jsonb; v_recovered int:=0; v_failed int:=0; v_skipped int:=0; v_finding uuid;
begin
 for r in select distinct on (j.jobid) j.jobid,j.jobname,d.status,d.start_time,d.return_message from penta_self.required_jobs_v1 q join cron.job j on j.jobname=q.jobname join cron.job_run_details d on d.jobid=j.jobid and d.start_time>now()-interval '30 minutes' where q.auto_repair order by j.jobid,d.start_time desc loop
  if r.status in('succeeded','running') then continue; end if;
  if exists(select 1 from penta_self.action_receipts_v1 a where a.action_key='recover_failed_required_job' and a.target_ref='cron:'||r.jobname and a.result_state='applied' and a.completed_at>=r.start_time) then continue; end if;
  insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence) values(p_cycle_id,'self.recover','degraded','open','cron:'||r.jobname,'latest_required_job_failed',jsonb_build_object('failed_at',r.start_time,'return_message',left(coalesce(r.return_message,''),500),'jobid',r.jobid)) returning finding_id into v_finding;
  begin
   v_result:=case r.jobname when 'ct-penta-self-v1' then jsonb_build_object('state','current_cycle_proves_runtime_live','cycle_id',p_cycle_id) else null end;
   if r.jobname='ct-phase3-self-discovery-v3' then v_result:=public.ct_phase3_self_discovery_tick_v3();
   elsif r.jobname='ct-penta-certify-v3' then v_result:=integration_control.penta_certify_cycle_v3(6);
   elsif r.jobname='ct-penta-provider-evidence-bridge-v1' then v_result:=integration_control.penta_certify_activate_control_evidence_v1();
   elsif r.jobname='ct-penta-build-quality-v1' then v_result:=integration_control.penta_build_quality_sweep_v1();
   elsif r.jobname='ct-penta-nurture-v1' then v_result:=public.penta_nurture_tick_v1();
   elsif r.jobname='ct-pentatime-reconcile-v1' then v_result:=pentatime.reconcile(true);
   elsif r.jobname='ct-pentaroute-autonomy-v3' then v_result:=integration_control.pentaroute_autonomy_cycle_v3();
   elsif r.jobname='ct-software-factory-continuity-v5' then v_result:=public.ct_factory_continuity_cycle(1);
   elsif r.jobname='ct-software-factory-dispatch-v3' then v_result:=public.ct_factory_dispatch_tick();
   elsif r.jobname='thivebase_self_diagnostic_v1' then v_result:=public.thrivebase_safe_self_heal_run_v1();
   end if;
   if v_result is null then
    update penta_self.findings_v1 set state='delegated' where finding_id=v_finding; v_skipped:=v_skipped+1;
   else
    update penta_self.findings_v1 set state='healed',resolved_at=now(),evidence=evidence||jsonb_build_object('recovery_result',v_result) where finding_id=v_finding;
    insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(p_cycle_id,v_finding,'self.recover','recover_failed_required_job','cron:'||r.jobname,'applied',true,'D1',jsonb_build_object('result',v_result,'original_failed_at',r.start_time)); v_recovered:=v_recovered+1;
   end if;
  exception when others then
   update penta_self.findings_v1 set state='delegated',evidence=evidence||jsonb_build_object('recovery_error',left(sqlerrm,300)) where finding_id=v_finding; v_failed:=v_failed+1;
  end;
 end loop;
 return jsonb_build_object('service','ct.penta.self.failed-job-recovery.v1','recovered',v_recovered,'failed',v_failed,'skipped',v_skipped,'at',now());
end $$;

create or replace function penta_self.fabric_mesh_reconcile_v1(p_cycle_id uuid default gen_random_uuid())
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_self','penta_runtime','public' as $$
declare v_bad boolean:=false; v_finding uuid;
begin
 if exists(select 1 from penta_runtime.fabrics_v1 where fabric_id in('ct.fabric.penta.v1','ct.mesh.penta.v1') and lifecycle_state<>'production') then v_bad:=true; end if;
 if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.self' and ordinal=3) then v_bad:=true; end if;
 if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.2' and ordinal=2) then v_bad:=true; end if;
 if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.4' and ordinal=4) then v_bad:=true; end if;
 if v_bad then
  insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence) values(p_cycle_id,'self.reconcile','degraded','open','penta:fabric-mesh-topology','fabric_mesh_production_topology_drift',jsonb_build_object('required_order',jsonb_build_array('PentaFabric','PentaSELF','PentaMesh'))) returning finding_id into v_finding;
  update penta_runtime.fabrics_v1 set lifecycle_state='production',metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true,'last_self_reconciled_at',now()),updated_at=now() where fabric_id in('ct.fabric.penta.v1','ct.mesh.penta.v1');
  update penta_self.findings_v1 set state='healed',resolved_at=now() where finding_id=v_finding;
  insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(p_cycle_id,v_finding,'self.reconcile','restore_fabric_self_mesh_topology','penta:fabric-mesh-topology','applied',true,'D1',jsonb_build_object('order',jsonb_build_array('PentaFabric','PentaSELF','PentaMesh')));
 end if;
 update public.penta_system_registry set maturity='production',last_verified_at=now(),updated_at=now(),metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true,'last_self_reconciled_at',now()) where system_key in('penta.fabrics','penta.self','penta.meshes');
 return jsonb_build_object('service','ct.penta.self.fabric-mesh-reconcile.v1','drift_detected',v_bad,'production',true,'order',jsonb_build_array('PentaFabric','PentaSELF','PentaMesh'),'at',now());
end $$;

create or replace function penta_self.health_snapshot_v1()
returns jsonb language plpgsql stable security definer set search_path='pg_catalog','penta_self','penta_runtime','integration_control','chlom_runtime','cron','public' as $$
declare v_required int; v_active int; v_unrecovered int; v_degraded_agents int; v_failed_tasks int; v_blocked_tasks int; v_open int; v_fabric text; v_mesh text; v_queue jsonb;
begin
 select count(*) into v_required from penta_self.required_jobs_v1 where auto_repair;
 select count(*) into v_active from penta_self.required_jobs_v1 r join cron.job j on j.jobname=r.jobname where r.auto_repair and j.active and j.schedule=r.expected_schedule and j.command=r.expected_command;
 select count(*) into v_unrecovered from (select distinct on (j.jobid) j.jobid,j.jobname,d.status,d.start_time from penta_self.required_jobs_v1 r join cron.job j on j.jobname=r.jobname left join cron.job_run_details d on d.jobid=j.jobid and d.start_time>now()-interval '30 minutes' where r.auto_repair order by j.jobid,d.start_time desc nulls last) latest where status is not null and status not in('succeeded','running') and not exists(select 1 from penta_self.action_receipts_v1 a where a.action_key='recover_failed_required_job' and a.target_ref='cron:'||latest.jobname and a.result_state='applied' and a.completed_at>=latest.start_time);
 select count(*) into v_degraded_agents from chlom_runtime.agent_health where health_state in('degraded','failed','critical') and updated_at>now()-interval '1 hour';
 select count(*) filter(where state='failed'),count(*) filter(where state='blocked') into v_failed_tasks,v_blocked_tasks from integration_control.penta_certify_tasks_v3;
 select count(*) into v_open from penta_self.findings_v1 where state in('open','delegated') and detected_at>now()-interval '1 hour';
 select lifecycle_state into v_fabric from penta_runtime.fabrics_v1 where fabric_id='ct.fabric.penta.v1'; select lifecycle_state into v_mesh from penta_runtime.fabrics_v1 where fabric_id='ct.mesh.penta.v1';
 select jsonb_object_agg(certification_state,cnt) into v_queue from (select certification_state,count(*) cnt from public.ct_factory_adapter_certification_queue group by certification_state)s;
 return jsonb_build_object('phase',3,'production',true,'required_jobs',v_required,'healthy_required_jobs',v_active,'scheduler_gaps',v_required-v_active,'unrecovered_required_job_failures_30m',v_unrecovered,'degraded_agents_1h',v_degraded_agents,'failed_certification_tasks',v_failed_tasks,'blocked_certification_tasks',v_blocked_tasks,'open_or_delegated_findings_1h',v_open,'fabric_state',v_fabric,'mesh_state',v_mesh,'provider_certification_queue',coalesce(v_queue,'{}'::jsonb),'authority_manufacture',false,'d3_human_reserved',true,'generated_at',now());
end $$;

create or replace function penta_self.tick_v1()
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_self','penta_runtime','integration_control','public' as $$
declare v_cycle uuid:=gen_random_uuid(); v_started timestamptz:=clock_timestamp(); v_scheduler jsonb; v_recovery jsonb; v_topology jsonb; v_discovery jsonb; v_legacy jsonb; v_evidence jsonb; v_build jsonb; v_nurture jsonb; v_route jsonb; v_secure jsonb; v_health jsonb; v_state text:='healthy';
begin
 if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.self.v1',0)) then return jsonb_build_object('service','ct.penta.self.v1','state','SKIPPED_LOCKED','phase',3,'production',true,'at',now()); end if;
 insert into penta_self.cycle_receipts_v1(cycle_id,state,started_at,summary,evidence) values(v_cycle,'running',v_started,'{}','{}');
 begin v_scheduler:=penta_self.scheduler_reconcile_v1(v_cycle); exception when others then v_scheduler:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_recovery:=penta_self.failed_job_recovery_v1(v_cycle); exception when others then v_recovery:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_topology:=penta_self.fabric_mesh_reconcile_v1(v_cycle); exception when others then v_topology:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_discovery:=public.ct_phase3_self_discovery_tick_v3(); exception when others then v_discovery:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_legacy:=public.thrivebase_safe_self_heal_run_v1(); exception when others then v_legacy:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_evidence:=integration_control.penta_certify_activate_control_evidence_v1(); exception when others then v_evidence:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_build:=integration_control.penta_build_quality_sweep_v1(); exception when others then v_build:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_nurture:=public.penta_nurture_tick_v1(); exception when others then v_nurture:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_route:=integration_control.pentaroute_autonomy_cycle_v3(); exception when others then v_route:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_secure:=penta_runtime.pentasecure_cycle_v1(false); exception when others then v_secure:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 v_health:=penta_self.health_snapshot_v1();
 if coalesce((v_health->>'scheduler_gaps')::int,0)>0 or coalesce((v_health->>'unrecovered_required_job_failures_30m')::int,0)>0 or coalesce((v_health->>'failed_certification_tasks')::int,0)>0 or v_health->>'fabric_state'<>'production' or v_health->>'mesh_state'<>'production' then v_state:='degraded'; end if;
 if v_scheduler->>'state'='failed' or v_recovery->>'state'='failed' or v_topology->>'state'='failed' then v_state:='failed'; end if;
 update penta_self.cycle_receipts_v1 set state=v_state,completed_at=clock_timestamp(),summary=jsonb_build_object('state',v_state,'health',v_health),evidence=jsonb_build_object('scheduler',v_scheduler,'failed_job_recovery',v_recovery,'topology',v_topology,'discovery',v_discovery,'legacy_heal',v_legacy,'provider_evidence',v_evidence,'build_quality',v_build,'nurture',v_nurture,'route',v_route,'secure',v_secure,'authority_manufacture',false,'d3_human_reserved',true) where cycle_id=v_cycle;
 update public.penta_system_registry set last_verified_at=now(),updated_at=now(),metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('last_self_cycle_id',v_cycle,'last_self_cycle_state',v_state,'last_self_cycle_at',now()) where system_key in('penta.fabrics','penta.self','penta.meshes');
 return jsonb_build_object('service','ct.penta.self.v1','phase',3,'production',true,'cycle_id',v_cycle,'state',upper(v_state),'health',v_health,'actions',jsonb_build_object('scheduler',v_scheduler,'failed_job_recovery',v_recovery,'topology',v_topology,'discovery',v_discovery,'legacy_heal',v_legacy,'provider_evidence',v_evidence,'build_quality',v_build,'nurture',v_nurture,'route',v_route,'secure',v_secure),'authority_manufacture',false,'d3_human_reserved',true,'at',now());
exception when others then
 update penta_self.cycle_receipts_v1 set state='failed',completed_at=clock_timestamp(),summary=jsonb_build_object('error',left(sqlerrm,300)),evidence=jsonb_build_object('sqlstate',sqlstate) where cycle_id=v_cycle;
 return jsonb_build_object('service','ct.penta.self.v1','phase',3,'production',true,'cycle_id',v_cycle,'state','FAILED','error',left(sqlerrm,300),'authority_manufacture',false,'d3_human_reserved',true,'at',now());
end $$;

create or replace function penta_self.status_v1()
returns jsonb language sql stable security definer set search_path='pg_catalog','penta_self','penta_runtime' as $$
select jsonb_build_object('service','ct.penta.self.v1','phase',3,'state','PRODUCTION','position','between PentaFabrics and PentaMeshes','health',penta_self.health_snapshot_v1(),'capabilities',(select jsonb_agg(jsonb_build_object('key',capability_key,'name',canonical_name,'mode',action_mode,'max_risk_class',max_risk_class,'handler_ref',handler_ref,'enabled',enabled) order by capability_key) from penta_self.capability_registry_v1),'latest_cycle',(select to_jsonb(c) from penta_self.cycle_receipts_v1 c order by started_at desc limit 1),'fabrics',penta_runtime.penta_fabrics_status_v1(),'meshes',penta_runtime.penta_meshes_status_v1(),'guardrails',jsonb_build_object('d3_human_reserved',true,'authority_manufacture',false,'credential_manufacture',false,'uncertified_provider_write',false,'money_movement_without_authority',false,'universal_delete',false),'generated_at',now());
$$;

create or replace function penta_runtime.penta_fabric_cycle_v1()
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_runtime','penta_self','public' as $$
declare v_self jsonb; v_status jsonb; v_mesh jsonb; v_state text;
begin
 if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.fabric.v1',0)) then return jsonb_build_object('service','ct.penta.fabrics.v1','phase',3,'state','SKIPPED_LOCKED','production',true,'at',now()); end if;
 begin v_self:=penta_self.tick_v1(); exception when others then v_self:=jsonb_build_object('state','FAILED','error',left(sqlerrm,300)); end;
 begin v_mesh:=penta_runtime.penta_meshes_status_v1(); exception when others then v_mesh:=jsonb_build_object('state','FAILED','error',left(sqlerrm,300)); end;
 v_status:=penta_runtime.penta_fabrics_status_v1();
 v_state:=case when coalesce(v_self->>'state','FAILED') in('HEALTHY','SKIPPED_LOCKED') and coalesce(v_mesh->>'state','FAILED')='PRODUCTION' then 'HEALTHY' else 'DEGRADED' end;
 update penta_runtime.fabrics_v1 set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('last_fabric_cycle_at',now(),'last_fabric_cycle_state',v_state,'self_cycle_state',v_self->>'state','mesh_state',v_mesh->>'state'),updated_at=now() where fabric_id='ct.fabric.penta.v1';
 return jsonb_build_object('service','ct.penta.fabrics.v1','phase',3,'production',true,'state',v_state,'fabric',v_status,'self',v_self,'mesh',v_mesh,'authority_manufacture',false,'at',now());
end $$;

create or replace function public.penta_self_tick_v1() returns jsonb language sql security definer set search_path='pg_catalog','penta_self' as $$ select penta_self.tick_v1(); $$;
create or replace function public.penta_self_status_v1() returns jsonb language sql stable security definer set search_path='pg_catalog','penta_self' as $$ select penta_self.status_v1(); $$;
create or replace function public.penta_fabrics_status_v1() returns jsonb language sql stable security definer set search_path='pg_catalog','penta_runtime' as $$ select penta_runtime.penta_fabrics_status_v1(); $$;
create or replace function public.penta_meshes_status_v1() returns jsonb language sql stable security definer set search_path='pg_catalog','penta_runtime' as $$ select penta_runtime.penta_meshes_status_v1(); $$;
create or replace function public.penta_fabric_cycle_v1() returns jsonb language sql security definer set search_path='pg_catalog','penta_runtime' as $$ select penta_runtime.penta_fabric_cycle_v1(); $$;
create or replace function public.penta_mesh_select_route_v1(p_request jsonb) returns jsonb language sql stable security definer set search_path='pg_catalog','penta_runtime' as $$ select penta_runtime.penta_mesh_select_route_v1(p_request); $$;

revoke all on function penta_runtime.penta_fabrics_status_v1() from public,anon,authenticated;
revoke all on function penta_runtime.penta_meshes_status_v1() from public,anon,authenticated;
revoke all on function penta_runtime.penta_fabric_cycle_v1() from public,anon,authenticated;
revoke all on function penta_self.scheduler_reconcile_v1(uuid) from public,anon,authenticated;
revoke all on function penta_self.failed_job_recovery_v1(uuid) from public,anon,authenticated;
revoke all on function penta_self.fabric_mesh_reconcile_v1(uuid) from public,anon,authenticated;
revoke all on function penta_self.health_snapshot_v1() from public,anon,authenticated;
revoke all on function penta_self.tick_v1() from public,anon,authenticated;
revoke all on function penta_self.status_v1() from public,anon,authenticated;
revoke all on function public.penta_self_tick_v1() from public,anon,authenticated;
revoke all on function public.penta_self_status_v1() from public,anon,authenticated;
revoke all on function public.penta_fabrics_status_v1() from public,anon,authenticated;
revoke all on function public.penta_meshes_status_v1() from public,anon,authenticated;
revoke all on function public.penta_fabric_cycle_v1() from public,anon,authenticated;
revoke all on function public.penta_mesh_select_route_v1(jsonb) from public,anon,authenticated;

grant execute on function penta_runtime.penta_fabrics_status_v1() to service_role;
grant execute on function penta_runtime.penta_meshes_status_v1() to service_role;
grant execute on function penta_runtime.penta_fabric_cycle_v1() to service_role;
grant execute on function penta_self.scheduler_reconcile_v1(uuid) to service_role;
grant execute on function penta_self.failed_job_recovery_v1(uuid) to service_role;
grant execute on function penta_self.fabric_mesh_reconcile_v1(uuid) to service_role;
grant execute on function penta_self.health_snapshot_v1() to service_role;
grant execute on function penta_self.tick_v1() to service_role;
grant execute on function penta_self.status_v1() to service_role;
grant execute on function public.penta_self_tick_v1() to service_role;
grant execute on function public.penta_self_status_v1() to service_role;
grant execute on function public.penta_fabrics_status_v1() to service_role;
grant execute on function public.penta_meshes_status_v1() to service_role;
grant execute on function public.penta_fabric_cycle_v1() to service_role;
grant execute on function public.penta_mesh_select_route_v1(jsonb) to service_role;

-- Ensure the self-healing worker exists and conforms to production cadence.
do $$ declare v_job bigint; begin
 select jobid into v_job from cron.job where jobname='ct-penta-self-v1' limit 1;
 if v_job is null then perform cron.schedule('ct-penta-self-v1','*/2 * * * *','select public.penta_self_tick_v1();');
 else perform cron.alter_job(v_job,schedule=>'*/2 * * * *',command=>'select public.penta_self_tick_v1();',active=>true); end if;
end $$;

update public.penta_system_registry set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('self_capability_count',(select count(*) from penta_self.capability_registry_v1 where enabled),'capability_registry','penta_self.capability_registry_v1','source_converged_at',now()),last_verified_at=now(),updated_at=now() where system_key='penta.self';
