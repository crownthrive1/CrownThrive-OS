-- CrownThrive Penta Assignment review-only owner routing v1
--
-- Stacked on ct.penta.assignment-owner-routing-repair.v1 / PR #1899.
-- Purpose: admit canonical non-executing review handoffs for PentaSecurity,
-- PentaTime and PentaDemocracy without creating PM execution eligibility,
-- provider-write, credential, money, D3, certification or authority-expansion power.
--
-- These are CENSUS_HANDOFF routes only. They are evidence/review admission routes;
-- they are not OS20 execution routes and do not convert a reviewer into an executor.
-- The generic PentaCensus production mobilizer intentionally recognizes only the four
-- executable #1899 targets. Review-only handoffs are therefore acknowledged into a
-- non-executing review lane and excluded from that generic mobilizer until a legitimate
-- reviewer transport/receipt advances the handoff.

insert into integration_control.penta_assignment_owner_routes_v1
  (owner_penta,identity_key,dispatch_kind,target_ref,authority_ceiling,active,source_ref,metadata)
values
  (
    'PentaSecurity','penta.security','CENSUS_HANDOFF','penta.security','D2',true,
    'ct.penta.assignment-review-only-owner-routing.v1',
    jsonb_build_object(
      'route_mode','review_only',
      'review_role','security',
      'pm_execution_eligible',false,
      'provider_write',false,
      'credential_change',false,
      'money_movement',false,
      'd3_execution',false,
      'authority_expansion',false,
      'authority_effect','none'
    )
  ),
  (
    'PentaTime','penta.time','CENSUS_HANDOFF','penta.time','D2',true,
    'ct.penta.assignment-review-only-owner-routing.v1',
    jsonb_build_object(
      'route_mode','review_only',
      'review_role','temporal_integrity',
      'pm_execution_eligible',false,
      'provider_write',false,
      'credential_change',false,
      'money_movement',false,
      'd3_execution',false,
      'authority_expansion',false,
      'authority_effect','none'
    )
  ),
  (
    'PentaDemocracy','penta.democracy','CENSUS_HANDOFF','penta.democracy','D2',true,
    'ct.penta.assignment-review-only-owner-routing.v1',
    jsonb_build_object(
      'route_mode','review_only',
      'review_role','governance_boundary',
      'pm_execution_eligible',false,
      'provider_write',false,
      'credential_change',false,
      'money_movement',false,
      'd3_execution',false,
      'authority_expansion',false,
      'authority_effect','none',
      'sovereign_vote_effect',false
    )
  )
on conflict(owner_penta) do update set
  identity_key=excluded.identity_key,
  dispatch_kind=excluded.dispatch_kind,
  target_ref=excluded.target_ref,
  authority_ceiling=excluded.authority_ceiling,
  active=excluded.active,
  source_ref=excluded.source_ref,
  metadata=integration_control.penta_assignment_owner_routes_v1.metadata||excluded.metadata,
  updated_at=now();

-- Guard the semantic boundary. Review-only rows may never be represented as OS20
-- execution routes or as possessing execution/provider/D3/authority-expansion power.
create or replace function integration_control.penta_assignment_review_only_route_guard_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $fn$
begin
  if coalesce(new.metadata->>'route_mode','')='review_only' then
    if new.dispatch_kind <> 'CENSUS_HANDOFF' then
      raise exception 'REVIEW_ONLY_ROUTE_MUST_BE_CENSUS_HANDOFF';
    end if;
    if coalesce((new.metadata->>'pm_execution_eligible')::boolean,false)
       or coalesce((new.metadata->>'provider_write')::boolean,false)
       or coalesce((new.metadata->>'credential_change')::boolean,false)
       or coalesce((new.metadata->>'money_movement')::boolean,false)
       or coalesce((new.metadata->>'d3_execution')::boolean,false)
       or coalesce((new.metadata->>'authority_expansion')::boolean,false) then
      raise exception 'REVIEW_ONLY_ROUTE_AUTHORITY_EXPANSION_FORBIDDEN';
    end if;
  end if;
  return new;
end
$fn$;

drop trigger if exists penta_assignment_review_only_route_guard_v1
  on integration_control.penta_assignment_owner_routes_v1;
