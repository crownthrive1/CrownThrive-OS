-- PentaMarketer Persona Execution Bridge v1 runtime.
-- Depends on 20260828193000_pentamarketer_persona_execution_bridge_schema_v1.sql.

create or replace function crm.penta_persona_enqueue_execution_v1(
  p_work_id uuid,
  p_persona_id text,
  p_capability_key text,
  p_input jsonb default '{}'::jsonb,
  p_context jsonb default '{}'::jsonb,
  p_risk_class text default 'D1',
  p_authority_class text default 'D1',
  p_idempotency_key text default null,
  p_entitlement_flow_id uuid default null,
  p_chlom_invocation_id uuid default null,
  p_simulation boolean default false
) returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm','public'
as $$
declare
  v_control crm.penta_persona_execution_control_v1%rowtype;
  v_cap crm.penta_persona_execution_capabilities_v1%rowtype;
  v_agent crm.penta_marketer_agents_v2%rowtype;
  v_work crm.penta_marketer_work_queue_v1%rowtype;
  v_req crm.penta_persona_execution_requests_v1%rowtype;
  v_key text;
  v_state text:='queued';
  v_entitlement_ok boolean:=false;
  v_chlom_ok boolean:=false;
  v_corr text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  select * into v_control from crm.penta_persona_execution_control_v1 where control_key='default';
  if not found or not v_control.active or v_control.kill_switch then
    return jsonb_build_object('status','hold','reason','EXECUTION_BRIDGE_DISABLED','d3_auto',false);
  end if;
  if p_risk_class not in ('D0','D1','D2','D3') or p_authority_class not in ('D0','D1','D2','D3') then
    raise exception 'INVALID_AUTHORITY_CLASS';
  end if;
  select * into v_agent from crm.penta_marketer_agents_v2
   where persona_id=p_persona_id and enabled=true and autonomous=true and state='active'
   order by agent_id limit 1;
  if not found then raise exception 'PERSONA_EXECUTOR_NOT_ACTIVE'; end if;
  select * into v_cap from crm.penta_persona_execution_capabilities_v1
   where persona_id=p_persona_id and capability_key=p_capability_key and enabled=true;
  if not found or v_cap.certification_state='hold' then raise exception 'CAPABILITY_NOT_ENABLED'; end if;

  if p_work_id is not null then
    select * into v_work from crm.penta_marketer_work_queue_v1 where work_id=p_work_id;
    if not found then raise exception 'WORK_NOT_FOUND'; end if;
    if v_work.assigned_persona_id<>p_persona_id or v_work.assigned_agent_id<>v_agent.agent_id then
      raise exception 'WORK_ASSIGNMENT_MISMATCH';
    end if;
  end if;

  if p_risk_class='D3' or p_authority_class='D3'
     or crm.penta_persona_authority_rank_v1(p_risk_class)>crm.penta_persona_authority_rank_v1(v_cap.authority_ceiling)
     or crm.penta_persona_authority_rank_v1(p_authority_class)>crm.penta_persona_authority_rank_v1(v_cap.authority_ceiling)
     or crm.penta_persona_authority_rank_v1(p_authority_class)>crm.penta_persona_authority_rank_v1(v_agent.risk_ceiling) then
    v_state:='held_authority';
  end if;

  if not crm.penta_persona_payload_safe_v1(coalesce(p_input,'{}'::jsonb))
     or not crm.penta_persona_payload_safe_v1(coalesce(p_context,'{}'::jsonb)) then
    raise exception 'SECRET_BEARING_PAYLOAD_REJECTED';
  end if;

  if v_state='queued' and v_cap.requires_entitlement then
    if p_entitlement_flow_id is not null then
      select exists(
        select 1 from crm.penta_service_intake_flow_v1 f
        where f.flow_id=p_entitlement_flow_id
          and f.entitlement_state in ('active','granted','verified','fulfilled')
          and f.payment_state in ('paid','verified','not_required','free')
          and (f.amount_due_cents=0 or f.payment_verified_at is not null)
      ) into v_entitlement_ok;
    end if;
    if not v_entitlement_ok then v_state:='held_entitlement'; end if;
  end if;

  if v_state='queued' and v_cap.requires_chlom_invocation then
    if p_chlom_invocation_id is not null then
      v_chlom_ok:=public.chlom_capability_invocation_validate(
        p_chlom_invocation_id,
        coalesce(v_cap.config->>'chlom_capability_id',p_capability_key),
        p_authority_class,300
      );
    end if;
    if not v_chlom_ok then v_state:='held_chlom'; end if;
  end if;

  v_key:=coalesce(nullif(trim(p_idempotency_key),''),
    'ct:persona-exec:'||coalesce(p_work_id::text,'no-work')||':'||p_persona_id||':'||p_capability_key);
  if length(v_key)<12 then raise exception 'IDEMPOTENCY_KEY_TOO_SHORT'; end if;
  v_corr:='ctcorr:'||gen_random_uuid()::text;

  insert into crm.penta_persona_execution_requests_v1(
    work_id,persona_id,agent_id,capability_key,idempotency_key,correlation_id,
    risk_class,authority_class,state,entitlement_flow_id,chlom_invocation_id,
    input,context,max_attempts,simulation
  ) values(
    p_work_id,p_persona_id,v_agent.agent_id,p_capability_key,v_key,v_corr,
    p_risk_class,p_authority_class,v_state,p_entitlement_flow_id,p_chlom_invocation_id,
    coalesce(p_input,'{}'::jsonb),coalesce(p_context,'{}'::jsonb),v_control.max_attempts,p_simulation
  )
  on conflict(idempotency_key) do update set updated_at=now()
  returning * into v_req;

  perform crm.penta_persona_append_execution_event_v1(
    v_req.request_id,case when v_req.state='queued' then 'execution.enqueued' else 'execution.held' end,
    v_agent.agent_id,v_req.correlation_id,v_req.state,
    jsonb_build_object('capability_key',p_capability_key,'work_id',p_work_id,'risk_class',p_risk_class,
                       'authority_class',p_authority_class,'idempotency_key',v_key,'simulation',p_simulation)
  );
  return jsonb_build_object('status','ok','request_id',v_req.request_id,'state',v_req.state,
                            'correlation_id',v_req.correlation_id,'idempotent',v_req.idempotency_key=v_key,
                            'd3_auto',false,'authority_expansion',false);
