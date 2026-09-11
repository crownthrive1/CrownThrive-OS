-- Transactional acceptance test for institutional pre-release certification ordering v2.
-- Uses the preserved #1995 institutional-change record as a stable integration fixture.
-- This test issues no release, provider write, D3 action, rights grant, money movement,
-- credential operation, or authority expansion. Any certification-path mutation is
-- transaction-local and rolled back.

begin;

do $$
declare
  v_change constant uuid := 'a924fba7-df3d-4337-b26a-0402b98f319c'::uuid;
  v_pre jsonb;
  v_post jsonb;
  v_before bigint;
  v_after bigint;
  v_issue jsonb;
  v_source_sha text;
begin
  if not exists (
    select 1 from integration_control.penta_change_contracts_v1 where change_id=v_change
  ) then
    raise exception 'stable #1995 institutional change fixture missing: %', v_change;
  end if;

  select count(*), max(source_sha256)
  into v_before, v_source_sha
  from integration_control.penta_change_contracts_v1 c
  left join integration_control.penta_change_certifications_v1 z on z.change_id=c.change_id
  where c.change_id=v_change
  group by c.change_id;

  if v_source_sha !~ '^[0-9a-f]{64}$' then
    raise exception 'stable fixture source digest missing: %', v_source_sha;
  end if;

  v_pre := integration_control.penta_change_precert_status_v2(v_change);
  v_post := integration_control.penta_change_postrelease_status_v2(v_change);

  if v_pre->>'contract' <> 'ct.penta.institutional-change.precert.v2'
     or v_pre->>'phase' <> 'pre_release' then
    raise exception 'unexpected precert v2 contract: %', v_pre;
  end if;

  if coalesce((v_pre->>'post_release_production_readback_required')::boolean,false) is not true then
    raise exception 'precert v2 must explicitly preserve post-release production readback requirement: %', v_pre;
  end if;

  if exists (
    select 1 from jsonb_array_elements_text(coalesce(v_pre->'missing','[]'::jsonb)) x(value)
    where value='PRODUCTION_READBACK'
  ) then
    raise exception 'precert v2 incorrectly requires post-release production readback: %', v_pre;
  end if;

  if not exists (
    select 1 from jsonb_array_elements_text(coalesce(v_post->'missing','[]'::jsonb)) x(value)
    where value='PRODUCTION_READBACK'
  ) then
    raise exception 'postrelease v2 must require actual production readback: %', v_post;
  end if;

  if not exists (
    select 1 from jsonb_array_elements_text(coalesce(v_post->'missing','[]'::jsonb)) x(value)
    where value='ACTIVE_INDEPENDENT_CERTIFICATION'
  ) then
    raise exception 'postrelease v2 must require active independent certification: %', v_post;
  end if;

  if coalesce((v_pre->>'authority_created')::boolean,true)
     or coalesce((v_post->>'authority_created')::boolean,true) then
    raise exception 'readiness functions must never create authority';
  end if;

  -- The real issuance path must consume precert v2. This fixture still has SECURITY /
  -- projection/dependency holds, so issuance must fail closed without creating a row.
  v_issue := integration_control.penta_change_issue_certification_v2(
    v_change,
    'canary.pr2020.'||replace(gen_random_uuid()::text,'-',''),
    'github-pr:crownthrive1/CrownThrive-OS#1995',
    v_source_sha,
    'penta.certify',
    clock_timestamp()+interval '15 minutes',
    jsonb_build_object('test','pr2020-issuance-v2-fail-closed')
  );

  if v_issue->>'state' <> 'HOLD'
     or v_issue->>'reason' <> 'PRECERT_PREDICATES_MISSING' then
    raise exception 'issuance v2 must fail closed on unsatisfied pre-release gates: %', v_issue;
  end if;

  if exists (
    select 1 from jsonb_array_elements_text(coalesce(v_issue->'precert'->'missing','[]'::jsonb)) x(value)
    where value='PRODUCTION_READBACK'
  ) then
    raise exception 'real issuance path still contains circular PRODUCTION_READBACK predicate: %', v_issue;
  end if;

  select count(*) into v_after
  from integration_control.penta_change_certifications_v1
  where change_id=v_change;

  if v_after <> v_before then
    raise exception 'readiness/held issuance checks mutated certification rows: before %, after %', v_before, v_after;
  end if;
