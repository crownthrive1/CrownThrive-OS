-- PentaReplicate v1
-- Governed MCP/API/site replication fabric. Secret-free public manifests;
-- provider mutations remain behind existing site authority/readback/rollback contracts.

create table if not exists integration_control.penta_replicate_policy_v1 (
  policy_id text primary key,
  contract_version text not null,
  source_inventory_view text not null,
  public_runtime_url text not null,
  cycle_minutes integer not null default 15 check (cycle_minutes between 5 and 1440),
  automatic_authority_ceiling text not null default 'D1' check (automatic_authority_ceiling in ('D0','D1','D2','D3')),
  production_auto_enabled boolean not null default true,
  fail_closed boolean not null default true,
  require_read_after_write boolean not null default true,
  require_rollback boolean not null default true,
  max_attempts integer not null default 3 check (max_attempts between 1 and 10),
  lease_seconds integer not null default 300 check (lease_seconds between 30 and 3600),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_replicate_events_v1 (
  event_id uuid primary key default gen_random_uuid(),
  source_kind text not null,
  source_key text not null,
  source_sha256 text not null,
  risk_class text not null default 'D1' check (risk_class in ('D0','D1','D2','D3')),
  event_state text not null default 'queued' check (event_state in ('queued','processing','applied','held','failed','superseded')),
  payload jsonb not null default '{}'::jsonb,
  processed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(source_kind,source_key,source_sha256)
);

create table if not exists integration_control.penta_replicate_targets_v1 (
  target_id text primary key,
  surface_id text not null unique references integration_control.website_surfaces(surface_id) on delete restrict,
  canonical_url text not null,
  provider_system text not null,
  environment text not null,
  update_mode text not null,
  auto_update_enabled boolean not null default false,
  provider_connection_state text not null,
  health_state text not null,
  eligibility_state text not null default 'PLANNED',
  authority_ceiling text not null default 'D1' check (authority_ceiling in ('D0','D1','D2','D3')),
  last_manifest_sha256 text,
  last_manifest_at timestamptz,
  last_applied_sha256 text,
  last_applied_at timestamptz,
  failure_count integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists integration_control.penta_replicate_manifests_v1 (
  manifest_id uuid primary key default gen_random_uuid(),
  surface_id text not null references integration_control.website_surfaces(surface_id) on delete restrict,
  manifest_sha256 text not null,
  contract_version text not null default 'ct.penta.replicate.manifest.v1',
  manifest jsonb not null,
  generated_at timestamptz not null default now(),
  unique(surface_id,manifest_sha256)
);

create table if not exists integration_control.penta_replicate_jobs_v1 (
  job_id uuid primary key default gen_random_uuid(),
  event_id uuid references integration_control.penta_replicate_events_v1(event_id) on delete set null,
  surface_id text not null references integration_control.website_surfaces(surface_id) on delete restrict,
  operation_key text not null,
  desired_sha256 text not null,
  risk_class text not null check (risk_class in ('D0','D1','D2','D3')),
  job_state text not null default 'queued' check (job_state in ('queued','leased','applied','held','failed','superseded')),
  autonomous_eligible boolean not null default false,
  requires_human_approval boolean not null default false,
  lease_owner text,
  lease_expires_at timestamptz,
  attempt_count integer not null default 0,
  rollback_ref text,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(surface_id,operation_key,desired_sha256)
);

create table if not exists integration_control.penta_replicate_receipts_v1 (
  receipt_id uuid primary key default gen_random_uuid(),
  job_id uuid references integration_control.penta_replicate_jobs_v1(job_id) on delete set null,
  surface_id text not null references integration_control.website_surfaces(surface_id) on delete restrict,
  operation_key text not null,
  decision text not null,
  before_sha256 text,
  after_sha256 text,
  readback_state text not null,
  provider_write boolean not null default false,
  authority_effect text not null default 'none',
  evidence jsonb not null default '{}'::jsonb,
  evidence_sha256 text not null,
  observed_at timestamptz not null default now()
);

create index if not exists penta_replicate_events_state_idx on integration_control.penta_replicate_events_v1(event_state,created_at);
create index if not exists penta_replicate_jobs_state_idx on integration_control.penta_replicate_jobs_v1(job_state,created_at);
create index if not exists penta_replicate_receipts_surface_idx on integration_control.penta_replicate_receipts_v1(surface_id,observed_at desc);

alter table integration_control.penta_replicate_policy_v1 enable row level security;
alter table integration_control.penta_replicate_events_v1 enable row level security;
alter table integration_control.penta_replicate_targets_v1 enable row level security;
alter table integration_control.penta_replicate_manifests_v1 enable row level security;
alter table integration_control.penta_replicate_jobs_v1 enable row level security;
alter table integration_control.penta_replicate_receipts_v1 enable row level security;

insert into integration_control.penta_replicate_policy_v1(
 policy_id,contract_version,source_inventory_view,public_runtime_url,cycle_minutes,
 automatic_authority_ceiling,production_auto_enabled,fail_closed,require_read_after_write,
 require_rollback,max_attempts,lease_seconds,metadata)
values(
 'ct.penta.replicate.policy.v1','ct.penta.replicate.v1','integration_control.api_mcp_reconciled_inventory_v1',
 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate',15,'D1',true,true,true,true,3,300,
 jsonb_build_object('founder_directive','2026-09-04','purpose','continuous MCP/API/site bootstrap reconciliation',
 'native_provider_writes','bounded by existing site authority and rollback contracts'))
on conflict(policy_id) do update set
 contract_version=excluded.contract_version,source_inventory_view=excluded.source_inventory_view,
 public_runtime_url=excluded.public_runtime_url,cycle_minutes=excluded.cycle_minutes,
 automatic_authority_ceiling=excluded.automatic_authority_ceiling,production_auto_enabled=excluded.production_auto_enabled,
 fail_closed=excluded.fail_closed,require_read_after_write=excluded.require_read_after_write,
 require_rollback=excluded.require_rollback,max_attempts=excluded.max_attempts,lease_seconds=excluded.lease_seconds,
 metadata=excluded.metadata,updated_at=now();

insert into chlom_runtime.agent_templates(
 agent_id,parent_agent_id,canonical_name,agent_class,autonomy_class,authority_ceiling,lifecycle_state,
 module_scope,tool_scope,schedule_profile,vote_eligible,self_healing_enabled,no_self_approval,heartbeat_ttl_seconds,metadata)
values(
 'ct.agent.penta-replicate','ct.governance.agent.commercial-sites-relay','PentaReplicate','continuity','A3','D2','active',
 array['commercial-sites','interoperability','penta-wire','chlom'],
 jsonb_build_object('read','all registered MCP/API/site contracts','write','bounded site-update queue only','provider_credentials',false,'money_movement',false),
 'penta_replicate_15m',false,true,true,900,
 jsonb_build_object('contract','ct.penta.replicate.v1','source_of_truth','integration_control.api_mcp_reconciled_inventory_v1','fail_closed',true,'read_after_write_required',true,'rollback_required',true))
on conflict(agent_id) do update set parent_agent_id=excluded.parent_agent_id,canonical_name=excluded.canonical_name,
 agent_class=excluded.agent_class,autonomy_class=excluded.autonomy_class,authority_ceiling=excluded.authority_ceiling,
 lifecycle_state=excluded.lifecycle_state,module_scope=excluded.module_scope,tool_scope=excluded.tool_scope,
 schedule_profile=excluded.schedule_profile,self_healing_enabled=excluded.self_healing_enabled,
 no_self_approval=excluded.no_self_approval,heartbeat_ttl_seconds=excluded.heartbeat_ttl_seconds,
 metadata=excluded.metadata,updated_at=now();

insert into integration_control.services(
 service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,write_gate,monthly_request_limit,timezone,metadata)
values(
 'penta_replicate','PentaReplicate','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate',
 'https://github.com/crownthrive1/CrownThrive-OS/tree/main/supabase/functions/penta-replicate',
 'public_read_only_plus_service_role_admin','none:public','configured','configured',true,null,'UTC',
 jsonb_build_object('contract','ct.penta.replicate.v1','agent_id','ct.agent.penta-replicate','public_reads',true,'provider_write_direct',false,'secret_exposure',false,'deployment_state','staged'))
on conflict(service_id) do update set display_name=excluded.display_name,base_url=excluded.base_url,docs_url=excluded.docs_url,
 auth_scheme=excluded.auth_scheme,credential_ref=excluded.credential_ref,credential_state=excluded.credential_state,
 integration_state=excluded.integration_state,write_gate=excluded.write_gate,
 metadata=coalesce(integration_control.services.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

insert into integration_control.mcp_tools(tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval,input_schema,output_schema,notes)
values
 ('penta.replicate.status','penta_replicate','status.read','D0',true,false,'{"type":"object","properties":{},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Secret-free PentaReplicate fleet status.'),
 ('penta.replicate.manifest','penta_replicate','manifest.read','D0',true,false,'{"type":"object","properties":{"surface_id":{"type":"string"}},"required":["surface_id"],"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Secret-free per-surface MCP/API/bootstrap manifest.'),
 ('penta.replicate.targets','penta_replicate','targets.read','D0',true,false,'{"type":"object","properties":{"limit":{"type":"integer","minimum":1,"maximum":100}},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Replication targets and eligibility without provider credentials.'),
 ('penta.replicate.drift','penta_replicate','drift.read','D1',true,false,'{"type":"object","properties":{"surface_id":{"type":"string"}},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Manifest/bootstrap drift read; no provider mutation.')
on conflict(tool_name) do update set service_id=excluded.service_id,operation_key=excluded.operation_key,risk_class=excluded.risk_class,
 enabled=excluded.enabled,requires_human_approval=excluded.requires_human_approval,input_schema=excluded.input_schema,
 output_schema=excluded.output_schema,notes=excluded.notes,updated_at=now();

insert into chlom_runtime.mcp_tool_exposure(tool_name,server_id,enabled,exposure_state,minimum_authority)
values
 ('penta.replicate.status','penta-replicate',true,'staged','D0'),
 ('penta.replicate.manifest','penta-replicate',true,'staged','D0'),
 ('penta.replicate.targets','penta-replicate',true,'staged','D0'),
 ('penta.replicate.drift','penta-replicate',true,'staged','D1')
on conflict(tool_name) do update set server_id=excluded.server_id,enabled=excluded.enabled,exposure_state=excluded.exposure_state,
 minimum_authority=excluded.minimum_authority,updated_at=now();

insert into integration_control.endpoint_catalog(endpoint_id,service_id,operation_key,http_method,path_template,risk_class,mutation,source_state,enabled,mcp_candidate,notes)
values
 ('ct.endpoint.penta-replicate.health.v1','penta_replicate','health.read','GET','/functions/v1/penta-replicate/health','D0',false,'documented',true,false,'Public secret-free health endpoint.'),
 ('ct.endpoint.penta-replicate.manifest.v1','penta_replicate','manifest.read','GET','/functions/v1/penta-replicate/manifest','D0',false,'documented',true,true,'Per-surface MCP/API/bootstrap manifest.'),
 ('ct.endpoint.penta-replicate.bootstrap.v1','penta_replicate','bootstrap.read','GET','/functions/v1/penta-replicate/bootstrap.js','D0',false,'documented',true,false,'Stable public bootstrap runtime; no credentials.'),
 ('ct.endpoint.penta-replicate.mcp.v1','penta_replicate','mcp.rpc','POST','/functions/v1/penta-replicate/mcp','D0',false,'documented',true,false,'Read-only MCP JSON-RPC endpoint.')
on conflict(endpoint_id) do update set service_id=excluded.service_id,operation_key=excluded.operation_key,http_method=excluded.http_method,
 path_template=excluded.path_template,risk_class=excluded.risk_class,mutation=excluded.mutation,source_state=excluded.source_state,
 enabled=excluded.enabled,mcp_candidate=excluded.mcp_candidate,notes=excluded.notes,updated_at=now();

create or replace function integration_control.penta_replicate_manifest_v1(p_surface_id text)
returns jsonb language plpgsql stable security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime','extensions'
as $$
declare v_surface jsonb; v_mcp jsonb; v_public_api jsonb; v_public_adapters jsonb; v_bindings jsonb; v_base jsonb; v_sha text;
begin
 select jsonb_build_object('surface_id',w.surface_id,'display_name',w.display_name,'platform_id',w.platform_id,'provider_system',w.provider_system,
 'environment',w.environment,'canonical_url',w.canonical_url,'provider_connection_state',w.provider_connection_state,'health_state',w.health_state,
 'update_mode',w.update_mode,'auto_update_enabled',w.auto_update_enabled) into v_surface
 from integration_control.website_surfaces w where w.surface_id=p_surface_id;
 if v_surface is null then raise exception 'penta_replicate_surface_not_found'; end if;
 select coalesce(jsonb_agg(jsonb_build_object('tool_name',i.subject_key,'service_id',i.service_id,'operation_key',i.operation_key,'risk_class',i.risk_class,'server_id',i.server_id) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_mcp from integration_control.api_mcp_reconciled_inventory_v1 i where i.inventory_kind='MCP_TOOL' and i.enabled and i.exposure_state='production' and i.risk_class in ('D0','D1');
 select coalesce(jsonb_agg(jsonb_build_object('public_api_id',i.subject_key,'service_id',i.service_id,'operation_key',i.operation_key,'risk_class',i.risk_class) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_public_api from integration_control.api_mcp_reconciled_inventory_v1 i where i.inventory_kind='PUBLIC_API' and i.enabled;
 select coalesce(jsonb_agg(jsonb_build_object('contract',i.subject_key,'service_id',i.service_id,'adapter_kind',i.interface_kind,'transport_ref',i.transport_ref) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_public_adapters from integration_control.api_mcp_reconciled_inventory_v1 i where i.inventory_kind='READ_ADAPTER' and i.enabled and i.public_projection is true;
 select coalesce(jsonb_agg(jsonb_build_object('binding_kind',b.binding_kind,'target_id',b.target_id,'target_version',b.target_version,'endpoint_ref',b.endpoint_ref,'install_mode',b.install_mode,'authority_ceiling',b.authority_ceiling) order by b.binding_kind,b.target_id),'[]'::jsonb)
 into v_bindings from integration_control.site_mesh_bindings b where b.surface_id=p_surface_id and b.binding_state='active';
 v_base:=jsonb_build_object('contract','ct.penta.replicate.manifest.v1','generated_at',clock_timestamp(),'surface',v_surface,'mcp_tools',v_mcp,
 'public_apis',v_public_api,'public_read_adapters',v_public_adapters,'site_bindings',v_bindings,
 'runtime',jsonb_build_object('base_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate',
 'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/manifest?surface_id='||p_surface_id,
 'bootstrap_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/bootstrap.js?surface_id='||p_surface_id,
 'mcp_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/mcp'),
 'controls',jsonb_build_object('provider_credentials_exposed',false,'provider_write',false,'money_movement',false,'read_after_write_required',true,'rollback_required',true));
 v_sha:=encode(extensions.digest(convert_to(v_base::text,'UTF8'),'sha256'),'hex'); return v_base||jsonb_build_object('manifest_sha256',v_sha);
end $$;

create or replace function integration_control.penta_replicate_refresh_targets_v1()
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control'
as $$ declare v_count integer; begin
 insert into integration_control.penta_replicate_targets_v1(target_id,surface_id,canonical_url,provider_system,environment,update_mode,auto_update_enabled,provider_connection_state,health_state,eligibility_state,authority_ceiling,metadata)
 select 'ct.replicate.target.'||w.surface_id,w.surface_id,w.canonical_url,w.provider_system,w.environment,w.update_mode,w.auto_update_enabled,w.provider_connection_state,w.health_state,
 case when w.provider_connection_state not in ('verified','documented') then 'HOLD_PROVIDER' when w.health_state<>'healthy' then 'HOLD_HEALTH'
 when w.update_mode='bounded_auto' and w.auto_update_enabled then 'AUTO_BOOTSTRAP' else 'DYNAMIC_MANIFEST_ONLY' end,
 case when exists(select 1 from integration_control.site_mesh_bindings b where b.surface_id=w.surface_id and b.binding_state='active' and b.authority_ceiling in ('D2','D3')) then 'D2' else 'D1' end,
 jsonb_build_object('manifest_runtime','dynamic','native_site_write_required_for_manifest',false)
 from integration_control.website_surfaces w where w.environment='production'
 on conflict(surface_id) do update set canonical_url=excluded.canonical_url,provider_system=excluded.provider_system,environment=excluded.environment,
 update_mode=excluded.update_mode,auto_update_enabled=excluded.auto_update_enabled,provider_connection_state=excluded.provider_connection_state,
 health_state=excluded.health_state,eligibility_state=excluded.eligibility_state,authority_ceiling=excluded.authority_ceiling,
 metadata=coalesce(integration_control.penta_replicate_targets_v1.metadata,'{}'::jsonb)||excluded.metadata,updated_at=clock_timestamp();
 get diagnostics v_count=row_count; return jsonb_build_object('state','PASS','targets_refreshed',v_count,'observed_at',clock_timestamp());
end $$;

create or replace function integration_control.penta_replicate_status_v1()
returns jsonb language sql stable security definer set search_path to 'pg_catalog','integration_control','chlom_runtime'
as $$ select jsonb_build_object('state','PASS','contract','ct.penta.replicate.v1','agent_id','ct.agent.penta-replicate',
 'targets',(select count(*) from integration_control.penta_replicate_targets_v1),
 'auto_bootstrap_targets',(select count(*) from integration_control.penta_replicate_targets_v1 where eligibility_state='AUTO_BOOTSTRAP'),
 'dynamic_manifest_targets',(select count(*) from integration_control.penta_replicate_targets_v1 where eligibility_state='DYNAMIC_MANIFEST_ONLY'),
 'held_targets',(select count(*) from integration_control.penta_replicate_targets_v1 where eligibility_state like 'HOLD_%'),
 'manifests',(select count(*) from integration_control.penta_replicate_manifests_v1),
 'queued_events',(select count(*) from integration_control.penta_replicate_events_v1 where event_state='queued'),
 'queued_jobs',(select count(*) from integration_control.penta_replicate_jobs_v1 where job_state='queued'),
 'bootstrap_queue',(select count(*) from integration_control.site_update_queue where trigger_key='penta-replicate-bootstrap-v1' and state in ('planned','approved','executing')),
 'mcp_inventory',(select count(*) from integration_control.mcp_tools),'endpoint_inventory',(select count(*) from integration_control.endpoint_catalog),
 'public_api_inventory',(select count(*) from integration_control.thrivebase_public_api_allowlist_v1),'provider_credentials_exposed',false,'provider_write_direct',false,'observed_at',clock_timestamp()) $$;

create or replace function integration_control.penta_replicate_capture_source_change_v1()
returns trigger language plpgsql security definer set search_path to 'pg_catalog','integration_control','extensions'
as $$ declare v_row jsonb:=to_jsonb(new); v_key text; v_kind text:=tg_table_schema||'.'||tg_table_name; v_fp jsonb; v_sha text; v_risk text; begin
 v_key:=case tg_table_name when 'mcp_tools' then coalesce(v_row->>'tool_name','unknown') when 'mcp_tool_exposure' then coalesce(v_row->>'tool_name','unknown')
 when 'endpoint_catalog' then coalesce(v_row->>'endpoint_id','unknown') when 'thrivebase_public_api_allowlist_v1' then coalesce(v_row->>'public_api_id','unknown')
 when 'website_surfaces' then coalesce(v_row->>'surface_id','unknown') when 'site_mesh_bindings' then coalesce(v_row->>'binding_id','unknown')
 when 'penta_wire_read_adapters_v1' then coalesce(v_row->>'service_id','unknown')||':'||coalesce(v_row->>'exact_contract','unknown')
 else coalesce(v_row->>'id',v_row->>'service_id','unknown') end;
 v_risk:=case when coalesce(v_row->>'risk_class','') in ('D0','D1','D2','D3') then v_row->>'risk_class' else 'D1' end;
 v_fp:=jsonb_build_object('source_kind',v_kind,'source_key',v_key,'operation',tg_op,'updated_at',coalesce(v_row->>'updated_at',clock_timestamp()::text),
 'enabled',v_row->>'enabled','state',coalesce(v_row->>'lifecycle_state',v_row->>'binding_state',v_row->>'source_state',v_row->>'exposure_state'));
 v_sha:=encode(extensions.digest(convert_to(v_fp::text,'UTF8'),'sha256'),'hex');
 insert into integration_control.penta_replicate_events_v1(source_kind,source_key,source_sha256,risk_class,payload)
 values(v_kind,v_key,v_sha,v_risk,v_fp) on conflict(source_kind,source_key,source_sha256) do nothing; return new; end $$;

-- Exact cycle is intentionally queue-first: dynamic manifest publication is D1 and provider-write-free;
-- native bootstrap installation is a D2 site_update_queue operation and uses the existing site provider authority/readback/rollback fabric.
create or replace function integration_control.penta_replicate_cycle_v1(p_force boolean default false)
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control','extensions'
as $$ declare r record; v_manifest jsonb; v_sha text; v_before text; v_job uuid; v_updates int:=0; v_boot int:=0; v_evidence jsonb; begin
 perform integration_control.penta_replicate_refresh_targets_v1();
 for r in select * from integration_control.penta_replicate_targets_v1 order by surface_id loop
  v_manifest:=integration_control.penta_replicate_manifest_v1(r.surface_id); v_sha:=v_manifest->>'manifest_sha256'; v_before:=r.last_applied_sha256;
  insert into integration_control.penta_replicate_manifests_v1(surface_id,manifest_sha256,manifest) values(r.surface_id,v_sha,v_manifest) on conflict(surface_id,manifest_sha256) do nothing;
  update integration_control.penta_replicate_targets_v1 set last_manifest_sha256=v_sha,last_manifest_at=clock_timestamp(),updated_at=clock_timestamp() where surface_id=r.surface_id;
  if p_force or v_before is distinct from v_sha then
   insert into integration_control.penta_replicate_jobs_v1(surface_id,operation_key,desired_sha256,risk_class,job_state,autonomous_eligible,requires_human_approval,rollback_ref,evidence)
   values(r.surface_id,'manifest.publish',v_sha,'D1','applied',true,false,'penta-replicate://manifest/'||coalesce(v_before,'none'),jsonb_build_object('delivery_mode','dynamic_runtime','provider_write',false,'authority_effect','none'))
   on conflict(surface_id,operation_key,desired_sha256) do update set job_state='applied',evidence=excluded.evidence,updated_at=clock_timestamp() returning job_id into v_job;
   v_evidence:=jsonb_build_object('contract','ct.penta.replicate.manifest.v1','surface_id',r.surface_id,'manifest_sha256',v_sha,'delivery_mode','dynamic_runtime','provider_write',false,'authority_effect','none');
   insert into integration_control.penta_replicate_receipts_v1(job_id,surface_id,operation_key,decision,before_sha256,after_sha256,readback_state,provider_write,authority_effect,evidence,evidence_sha256)
   values(v_job,r.surface_id,'manifest.publish','PASS_DYNAMIC_MANIFEST',v_before,v_sha,'DATABASE_READBACK',false,'none',v_evidence,encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex'));
   update integration_control.penta_replicate_targets_v1 set last_applied_sha256=v_sha,last_applied_at=clock_timestamp(),failure_count=0,updated_at=clock_timestamp() where surface_id=r.surface_id; v_updates:=v_updates+1;
  end if;
 end loop;
 insert into integration_control.site_update_queue(surface_id,trigger_key,operation_key,risk_class,requested_change,state,autonomous_eligible,requires_human_approval,rollback_ref,metadata)
 select t.surface_id,'penta-replicate-bootstrap-v1','site.replicate.bootstrap.install','D2',
 jsonb_build_object('contract','ct.penta.replicate.bootstrap.v1','script_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/bootstrap.js?surface_id='||t.surface_id,
 'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/manifest?surface_id='||t.surface_id,'script_id','ct-penta-replicate-v1','behavior','idempotent dynamic loader; no credentials; no money movement'),
 case when t.eligibility_state='AUTO_BOOTSTRAP' then 'approved' else 'planned' end,t.eligibility_state='AUTO_BOOTSTRAP',t.eligibility_state<>'AUTO_BOOTSTRAP',
 'penta-replicate://bootstrap/v1/remove',jsonb_build_object('source','penta-replicate','founder_explicit_authority','2026-09-04','provider_write_requires_existing_site_adapter',true,'read_after_write_required',true,'rollback_required',true)
 from integration_control.penta_replicate_targets_v1 t where not exists(select 1 from integration_control.site_update_queue q where q.surface_id=t.surface_id and q.trigger_key='penta-replicate-bootstrap-v1' and q.state in ('planned','approved','executing','completed'));
 get diagnostics v_boot=row_count; update integration_control.penta_replicate_events_v1 set event_state='applied',processed_at=clock_timestamp() where event_state='queued';
 return jsonb_build_object('state','PASS','contract','ct.penta.replicate.cycle.v1','manifest_updates',v_updates,'bootstrap_updates_created',v_boot,'force',p_force,'status',integration_control.penta_replicate_status_v1(),'observed_at',clock_timestamp()); end $$;

drop trigger if exists trg_penta_replicate_mcp_tools on integration_control.mcp_tools;
create trigger trg_penta_replicate_mcp_tools after insert or update on integration_control.mcp_tools for each row execute function integration_control.penta_replicate_capture_source_change_v1();
drop trigger if exists trg_penta_replicate_mcp_exposure on chlom_runtime.mcp_tool_exposure;
create trigger trg_penta_replicate_mcp_exposure after insert or update on chlom_runtime.mcp_tool_exposure for each row execute function integration_control.penta_replicate_capture_source_change_v1();
drop trigger if exists trg_penta_replicate_endpoint_catalog on integration_control.endpoint_catalog;
create trigger trg_penta_replicate_endpoint_catalog after insert or update on integration_control.endpoint_catalog for each row execute function integration_control.penta_replicate_capture_source_change_v1();
drop trigger if exists trg_penta_replicate_public_api on integration_control.thrivebase_public_api_allowlist_v1;
create trigger trg_penta_replicate_public_api after insert or update on integration_control.thrivebase_public_api_allowlist_v1 for each row execute function integration_control.penta_replicate_capture_source_change_v1();
drop trigger if exists trg_penta_replicate_surfaces on integration_control.website_surfaces;
create trigger trg_penta_replicate_surfaces after insert or update on integration_control.website_surfaces for each row execute function integration_control.penta_replicate_capture_source_change_v1();
drop trigger if exists trg_penta_replicate_site_bindings on integration_control.site_mesh_bindings;
create trigger trg_penta_replicate_site_bindings after insert or update on integration_control.site_mesh_bindings for each row execute function integration_control.penta_replicate_capture_source_change_v1();
drop trigger if exists trg_penta_replicate_read_adapters on integration_control.penta_wire_read_adapters_v1;
create trigger trg_penta_replicate_read_adapters after insert or update on integration_control.penta_wire_read_adapters_v1 for each row execute function integration_control.penta_replicate_capture_source_change_v1();

insert into integration_control.site_mesh_bindings(binding_id,surface_id,binding_kind,target_id,target_version,endpoint_ref,install_mode,binding_state,authority_ceiling,native_site_write_required,read_after_write_required,rollback_required,founder_superadmin_required,metadata)
select 'ct.bind.penta-replicate.service.'||substr(md5(w.surface_id),1,16),w.surface_id,'service','penta-replicate','1.0.0','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate','remote_runtime','ready','D1',false,true,true,false,jsonb_build_object('contract','ct.penta.replicate.v1','secret_free',true,'dynamic_manifest',true)
from integration_control.website_surfaces w where w.environment='production'
on conflict(surface_id,binding_kind,target_id) do update set target_version=excluded.target_version,endpoint_ref=excluded.endpoint_ref,install_mode=excluded.install_mode,binding_state=excluded.binding_state,authority_ceiling=excluded.authority_ceiling,native_site_write_required=excluded.native_site_write_required,read_after_write_required=excluded.read_after_write_required,rollback_required=excluded.rollback_required,metadata=coalesce(integration_control.site_mesh_bindings.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

insert into integration_control.site_mesh_bindings(binding_id,surface_id,binding_kind,target_id,target_version,endpoint_ref,install_mode,binding_state,authority_ceiling,native_site_write_required,read_after_write_required,rollback_required,founder_superadmin_required,metadata)
select 'ct.bind.penta-replicate.mcp.'||substr(md5(w.surface_id),1,16),w.surface_id,'mcp','ct.mcp.penta-replicate','1.0.0','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/mcp','remote_runtime','ready','D1',false,true,true,false,jsonb_build_object('contract','ct.penta.replicate.mcp.v1','read_only',true)
from integration_control.website_surfaces w where w.environment='production'
on conflict(surface_id,binding_kind,target_id) do update set target_version=excluded.target_version,endpoint_ref=excluded.endpoint_ref,install_mode=excluded.install_mode,binding_state=excluded.binding_state,authority_ceiling=excluded.authority_ceiling,native_site_write_required=excluded.native_site_write_required,read_after_write_required=excluded.read_after_write_required,rollback_required=excluded.rollback_required,metadata=coalesce(integration_control.site_mesh_bindings.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

insert into integration_control.site_mesh_bindings(binding_id,surface_id,binding_kind,target_id,target_version,endpoint_ref,install_mode,binding_state,authority_ceiling,native_site_write_required,read_after_write_required,rollback_required,founder_superadmin_required,metadata)
select 'ct.bind.penta-replicate.feed.'||substr(md5(w.surface_id),1,16),w.surface_id,'feed','ct.feed.penta-replicate.v1','1.0.0','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate/manifest?surface_id='||w.surface_id,'dynamic_feed','ready','D1',false,true,true,false,jsonb_build_object('contract','ct.penta.replicate.manifest.v1','refresh_mode','dynamic')
from integration_control.website_surfaces w where w.environment='production'
on conflict(surface_id,binding_kind,target_id) do update set target_version=excluded.target_version,endpoint_ref=excluded.endpoint_ref,install_mode=excluded.install_mode,binding_state=excluded.binding_state,authority_ceiling=excluded.authority_ceiling,native_site_write_required=excluded.native_site_write_required,read_after_write_required=excluded.read_after_write_required,rollback_required=excluded.rollback_required,metadata=coalesce(integration_control.site_mesh_bindings.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

select cron.unschedule(jobid) from cron.job where jobname='ct-penta-replicate-v1';
select cron.schedule('ct-penta-replicate-v1','14,29,44,59 * * * *',$cron$select integration_control.penta_replicate_cycle_v1(false);$cron$);