end $$;

create or replace function crm.penta_persona_execute_one_v1(p_request_id uuid,p_worker_ref text default 'penta.persona-executor.v1')
returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm','public','developer_commerce','extensions'
as $$
declare
  r crm.penta_persona_execution_requests_v1%rowtype;
  c crm.penta_persona_execution_capabilities_v1%rowtype;
  ctl crm.penta_persona_execution_control_v1%rowtype;
  out jsonb:='{}'::jsonb;
  target_persona text; target_agent text; child_work uuid;
  v_action text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  select * into ctl from crm.penta_persona_execution_control_v1 where control_key='default';
  if not found or not ctl.active or ctl.kill_switch then
    return jsonb_build_object('status','hold','reason','EXECUTION_BRIDGE_DISABLED');
  end if;

  select * into r from crm.penta_persona_execution_requests_v1 where request_id=p_request_id for update;
  if not found then raise exception 'REQUEST_NOT_FOUND'; end if;
  if r.state='succeeded' then return jsonb_build_object('status','ok','state','succeeded','idempotent_replay',true,'result',r.result); end if;
  if r.state not in ('queued','retry_wait') or r.next_attempt_at>now() then
    return jsonb_build_object('status','hold','state',r.state,'reason','REQUEST_NOT_READY');
  end if;
  select * into c from crm.penta_persona_execution_capabilities_v1
   where persona_id=r.persona_id and capability_key=r.capability_key and enabled=true;
  if not found or c.certification_state='hold' then
    update crm.penta_persona_execution_requests_v1 set state='failed_terminal',error_code='CAPABILITY_DISABLED',completed_at=now(),updated_at=now()
      where request_id=r.request_id;
    return jsonb_build_object('status','failed','state','failed_terminal','reason','CAPABILITY_DISABLED');
  end if;
  if r.risk_class='D3' or r.authority_class='D3' then
    update crm.penta_persona_execution_requests_v1 set state='held_authority',error_code='D3_HUMAN_RESERVED',updated_at=now()
      where request_id=r.request_id;
    return jsonb_build_object('status','hold','state','held_authority','reason','D3_HUMAN_RESERVED','d3_auto',false);
  end if;

  update crm.penta_persona_execution_requests_v1
    set state='running',attempt_count=attempt_count+1,claimed_by=p_worker_ref,
        lease_expires_at=now()+interval '2 minutes',started_at=coalesce(started_at,now()),updated_at=now()
    where request_id=r.request_id
    returning * into r;
  perform crm.penta_persona_append_execution_event_v1(
    r.request_id,'execution.started',p_worker_ref,r.correlation_id,'running',
    jsonb_build_object('capability_key',r.capability_key,'attempt',r.attempt_count)
  );

  begin
    if r.simulation then
      out:=jsonb_build_object('simulation',true,'handler_key',c.handler_key,'effect','NO_PROVIDER_WRITE');
    elsif c.handler_key='penta_system_status' then
      select jsonb_build_object(
        'system_key',s.system_key,'canonical_name',s.canonical_name,'maturity',s.maturity,
        'version',s.version,'risk_ceiling',s.risk_ceiling,'runtime_ref',s.runtime_ref,
        'last_verified_at',s.last_verified_at
      ) into out from public.penta_system_registry s
      where s.system_key=coalesce(r.input->>'system_key',c.penta_system_key);
      out:=coalesce(out,jsonb_build_object('state','not_found','system_key',r.input->>'system_key'));
    elsif c.handler_key='penta_maker_select' then
      out:=public.penta_maker_select_v1(coalesce(r.input->>'artifact_type','system'),coalesce(r.input->'context','{}'::jsonb));
    elsif c.handler_key='penta_mation_run' then
      if coalesce(r.input->>'workflow_id','')='' then raise exception 'workflow_id_required'; end if;
      out:=public.penta_mation_run_bounded_v1(
        r.input->>'workflow_id',
        coalesce((r.input->>'version')::integer,1),
        r.idempotency_key||':pentamation',
        coalesce(r.input->'inputs','{}'::jsonb),
        coalesce(r.input->'trigger_context','{}'::jsonb)||jsonb_build_object('persona_id',r.persona_id,'work_id',r.work_id)
      );
    elsif c.handler_key='chlom_mesh_request' then
      v_action:=coalesce(r.input->>'action_type','inspect');
      if not (c.config->'allowed_actions' ? v_action) then raise exception 'mesh_action_not_allowed'; end if;
      out:=public.chlom_mesh_request_action_v1(
        r.idempotency_key||':mesh',
        v_action,
        coalesce(nullif(r.input->>'target_ref',''),'work:'||coalesce(r.work_id::text,r.request_id::text)),
        coalesce(r.input->>'reason','PentaMarketer persona governed execution'),
        coalesce(r.input->'payload','{}'::jsonb)||
          jsonb_build_object('persona_id',r.persona_id,'agent_id',r.agent_id,'work_id',r.work_id,'correlation_id',r.correlation_id),
        r.risk_class,'A2'
      );
    elsif c.handler_key='virality_knowledge' then
      out:=crm.penta_marketer_virality_knowledge_v1();
    elsif c.handler_key='virality_service_quote' then
      if coalesce(r.input->>'service_key','')='' then raise exception 'service_key_required'; end if;
      out:=developer_commerce.virality_service_quote_v1(r.input->>'service_key');
      if out is null then raise exception 'service_key_not_found'; end if;
    elsif c.handler_key='go_flipbooks_quote' then
      out:=developer_commerce.go_flipbooks_quote_v1(
        coalesce(nullif(r.input->>'customer_identity_ref',''),'work:'||coalesce(r.work_id::text,r.request_id::text)),
        nullif(r.input->>'page_count','')::integer,
        nullif(r.input->>'file_size_mb','')::numeric,
        coalesce(nullif(r.input->>'items','')::integer,1),
        coalesce(r.input->'features','[]'::jsonb),
        nullif(r.input->>'package','')
      );
    elsif c.handler_key='penta_service_quote' then
      if coalesce(r.input->>'service_key','')='' then raise exception 'service_key_required'; end if;
      out:=developer_commerce.penta_service_quote_v2(
        coalesce(nullif(r.input->>'customer_identity_ref',''),'work:'||coalesce(r.work_id::text,r.request_id::text)),
        coalesce(nullif(r.input->>'source_system',''),'penta_persona_execution'),
        coalesce(r.input->>'source_message_id',coalesce(r.work_id::text,r.request_id::text)),
        r.input->>'service_key',
        coalesce(r.input->>'summary','PentaMarketer governed service qualification'),
        coalesce((r.input->>'test_mode')::boolean,false),
        r.idempotency_key||':service'
      );
    elsif c.handler_key='persona_handoff' then
      target_persona:=r.input->>'target_persona_id';
      if coalesce(target_persona,'')='' then raise exception 'target_persona_id_required'; end if;
      select a.agent_id into target_agent from crm.penta_marketer_agents_v2 a
       where a.persona_id=target_persona and a.enabled=true and a.autonomous=true and a.state='active'
       order by a.agent_id limit 1;
      if target_agent is null then raise exception 'target_persona_not_active'; end if;
      insert into crm.penta_marketer_work_queue_v1(
        dedupe_key,source_system,source_event_id,channel,work_class,purpose,summary,recipient,
        assigned_agent_id,assigned_persona_id,opportunity_score,urgency_score,authority_class,
        requires_founder_attention,state,payload
      )
      select
        'persona-handoff:'||r.request_id::text||':'||target_persona,
        'penta-persona-execution',r.request_id::text,'internal',
        coalesce(r.input->>'work_class',w.work_class,'persona_handoff'),
        coalesce(r.input->>'purpose',w.purpose,'specialist_handoff'),
        coalesce(r.input->>'summary',w.summary,'PentaMarketer specialist handoff'),
        w.recipient,target_agent,target_persona,w.opportunity_score,w.urgency_score,
        case least(crm.penta_persona_authority_rank_v1(w.authority_class),2) when 0 then 'D0' when 1 then 'D1' else 'D2' end,
        w.requires_founder_attention,'routed',
        jsonb_build_object('parent_work_id',r.work_id,'parent_execution_request_id',r.request_id,'handoff_reason',r.input->>'reason')
      from crm.penta_marketer_work_queue_v1 w where w.work_id=r.work_id
      on conflict(dedupe_key) do update set updated_at=now()
      returning work_id into child_work;
      if child_work is null then raise exception 'handoff_requires_work_id'; end if;
      out:=jsonb_build_object('state','routed','child_work_id',child_work,'target_persona_id',target_persona,'target_agent_id',target_agent);
    else
      raise exception 'UNREGISTERED_HANDLER:%',c.handler_key;
    end if;

    update crm.penta_persona_execution_requests_v1
      set state='succeeded',result=coalesce(out,'{}'::jsonb),
          evidence_refs=evidence_refs||jsonb_build_array(jsonb_build_object(
            'type','execution_receipt','handler_key',c.handler_key,'penta_system_key',c.penta_system_key,
            'completed_at',now(),'provider_write_authority',false,'money_movement_authority',false,
            'rights_grant_authority',false,'credential_body_exposed',false,'d3_auto',false
          )),
          completed_at=now(),lease_expires_at=null,error_code=null,error_message=null,updated_at=now()
      where request_id=r.request_id;
    perform crm.penta_persona_append_execution_event_v1(
      r.request_id,'execution.succeeded',p_worker_ref,r.correlation_id,'succeeded',
      jsonb_build_object('handler_key',c.handler_key,'penta_system_key',c.penta_system_key,
                         'result_digest',encode(extensions.digest(convert_to(coalesce(out,'{}'::jsonb)::text,'UTF8'),'sha256'),'hex'))
    );
    return jsonb_build_object('status','ok','request_id',r.request_id,'state','succeeded','result',out,
                              'provider_write_authority',false,'money_movement_authority',false,
                              'rights_grant_authority',false,'credential_body_exposed',false,'d3_auto',false);
  exception when others then
    update crm.penta_persona_execution_requests_v1
      set state=case when attempt_count>=max_attempts then 'failed_terminal' else 'retry_wait' end,
          next_attempt_at=case when attempt_count>=max_attempts then next_attempt_at
            else now()+make_interval(secs=>least(900,15*power(2,greatest(0,attempt_count-1))::integer)) end,
          lease_expires_at=null,error_code=sqlstate,error_message=left(sqlerrm,500),updated_at=now(),
          completed_at=case when attempt_count>=max_attempts then now() else completed_at end
      where request_id=r.request_id;
    perform crm.penta_persona_append_execution_event_v1(
      r.request_id,'execution.failed',p_worker_ref,r.correlation_id,
      case when r.attempt_count>=r.max_attempts then 'failed_terminal' else 'retry_wait' end,
      jsonb_build_object('sqlstate',sqlstate,'error',left(sqlerrm,300),'attempt',r.attempt_count)
    );
    return jsonb_build_object('status','failed','request_id',r.request_id,
      'state',case when r.attempt_count>=r.max_attempts then 'failed_terminal' else 'retry_wait' end,
      'error_code',sqlstate,'error',left(sqlerrm,300));
  end;
