-- CrownThrive OS — Penta persona execution exact work-agent binding
-- A persona may have multiple active autonomous agents/subagents. Work-bound execution
-- must select the exact assigned agent rather than an arbitrary first agent for the persona.

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
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','crm','public'
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

  if p_work_id is not null then
    select * into v_work from crm.penta_marketer_work_queue_v1 where work_id=p_work_id;
    if not found then raise exception 'WORK_NOT_FOUND'; end if;
    if v_work.assigned_persona_id is distinct from p_persona_id then
      raise exception 'WORK_PERSONA_ASSIGNMENT_MISMATCH';
    end if;
    if v_work.assigned_agent_id is null then
      raise exception 'WORK_ASSIGNED_AGENT_REQUIRED';
    end if;
    select * into v_agent from crm.penta_marketer_agents_v2
     where agent_id=v_work.assigned_agent_id
       and persona_id=p_persona_id
       and enabled=true and autonomous=true and state='active';
    if not found then raise exception 'WORK_ASSIGNED_AGENT_NOT_ACTIVE'; end if;
  else
    select * into v_agent from crm.penta_marketer_agents_v2
     where persona_id=p_persona_id and enabled=true and autonomous=true and state='active'
     order by case when coalesce((metadata->>'subagent')::boolean,false) then 1 else 0 end,
              created_at,agent_id
     limit 1;
    if not found then raise exception 'PERSONA_EXECUTOR_NOT_ACTIVE'; end if;
  end if;

  select * into v_cap from crm.penta_persona_execution_capabilities_v1
   where persona_id=p_persona_id and capability_key=p_capability_key and enabled=true;
  if not found or v_cap.certification_state='hold' then raise exception 'CAPABILITY_NOT_ENABLED'; end if;

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
                       'authority_class',p_authority_class,'idempotency_key',v_key,'simulation',p_simulation,
                       'exact_work_agent_binding',p_work_id is not null)
  );
  return jsonb_build_object('status','ok','request_id',v_req.request_id,'state',v_req.state,
                            'agent_id',v_req.agent_id,'correlation_id',v_req.correlation_id,
                            'idempotent',v_req.idempotency_key=v_key,'exact_work_agent_binding',p_work_id is not null,
                            'd3_auto',false,'authority_expansion',false);
end
$$;

revoke all on function crm.penta_persona_enqueue_execution_v1(uuid,text,text,jsonb,jsonb,text,text,text,uuid,uuid,boolean) from public,anon,authenticated;
grant execute on function crm.penta_persona_enqueue_execution_v1(uuid,text,text,jsonb,jsonb,text,text,text,uuid,uuid,boolean) to service_role;
