-- CrownThrive Institutional Capability Runtime v1
-- Additive, service-only control plane extension. No secret values are stored here.

insert into chlom_runtime.modules (
  module_id, framework_id, canonical_name, module_class, semantic_version,
  lifecycle_state, authority_ceiling, self_healing_class, public_contract,
  restricted_contract_ref, implementation_ref, mcp_enabled, api_enabled, metadata
) values (
  'ct.chlom.institutional-capability-runtime',
  'ct.framework.chlom',
  'CrownThrive Institutional Capability Runtime',
  'agent_fabric',
  '1.0.0',
  'test',
  'D2',
  'rollback_capable',
  jsonb_build_object(
    'contract','ct.contract.institutional-capability-runtime.v1',
    'modes',jsonb_build_array('registry','compile','invoke','self','baseline'),
    'self_awareness','bounded_and_queryable',
    'no_unconstrained_autonomy',true
  ),
  'vault://chlom/institutional-capability-runtime/v1',
  'edge://crownthrive-continuity-compiler/v1',
  true,
  true,
  jsonb_build_object(
    'owner','CrownThrive LLC',
    'control_plane','THIVEBASE',
    'identity_provenance','CHLOM',
    'culture_alignment','CIE',
    'state','CONTROLLED_TEST',
    'builder_verifier_separation',true
  )
)
on conflict (module_id) do update set
  semantic_version=excluded.semantic_version,
  lifecycle_state=excluded.lifecycle_state,
  authority_ceiling=excluded.authority_ceiling,
  self_healing_class=excluded.self_healing_class,
  public_contract=excluded.public_contract,
  restricted_contract_ref=excluded.restricted_contract_ref,
  implementation_ref=excluded.implementation_ref,
  mcp_enabled=excluded.mcp_enabled,
  api_enabled=excluded.api_enabled,
  metadata=chlom_runtime.modules.metadata || excluded.metadata,
  updated_at=now();

create table if not exists institutional_federation.capability_genome_versions (
  capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete cascade,
  semantic_version text not null,
  genome jsonb not null,
  genome_sha256 text not null check (genome_sha256 ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('controlled_test','verified','active','hold','superseded','retired')),
  executable boolean not null default false,
  implementation_ref text,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  primary key (capability_id, semantic_version)
);

create table if not exists institutional_federation.skill_genome_versions (
  skill_id text not null,
  semantic_version text not null,
  capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete cascade,
  genome jsonb not null,
  genome_sha256 text not null check (genome_sha256 ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('controlled_test','verified','active','hold','superseded','retired')),
  executable boolean not null default false,
  implementation_ref text,
  created_at timestamptz not null default now(),
  primary key (skill_id, semantic_version)
);

create table if not exists institutional_federation.agent_genome_versions (
  agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  semantic_version text not null,
  genome jsonb not null,
  genome_sha256 text not null check (genome_sha256 ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('controlled_test','verified','active','hold','superseded','retired')),
  created_at timestamptz not null default now(),
  last_verified_at timestamptz,
  primary key (agent_id, semantic_version)
);

