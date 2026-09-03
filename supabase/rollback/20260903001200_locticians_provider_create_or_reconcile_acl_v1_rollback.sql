-- Fail-closed recovery for 20260903001200_locticians_provider_create_or_reconcile_acl_v1.sql.
-- Security containment is monotonic: recovery MUST NOT reopen PUBLIC/anon/authenticated
-- execution. It verifies exact function bytes and reasserts the safe service-only ACL.

do $guard$
declare
  v_oid oid;
  v_hash text;
begin
  v_oid := pg_catalog.to_regprocedure('integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)');
  if v_oid is null then
    raise exception 'target function missing';
  end if;

  select pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid), 'UTF8'),
             'sha256'
           ),
           'hex'
         )
    into v_hash
  from pg_catalog.pg_proc p
  where p.oid = v_oid;

  if v_hash <> '3453a6b6ece69dc2d75cb1a48bf64dd11c9bd9a72a93e68ce8e6695ac4cc8947' then
    raise exception 'rollback_refuses_changed_locticians_provider_rpc: %', v_hash;
  end if;
end
$guard$;

revoke execute on function integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)
  from public, anon, authenticated;
grant execute on function integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)
  to postgres, service_role;

do $readback$
declare
  v_oid oid := 'integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)'::regprocedure::oid;
begin
  if pg_catalog.has_function_privilege('anon', v_oid, 'EXECUTE') then
    raise exception 'anon_execute_present';
  end if;
  if pg_catalog.has_function_privilege('authenticated', v_oid, 'EXECUTE') then
    raise exception 'authenticated_execute_present';
  end if;
  if not pg_catalog.has_function_privilege('service_role', v_oid, 'EXECUTE') then
    raise exception 'service_role_execute_missing';
  end if;
  if not pg_catalog.has_function_privilege('postgres', v_oid, 'EXECUTE') then
    raise exception 'postgres_execute_missing';
  end if;
end
$readback$;
