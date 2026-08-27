-- PentaFabric v1 mesh convergence: make the production packet path explicit in every canonical registry.

insert into integration_control.services (
  service_id, display_name, base_url, docs_url, auth_scheme, credential_ref,
  credential_state, integration_state, write_gate, metadata, updated_at
) values
(
  'penta_fabric_vercel_hot',
  'PentaFabric Vercel Hot Ingress',
  'https://crown-thrive-os.vercel.app/penta',
  'https://github.com/crownthrive1/CrownThrive-OS/blob/main/apps/crownthrive-os-control-plane/api/penta.js',
  'canonical Penta contract ingress; rotating Vercel OIDC RS256 for downstream evidence',
  'vercel-workload-identity:crownthrive-os:production',
  'verified','write_verified',false,
  jsonb_build_object(
    'contract','crownthrive.penta.event.v1','fabric','crownthrive.pentafabric.v1',
    'chlom_binding','crownthrive.chlom.pentafabric.v1','packet_name','Penta',
    'provider','Vercel','route','/penta','transport_assurance','VERCEL_OIDC_RS256',
    'production_build_sha','d20171a1df2909aaf8b0e1779bd4962ad6b0f8b6',
    'certification_penta_id','penta_17b420e9-8d79-4903-a455-2c13c4acc931',
    'penta_wire_bound',true,'mesh_required',true
  ),now()
),
(
  'pentafabric_ingest',
  'PentaFabric Supabase Evidence Ingest',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentafabric-ingest',
  'https://github.com/crownthrive1/CrownThrive-OS/blob/main/supabase/functions/pentafabric-ingest/index.ts',
  'Vercel OIDC RS256 exact owner/project/production claims',
  'vercel-workload-identity:crownthrive-os:production',
  'verified','write_verified',false,
  jsonb_build_object(
    'contract','ct.penta.supabase.ingest.20260827.v1','accepts','crownthrive.penta.event.v1',
    'fabric','crownthrive.pentafabric.v1','chlom_binding','crownthrive.chlom.pentafabric.v1',
    'ledger','public.pentafabric_events','append_only',true,'rls',true,
    'transport_assurance','VERCEL_OIDC_RS256','certification_result','PERSISTED',
    'certification_penta_id','penta_17b420e9-8d79-4903-a455-2c13c4acc931',
    'penta_wire_bound',true,'mesh_required',true
  ),now()
),
(
  'private_penta_os_kernel',
  'PRIVATE-PentaOS Kernel',
  'https://private-penta-os.vercel.app',
  'https://github.com/crownthrive1/PRIVATE-PentaOS',
  'private repository plus Vercel production runtime',
  'vercel-project:private-penta-os',
  'verified','configured',false,
  jsonb_build_object(
    'repository','crownthrive1/PRIVATE-PentaOS','kernel_contract','crownthrive.penta.event.v1',
    'fabric','crownthrive.pentafabric.v1','private_kernel_preferred_integrity','HMAC-SHA256',
    'production_merge_sha','08b1d8c59dbedd13cd01b8f0e566aa1dc4f97909',
    'penta_wire_bound',true,'mesh_required',true
  ),now()
),
(
  'chlom_pentafabric_governance',
  'CHLOM PentaFabric Governance',
  'https://chlom-protocol.vercel.app',
  'https://github.com/crownthrive1/chlom-protocol/blob/main/artifacts/pentafabric-v1.binding.json',
  'CHLOM governed production binding',
  'github+vercel:chlom-protocol',
  'verified','read_verified',false,
  jsonb_build_object(
    'repository','crownthrive1/chlom-protocol','binding','crownthrive.chlom.pentafabric.v1',
    'binding_status','PRODUCTION','production_merge_sha','d81949fb85f0b80045a1ad38e21c7c1f66f62de0',
    'penta_wire_bound',true,'mesh_required',true
  ),now()
)
on conflict (service_id) do update set
  display_name=excluded.display_name, base_url=excluded.base_url, docs_url=excluded.docs_url,
  auth_scheme=excluded.auth_scheme, credential_ref=excluded.credential_ref,
  credential_state=excluded.credential_state, integration_state=excluded.integration_state,
  write_gate=excluded.write_gate, metadata=coalesce(integration_control.services.metadata,'{}'::jsonb)||excluded.metadata,
  updated_at=now();