create table if not exists institutional_federation.capability_dependency_edges (
  capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete cascade,
  depends_on_capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete restrict,
  dependency_type text not null default 'required' check (dependency_type in ('required','optional','verification','commercialization','custody')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (capability_id, depends_on_capability_id, dependency_type),
  check (capability_id <> depends_on_capability_id)
);

create table if not exists institutional_federation.capability_agent_bindings (
  capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete cascade,
  agent_id text not null references chlom_runtime.agent_templates(agent_id) on delete restrict,
  binding_role text not null check (binding_role in ('owner','builder','verifier','security','custody','docs','commercialization')),
  priority smallint not null default 100 check (priority between 1 and 1000),
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (capability_id, agent_id, binding_role)
);

create table if not exists institutional_federation.completion_contract_versions (
  contract_id text not null,
  semantic_version text not null,
  contract jsonb not null,
  contract_sha256 text not null check (contract_sha256 ~ '^[0-9a-f]{64}$'),
  status text not null check (status in ('controlled_test','verified','active','hold','superseded','retired')),
  created_at timestamptz not null default now(),
  primary key (contract_id, semantic_version)
);

create table if not exists institutional_federation.continuity_compiler_runs (
  run_id uuid primary key default gen_random_uuid(),
  intent text not null,
  requested_by text,
  compiled_graph jsonb not null,
  risk_ceiling text not null check (risk_ceiling in ('D0','D1','D2','D3')),
  run_state text not null check (run_state in ('compiled','queued','running','hold','completed','failed','superseded')),
  graph_sha256 text not null check (graph_sha256 ~ '^[0-9a-f]{64}$'),
  evidence_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists institutional_federation.capability_execution_queue (
  queue_id uuid primary key default gen_random_uuid(),
  compiler_run_id uuid references institutional_federation.continuity_compiler_runs(run_id) on delete set null,
  capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete restrict,
  semantic_version text not null default '1.0.0',
  assigned_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verifier_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  execution_mode text not null check (execution_mode in ('native','agent_dispatch','provider_adapter','human_gate')),
  queue_state text not null check (queue_state in ('queued','dispatched','running','hold','completed','failed','superseded')),
  requires_human boolean not null default false,
  payload jsonb not null default '{}'::jsonb,
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  scheduled_for timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists institutional_federation.capability_execution_receipts (
  receipt_id uuid primary key default gen_random_uuid(),
  queue_id uuid references institutional_federation.capability_execution_queue(queue_id) on delete set null,
  compiler_run_id uuid references institutional_federation.continuity_compiler_runs(run_id) on delete set null,
  capability_id text not null references chlom_runtime.module_capabilities(capability_id) on delete restrict,
  agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  verifier_agent_id text references chlom_runtime.agent_templates(agent_id) on delete restrict,
  receipt_state text not null check (receipt_state in ('dispatched','running','pass','hold','fail','superseded')),
  input_sha256 text not null check (input_sha256 ~ '^[0-9a-f]{64}$'),
  output_sha256 text check (output_sha256 is null or output_sha256 ~ '^[0-9a-f]{64}$'),
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  verified_at timestamptz
);

create table if not exists institutional_federation.baseline_snapshots (
  snapshot_id uuid primary key default gen_random_uuid(),
  scope text not null,
  semantic_version text not null,
  capability_count integer not null,
  skill_count integer not null,
  agent_count integer not null,
  dependency_count integer not null,
  snapshot jsonb not null,
  snapshot_sha256 text not null check (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  snapshot_state text not null check (snapshot_state in ('controlled_test','verified','active','hold','superseded')),
  created_at timestamptz not null default now()
);

alter table institutional_federation.capability_genome_versions enable row level security;
alter table institutional_federation.capability_genome_versions force row level security;
alter table institutional_federation.skill_genome_versions enable row level security;
alter table institutional_federation.skill_genome_versions force row level security;
alter table institutional_federation.agent_genome_versions enable row level security;
alter table institutional_federation.agent_genome_versions force row level security;
alter table institutional_federation.capability_dependency_edges enable row level security;
alter table institutional_federation.capability_dependency_edges force row level security;
alter table institutional_federation.capability_agent_bindings enable row level security;
alter table institutional_federation.capability_agent_bindings force row level security;
alter table institutional_federation.completion_contract_versions enable row level security;
alter table institutional_federation.completion_contract_versions force row level security;
alter table institutional_federation.continuity_compiler_runs enable row level security;
alter table institutional_federation.continuity_compiler_runs force row level security;
alter table institutional_federation.capability_execution_queue enable row level security;
alter table institutional_federation.capability_execution_queue force row level security;
alter table institutional_federation.capability_execution_receipts enable row level security;
alter table institutional_federation.capability_execution_receipts force row level security;
alter table institutional_federation.baseline_snapshots enable row level security;
alter table institutional_federation.baseline_snapshots force row level security;

revoke all on table institutional_federation.capability_genome_versions from public, anon, authenticated;
revoke all on table institutional_federation.skill_genome_versions from public, anon, authenticated;
revoke all on table institutional_federation.agent_genome_versions from public, anon, authenticated;
revoke all on table institutional_federation.capability_dependency_edges from public, anon, authenticated;
revoke all on table institutional_federation.capability_agent_bindings from public, anon, authenticated;
revoke all on table institutional_federation.completion_contract_versions from public, anon, authenticated;
revoke all on table institutional_federation.continuity_compiler_runs from public, anon, authenticated;
revoke all on table institutional_federation.capability_execution_queue from public, anon, authenticated;
revoke all on table institutional_federation.capability_execution_receipts from public, anon, authenticated;
revoke all on table institutional_federation.baseline_snapshots from public, anon, authenticated;

grant usage on schema institutional_federation to service_role;
grant select, insert, update on table institutional_federation.capability_genome_versions to service_role;
grant select, insert, update on table institutional_federation.skill_genome_versions to service_role;
grant select, insert, update on table institutional_federation.agent_genome_versions to service_role;
grant select, insert, update on table institutional_federation.capability_dependency_edges to service_role;
grant select, insert, update on table institutional_federation.capability_agent_bindings to service_role;
grant select, insert, update on table institutional_federation.completion_contract_versions to service_role;
grant select, insert, update on table institutional_federation.continuity_compiler_runs to service_role;
grant select, insert, update on table institutional_federation.capability_execution_queue to service_role;
grant select, insert, update on table institutional_federation.capability_execution_receipts to service_role;
grant select, insert on table institutional_federation.baseline_snapshots to service_role;

create or replace function institutional_federation.capture_capability_baseline(
  p_scope text default 'ct.chlom.institutional-capability-runtime'
) returns uuid
language plpgsql
security invoker
set search_path = pg_catalog, extensions, institutional_federation, chlom_runtime
as $$
declare
  v_snapshot jsonb;
  v_id uuid;
  v_hash text;
  v_cap_count int;
  v_skill_count int;
  v_agent_count int;
  v_dep_count int;
begin
  select count(*) into v_cap_count
  from chlom_runtime.module_capabilities
  where module_id='ct.chlom.institutional-capability-runtime';

  select count(*) into v_skill_count
  from institutional_federation.skill_genome_versions s
  join chlom_runtime.module_capabilities c on c.capability_id=s.capability_id
  where c.module_id='ct.chlom.institutional-capability-runtime'
    and s.semantic_version='1.0.0';

  select count(distinct agent_id) into v_agent_count
  from institutional_federation.capability_agent_bindings b
  join chlom_runtime.module_capabilities c on c.capability_id=b.capability_id
  where c.module_id='ct.chlom.institutional-capability-runtime'
    and b.active;

  select count(*) into v_dep_count
  from institutional_federation.capability_dependency_edges d
  join chlom_runtime.module_capabilities c on c.capability_id=d.capability_id
  where c.module_id='ct.chlom.institutional-capability-runtime';

  select jsonb_build_object(
    'scope',p_scope,
    'semantic_version','1.0.0',
    'capabilities',coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability_id',c.capability_id,
        'name',c.canonical_name,
        'version',c.semantic_version,
        'risk_class',c.risk_class,
        'state',c.capability_state,
        'public_safe',c.public_safe,
        'metadata',c.metadata
      ) order by c.capability_id)
      from chlom_runtime.module_capabilities c
      where c.module_id='ct.chlom.institutional-capability-runtime'
    ),'[]'::jsonb),
    'dependencies',coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability_id',d.capability_id,
        'depends_on',d.depends_on_capability_id,
        'type',d.dependency_type
      ) order by d.capability_id,d.depends_on_capability_id,d.dependency_type)
      from institutional_federation.capability_dependency_edges d
      join chlom_runtime.module_capabilities c on c.capability_id=d.capability_id
      where c.module_id='ct.chlom.institutional-capability-runtime'
    ),'[]'::jsonb),
    'bindings',coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability_id',b.capability_id,
        'agent_id',b.agent_id,
        'role',b.binding_role,
        'priority',b.priority
      ) order by b.capability_id,b.binding_role,b.priority,b.agent_id)
      from institutional_federation.capability_agent_bindings b
      join chlom_runtime.module_capabilities c on c.capability_id=b.capability_id
      where c.module_id='ct.chlom.institutional-capability-runtime' and b.active
    ),'[]'::jsonb),
    'completion_contract',(
      select contract
      from institutional_federation.completion_contract_versions
      where contract_id='ct.contract.completion.v1' and semantic_version='1.0.0'
      limit 1
    )
  ) into v_snapshot;

  v_hash := encode(extensions.digest(convert_to(v_snapshot::text,'UTF8'),'sha256'),'hex');

  insert into institutional_federation.baseline_snapshots(
    scope, semantic_version, capability_count, skill_count, agent_count, dependency_count,
    snapshot, snapshot_sha256, snapshot_state
  ) values (
    p_scope,'1.0.0',v_cap_count,v_skill_count,v_agent_count,v_dep_count,
    v_snapshot,v_hash,'controlled_test'
  ) returning snapshot_id into v_id;

  return v_id;
