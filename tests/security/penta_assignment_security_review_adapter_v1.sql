-- Transactional deterministic / negative acceptance for
-- 20260907211000_penta_assignment_security_review_adapter_v1.sql.
--
-- This test never manufactures PentaSecurity PASS, CHLOM/CIE disposition,
-- independent certification, release authority or provider mutation.

begin;

do $$
declare
  v_count integer;
  v_def text;
  v_result jsonb;
  v_non_security_assignment uuid;
begin
  select count(*) into v_count
  from penta_security.provider_source_policies_v1
  where policy_key in (
    'ct.penta.security.assignment-migration.20260831093500.v1',
    'ct.penta.security.assignment-migration.20260831135000.v1',
    'ct.penta.security.assignment-migration.20260831143500.v1',
    'ct.penta.security.assignment-migration.20260831154500.v1'
  )
    and policy_version='1.0.0'
    and state='active'
    and authority_effect='none'
    and repository='crownthrive1/CrownThrive-OS';
  if v_count<>4 then raise exception 'expected four active authority-neutral source policies, got %',v_count; end if;

  if exists(
    select 1 from penta_security.provider_source_policies_v1
    where policy_key like 'ct.penta.security.assignment-migration.%'
      and policy_version='1.0.0'
      and (
        authority_effect<>'none'
        or source_path ~ '(^/|\.\.)'
        or max_source_bytes<1
        or max_source_bytes>2000000
      )
  ) then
    raise exception 'assignment source policy boundary invalid';
  end if;

  select pg_get_functiondef('penta_security.review_assignment_exact_subject_v1(uuid)'::regprocedure) into v_def;
  if strpos(v_def,'pg_try_advisory_xact_lock')=0 then raise exception 'adapter must use bounded concurrency guard'; end if;
  if strpos(v_def,'PENTASECURITY_NOT_ASSIGNED_OWNER')=0 then raise exception 'adapter must reject non-owner assignment'; end if;
  if strpos(v_def,'ASSIGNMENT_AUTHORITY_BOUNDARY')=0 then raise exception 'adapter must enforce D0-D2/no-reserved-effects boundary'; end if;
  if strpos(v_def,'EXACT_SUBJECT_REQUIRED')=0 then raise exception 'adapter must require exact head and subject digest'; end if;
  if strpos(v_def,'EXACT_MIGRATION_MANIFEST_REQUIRED')=0 then raise exception 'adapter must bind exact migration manifest'; end if;
  if strpos(v_def,'review_github_provider_source_v1')=0 then raise exception 'adapter must use PentaSecurity exact-head provider source reviews'; end if;
  if strpos(v_def,'penta_assignment_record_owner_result_v1')=0 then raise exception 'adapter must use canonical owner-result sink'; end if;
  if strpos(v_def,'penta_assignment_bind_release_gate_v1')=0 then raise exception 'adapter must use exact-subject release-gate binding'; end if;
  if strpos(v_def,'ct.penta.release-gate.receipt.v1')=0 then raise exception 'adapter must emit hardened release-gate receipt contract'; end if;
  if strpos(v_def,'''independent_certification'',false')=0 then raise exception 'adapter must not claim independent certification'; end if;
  if strpos(v_def,'''release_authorized'',false')=0 then raise exception 'adapter must not create release authority'; end if;
  if strpos(v_def,'''authority_created'',false')=0 then raise exception 'adapter must remain authority-neutral'; end if;

  v_result:=penta_security.review_assignment_exact_subject_v1(gen_random_uuid());
  if v_result->>'state'<>'HOLD' or v_result->>'reason'<>'ASSIGNMENT_NOT_FOUND' then
    raise exception 'unknown assignment must fail closed: %',v_result;
  end if;
  if coalesce((v_result->>'authority_created')::boolean,true) then
    raise exception 'unknown assignment HOLD must create no authority: %',v_result;
  end if;

  select assignment_id into v_non_security_assignment
  from integration_control.penta_assignment_contracts_v1
  where not (owner_pentas ? 'PentaSecurity')
    and state not in ('COMPLETED','SUPERSEDED','RETIRED')
  order by created_at desc
  limit 1;

  if v_non_security_assignment is not null then
    v_result:=penta_security.review_assignment_exact_subject_v1(v_non_security_assignment);
    if v_result->>'state'<>'HOLD' or v_result->>'reason'<>'PENTASECURITY_NOT_ASSIGNED_OWNER' then
      raise exception 'non-owner assignment must fail closed: %',v_result;
    end if;
  end if;
end
$$;

do $$
begin
  if has_function_privilege('public','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE')
     or has_function_privilege('anon','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE')
     or has_function_privilege('authenticated','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE') then
    raise exception 'assignment review adapter must not be publicly executable';
  end if;
  if not has_function_privilege('service_role','penta_security.review_assignment_exact_subject_v1(uuid)','EXECUTE') then
    raise exception 'service_role must retain assignment review adapter execution';
  end if;
end
$$;

rollback;