insert into integration_control.penta_wire_service_bindings_v1 (
  service_id,binding_state,gap_state,public_read_safe,probe_method,probe_url,
  mesh_adapter_service_id,mesh_api_url,direct_tool_count,enabled_tool_count,closed_input_tool_count,
  current_integration_state,last_probe_state,last_http_status,evidence,updated_at
) values
(
  'penta_fabric_vercel_hot','active_probe','complete',true,'GET',
  'https://crown-thrive-os.vercel.app/pentafabric/health?selftest=1','penta_wire_mesh',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-wire-mesh/api/services/penta_fabric_vercel_hot',
  2,2,2,'write_verified','pass',200,
  jsonb_build_object('state','production','contract','crownthrive.penta.event.v1','fabric','crownthrive.pentafabric.v1',
    'chlom_binding','crownthrive.chlom.pentafabric.v1','transport_assurance','VERCEL_OIDC_RS256',
    'certification_penta_id','penta_17b420e9-8d79-4903-a455-2c13c4acc931','provider_write',false,'money_movement',false),now()
),
(
  'pentafabric_ingest','active_probe','complete',true,'GET',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentafabric-ingest','penta_wire_mesh',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-wire-mesh/api/services/pentafabric_ingest',
  2,2,2,'write_verified','pass',200,
  jsonb_build_object('state','production','contract','ct.penta.supabase.ingest.20260827.v1',
    'authentication','VERCEL_OIDC_RS256','ledger','public.pentafabric_events','append_only',true,
    'certification_penta_id','penta_17b420e9-8d79-4903-a455-2c13c4acc931','provider_write',false,'money_movement',false),now()
),
(
  'private_penta_os_kernel','registry_bound','complete',false,'REGISTRY',null,'penta_wire_mesh',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-wire-mesh/api/services/private_penta_os_kernel',
  1,1,1,'configured','not_run',null,
  jsonb_build_object('state','production','repository','crownthrive1/PRIVATE-PentaOS',
    'production_merge_sha','08b1d8c59dbedd13cd01b8f0e566aa1dc4f97909','provider_write',false,'money_movement',false),now()
),
(
  'chlom_pentafabric_governance','registry_bound','complete',true,'REGISTRY',null,'penta_wire_mesh',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-wire-mesh/api/services/chlom_pentafabric_governance',
  1,1,1,'read_verified','not_run',null,
  jsonb_build_object('state','production','binding','crownthrive.chlom.pentafabric.v1',
    'production_merge_sha','d81949fb85f0b80045a1ad38e21c7c1f66f62de0','provider_write',false,'money_movement',false),now()
)
on conflict (service_id) do update set
  binding_state=excluded.binding_state,gap_state=excluded.gap_state,public_read_safe=excluded.public_read_safe,
  probe_method=excluded.probe_method,probe_url=excluded.probe_url,mesh_adapter_service_id=excluded.mesh_adapter_service_id,
  mesh_api_url=excluded.mesh_api_url,direct_tool_count=excluded.direct_tool_count,enabled_tool_count=excluded.enabled_tool_count,
  closed_input_tool_count=excluded.closed_input_tool_count,current_integration_state=excluded.current_integration_state,
  last_probe_state=excluded.last_probe_state,last_http_status=excluded.last_http_status,
  evidence=coalesce(integration_control.penta_wire_service_bindings_v1.evidence,'{}'::jsonb)||excluded.evidence,updated_at=now();