end;
$$;

create or replace function public.ct_continuity_context()
returns jsonb
language sql
security invoker
set search_path = pg_catalog, extensions, institutional_federation, chlom_runtime
as $$
  select jsonb_build_object(
    'module', (
      select jsonb_build_object(
        'module_id',m.module_id,
        'name',m.canonical_name,
        'version',m.semantic_version,
        'state',m.lifecycle_state,
        'authority_ceiling',m.authority_ceiling,
        'public_contract',m.public_contract,
        'metadata',m.metadata
      )
      from chlom_runtime.modules m
      where m.module_id='ct.chlom.institutional-capability-runtime'
    ),
    'capabilities', coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability_id',c.capability_id,
        'name',c.canonical_name,
        'kind',c.capability_kind,
        'version',c.semantic_version,
        'risk_class',c.risk_class,
        'state',c.capability_state,
        'interface_ref',c.interface_ref,
        'public_safe',c.public_safe,
        'genome',g.genome,
        'owner_agent_id',ob.agent_id,
        'verifier_agent_id',vb.agent_id
      ) order by c.capability_id)
      from chlom_runtime.module_capabilities c
      left join institutional_federation.capability_genome_versions g
        on g.capability_id=c.capability_id and g.semantic_version='1.0.0'
      left join lateral (
        select b.agent_id
        from institutional_federation.capability_agent_bindings b
        where b.capability_id=c.capability_id and b.binding_role='owner' and b.active
        order by b.priority asc
        limit 1
      ) ob on true
      left join lateral (
        select b.agent_id
        from institutional_federation.capability_agent_bindings b
        where b.capability_id=c.capability_id and b.binding_role='verifier' and b.active
        order by b.priority asc
        limit 1
      ) vb on true
      where c.module_id='ct.chlom.institutional-capability-runtime'
    ),'[]'::jsonb),
    'dependencies', coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability_id',d.capability_id,
        'depends_on',d.depends_on_capability_id,
        'type',d.dependency_type
      ) order by d.capability_id,d.depends_on_capability_id)
      from institutional_federation.capability_dependency_edges d
      join chlom_runtime.module_capabilities c on c.capability_id=d.capability_id
      where c.module_id='ct.chlom.institutional-capability-runtime'
    ),'[]'::jsonb),
    'completion_contract',(
      select contract
      from institutional_federation.completion_contract_versions
      where contract_id='ct.contract.completion.v1' and semantic_version='1.0.0'
      limit 1
    ),
    'latest_baseline',(
      select jsonb_build_object(
        'snapshot_id',snapshot_id,
        'snapshot_sha256',snapshot_sha256,
        'created_at',created_at,
        'capability_count',capability_count,
        'skill_count',skill_count,
        'agent_count',agent_count,
        'dependency_count',dependency_count,
        'state',snapshot_state
      )
      from institutional_federation.baseline_snapshots
      where scope='ct.chlom.institutional-capability-runtime'
      order by created_at desc
      limit 1
    )
  );