end $$;

create or replace function crm.penta_persona_execution_tick_v1(p_limit integer default 10)
returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm'
as $$
declare x record; results jsonb:='[]'::jsonb; lim integer;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtext('ct:penta-persona-execution:v1')) then
    return jsonb_build_object('status','skipped_locked','results','[]'::jsonb);
  end if;
  select least(greatest(coalesce(p_limit,10),1),max_batch_size) into lim
  from crm.penta_persona_execution_control_v1 where control_key='default';
  for x in
    select request_id from crm.penta_persona_execution_requests_v1
    where state in ('queued','retry_wait') and next_attempt_at<=now()
    order by case risk_class when 'D2' then 0 when 'D1' then 1 else 2 end,created_at
    limit lim for update skip locked
  loop
    results:=results||jsonb_build_array(crm.penta_persona_execute_one_v1(x.request_id,'penta.persona-executor.v1'));
  end loop;
  return jsonb_build_object('status','ok','processed',jsonb_array_length(results),'results',results,'at',now());
end $$;

create or replace function crm.penta_persona_execution_scheduler_tick_v1(p_limit integer default 25)
returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm'
as $$
declare w record; p record; enq jsonb; n integer:=0;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if not exists(select 1 from crm.penta_persona_execution_control_v1 where control_key='default' and active and automation_enabled and not kill_switch) then
    return jsonb_build_object('status','disabled','enqueued',0);
  end if;
  if not pg_try_advisory_xact_lock(hashtext('ct:penta-persona-execution-scheduler:v1')) then
    return jsonb_build_object('status','skipped_locked','enqueued',0);
  end if;
  for w in
    select q.* from crm.penta_marketer_work_queue_v1 q
    where q.state in ('routed','queued')
      and not exists(select 1 from crm.penta_persona_execution_requests_v1 e where e.work_id=q.work_id)
    order by q.urgency_score desc,q.created_at
    limit least(greatest(coalesce(p_limit,25),1),100)
  loop
    select pb.* into p from crm.penta_persona_execution_playbooks_v1 pb
    where pb.enabled and pb.auto_enqueue
      and (pb.persona_id is null or pb.persona_id=w.assigned_persona_id)
      and (pb.work_class is null or pb.work_class=w.work_class)
      and (pb.purpose is null or pb.purpose=w.purpose)
      and exists(select 1 from crm.penta_persona_execution_capabilities_v1 c
                 where c.persona_id=w.assigned_persona_id and c.capability_key=pb.capability_key and c.enabled)
    order by
      ((pb.persona_id is not null)::integer + (pb.work_class is not null)::integer + (pb.purpose is not null)::integer) desc,
      pb.priority asc
    limit 1;
    if found then
      enq:=crm.penta_persona_enqueue_execution_v1(
        w.work_id,w.assigned_persona_id,p.capability_key,
        p.input_template||
          case when p.capability_key='chlom.mesh.request' then jsonb_build_object(
            'target_ref','work:'||w.work_id::text,'reason',coalesce(w.summary,w.purpose),
            'payload',jsonb_build_object('work_id',w.work_id,'source_system',w.source_system,'source_event_id',w.source_event_id,
                                         'work_class',w.work_class,'purpose',w.purpose,'assigned_persona_id',w.assigned_persona_id)
          ) else '{}'::jsonb end,
        jsonb_build_object('scheduler','penta.persona-execution.v1','work_class',w.work_class,'purpose',w.purpose),
        case least(crm.penta_persona_authority_rank_v1(w.authority_class),crm.penta_persona_authority_rank_v1(p.risk_class)) when 0 then 'D0' when 1 then 'D1' else 'D2' end,
        case least(crm.penta_persona_authority_rank_v1(w.authority_class),crm.penta_persona_authority_rank_v1(p.authority_class)) when 0 then 'D0' when 1 then 'D1' else 'D2' end,
        'auto:'||w.work_id::text||':'||p.playbook_key,null,null,false
      );
      if enq->>'state'='queued' then n:=n+1; end if;
    end if;
  end loop;
  return jsonb_build_object('status','ok','enqueued',n,'at',now());
