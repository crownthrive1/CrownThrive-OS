create table if not exists integration_control.penta_replicate_public_mcp_servers_v1 (
  server_id text primary key,
  enabled boolean not null default true,
  rationale text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table integration_control.penta_replicate_public_mcp_servers_v1 enable row level security;

insert into integration_control.penta_replicate_public_mcp_servers_v1(server_id,enabled,rationale,metadata)
values
 ('pentaads-public-mcp',true,'Explicit public PentaAds MCP; read-only public tool surface.',jsonb_build_object('access_class','public')),
 ('ct.mcp.us-gov-data',true,'Public government-data read fabric.',jsonb_build_object('access_class','public')),
 ('ct.mcp.public-provider-fabric',true,'Explicit public provider read fabric.',jsonb_build_object('access_class','public')),
 ('ct.mcp.api-marketplace-public',true,'Public API marketplace discovery MCP.',jsonb_build_object('access_class','public')),
 ('penta-replicate',true,'PentaReplicate public read-only manifest/status MCP.',jsonb_build_object('access_class','public'))
on conflict(server_id) do update set enabled=excluded.enabled,rationale=excluded.rationale,metadata=excluded.metadata,updated_at=now();

update integration_control.services
set docs_url='https://github.com/crownthrive1/CrownThrive-OS/tree/main/supabase/functions/penta-replicate-v1',updated_at=now()
where service_id='penta_replicate';

create or replace function integration_control.penta_replicate_manifest_v1(p_surface_id text)
returns jsonb language plpgsql stable security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime','extensions'
as $$
declare v_surface jsonb; v_mcp jsonb; v_public_api jsonb; v_public_adapters jsonb; v_bindings jsonb; v_base jsonb; v_sha text;
begin
 select jsonb_build_object('surface_id',w.surface_id,'display_name',w.display_name,'platform_id',w.platform_id,
 'environment',w.environment,'canonical_url',w.canonical_url,'health_state',w.health_state)
 into v_surface from integration_control.website_surfaces w where w.surface_id=p_surface_id and w.environment='production';
 if v_surface is null then raise exception 'penta_replicate_public_surface_not_found'; end if;

 select coalesce(jsonb_agg(jsonb_build_object('tool_name',i.subject_key,'service_id',i.service_id,'operation_key',i.operation_key,
 'risk_class',i.risk_class,'server_id',i.server_id) order by i.server_id,i.service_id,i.subject_key),'[]'::jsonb)
 into v_mcp from integration_control.api_mcp_reconciled_inventory_v1 i
 join integration_control.penta_replicate_public_mcp_servers_v1 s on s.server_id=i.server_id and s.enabled
 where i.inventory_kind='MCP_TOOL' and i.enabled and i.exposure_state='production' and i.risk_class in ('D0','D1');

 select coalesce(jsonb_agg(jsonb_build_object('public_api_id',i.subject_key,'service_id',i.service_id,
 'operation_key',i.operation_key,'risk_class',i.risk_class) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_public_api from integration_control.api_mcp_reconciled_inventory_v1 i
 where i.inventory_kind='PUBLIC_API' and i.enabled;

 select coalesce(jsonb_agg(jsonb_build_object('contract',i.subject_key,'service_id',i.service_id,'transport_ref',i.transport_ref)
 order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_public_adapters from integration_control.api_mcp_reconciled_inventory_v1 i
 where i.inventory_kind='READ_ADAPTER' and i.enabled and i.public_projection is true
 and i.interface_kind='PUBLIC_HTTP' and i.transport_ref like 'https://%';

 select coalesce(jsonb_agg(jsonb_build_object('binding_kind',b.binding_kind,'target_id',b.target_id,'target_version',b.target_version,
 'endpoint_ref',b.endpoint_ref,'install_mode',b.install_mode,'authority_ceiling',b.authority_ceiling)
 order by b.binding_kind,b.target_id),'[]'::jsonb)
 into v_bindings from integration_control.site_mesh_bindings b
 where b.surface_id=p_surface_id and b.binding_state='active'
 and b.target_id in ('penta-replicate','ct.mcp.penta-replicate','ct.feed.penta-replicate.v1')
 and b.authority_ceiling in ('D0','D1');

 v_base:=jsonb_build_object('contract','ct.penta.replicate.manifest.v1','manifest_class','PUBLIC_SAFE','generated_at',clock_timestamp(),
 'surface',v_surface,'mcp_tools',v_mcp,'public_apis',v_public_api,'public_read_adapters',v_public_adapters,'site_bindings',v_bindings,
 'runtime',jsonb_build_object('base_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1',
 'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=manifest&surface_id='||p_surface_id,
 'bootstrap_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=bootstrap&surface_id='||p_surface_id,
 'mcp_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=mcp'),
 'controls',jsonb_build_object('provider_credentials_exposed',false,'provider_write',false,'money_movement',false,
 'internal_sql_topology_exposed',false,'non_public_mcp_servers_exposed',false,'read_after_write_required',true,'rollback_required',true));
 v_sha:=encode(extensions.digest(convert_to(v_base::text,'UTF8'),'sha256'),'hex');
 return v_base||jsonb_build_object('manifest_sha256',v_sha);
end $$;