end
$$;

-- Adversarial exact-source binding: a syntactically valid but wrong digest must be rejected.
do $$
declare
  v_change constant uuid := 'a924fba7-df3d-4337-b26a-0402b98f319c'::uuid;
  v_rejected boolean := false;
begin
  begin
    perform integration_control.penta_change_issue_certification_v2(
      v_change,
      'canary.pr2020.digest-mismatch.'||replace(gen_random_uuid()::text,'-',''),
      'github-pr:crownthrive1/CrownThrive-OS#1995',
      repeat('0',64),
      'penta.certify',
      clock_timestamp()+interval '15 minutes',
      '{}'::jsonb
    );
  exception when others then
    if sqlerrm='SUBJECT_DIGEST_MISMATCH' then
      v_rejected := true;
    else
      raise;
    end if;
  end;
  if not v_rejected then
    raise exception 'issuance v2 must reject a subject digest not bound to current source';
  end if;
end
$$;

-- Adversarial separation: originator cannot certify its own change.
do $$
declare
  v_change constant uuid := 'a924fba7-df3d-4337-b26a-0402b98f319c'::uuid;
  v_source_sha text;
  v_originator text;
  v_rejected boolean := false;
begin
  select source_sha256,originator_system_key into v_source_sha,v_originator
  from integration_control.penta_change_contracts_v1 where change_id=v_change;
  begin
    perform integration_control.penta_change_issue_certification_v2(
      v_change,
      'canary.pr2020.originator.'||replace(gen_random_uuid()::text,'-',''),
      'github-pr:crownthrive1/CrownThrive-OS#1995',
      v_source_sha,
      v_originator,
      clock_timestamp()+interval '15 minutes',
      '{}'::jsonb
    );
  exception when others then
    if sqlerrm='ORIGINATOR_CANNOT_CERTIFY' then
      v_rejected := true;
    else
      raise;
    end if;
  end;
  if not v_rejected then
    raise exception 'originator self-certification must be rejected';
  end if;
end
$$;

do $$
begin
  if has_function_privilege('anon','integration_control.penta_change_precert_status_v2(uuid)','EXECUTE') then
    raise exception 'anon must not execute precert v2';
  end if;
  if has_function_privilege('authenticated','integration_control.penta_change_precert_status_v2(uuid)','EXECUTE') then
    raise exception 'authenticated must not execute precert v2';
  end if;
  if not has_function_privilege('service_role','integration_control.penta_change_precert_status_v2(uuid)','EXECUTE') then
    raise exception 'service_role must retain precert v2 execution';
  end if;

  if has_function_privilege('anon','integration_control.penta_change_postrelease_status_v2(uuid)','EXECUTE') then
    raise exception 'anon must not execute postrelease v2';
  end if;
  if has_function_privilege('authenticated','integration_control.penta_change_postrelease_status_v2(uuid)','EXECUTE') then
    raise exception 'authenticated must not execute postrelease v2';
  end if;
  if not has_function_privilege('service_role','integration_control.penta_change_postrelease_status_v2(uuid)','EXECUTE') then
    raise exception 'service_role must retain postrelease v2 execution';
  end if;

  if has_function_privilege('anon','integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamp with time zone,jsonb)','EXECUTE') then
    raise exception 'anon must not execute certification issuance v2';
  end if;
  if has_function_privilege('authenticated','integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamp with time zone,jsonb)','EXECUTE') then
    raise exception 'authenticated must not execute certification issuance v2';
  end if;
  if not has_function_privilege('service_role','integration_control.penta_change_issue_certification_v2(uuid,text,text,text,text,timestamp with time zone,jsonb)','EXECUTE') then
    raise exception 'service_role must retain certification issuance v2 execution';
  end if;
end
$$;

rollback;