end $$;

create or replace function crm.penta_persona_execution_status_v1(p_request_id uuid default null)
returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm'
as $$
declare out jsonb;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if p_request_id is not null then
    select to_jsonb(r) into out from crm.penta_persona_execution_requests_v1 r where r.request_id=p_request_id;
    return coalesce(out,jsonb_build_object('state','not_found'));
  end if;
  select jsonb_build_object(
    'component','ct.pentamarketer.persona-execution-bridge','version',c.component_version,
    'active',c.active,'automation_enabled',c.automation_enabled,'kill_switch',c.kill_switch,
    'certification_state',c.certification_state,'certification_id',c.certification_id,
    'capability_bindings',(select count(*) from crm.penta_persona_execution_capabilities_v1 where enabled),
    'covered_personas',(select count(distinct persona_id) from crm.penta_persona_execution_capabilities_v1 where enabled),
    'requests_by_state',(select coalesce(jsonb_object_agg(state,n),'{}'::jsonb) from
      (select state,count(*) n from crm.penta_persona_execution_requests_v1 group by state) s),
    'cron_active',exists(select 1 from cron.job where jobname='penta-persona-execution-v1' and active),
    'at',now()
  ) into out from crm.penta_persona_execution_control_v1 c where c.control_key='default';
  return out;
