update penta_runtime.fabrics_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'packet_name', 'Penta',
      'packet_contract', 'crownthrive.penta.event.v1',
      'packet_schema', 'crownthrive.pentafabric.v1',
      'chlom_packet_binding', 'crownthrive.chlom.pentafabric.v1',
      'hot_transport_provider', 'Vercel',
      'evidence_ledger', 'public.pentafabric_events',
      'packet_hotfix_version', '1.0.0',
      'packet_contract_bound_at', now()
    ),
    updated_at = now()
where fabric_id = 'ct.fabric.penta.v1';

update penta_runtime.fabric_layers_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'packet_name', 'Penta',
      'packet_contract', 'crownthrive.penta.event.v1',
      'packet_schema', 'crownthrive.pentafabric.v1',
      'chlom_binding', 'crownthrive.chlom.pentafabric.v1',
      'hot_transport_provider', 'Vercel',
      'packet_delivery_type', 'penta.relay.forwarded',
      'packet_delivery_status', 'DELIVERED',
      'packet_contract_bound_at', now()
    ),
    updated_at = now()
where layer_id = 'ct.penta.layer.2' and fabric_id = 'ct.fabric.penta.v1';

update penta_runtime.fabric_layers_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'pentafabric_evidence_ledger', 'public.pentafabric_events',
      'pentafabric_append_only', true,
      'pentafabric_rls', true,
      'pentafabric_chlom_binding', 'crownthrive.chlom.pentafabric.v1',
      'packet_contract_bound_at', now()
    ),
    updated_at = now()
where layer_id = 'ct.penta.layer.9' and fabric_id = 'ct.fabric.penta.v1';
