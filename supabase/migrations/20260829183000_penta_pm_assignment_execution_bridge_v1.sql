-- PentaPM assignment -> executable Penta remediation bridge.
-- Production-applied 2026-08-29; this repository migration is the canonical replay form.

create table if not exists penta_runtime.remediation_execution_queue_v1 (
  execution_id uuid primary key default gen_random_uuid(),
  finding_id uuid not null unique,
  issue_number integer not null check (issue_number > 0),
  pr_number integer not null check (pr_number > 0),
  head_sha text not null check (head_sha ~ '^[0-9a-f]{40}$'),
  target_ref text not null,
  lane text not null,
  risk text not null check (risk in ('D0','D1','D2','D3')),
  assigned_pentas jsonb not null default '[]'::jsonb,
  executable_pentas jsonb not null default '[]'::jsonb,
  task_id uuid references penta_os20.execution_tasks(id),
  message_id bigint,
  state text not null default 'queued' check (state in ('queued','leased','applied','verification','verified','held','failed','superseded')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  lease_until timestamptz,
  last_error text,
  receipt jsonb not null default '{}'::jsonb,
  dail_event_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table penta_runtime.remediation_execution_queue_v1 enable row level security;
create index if not exists remediation_execution_queue_state_idx on penta_runtime.remediation_execution_queue_v1(state, updated_at);
create index if not exists remediation_execution_queue_pr_idx on penta_runtime.remediation_execution_queue_v1(pr_number);

create or replace function public.penta_pm_enqueue_remediation_execution_v1(
  p_finding_id uuid,
  p_issue_number integer,
  p_pr_number integer,
  p_head_sha text,
  p_target_ref text,
  p_lane text,
  p_risk text,
  p_assigned_pentas jsonb default '[]'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_os20','penta_self','pgmq','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_problem penta_self.problem_ledger_v1%rowtype;
  v_penta uuid; v_task uuid; v_task_state text; v_auth jsonb; v_exec uuid; v_msg bigint; v_dail jsonb;
  v_exec_pentas jsonb:='[]'::jsonb; v_state text; v_existing_msg bigint;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  if p_issue_number<=0 or p_pr_number<=0 or coalesce(p_head_sha,'') !~ '^[0-9a-f]{40}$' then raise exception 'invalid_remediation_execution_identity'; end if;
  select * into v_problem from penta_self.problem_ledger_v1 where problem_id=p_finding_id;
  if not found then raise exception 'pentaself_problem_not_found:%',p_finding_id; end if;
  select id into v_penta from penta_os20.pentas where canonical_name='PentaBuild' and status in ('active','probation') order by updated_at desc limit 1;
  if v_penta is null then raise exception 'PENTABUILD_EXECUTABLE_PRINCIPAL_MISSING'; end if;
  v_exec_pentas:=jsonb_build_array('PentaBuild');
  if exists(select 1 from penta_os20.pentas where canonical_name='PentaCertify' and status in ('active','probation')) then
    v_exec_pentas:=v_exec_pentas||jsonb_build_array('PentaCertify');
  end if;
  insert into penta_os20.execution_tasks(task_key,penta_id,release_version,operation_key,estimated_units,status,authority_check)
  values('ct.penta.remediation.'||p_finding_id::text,v_penta,'OS-2.0.0','github_remediation',1,'queued',jsonb_build_object('finding_id',p_finding_id,'issue_number',p_issue_number,'pr_number',p_pr_number,'head_sha',p_head_sha,'target_ref',p_target_ref,'risk',p_risk,'authority_expansion',false))
  on conflict(task_key) do update set authority_check=penta_os20.execution_tasks.authority_check||excluded.authority_check returning id,status into v_task,v_task_state;
  if v_task_state='queued' then v_auth:=penta_os20.authorize_task(v_task); else v_auth:=jsonb_build_object('authorized',v_task_state in ('authorized','completed'),'existing_state',v_task_state); end if;
  insert into penta_runtime.remediation_execution_queue_v1(finding_id,issue_number,pr_number,head_sha,target_ref,lane,risk,assigned_pentas,executable_pentas,task_id,state,receipt,updated_at)
  values(p_finding_id,p_issue_number,p_pr_number,p_head_sha,p_target_ref,coalesce(nullif(p_lane,''),'general'),coalesce(nullif(p_risk,''),'D1'),coalesce(p_assigned_pentas,'[]'::jsonb),v_exec_pentas,v_task,case when p_risk='D3' then 'held' else 'queued' end,jsonb_build_object('enqueue_authorization',v_auth,'source','PentaPM','authority_manufactured',false),now())
  on conflict(finding_id) do update set issue_number=excluded.issue_number,pr_number=excluded.pr_number,head_sha=excluded.head_sha,target_ref=excluded.target_ref,lane=excluded.lane,risk=excluded.risk,assigned_pentas=excluded.assigned_pentas,executable_pentas=excluded.executable_pentas,task_id=coalesce(penta_runtime.remediation_execution_queue_v1.task_id,excluded.task_id),state=case when penta_runtime.remediation_execution_queue_v1.state in ('verified','held') then penta_runtime.remediation_execution_queue_v1.state else excluded.state end,receipt=penta_runtime.remediation_execution_queue_v1.receipt||excluded.receipt,updated_at=now()
  returning execution_id,state,message_id into v_exec,v_state,v_existing_msg;
  if v_state not in ('verified','held','superseded') and p_risk<>'D3' and v_existing_msg is null then
    select x into v_msg from pgmq.send('penta_execution',jsonb_build_object('schema','ct.penta.remediation.execution-request.v1','execution_id',v_exec,'finding_id',p_finding_id,'issue_number',p_issue_number,'pr_number',p_pr_number,'head_sha',p_head_sha,'target_ref',p_target_ref,'assigned_pentas',coalesce(p_assigned_pentas,'[]'::jsonb),'executable_pentas',v_exec_pentas,'authority_ceiling','D2')) x limit 1;
    update penta_runtime.remediation_execution_queue_v1 set message_id=v_msg,updated_at=now() where execution_id=v_exec;
  else
    v_msg:=v_existing_msg;
  end if;
  v_dail:=chlom_runtime.append_dail_event('penta.pm.remediation_execution_queued','penta_remediation_execution',v_exec::text,jsonb_build_object('finding_id',p_finding_id,'issue_number',p_issue_number,'pr_number',p_pr_number,'head_sha',p_head_sha,'target_ref',p_target_ref,'assigned_pentas',coalesce(p_assigned_pentas,'[]'::jsonb),'executable_pentas',v_exec_pentas,'task_id',v_task,'message_id',v_msg,'risk',p_risk,'state',v_state,'d3_human_reserved',true),'PentaPM',null,'PentaPM','1.0.0','remediation:'||p_finding_id::text,v_task::text,'ct.penta.pm.assignment-execution.v1',null,'restricted');
  update penta_runtime.remediation_execution_queue_v1 set dail_event_id=(v_dail->>'event_id')::uuid where execution_id=v_exec;
  return jsonb_build_object('queued',v_state='queued','state',v_state,'held_d3',v_state='held' and p_risk='D3','execution_id',v_exec,'task_id',v_task,'message_id',v_msg,'executable_pentas',v_exec_pentas,'authorization',v_auth,'dail_event_id',v_dail->>'event_id');
end
$function$;

create or replace function public.penta_remediation_execution_claim_v1(p_limit integer default 5)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_self'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_rows jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  with picked as (
    select q.execution_id from penta_runtime.remediation_execution_queue_v1 q
    join penta_self.problem_ledger_v1 p on p.problem_id=q.finding_id
    where q.state in ('queued','verification','failed') and (q.lease_until is null or q.lease_until<=now()) and q.attempt_count<12
      and p.persistent is true and p.state not in ('resolved','closed','false_positive','retired')
    order by case q.risk when 'D0' then 0 when 'D1' then 1 when 'D2' then 2 else 3 end,q.updated_at
    for update of q skip locked
    limit greatest(1,least(coalesce(p_limit,5),10))
  ), leased as (
    update penta_runtime.remediation_execution_queue_v1 q set state='leased',lease_until=now()+interval '15 minutes',attempt_count=attempt_count+1,updated_at=now()
    from picked where q.execution_id=picked.execution_id returning q.*
  )
  select coalesce(jsonb_agg(to_jsonb(leased) order by leased.created_at),'[]'::jsonb) into v_rows from leased;
  return jsonb_build_object('state','LEASED','count',jsonb_array_length(v_rows),'items',v_rows);
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
  r record; v_complete jsonb; v_dail jsonb; v_count integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  for r in
    select q.execution_id,q.finding_id,q.issue_number,q.pr_number,q.head_sha,q.task_id,q.message_id,p.title,p.resolved_at,p.verification_evidence
    from penta_runtime.remediation_execution_queue_v1 q join penta_self.problem_ledger_v1 p on p.problem_id=q.finding_id
    where q.state in ('queued','leased','verification','failed') and p.state='resolved' for update of q skip locked
  loop
    if r.task_id is not null and exists(select 1 from penta_os20.execution_tasks where id=r.task_id and status='authorized') then
      v_complete:=penta_os20.complete_task(r.task_id,1);
    else
      v_complete:=jsonb_build_object('completed',false,'reason','task_not_authorized_or_already_terminal');
    end if;
    if r.message_id is not null then perform pgmq.archive('penta_execution',r.message_id); end if;
    update penta_runtime.remediation_execution_queue_v1 set state='verified',lease_until=null,last_error=null,completed_at=coalesce(completed_at,now()),receipt=receipt||jsonb_build_object('reconciled_at',now(),'resolution_source','PentaSELF','no_code_delta',true,'resolved_at',r.resolved_at,'verification_evidence',coalesce(r.verification_evidence,'{}'::jsonb),'build_task',v_complete),updated_at=now() where execution_id=r.execution_id;
    v_dail:=chlom_runtime.append_dail_event('penta.remediation.execution_reconciled','penta_remediation_execution',r.execution_id::text,jsonb_build_object('finding_id',r.finding_id,'issue_number',r.issue_number,'pr_number',r.pr_number,'head_sha',r.head_sha,'state','verified','resolution_source','PentaSELF','no_code_delta',true,'resolved_at',r.resolved_at,'authority_manufactured',false),'PentaCertify',null,'PentaExecution','1.0.0','remediation:'||r.finding_id::text,r.task_id::text,'ct.penta.pm.assignment-execution.v1',null,'restricted');
    update penta_runtime.remediation_execution_queue_v1 set dail_event_id=(v_dail->>'event_id')::uuid where execution_id=r.execution_id;
    v_count:=v_count+1;
  end loop;
  return jsonb_build_object('state','RECONCILED','verified_no_code_delta',v_count,'authority','PentaCertify','at',now());
end
$function$;

create or replace function public.penta_remediation_execute_known_v1(p_execution_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','penta_runtime','penta_os20','penta_self','integration_control','cron','pgmq','chlom_runtime','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  q penta_runtime.remediation_execution_queue_v1%rowtype; p penta_self.problem_ledger_v1%rowtype; j cron.job%rowtype; d cron.job_run_details%rowtype;
  v_result jsonb:='{}'::jsonb; v_state text:='failed'; v_error text; v_build_complete jsonb; v_cert_penta uuid; v_cert_task uuid; v_cert_auth jsonb; v_cert_complete jsonb; v_dail jsonb; v_cycle uuid:=gen_random_uuid();
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into q from penta_runtime.remediation_execution_queue_v1 where execution_id=p_execution_id for update;
  if not found then raise exception 'remediation_execution_not_found'; end if;
  select * into p from penta_self.problem_ledger_v1 where problem_id=q.finding_id for update;
  if not found then raise exception 'pentaself_problem_not_found'; end if;
  if q.risk='D3' or p.authority_class='D3' or not p.auto_heal_allowed then
    v_state:='held';
    v_result:=jsonb_build_object('reason',case when q.risk='D3' or p.authority_class='D3' then 'D3_HUMAN_RESERVED' else 'AUTO_HEAL_NOT_ALLOWED' end,'authority_manufactured',false);
  else
    begin
      case p.handler_key
        when 'recover.required_cron.v1' then
          select * into j from cron.job where 'cron:'||jobname=p.source_ref limit 1;
          if not found then raise exception 'required_cron_missing:%',p.source_ref; end if;
          select * into d from cron.job_run_details where jobid=j.jobid order by start_time desc limit 1;
          if p.source_ref='cron:ct-penta-crawler-roam-v3' and d.status='failed' and coalesce(d.return_message,'') ilike '%deadlock detected%' then
            perform cron.alter_job(j.jobid,schedule=>'9,19,29,39,49,59 * * * *',command=>j.command,active=>true);
            insert into penta_self.required_jobs_v1(jobname,expected_schedule,expected_command,auto_repair,risk_class,metadata)
            values(j.jobname,'9,19,29,39,49,59 * * * *',j.command,true,'D1',jsonb_build_object('owner','PentaTime/PentaBuild','repair','stagger recurring PentaCrawler deadlock away from minute-8 gap healer','execution_id',p_execution_id))
            on conflict(jobname) do update set expected_schedule=excluded.expected_schedule,expected_command=excluded.expected_command,auto_repair=true,risk_class='D1',metadata=penta_self.required_jobs_v1.metadata||excluded.metadata,updated_at=now();
            v_result:=jsonb_build_object('action','stagger_cron','jobname',j.jobname,'prior_schedule',j.schedule,'new_schedule','9,19,29,39,49,59 * * * *','deadlock_repair',true);
            v_state:='verification';
          else
            v_result:=jsonb_build_object('scheduler',penta_self.scheduler_reconcile_v1(v_cycle),'recovery',penta_self.failed_job_recovery_v1(v_cycle));
            select * into d from cron.job_run_details where jobid=j.jobid order by start_time desc limit 1;
            if d.status='succeeded' and d.start_time>=p.last_seen_at then
              perform penta_self.resolve_verified_problem_v2(p.title,jsonb_build_object('execution_id',p_execution_id,'jobid',j.jobid,'latest_status',d.status,'latest_started_at',d.start_time,'resolver','PentaBuild/PentaCertify execution bridge'),'PentaBuild/PentaCertify');
              v_state:='verified';
              v_result:=v_result||jsonb_build_object('jobid',j.jobid,'latest_status',d.status,'latest_started_at',d.start_time,'verified',true);
            else
              v_state:='verification';
              v_result:=v_result||jsonb_build_object('jobid',j.jobid,'latest_status',d.status,'latest_started_at',d.start_time,'verified',false);
            end if;
          end if;
        when 'diagnose.generic.v1' then
          v_result:=public.thrivebase_safe_self_heal_run_v1(); v_state:='verification';
        when 'repair.software.via_pentabuild.v1' then
          v_result:=integration_control.penta_build_quality_sweep_v1(); v_state:='verification';
        else
          v_state:='held'; v_result:=jsonb_build_object('reason','UNSUPPORTED_EXECUTABLE_HANDLER','handler_key',p.handler_key,'requires_specialist_action_contract',true,'authority_manufactured',false);
      end case;
    exception when others then
      v_error:=left(sqlerrm,700); v_state:='failed'; v_result:=jsonb_build_object('error',v_error,'sqlstate',sqlstate,'retryable',true);
    end;
  end if;
  if q.task_id is not null and exists(select 1 from penta_os20.execution_tasks where id=q.task_id and status='authorized') and v_state in ('verification','verified','held') then
    v_build_complete:=penta_os20.complete_task(q.task_id,1);
  else
    v_build_complete:=jsonb_build_object('completed',false,'reason','task_not_authorized_or_execution_failed');
  end if;
  if v_state='verified' then
    select id into v_cert_penta from penta_os20.pentas where canonical_name='PentaCertify' and status in ('active','probation') order by updated_at desc limit 1;
    if v_cert_penta is not null then
      insert into penta_os20.execution_tasks(task_key,penta_id,release_version,operation_key,estimated_units,status,authority_check)
      values('ct.penta.remediation.certify.'||q.finding_id::text,v_cert_penta,'OS-2.0.0','remediation_certification',1,'queued',jsonb_build_object('execution_id',q.execution_id,'finding_id',q.finding_id,'independent_from_builder',true))
      on conflict(task_key) do update set authority_check=penta_os20.execution_tasks.authority_check||excluded.authority_check returning id into v_cert_task;
      if exists(select 1 from penta_os20.execution_tasks where id=v_cert_task and status='queued') then v_cert_auth:=penta_os20.authorize_task(v_cert_task); end if;
      if exists(select 1 from penta_os20.execution_tasks where id=v_cert_task and status='authorized') then v_cert_complete:=penta_os20.complete_task(v_cert_task,1); end if;
    end if;
  end if;
  update penta_runtime.remediation_execution_queue_v1 set state=v_state,lease_until=null,last_error=v_error,receipt=receipt||jsonb_build_object('executed_at',now(),'handler_key',p.handler_key,'result',v_result,'build_task',v_build_complete,'certify_task_id',v_cert_task,'certify_authorization',v_cert_auth,'certify_completion',v_cert_complete),completed_at=case when v_state in ('verified','held') then now() else null end,updated_at=now() where execution_id=q.execution_id;
  if q.message_id is not null and v_state in ('verified','held') then perform pgmq.archive('penta_execution',q.message_id); end if;
  v_dail:=chlom_runtime.append_dail_event('penta.remediation.execution_result','penta_remediation_execution',q.execution_id::text,jsonb_build_object('finding_id',q.finding_id,'issue_number',q.issue_number,'pr_number',q.pr_number,'head_sha',q.head_sha,'state',v_state,'handler_key',p.handler_key,'result',v_result,'build_task_id',q.task_id,'certify_task_id',v_cert_task,'authority_manufactured',false,'d3_human_reserved',true),case when v_state='verified' then 'PentaCertify' else 'PentaBuild' end,null,'PentaExecution','1.0.0','remediation:'||q.finding_id::text,q.task_id::text,'ct.penta.pm.assignment-execution.v1',null,'restricted');
  update penta_runtime.remediation_execution_queue_v1 set dail_event_id=(v_dail->>'event_id')::uuid where execution_id=q.execution_id;
  return jsonb_build_object('execution_id',q.execution_id,'finding_id',q.finding_id,'state',v_state,'handler_key',p.handler_key,'result',v_result,'build_task',v_build_complete,'certify_task_id',v_cert_task,'dail_event_id',v_dail->>'event_id');
end
$function$;

create or replace function public.penta_remediation_execution_read_v1(p_pr_number integer default null)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','penta_runtime'
as $function$
declare v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),''); v_rows jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select coalesce(jsonb_agg(to_jsonb(q) order by q.created_at),'[]'::jsonb) into v_rows from penta_runtime.remediation_execution_queue_v1 q where p_pr_number is null or q.pr_number=p_pr_number;
  return jsonb_build_object('schema','ct.penta.remediation.execution-read.v1','count',jsonb_array_length(v_rows),'items',v_rows);
end
$function$;

create or replace function public.penta_remediation_execution_status_v1()
returns jsonb
language sql
security definer
set search_path to 'pg_catalog','penta_runtime'
as $function$
select jsonb_build_object('schema','ct.penta.remediation.execution-status.v1','total',count(*),'queued',count(*) filter(where state='queued'),'leased',count(*) filter(where state='leased'),'verification',count(*) filter(where state='verification'),'verified',count(*) filter(where state='verified'),'held',count(*) filter(where state='held'),'failed',count(*) filter(where state='failed'),'oldest_actionable',min(created_at) filter(where state in ('queued','leased','verification','failed')),'latest_update',max(updated_at)) from penta_runtime.remediation_execution_queue_v1
$function$;

grant execute on function public.penta_pm_enqueue_remediation_execution_v1(uuid,integer,integer,text,text,text,text,jsonb) to service_role;
grant execute on function public.penta_remediation_execution_claim_v1(integer) to service_role;
grant execute on function public.penta_remediation_execution_reconcile_v1() to service_role;
grant execute on function public.penta_remediation_execute_known_v1(uuid) to service_role;
grant execute on function public.penta_remediation_execution_read_v1(integer) to service_role;
grant execute on function public.penta_remediation_execution_status_v1() to service_role;
