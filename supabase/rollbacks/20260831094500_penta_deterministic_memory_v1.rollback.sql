-- CrownThrive Penta deterministic memory fabric v1 containment rollback
-- Preserves every allocation, memory record, PentaContext record, replay receipt,
-- lifecycle event, and census receipt. It removes write capability and marks the
-- projections held; it does not manufacture a prior-state PASS.

begin;

-- Stop new allocation, semantic ingest, arbitrary append, and replay writes.
revoke execute on function penta_runtime.penta_memory_reconcile_v1() from service_role;
revoke execute on function penta_runtime.penta_memory_append_v1(text,text,text,text,jsonb,text,uuid,text,jsonb,uuid) from service_role;
revoke execute on function penta_runtime.penta_memory_remember_v1(text,text,text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz) from service_role;
revoke execute on function penta_runtime.penta_memory_context_query_v1(text,text,text,integer,integer,text[],text) from service_role;
revoke execute on function penta_runtime.penta_deterministic_replay_record_v1(text,text,text,text,text,text,text,text,text,text,text,jsonb) from service_role;

-- Add one hash-chained containment event per namespace and retain the evidence.
do $$
declare
  r record;
begin
  for r in
    select identity_key, namespace_key, allocation_sha256
    from penta_runtime.penta_memory_namespaces_v1
    where current and memory_state <> 'ROLLBACK_HOLD'
    order by identity_key
  loop
    perform penta_runtime.penta_memory_lifecycle_append_v1(
      r.identity_key,
      'ROLLBACK_HOLD',
      'ROLLBACK_HOLD',
      jsonb_build_object(
        'namespace_key', r.namespace_key,
        'allocation_sha256', r.allocation_sha256,
        'rollback_contract', 'ct.penta.deterministic-memory.v1.containment',
        'preserve_records', true,
        'authority_created', false
      )
    );
  end loop;
end;
$$;

update penta_runtime.penta_memory_namespaces_v1
set memory_state='ROLLBACK_HOLD', write_enabled=false
where current;

update penta_runtime.penta_memory_family_grants_v1
set current=false
where current;

update integration_control.penta_census_entities_v1
set lifecycle_state='ROLLBACK_HOLD', current=false, last_seen_at=now()
where entity_kind='PENTA_MEMORY_NAMESPACE';

update pentamocracy.universal_penta_census_v1
set lifecycle_state='ROLLBACK_HOLD', last_accounted_at=now()
where source_kind='penta_memory_namespace';

update integration_control.penta_identity_registry_v1
set metadata = metadata
  - 'deterministic_memory_bound'
  - 'memory_contract'
  - 'memory_namespace'
  - 'memory_profile'
  - 'memory_write_enabled'
  - 'memory_allocation_sha256'
  - 'memory_authority_expansion'
where current and metadata ? 'deterministic_memory_bound';

update integration_control.penta_family_runtime_v1
set metadata = metadata
  - 'deterministic_memory_bound'
  - 'memory_contract'
  - 'memory_mesh_role'
  - 'memory_cross_family_write'
  - 'memory_authority_expansion'
where metadata ? 'deterministic_memory_bound';

update public.penta_runtime_activations
set metadata = metadata
  - 'deterministic_memory_bound'
  - 'memory_namespace'
  - 'memory_profile'
  - 'memory_contract',
  updated_at=now()
where penta='penta.brain';

-- Read-only evidence remains available to the server role for recovery/readback.
grant execute on function penta_runtime.penta_memory_health_v1() to service_role;
grant execute on function penta_runtime.penta_memory_read_v1(text,text,integer,text) to service_role;

commit;
