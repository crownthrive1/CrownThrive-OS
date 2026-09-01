-- CHLOM-C2-0001 deterministic authority-lease revocation invariants.
-- Run after migration 20260831235920 in an isolated transaction.
-- All synthetic authority, lease, receipt, and DAIL rows are rolled back.

begin;

do $test$
declare
  v_founder text := 'ct.test.founder.chlom-c2';
  v_agent text := 'ct.test.agent.chlom-c2';
  v_authorization uuid;
  v_active uuid := extensions.gen_random_uuid();
  v_expired uuid := extensions.gen_random_uuid();
  v_missing uuid := extensions.gen_random_uuid();
  v_result jsonb;
  v_second jsonb;
  v_expired_result jsonb;
  v_missing_result jsonb;
  v_state text;
  v_receipts integer;
  v_raised boolean := false;
begin
  insert into chlom_runtime.archive_reverse_authorizations(
    principal_kind,principal_id,capability,scope,state,founder_granted,expires_at
  ) values (
    'founder',v_founder,'archive_reverse_verify',
    jsonb_build_object('test_only',true,'work_package','CHLOM-C2-0001'),
    'active',true,clock_timestamp()+interval '15 minutes'
  ) returning authorization_id into v_authorization;

  insert into chlom_runtime.agent_authority_leases_v1(
    lease_id,principal_kind,principal_id,capability,resource_type,resource_id,
    sensitivity_level,plaintext_return,key_material_return,state,issuer_kind,issuer_id,
    issued_at,expires_at,scope
  ) values (
    v_active,'agent',v_agent,'test.capability','test_resource','active',
    1,false,false,'active','founder',v_founder,
    clock_timestamp(),clock_timestamp()+interval '10 minutes',
    jsonb_build_object('test_only',true,'work_package','CHLOM-C2-0001')
  );

  v_result := chlom_runtime.revoke_agent_authority_lease_v1(
    v_active,'founder',v_founder,v_authorization,'TEST_REVOKE','active'
  );

  if v_result->>'state' <> 'revoked'
     or not coalesce((v_result->>'mutation_applied')::boolean,false)
     or coalesce((v_result->>'authority_created')::boolean,true)
     or v_result->>'authority_ref' <> v_authorization::text
     or v_result->>'dail_event_id' is null then
    raise exception 'TEST_FAIL_REVOKE_RESULT:%',v_result;
  end if;

  select state into v_state
    from chlom_runtime.agent_authority_leases_v1
   where lease_id=v_active;
  if v_state <> 'revoked' then
    raise exception 'TEST_FAIL_REVOKED_STATE:%',v_state;
  end if;

  v_second := chlom_runtime.revoke_agent_authority_lease_v1(
    v_active,'founder',v_founder,v_authorization,'TEST_REPLAY','active'
  );
  if v_second->>'state' <> 'already_terminal'
     or coalesce((v_second->>'mutation_applied')::boolean,true)
     or v_second->>'dail_event_id' is not null then
    raise exception 'TEST_FAIL_REPLAY:%',v_second;
  end if;

  insert into chlom_runtime.agent_authority_leases_v1(
    lease_id,principal_kind,principal_id,capability,resource_type,resource_id,
    sensitivity_level,plaintext_return,key_material_return,state,issuer_kind,issuer_id,
    issued_at,expires_at,scope
  ) values (
    v_expired,'agent',v_agent,'test.capability','test_resource','expired',
    1,false,false,'active','founder',v_founder,
    clock_timestamp()-interval '10 minutes',clock_timestamp()-interval '1 minute',
    jsonb_build_object('test_only',true,'work_package','CHLOM-C2-0001')
  );

  v_expired_result := chlom_runtime.revoke_agent_authority_lease_v1(
    v_expired,'founder',v_founder,v_authorization,'TEST_EXPIRED','active'
  );
  if v_expired_result->>'state' <> 'expired_before_revoke'
     or not coalesce((v_expired_result->>'mutation_applied')::boolean,false)
     or v_expired_result->>'dail_event_id' is not null then
    raise exception 'TEST_FAIL_EXPIRED:%',v_expired_result;
  end if;

  select state into v_state
    from chlom_runtime.agent_authority_leases_v1
   where lease_id=v_expired;
  if v_state <> 'expired' then
    raise exception 'TEST_FAIL_EXPIRED_STATE:%',v_state;
  end if;

  v_missing_result := chlom_runtime.revoke_agent_authority_lease_v1(
    v_missing,'founder',v_founder,v_authorization,'TEST_MISSING','active'
  );
  if v_missing_result->>'state' <> 'lease_not_found'
     or coalesce((v_missing_result->>'mutation_applied')::boolean,true) then
    raise exception 'TEST_FAIL_MISSING:%',v_missing_result;
  end if;

  begin
    perform chlom_runtime.revoke_agent_authority_lease_v1(
      v_missing,'agent',v_agent,v_authorization,'TEST_BAD_ACTOR','active'
    );
  exception when others then
    v_raised := position('founder_revoker_required' in sqlerrm)>0;
  end;
  if not v_raised then
    raise exception 'TEST_FAIL_NON_FOUNDER_GUARD';
  end if;

  v_raised := false;
  begin
    perform chlom_runtime.revoke_agent_authority_lease_v1(
      v_missing,'founder',v_founder,extensions.gen_random_uuid(),'TEST_BAD_AUTH','active'
    );
  exception when others then
    v_raised := position('exact_active_founder_authority_required' in sqlerrm)>0;
  end;
  if not v_raised then
    raise exception 'TEST_FAIL_EXACT_AUTHORITY_BINDING';
  end if;

  if has_function_privilege(
       'anon',
       'chlom_runtime.revoke_agent_authority_lease_v1(uuid,text,text,uuid,text,text)',
       'EXECUTE'
     )
     or has_function_privilege(
       'authenticated',
       'chlom_runtime.revoke_agent_authority_lease_v1(uuid,text,text,uuid,text,text)',
       'EXECUTE'
     ) then
    raise exception 'TEST_FAIL_PUBLIC_EXECUTE_GRANT';
  end if;

  if has_table_privilege('anon','chlom_runtime.authority_lease_revocation_receipts_v1','SELECT')
     or has_table_privilege('authenticated','chlom_runtime.authority_lease_revocation_receipts_v1','SELECT') then
    raise exception 'TEST_FAIL_PUBLIC_RECEIPT_READ';
  end if;

  select count(*) into v_receipts
    from chlom_runtime.authority_lease_revocation_receipts_v1
   where revoker_id=v_founder
     and authority_ref=v_authorization
     and reason_code in ('TEST_REVOKE','TEST_REPLAY','TEST_EXPIRED','TEST_MISSING');
  if v_receipts <> 4 then
    raise exception 'TEST_FAIL_RECEIPT_COUNT:%',v_receipts;
  end if;

  if exists (
    select 1
      from chlom_runtime.authority_lease_revocation_receipts_v1
     where revoker_id=v_founder
       and authority_created
  ) then
    raise exception 'TEST_FAIL_AUTHORITY_CREATED';
  end if;

  raise notice 'CHLOM-C2-0001 invariant tests PASS';
end
$test$;

rollback;
