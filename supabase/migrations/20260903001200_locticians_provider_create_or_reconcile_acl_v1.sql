-- PentaSecurity S13: least-privilege containment for a provider-writing SECURITY DEFINER RPC.
-- Exact production prestate at discovery:
--   integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)
--   definition SHA-256: 3453a6b6ece69dc2d75cb1a48bf64dd11c9bd9a72a93e68ce8e6695ac4cc8947
--   owner=postgres; PUBLIC EXECUTE present; service_role EXECUTE present.
-- Five known database callers are already service-role-only.
-- This migration changes privileges only. Function bytes and provider behavior are unchanged.

do $guard$
declare
  v_oid oid;
  v_hash text;
  v_secdef boolean;
begin
  v_oid := pg_catalog.to_regprocedure('integration_control.locticians_universal_provider_create_or_reconcile_v4(uuid)');
  if v_oid is null then
    raise exception 'target function missing';
  end if;

  select p.prosecdef,
         pg_catalog.encode(
           extensions.digest(
             pg_catalog.convert_to(pg_catalog.pg_get_functiondef(p.oid), 'UTF8'),
             'sha256'
           ),
           'hex'
         )
    into v_secdef, v_hash
  from pg_catalog.pg_proc p
  where p.oid = v_oid;

  if v_secdef is distinct from true then
    raise exception 'target function is no longer SECURITY DEFINER';
  end if;
  if v_hash <> '3453a6b6ece69dc2d75cb1a48bf64dd11c9bd9a72a93e68ce8e6695ac4cc8947' then
    raise exception 'target function definition drift: %', v_hash;
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
    raise exception 'anon EXECUTE remains enabled';
  end if;
  if pg_catalog.has_function_privilege('authenticated', v_oid, 'EXECUTE') then
    raise exception 'authenticated EXECUTE remains enabled';
  end if;
  if not pg_catalog.has_function_privilege('service_role', v_oid, 'EXECUTE') then
    raise exception 'service_role EXECUTE missing';
  end if;
  if not pg_catalog.has_function_privilege('postgres', v_oid, 'EXECUTE') then
    raise exception 'postgres EXECUTE missing';
  end if;
end
$readback$;
