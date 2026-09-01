-- Transactional acceptance/negative tests for
-- ct.penta.security.provider-source-review.v1.
-- No persistent production effect: callers execute this suite inside its
-- explicit transaction and the final ROLLBACK removes test receipts/DAIL rows.

begin;

do $test$
declare
  v_pass jsonb;
  v_negative jsonb;
  v_mutation_blocked boolean:=false;
begin
  v_pass:=penta_security.review_github_provider_source_v1(
    'ct.penta.security.policy.institutional-pr-terminal-provider.v1',
    'efc40a379a99f6183a3149a5f4c6ea646a1d6c9a'
  );

  if v_pass->>'disposition'<>'PASS' then
    raise exception 'EXPECTED_PROVIDER_SOURCE_PASS:%',v_pass;
  end if;
  if v_pass->>'source_sha256'<>'2d9145c5884a704c24b079be79fa774a115f0d1fe2b53c6a65fae2d27cf9251c' then
    raise exception 'EXACT_SOURCE_DIGEST_MISMATCH:%',v_pass->>'source_sha256';
  end if;
  if coalesce((v_pass->>'raw_source_stored')::boolean,true) then
    raise exception 'RAW_SOURCE_RETENTION_NOT_ALLOWED';
  end if;
  if coalesce((v_pass->>'provider_write')::boolean,true)
     or coalesce((v_pass->>'credential_change')::boolean,true)
     or coalesce((v_pass->>'money_movement')::boolean,true)
     or coalesce((v_pass->>'d3_execution')::boolean,true)
     or coalesce((v_pass->>'authority_expansion')::boolean,true) then
    raise exception 'PROVIDER_REVIEW_EXCEEDED_AUTHORITY_BOUNDARY';
  end if;
  if coalesce((v_pass->>'independent_certification')::boolean,true) then
    raise exception 'SECURITY_DECISION_MUST_NOT_SELF_CERTIFY';
  end if;
  if nullif(v_pass->>'dail_event_id','') is null or nullif(v_pass->>'dail_event_hash','') is null then
    raise exception 'DAIL_PROVIDER_SECURITY_READBACK_MISSING';
  end if;

  -- Negative exact-head read: syntactically valid SHA, nonexistent immutable
  -- object. Must fail closed instead of falling back to a branch/default head.
  v_negative:=penta_security.review_github_provider_source_v1(
    'ct.penta.security.policy.institutional-pr-terminal-provider.v1',
    '0000000000000000000000000000000000000000'
  );
  if v_negative->>'disposition'<>'HOLD_SOURCE_FETCH_FAILED' then
    raise exception 'NONEXISTENT_EXACT_HEAD_DID_NOT_FAIL_CLOSED:%',v_negative;
  end if;

  -- Policy rows are append-only. A new version is required for control drift.
  begin
    update penta_security.provider_source_policies_v1
       set max_source_bytes=max_source_bytes+1
     where policy_key='ct.penta.security.policy.institutional-pr-terminal-provider.v1'
       and policy_version='1.0.0';
  exception when others then
    v_mutation_blocked:=true;
  end;
  if not v_mutation_blocked then
    raise exception 'PROVIDER_SOURCE_POLICY_MUTATION_NOT_BLOCKED';
  end if;

  if has_function_privilege('public','penta_security.review_github_provider_source_v1(text,text)','EXECUTE')
     or has_function_privilege('anon','penta_security.review_github_provider_source_v1(text,text)','EXECUTE')
     or has_function_privilege('authenticated','penta_security.review_github_provider_source_v1(text,text)','EXECUTE') then
    raise exception 'PROVIDER_SOURCE_REVIEW_EXECUTE_EXPOSURE';
  end if;
  if not has_function_privilege('service_role','penta_security.review_github_provider_source_v1(text,text)','EXECUTE') then
    raise exception 'PROVIDER_SOURCE_REVIEW_SERVICE_ROLE_MISSING';
  end if;
end
$test$;

rollback;
