-- Transactional acceptance test for institutional pre-release certification ordering v2.
-- Uses the preserved #1995 institutional-change record as a stable integration fixture.
-- This test issues no certification, release, provider write, D3 action, rights grant,
-- money movement, credential operation, or authority expansion.

begin;

do $$
declare
  v_change constant uuid := 'a924fba7-df3d-4337-b26a-0402b98f319c'::uuid;
  v_pre jsonb;
  v_post jsonb;
  v_before bigint;
  v_after bigint;
begin
  if not exists (
    select 1 from integration_control.penta_change_contracts_v1 where change_id=v_change
  ) then
    raise exception 'stable #1995 institutional change fixture missing: %', v_change;
  end if;

  select count(*) into v_before
  from integration_control.penta_change_certifications_v1
  where change_id=v_change;

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

  select count(*) into v_after
  from integration_control.penta_change_certifications_v1
  where change_id=v_change;

  if v_after <> v_before then
    raise exception 'readiness checks mutated certification rows: before %, after %', v_before, v_after;
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
end
$$;

rollback;
