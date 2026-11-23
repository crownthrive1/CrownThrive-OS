-- Transactional deterministic / negative acceptance for
-- 20260907225700_penta_assignment_manifest_content_binding_v1.sql.
--
-- This test proves only manifest/content binding and wrapper isolation. It never
-- manufactures PentaSecurity PASS, CHLOM/CIE disposition, certification, release,
-- provider mutation, credential change, money movement, D3 action or authority expansion.

begin;

do $$
declare
  v_good jsonb:='[
    {"version":"20260831154500","blob":"38271658d7636ea904a246bac80263c9c86d3639"},
    {"version":"20260831093500","blob":"3aeaedbbfdde2224cbe82ee4ffcdd852fd4fa9d8"},
    {"version":"20260831143500","blob":"69be05c061489370353f23dfab0882b4ca15097f"},
    {"version":"20260831135000","blob":"596514b2c5db42a20b13855292bbe3013601e74c"}
  ]'::jsonb;
  v_duplicate jsonb:='[
    {"version":"20260831093500","blob":"3aeaedbbfdde2224cbe82ee4ffcdd852fd4fa9d8"},
    {"version":"20260831093500","blob":"3aeaedbbfdde2224cbe82ee4ffcdd852fd4fa9d8"},
    {"version":"20260831143500","blob":"69be05c061489370353f23dfab0882b4ca15097f"},
    {"version":"20260831154500","blob":"38271658d7636ea904a246bac80263c9c86d3639"}
  ]'::jsonb;
  v_missing jsonb:='[
    {"version":"20260831093500","blob":"3aeaedbbfdde2224cbe82ee4ffcdd852fd4fa9d8"},
    {"version":"20260831135000","blob":"596514b2c5db42a20b13855292bbe3013601e74c"},
    {"version":"20260831143500","blob":"69be05c061489370353f23dfab0882b4ca15097f"}
  ]'::jsonb;
  v_substitution jsonb:='[
    {"version":"20260831093500","blob":"3aeaedbbfdde2224cbe82ee4ffcdd852fd4fa9d8"},
    {"version":"20260831135000","blob":"596514b2c5db42a20b13855292bbe3013601e74c"},
    {"version":"20260831143500","blob":"69be05c061489370353f23dfab0882b4ca15097f"},
    {"version":"20260831160000","blob":"38271658d7636ea904a246bac80263c9c86d3639"}
  ]'::jsonb;
  v_normalized jsonb;
  v_envelope jsonb;
  v_sha text;
  v_result jsonb;
  v_def text;
begin
  select jsonb_agg(
    jsonb_build_object('version',e->>'version','blob',e->>'blob')
    order by e->>'version'
  ) into v_normalized
  from jsonb_array_elements(v_good) e;

  v_envelope:=jsonb_build_object(
    'contract','ct.penta.security.assignment-migration-manifest.v1',
    'source_repo','crownthrive1/CrownThrive-OS',
    'exact_head_sha','27932acd343f9ae9a283f2f01d98fb892d8df652',
    'migrations',v_normalized
  );
  v_sha:=encode(extensions.digest(convert_to(v_envelope::text,'UTF8'),'sha256'),'hex');

  v_result:=penta_security.verify_assignment_migration_manifest_v1(
    'crownthrive1/CrownThrive-OS',
    '27932acd343f9ae9a283f2f01d98fb892d8df652',
    v_good,
    v_sha,
    v_sha
  );
  if v_result->>'state'<>'PASS' then
    raise exception 'canonical unordered manifest must normalize and PASS: %',v_result;
  end if;
  if v_result->>'computed_manifest_sha256'<>v_sha then
    raise exception 'canonical manifest digest mismatch: %',v_result;
  end if;

  v_result:=penta_security.verify_assignment_migration_manifest_v1(
    'crownthrive1/CrownThrive-OS',
    '27932acd343f9ae9a283f2f01d98fb892d8df652',
    v_good,
    repeat('0',64),
    repeat('0',64)
  );
  if v_result->>'state'<>'HOLD' or v_result->>'reason'<>'MIGRATION_MANIFEST_DIGEST_MISMATCH' then
    raise exception 'stale/foreign digest must HOLD: %',v_result;
  end if;

  v_result:=penta_security.verify_assignment_migration_manifest_v1(
    'crownthrive1/CrownThrive-OS',
    '27932acd343f9ae9a283f2f01d98fb892d8df652',
    v_duplicate,
    repeat('0',64),
    repeat('0',64)
  );
  if v_result->>'state'<>'HOLD' or v_result->>'reason'<>'MIGRATION_MANIFEST_DUPLICATE_VERSION' then
    raise exception 'duplicate supported migration version must HOLD: %',v_result;
  end if;

  v_result:=penta_security.verify_assignment_migration_manifest_v1(
    'crownthrive1/CrownThrive-OS',
    '27932acd343f9ae9a283f2f01d98fb892d8df652',
    v_missing,
    repeat('0',64),
    repeat('0',64)
  );
  if v_result->>'state'<>'HOLD' or v_result->>'reason'<>'MIGRATION_MANIFEST_REQUIRED_SET_MISMATCH' then
    raise exception 'missing expected cohort member must HOLD: %',v_result;
  end if;

  v_result:=penta_security.verify_assignment_migration_manifest_v1(
    'crownthrive1/CrownThrive-OS',
    '27932acd343f9ae9a283f2f01d98fb892d8df652',
    v_substitution,
    repeat('0',64),
    repeat('0',64)
  );
  if v_result->>'state'<>'HOLD' or v_result->>'reason'<>'MIGRATION_MANIFEST_REQUIRED_SET_MISMATCH' then
    raise exception 'supported-version substitution must HOLD: %',v_result;
  end if;

  select pg_get_functiondef('penta_security.review_assignment_exact_subject_v1(uuid)'::regprocedure)
    into v_def;
  if strpos(v_def,'verify_assignment_migration_manifest_v1')=0
     or strpos(v_def,'review_assignment_exact_subject_unbound_v1')=0
     or strpos(v_def,'manifest_content_bound')=0 then
    raise exception 'canonical wrapper must verify manifest before invoking exact-source core';
  end if;

  if has_function_privilege('public','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE')
     or has_function_privilege('anon','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE')
     or has_function_privilege('authenticated','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE') then
    raise exception 'canonical assignment review wrapper must not be publicly executable';
  end if;
  if not has_function_privilege('service_role','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE') then
    raise exception 'service_role must retain canonical wrapper execution';
  end if;
  if has_function_privilege('service_role','penta_security.review_assignment_exact_subject_unbound_v1(uuid)','EXECUTE') then
    raise exception 'service_role must not bypass manifest wrapper through unbound core';
  end if;
end
$$;

rollback;