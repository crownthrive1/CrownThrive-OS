create or replace function penta_runtime.validate_penta_envelope_v1(p_event jsonb)
returns jsonb
language plpgsql
immutable
security invoker
set search_path = pg_catalog
as $$
begin
  if p_event is null or jsonb_typeof(p_event) <> 'object' then
    raise exception 'PENTA_CONTRACT: event must be an object';
  end if;
  if p_event ->> 'specversion' <> '1.0' then
    raise exception 'PENTA_CONTRACT: specversion must be 1.0';
  end if;
  if coalesce(p_event ->> 'id','') !~ '^penta_' then
    raise exception 'PENTA_CONTRACT: id must start with penta_';
  end if;
  if coalesce(p_event ->> 'type','') !~ '^penta\\.' then
    raise exception 'PENTA_CONTRACT: type must start with penta.';
  end if;
  if p_event ->> 'datacontenttype' <> 'application/json' then
    raise exception 'PENTA_CONTRACT: datacontenttype must be application/json';
  end if;
  if p_event #>> '{mesh,contract}' <> 'crownthrive.penta.event.v1' then
    raise exception 'PENTA_CONTRACT: canonical event contract mismatch';
  end if;
  if p_event #>> '{mesh,family}' <> 'PentaFamily' then
    raise exception 'PENTA_CONTRACT: family must be PentaFamily';
  end if;
  if p_event #>> '{mesh,fabric,schema}' <> 'crownthrive.pentafabric.v1' then
    raise exception 'PENTA_CONTRACT: PentaFabric schema mismatch';
  end if;
  if p_event #>> '{mesh,fabric,version}' <> '1.0.0' then
    raise exception 'PENTA_CONTRACT: PentaFabric version mismatch';
  end if;
  if p_event #>> '{mesh,chlom,binding}' <> 'crownthrive.chlom.pentafabric.v1' then
    raise exception 'PENTA_CONTRACT: CHLOM binding mismatch';
  end if;
  if coalesce((p_event #>> '{mesh,chlom,governed}')::boolean, false) is not true then
    raise exception 'PENTA_CONTRACT: CHLOM governed=true is required';
  end if;
  if nullif(p_event #>> '{mesh,chlom,intent_id}','') is null then
    raise exception 'PENTA_CONTRACT: CHLOM intent_id is required';
  end if;
  if coalesce(p_event #>> '{integrity,digest}','') !~ '^[a-f0-9]{64}$' then
    raise exception 'PENTA_CONTRACT: integrity digest must be 64 lowercase hex characters';
  end if;
  if coalesce(p_event #>> '{data,status}','') not in ('DELIVERED','ADMITTED','ACKED') then
    raise exception 'PENTA_CONTRACT: delivery status is invalid';
  end if;
  return p_event;
end;
$$;

revoke all on function penta_runtime.validate_penta_envelope_v1(jsonb) from public;
grant execute on function penta_runtime.validate_penta_envelope_v1(jsonb) to service_role;

update penta_runtime.component_registry_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'output_packet_name', 'Penta',
      'output_contract_required', 'crownthrive.penta.event.v1',
      'pentafabric_schema_required', 'crownthrive.pentafabric.v1',
      'chlom_binding_required', 'crownthrive.chlom.pentafabric.v1',
      'delivery_fabric_required', 'ct.fabric.penta.v1',
      'output_validator', 'penta_runtime.validate_penta_envelope_v1(jsonb)',
      'packet_contract_bound_at', now()
    ),
    updated_at = now()
where enabled is true and implementation_state = 'active';

update penta_runtime.component_registry_v1
set metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object(
      'route_pentas_only', true,
      'canonical_delivery_event', 'penta.relay.forwarded',
      'canonical_delivery_status', 'DELIVERED',
      'packet_ingress', 'Vercel:/penta',
      'evidence_ledger', 'public.pentafabric_events'
    ),
    updated_at = now()
where component_key in ('penta.fabric','penta.wire');

create or replace function penta_runtime.penta_output_contract_status_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, penta_runtime
as $$
  select jsonb_build_object(
    'service','ct.penta.output-contract.v1',
    'packet_name','Penta',
    'event_contract','crownthrive.penta.event.v1',
    'fabric_schema','crownthrive.pentafabric.v1',
    'chlom_binding','crownthrive.chlom.pentafabric.v1',
    'active_components',count(*) filter (where enabled is true and implementation_state='active'),
    'contract_bound_components',count(*) filter (
      where enabled is true
        and implementation_state='active'
        and metadata ->> 'output_contract_required' = 'crownthrive.penta.event.v1'
        and metadata ->> 'pentafabric_schema_required' = 'crownthrive.pentafabric.v1'
        and metadata ->> 'chlom_binding_required' = 'crownthrive.chlom.pentafabric.v1'
    ),
    'state',case when count(*) filter (where enabled is true and implementation_state='active') = count(*) filter (
      where enabled is true
        and implementation_state='active'
        and metadata ->> 'output_contract_required' = 'crownthrive.penta.event.v1'
        and metadata ->> 'pentafabric_schema_required' = 'crownthrive.pentafabric.v1'
        and metadata ->> 'chlom_binding_required' = 'crownthrive.chlom.pentafabric.v1'
    ) then 'PASS' else 'HOLD' end,
    'generated_at',now()
  )
  from penta_runtime.component_registry_v1;
$$;

revoke all on function penta_runtime.penta_output_contract_status_v1() from public;
grant execute on function penta_runtime.penta_output_contract_status_v1() to service_role;
