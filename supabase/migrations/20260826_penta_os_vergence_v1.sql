-- PentaOS / PentaVergence v1
-- Canonical Penta* human namespace over compatibility-preserved machine contracts.

create schema if not exists penta_runtime;

create table if not exists penta_runtime.component_registry_v1 (
  component_key text primary key,
  canonical_name text not null unique,
  role text not null,
  primary_axis text not null check (primary_axis in ('truth','authority','execution','interoperation','continuity')),
  stable_contract_id text not null,
  implementation_state text not null default 'active',
  aliases text[] not null default '{}',
  backing_refs jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table penta_runtime.component_registry_v1 enable row level security;
alter table penta_runtime.component_registry_v1 force row level security;
revoke all on penta_runtime.component_registry_v1 from public, anon, authenticated;
grant select,insert,update,delete on penta_runtime.component_registry_v1 to service_role;

create table if not exists penta_runtime.topology_edges_v1 (
  edge_id uuid primary key default gen_random_uuid(),
  source_key text not null references penta_runtime.component_registry_v1(component_key) on delete cascade,
  target_key text not null references penta_runtime.component_registry_v1(component_key) on delete cascade,
  relation text not null,
  required boolean not null default true,
  state text not null default 'bound',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(source_key,target_key,relation)
);
alter table penta_runtime.topology_edges_v1 enable row level security;
alter table penta_runtime.topology_edges_v1 force row level security;
revoke all on penta_runtime.topology_edges_v1 from public, anon, authenticated;
grant select,insert,update,delete on penta_runtime.topology_edges_v1 to service_role;

create table if not exists penta_runtime.agent_registry_v1 (
  agent_id text primary key,
  canonical_name text not null,
  owner_component_key text not null references penta_runtime.component_registry_v1(component_key),
  role text not null,
  autonomy_ceiling text not null default 'A2',
  decision_ceiling text not null default 'D2',
  vote_eligible boolean not null default false,
  self_approval boolean not null default false,
  status text not null default 'active',
  capabilities text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table penta_runtime.agent_registry_v1 enable row level security;
alter table penta_runtime.agent_registry_v1 force row level security;
revoke all on penta_runtime.agent_registry_v1 from public, anon, authenticated;
grant select,insert,update,delete on penta_runtime.agent_registry_v1 to service_role;

create table if not exists penta_runtime.repository_registry_v1 (
  repository_full_name text primary key,
  canonical_role text not null,
  enabled boolean not null default true,
  mutation_policy text not null default 'governed',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table penta_runtime.repository_registry_v1 enable row level security;
alter table penta_runtime.repository_registry_v1 force row level security;
revoke all on penta_runtime.repository_registry_v1 from public, anon, authenticated;
grant select,insert,update,delete on penta_runtime.repository_registry_v1 to service_role;

create table if not exists penta_runtime.vergence_jobs_v1 (
  job_id uuid primary key default gen_random_uuid(),
  cycle_key text not null,
  repository_full_name text not null references penta_runtime.repository_registry_v1(repository_full_name),
  mode text not null check (mode in ('continuity','deep','manual')),
  state text not null default 'queued' check (state in ('queued','claimed','completed','failed')),
  request jsonb not null default '{}'::jsonb,
  result jsonb,
  worker_run_id text,
  available_at timestamptz not null default now(),
  claimed_at timestamptz,
  completed_at timestamptz,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(cycle_key, repository_full_name)
);
create index if not exists vergence_jobs_v1_claim_idx on penta_runtime.vergence_jobs_v1(repository_full_name,state,available_at,created_at);
alter table penta_runtime.vergence_jobs_v1 enable row level security;
alter table penta_runtime.vergence_jobs_v1 force row level security;
revoke all on penta_runtime.vergence_jobs_v1 from public, anon, authenticated;
grant select,insert,update,delete on penta_runtime.vergence_jobs_v1 to service_role;

create table if not exists penta_runtime.vergence_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  job_id uuid not null references penta_runtime.vergence_jobs_v1(job_id) on delete cascade,
  repository_full_name text not null,
  mode text not null,
  disposition text not null,
  report jsonb not null,
  evidence_sha256 text,
  created_at timestamptz not null default now()
);
alter table penta_runtime.vergence_receipts_v1 enable row level security;
alter table penta_runtime.vergence_receipts_v1 force row level security;
revoke all on penta_runtime.vergence_receipts_v1 from public, anon, authenticated;
grant select,insert on penta_runtime.vergence_receipts_v1 to service_role;

insert into penta_runtime.component_registry_v1(component_key,canonical_name,role,primary_axis,stable_contract_id,aliases,backing_refs) values
('penta.os','PentaOS','Operating-system umbrella and canonical technical namespace','execution','ct.penta.os.v1',array['CrownThrive OS'],jsonb_build_object('source','CrownThrive-Support')),
('penta.vergence','PentaVergence','Convergence, reconciliation, stale-state repair and supersession','continuity','ct.penta.vergence.v1','{}',jsonb_build_object('runtime','penta_runtime.vergence_jobs_v1')),
('penta.techture','PentaTechture','Architecture definitions, ADRs and system decomposition','truth','ct.penta.techture.v1',array['architecture'],'{}'),
('penta.pology','PentaPology','Topology graph, dependencies, routes and reachability','interoperation','ct.penta.pology.v1',array['topology'],jsonb_build_object('runtime','penta_runtime.topology_edges_v1')),
('penta.planes','PentaPlanes','Plane abstraction and plane boundary registry','authority','ct.penta.planes.v1',array['planes'],'{}'),
('penta.orchestrator','PentaOrchestrator','Governed orchestration and sequencing','execution','ct.penta.orchestrator.v1',array['orchestration layer'],'{}'),
('penta.flows','PentaFlows','Workflows, state machines and runbooks','execution','ct.penta.flows.v1',array['workflows'],'{}'),
('penta.flex','PentaFlex','API, MCP and adapter framework','interoperation','ct.penta.flex.v1',array['API/MCP framework'],jsonb_build_object('edge_function','penta-flex')),
('penta.interops','PentaInterOps','Interoperability contracts, transforms and certification','interoperation','ct.penta.interops.v1',array['interoperability layer'],jsonb_build_object('legacy_tables',jsonb_build_array('chlom_runtime.interop_contract_registry','chlom_runtime.interop_route_registry','chlom_runtime.interop_certification_registry'))),
('penta.wire','PentaWire','Transport, event and connection fabric','interoperation','ct.penta.wire.v1',array['wire'],'{}'),
('penta.bind','PentaBind','Explicit bindings among systems, services, agents and assets','interoperation','ct.penta.bind.v1',array['bind'],jsonb_build_object('legacy_bindings_preserved',true)),
('penta.bound','PentaBound','Policy, capability and authority boundaries','authority','ct.penta.bound.v1',array['bounded authority'],'{}'),
('penta.secure','PentaSecure','Security, trust, identity, secret boundary and assurance','authority','ct.penta.secure.v1',array['PentaSecure Layer'],jsonb_build_object('runtime','penta_runtime.pentasecure_cycle_v1')),
('penta.agents','PentaAgents','Executable agent layer and agent registry','execution','ct.penta.agents.v1',array['PentaAgentic'],jsonb_build_object('runtime','penta_runtime.agent_registry_v1')),
('penta.mcl','PentaMCL','Machine-learning lifecycle, evaluation and advisory models','execution','ct.penta.mcl.v1',array['PentaML','ML'],'{}'),
('penta.llm','PentaLLM','LLM provider, model, prompt and routing contracts','execution','ct.penta.llm.v1',array['LLM'],'{}'),
('penta.rithms','PentaRithms','Algorithm registry and deterministic/model-assisted algorithm assets','execution','ct.penta.rithms.v1',array['algorithms'],'{}'),
('penta.boxes','PentaBoxes','Plugin and capability packages','execution','ct.penta.boxes.v1',array['plugins'],jsonb_build_object('legacy_tables',jsonb_build_array('chlom_runtime.plugin_bindings','chlom_runtime.plugin_capability_bindings'))),
('penta.stars','PentaStars','Contracts, schemas, invariants, SLAs and interface guarantees','truth','ct.penta.stars.v1',array['contracts'],'{}'),
('penta.sets','PentaSets','Asset, dataset, corpus, model and creative-asset registry','truth','ct.penta.sets.v1',array['assets'],jsonb_build_object('legacy_table','penta_runtime.asset_bindings_v1')),
('penta.skills','PentaSkills','Reusable skill packages','execution','ct.penta.skills.v1',array['skills'],'{}'),
('penta.tools','PentaTools','Executable tools and tool contracts','execution','ct.penta.tools.v1',array['tools'],'{}'),
('penta.scripts','PentaScripts','Reproducible scripts and maintenance utilities','execution','ct.penta.scripts.v1',array['scripts'],'{}'),
('penta.maps','PentaMaps','Architecture, topology and flow visualization specs and projections','truth','ct.penta.maps.v1',array['diagrams','Canva infographics','visualized data'],'{}'),
('penta.ip','PentaIP','IP classification, provenance, disclosure, licensing and commercialization controls','authority','ct.penta.ip.v1',array['IP'],'{}'),
('penta.base','PentaBase','Data and control-plane substrate','execution','ct.penta.base.v1',array['ThriveBase','Supabase'],jsonb_build_object('project_ref','tzajnzshmtzjenqulehq')),
('penta.factory','PentaFactory','Governed software and component production factory','execution','ct.pentaframework-factory.v1',array['PentaFramework Factory','Software Factory v2','Software Factory v3','Software Factory v4'],jsonb_build_object('legacy_prefix','ct_factory_')),
('penta.docs','PentaDocs','Institutional documentation and knowledge projection','truth','ct.penta.docs.v1',array['Mintlify','Help Center'],'{}'),
('penta.route','PentaRoute','Routing and delivery primitives','interoperation','ct.penta.route.v3',array['PentaFetch','PentaGet','PentaQuery','PentaSearch','PentaParse','PentaCache','PentaQueue','PentaRetry','PentaSync','PentaResolve','PentaStream','PentaEvent','PentaHook','PentaAuth','PentaSign','PentaAudit','PentaTest','PentaDeploy'],jsonb_build_object('runtime_table','integration_control.pentaroute_components_v3')),
('penta.federation','PentaFederation','Repository, platform and system federation','interoperation','ct.penta.federation.v1',array['federation layer'],jsonb_build_object('runtime_function','penta_runtime.penta_federation_status_v1')),
('penta.fabric','PentaFabric','Runtime and federation fabric compatibility surface','interoperation','ct.penta.fabric.v1',array['Pentafabric'],'{}'),
('penta.generation','PentaGeneration','Seven-generation continuity and succession','continuity','ct.penta.generation.v1','{}',jsonb_build_object('runtime_function','penta_runtime.penta_generation_handoff_v1')),
('penta.studios','PentaStudios','Media production/runtime integration','execution','ct.penta.studios.v1','{}',jsonb_build_object('adapter','ct.adapter.pentastudios.control.v1')),
('penta.books','PentaBooks','Governed publishing, canon and book-production runtime','execution','ct.penta.books.v1','{}',jsonb_build_object('runtime_table','public.penta_books'))
on conflict(component_key) do update set canonical_name=excluded.canonical_name,role=excluded.role,primary_axis=excluded.primary_axis,stable_contract_id=excluded.stable_contract_id,aliases=excluded.aliases,backing_refs=excluded.backing_refs,enabled=true,updated_at=now();

insert into penta_runtime.topology_edges_v1(source_key,target_key,relation,required) values
('penta.os','penta.vergence','contains',true),('penta.os','penta.techture','contains',true),('penta.os','penta.pology','contains',true),('penta.os','penta.planes','contains',true),('penta.os','penta.orchestrator','contains',true),('penta.os','penta.flex','contains',true),('penta.os','penta.secure','contains',true),('penta.os','penta.agents','contains',true),('penta.os','penta.base','runs_on',true),('penta.vergence','penta.base','stores_state_in',true),('penta.vergence','penta.pology','reads',true),('penta.vergence','penta.factory','queues_repairs_to',true),('penta.vergence','penta.docs','reconciles',true),('penta.vergence','penta.federation','reconciles',true),('penta.vergence','penta.secure','gated_by',true),('penta.flex','penta.interops','implements',true),('penta.flex','penta.stars','constrained_by',true),('penta.bind','penta.bound','constrained_by',true),('penta.wire','penta.route','uses',true),('penta.agents','penta.skills','uses',true),('penta.agents','penta.tools','uses',true),('penta.agents','penta.rithms','uses',true),('penta.llm','penta.bound','gated_by',true),('penta.mcl','penta.bound','gated_by',true),('penta.sets','penta.ip','classified_by',true),('penta.maps','penta.pology','projects',true),('penta.generation','penta.vergence','inherits',true)
on conflict(source_key,target_key,relation) do update set required=excluded.required,state='bound',updated_at=now();

insert into penta_runtime.agent_registry_v1(agent_id,canonical_name,owner_component_key,role,capabilities) values
('ct.penta.agent.vergence','PentaVergence Agent','penta.vergence','Repository/runtime reconciliation and stale-state classification',array['audit','classify','close_represented','merge_governed_candidate','queue_repair']),
('ct.penta.agent.architect','PentaTechture Agent','penta.techture','Architecture consistency and ADR stewardship',array['architecture_check','adr_diff','dependency_review']),
('ct.penta.agent.topologist','PentaPology Agent','penta.pology','Topology graph and dependency assurance',array['topology_read','edge_validate','reachability']),
('ct.penta.agent.flex','PentaFlex Agent','penta.flex','API/MCP/tool-contract interoperability stewardship',array['mcp_contract','api_contract','adapter_check']),
('ct.penta.agent.security','PentaSecure Agent','penta.secure','Security and boundary assurance',array['security_review','boundary_check','secret_shape_scan']),
('ct.penta.agent.orchestrator','PentaOrchestrator Agent','penta.orchestrator','Sequencing and governed work dispatch',array['plan','dispatch','reconcile']),
('ct.penta.agent.ip','PentaIP Agent','penta.ip','IP classification and disclosure-routing support',array['classify','provenance','license_route']),
('ct.penta.agent.model-governor','PentaModel Agent','penta.mcl','ML/LLM lifecycle and evaluation routing',array['model_registry','eval_route','llm_route'])
on conflict(agent_id) do update set canonical_name=excluded.canonical_name,owner_component_key=excluded.owner_component_key,role=excluded.role,capabilities=excluded.capabilities,status='active',updated_at=now();

insert into penta_runtime.repository_registry_v1(repository_full_name,canonical_role,mutation_policy) values
('crownthrive1/CrownThrive-Support','PentaOS institutional source and PentaDocs','governed'),
('crownthrive1/CrownThrive-CIE','CIE child framework repository','governed'),
('crownthrive1/chlom-protocol','CHLOM protocol child repository','governed')
on conflict(repository_full_name) do update set canonical_role=excluded.canonical_role,mutation_policy=excluded.mutation_policy,enabled=true,updated_at=now();

create or replace function penta_runtime.penta_registry_status_v1()
returns jsonb language sql stable security definer set search_path=penta_runtime,pg_temp as $$
  select jsonb_build_object(
    'contract','ct.penta.registry.status.v1',
    'components',(select count(*) from component_registry_v1 where enabled),
    'agents',(select count(*) from agent_registry_v1 where status='active'),
    'edges',(select count(*) from topology_edges_v1 where state='bound'),
    'repositories',(select count(*) from repository_registry_v1 where enabled),
    'axes',jsonb_build_array('truth','authority','execution','interoperation','continuity'),
    'generated_at',now()
  );
$$;
revoke all on function penta_runtime.penta_registry_status_v1() from public,anon,authenticated;
grant execute on function penta_runtime.penta_registry_status_v1() to service_role;

create or replace function penta_runtime.penta_topology_v1()
returns jsonb language sql stable security definer set search_path=penta_runtime,pg_temp as $$
  select jsonb_build_object(
    'contract','ct.penta.pology.graph.v1',
    'nodes',coalesce((select jsonb_agg(jsonb_build_object('key',component_key,'name',canonical_name,'axis',primary_axis,'contract',stable_contract_id,'state',implementation_state) order by component_key) from component_registry_v1 where enabled),'[]'::jsonb),
    'edges',coalesce((select jsonb_agg(jsonb_build_object('source',source_key,'target',target_key,'relation',relation,'required',required,'state',state) order by source_key,target_key,relation) from topology_edges_v1),'[]'::jsonb),
    'generated_at',now()
  );
$$;
revoke all on function penta_runtime.penta_topology_v1() from public,anon,authenticated;
grant execute on function penta_runtime.penta_topology_v1() to service_role;

create or replace function penta_runtime.penta_vergence_enqueue_v1(p_mode text default 'continuity')
returns jsonb language plpgsql security definer set search_path=penta_runtime,pg_temp as $$
declare v_mode text:=lower(coalesce(p_mode,'continuity')); v_cycle text; v_count integer:=0;
begin
  if v_mode not in ('continuity','deep','manual') then raise exception 'unsupported mode: %',v_mode; end if;
  if v_mode='deep' then
    v_cycle:='deep:'||to_char(timezone('America/New_York',now()),'YYYY-MM-DD');
  elsif v_mode='continuity' then
    v_cycle:='continuity:'||floor(extract(epoch from now())/14400)::bigint::text;
  else
    v_cycle:='manual:'||to_char(now(),'YYYYMMDDHH24MISSMS');
  end if;
  insert into vergence_jobs_v1(cycle_key,repository_full_name,mode,request)
  select v_cycle,r.repository_full_name,v_mode,jsonb_build_object('contract','ct.penta.vergence.request.v1','source','PentaBase','mode',v_mode,'requested_at',now())
  from repository_registry_v1 r where r.enabled
  on conflict(cycle_key,repository_full_name) do nothing;
  get diagnostics v_count=row_count;
  return jsonb_build_object('contract','ct.penta.vergence.enqueue.v1','cycle_key',v_cycle,'mode',v_mode,'jobs_created',v_count,'scheduled_at',now());
end;$$;
revoke all on function penta_runtime.penta_vergence_enqueue_v1(text) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_enqueue_v1(text) to service_role;

create or replace function penta_runtime.penta_vergence_deep_gate_v1()
returns jsonb language plpgsql security definer set search_path=penta_runtime,pg_temp as $$
declare v_local timestamp:=timezone('America/New_York',now());
begin
  if extract(hour from v_local)::integer <> 23 then
    return jsonb_build_object('contract','ct.penta.vergence.deep-gate.v1','result','NOOP_OUTSIDE_23_LOCAL','local_time',v_local);
  end if;
  return penta_runtime.penta_vergence_enqueue_v1('deep');
end;$$;
revoke all on function penta_runtime.penta_vergence_deep_gate_v1() from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_deep_gate_v1() to service_role;

create or replace function penta_runtime.penta_vergence_claim_v1(p_repository text,p_worker_run_id text default null)
returns jsonb language plpgsql security definer set search_path=penta_runtime,pg_temp as $$
declare v_job vergence_jobs_v1%rowtype;
begin
  with candidate as (
    select job_id from vergence_jobs_v1
    where repository_full_name=p_repository and state='queued' and available_at<=now()
    order by case mode when 'deep' then 0 when 'manual' then 1 else 2 end, created_at
    for update skip locked limit 1
  )
  update vergence_jobs_v1 j set state='claimed',claimed_at=now(),worker_run_id=p_worker_run_id,updated_at=now()
  from candidate c where j.job_id=c.job_id returning j.* into v_job;
  if v_job.job_id is null then return jsonb_build_object('claimed',false,'repository',p_repository); end if;
  return jsonb_build_object('claimed',true,'job_id',v_job.job_id,'cycle_key',v_job.cycle_key,'repository',v_job.repository_full_name,'mode',v_job.mode,'request',v_job.request);
end;$$;
revoke all on function penta_runtime.penta_vergence_claim_v1(text,text) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_claim_v1(text,text) to service_role;

create or replace function penta_runtime.penta_vergence_complete_v1(p_job_id uuid,p_report jsonb,p_evidence_sha256 text default null)
returns jsonb language plpgsql security definer set search_path=penta_runtime,pg_temp as $$
declare v_job vergence_jobs_v1%rowtype; v_disposition text;
begin
  select * into v_job from vergence_jobs_v1 where job_id=p_job_id for update;
  if v_job.job_id is null then raise exception 'job not found'; end if;
  if v_job.state <> 'claimed' then raise exception 'job not claimed: %',v_job.state; end if;
  v_disposition:=case when coalesce((p_report->>'mutations')::integer,0)>0 then 'MUTATED' else 'OBSERVED' end;
  update vergence_jobs_v1 set state='completed',result=p_report,error=null,completed_at=now(),updated_at=now() where job_id=p_job_id;
  insert into vergence_receipts_v1(job_id,repository_full_name,mode,disposition,report,evidence_sha256)
  values(p_job_id,v_job.repository_full_name,v_job.mode,v_disposition,p_report,p_evidence_sha256);
  return jsonb_build_object('contract','ct.penta.vergence.complete.v1','job_id',p_job_id,'state','completed','disposition',v_disposition);
end;$$;
revoke all on function penta_runtime.penta_vergence_complete_v1(uuid,jsonb,text) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_complete_v1(uuid,jsonb,text) to service_role;

create or replace function penta_runtime.penta_vergence_release_v1(p_job_id uuid,p_error text default 'worker_failed')
returns jsonb language plpgsql security definer set search_path=penta_runtime,pg_temp as $$
begin
  update vergence_jobs_v1 set state='queued',claimed_at=null,worker_run_id=null,available_at=now()+interval '15 minutes',error=left(coalesce(p_error,'worker_failed'),1000),updated_at=now()
  where job_id=p_job_id and state='claimed';
  return jsonb_build_object('contract','ct.penta.vergence.release.v1','job_id',p_job_id,'released',found);
end;$$;
revoke all on function penta_runtime.penta_vergence_release_v1(uuid,text) from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_release_v1(uuid,text) to service_role;

create or replace function penta_runtime.penta_vergence_status_v1()
returns jsonb language sql stable security definer set search_path=penta_runtime,pg_temp as $$
  select jsonb_build_object(
    'contract','ct.penta.vergence.status.v1',
    'queued',(select count(*) from vergence_jobs_v1 where state='queued'),
    'claimed',(select count(*) from vergence_jobs_v1 where state='claimed'),
    'completed',(select count(*) from vergence_jobs_v1 where state='completed'),
    'failed',(select count(*) from vergence_jobs_v1 where state='failed'),
    'last_completed_at',(select max(completed_at) from vergence_jobs_v1 where state='completed'),
    'cadence',jsonb_build_object('continuity','every_4_hours','deep','23:00 America/New_York'),
    'generated_at',now()
  );
$$;
revoke all on function penta_runtime.penta_vergence_status_v1() from public,anon,authenticated;
grant execute on function penta_runtime.penta_vergence_status_v1() to service_role;

-- PentaBase owns the substantive cadence. Repository workers may poll more often,
-- but perform no convergence work unless one of these jobs exists.
do $$
begin
  perform cron.unschedule(jobid) from cron.job where jobname='penta-vergence-continuity-4h-v1';
  perform cron.unschedule(jobid) from cron.job where jobname='penta-vergence-deep-local-gate-v1';
exception when undefined_table then null;
end$$;
select cron.schedule('penta-vergence-continuity-4h-v1','23 */4 * * *',$$select penta_runtime.penta_vergence_enqueue_v1('continuity');$$);
select cron.schedule('penta-vergence-deep-local-gate-v1','0 * * * *',$$select penta_runtime.penta_vergence_deep_gate_v1();$$);
