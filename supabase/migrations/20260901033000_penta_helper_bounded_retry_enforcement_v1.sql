-- PentaHelper bounded retry enforcement v1.
--
-- Root cause: penta_helper_prepare_cycle_v1() re-selected waiting_external work and did not
-- enforce attempt_count < max_attempts. penta_helper_record_attempt_v1() also returned
-- successful-but-unresolved exhausted work to triaged. The combination allowed retry counts
-- to grow indefinitely (production observation: attempt_count=727 with max_attempts=6).
--
-- This repair is control-plane only. It creates no provider write, money, credential, rights,
-- vote/quorum, D3, or authority effect. Exhausted work is preserved and routed to the existing
-- liaison/external path rather than silently deleted or retried forever.

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
begin
  v_limit:=greatest(1,least(coalesce(p_limit,2),2));

  -- Recover only stale leases. The request is then subject to the same bounded-attempt guard
  -- as every other candidate below.
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
      'retry_guard','bounded_v1','at',now());
  end if;

  update penta_help.requests_v1
     set state='expired',updated_at=now()
   where state not in ('resolved','retired','expired') and expires_at<=now() and risk_class<>'D3';

  -- Exhausted autonomous work is terminal for this bounded attempt budget. Preserve the row,
  -- clear any lease, and move it to the already-governed external/liaison path. A later explicit
  -- governed rearm may create a new budget; this function never silently resets attempts.
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
       and not exists(select 1 from penta_help.liaison_threads_v1 l where l.request_id=r.request_id)
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
       and not exists(select 1 from penta_help.liaison_threads_v1 l where l.request_id=r.request_id)
     limit 8
  loop
    perform public.penta_liaison_route_v1(
      x.request_id,null,null,'TTYL reached before autonomous resolution','{}'::jsonb);
  end loop;

  update penta_help.requests_v1
     set state='waiting_human',updated_at=now()
   where risk_class='D3' and state not in ('resolved','retired','expired','waiting_human');

  for x in
    select request_id
      from penta_help.requests_v1 r
     where r.state='waiting_human'
       and not exists(select 1 from penta_help.liaison_threads_v1 l where l.request_id=r.request_id)
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
    'exhausted_routed_external',v_exhausted,'at',now());
end
$function$;

create or replace function public.penta_helper_record_attempt_v1(
  p_request_id uuid,
  p_success boolean,
  p_result jsonb,
  p_state text default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'penta_help', 'extensions'
as $function$
declare
  r penta_help.requests_v1%rowtype;
  v_state text;
  v_sha text;
begin
  select * into r from penta_help.requests_v1 where request_id=p_request_id for update;
  if not found then raise exception 'PENTA_HELP_REQUEST_NOT_FOUND'; end if;

  v_sha:=encode(extensions.digest(convert_to(coalesce(p_result,'{}'::jsonb)::text,'UTF8'),'sha256'::text),'hex');
  insert into penta_help.receipts_v1(request_id,actor_system_key,action,attempt_no,success,evidence,evidence_sha256)
  values(r.request_id,'penta.helper',r.resolution_mode,r.attempt_count,p_success,coalesce(p_result,'{}'::jsonb),v_sha);

  -- Resolution wins. Otherwise an exhausted budget always leaves the automatic retry pool,
  -- including a technically successful attempt whose semantic result remains unresolved.
  v_state:=coalesce(
    nullif(p_state,''),
    case
      when p_success and coalesce((p_result->>'resolved')::boolean,false) then 'resolved'
      when r.attempt_count>=r.max_attempts then 'waiting_external'
      else 'triaged'
    end
  );

  -- Callers cannot use p_state to silently rearm exhausted unresolved work.
  if v_state in ('raised','triaged','waiting_evidence')
     and r.attempt_count>=r.max_attempts
     and not (p_success and coalesce((p_result->>'resolved')::boolean,false)) then
    v_state:='waiting_external';
  end if;

  update penta_help.requests_v1
     set state=v_state,
         evidence=evidence||jsonb_build_object(
           'last_attempt',coalesce(p_result,'{}'::jsonb),
           'last_attempt_sha256',v_sha,
           'last_attempt_at',now(),
           'retry_guard','bounded_v1'),
         resolution=case when v_state='resolved'
           then resolution||jsonb_build_object('result',p_result,'at',now()) else resolution end,
         resolved_at=case when v_state='resolved' then now() else resolved_at end,
         next_action_at=case when v_state in ('triaged','waiting_evidence')
           then now()+interval '5 minutes' else next_action_at end,
         lease_owner=null,lease_expires_at=null,updated_at=now()
   where request_id=r.request_id;

  if v_state='waiting_external'
     and not exists(select 1 from penta_help.liaison_threads_v1 where request_id=r.request_id) then
    perform public.penta_liaison_route_v1(
      r.request_id,null,null,'PentaHelper exhausted its bounded automatic attempt budget',
      jsonb_build_object('retry_guard','bounded_v1','automatic_retry',false));
  end if;

  return jsonb_build_object(
    'request_id',r.request_id,'state',v_state,'success',p_success,
    'evidence_sha256',v_sha,'attempt_count',r.attempt_count,'max_attempts',r.max_attempts,
    'automatic_retry_allowed',v_state in ('triaged','waiting_evidence') and r.attempt_count<r.max_attempts,
    'at',now());
end
$function$;

revoke all on function public.penta_helper_prepare_cycle_v1(integer) from public,anon,authenticated;
grant execute on function public.penta_helper_prepare_cycle_v1(integer) to service_role;
revoke all on function public.penta_helper_record_attempt_v1(uuid,boolean,jsonb,text) from public,anon,authenticated;
grant execute on function public.penta_helper_record_attempt_v1(uuid,boolean,jsonb,text) to service_role;

comment on function public.penta_helper_prepare_cycle_v1(integer) is
'Prepares at most two bounded PentaHelper tasks. Exhausted or waiting_external work is excluded from autonomous retry and preserved for liaison/external resolution.';
comment on function public.penta_helper_record_attempt_v1(uuid,boolean,jsonb,text) is
'Records an immutable helper attempt. Unresolved work at max_attempts transitions to waiting_external regardless of transport success; no silent attempt-budget reset.';