end $$;

create or replace function crm.penta_persona_execution_canary_v1()
returns jsonb language plpgsql security definer
set search_path='pg_catalog','crm','public'
as $$
declare
  v_persona text; q1 jsonb; q2 jsonb; q3 jsonb; rid uuid;
  checks jsonb:='[]'::jsonb; all_pass boolean;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  perform crm.penta_persona_capability_sync_v1();
  select a.persona_id into v_persona from crm.penta_marketer_agents_v2 a
   where a.enabled and a.autonomous and a.state='active' order by a.persona_id limit 1;

  q1:=crm.penta_persona_enqueue_execution_v1(null,v_persona,'penta.system.status',
    jsonb_build_object('system_key','penta.mation'),'{}'::jsonb,'D0','D0',
    'canary:persona-exec:status:'||to_char(clock_timestamp(),'YYYYMMDDHH24MISSUS'),null,null,false);
  rid:=(q1->>'request_id')::uuid;
  q2:=crm.penta_persona_execute_one_v1(rid,'penta.persona-exec.canary');
  q3:=crm.penta_persona_enqueue_execution_v1(null,v_persona,'penta.system.status',
    jsonb_build_object('system_key','penta.mation'),'{}'::jsonb,'D3','D3',
    'canary:persona-exec:d3:'||to_char(clock_timestamp(),'YYYYMMDDHH24MISSUS'),null,null,true);

  checks:=checks||jsonb_build_array(
    jsonb_build_object('check','safe_execution_succeeds','passed',q2->>'state'='succeeded','evidence',q2),
    jsonb_build_object('check','d3_fail_closed','passed',q3->>'state'='held_authority','evidence',q3),
    jsonb_build_object('check','rls_enabled','passed',not exists(
      select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
      where n.nspname='crm' and c.relname in (
        'penta_persona_execution_control_v1','penta_persona_execution_capabilities_v1',
        'penta_persona_execution_playbooks_v1','penta_persona_execution_requests_v1','penta_persona_execution_events_v1'
      ) and not c.relrowsecurity),'evidence','crm execution tables'),
    jsonb_build_object('check','client_execute_revoked','passed',not exists(
      select 1 from information_schema.routine_privileges rp
      where rp.routine_schema='crm' and rp.routine_name like 'penta_persona_%'
        and rp.grantee in ('anon','authenticated') and rp.privilege_type='EXECUTE'),'evidence','routine ACLs'),
    jsonb_build_object('check','base_persona_coverage','passed',not exists(
      select 1 from crm.penta_marketer_agents_v2 a
      where a.enabled and a.autonomous and a.state='active'
        and not exists(select 1 from crm.penta_persona_execution_capabilities_v1 c
                       where c.persona_id=a.persona_id and c.capability_key='chlom.mesh.request' and c.enabled)),
      'evidence','all active autonomous personas')
  );
  select not exists(select 1 from jsonb_array_elements(checks) x where coalesce((x->>'passed')::boolean,false)=false) into all_pass;
  return jsonb_build_object('component','ct.pentamarketer.persona-execution-bridge','version','1.0.0',
    'all_pass',all_pass,'checks',checks,'d3_auto',false,'provider_write_authority',false,
    'money_movement_authority',false,'rights_grant_authority',false,'credential_body_exposed',false,'at',now());
