-- CrownThrive Penta Assignment owner-routing hard repair v1
-- Purpose: eliminate false target_node_unavailable failures, preserve typed HOLDs,
-- route only through registered executable targets, and convert only completed
-- real dispatches into immutable owner-result evidence.

create table if not exists integration_control.penta_assignment_owner_routes_v1 (
  owner_penta text primary key,
  identity_key text,
  dispatch_kind text not null check (dispatch_kind in ('CENSUS_HANDOFF','OS20_TASK')),
  target_ref text,
  authority_ceiling text not null default 'D2' check (authority_ceiling in ('D0','D1','D2')),
  active boolean not null default true,
  source_ref text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into integration_control.penta_assignment_owner_routes_v1
  (owner_penta,identity_key,dispatch_kind,target_ref,authority_ceiling,active,source_ref,metadata)
values
  ('PentaBuild','penta.build','CENSUS_HANDOFF','penta.build','D2',true,'ct.penta.assignment-owner-routing-repair.v1',jsonb_build_object('target_node_id','ct.penta.factory.software','authority_created',false)),
  ('PentaWire','penta.wire','CENSUS_HANDOFF','ct.agent.penta-wire','D2',true,'ct.penta.assignment-owner-routing-repair.v1',jsonb_build_object('target_node_id','ct.penta.wire','authority_created',false)),
  ('PentaCertify','penta.certify','CENSUS_HANDOFF','penta.certify','D2',true,'ct.penta.assignment-owner-routing-repair.v1',jsonb_build_object('target_node_id','ct.penta.certify','authority_created',false)),
  ('PentaRelease','penta.release','CENSUS_HANDOFF','penta.release','D2',true,'ct.penta.assignment-owner-routing-repair.v1',jsonb_build_object('target_node_id','ct.penta.release','authority_created',false))
on conflict(owner_penta) do update set
  identity_key=excluded.identity_key,
  dispatch_kind=excluded.dispatch_kind,
  target_ref=excluded.target_ref,
  authority_ceiling=excluded.authority_ceiling,
  active=excluded.active,
  source_ref=excluded.source_ref,
  metadata=integration_control.penta_assignment_owner_routes_v1.metadata||excluded.metadata,
  updated_at=now();

create or replace function integration_control.penta_assignment_route_v2(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_os20','extensions','chlom_runtime','public'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  v_owner text;
  v_penta_id uuid;
  v_task_id uuid;
  v_discovery_key text;
  v_handoff_key text;
  v_payload jsonb;
  v_sha text;
  v_dispatches integer:=0;
  v_holds integer:=0;
  v_event jsonb;
  v_route integration_control.penta_assignment_owner_routes_v1%rowtype;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id for update;
  if not found then raise exception 'assignment_not_found'; end if;
  if a.state in ('COMPLETED','SUPERSEDED','RETIRED') then
    return jsonb_build_object('assignment_id',a.assignment_id,'state',a.state,'dispatches',0,'holds',0);
  end if;

  v_discovery_key:='penta-assignment:'||a.assignment_id::text;
  insert into integration_control.penta_census_discoveries_v1(
    discovery_key,entity_kind,entity_key,canonical_name,source_ref,tags,rationale,risk_class,state,evidence
  ) values (
    v_discovery_key,'penta_assignment',a.assignment_key,a.title,a.exact_artifact_ref,
    array['assignment',a.owning_family_key,a.task_kind]::text[],
    'Governed assignment accepted for owner execution and institutional completion.',a.risk_class,'routed',
    jsonb_build_object('assignment_id',a.assignment_id,'owner_pentas',a.owner_pentas,'authority_expansion',false)
  ) on conflict(discovery_key) do update set
    last_seen_at=now(),
    state=case when integration_control.penta_census_discoveries_v1.state='resolved' then 'resolved' else 'routed' end,
    evidence=integration_control.penta_census_discoveries_v1.evidence||excluded.evidence;

  for v_owner in select jsonb_array_elements_text(a.owner_pentas) loop
    v_payload:=jsonb_build_object(
      'contract','ct.penta.assignment-fulfillment.v1','assignment_id',a.assignment_id,'assignment_key',a.assignment_key,
      'subject_ref',a.subject_ref,'task_kind',a.task_kind,'title',a.title,'summary',a.summary,
      'family_key',a.owning_family_key,'owner_penta',v_owner,'risk_class',a.risk_class,
      'authority_ceiling',a.authority_ceiling,'exact_artifact_ref',a.exact_artifact_ref,
      'exact_artifact_sha256',a.exact_artifact_sha256,'source_repo',a.source_repo,
      'source_pr_number',a.source_pr_number,'exact_head_sha',a.exact_head_sha,
      'acceptance_criteria',a.acceptance_criteria,'required_projections',to_jsonb(a.required_projections),
      'money_movement',false,'credential_change',false,'d3_execution',false,'authority_expansion',false
    );
    v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');

    select * into v_route
    from integration_control.penta_assignment_owner_routes_v1
    where lower(owner_penta)=lower(v_owner) and active=true and authority_ceiling in ('D0','D1','D2')
    limit 1;

    if found and v_route.dispatch_kind='CENSUS_HANDOFF' and nullif(v_route.target_ref,'') is not null then
      v_handoff_key:='assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g'));
      insert into integration_control.penta_census_handoffs_v1(handoff_key,discovery_key,tag,target_ref,risk_class,state,authority_note,payload)
      values(
        v_handoff_key,v_discovery_key,'assignment:'||a.task_kind,v_route.target_ref,a.risk_class,'queued',
        'D0-D2 registered owner route; target retains its own authority and certification boundaries.',
        v_payload||jsonb_build_object('owner_route_source',v_route.source_ref,'owner_identity_key',v_route.identity_key,'registered_target_ref',v_route.target_ref)
      ) on conflict(handoff_key) do update set
        target_ref=excluded.target_ref,
        authority_note=excluded.authority_note,
        payload=integration_control.penta_census_handoffs_v1.payload||excluded.payload,
        state=case when integration_control.penta_census_handoffs_v1.state='completed' then 'completed' else 'queued' end,
        updated_at=now();
      insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
      values(a.assignment_id,v_owner,a.owning_family_key,'CENSUS_HANDOFF',v_handoff_key,'ROUTED',v_payload,v_sha)
      on conflict(assignment_id,owner_penta,dispatch_kind) do update set
        external_ref=excluded.external_ref,state='ROUTED',evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
    else
      select id into v_penta_id from penta_os20.pentas where lower(canonical_name)=lower(v_owner) and status='active' limit 1;
      if v_penta_id is not null then
        insert into penta_os20.execution_tasks(task_key,penta_id,release_version,operation_key,estimated_units,status,authority_check)
        values('assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g')),v_penta_id,'OS-2.0.0',a.task_kind,1,'queued',v_payload)
        on conflict(task_key) do update set authority_check=penta_os20.execution_tasks.authority_check||excluded.authority_check
        returning id into v_task_id;
        begin perform public.penta_os20_authorize_task(v_task_id); exception when others then null; end;
        insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
        values(a.assignment_id,v_owner,a.owning_family_key,'OS20_TASK',v_task_id::text,'ROUTED',v_payload,v_sha)
        on conflict(assignment_id,owner_penta,dispatch_kind) do update set
          external_ref=excluded.external_ref,state='ROUTED',evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
      else
        v_handoff_key:='assignment:'||a.assignment_id::text||':'||lower(regexp_replace(v_owner,'[^A-Za-z0-9]+','-','g'));
        insert into integration_control.penta_census_handoffs_v1(handoff_key,discovery_key,tag,target_ref,risk_class,state,authority_note,payload)
        values(
          v_handoff_key,v_discovery_key,'assignment:'||a.task_kind,v_owner,a.risk_class,'approval_required',
          'HOLD_ASSIGNMENT_OWNER_ROUTE_UNREGISTERED: owner has no registered executable route; no authority was created.',
          v_payload||jsonb_build_object('hold_code','HOLD_ASSIGNMENT_OWNER_ROUTE_UNREGISTERED','authority_created',false)
        ) on conflict(handoff_key) do update set
          authority_note=excluded.authority_note,
          payload=integration_control.penta_census_handoffs_v1.payload||excluded.payload,
          state=case when integration_control.penta_census_handoffs_v1.state='completed' then 'completed' else 'approval_required' end,
          updated_at=now();
        insert into integration_control.penta_assignment_dispatches_v1(assignment_id,owner_penta,family_key,dispatch_kind,external_ref,state,evidence,evidence_sha256)
        values(a.assignment_id,v_owner,a.owning_family_key,'CENSUS_HANDOFF',v_handoff_key,'HOLD',v_payload||jsonb_build_object('hold_code','HOLD_ASSIGNMENT_OWNER_ROUTE_UNREGISTERED'),v_sha)
        on conflict(assignment_id,owner_penta,dispatch_kind) do update set
          external_ref=excluded.external_ref,state='HOLD',evidence=excluded.evidence,evidence_sha256=excluded.evidence_sha256,updated_at=now();
        v_holds:=v_holds+1;
      end if;
    end if;
    v_dispatches:=v_dispatches+1;
  end loop;

  update integration_control.penta_assignment_contracts_v1
  set state=case when state='DISCOVERED' then 'ROUTED' else state end,updated_at=now()
  where assignment_id=a.assignment_id;

  v_event:=chlom_runtime.append_dail_event(
    'penta.assignment.routed','penta_assignment',a.assignment_id::text,
    jsonb_build_object('assignment_key',a.assignment_key,'family_key',a.owning_family_key,'owner_pentas',a.owner_pentas,
      'dispatch_count',v_dispatches,'route_holds',v_holds,'router_version','v2','authority_expansion',false,'routed_at',clock_timestamp()),
    'PentaAssignmentFabric/PentaCensus/PentaWire/PentaRoute',null,'PentaAssignmentFabric','2.0.0',
    'ctcorr:penta-assignment:'||a.assignment_id::text,null,'ct.penta.assignment-fulfillment.v1',null,'internal'
  );
  return jsonb_build_object('assignment_id',a.assignment_id,'state','ROUTED','dispatches',v_dispatches,'holds',v_holds,'event',v_event,'authority_expansion',false);
