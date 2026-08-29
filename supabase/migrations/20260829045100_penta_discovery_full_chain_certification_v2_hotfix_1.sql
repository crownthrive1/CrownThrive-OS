do $patch$
declare
  v_ddl text;
  v_patched text;
begin
  select pg_get_functiondef('penta_runtime.certify_penta_discovery_family_v2(text,text,text)'::regprocedure)
    into v_ddl;

  v_patched := replace(
    v_ddl,
    'select sum(actual_internal_units) = rr.actual_internal_units',
    'select sum(u.actual_internal_units) = rr.actual_internal_units'
  );

  if v_patched = v_ddl
     and position('select sum(u.actual_internal_units) = rr.actual_internal_units' in v_ddl) = 0 then
    raise exception 'PENTA_DISCOVERY_CERT_V2_EXPECTED_PATCH_TARGET_NOT_FOUND';
  end if;

  if v_patched <> v_ddl then
    execute v_patched;
  end if;
end
$patch$;
