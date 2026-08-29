-- Guard PentaSELF/PentaCertify from accepting a pre-surgery green readback.

create or replace function penta_self.resolve_verified_problem_v2(p_title text, p_evidence jsonb, p_actor_ref text default 'PentaSELF/PentaAssure')
returns integer
language plpgsql
security definer
set search_path to 'pg_catalog','penta_self','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_row record;
  v_count integer:=0;
  v_payload jsonb;
  v_digest text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  for v_row in
    update penta_self.problem_ledger_v1 p
       set state='resolved',resolved_at=now(),updated_at=now(),next_attempt_at=now()+interval '100 years',blocked_reason=null,last_error=null,
           verification_evidence=coalesce(p.verification_evidence,'{}'::jsonb)||coalesce(p_evidence,'{}'::jsonb)||jsonb_build_object('verified_at',now(),'resolver','penta_self.resolve_verified_problem_v2')
     where p.title=p_title
       and p.state not in ('resolved','false_positive','retired')
       and not exists (
         select 1
         from penta_runtime.remediation_execution_queue_v1 q
         where q.finding_id=p.problem_id
           and q.state='verification'
           and q.receipt ? 'recurrence_surgery'
           and not (
             coalesce(p_evidence->>'latest_status','')='succeeded'
             and nullif(p_evidence->>'latest_started_at','') is not null
             and (p_evidence->>'latest_started_at')::timestamptz >= (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
           )
       )
     returning p.problem_id,p.priority,p.severity,p.category,p.title,p.owner_penta
  loop
    v_count:=v_count+1;
    v_payload:=jsonb_build_object('problem_id',v_row.problem_id,'title',v_row.title,'priority',v_row.priority,'severity',v_row.severity,'category',v_row.category,'owner_penta',v_row.owner_penta,'resolution_evidence',coalesce(p_evidence,'{}'::jsonb),'resolution_state','resolved','authority_created',false,'observed_at',now());
    v_digest:=encode(extensions.digest(v_payload::text,'sha256'),'hex');
    perform chlom_runtime.append_dail_event('pentaself.problem.verified_resolved','problem',v_row.problem_id::text,v_payload,p_actor_ref,null,'PentaSELF','2.1.0',v_digest,null,'post-remediation current-state evidence; no authority expansion',null,'internal');
  end loop;
  return v_count;
end
$function$;

create or replace function public.penta_remediation_execution_reconcile_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_os20','penta_self','pgmq','chlom_runtime'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  v_complete jsonb;
  v_dail jsonb;
  v_count integer:=0;
  v_reopened integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;

  with stale as (
    select p.problem_id
    from penta_self.problem_ledger_v1 p
    join penta_runtime.remediation_execution_queue_v1 q on q.finding_id=p.problem_id
    where q.state='verification'
      and q.receipt ? 'recurrence_surgery'
      and p.state='resolved'
      and p.resolved_at is not null
      and p.resolved_at < (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
  )
  update penta_self.problem_ledger_v1 p
  set state='verification',resolved_at=null,next_attempt_at=now(),blocked_reason=null,
      verification_evidence=p.verification_evidence||jsonb_build_object('post_surgery_guard',jsonb_build_object('reopened_at',now(),'reason','pre_surgery_resolution_rejected')),
      updated_at=now()
  from stale
  where p.problem_id=stale.problem_id;
  get diagnostics v_reopened=row_count;

  for r in
    select q.execution_id,q.finding_id,q.issue_number,q.pr_number,q.head_sha,q.task_id,q.message_id,p.title,p.resolved_at,p.verification_evidence
    from penta_runtime.remediation_execution_queue_v1 q
    join penta_self.problem_ledger_v1 p on p.problem_id=q.finding_id
    where q.state in ('queued','leased','verification','failed')
      and p.state='resolved'
      and (
        not (q.receipt ? 'recurrence_surgery')
        or (
          p.resolved_at >= (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
          and coalesce(p.verification_evidence->>'latest_status','')='succeeded'
          and nullif(p.verification_evidence->>'latest_started_at','') is not null
          and (p.verification_evidence->>'latest_started_at')::timestamptz >= (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
        )
      )
    for update of q skip locked
  loop
    if r.task_id is not null and exists(select 1 from penta_os20.execution_tasks where id=r.task_id and status='authorized') then
      v_complete:=penta_os20.complete_task(r.task_id,1);
    else
      v_complete:=jsonb_build_object('completed',false,'reason','task_not_authorized_or_already_terminal');
    end if;
    if r.message_id is not null then perform pgmq.archive('penta_execution',r.message_id); end if;
    update penta_runtime.remediation_execution_queue_v1
    set state='verified',lease_until=null,last_error=null,completed_at=coalesce(completed_at,now()),
        receipt=receipt||jsonb_build_object('reconciled_at',now(),'resolution_source','PentaSELF','no_code_delta',true,'resolved_at',r.resolved_at,'verification_evidence',coalesce(r.verification_evidence,'{}'::jsonb),'build_task',v_complete),
        updated_at=now()
    where execution_id=r.execution_id;
    v_dail:=chlom_runtime.append_dail_event('penta.remediation.execution_reconciled','penta_remediation_execution',r.execution_id::text,
      jsonb_build_object('finding_id',r.finding_id,'issue_number',r.issue_number,'pr_number',r.pr_number,'head_sha',r.head_sha,'state','verified','resolution_source','PentaSELF','no_code_delta',true,'resolved_at',r.resolved_at,'authority_manufactured',false),
      'PentaCertify',null,'PentaExecution','2.0.0','remediation:'||r.finding_id::text,r.task_id::text,'ct.penta.pm.assignment-execution.v2',null,'restricted');
    update penta_runtime.remediation_execution_queue_v1 set dail_event_id=(v_dail->>'event_id')::uuid where execution_id=r.execution_id;
    v_count:=v_count+1;
  end loop;
  return jsonb_build_object('state','RECONCILED','verified_no_code_delta',v_count,'stale_pre_surgery_resolutions_reopened',v_reopened,'authority','PentaCertify','at',now());
end
$function$;

create or replace function public.penta_remediation_execute_known_v3(p_execution_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_self','cron','chlom_runtime'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  q penta_runtime.remediation_execution_queue_v1%rowtype;
  p penta_self.problem_ledger_v1%rowtype;
  j cron.job%rowtype;
  d cron.job_run_details%rowtype;
  v_surgery_at timestamptz;
  v_dail jsonb;
  v_result jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into q from penta_runtime.remediation_execution_queue_v1 where execution_id=p_execution_id for update;
  if not found then raise exception 'remediation_execution_not_found'; end if;
  select * into p from penta_self.problem_ledger_v1 where problem_id=q.finding_id;
  if not found then raise exception 'pentaself_problem_not_found'; end if;

  if q.receipt ? 'recurrence_surgery' then
    v_surgery_at:=(q.receipt#>>'{recurrence_surgery,at}')::timestamptz;
    if p.handler_key='recover.required_cron.v1' and p.source_ref like 'cron:%' then
      select * into j from cron.job where 'cron:'||jobname=p.source_ref limit 1;
      if found then
        select * into d from cron.job_run_details where jobid=j.jobid order by start_time desc limit 1;
      end if;
      if d.start_time is null or d.start_time < v_surgery_at or d.status<>'succeeded' then
        update penta_runtime.remediation_execution_queue_v1
        set state='verification',lease_until=null,last_error=null,
            receipt=receipt||jsonb_build_object('post_surgery_verification',jsonb_build_object(
              'checked_at',now(),'surgery_at',v_surgery_at,'current_jobid',j.jobid,'latest_started_at',d.start_time,
              'latest_status',d.status,'ready',false,'reason','awaiting_successful_post_surgery_execution')),
            updated_at=now()
        where execution_id=q.execution_id;
        v_dail:=chlom_runtime.append_dail_event('penta.remediation.post_surgery_verification_wait','penta_remediation_execution',q.execution_id::text,
          jsonb_build_object('finding_id',q.finding_id,'issue_number',q.issue_number,'pr_number',q.pr_number,'surgery_at',v_surgery_at,
            'current_jobid',j.jobid,'latest_started_at',d.start_time,'latest_status',d.status,'state','verification','authority_manufactured',false),
          'PentaCertify',null,'PentaExecution','3.0.0','remediation-verify:'||q.finding_id::text,q.task_id::text,'ct.penta.pm.assignment-execution.v3',null,'restricted');
        update penta_runtime.remediation_execution_queue_v1 set dail_event_id=(v_dail->>'event_id')::uuid where execution_id=q.execution_id;
        return jsonb_build_object('execution_id',q.execution_id,'finding_id',q.finding_id,'state','verification','handler_key',p.handler_key,
          'post_surgery_verification_ready',false,'surgery_at',v_surgery_at,'current_jobid',j.jobid,'latest_started_at',d.start_time,
          'latest_status',d.status,'reason','awaiting_successful_post_surgery_execution','dail_event_id',v_dail->>'event_id');
      end if;
    end if;
  end if;

  v_result:=public.penta_remediation_execute_known_v2(p_execution_id);
  return v_result||jsonb_build_object('execution_contract','ct.penta.pm.assignment-execution.v3','post_surgery_guard_checked',q.receipt ? 'recurrence_surgery');
end
$function$;

grant execute on function public.penta_remediation_execution_reconcile_v1() to service_role;
grant execute on function public.penta_remediation_execute_known_v3(uuid) to service_role;
