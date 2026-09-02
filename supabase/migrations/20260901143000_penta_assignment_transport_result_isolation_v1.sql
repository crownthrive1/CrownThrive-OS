-- PentaAssignment transport/result isolation v1.
--
-- Root cause: penta_assignment_reconcile_owner_dispatches_v1() historically converted
-- completed transport/execution evidence into semantic owner PASS. A completed Census handoff
-- or OS20 execution task proves delivery/execution only; neither proves that the assigned owner
-- reached an independent semantic review/certification disposition for this exact head.
--
-- This repair keeps owner-result authority with the assigned owner. Explicit current-head
-- penta_assignment_owner_results_v1 PASS remains authoritative. CENSUS_HANDOFF and OS20_TASK
-- completion without that result become precise HOLDs instead of synthesized PASS.

create or replace function integration_control.penta_assignment_reconcile_owner_dispatches_v1(
  p_assignment_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','penta_os20','extensions'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  d record;
  h record;
  t record;
  v_progress integer:=0;
  v_hold integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;

  for d in
    select *
    from integration_control.penta_assignment_dispatches_v1
    where assignment_id=a.assignment_id
      and state not in ('COMPLETED','SUPERSEDED')
    order by owner_penta,created_at
  loop
    -- The assigned owner's explicit current-head result is the only PASS authority here.
    if exists(
      select 1
      from integration_control.penta_assignment_owner_results_v1 r
      where r.assignment_id=a.assignment_id
        and lower(r.owner_penta)=lower(d.owner_penta)
        and r.result_state='PASS'
        and r.exact_head_sha is not distinct from a.exact_head_sha
    ) then
      update integration_control.penta_assignment_dispatches_v1
      set state='COMPLETED',
          completed_at=coalesce(completed_at,now()),
          evidence=evidence||jsonb_build_object(
            'completion_basis','explicit_current_head_owner_result',
            'semantic_owner_result_required',true,
            'authority_created',false),
          updated_at=now()
      where dispatch_id=d.dispatch_id;
      v_progress:=v_progress+1;
      continue;
    end if;

    if d.dispatch_kind='CENSUS_HANDOFF' then
      select * into h
      from integration_control.penta_census_handoffs_v1
      where handoff_key=d.external_ref;

      if found and h.state='completed' and coalesce((h.payload->>'receipt_count')::integer,0)>0 then
        -- Completed/routed/delivered packet receipts prove transport only.
        update integration_control.penta_assignment_dispatches_v1
        set state='HOLD',
            evidence=evidence||jsonb_build_object(
              'hold_code','HOLD_ASSIGNMENT_OWNER_SEMANTIC_RESULT_MISSING',
              'handoff_state',h.state,
              'packet_id',h.payload->>'packet_id',
              'packet_delivery_state',h.payload->>'packet_delivery_state',
              'receipt_count',coalesce((h.payload->>'receipt_count')::integer,0),
              'required_owner_result','integration_control.penta_assignment_owner_results_v1 current-head PASS',
              'transport_completion_is_not_owner_pass',true,
              'semantic_owner_result_required',true,
              'authority_created',false),
            updated_at=now()
        where dispatch_id=d.dispatch_id;
        v_hold:=v_hold+1;
      elsif found and h.state in ('failed','approval_required') then
        update integration_control.penta_assignment_dispatches_v1
        set state='HOLD',
            evidence=evidence||jsonb_build_object(
              'hold_code',case when h.state='failed'
                then 'HOLD_ASSIGNMENT_DISPATCH_FAILED_READBACK'
                else 'HOLD_ASSIGNMENT_OWNER_ROUTE_UNREGISTERED' end,
              'handoff_state',h.state,
              'semantic_owner_result_required',true,
              'authority_created',false),
            updated_at=now()
        where dispatch_id=d.dispatch_id;
        v_hold:=v_hold+1;
      end if;

    elsif d.dispatch_kind='OS20_TASK' then
      select * into t
      from penta_os20.execution_tasks
      where id=d.external_ref::uuid;

      if found and t.status='completed' and t.completed_at is not null then
        -- OS20 completion proves bounded execution only. It cannot create an owner PASS.
        update integration_control.penta_assignment_dispatches_v1
        set state='HOLD',
            evidence=evidence||jsonb_build_object(
              'hold_code','HOLD_ASSIGNMENT_OWNER_SEMANTIC_RESULT_MISSING',
              'execution_mode','verified_os20_task',
              'task_id',t.id,
              'task_key',t.task_key,
              'operation_key',t.operation_key,
              'completed_at',t.completed_at,
              'required_owner_result','integration_control.penta_assignment_owner_results_v1 current-head PASS',
              'execution_completion_is_not_owner_pass',true,
              'semantic_owner_result_required',true,
              'authority_created',false),
            updated_at=now()
        where dispatch_id=d.dispatch_id;
        v_hold:=v_hold+1;
      elsif found and t.status='needs_help' then
        update integration_control.penta_assignment_dispatches_v1
        set state='HOLD',
            evidence=evidence||jsonb_build_object(
              'hold_code','HOLD_ASSIGNMENT_OS20_TASK_NEEDS_HELP',
              'task_id',t.id,
              'semantic_owner_result_required',true,
              'authority_created',false),
            updated_at=now()
        where dispatch_id=d.dispatch_id;
        v_hold:=v_hold+1;
      end if;
    end if;
  end loop;

  return jsonb_build_object(
    'assignment_id',a.assignment_id,
    'state',case when v_hold>0 then 'SUCCESS_HOLD'
                 when v_progress>0 then 'SUCCESS_PROGRESS'
                 else 'SUCCESS_NO_CHANGE' end,
    'new_pass_results',0,
    'completed_from_existing_owner_results',v_progress,
    'holds',v_hold,
    'transport_completion_is_not_owner_pass',true,
    'execution_completion_is_not_owner_pass',true,
    'semantic_owner_result_required',true,
    'authority_expansion',false,
    'observed_at',clock_timestamp());
end
$function$;

revoke all on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid)
  from public,anon,authenticated;
grant execute on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid)
  to service_role;

comment on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid) is
'Reconciles assignment owner execution without converting transport or OS20 execution completion into owner PASS. CENSUS_HANDOFF and OS20_TASK completion require an explicit exact-head owner result.';
