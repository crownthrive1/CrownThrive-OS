create or replace function public.penta_remediation_execution_reconcile_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_os20','penta_self','pgmq','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  r record;
  v_complete jsonb;
  v_dail jsonb;
  v_count integer:=0;
  v_repaired integer:=0;
  v_reopened integer:=0;
  v_no_code_delta boolean;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;

  with stale as (
    select p.problem_id,(q.receipt#>>'{recurrence_surgery,at}')::timestamptz as surgery_at,q.execution_id
    from penta_self.problem_ledger_v1 p
    join penta_runtime.remediation_execution_queue_v1 q on q.finding_id=p.problem_id
    where q.state in ('queued','verification')
      and q.receipt ? 'recurrence_surgery'
      and p.state='resolved'
      and p.resolved_at is not null
      and p.resolved_at < (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
  )
  update penta_self.problem_ledger_v1 p
  set state='verification',next_attempt_at=now(),blocked_reason=null,
      last_seen_at=greatest(p.last_seen_at,stale.surgery_at),
      evidence=p.evidence||jsonb_build_object(
        'observed_at',stale.surgery_at,
        'regression_verified',true,
        'regression_evidence_sha256',encode(extensions.digest(convert_to(p.problem_id::text||'|'||stale.execution_id::text||'|'||stale.surgery_at::text,'UTF8'),'sha256'),'hex'),
        'recurrence_surgery_reopen',jsonb_build_object('execution_id',stale.execution_id,'surgery_at',stale.surgery_at,'reason','newer_remediation_evidence_requires_post_surgery_verification')
      ),
      verification_evidence=p.verification_evidence||jsonb_build_object('post_surgery_guard',jsonb_build_object('reopened_at',now(),'surgery_at',stale.surgery_at,'reason','pre_surgery_resolution_rejected')),
      updated_at=now()
  from stale
  where p.problem_id=stale.problem_id;
  get diagnostics v_reopened=row_count;

  for r in
    select q.execution_id,q.finding_id,q.issue_number,q.pr_number,q.head_sha,q.task_id,q.message_id,q.receipt,
           p.title,p.resolved_at,p.verification_evidence
    from penta_runtime.remediation_execution_queue_v1 q
    join penta_self.problem_ledger_v1 p on p.problem_id=q.finding_id
    where q.state in ('queued','leased','verification','failed')
      and p.state='resolved'
      and (
        not (q.receipt ? 'recurrence_surgery')
        or (
          p.resolved_at >= (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
          and coalesce(p.verification_evidence->>'latest_status','')='succeeded'
          and greatest(
                nullif(p.verification_evidence->>'latest_started_at','')::timestamptz,
                nullif(p.verification_evidence->>'last_success_at','')::timestamptz
              ) >= (q.receipt#>>'{recurrence_surgery,at}')::timestamptz
        )
      )
    for update of q skip locked
  loop
    v_no_code_delta := not (coalesce(r.receipt,'{}'::jsonb) ? 'recurrence_surgery');
    if r.task_id is not null and exists(select 1 from penta_os20.execution_tasks where id=r.task_id and status='authorized') then
      v_complete:=penta_os20.complete_task(r.task_id,1);
    else
      v_complete:=jsonb_build_object('completed',false,'reason','task_not_authorized_or_already_terminal');
    end if;
    if r.message_id is not null then perform pgmq.archive('penta_execution',r.message_id); end if;
    update penta_runtime.remediation_execution_queue_v1
    set state='verified',lease_until=null,last_error=null,completed_at=coalesce(completed_at,now()),
        receipt=receipt||jsonb_build_object('reconciled_at',now(),'resolution_source','PentaSELF','no_code_delta',v_no_code_delta,'resolved_at',r.resolved_at,'verification_evidence',coalesce(r.verification_evidence,'{}'::jsonb),'build_task',v_complete),
        updated_at=now()
    where execution_id=r.execution_id;
    v_dail:=chlom_runtime.append_dail_event('penta.remediation.execution_reconciled','penta_remediation_execution',r.execution_id::text,
      jsonb_build_object('finding_id',r.finding_id,'issue_number',r.issue_number,'pr_number',r.pr_number,'head_sha',r.head_sha,'state','verified','resolution_source','PentaSELF','no_code_delta',v_no_code_delta,'resolved_at',r.resolved_at,'authority_manufactured',false),
      'PentaCertify',null,'PentaExecution','4.0.0','remediation:'||r.finding_id::text,r.task_id::text,'ct.penta.pm.assignment-execution.v4',null,'restricted');
    update penta_runtime.remediation_execution_queue_v1 set dail_event_id=(v_dail->>'event_id')::uuid where execution_id=r.execution_id;
    v_count:=v_count+1;
    if not v_no_code_delta then v_repaired:=v_repaired+1; end if;
  end loop;
  return jsonb_build_object('state','RECONCILED','verified_total',v_count,'verified_no_code_delta',v_count-v_repaired,'verified_repaired',v_repaired,'stale_pre_surgery_resolutions_reopened',v_reopened,'authority','PentaCertify','at',now());
end
$function$;