end $$;

create or replace function integration_control.penta_assignment_route_v1(p_assignment_id uuid)
returns jsonb
language sql security definer
set search_path to 'pg_catalog','integration_control'
as $$
  select integration_control.penta_assignment_route_v2(p_assignment_id);
$$;

create or replace function integration_control.penta_assignment_reconcile_owner_dispatches_v1(p_assignment_id uuid)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','penta_os20','extensions'
as $$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
  d record;
  h record;
  t record;
  v_result jsonb;
  v_pass integer:=0;
  v_hold integer:=0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select * into a from integration_control.penta_assignment_contracts_v1 where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;

  for d in
    select * from integration_control.penta_assignment_dispatches_v1
    where assignment_id=a.assignment_id and state not in ('COMPLETED','SUPERSEDED')
    order by owner_penta,created_at
  loop
    if exists(
      select 1 from integration_control.penta_assignment_owner_results_v1 r
      where r.assignment_id=a.assignment_id and lower(r.owner_penta)=lower(d.owner_penta)
        and r.result_state='PASS' and r.exact_head_sha is not distinct from a.exact_head_sha
    ) then
      update integration_control.penta_assignment_dispatches_v1 set state='COMPLETED',completed_at=coalesce(completed_at,now()),updated_at=now() where dispatch_id=d.dispatch_id;
      continue;
    end if;

    if d.dispatch_kind='CENSUS_HANDOFF' then
      select * into h from integration_control.penta_census_handoffs_v1 where handoff_key=d.external_ref;
      if found and h.state='completed' and coalesce((h.payload->>'receipt_count')::integer,0)>0 then
        v_result:=integration_control.penta_assignment_record_owner_result_v1(
          a.assignment_id,d.owner_penta,'PASS',a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,
          jsonb_build_object('execution_mode','verified_census_handoff','handoff_key',h.handoff_key,'target_ref',h.target_ref,
            'packet_id',h.payload->>'packet_id','packet_delivery_state',h.payload->>'packet_delivery_state',
            'receipt_count',coalesce((h.payload->>'receipt_count')::integer,0),'authority_created',false)
        );
        v_pass:=v_pass+1;
      elsif found and h.state in ('failed','approval_required') then
        update integration_control.penta_assignment_dispatches_v1 set
          state='HOLD',evidence=evidence||jsonb_build_object('hold_code',case when h.state='failed' then 'HOLD_ASSIGNMENT_DISPATCH_FAILED_READBACK' else 'HOLD_ASSIGNMENT_OWNER_ROUTE_UNREGISTERED' end,
            'handoff_state',h.state,'authority_created',false),updated_at=now()
        where dispatch_id=d.dispatch_id;
        v_hold:=v_hold+1;
      end if;
    elsif d.dispatch_kind='OS20_TASK' then
      select * into t from penta_os20.execution_tasks where id=d.external_ref::uuid;
      if found and t.status='completed' and t.completed_at is not null then
        v_result:=integration_control.penta_assignment_record_owner_result_v1(
          a.assignment_id,d.owner_penta,'PASS',a.exact_artifact_ref,a.exact_artifact_sha256,a.exact_head_sha,
          jsonb_build_object('execution_mode','verified_os20_task','task_id',t.id,'task_key',t.task_key,
            'operation_key',t.operation_key,'completed_at',t.completed_at,'authority_created',false)
        );
        v_pass:=v_pass+1;
      elsif found and t.status='needs_help' then
        update integration_control.penta_assignment_dispatches_v1 set
          state='HOLD',evidence=evidence||jsonb_build_object('hold_code','HOLD_ASSIGNMENT_OS20_TASK_NEEDS_HELP','task_id',t.id,'authority_created',false),updated_at=now()
        where dispatch_id=d.dispatch_id;
        v_hold:=v_hold+1;
      end if;
    end if;
  end loop;

  return jsonb_build_object('assignment_id',a.assignment_id,'state',case when v_hold>0 then 'SUCCESS_HOLD' when v_pass>0 then 'SUCCESS_PROGRESS' else 'SUCCESS_NO_CHANGE' end,
    'new_pass_results',v_pass,'holds',v_hold,'authority_expansion',false,'observed_at',clock_timestamp());