insert into integration_control.chlom_mesh_object_bindings_v1 (
 binding_id,object_type,object_ref,binding_kind,control_class,authority_ceiling,desired_state,current_state,
 environment,endpoint_ref,vault_policy_ref,dail_required,independent_verifier_required,human_gate_required,
 no_secret_exposure,no_delete,no_money_movement,source_refs,evidence_refs,metadata,last_verified_at,updated_at
) values
(
 'ct.bind.pentafabric-runtime.v1','runtime_fabric','ct.fabric.penta.v1','governed_runtime_binding','D2_GOVERNED_RUNTIME','A2','bound','bound',
 'production','https://crown-thrive-os.vercel.app/penta','ct.vault.policy.runtime-authority.v1',true,true,false,true,true,true,
 jsonb_build_array('github:crownthrive1/CrownThrive-OS#616','github:crownthrive1/chlom-protocol#41'),
 jsonb_build_array('penta:penta_17b420e9-8d79-4903-a455-2c13c4acc931','vercel:dpl_G5d8DGnif4KrbRcXVmvoari3jJuf'),
 jsonb_build_object('contract','crownthrive.penta.event.v1','fabric_schema','crownthrive.pentafabric.v1','chlom_binding','crownthrive.chlom.pentafabric.v1'),now(),now()
),
(
 'ct.bind.pentafabric-vercel-hot.v1','vercel_service','penta_fabric_vercel_hot','hot_transport','D1_TRANSPORT','A2','bound','bound',
 'production','https://crown-thrive-os.vercel.app/penta','ct.vault.policy.mesh-provider.v1',true,true,false,true,true,true,
 jsonb_build_array('github:crownthrive1/CrownThrive-OS#623'),
 jsonb_build_array('vercel:dpl_G5d8DGnif4KrbRcXVmvoari3jJuf','penta:penta_17b420e9-8d79-4903-a455-2c13c4acc931'),
 jsonb_build_object('transport_assurance','VERCEL_OIDC_RS256','delivery_type','penta.relay.forwarded','delivery_status','DELIVERED'),now(),now()
),
(
 'ct.bind.pentafabric-ingest.v1','edge_function','pentafabric-ingest','evidence_ingest','D1_EVIDENCE','A2','bound','bound',
 'production','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentafabric-ingest','ct.vault.policy.audit-evidence.v1',true,true,false,true,true,true,
 jsonb_build_array('github:crownthrive1/CrownThrive-OS#618','github:crownthrive1/CrownThrive-OS#623'),
 jsonb_build_array('penta:penta_17b420e9-8d79-4903-a455-2c13c4acc931','ledger:public.pentafabric_events'),
 jsonb_build_object('authentication','VERCEL_OIDC_RS256','append_only',true,'rls',true,'idempotent_key','penta_id'),now(),now()
),
(
 'ct.bind.private-pentaos-kernel.v1','repository_runtime','crownthrive1/PRIVATE-PentaOS','kernel_binding','D2_KERNEL','A2','bound','bound',
 'production','https://private-penta-os.vercel.app','ct.vault.policy.runtime-authority.v1',true,true,false,true,true,true,
 jsonb_build_array('github:crownthrive1/PRIVATE-PentaOS#9'),
 jsonb_build_array('git:08b1d8c59dbedd13cd01b8f0e566aa1dc4f97909'),
 jsonb_build_object('kernel_contract','crownthrive.penta.event.v1','private_kernel_preferred_integrity','HMAC-SHA256'),now(),now()
)
on conflict (binding_id) do update set
 object_type=excluded.object_type,object_ref=excluded.object_ref,binding_kind=excluded.binding_kind,control_class=excluded.control_class,
 authority_ceiling=excluded.authority_ceiling,desired_state=excluded.desired_state,current_state=excluded.current_state,
 environment=excluded.environment,endpoint_ref=excluded.endpoint_ref,vault_policy_ref=excluded.vault_policy_ref,
 dail_required=excluded.dail_required,independent_verifier_required=excluded.independent_verifier_required,
 human_gate_required=excluded.human_gate_required,no_secret_exposure=excluded.no_secret_exposure,no_delete=excluded.no_delete,
 no_money_movement=excluded.no_money_movement,source_refs=excluded.source_refs,evidence_refs=excluded.evidence_refs,
 metadata=coalesce(integration_control.chlom_mesh_object_bindings_v1.metadata,'{}'::jsonb)||excluded.metadata,
 last_verified_at=now(),updated_at=now();

insert into penta_runtime.repository_registry_v1(repository_full_name,canonical_role,enabled,mutation_policy,metadata,updated_at)
values
 ('crownthrive1/CrownThrive-OS','PentaFabric public runtime and governed control plane',true,'governed',
  jsonb_build_object('fabric','ct.fabric.penta.v1','penta_packet_contract','crownthrive.penta.event.v1','vercel_project','crownthrive-os','mesh_connected',true),now()),
 ('crownthrive1/PRIVATE-PentaOS','Private Penta kernel and canonical PentaFabric transport implementation',true,'governed',
  jsonb_build_object('fabric','ct.fabric.penta.v1','kernel_contract','crownthrive.penta.event.v1','vercel_project','private-penta-os','mesh_connected',true),now()),
 ('crownthrive1/chlom-protocol','CHLOM protocol child repository',true,'governed',
  jsonb_build_object('pentafabric_binding','crownthrive.chlom.pentafabric.v1','vercel_project','chlom-protocol','mesh_connected',true),now())