$$;

create or replace function public.ct_continuity_record_run(
  p_intent text,
  p_requested_by text,
  p_compiled_graph jsonb,
  p_risk_ceiling text,
  p_run_state text default 'compiled'
) returns uuid
language plpgsql
security invoker
set search_path = pg_catalog, extensions, institutional_federation
as $$
declare
  v_id uuid;
  v_hash text;
begin
  v_hash := encode(extensions.digest(convert_to(p_compiled_graph::text,'UTF8'),'sha256'),'hex');
  insert into institutional_federation.continuity_compiler_runs(
    intent,requested_by,compiled_graph,risk_ceiling,run_state,graph_sha256
  ) values (
    p_intent,p_requested_by,p_compiled_graph,p_risk_ceiling,p_run_state,v_hash
  ) returning run_id into v_id;
  return v_id;
end;
$$;

create or replace function public.ct_capability_enqueue(
  p_compiler_run_id uuid,
  p_capability_id text,
  p_assigned_agent_id text,
  p_verifier_agent_id text,
  p_risk_class text,
  p_execution_mode text,
  p_requires_human boolean,
  p_payload jsonb
) returns uuid
language plpgsql
security invoker
set search_path = pg_catalog, extensions, institutional_federation
as $$
declare
  v_id uuid;
  v_hash text;
  v_state text;
