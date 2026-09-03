-- Guarded rollback for 20260903001200_locticians_provider_create_or_reconcile_acl_v1.sql.
-- Restores the exact prior privilege shape only if target function bytes are unchanged.

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
    raise exception 'target function definition drift: %', v_hash;
  end if;
end
$guard$;

grant execute on function integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)
  to public, postgres, service_role;

do $readback$
declare
  v_oid oid := 'integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)'::regprocedure::oid;
begin
  if not pg_catalog.has_function_privilege('anon', v_oid, 'EXECUTE') then
    raise exception 'rollback did not restore PUBLIC/anon EXECUTE';
  end if;
  if not pg_catalog.has_function_privilege('authenticated', v_oid, 'EXECUTE') then
    raise exception 'rollback did not restore PUBLIC/authenticated EXECUTE';
  end if;
  if not pg_catalog.has_function_privilege('service_role', v_oid, 'EXECUTE') then
    raise exception 'service_role EXECUTE missing after rollback';
  end if;
end
$readback$;