on conflict (repository_full_name) do update set
 canonical_role=excluded.canonical_role,enabled=true,mutation_policy='governed',
 metadata=coalesce(penta_runtime.repository_registry_v1.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

insert into penta_runtime.topology_edges_v1(edge_id,source_key,target_key,relation,required,state,metadata)
values
 (gen_random_uuid(),'penta.fabric','penta.self','delegates_resilience_to',true,'bound',jsonb_build_object('order',1,'contract','ct.penta.fabric.mesh-convergence.v1')),
 (gen_random_uuid(),'penta.self','penta.mesh','precedes_and_authorizes',true,'bound',jsonb_build_object('order',2,'contract','ct.penta.fabric.mesh-convergence.v1')),
 (gen_random_uuid(),'penta.mesh','penta.wire','transports_through',true,'bound',jsonb_build_object('order',3,'contract','ct.penta.fabric.mesh-convergence.v1')),
 (gen_random_uuid(),'penta.fabric','penta.wire','distributes_pentas_through',true,'bound',jsonb_build_object('packet','Penta','contract','ct.penta.fabric.mesh-convergence.v1'))
on conflict (source_key,target_key,relation) do update set required=true,state='bound',metadata=coalesce(penta_runtime.topology_edges_v1.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

insert into penta_runtime.edges_v1(
 edge_id,source_id,target_id,edge_kind,route_state,authority_class,redundancy_group,fail_closed,
 provider_write,money_movement,rights_grant,source_ref,metadata,updated_at
) values
 ('ct.penta.edge.chlom-to-fabric','crownthrive1/chlom-protocol','ct.fabric.penta.v1','control','read_verified','D2','pentafabric-governance',true,false,false,false,'github:crownthrive1/chlom-protocol#41',jsonb_build_object('binding','crownthrive.chlom.pentafabric.v1'),now()),
 ('ct.penta.edge.fabric-to-private-kernel','ct.fabric.penta.v1','crownthrive1/PRIVATE-PentaOS','control','read_verified','D2','pentafabric-kernel',true,false,false,false,'github:crownthrive1/PRIVATE-PentaOS#9',jsonb_build_object('kernel_contract','crownthrive.penta.event.v1'),now()),
 ('ct.penta.edge.fabric-to-vercel-hot','ct.fabric.penta.v1','penta_fabric_vercel_hot','handoff','write_verified','D1','pentafabric-hot-path',true,true,false,false,'vercel:dpl_G5d8DGnif4KrbRcXVmvoari3jJuf',jsonb_build_object('packet','Penta','transport_assurance','VERCEL_OIDC_RS256'),now()),
 ('ct.penta.edge.vercel-hot-to-ingest','penta_fabric_vercel_hot','pentafabric_ingest','evidence','write_verified','D1','pentafabric-hot-path',true,true,false,false,'penta:penta_17b420e9-8d79-4903-a455-2c13c4acc931',jsonb_build_object('authentication','VERCEL_OIDC_RS256'),now()),
 ('ct.penta.edge.ingest-to-ledger','pentafabric_ingest','public.pentafabric_events','evidence','write_verified','D1','pentafabric-evidence',true,true,false,false,'ledger:public.pentafabric_events',jsonb_build_object('append_only',true,'rls',true,'idempotent_key','penta_id'),now())
on conflict (edge_id) do update set
 source_id=excluded.source_id,target_id=excluded.target_id,edge_kind=excluded.edge_kind,route_state=excluded.route_state,
 authority_class=excluded.authority_class,redundancy_group=excluded.redundancy_group,fail_closed=excluded.fail_closed,
 provider_write=excluded.provider_write,money_movement=excluded.money_movement,rights_grant=excluded.rights_grant,
 source_ref=excluded.source_ref,metadata=coalesce(penta_runtime.edges_v1.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

update penta_runtime.component_registry_v1
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
 'mesh_connected',true,'mesh_convergence_contract','ct.penta.fabric.mesh-convergence.v1',
 'mesh_converged_at',now(),'penta_wire_mesh_service','penta_wire_mesh'
),updated_at=now()
where component_key in ('penta.fabric','penta.self','penta.mesh','penta.wire');

update penta_runtime.fabrics_v1
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
 'mesh_connected',true,'mesh_convergence_contract','ct.penta.fabric.mesh-convergence.v1',
 'mesh_converged_at',now(),'core_topology_edges',4,'chlom_mesh_bindings',4,
 'wire_service_bindings',4,'repository_bindings',3,'provider_route_edges',5
),updated_at=now()
where fabric_id='ct.fabric.penta.v1';

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
  (select count(*) from core_edges e where exists(select 1 from penta_runtime.topology_edges_v1 t where t.source_key=e.source_key and t.target_key=e.target_key and t.relation=e.relation and t.required and t.state='bound')) as topology_bound,
  (select count(*) from integration_control.chlom_mesh_object_bindings_v1 where binding_id in ('ct.bind.pentafabric-runtime.v1','ct.bind.pentafabric-vercel-hot.v1','ct.bind.pentafabric-ingest.v1','ct.bind.private-pentaos-kernel.v1') and current_state='bound') as chlom_bound,
  (select count(*) from integration_control.penta_wire_service_bindings_v1 where service_id in ('penta_fabric_vercel_hot','pentafabric_ingest','private_penta_os_kernel','chlom_pentafabric_governance') and gap_state='complete' and binding_state in ('active_probe','registry_bound')) as wire_bound,
  (select count(*) from penta_runtime.repository_registry_v1 where repository_full_name in ('crownthrive1/CrownThrive-OS','crownthrive1/PRIVATE-PentaOS','crownthrive1/chlom-protocol') and enabled) as repos_bound,
  (select count(*) from penta_runtime.edges_v1 where edge_id in ('ct.penta.edge.chlom-to-fabric','ct.penta.edge.fabric-to-private-kernel','ct.penta.edge.fabric-to-vercel-hot','ct.penta.edge.vercel-hot-to-ingest','ct.penta.edge.ingest-to-ledger') and route_state in ('read_verified','write_verified')) as route_edges_bound
)
select jsonb_build_object(
 'service','ct.penta.fabric.mesh-convergence.v1',
 'state',case when topology_bound=4 and chlom_bound=4 and wire_bound=4 and repos_bound=3 and route_edges_bound=5
   and coalesce((penta_runtime.penta_output_contract_status_v1()->>'state'),'FAIL')='PASS'
   and coalesce((penta_runtime.penta_meshes_status_v1()->>'state'),'FAIL')='PRODUCTION'
   then 'PASS' else 'FAIL' end,
 'packet','Penta','event_contract','crownthrive.penta.event.v1','fabric_schema','crownthrive.pentafabric.v1',
 'chlom_binding','crownthrive.chlom.pentafabric.v1','topology_bound',topology_bound,'topology_required',4,
 'chlom_bound',chlom_bound,'chlom_required',4,'wire_bound',wire_bound,'wire_required',4,
 'repositories_bound',repos_bound,'repositories_required',3,'route_edges_bound',route_edges_bound,'route_edges_required',5,
 'generated_at',now()
) from counts;
$function$;

