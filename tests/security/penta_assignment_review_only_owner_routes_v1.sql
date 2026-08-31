-- Transactional deterministic/negative/adversarial acceptance for
-- ct.penta.assignment-review-only-owner-routing.v1.
-- All state created by this test is rolled back.

begin;

do $$
declare
  v_assignment jsonb;
  v_assignment_id uuid;
  v_route jsonb;
  v_count integer;
  v_os20 integer;
  v_rejected boolean:=false;
begin
  -- Existing executable owner routes from PR #1899 must remain present.
  select count(*) into v_count
  from integration_control.penta_assignment_owner_routes_v1
  where (owner_penta,identity_key,dispatch_kind,target_ref) in (
    ('PentaBuild','penta.build','CENSUS_HANDOFF','penta.build'),
    ('PentaWire','penta.wire','CENSUS_HANDOFF','ct.agent.penta-wire'),
    ('PentaCertify','penta.certify','CENSUS_HANDOFF','penta.certify'),
    ('PentaRelease','penta.release','CENSUS_HANDOFF','penta.release')
  ) and active;
  if v_count<>4 then raise exception 'existing executable owner routes changed'; end if;

  -- Canonical reviewer identities are admitted only as review-only handoffs.
  select count(*) into v_count
  from integration_control.penta_assignment_owner_routes_v1
  where owner_penta in ('PentaSecurity','PentaTime','PentaDemocracy')
    and dispatch_kind='CENSUS_HANDOFF'
    and active
    and metadata->>'route_mode'='review_only'
    and coalesce((metadata->>'pm_execution_eligible')::boolean,false)=false
    and coalesce((metadata->>'provider_write')::boolean,false)=false
    and coalesce((metadata->>'credential_change')::boolean,false)=false
    and coalesce((metadata->>'money_movement')::boolean,false)=false
    and coalesce((metadata->>'d3_execution')::boolean,false)=false
    and coalesce((metadata->>'authority_expansion')::boolean,false)=false;
  if v_count<>3 then raise exception 'review-only route invariants missing'; end if;

  -- Negative: a review-only route cannot be mutated into an OS20 execution route.
  begin
    update integration_control.penta_assignment_owner_routes_v1
    set dispatch_kind='OS20_TASK'
    where owner_penta='PentaSecurity';
  exception when others then
    if sqlerrm='REVIEW_ONLY_ROUTE_MUST_BE_CENSUS_HANDOFF' then v_rejected:=true; else raise; end if;
  end;
  if not v_rejected then raise exception 'review-only OS20 escalation was not rejected'; end if;

  -- Adversarial: execution eligibility cannot be smuggled through metadata.
  v_rejected:=false;
  begin
    update integration_control.penta_assignment_owner_routes_v1
    set metadata=metadata||jsonb_build_object('pm_execution_eligible',true)
    where owner_penta='PentaSecurity';
  exception when others then
    if sqlerrm='REVIEW_ONLY_ROUTE_AUTHORITY_EXPANSION_FORBIDDEN' then v_rejected:=true; else raise; end if;
  end;
  if not v_rejected then raise exception 'review-only execution eligibility escalation was not rejected'; end if;

  -- Integration canary: route a synthetic D1 assignment through all three reviewers.
  v_assignment:=integration_control.penta_assignment_create_v1(
    'ct.canary.assignment.review-only-routing.'||replace(gen_random_uuid()::text,'-',''),
    'internal_canary',
    'canary:review-only-owner-routing',
    'review_only_route_canary',
    'Review-only route canary',
    'Transactional canary only; no production execution or authority.',
    'SECURITY_TRUST',
    '["PentaSecurity","PentaTime","PentaDemocracy"]'::jsonb,
    'D1','D1',
    'canary:review-only-owner-routing',
    repeat('a',64),
    'crownthrive1/CrownThrive-OS',
    null,
    null,
    jsonb_build_array('review-only CENSUS handoffs only','no OS20 execution'),
    false,
    'P2',
    jsonb_build_object('canary',true,'authority_created',false)
  );
  v_assignment_id:=(v_assignment->>'assignment_id')::uuid;
  if v_assignment_id is null then raise exception 'canary assignment creation failed: %',v_assignment; end if;

  v_route:=integration_control.penta_assignment_route_v2(v_assignment_id);
  if (v_route->>'holds')::integer<>0 then raise exception 'registered review routes unexpectedly held: %',v_route; end if;

  select count(*) into v_count
  from integration_control.penta_assignment_dispatches_v1 d
  join integration_control.penta_assignment_owner_routes_v1 r on r.owner_penta=d.owner_penta
  where d.assignment_id=v_assignment_id
    and d.owner_penta in ('PentaSecurity','PentaTime','PentaDemocracy')
    and d.dispatch_kind='CENSUS_HANDOFF'
    and d.state='ROUTED'
    and r.metadata->>'route_mode'='review_only';
  if v_count<>3 then raise exception 'review handoff dispatch readback failed'; end if;

  select count(*) into v_count
  from integration_control.penta_census_handoffs_v1 h
  where h.handoff_key like 'assignment:'||v_assignment_id::text||':%'
    and h.target_ref in ('penta.security','penta.time','penta.democracy')
    and h.state='queued';
  if v_count<>3 then raise exception 'review handoff queue readback failed'; end if;

  select count(*) into v_os20
  from penta_os20.execution_tasks
  where task_key like 'assignment:'||v_assignment_id::text||':%';
  if v_os20<>0 then raise exception 'review-only routing created OS20 execution tasks: %',v_os20; end if;
end
$$;

rollback;
