-- Rollback for PentaWire Unsplash secure-read adapter v1.
-- Removes only the helper and the exact adapter contract introduced by the matching migration.
-- Existing Unsplash provider broker/runtime is preserved untouched.

drop function if exists integration_control.penta_wire_unsplash_secure_read_v1(text,jsonb);

delete from integration_control.penta_wire_read_adapters_v1
where service_id='unsplash_crownthrive_studios'
  and adapter_kind='SECURE_HTTP'
  and exact_contract='ct.penta.wire.secure.unsplash-crownthrive-studios.v1'
  and transport_ref='edge:unsplash-image-control';