create trigger penta_assignment_review_only_route_guard_v1
before insert or update on integration_control.penta_assignment_owner_routes_v1
for each row execute function integration_control.penta_assignment_review_only_route_guard_v1();

-- The generic production mobilizer maps only executable #1899 routes. A review-only
-- handoff must never enter that queue and be misclassified as target_node_unavailable.
-- On initial route admission we acknowledge it into the review lane instead. A later
-- legitimate reviewer transport may advance acknowledged -> completed/HOLD using
-- independent evidence; this trigger does not manufacture that result.
create or replace function integration_control.penta_assignment_review_handoff_guard_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $fn$
declare
  v_route integration_control.penta_assignment_owner_routes_v1%rowtype;
begin
  if new.state='queued' then
    select * into v_route
    from integration_control.penta_assignment_owner_routes_v1
    where active=true
      and dispatch_kind='CENSUS_HANDOFF'
      and target_ref=new.target_ref
      and metadata->>'route_mode'='review_only'
    order by owner_penta
    limit 1;

    if found then
      new.state:='acknowledged';
      new.authority_note:='REVIEW_ONLY_HANDOFF: admitted to non-executing review lane; generic production mobilizer excluded; independent reviewer transport/receipt still required.';
      new.payload:=coalesce(new.payload,'{}'::jsonb)||jsonb_build_object(
        'review_only',true,
        'review_transport_state','queued',
        'review_route_owner',v_route.owner_penta,
        'review_route_identity_key',v_route.identity_key,
        'pm_execution_eligible',false,
        'provider_write',false,
        'credential_change',false,
        'money_movement',false,
        'd3_execution',false,
        'authority_expansion',false,
        'hold_code','HOLD_ASSIGNMENT_REVIEW_TRANSPORT_PENDING'
      );
    end if;
  end if;
  return new;
end
$fn$;

drop trigger if exists penta_assignment_review_handoff_guard_v1
  on integration_control.penta_census_handoffs_v1;
create trigger penta_assignment_review_handoff_guard_v1
before insert or update of state,target_ref,payload on integration_control.penta_census_handoffs_v1
for each row execute function integration_control.penta_assignment_review_handoff_guard_v1();

revoke all on function integration_control.penta_assignment_review_only_route_guard_v1() from public,anon,authenticated;
revoke all on function integration_control.penta_assignment_review_handoff_guard_v1() from public,anon,authenticated;

-- Exact migration-time readback. Existing executable routes remain untouched and
-- the new routes are review-only, fail-closed and non-authority-bearing.
do $verify$
declare
  v_count integer;
  v_bad integer;
begin
  select count(*) into v_count
  from integration_control.penta_assignment_owner_routes_v1
  where owner_penta in ('PentaSecurity','PentaTime','PentaDemocracy')
    and identity_key in ('penta.security','penta.time','penta.democracy')
    and dispatch_kind='CENSUS_HANDOFF'
    and active
    and metadata->>'route_mode'='review_only'
    and coalesce((metadata->>'pm_execution_eligible')::boolean,false)=false
    and coalesce((metadata->>'authority_expansion')::boolean,false)=false;

  if v_count <> 3 then
    raise exception 'REVIEW_ONLY_OWNER_ROUTE_REGISTRATION_FAILED';
  end if;

  select count(*) into v_bad
  from integration_control.penta_assignment_owner_routes_v1
  where owner_penta in ('PentaSecurity','PentaTime','PentaDemocracy')
    and (
      dispatch_kind <> 'CENSUS_HANDOFF'
      or coalesce((metadata->>'pm_execution_eligible')::boolean,false)
      or coalesce((metadata->>'provider_write')::boolean,false)
      or coalesce((metadata->>'credential_change')::boolean,false)
      or coalesce((metadata->>'money_movement')::boolean,false)
      or coalesce((metadata->>'d3_execution')::boolean,false)
      or coalesce((metadata->>'authority_expansion')::boolean,false)
    );

  if v_bad <> 0 then
    raise exception 'REVIEW_ONLY_OWNER_ROUTE_BOUNDARY_FAILED';
  end if;
end
$verify$;
