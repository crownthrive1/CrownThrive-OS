-- CrownThrive Autonomous Software Factory v4 breadth migration
-- Production application was performed through ThriveBase migrations before this source-control snapshot.

create table if not exists public.ct_factory_component_families (
  kind text primary key,
  compiler_version text not null,
  output_class text not null,
  risk_class text not null default 'D1',
  enabled boolean not null default true,
  deterministic boolean not null default true,
  description text not null,
  contract jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.ct_factory_component_families enable row level security;
revoke all on public.ct_factory_component_families from anon, authenticated;

create table if not exists public.ct_factory_surface_bindings (
  surface_id text primary key,
  project_id uuid not null references public.ct_factory_projects(id) on delete cascade,
  target_id uuid references public.ct_factory_deployment_targets(id) on delete set null,
  platform_id text,
  provider_system text not null,
  adapter_key text not null,
  deployment_policy text not null check (deployment_policy in ('auto','manual','observe','hold_unbound')),
  required_for_release boolean not null default false,
  binding_state text not null default 'bound',
  certification_state text not null default 'unverified',
  config jsonb not null default '{}'::jsonb,
  synced_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ct_factory_surface_bindings_project_idx on public.ct_factory_surface_bindings(project_id,provider_system,deployment_policy);
alter table public.ct_factory_surface_bindings enable row level security;
revoke all on public.ct_factory_surface_bindings from anon, authenticated;

insert into public.ct_factory_component_families(kind,compiler_version,output_class,risk_class,description,contract) values
('typescript_module','ct-factory-compiler.v4','source','D1','Typed TypeScript module from structured values','{"arbitrary_code":false}'::jsonb),
('edge_api','ct-factory-compiler.v4','edge_function','D1','Bounded GET/health Edge API source','{"arbitrary_network":false}'::jsonb),
('static_site','ct-factory-compiler.v4','web','D1','Static HTML page','{"inline_script":false}'::jsonb),
('sql_table','ct-factory-compiler.v4','database','D2','Bounded table DDL from identifiers and allowlisted types','{"arbitrary_sql":false}'::jsonb),
('postgres_view','ct-factory-compiler.v4','database','D2','Bounded projection view over one table','{"arbitrary_sql":false}'::jsonb),
('deno_test','ct-factory-compiler.v4','test','D1','Deno source-existence test','{}'::jsonb),
('json_document','ct-factory-compiler.v4','config','D1','Canonical JSON document','{}'::jsonb),
('openapi_spec','ct-factory-compiler.v4','api_contract','D1','OpenAPI 3.1 contract from structured path definitions','{"methods":["get","post","put","patch","delete"]}'::jsonb),
('mcp_tool_manifest','ct-factory-compiler.v4','mcp_contract','D1','MCP tool manifest with JSON-schema inputs','{}'::jsonb),
('github_workflow','ct-factory-compiler.v4','workflow','D2','GitHub Actions workflow from allowlisted step types only','{"arbitrary_run":false}'::jsonb),
('mdx_document','ct-factory-compiler.v4','documentation','D0','MDX documentation page','{}'::jsonb),
('service_worker','ct-factory-compiler.v4','web_runtime','D1','Bounded cache-first service worker for explicit assets','{"external_fetch":false}'::jsonb),
('env_contract','ct-factory-compiler.v4','runtime_contract','D1','Environment-variable contract without secret values','{"secret_values":false}'::jsonb),
('event_contract','ct-factory-compiler.v4','event_contract','D1','Versioned event JSON-schema contract','{}'::jsonb),
('policy_manifest','ct-factory-compiler.v4','governance','D1','Governance and authority manifest','{}'::jsonb),
('route_manifest','ct-factory-compiler.v4','routing','D1','Application route manifest','{}'::jsonb),
('asset_manifest','ct-factory-compiler.v4','asset_registry','D1','Generated-asset registry manifest','{}'::jsonb)
on conflict(kind) do update set compiler_version=excluded.compiler_version,output_class=excluded.output_class,risk_class=excluded.risk_class,enabled=true,description=excluded.description,contract=excluded.contract,updated_at=now();

alter table public.ct_factory_deployments drop constraint if exists ct_factory_deployments_state_check;
alter table public.ct_factory_deployments add constraint ct_factory_deployments_state_check check (state = any (array['requested'::text,'implemented'::text,'failed'::text,'rolled_back'::text,'skipped'::text,'hold'::text]));

create or replace function public.ct_factory_required_deployments_satisfied(p_run_id uuid)
returns boolean language sql stable security definer set search_path=public,pg_temp as $$
  with ctx as (
    select r.project_id from public.ct_factory_build_runs b join public.ct_factory_build_requests r on r.id=b.build_request_id where b.id=p_run_id
  ), required_targets as (
    select t.id from public.ct_factory_deployment_targets t join ctx on ctx.project_id=t.project_id
    where t.enabled and case when t.config ? 'required_for_release' then coalesce((t.config->>'required_for_release')::boolean,false) else t.target_type <> 'website_surface' end
  )
  select not exists (
    select 1 from required_targets rt left join public.ct_factory_deployments d on d.build_run_id=p_run_id and d.target_id=rt.id
    where coalesce(d.state,'missing') <> 'implemented'
  );
$$;
revoke all on function public.ct_factory_required_deployments_satisfied(uuid) from public,anon,authenticated;
grant execute on function public.ct_factory_required_deployments_satisfied(uuid) to service_role;

-- Surface synchronization is intentionally registry-driven. Provider mutation is never inferred
-- from a URL or a documented account: only certified adapter bindings may be release-required.
create or replace function public.ct_factory_sync_surface_bindings(p_project_key text default 'crownthrive-os-v2-factory')
returns jsonb language plpgsql security definer set search_path=public,integration_control,pg_temp as $$
declare v_project_id uuid; r record; v_adapter text; v_policy text; v_required boolean; v_cert text; v_target_id uuid; v_count integer:=0; v_auto integer:=0; v_manual integer:=0; v_observe integer:=0; v_hold integer:=0;
begin
  select id into v_project_id from public.ct_factory_projects where project_key=p_project_key;
  if v_project_id is null then raise exception 'factory project not found: %',p_project_key; end if;
  for r in select surface_id,platform_id,display_name,provider_system,provider_project_ref,canonical_url,repository_ref,provider_connection_state,health_state,update_mode,auto_update_enabled from integration_control.website_surfaces where environment='production' order by surface_id loop
    if r.provider_system='Sites' and r.provider_connection_state='verified' then
      v_adapter:='ct.adapter.sites.surface.v2'; v_cert:='verified';
      if r.auto_update_enabled and r.update_mode='bounded_auto' then v_policy:='auto'; v_required:=true; v_auto:=v_auto+1;
      elsif r.update_mode='observe_only' then v_policy:='observe'; v_required:=false; v_observe:=v_observe+1;
      else v_policy:='manual'; v_required:=false; v_manual:=v_manual+1; end if;
    else
      v_adapter:='ct.adapter.external.surface.v1'; v_cert:=case when r.provider_connection_state='verified' then 'connection_verified_write_unverified' else coalesce(r.provider_connection_state,'unverified') end;
      if r.update_mode='observe_only' or not coalesce(r.auto_update_enabled,false) then v_policy:='observe'; v_observe:=v_observe+1; else v_policy:='hold_unbound'; v_hold:=v_hold+1; end if;
      v_required:=false;
    end if;
    insert into public.ct_factory_deployment_targets(project_id,target_key,target_type,endpoint,config,enabled,production)
    values(v_project_id,'surface:'||r.surface_id,'website_surface',r.canonical_url,jsonb_build_object('adapter_key',v_adapter,'surface_id',r.surface_id,'platform_id',r.platform_id,'display_name',r.display_name,'provider_system',r.provider_system,'provider_project_ref',r.provider_project_ref,'repository_ref',r.repository_ref,'deployment_policy',v_policy,'required_for_release',v_required,'connection_state',r.provider_connection_state,'health_state',r.health_state,'source','integration_control.website_surfaces'),true,true)
    on conflict(project_id,target_key) do update set endpoint=excluded.endpoint,config=excluded.config,enabled=true,production=true returning id into v_target_id;
    insert into public.ct_factory_surface_bindings(surface_id,project_id,target_id,platform_id,provider_system,adapter_key,deployment_policy,required_for_release,binding_state,certification_state,config,synced_at,updated_at)
    values(r.surface_id,v_project_id,v_target_id,r.platform_id,r.provider_system,v_adapter,v_policy,v_required,'bound',v_cert,jsonb_build_object('canonical_url',r.canonical_url,'provider_project_ref',r.provider_project_ref,'repository_ref',r.repository_ref,'update_mode',r.update_mode,'auto_update_enabled',r.auto_update_enabled,'health_state',r.health_state),now(),now())
    on conflict(surface_id) do update set project_id=excluded.project_id,target_id=excluded.target_id,platform_id=excluded.platform_id,provider_system=excluded.provider_system,adapter_key=excluded.adapter_key,deployment_policy=excluded.deployment_policy,required_for_release=excluded.required_for_release,binding_state=excluded.binding_state,certification_state=excluded.certification_state,config=excluded.config,synced_at=now(),updated_at=now();
    v_count:=v_count+1;
  end loop;
  return jsonb_build_object('project_id',v_project_id,'bound_surfaces',v_count,'auto',v_auto,'manual',v_manual,'observe',v_observe,'hold_unbound',v_hold,'synced_at',now());
end;$$;
revoke all on function public.ct_factory_sync_surface_bindings(text) from public,anon,authenticated;
grant execute on function public.ct_factory_sync_surface_bindings(text) to service_role;

-- Production scheduler installed as:
-- ct-factory-surface-binding-sync-v4 | */15 * * * * | select public.ct_factory_sync_surface_bindings('crownthrive-os-v2-factory');