end $$;

revoke execute on function crm.penta_persona_authority_rank_v1(text) from public,anon,authenticated;
revoke execute on function crm.penta_persona_payload_safe_v1(jsonb) from public,anon,authenticated;
revoke execute on function crm.penta_persona_append_execution_event_v1(uuid,text,text,text,text,jsonb) from public,anon,authenticated;
revoke execute on function crm.penta_persona_capability_sync_v1() from public,anon,authenticated;
revoke execute on function crm.penta_persona_enqueue_execution_v1(uuid,text,text,jsonb,jsonb,text,text,text,uuid,uuid,boolean) from public,anon,authenticated;
revoke execute on function crm.penta_persona_execute_one_v1(uuid,text) from public,anon,authenticated;
revoke execute on function crm.penta_persona_execution_tick_v1(integer) from public,anon,authenticated;
revoke execute on function crm.penta_persona_execution_scheduler_tick_v1(integer) from public,anon,authenticated;
revoke execute on function crm.penta_persona_execution_status_v1(uuid) from public,anon,authenticated;
revoke execute on function crm.penta_persona_execution_canary_v1() from public,anon,authenticated;

revoke execute on function crm.penta_persona_execution_event_immutable_v1() from public,anon,authenticated;
grant execute on function crm.penta_persona_authority_rank_v1(text) to service_role;
grant execute on function crm.penta_persona_payload_safe_v1(jsonb) to service_role;
grant execute on function crm.penta_persona_append_execution_event_v1(uuid,text,text,text,text,jsonb) to service_role;
grant execute on function crm.penta_persona_capability_sync_v1() to service_role;
grant execute on function crm.penta_persona_enqueue_execution_v1(uuid,text,text,jsonb,jsonb,text,text,text,uuid,uuid,boolean) to service_role;
grant execute on function crm.penta_persona_execute_one_v1(uuid,text) to service_role;
grant execute on function crm.penta_persona_execution_tick_v1(integer) to service_role;
grant execute on function crm.penta_persona_execution_scheduler_tick_v1(integer) to service_role;
grant execute on function crm.penta_persona_execution_status_v1(uuid) to service_role;
grant execute on function crm.penta_persona_execution_canary_v1() to service_role;