create or replace function public.penta_fabric_mesh_convergence_status_v1()
returns jsonb
language sql
stable
security definer
set search_path to 'pg_catalog','penta_runtime'
as $function$ select penta_runtime.penta_fabric_mesh_convergence_status_v1(); $function$;

create or replace function penta_runtime.penta_fabric_cycle_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_runtime','penta_self','integration_control','public'
as $function$
declare v_self jsonb; v_status jsonb; v_mesh jsonb; v_convergence jsonb; v_state text;
begin
 if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.fabric.v1',0)) then
   return jsonb_build_object('service','ct.penta.fabrics.v1','phase',3,'state','SKIPPED_LOCKED','production',true,'at',now());
 end if;
 begin v_self:=penta_self.tick_v1(); exception when others then v_self:=jsonb_build_object('state','FAILED','error',left(sqlerrm,300)); end;
 begin v_mesh:=penta_runtime.penta_meshes_status_v1(); exception when others then v_mesh:=jsonb_build_object('state','FAILED','error',left(sqlerrm,300)); end;
 begin v_convergence:=penta_runtime.penta_fabric_mesh_convergence_status_v1(); exception when others then v_convergence:=jsonb_build_object('state','FAIL','error',left(sqlerrm,300)); end;
 v_status:=penta_runtime.penta_fabrics_status_v1();
 v_state:=case when coalesce(v_self->>'state','FAILED') in('HEALTHY','SKIPPED_LOCKED')
   and coalesce(v_mesh->>'state','FAILED')='PRODUCTION'
   and coalesce(v_convergence->>'state','FAIL')='PASS'
   then 'HEALTHY' else 'DEGRADED' end;
 update penta_runtime.fabrics_v1
 set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
   'last_fabric_cycle_at',now(),'last_fabric_cycle_state',v_state,
   'self_cycle_state',v_self->>'state','mesh_state',v_mesh->>'state',
   'mesh_convergence_state',v_convergence->>'state','mesh_convergence_contract','ct.penta.fabric.mesh-convergence.v1'
 ),updated_at=now() where fabric_id='ct.fabric.penta.v1';
 return jsonb_build_object('service','ct.penta.fabrics.v1','phase',3,'production',true,'state',v_state,
   'fabric',v_status,'self',v_self,'mesh',v_mesh,'mesh_convergence',v_convergence,
   'authority_manufacture',false,'at',now());
end $function$;
