-- Preserve recurrence history across pg_cron job identity replacement and require
-- permanent repair before a recurrent cron problem may be treated as complete.

create or replace function public.penta_remediation_execute_known_v2(p_execution_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_os20','penta_self','integration_control','cron','pgmq','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  q penta_runtime.remediation_execution_queue_v1%rowtype;
  p penta_self.problem_ledger_v1%rowtype;
  j cron.job%rowtype;
  v_failure_jobid bigint;
  v_deadlocks integer:=0;
  v_surgery_at timestamptz;
  v_build_task uuid;
  v_build_penta uuid;
  v_auth jsonb;
  v_complete jsonb;
  v_dail jsonb;
  v_result jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into q from penta_runtime.remediation_execution_queue_v1 where execution_id=p_execution_id for update;
  if not found then raise exception 'remediation_execution_not_found'; end if;
  select * into p from penta_self.problem_ledger_v1 where problem_id=q.finding_id for update;
  if not found then raise exception 'pentaself_problem_not_found'; end if;

  if p.handler_key='recover.required_cron.v1'
     and p.source_ref='cron:ct-penta-crawler-roam-v3'
     and q.risk<>'D3'
     and p.authority_class<>'D3'
     and p.auto_heal_allowed then
    v_failure_jobid:=nullif(p.evidence->>'jobid','')::bigint;
    if v_failure_jobid is not null then
      select count(*) into v_deadlocks
      from cron.job_run_details
      where jobid=v_failure_jobid
        and status='failed'
        and coalesce(return_message,'') ilike '%deadlock detected%';
    end if;
    select * into j from cron.job where 'cron:'||jobname=p.source_ref limit 1;
    if v_deadlocks>=3 and found and j.schedule='8,18,28,38,48,58 * * * *' then
      v_surgery_at:=clock_timestamp();
      if q.task_id is not null and exists(select 1 from penta_os20.execution_tasks where id=q.task_id and status='authorized') then
        v_build_task:=q.task_id;
      else
        select id into v_build_penta from penta_os20.pentas
        where canonical_name='PentaBuild' and status in ('active','probation')
        order by updated_at desc limit 1;
        if v_build_penta is null then raise exception 'PENTABUILD_EXECUTABLE_PRINCIPAL_MISSING'; end if;
        insert into penta_os20.execution_tasks(task_key,penta_id,release_version,operation_key,estimated_units,status,authority_check)
        values('ct.penta.remediation.surgery.'||q.finding_id::text,v_build_penta,'OS-2.0.0','recurring_cron_surgery',1,'queued',
          jsonb_build_object('finding_id',q.finding_id,'execution_id',q.execution_id,'source_ref',p.source_ref,'recurring_deadlocks',v_deadlocks,'authority_expansion',false))
        on conflict(task_key) do update set authority_check=penta_os20.execution_tasks.authority_check||excluded.authority_check
        returning id into v_build_task;
        if exists(select 1 from penta_os20.execution_tasks where id=v_build_task and status='queued') then
          v_auth:=penta_os20.authorize_task(v_build_task);
        end if;
      end if;

      perform cron.alter_job(j.jobid,schedule=>'9,19,29,39,49,59 * * * *',command=>j.command,active=>true);
      insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
      values(j.jobname,'9,19,29,39,49,59 * * * *',j.command,true,'D1',
        jsonb_build_object('owner','PentaTime/PentaBuild','repair','stagger recurring PentaCrawler deadlock away from minute-8 peer work','execution_id',p_execution_id,'prior_jobid',v_failure_jobid,'deadlocks_observed',v_deadlocks,'surgery_at',v_surgery_at))
      on conflict(jobname) do update set
        expected_schedule=excluded.expected_schedule,
        expected_command=excluded.expected_command,
        auto_repair=true,
        risk_class='D1',
        metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,
        updated_at=now();

      update penta_self.problem_ledger_v1
      set state='verification',persistent=true,resolved_at=null,next_attempt_at=now(),blocked_reason=null,
          verification_evidence=verification_evidence||jsonb_build_object('recurrence_surgery',jsonb_build_object(
            'at',v_surgery_at,'prior_jobid',v_failure_jobid,'current_jobid',j.jobid,'deadlocks_observed',v_deadlocks,
            'prior_schedule',j.schedule,'new_schedule','9,19,29,39,49,59 * * * *','authority','PentaBuild/PentaTime')),
          updated_at=now()
      where problem_id=p.problem_id;

      if v_build_task is not null and exists(select 1 from penta_os20.execution_tasks where id=v_build_task and status='authorized') then
        v_complete:=penta_os20.complete_task(v_build_task,1);
      end if;
      update penta_runtime.remediation_execution_queue_v1
      set state='verification',lease_until=null,completed_at=null,last_error=null,message_id=null,
          receipt=receipt||jsonb_build_object('recurrence_surgery',jsonb_build_object(
            'at',v_surgery_at,'prior_jobid',v_failure_jobid,'current_jobid',j.jobid,'deadlocks_observed',v_deadlocks,
            'prior_schedule',j.schedule,'new_schedule','9,19,29,39,49,59 * * * *','build_task_id',v_build_task,
            'build_authorization',v_auth,'build_completion',v_complete)),
          updated_at=now()
      where execution_id=q.execution_id;

      v_dail:=chlom_runtime.append_dail_event(
        'penta.remediation.recurring_cron_surgery','penta_remediation_execution',q.execution_id::text,
        jsonb_build_object('finding_id',q.finding_id,'issue_number',q.issue_number,'pr_number',q.pr_number,'source_ref',p.source_ref,
          'prior_jobid',v_failure_jobid,'current_jobid',j.jobid,'deadlocks_observed',v_deadlocks,'prior_schedule',j.schedule,
          'new_schedule','9,19,29,39,49,59 * * * *','state','verification','build_task_id',v_build_task,
          'authority_manufactured',false,'d3_human_reserved',true),
        'PentaBuild',null,'PentaExecution','2.0.0','remediation-surgery:'||q.finding_id::text,v_build_task::text,
        'ct.penta.pm.assignment-execution.v2',null,'restricted');
      update penta_runtime.remediation_execution_queue_v1
      set dail_event_id=(v_dail->>'event_id')::uuid
      where execution_id=q.execution_id;
      return jsonb_build_object(
        'execution_id',q.execution_id,'finding_id',q.finding_id,'state','verification','handler_key',p.handler_key,
        'surgery_applied',true,'deadlocks_observed',v_deadlocks,'prior_jobid',v_failure_jobid,'current_jobid',j.jobid,
        'prior_schedule',j.schedule,'new_schedule','9,19,29,39,49,59 * * * *','build_task_id',v_build_task,
        'dail_event_id',v_dail->>'event_id');
    end if;
  end if;

  v_result:=public.penta_remediation_execute_known_v1(p_execution_id);
  return v_result||jsonb_build_object(
    'execution_contract','ct.penta.pm.assignment-execution.v2',
    'recurrence_guard_checked',p.handler_key='recover.required_cron.v1',
    'historical_deadlocks_observed',v_deadlocks);
end
$function$;

grant execute on function public.penta_remediation_execute_known_v2(uuid) to service_role;
