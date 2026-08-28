-- PentaMarketer Persona Execution Bridge v1 scheduler hardening.
-- Prevent transport tests, system reports, and simulation-marked work from crossing the domain-execution boundary.

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
      and q.work_class not in ('persona_transport_test','penta_self_report')
      and coalesce((q.payload->>'simulation')::boolean,false)=false
      and coalesce(q.purpose,'') not in ('persona_introduction_stress_test','hourly_healing_report')
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

revoke execute on function crm.penta_persona_execution_scheduler_tick_v1(integer) from public,anon,authenticated;
grant execute on function crm.penta_persona_execution_scheduler_tick_v1(integer) to service_role;
