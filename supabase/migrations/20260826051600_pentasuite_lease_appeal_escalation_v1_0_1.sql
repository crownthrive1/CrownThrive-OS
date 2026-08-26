-- PentaSuite v1.0.1: appeal review, escalation ladder, activation-started TTL, and appeal stays.

create or replace function public.pentasuite_review_appeal(
  p_appeal_id uuid,
  p_actor_ref text,
  p_stay_granted boolean default false
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare a public.pentasuite_appeals%rowtype;
begin
  select * into a from public.pentasuite_appeals where id=p_appeal_id for update;
  if not found then raise exception 'appeal not found'; end if;
  if a.state <> 'filed' then raise exception 'appeal is not awaiting review'; end if;
  update public.pentasuite_appeals
  set state='accepted_for_review',stay_granted=p_stay_granted,updated_at=now()
  where id=p_appeal_id;
  perform public.pentasuite_emit_event(a.request_id,a.lease_id,'pentasuite.appeal.accepted_for_review',p_actor_ref,
    jsonb_build_object('appeal_id',p_appeal_id,'stay_granted',p_stay_granted,'body','Membership and Ethics Committee'));
  return jsonb_build_object('appeal_id',p_appeal_id,'state','accepted_for_review','stay_granted',p_stay_granted);
end;
$$;

create or replace function public.pentasuite_record_violation(
  p_lease_id uuid,
  p_actor_ref text,
  p_reason text,
  p_severity text default 'medium'
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare l public.pentasuite_agent_leases%rowtype;
declare r public.pentarfa_agent_requests%rowtype;
declare v_next integer;
declare v_action text;
declare v_result jsonb;
begin
  if p_severity not in ('low','medium','high','critical') then raise exception 'invalid severity'; end if;
  select * into l from public.pentasuite_agent_leases where id=p_lease_id for update;
  if not found then raise exception 'lease not found'; end if;
  select * into r from public.pentarfa_agent_requests where id=l.request_id;
  v_next := l.strike_count + 1;
  v_action := case
    when p_severity='critical' and v_next <= 3 then 'suspended'
    when v_next=1 then 'remediation'
    when v_next=2 then 'restricted'
    when v_next=3 then 'suspended'
    when v_next=4 then 'revoked'
    else 'barred'
  end;
  v_result := public.pentasuite_enforce_lease(p_lease_id,v_action,p_actor_ref,p_reason,
    case when v_action in ('revoked','barred') then r.lockout_seconds else null end);
  if v_action in ('revoked','barred') then
    perform public.pentasuite_schedule_rollback(p_lease_id,p_reason,p_actor_ref);
  end if;
  return v_result || jsonb_build_object('severity',p_severity,'strike',v_next,'escalation_ladder',jsonb_build_array('remediation','restricted','suspended','revoked','barred'));
end;
$$;

create or replace function public.pentasuite_tick() returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare rec record;
declare v_activated integer := 0;
declare v_expired integer := 0;
declare v_revoked integer := 0;
declare v_lockouts integer := 0;
declare v_rollbacks integer := 0;
begin
  update public.pentasuite_lockouts set state='expired',updated_at=now() where state='active' and ends_at <= now();
  get diagnostics v_lockouts = row_count;

  for rec in
    select b.id as blueprint_id,b.request_id,b.factory_build_request_id,l.id as lease_id,l.state as lease_state,l.ttl_seconds,r.state as request_state
    from public.pentasuite_agent_blueprints b
    join public.pentasuite_agent_leases l on l.blueprint_id=b.id
    join public.pentarfa_agent_requests r on r.id=b.request_id
    join public.ct_factory_build_requests f on f.id=b.factory_build_request_id
    where b.state='factory_dispatched' and f.status='implemented' and l.starts_at is null
  loop
    update public.pentasuite_agent_blueprints set state='validated',updated_at=now() where id=rec.blueprint_id;
    update public.pentasuite_agent_assets set state='validated',updated_at=now() where blueprint_id=rec.blueprint_id and state in ('planned','generated');
    update public.pentasuite_agent_leases
    set state=case when rec.request_state='conditional_grant' then 'conditional' else 'active' end,
        starts_at=now(),
        expires_at=now()+make_interval(secs=>ttl_seconds),
        remediation_due_at=case when rec.request_state='conditional_grant' then now()+make_interval(secs=>ttl_seconds) else null end,
        last_heartbeat_at=now(),
        updated_at=now()
    where id=rec.lease_id and state in ('staged','conditional');
    if rec.request_state='conditional_grant' then
      update public.pentasuite_remediation_items set due_at=now()+make_interval(secs=>rec.ttl_seconds),updated_at=now() where lease_id=rec.lease_id and state not in ('verified','waived_by_governance');
    end if;
    perform public.pentasuite_emit_event(rec.request_id,rec.lease_id,'pentasuite.activated','pentasuite-sentinel',
      jsonb_build_object('factory_build_request_id',rec.factory_build_request_id,'ttl_clock','starts_on_activation'));
    v_activated := v_activated + 1;
  end loop;

  for rec in
    select l.*,r.requester_ref,r.lockout_seconds
    from public.pentasuite_agent_leases l join public.pentarfa_agent_requests r on r.id=l.request_id
    where l.state in ('active','conditional','remediation','restricted','suspended')
      and l.starts_at is not null and l.expires_at is not null and l.expires_at <= now()
      and not exists (
        select 1 from public.pentasuite_appeals a
        where a.lease_id=l.id and a.stay_granted=true and a.state in ('filed','accepted_for_review','board_escalation')
      )
  loop
    update public.pentasuite_agent_leases set state='expired',status_reason='lease_ttl_expired',updated_at=now() where id=rec.id;
    perform public.pentasuite_schedule_rollback(rec.id,'lease_ttl_expired','pentasuite-sentinel');
    v_expired := v_expired + 1;
    v_rollbacks := v_rollbacks + 1;
  end loop;

  for rec in
    select distinct l.id,l.request_id,l.agent_key,l.strike_count,r.requester_ref,r.lockout_seconds
    from public.pentasuite_agent_leases l
    join public.pentarfa_agent_requests r on r.id=l.request_id
    where l.state in ('conditional','remediation','restricted')
      and l.starts_at is not null
      and l.remediation_due_at is not null and l.remediation_due_at <= now()
      and exists (select 1 from public.pentasuite_remediation_items m where m.lease_id=l.id and m.state not in ('verified','waived_by_governance'))
      and not exists (
        select 1 from public.pentasuite_appeals a
        where a.lease_id=l.id and a.stay_granted=true and a.state in ('filed','accepted_for_review','board_escalation')
      )
  loop
    perform public.pentasuite_enforce_lease(rec.id,'revoked','pentasuite-sentinel','remediation_ttl_missed',rec.lockout_seconds);
    perform public.pentasuite_schedule_rollback(rec.id,'remediation_ttl_missed','pentasuite-sentinel');
    v_revoked := v_revoked + 1;
    v_rollbacks := v_rollbacks + 1;
  end loop;

  for rec in
    select l.id,l.request_id,l.rollback_build_request_id,f.status
    from public.pentasuite_agent_leases l join public.ct_factory_build_requests f on f.id=l.rollback_build_request_id
    where l.state='rollback_pending' and f.status='implemented'
  loop
    update public.pentasuite_agent_leases set state='rolled_back',updated_at=now() where id=rec.id;
    update public.pentasuite_agent_assets set state='rolled_back',updated_at=now()
    where blueprint_id=(select blueprint_id from public.pentasuite_agent_leases where id=rec.id) and state in ('validated','active');
    perform public.pentasuite_emit_event(rec.request_id,rec.id,'pentasuite.rollback.completed','pentasuite-sentinel',jsonb_build_object('factory_build_request_id',rec.rollback_build_request_id));
  end loop;

  return jsonb_build_object('at',now(),'activated',v_activated,'expired',v_expired,'revoked_for_missed_remediation',v_revoked,'lockouts_expired',v_lockouts,'rollbacks_scheduled',v_rollbacks);
end;
$$;
