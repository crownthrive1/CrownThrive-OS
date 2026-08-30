-- PentaSuper DND-on-demand semantics + task-runtime least-privilege hardening v1.
-- This migration narrows authority. It does not certify PentaSuper or create D3/provider-write authority.

begin;

-- The full acceptance matrix is an internal mutating verification surface.
-- A function-body role check is defense in depth; the entrypoint ACL itself must also be least privilege.
revoke all on function penta_task_runtime.run_full_acceptance_matrix_v3(text) from public;
revoke execute on function penta_task_runtime.run_full_acceptance_matrix_v3(text) from anon;
revoke execute on function penta_task_runtime.run_full_acceptance_matrix_v3(text) from authenticated;
grant execute on function penta_task_runtime.run_full_acceptance_matrix_v3(text) to service_role;

-- Institutional semantics: PentaDND is an on-demand scoped TTL maintenance/isolation window.
-- PentaSuper remains operational without DND and uses lease/CAS/collision fencing for ordinary ownership.
update public.penta_system_registry
set metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'dnd_mode','on_demand_ttl_isolation',
      'dnd_required_for_every_tick',false,
      'read_only_preflight_without_dnd',true,
      'ordinary_mutation_ownership','penta_lease_cas_collision',
      'scheduler_tick_creates_dnd',false,
      'authority_created',false
    ),
    updated_at = clock_timestamp(),
    last_verified_at = clock_timestamp()
where system_key='penta.super';

update public.penta_system_registry
set metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
      'activation_mode','explicit_on_demand',
      'lease_semantics','scoped_ttl_maintenance_isolation',
      'global_maintenance_mode',false,
      'scheduler_tick_creates_lease',false,
      'authority_created',false
    ),
    updated_at = clock_timestamp(),
    last_verified_at = clock_timestamp()
where system_key='penta.dnd';

-- Deterministic negative authority checks. Fail closed if the ACL is not actually narrowed.
do $$
begin
  if has_function_privilege('public','penta_task_runtime.run_full_acceptance_matrix_v3(text)','execute') then
    raise exception 'pentasuper_acl_hardening_failed: PUBLIC retains execute';
  end if;
  if has_function_privilege('anon','penta_task_runtime.run_full_acceptance_matrix_v3(text)','execute') then
    raise exception 'pentasuper_acl_hardening_failed: anon retains execute';
  end if;
  if has_function_privilege('authenticated','penta_task_runtime.run_full_acceptance_matrix_v3(text)','execute') then
    raise exception 'pentasuper_acl_hardening_failed: authenticated retains execute';
  end if;
  if not has_function_privilege('service_role','penta_task_runtime.run_full_acceptance_matrix_v3(text)','execute') then
    raise exception 'pentasuper_acl_hardening_failed: service_role missing execute';
  end if;
end
$$;

commit;