end $$;

create or replace function integration_control.penta_assignment_fulfillment_tick_v1(p_limit integer default 25)
returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public'
as $$
declare
  a record;
  v_routed integer:=0;
  v_reconciled integer:=0;
  v_institutionalized integer:=0;
  v_os_projected integer:=0;
  v_activated integer:=0;
  v_dispatched integer:=0;
  v_terminalized integer:=0;
  v_result jsonb;
begin
  if session_user not in ('postgres','supabase_admin')
     and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'')<>'service_role'
  then raise exception 'service_role_required'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:assignment-fulfillment:v1',0)) then return jsonb_build_object('state','DEFERRED_CONTENTION'); end if;

  for a in
    select assignment_id,state from integration_control.penta_assignment_contracts_v1
    where state not in ('FAILED','SUPERSEDED','RETIRED')
    order by case priority when 'P0' then 0 when 'P1' then 1 when 'P2' then 2 else 3 end,created_at
    for update skip locked limit greatest(1,least(coalesce(p_limit,25),100))
  loop
    if a.state='DISCOVERED' then
      v_result:=integration_control.penta_assignment_route_v2(a.assignment_id); v_routed:=v_routed+1;
    elsif a.state in ('ROUTED','IN_PROGRESS','AWAITING_PROJECTION','HOLD') then
      v_result:=integration_control.penta_assignment_reconcile_owner_dispatches_v1(a.assignment_id);
      if coalesce((v_result->>'new_pass_results')::integer,0)>0 then v_reconciled:=v_reconciled+1; end if;
      v_result:=integration_control.penta_assignment_institutionalize_v1(a.assignment_id);
      if v_result->>'state' in ('AWAITING_CERTIFICATION','CERTIFIED') then v_institutionalized:=v_institutionalized+1; end if;
    elsif a.state='CERTIFIED' then
      v_result:=integration_control.penta_assignment_project_os_v1(a.assignment_id);
      if v_result->>'state'='READBACK_PASS' then v_os_projected:=v_os_projected+1; end if;
      v_result:=integration_control.penta_assignment_refresh_chain_gate_v1(a.assignment_id);
      if v_result->>'terminal_gate_state'='PASS' then
        v_activated:=v_activated+1;
        v_result:=integration_control.penta_assignment_terminal_dispatch_v1(a.assignment_id);
        if v_result->>'state'='DISPATCHED' then v_dispatched:=v_dispatched+1; end if;
      end if;
    elsif a.state='COMPLETED' then
      if exists(select 1 from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id and l.state in ('LINKED','GATE_HOLD')) then
        v_result:=integration_control.penta_assignment_terminal_dispatch_v1(a.assignment_id);
        if v_result->>'state'='DISPATCHED' then v_dispatched:=v_dispatched+1; end if;
      elsif exists(select 1 from integration_control.penta_assignment_pr_links_v1 l where l.assignment_id=a.assignment_id and l.state='DISPATCHED') then
        v_result:=integration_control.penta_assignment_reconcile_terminal_v1(a.assignment_id);
        if v_result->>'state'='TERMINALIZED' then v_terminalized:=v_terminalized+1; end if;
      end if;
    end if;
  end loop;

  return jsonb_build_object(
    'state','COMPLETE','routed',v_routed,'owner_dispatches_reconciled',v_reconciled,
    'institutionalized',v_institutionalized,'os_projected',v_os_projected,'activated',v_activated,
    'terminal_dispatched',v_dispatched,'terminalized',v_terminalized,'observed_at',clock_timestamp(),'authority_expansion',false
  );
end $$;

revoke all on integration_control.penta_assignment_owner_routes_v1 from anon,authenticated;
revoke all on function integration_control.penta_assignment_route_v2(uuid) from public,anon,authenticated;
revoke all on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid) from public,anon,authenticated;
grant select on integration_control.penta_assignment_owner_routes_v1 to service_role;
grant execute on function integration_control.penta_assignment_route_v2(uuid) to service_role;
grant execute on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid) to service_role;

comment on table integration_control.penta_assignment_owner_routes_v1 is 'Governed executable owner-route registry. Registration does not grant provider, financial, credential, certification, vote/quorum or D3 authority.';
comment on function integration_control.penta_assignment_route_v2(uuid) is 'Routes assignment owners only through registered executable targets or existing OS20 nodes; unresolved routes HOLD instead of false failing.';
comment on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid) is 'Creates immutable owner PASS evidence only after completed dispatch readback with receipts; never auto-completes underlying work.';
