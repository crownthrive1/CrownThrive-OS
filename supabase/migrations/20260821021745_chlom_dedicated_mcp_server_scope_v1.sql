create table if not exists chlom_runtime.mcp_tool_exposure (
  tool_name text primary key references integration_control.mcp_tools(tool_name) on delete cascade,
  server_id text not null default 'ct.mcp.chlom-core',
  enabled boolean not null default false,
  exposure_state text not null default 'test' check (exposure_state in ('specified','test','staged','production','suspended','retired')),
  minimum_authority text not null default 'D0' check (minimum_authority in ('D0','D1','D2','D3')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into chlom_runtime.mcp_tool_exposure(tool_name,server_id,enabled,exposure_state,minimum_authority)
select tool_name,'ct.mcp.chlom-core',true,'test',risk_class
from integration_control.mcp_tools
where service_id='chlom_core'
on conflict(tool_name) do update set server_id=excluded.server_id,enabled=excluded.enabled,exposure_state=excluded.exposure_state,minimum_authority=excluded.minimum_authority,updated_at=now();

-- Keep the legacy/general CrownThrive MCP dispatcher from advertising tools it cannot route.
update integration_control.mcp_tools
set enabled=false,
    notes=coalesce(notes,'') || ' Dedicated CHLOM MCP exposure is controlled by chlom_runtime.mcp_tool_exposure; disabled on legacy/general dispatcher.',
    updated_at=now()
where service_id='chlom_core' and enabled=true;

create or replace function public.chlom_mcp_snapshot()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, integration_control, chlom_runtime
as $$
  select jsonb_build_object(
    'server_id','ct.mcp.chlom-core',
    'tools',coalesce(jsonb_agg(jsonb_build_object(
      'tool_name',m.tool_name,
      'service_id',m.service_id,
      'operation_key',m.operation_key,
      'risk_class',m.risk_class,
      'requires_human_approval',m.requires_human_approval,
      'input_schema',m.input_schema,
      'output_schema',m.output_schema,
      'notes',m.notes,
      'exposure_state',e.exposure_state,
      'minimum_authority',e.minimum_authority
    ) order by m.tool_name) filter (where e.enabled=true), '[]'::jsonb)
  )
  from chlom_runtime.mcp_tool_exposure e
  join integration_control.mcp_tools m using(tool_name)
  where e.server_id='ct.mcp.chlom-core'
$$;

revoke all on function public.chlom_mcp_snapshot() from public, anon, authenticated;
grant execute on function public.chlom_mcp_snapshot() to service_role;

select chlom_runtime.append_dail_event(
  'chlom.mcp.server_scope.created','module','ct.chlom.api-mcp',
  jsonb_build_object('server_id','ct.mcp.chlom-core','legacy_dispatcher_exposure_disabled',true,'dedicated_tool_count',(select count(*) from chlom_runtime.mcp_tool_exposure where enabled)),
  'founder-directive-2026-08-20',null,'ct.agent.founder-orchestrator','0.1.0',null,null,'D2 founder authorized',null,'internal'
);