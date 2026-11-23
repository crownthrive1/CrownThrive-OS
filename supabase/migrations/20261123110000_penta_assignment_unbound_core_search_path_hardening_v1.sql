-- PentaSecurity internal SECURITY DEFINER core search-path hardening.
-- Source candidate only: do not apply until authoritative provider continuity is independently verified.
-- The core body schema-qualifies its public, chlom_runtime, and extensions references.
-- Rollback reference (not executed): restore the prior broad search_path only under explicit security approval.
-- ALTER FUNCTION penta_security.review_assignment_exact_subject_unbound_v1(uuid)
--   SET search_path TO 'pg_catalog','penta_security','integration_control','public','chlom_runtime','extensions';

begin;

do $preflight$
begin
  if to_regprocedure('penta_security.review_assignment_exact_subject_unbound_v1(uuid)') is null then
    raise exception 'PENTASECURITY_UNBOUND_CORE_MISSING';
  end if;
  if exists (
    select 1
    from pg_namespace n
    cross join lateral aclexplode(coalesce(n.nspacl, acldefault('n', n.nspowner))) acl
    where n.nspname in ('penta_security', 'integration_control')
      and acl.grantee = 0
      and acl.privilege_type = 'CREATE'
  ) then
    raise exception 'PENTASECURITY_PROTECTED_SCHEMA_PUBLIC_CREATE';
  end if;

  if has_schema_privilege('anon', 'penta_security', 'CREATE')
     or has_schema_privilege('authenticated', 'penta_security', 'CREATE')
     or has_schema_privilege('service_role', 'penta_security', 'CREATE')
     or has_schema_privilege('anon', 'integration_control', 'CREATE')
     or has_schema_privilege('authenticated', 'integration_control', 'CREATE')
     or has_schema_privilege('service_role', 'integration_control', 'CREATE') then
    raise exception 'PENTASECURITY_PROTECTED_SCHEMA_RUNTIME_CREATE';
  end if;
end
$preflight$;

alter function penta_security.review_assignment_exact_subject_unbound_v1(uuid)
  set search_path to 'pg_catalog','penta_security','integration_control';

do $verify$
declare
  v_prosecdef boolean;
  v_proconfig text;
begin
  select
    p.prosecdef,
    regexp_replace(coalesce(array_to_string(p.proconfig, ','), ''), '[[:space:]]', '', 'g')
  into v_prosecdef, v_proconfig
  from pg_proc p
  where p.oid = 'penta_security.review_assignment_exact_subject_unbound_v1(uuid)'::regprocedure;

  if not coalesce(v_prosecdef, false) then
    raise exception 'PENTASECURITY_UNBOUND_CORE_NOT_SECURITY_DEFINER';
  end if;
  if v_proconfig <> 'search_path=pg_catalog,penta_security,integration_control' then
    raise exception 'PENTASECURITY_UNBOUND_CORE_SEARCH_PATH_MISMATCH: %', v_proconfig;
  end if;

  if has_function_privilege('public', 'penta_security.review_assignment_exact_subject_unbound_v1(uuid)', 'EXECUTE')
     or has_function_privilege('anon', 'penta_security.review_assignment_exact_subject_unbound_v1(uuid)', 'EXECUTE')
     or has_function_privilege('authenticated', 'penta_security.review_assignment_exact_subject_unbound_v1(uuid)', 'EXECUTE')
     or has_function_privilege('service_role', 'penta_security.review_assignment_exact_subject_unbound_v1(uuid)', 'EXECUTE') then
    raise exception 'PENTASECURITY_UNBOUND_CORE_MUST_NOT_BE_RUNTIME_EXECUTABLE';
  end if;
end
$verify$;

commit;