insert into public.penta_system_registry(
  system_key,canonical_name,category,purpose,authority_boundary,risk_ceiling,maturity,
  version,public_exposure,docs_ref,runtime_ref,metadata,last_verified_at,updated_at
) values(
  'penta.persona-execution','PentaMarketer Persona Execution Bridge','agentic_runtime',
  'Turns PentaMarketer persona routing into bounded, idempotent, evidence-backed execution through existing Penta systems.',
  'D0-D2 only; D3 human-reserved; no raw secret access; no direct rights grant, money movement, provider-wide mutation, or merge authority.',
  'D2','implemented','1.0.0',false,
  'data/penta/pentamarketer-persona-execution-bridge.v1.json',
  'postgres:crm.penta_persona_execution_tick_v1',
  jsonb_build_object('component_id','ct.pentamarketer.persona-execution-bridge',
    'broker','least_privilege','idempotent',true,'append_only_events',true,'retry_backoff',true,
    'chlom_gated',true,'pentaservice_gated',true,'d3_auto',false,'automation_state','controlled_test'),
  now(),now()
)
on conflict(system_key) do update set
  purpose=excluded.purpose,authority_boundary=excluded.authority_boundary,risk_ceiling=excluded.risk_ceiling,
  maturity='implemented',version=excluded.version,public_exposure=false,docs_ref=excluded.docs_ref,
  runtime_ref=excluded.runtime_ref,metadata=excluded.metadata,last_verified_at=now(),updated_at=now();

