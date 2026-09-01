-- PentaHelp independent-gate lifecycle hardening v1.
--
-- Production defect reproduced 2026-09-01: exact-head independent authority requests could
-- expire with attempt_count=0, and liaison threads could be created with ttyl_at later than
-- expires_at. That makes a routed independent review mathematically impossible to complete
-- inside its own service window and silently collapses a fail-closed gate into EXPIRED.
--
-- This repair changes lifecycle only. It never creates PASS, certification, rights, provider
-- write, credential, money, vote/quorum, D3, or authority. Independent gates remain fail-closed
-- in waiting_external until an actual independent disposition is recorded.

create or replace function public.penta_liaison_route_v1(
  p_request_id uuid,
  p_destination_kind text default null,
  p_destination_ref text default null,
  p_reason text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'penta_help'
as $function$
declare
  r penta_help.requests_v1%rowtype;
  v_kind text;
  v_ref text;
  v_thread uuid;
  v_mail uuid;
  v_subject text;
  v_body text;
  v_ttyl_at timestamptz;
  v_thread_expires timestamptz;
begin
  select * into r from penta_help.requests_v1 where request_id=p_request_id;
  if not found then raise exception 'PENTA_HELP_REQUEST_NOT_FOUND'; end if;

  v_kind:=coalesce(
    nullif(p_destination_kind,''),
    case
      when r.risk_class='D3' or r.resolution_mode='human_governance' then 'founder'
      when r.blocker_class='provider' then 'provider'
      else 'penta'
    end);
  v_ref:=coalesce(
    nullif(p_destination_ref,''),
    case
      when v_kind='founder' then 'PentaMail owner route'
      when v_kind='provider' then coalesce(r.context->>'provider_system',r.source_ref)
      else case r.blocker_class
        when 'software' then 'penta.build'
        when 'credential' then 'penta.credentials'
        when 'evidence' then 'penta.certify'
        else 'penta.self'
      end
    end);

  v_ttyl_at:=now()+make_interval(secs=>greatest(30,coalesce(r.ttyl_seconds,900)));
  -- An independent review must retain a real resolution window after its TTYL. The request
  -- remains fail-closed; this only prevents routing a task whose expiry precedes its own TTYL.
  v_thread_expires:=case
    when r.blocker_class='independent_gate' and r.risk_class<>'D3'
      then greatest(
        r.expires_at,
        v_ttyl_at + interval '1 hour')
    else r.expires_at
  end;

  if r.blocker_class='independent_gate' and r.risk_class<>'D3' then
    update penta_help.requests_v1
       set expires_at=v_thread_expires,
           state=case when state='expired' then 'waiting_external' else state end,
           resolved_at=case when state='expired' then null else resolved_at end,
           lease_owner=case when state='expired' then null else lease_owner end,
           lease_expires_at=case when state='expired' then null else lease_expires_at end,
           updated_at=now()
     where request_id=r.request_id;
  end if;

  insert into penta_help.liaison_threads_v1(
    request_id,destination_kind,destination_ref,route_key,state,ttyl_at,expires_at,ask,metadata)
  values(
    r.request_id,v_kind,v_ref,'liaison:'||r.blocker_class,'routed',v_ttyl_at,v_thread_expires,
    coalesce(p_reason,r.need),
    coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object(
      'risk_class',r.risk_class,
      'authority_required',r.authority_required,
      'lifecycle_guard','independent_gate_window_v1'))
  on conflict(request_id,destination_kind,destination_ref) do update set
    ask=excluded.ask,
    metadata=excluded.metadata,
    state=case
      when penta_help.liaison_threads_v1.state='resolved' then 'resolved'
      else 'routed'
    end,
    ttyl_at=case
      when penta_help.liaison_threads_v1.state='resolved' then penta_help.liaison_threads_v1.ttyl_at
      else excluded.ttyl_at
    end,
    expires_at=case
      when penta_help.liaison_threads_v1.state='resolved' then penta_help.liaison_threads_v1.expires_at
      else excluded.expires_at
    end,
    resolved_at=case
      when penta_help.liaison_threads_v1.state='resolved' then penta_help.liaison_threads_v1.resolved_at
      else null
    end,
    updated_at=now()
  returning thread_id into v_thread;

  if v_kind='founder' or r.risk_class='D3' or r.blocker_class in ('package','governance') then
    v_subject:='PentaLiaison: action required — '||r.requester_system_key||' / '||r.blocker_code;
    v_body:='PentaLiaison routed an unresolved dependency.'||E'\n\n'||
      'Requester: '||r.requester_system_key||E'\n'||
      'Blocker: '||r.blocker_code||E'\n'||
      'Need: '||r.need||E'\n'||
      'Risk: '||r.risk_class||E'\n'||
      'Authority: '||r.authority_required||E'\n'||
      'Destination: '||v_ref||E'\n'||
      'TTL seconds: '||r.ttl_seconds||E'\n'||
      'TTYL seconds: '||r.ttyl_seconds||E'\n'||
      'Request ID: '||r.request_id::text||E'\n\n'||
      'The system remains fail-closed while PentaHelper continues all bounded work it can perform automatically.';
    v_mail:=public.penta_mail_enqueue_with_maker_v1(
      'penta_help_escalation',case when r.risk_class='D3' then 'HIGH' else 'INFO' end,
      v_subject,v_body,'penta-liaison:'||r.request_id::text||':'||v_ref,
      jsonb_build_object(
        'request_id',r.request_id,'thread_id',v_thread,'destination_kind',v_kind,
        'destination_ref',v_ref,'risk_class',r.risk_class,'authority_required',r.authority_required));
  end if;

  return jsonb_build_object(
    'state','routed','request_id',r.request_id,'thread_id',v_thread,
    'destination_kind',v_kind,'destination_ref',v_ref,'mail_message_id',v_mail,
    'ttyl_at',v_ttyl_at,'expires_at',v_thread_expires,
    'lifecycle_guard','independent_gate_window_v1','at',now());
end
$function$;

create or replace function public.penta_helper_prepare_cycle_v1(p_limit integer default 2)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'penta_help'
as $function$
declare
  v_scan jsonb;
  v_stalled jsonb;
  v_rec jsonb;
  v_stalled_rec jsonb;
  v_tasks jsonb;
  x record;
  v_conn int;
  v_max int;
  v_limit int;
  v_exhausted int := 0;
  v_independent_preserved int := 0;
begin
  v_limit:=greatest(1,least(coalesce(p_limit,2),2));

  update penta_help.requests_v1
     set state='triaged',lease_owner=null,lease_expires_at=null,next_action_at=now(),updated_at=now()
   where state='executing' and lease_expires_at<now();

  v_scan:=public.penta_helper_scan_v1();
  v_stalled:=public.penta_helper_scan_stalled_work_v1();
  v_rec:=public.penta_helper_reconcile_v1();
  v_stalled_rec:=public.penta_helper_reconcile_stalled_work_v1();

  select count(*) into v_conn from pg_stat_activity;
  v_max:=current_setting('max_connections')::int;
  if v_conn >= greatest(20,floor(v_max*0.65)::int) then
    return jsonb_build_object(
      'state','backpressure','connections',v_conn,'max_connections',v_max,
      'scan',v_scan,'stalled_scan',v_stalled,'reconcile',v_rec,
      'stalled_reconcile',v_stalled_rec,'tasks','[]'::jsonb,'task_count',0,
      'retry_guard','bounded_v1','independent_gate_guard','window_v1','at',now());
  end if;

  -- Independent authority/certification work is not disposable retry work. When its TTL elapses
  -- without a disposition, preserve it fail-closed outside the automatic retry pool. A later
  -- liaison route may extend its service window, but only the independent owner can resolve it.
  with preserved as (
    update penta_help.requests_v1
       set state='waiting_external',
           lease_owner=null,
           lease_expires_at=null,
           updated_at=now()
     where blocker_class='independent_gate'
       and risk_class<>'D3'
       and state not in ('resolved','retired','expired','waiting_human','waiting_external')
       and expires_at<=now()
     returning request_id
  ) select count(*) into v_independent_preserved from preserved;

  update penta_help.requests_v1
     set state='expired',updated_at=now()
   where state not in ('resolved','retired','expired')
     and expires_at<=now()
     and risk_class<>'D3'
     and blocker_class is distinct from 'independent_gate';

  with exhausted as (
    update penta_help.requests_v1
       set state='waiting_external',lease_owner=null,lease_expires_at=null,updated_at=now()
     where state in ('raised','triaged','waiting_evidence')
       and risk_class<>'D3'
       and attempt_count>=max_attempts
     returning request_id
  ) select count(*) into v_exhausted from exhausted;

  for x in
    select request_id
      from penta_help.requests_v1 r
     where r.state='waiting_external'
       and r.risk_class<>'D3'
       and r.attempt_count>=r.max_attempts
       and not exists(
         select 1 from penta_help.liaison_threads_v1 l
          where l.request_id=r.request_id and l.state not in ('resolved','expired'))
     limit 8
  loop
    perform public.penta_liaison_route_v1(
      x.request_id,null,null,
      'PentaHelper exhausted its bounded automatic attempt budget',
      jsonb_build_object('retry_guard','bounded_v1','automatic_retry',false));
  end loop;

  for x in
    select request_id
      from penta_help.requests_v1 r
     where r.state not in ('resolved','retired','expired','waiting_human')
       and r.liaison_due_at<=now()
       and not exists(
         select 1 from penta_help.liaison_threads_v1 l
          where l.request_id=r.request_id and l.state not in ('resolved','expired'))
     limit 8
  loop
    perform public.penta_liaison_route_v1(
      x.request_id,null,null,'TTYL reached before autonomous resolution',
      jsonb_build_object('lifecycle_guard','independent_gate_window_v1'));
  end loop;

  update penta_help.requests_v1
     set state='waiting_human',updated_at=now()
   where risk_class='D3' and state not in ('resolved','retired','expired','waiting_human');

  for x in
    select request_id
      from penta_help.requests_v1 r
     where r.state='waiting_human'
       and not exists(
         select 1 from penta_help.liaison_threads_v1 l
          where l.request_id=r.request_id and l.state not in ('resolved','expired'))
     limit 8
  loop
    perform public.penta_liaison_route_v1(
      x.request_id,'founder','PentaMail owner route','Human-reserved authority is required','{}'::jsonb);
  end loop;

  with picked as (
    select request_id
      from penta_help.requests_v1
     where state in ('raised','triaged','waiting_evidence')
       and next_action_at<=now()
       and (lease_expires_at is null or lease_expires_at<now())
       and risk_class<>'D3'
       and attempt_count<max_attempts
       and blocker_class is distinct from 'independent_gate'
     order by case
       when resolution_mode='restore_evidence' then 0
       when resolution_mode='evidence_test' and context->>'certification_state'='needs_readback' then 1
       when resolution_mode='provider_route' then 2
       when resolution_mode='factory_reconcile' then 3
       when resolution_mode='credential_reconcile' then 4
       when resolution_mode='self_repair' then 5
       when resolution_mode='build_software' then 6 else 7 end,
       created_at
     for update skip locked
     limit v_limit
  ), upd as (
    update penta_help.requests_v1 r
       set state='executing',attempt_count=attempt_count+1,lease_owner='penta-helper',
           lease_expires_at=now()+interval '3 minutes',updated_at=now()
      from picked p
     where r.request_id=p.request_id
     returning r.*
  ) select coalesce(jsonb_agg(to_jsonb(upd)),'[]'::jsonb) into v_tasks from upd;

  return jsonb_build_object(
    'state','prepared','connections',v_conn,'max_connections',v_max,
    'scan',v_scan,'stalled_scan',v_stalled,'reconcile',v_rec,
    'stalled_reconcile',v_stalled_rec,'tasks',v_tasks,
    'task_count',jsonb_array_length(v_tasks),'retry_guard','bounded_v1',
    'independent_gate_guard','window_v1',
    'independent_gates_preserved',v_independent_preserved,
    'exhausted_routed_external',v_exhausted,'at',now());
end
$function$;

revoke all on function public.penta_liaison_route_v1(uuid,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.penta_liaison_route_v1(uuid,text,text,text,jsonb) to service_role;
revoke all on function public.penta_helper_prepare_cycle_v1(integer) from public,anon,authenticated;
grant execute on function public.penta_helper_prepare_cycle_v1(integer) to service_role;

comment on function public.penta_liaison_route_v1(uuid,text,text,text,jsonb) is
'Routes unresolved help work. Independent-gate threads receive a fail-closed service window whose expiry is always later than TTYL; rerouting reopens expired unresolved threads but never resolved threads.';
comment on function public.penta_helper_prepare_cycle_v1(integer) is
'Prepares bounded autonomous help tasks. Independent authority/certification gates are excluded from automatic attempts and terminal TTL expiry; elapsed independent gates remain waiting_external until real independent disposition.';
