-- Rollback for 20260901090500_penta_help_independent_gate_lifecycle_hardening_v1.sql.
-- Restores the exact liaison routing semantics observed before this repair and the bounded-retry
-- prepare-cycle semantics introduced by 20260901033000_penta_helper_bounded_retry_enforcement_v1.

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
declare r penta_help.requests_v1%rowtype; v_kind text; v_ref text; v_thread uuid; v_mail uuid; v_subject text; v_body text;
begin
 select * into r from penta_help.requests_v1 where request_id=p_request_id;
 if not found then raise exception 'PENTA_HELP_REQUEST_NOT_FOUND'; end if;
 v_kind:=coalesce(nullif(p_destination_kind,''),case when r.risk_class='D3' or r.resolution_mode='human_governance' then 'founder' when r.blocker_class='provider' then 'provider' else 'penta' end);
 v_ref:=coalesce(nullif(p_destination_ref,''),case when v_kind='founder' then 'PentaMail owner route' when v_kind='provider' then coalesce(r.context->>'provider_system',r.source_ref) else case r.blocker_class when 'software' then 'penta.build' when 'credential' then 'penta.credentials' when 'evidence' then 'penta.certify' else 'penta.self' end end);
 insert into penta_help.liaison_threads_v1(request_id,destination_kind,destination_ref,route_key,state,ttyl_at,expires_at,ask,metadata)
 values(r.request_id,v_kind,v_ref,'liaison:'||r.blocker_class,'routed',now()+make_interval(secs=>r.ttyl_seconds),r.expires_at,coalesce(p_reason,r.need),coalesce(p_metadata,'{}'::jsonb)||jsonb_build_object('risk_class',r.risk_class,'authority_required',r.authority_required))
 on conflict(request_id,destination_kind,destination_ref) do update set ask=excluded.ask,metadata=excluded.metadata,updated_at=now()
 returning thread_id into v_thread;
 if v_kind='founder' or r.risk_class='D3' or r.blocker_class in ('package','governance') then
   v_subject:='PentaLiaison: action required — '||r.requester_system_key||' / '||r.blocker_code;
   v_body:='PentaLiaison routed an unresolved dependency.'||E'\n\n'||'Requester: '||r.requester_system_key||E'\n'||'Blocker: '||r.blocker_code||E'\n'||'Need: '||r.need||E'\n'||'Risk: '||r.risk_class||E'\n'||'Authority: '||r.authority_required||E'\n'||'Destination: '||v_ref||E'\n'||'TTL seconds: '||r.ttl_seconds||E'\n'||'TTYL seconds: '||r.ttyl_seconds||E'\n'||'Request ID: '||r.request_id::text||E'\n\n'||'The system remains fail-closed while PentaHelper continues all bounded work it can perform automatically.';
   v_mail:=public.penta_mail_enqueue_with_maker_v1('penta_help_escalation',case when r.risk_class='D3' then 'HIGH' else 'INFO' end,v_subject,v_body,'penta-liaison:'||r.request_id::text||':'||v_ref,jsonb_build_object('request_id',r.request_id,'thread_id',v_thread,'destination_kind',v_kind,'destination_ref',v_ref,'risk_class',r.risk_class,'authority_required',r.authority_required));
 end if;
 return jsonb_build_object('state','routed','request_id',r.request_id,'thread_id',v_thread,'destination_kind',v_kind,'destination_ref',v_ref,'mail_message_id',v_mail,'at',now());
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
    return jsonb_build_object('state','backpressure','connections',v_conn,'max_connections',v_max,'scan',v_scan,'stalled_scan',v_stalled,'reconcile',v_rec,'stalled_reconcile',v_stalled_rec,'tasks','[]'::jsonb,'task_count',0,'retry_guard','bounded_v1','at',now());
  end if;
  update penta_help.requests_v1
     set state='expired',updated_at=now()
   where state not in ('resolved','retired','expired') and expires_at<=now() and risk_class<>'D3';
  with exhausted as (
    update penta_help.requests_v1
       set state='waiting_external',lease_owner=null,lease_expires_at=null,updated_at=now()
     where state in ('raised','triaged','waiting_evidence')
       and risk_class<>'D3'
       and attempt_count>=max_attempts
     returning request_id
  ) select count(*) into v_exhausted from exhausted;
  for x in
    select request_id from penta_help.requests_v1 r
     where r.state='waiting_external' and r.risk_class<>'D3' and r.attempt_count>=r.max_attempts
       and not exists(select 1 from penta_help.liaison_threads_v1 l where l.request_id=r.request_id)
     limit 8
  loop
    perform public.penta_liaison_route_v1(x.request_id,null,null,'PentaHelper exhausted its bounded automatic attempt budget',jsonb_build_object('retry_guard','bounded_v1','automatic_retry',false));
  end loop;
  for x in
    select request_id from penta_help.requests_v1 r
     where r.state not in ('resolved','retired','expired','waiting_human') and r.liaison_due_at<=now()
       and not exists(select 1 from penta_help.liaison_threads_v1 l where l.request_id=r.request_id)
     limit 8
  loop
    perform public.penta_liaison_route_v1(x.request_id,null,null,'TTYL reached before autonomous resolution','{}'::jsonb);
  end loop;
  update penta_help.requests_v1 set state='waiting_human',updated_at=now() where risk_class='D3' and state not in ('resolved','retired','expired','waiting_human');
  for x in
    select request_id from penta_help.requests_v1 r where r.state='waiting_human'
      and not exists(select 1 from penta_help.liaison_threads_v1 l where l.request_id=r.request_id)
    limit 8
  loop
    perform public.penta_liaison_route_v1(x.request_id,'founder','PentaMail owner route','Human-reserved authority is required','{}'::jsonb);
  end loop;
  with picked as (
    select request_id from penta_help.requests_v1
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
       when resolution_mode='build_software' then 6 else 7 end, created_at
     for update skip locked limit v_limit
  ), upd as (
    update penta_help.requests_v1 r
       set state='executing',attempt_count=attempt_count+1,lease_owner='penta-helper',lease_expires_at=now()+interval '3 minutes',updated_at=now()
      from picked p where r.request_id=p.request_id returning r.*
  ) select coalesce(jsonb_agg(to_jsonb(upd)),'[]'::jsonb) into v_tasks from upd;
  return jsonb_build_object('state','prepared','connections',v_conn,'max_connections',v_max,'scan',v_scan,'stalled_scan',v_stalled,'reconcile',v_rec,'stalled_reconcile',v_stalled_rec,'tasks',v_tasks,'task_count',jsonb_array_length(v_tasks),'retry_guard','bounded_v1','exhausted_routed_external',v_exhausted,'at',now());
end
$function$;

revoke all on function public.penta_liaison_route_v1(uuid,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.penta_liaison_route_v1(uuid,text,text,text,jsonb) to service_role;
revoke all on function public.penta_helper_prepare_cycle_v1(integer) from public,anon,authenticated;
grant execute on function public.penta_helper_prepare_cycle_v1(integer) to service_role;
