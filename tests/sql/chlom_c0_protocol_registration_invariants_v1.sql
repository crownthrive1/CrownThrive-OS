-- CHLOM-C0-0002 deterministic registration invariants.
-- Run against a database containing migration 20260831211500, inside an isolated
-- transaction. The script intentionally rolls back all test-only vault/assets/receipts.

begin;

do $test$
declare
  v_owner text := 'ct.agent.execution-builder';
  v_verifier text;
  v_protocol text := 'ct.protocol.c0-registration-invariant-test';
  v_source text := 'test:CHLOM-C0-0002';
  v_body jsonb := '{"kernel":"c0","tenant":"test","contract":"registration-cas","revision":1}'::jsonb;
  v_body_conflict jsonb := '{"kernel":"c0","tenant":"test","contract":"registration-cas","revision":2}'::jsonb;
  v_expected_digest text;
  v_wrong_digest text := repeat('0',64);
  v_first jsonb;
  v_same jsonb;
  v_conflict jsonb;
  v_cas_mismatch jsonb;
  v_missing jsonb;
  v_receipt_count integer;
begin
  select agent_id into v_verifier
    from chlom_runtime.agent_templates
   where agent_id <> v_owner
   order by agent_id
   limit 1;

  if v_verifier is null then
    raise exception 'TEST_SETUP_NO_INDEPENDENT_VERIFIER';
  end if;

  v_expected_digest := encode(extensions.digest(v_body::text,'sha256'),'hex');

  v_first := chlom_runtime.register_proprietary_protocol_v2(
    v_protocol,'CHLOM C0 Registration Invariant Test','0.0.1',v_body,
    v_owner,v_verifier,v_source,false,null
  );
  if v_first->>'state' <> 'registered_hold' then
    raise exception 'TEST_FAIL_FIRST_REGISTER:%',v_first;
  end if;
  if coalesce((v_first->>'activation_allowed')::boolean,true) then
    raise exception 'TEST_FAIL_ACTIVATION_ALLOWED';
  end if;
  if coalesce((v_first->>'body_exposed')::boolean,true) then
    raise exception 'TEST_FAIL_BODY_EXPOSED';
  end if;
  if v_first->>'public_contract_digest' <> v_expected_digest then
    raise exception 'TEST_FAIL_DIGEST';
  end if;

  v_same := chlom_runtime.register_proprietary_protocol_v2(
    v_protocol,'CHLOM C0 Registration Invariant Test','0.0.1',v_body,
    v_owner,v_verifier,v_source,false,v_expected_digest
  );
  if v_same->>'state' <> 'already_registered' or coalesce((v_same->>'mutation_applied')::boolean,true) then
    raise exception 'TEST_FAIL_IDEMPOTENT:%',v_same;
  end if;

  v_conflict := chlom_runtime.register_proprietary_protocol_v2(
    v_protocol,'CHLOM C0 Registration Invariant Test','0.0.1',v_body_conflict,
    v_owner,v_verifier,v_source,false,v_expected_digest
  );
  if v_conflict->>'state' <> 'digest_conflict' or coalesce((v_conflict->>'mutation_applied')::boolean,true) then
    raise exception 'TEST_FAIL_DIGEST_CONFLICT:%',v_conflict;
  end if;

  v_cas_mismatch := chlom_runtime.register_proprietary_protocol_v2(
    v_protocol,'CHLOM C0 Registration Invariant Test','0.0.1',v_body,
    v_owner,v_verifier,v_source,false,v_wrong_digest
  );
  if v_cas_mismatch->>'state' <> 'cas_mismatch' or coalesce((v_cas_mismatch->>'mutation_applied')::boolean,true) then
    raise exception 'TEST_FAIL_CAS_MISMATCH:%',v_cas_mismatch;
  end if;

  v_missing := chlom_runtime.register_proprietary_protocol_v2(
    'ct.protocol.c0-registration-invariant-missing','CHLOM C0 Missing Target Test','0.0.1',v_body,
    v_owner,v_verifier,v_source,false,v_wrong_digest
  );
  if v_missing->>'state' <> 'cas_target_missing' or coalesce((v_missing->>'mutation_applied')::boolean,true) then
    raise exception 'TEST_FAIL_CAS_TARGET_MISSING:%',v_missing;
  end if;

  select count(*) into v_receipt_count
    from chlom_runtime.protocol_registration_receipts_v1
   where protocol_id in (v_protocol,'ct.protocol.c0-registration-invariant-missing')
     and source_ref=v_source;
  if v_receipt_count <> 5 then
    raise exception 'TEST_FAIL_RECEIPT_COUNT:%',v_receipt_count;
  end if;

  if exists (
    select 1
      from chlom_runtime.protocol_registration_receipts_v1
     where protocol_id in (v_protocol,'ct.protocol.c0-registration-invariant-missing')
       and (body_exposed or activation_allowed)
  ) then
    raise exception 'TEST_FAIL_RECEIPT_SAFETY_FLAGS';
  end if;

  if has_function_privilege('anon',
      'chlom_runtime.register_proprietary_protocol_v2(text,text,text,jsonb,text,text,text,boolean,text)',
      'EXECUTE')
     or has_function_privilege('authenticated',
      'chlom_runtime.register_proprietary_protocol_v2(text,text,text,jsonb,text,text,text,boolean,text)',
      'EXECUTE') then
    raise exception 'TEST_FAIL_PUBLIC_EXECUTE_GRANT';
  end if;

  if has_table_privilege('anon','chlom_runtime.protocol_registration_receipts_v1','SELECT')
     or has_table_privilege('authenticated','chlom_runtime.protocol_registration_receipts_v1','SELECT') then
    raise exception 'TEST_FAIL_PUBLIC_RECEIPT_READ';
  end if;

  raise notice 'CHLOM-C0-0002 invariant tests PASS';
end
$test$;

rollback;
