-- Production containment for internal SECURITY DEFINER surfaces.
-- Canonical provider migration: 20260828000306_contain_internal_security_definer_surfaces_v2_20260828.
--
-- Internal schemas default to service-role execution only. Public/anon/authenticated
-- execution must be explicitly granted by a later reviewed migration when a function
-- is intentionally a direct client RPC.

do $$
declare r record;
begin
  for r in
    select p.oid::regprocedure as signature
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where p.prosecdef
      and n.nspname in (
        'penta_runtime',
        'integration_control',
        'chlom_runtime',
        'os_v2',
        'penta_help',
        'chlom_identity',
        'developer_commerce'
      )
  loop
    execute format(
      'revoke execute on function %s from public, anon, authenticated',
      r.signature
    );
    execute format(
      'grant execute on function %s to service_role',
      r.signature
    );
  end loop;
end $$;

alter view chlom_runtime.construction_gate_current set (security_invoker = true);

alter default privileges for role postgres in schema penta_runtime
  revoke execute on functions from public;
alter default privileges for role postgres in schema integration_control
  revoke execute on functions from public;
alter default privileges for role postgres in schema chlom_runtime
  revoke execute on functions from public;
alter default privileges for role postgres in schema os_v2
  revoke execute on functions from public;
alter default privileges for role postgres in schema penta_help
  revoke execute on functions from public;
alter default privileges for role postgres in schema chlom_identity
  revoke execute on functions from public;
alter default privileges for role postgres in schema developer_commerce
  revoke execute on functions from public;

alter default privileges for role postgres in schema penta_runtime
  grant execute on functions to service_role;
alter default privileges for role postgres in schema integration_control
  grant execute on functions to service_role;
alter default privileges for role postgres in schema chlom_runtime
  grant execute on functions to service_role;
alter default privileges for role postgres in schema os_v2
  grant execute on functions to service_role;
alter default privileges for role postgres in schema penta_help
  grant execute on functions to service_role;
alter default privileges for role postgres in schema chlom_identity
  grant execute on functions to service_role;
alter default privileges for role postgres in schema developer_commerce
  grant execute on functions to service_role;
