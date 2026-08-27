-- Strengthen PentaFabric mesh convergence from core-path proof to global connectedness proof.
create or replace function penta_runtime.penta_fabric_mesh_convergence_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog','penta_runtime','integration_control','public'
as $function$
with core_edges(source_key,target_key,relation) as (
 values
  ('penta.fabric'::text,'penta.self'::text,'delegates_resilience_to'::text),
  ('penta.self','penta.mesh','precedes_and_authorizes'),
  ('penta.mesh','penta.wire','transports_through'),
  ('penta.fabric','penta.wire','distributes_pentas_through')
),
counts as (
 select
  (select count(*) from core_edges e where exists(
    select 1 from penta_runtime.topology_edges_v1 t
    where t.source_key=e.source_key and t.target_key=e.target_key and t.relation=e.relation and t.required and t.state='bound'
  )) as topology_bound,
  (select count(*) from integration_control.chlom_mesh_object_bindings_v1
    where binding_id in ('ct.bind.pentafabric-runtime.v1','ct.bind.pentafabric-vercel-hot.v1','ct.bind.pentafabric-ingest.v1','ct.bind.private-pentaos-kernel.v1')
      and current_state='bound') as core_chlom_bound,
  (select count(*) from integration_control.penta_wire_service_bindings_v1
    where service_id in ('penta_fabric_vercel_hot','pentafabric_ingest','private_penta_os_kernel','chlom_pentafabric_governance')
      and gap_state='complete' and binding_state in ('active_probe','registry_bound')) as core_wire_bound,
  (select count(*) from penta_runtime.repository_registry_v1
    where repository_full_name in ('crownthrive1/CrownThrive-OS','crownthrive1/PRIVATE-PentaOS','crownthrive1/chlom-protocol') and enabled) as repos_bound,
  (select count(*) from penta_runtime.edges_v1
    where edge_id in ('ct.penta.edge.chlom-to-fabric','ct.penta.edge.fabric-to-private-kernel','ct.penta.edge.fabric-to-vercel-hot','ct.penta.edge.vercel-hot-to-ingest','ct.penta.edge.ingest-to-ledger')
      and route_state in ('read_verified','write_verified')) as route_edges_bound,
  (select count(*) from integration_control.penta_wire_service_bindings_v1) as wire_total,
  (select count(*) from integration_control.penta_wire_service_bindings_v1 where mesh_adapter_service_id='penta_wire_mesh') as wire_mesh_bound,
  (select count(*) from integration_control.penta_wire_service_bindings_v1 where gap_state='tool_contract_drift') as wire_contract_drift,
  (select count(*) from integration_control.penta_wire_service_bindings_v1 where gap_state='exact_provider_contract_required') as wire_provider_holds,
  penta_runtime.penta_output_contract_status_v1() as output_status,
  integration_control.chlom_mesh_status_v1() as chlom_status,
  penta_runtime.penta_meshes_status_v1() as mesh_status
), normalized as (
 select *,
   coalesce((output_status->>'active_components')::int,0) as active_components,
   coalesce((output_status->>'contract_bound_components')::int,0) as output_bound_components,
   coalesce((chlom_status->'binding_summary'->>'total')::int,0) as chlom_total,
   coalesce((chlom_status->'binding_summary'->>'bound')::int,0) as chlom_all_bound,
   coalesce((chlom_status->'binding_summary'->>'hold')::int,0) as chlom_hold,
   coalesce((chlom_status->'binding_summary'->>'degraded')::int,0) as chlom_degraded
 from counts
)
select jsonb_build_object(
 'service','ct.penta.fabric.mesh-convergence.v1',
 'state',case when topology_bound=4
   and core_chlom_bound=4
   and core_wire_bound=4
   and repos_bound=3
   and route_edges_bound=5
   and wire_total=wire_mesh_bound
   and wire_total>0
   and wire_provider_holds=0
   and coalesce(output_status->>'state','FAIL')='PASS'
   and active_components=output_bound_components
   and active_components>0
   and coalesce(mesh_status->>'state','FAIL')='PRODUCTION'
   and chlom_total=chlom_all_bound
   and chlom_hold=0
   and chlom_degraded=0
   then 'PASS' else 'FAIL' end,
 'packet','Penta',
 'event_contract','crownthrive.penta.event.v1',
 'fabric_schema','crownthrive.pentafabric.v1',
 'chlom_binding','crownthrive.chlom.pentafabric.v1',
 'topology_bound',topology_bound,'topology_required',4,
 'core_chlom_bound',core_chlom_bound,'core_chlom_required',4,
 'core_wire_bound',core_wire_bound,'core_wire_required',4,
 'repositories_bound',repos_bound,'repositories_required',3,
 'route_edges_bound',route_edges_bound,'route_edges_required',5,
 'wire_services_total',wire_total,'wire_services_mesh_bound',wire_mesh_bound,
 'wire_services_unmeshed',wire_total-wire_mesh_bound,
 'wire_exact_provider_holds',wire_provider_holds,
 'wire_tool_contract_drift',wire_contract_drift,
 'active_penta_components',active_components,
 'penta_output_bound_components',output_bound_components,
 'chlom_bindings_total',chlom_total,'chlom_bindings_bound',chlom_all_bound,
 'chlom_holds',chlom_hold,'chlom_degraded',chlom_degraded,
 'penta_mesh_state',mesh_status->>'state',
 'quality_note','tool_contract_drift is schema/tool hardening debt inside mesh-bound services; it does not represent connectivity loss',
 'generated_at',now()
) from normalized;
$function$;

update penta_runtime.fabrics_v1
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'global_mesh_enforcement',true,
  'global_mesh_enforcement_contract','ct.penta.fabric.mesh-convergence.v1',
  'global_mesh_requires_all_wire_services_bound',true,
  'global_mesh_requires_all_active_pentas_output_bound',true,
  'global_mesh_requires_chlom_all_bound',true,
  'global_mesh_enforced_at',now()
),updated_at=now()
where fabric_id='ct.fabric.penta.v1';
