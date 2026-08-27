create or replace function penta_runtime.enforce_penta_output_contract_v1()
returns trigger
language plpgsql
security invoker
set search_path = pg_catalog
as $$
begin
  if new.enabled is true and new.implementation_state = 'active' then
    new.metadata := coalesce(new.metadata, '{}'::jsonb) || jsonb_build_object(
      'output_packet_name', 'Penta',
      'output_contract_required', 'crownthrive.penta.event.v1',
      'pentafabric_schema_required', 'crownthrive.pentafabric.v1',
      'chlom_binding_required', 'crownthrive.chlom.pentafabric.v1',
      'delivery_fabric_required', 'ct.fabric.penta.v1',
      'output_validator', 'penta_runtime.validate_penta_envelope_v1(jsonb)',
      'packet_contract_enforced', true,
      'packet_contract_bound_at', now()
    );
  end if;
  return new;
end;
$$;

revoke all on function penta_runtime.enforce_penta_output_contract_v1() from public;

drop trigger if exists component_registry_require_penta_output_v1
  on penta_runtime.component_registry_v1;

create trigger component_registry_require_penta_output_v1
before insert or update of enabled, implementation_state, metadata
on penta_runtime.component_registry_v1
for each row
execute function penta_runtime.enforce_penta_output_contract_v1();

update penta_runtime.component_registry_v1
set metadata = metadata
where enabled is true and implementation_state = 'active';