begin
  v_hash := encode(extensions.digest(convert_to(coalesce(p_payload,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex');
  v_state := case when p_requires_human then 'hold' else 'queued' end;
  insert into institutional_federation.capability_execution_queue(
    compiler_run_id,capability_id,assigned_agent_id,verifier_agent_id,risk_class,
    execution_mode,queue_state,requires_human,payload,input_sha256
  ) values (
    p_compiler_run_id,p_capability_id,p_assigned_agent_id,p_verifier_agent_id,p_risk_class,
    p_execution_mode,v_state,p_requires_human,coalesce(p_payload,'{}'::jsonb),v_hash
  ) returning queue_id into v_id;

  insert into institutional_federation.capability_execution_receipts(
    queue_id,compiler_run_id,capability_id,agent_id,verifier_agent_id,receipt_state,input_sha256,evidence
  ) values (
    v_id,p_compiler_run_id,p_capability_id,p_assigned_agent_id,p_verifier_agent_id,
    case when p_requires_human then 'hold' else 'dispatched' end,
    v_hash,
    jsonb_build_object('execution_mode',p_execution_mode,'requires_human',p_requires_human)
  );
  return v_id;
end;
$$;

create or replace function public.ct_continuity_agent_self(p_agent_id text)
returns jsonb
language sql
security invoker
set search_path = pg_catalog, extensions, institutional_federation, chlom_runtime
as $$
  select jsonb_build_object(
    'agent',(
      select g.genome
      from institutional_federation.agent_genome_versions g
      where g.agent_id=p_agent_id
      order by g.created_at desc
      limit 1
    ),
    'template',(
      select jsonb_build_object(
        'agent_id',a.agent_id,
        'name',a.canonical_name,
        'class',a.agent_class,
        'autonomy_class',a.autonomy_class,
        'authority_ceiling',a.authority_ceiling,
        'lifecycle_state',a.lifecycle_state,
        'module_scope',a.module_scope,
        'tool_scope',a.tool_scope,
        'vote_eligible',a.vote_eligible,
        'no_self_approval',a.no_self_approval,
        'heartbeat_ttl_seconds',a.heartbeat_ttl_seconds
      )
      from chlom_runtime.agent_templates a
      where a.agent_id=p_agent_id
    ),
    'capabilities',coalesce((
      select jsonb_agg(jsonb_build_object(
        'capability_id',b.capability_id,
        'role',b.binding_role,
        'risk_class',c.risk_class,
        'state',c.capability_state
      ) order by b.binding_role,b.capability_id)
      from institutional_federation.capability_agent_bindings b
      join chlom_runtime.module_capabilities c on c.capability_id=b.capability_id
      where b.agent_id=p_agent_id and b.active
    ),'[]'::jsonb),
    'latest_baseline',(
      select jsonb_build_object(
        'snapshot_id',snapshot_id,
        'sha256',snapshot_sha256,
        'created_at',created_at,
        'state',snapshot_state
      )
      from institutional_federation.baseline_snapshots
      where scope='ct.chlom.institutional-capability-runtime'
      order by created_at desc limit 1
    )
  );
$$;

create or replace function public.ct_continuity_capture_baseline()
returns uuid
language sql
security invoker
set search_path = pg_catalog, extensions, institutional_federation
as $$
  select institutional_federation.capture_capability_baseline('ct.chlom.institutional-capability-runtime');
$$;

revoke all on function institutional_federation.capture_capability_baseline(text) from public, anon, authenticated;
grant execute on function institutional_federation.capture_capability_baseline(text) to service_role;

revoke all on function public.ct_continuity_context() from public, anon, authenticated;
revoke all on function public.ct_continuity_record_run(text,text,jsonb,text,text) from public, anon, authenticated;
revoke all on function public.ct_capability_enqueue(uuid,text,text,text,text,text,boolean,jsonb) from public, anon, authenticated;
revoke all on function public.ct_continuity_agent_self(text) from public, anon, authenticated;
revoke all on function public.ct_continuity_capture_baseline() from public, anon, authenticated;

grant execute on function public.ct_continuity_context() to service_role;
grant execute on function public.ct_continuity_record_run(text,text,jsonb,text,text) to service_role;
grant execute on function public.ct_capability_enqueue(uuid,text,text,text,text,text,boolean,jsonb) to service_role;
grant execute on function public.ct_continuity_agent_self(text) to service_role;
grant execute on function public.ct_continuity_capture_baseline() to service_role;

do $$
begin
  if not exists (select 1 from cron.job where jobname='crownthrive_institutional_baseline_hourly') then
    perform cron.schedule(
      'crownthrive_institutional_baseline_hourly',
      '17 * * * *',
      'select institutional_federation.capture_capability_baseline();'
    );
  end if;
end;
$$;