insert into crm.penta_persona_execution_playbooks_v1(
  playbook_key,persona_id,work_class,purpose,capability_key,risk_class,authority_class,input_template,priority,metadata
) values
('security-incident-inspect-v1','ct.persona.crownthrive.security.amara.v1','security_reliability',null,'chlom.mesh.request','D2','D2','{"action_type":"inspect"}',10,'{"effect":"request_only","no_destructive_containment":true}'),
('technology-ops-inspect-v1','ct.persona.crownthrive.tech.nolan.v1','technology_operations',null,'chlom.mesh.request','D1','D1','{"action_type":"inspect"}',20,'{"effect":"request_only"}'),
('virality-tessa-knowledge-v1','ct.persona.virality.licensing.tessa.v1',null,null,'virality.knowledge','D0','D0','{}',30,'{"rights_grant_effect":false}'),
('virality-ellis-knowledge-v1','ct.persona.virality.commissions.ellis.v1',null,null,'virality.knowledge','D0','D0','{}',30,'{"rights_grant_effect":false}'),
('virality-camille-knowledge-v1','ct.persona.virality.ip.camille.v1',null,null,'virality.knowledge','D0','D0','{}',30,'{"rights_grant_effect":false}'),
('backroad-sierra-knowledge-v1','ct.persona.backroad.artist-relations.sierra.v1',null,null,'virality.knowledge','D0','D0','{}',30,'{"editorial_firewall":true}'),
('backroad-malik-knowledge-v1','ct.persona.backroad.programming.malik.v1',null,null,'virality.knowledge','D0','D0','{}',30,'{"editorial_firewall":true}')
on conflict(playbook_key) do update set
  persona_id=excluded.persona_id,work_class=excluded.work_class,purpose=excluded.purpose,
  capability_key=excluded.capability_key,risk_class=excluded.risk_class,authority_class=excluded.authority_class,
  input_template=excluded.input_template,enabled=true,metadata=excluded.metadata,updated_at=now();

select crm.penta_persona_capability_sync_v1();
