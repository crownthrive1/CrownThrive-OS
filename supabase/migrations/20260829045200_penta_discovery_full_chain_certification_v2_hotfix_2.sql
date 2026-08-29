do $patch$
declare
  v_ddl text;
  v_patched text;
begin
  select pg_get_functiondef('penta_runtime.certify_penta_discovery_family_v2(text,text,text)'::regprocedure)
    into v_ddl;

  v_patched := replace(
    v_ddl,
    E'penta_route_anti_abuse_policy_v2\n      where state = ''active''',
    E'penta_route_anti_abuse_policy_v2\n      where governance_state = ''active'''
  );

  if v_patched = v_ddl
     and position(E'penta_route_anti_abuse_policy_v2\n      where governance_state = ''active''' in v_ddl) = 0 then
    raise exception 'PENTA_DISCOVERY_CERT_V2_ANTI_ABUSE_PATCH_TARGET_NOT_FOUND';
  end if;

  if v_patched <> v_ddl then
    execute v_patched;
  end if;
end
$patch$;
