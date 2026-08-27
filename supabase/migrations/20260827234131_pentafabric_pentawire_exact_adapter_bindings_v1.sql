-- Make PentaFabric peers first-class PentaWire exact contracts so autonomous reconciliation preserves them.

update integration_control.services
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'public_safe',true,
  'penta_wire_public_status_safe',true,
  'write_methods_enabled',false,
  'delete_methods_enabled',false,
  'penta_wire_public_probe_url','https://crown-thrive-os.vercel.app/pentafabric/health?selftest=1',
  'penta_wire_exact_contract','ct.penta.vercel.fabric.20260827.v1',
  'penta_wire_adapter_kind','PUBLIC_HTTP'
),updated_at=now()
where service_id='penta_fabric_vercel_hot';

update integration_control.services
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'public_safe',true,
  'penta_wire_public_status_safe',true,
  'write_methods_enabled',false,
  'delete_methods_enabled',false,
  'penta_wire_public_probe_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentafabric-ingest',
  'penta_wire_exact_contract','ct.penta.supabase.ingest.20260827.v1',
  'penta_wire_adapter_kind','PUBLIC_HTTP',
  'public_projection_scope','GET health/contract only; POST remains Vercel OIDC gated'
),updated_at=now()
where service_id='pentafabric_ingest';

update integration_control.services
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'penta_wire_exact_contract','crownthrive.chlom.pentafabric.v1',
  'penta_wire_adapter_kind','INTERNAL_SQL',
  'penta_wire_projection','CHLOM mesh binding and production artifact state only',
  'write_methods_enabled',false,'delete_methods_enabled',false
),updated_at=now()
where service_id='chlom_pentafabric_governance';

update integration_control.services
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'penta_wire_exact_contract','crownthrive.penta.event.v1',
  'penta_wire_adapter_kind','INTERNAL_SQL',
  'penta_wire_projection','repository registry plus certified Vercel runtime evidence only',
  'write_methods_enabled',false,'delete_methods_enabled',false
),updated_at=now()
where service_id='private_penta_os_kernel';

insert into integration_control.penta_wire_read_adapters_v1(
  service_id,adapter_kind,exact_contract,transport_ref,allowed_operations,
  public_projection,provider_write,credential_forwarding,authority_effect,state,evidence,updated_at
) values
(
  'penta_fabric_vercel_hot','PUBLIC_HTTP','ct.penta.vercel.fabric.20260827.v1',
  'https://crown-thrive-os.vercel.app/pentafabric/health?selftest=1',
  jsonb_build_array('health.read','contract.read','selftest.read'),true,false,false,'none','active',
  jsonb_build_object(
    'provider','Vercel','production_route','/penta','packet','Penta',
    'event_contract','crownthrive.penta.event.v1','fabric_schema','crownthrive.pentafabric.v1',
    'chlom_binding','crownthrive.chlom.pentafabric.v1','public_probe_contains_secrets',false,
    'provider_write',false,'money_movement',false,'transport_attestation','VERCEL_OIDC_RS256'
  ),now()
),
(
  'pentafabric_ingest','PUBLIC_HTTP','ct.penta.supabase.ingest.20260827.v1',
  'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentafabric-ingest',
  jsonb_build_array('health.read','contract.read'),true,false,false,'none','active',
  jsonb_build_object(
    'provider','Supabase Edge','post_authentication','VERCEL_OIDC_RS256',
    'public_projection','GET health and contract only','post_exposed_publicly',false,
    'ledger','public.pentafabric_events','append_only',true,'rls',true,
    'provider_write',false,'money_movement',false
  ),now()
),
(
  'chlom_pentafabric_governance','INTERNAL_SQL','crownthrive.chlom.pentafabric.v1',
  'sql:integration_control.chlom_mesh_status_v1()+chlom_mesh_object_bindings_v1',
  jsonb_build_array('status.read','binding.read'),true,false,false,'none','active',
  jsonb_build_object(
    'projection','PentaFabric CHLOM governance state only','binding_id','ct.bind.pentafabric-runtime.v1',
    'production_artifact','github:crownthrive1/chlom-protocol/artifacts/pentafabric-v1.binding.json',
    'provider_write',false,'authority_expansion',false
  ),now()
),
(
  'private_penta_os_kernel','INTERNAL_SQL','crownthrive.penta.event.v1',
  'sql:penta_runtime.repository_registry_v1+integration_control.services',
  jsonb_build_array('status.read','repository_binding.read'),true,false,false,'none','active',
  jsonb_build_object(
    'projection','certified repository/runtime identity only','repository','crownthrive1/PRIVATE-PentaOS',
    'production_merge_sha','08b1d8c59dbedd13cd01b8f0e566aa1dc4f97909',
    'secret_material_exposed',false,'provider_write',false,'authority_expansion',false
  ),now()
)
on conflict (service_id) do update set
  adapter_kind=excluded.adapter_kind,
  exact_contract=excluded.exact_contract,
  transport_ref=excluded.transport_ref,
  allowed_operations=excluded.allowed_operations,
  public_projection=excluded.public_projection,
  provider_write=false,
  credential_forwarding=false,
  authority_effect='none',
  state='active',
  evidence=coalesce(integration_control.penta_wire_read_adapters_v1.evidence,'{}'::jsonb)||excluded.evidence,
  updated_at=now();

update penta_runtime.fabrics_v1
set metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
  'penta_wire_exact_adapter_contracts',4,
  'penta_wire_exact_adapters_bound_at',now(),
  'mesh_convergence_source_of_truth','PentaWire exact adapters + CHLOM mesh + topology graph + repository registry'
),updated_at=now()
where fabric_id='ct.fabric.penta.v1';
