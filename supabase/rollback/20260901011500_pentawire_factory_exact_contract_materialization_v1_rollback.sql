-- Rollback for PentaWire/PentaFactory exact-provider candidate materialization hardening v1.
-- Restores the pre-change generator/gap-work definitions and removes only the new helper functions.

create or replace function integration_control.penta_wire_generate_gap_work_v1(p_limit integer default 100)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime','public'
as $function$
declare
  b record;
  v_work_id text;
  v_request_key text;
  v_priority integer;
  v_objective text;
  v_requirements jsonb;
  v_reconciled_work integer:=0;
  v_created_requests integer:=0;
  v_existing_state text;
begin
  p_limit:=greatest(1,least(coalesce(p_limit,100),200));
  for b in
    select w.*,s.display_name,s.auth_scheme,s.credential_state,s.write_gate
    from integration_control.penta_wire_service_bindings_v1 w
    join integration_control.services s using(service_id)
    where w.gap_state in ('tool_contract_drift','exact_provider_contract_required')
    order by case w.gap_state when 'tool_contract_drift' then 1 else 2 end,w.service_id
    limit p_limit
  loop
    v_work_id:='ct.work.penta-wire.'||regexp_replace(lower(b.service_id),'[^a-z0-9]+','-','g')||'.v1';
    v_request_key:='penta-wire:'||b.service_id||':'||b.gap_state||':v1';
    v_priority:=case when b.gap_state='tool_contract_drift' then 2 else 3 end;
    v_objective:=case when b.gap_state='tool_contract_drift'
      then 'Reconcile existing MCP/API contracts for '||b.display_name||' to exact enabled, closed-schema, provider-readback state without expanding authority.'
      else 'Discover and bind the exact read/API/MCP provider contract for '||b.display_name||' while preserving credential, write, billing, and D3 boundaries.' end;
    v_requirements:=jsonb_build_object(
      'contract','ct.penta.wire.gap-work.v1','service_id',b.service_id,'gap_state',b.gap_state,
      'display_name',b.display_name,'direct_tool_count',b.direct_tool_count,'enabled_tool_count',b.enabled_tool_count,
      'closed_input_tool_count',b.closed_input_tool_count,'integration_state',b.current_integration_state,
      'required_outputs',case when b.gap_state='tool_contract_drift' then jsonb_build_array(
        'exact_operation_inventory','closed_input_schemas','bounded_output_schemas','enabled_disabled_rationale',
        'provider_or_runtime_readback','mesh_binding','regression_tests','certification_receipt') else jsonb_build_array(
        'exact_provider_or_runtime_contract','authentication_class_without_secret_value','read_operation_inventory',
        'provider_limits_and_rate_controls','closed_mcp_schemas','credential_vault_reference_name_only',
        'provider_read_canary','mesh_binding','security_tests','certification_receipt') end,
      'prohibited',jsonb_build_array('credential_value_exposure','inferred_provider_write','delete','money_movement','checkout_activation','D3_auto','self_approval'),
      'provider_write',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true,
      'authority_ceiling','D2','release_only_after_exact_evidence',true,'source','PentaWire autonomous convergence'
    );

    insert into chlom_runtime.construction_work_queue(
      work_id,workstream,canonical_name,scope_type,scope_id,priority,owner_agent_id,verifier_agent_id,
      depends_on,closes_gates,required_outputs,state,blocker_reason,evidence
    ) values(
      v_work_id,'PentaWire API/MCP convergence',v_objective,'platform',b.service_id,v_priority,
      'ct.agent.penta-wire','ct.agent.factory.api-mcp-packaging','{}'::text[],array['api_mcp_mesh_convergence'],
      v_requirements,'ready',null,
      jsonb_build_object('penta_wire',true,'service_id',b.service_id,'gap_state',b.gap_state,'mesh_api_url',b.mesh_api_url,
        'provider_write',false,'authority_effect','none','d3_human_reserved',true,'created_from_scan',true)
    ) on conflict(work_id) do update set
      priority=excluded.priority,required_outputs=excluded.required_outputs,evidence=chlom_runtime.construction_work_queue.evidence||excluded.evidence,
      state=case when chlom_runtime.construction_work_queue.state='done' then 'done' else 'ready' end,
      blocker_reason=null,updated_at=now();
    v_reconciled_work:=v_reconciled_work+1;

    select status into v_existing_state from public.ct_factory_build_requests where request_key=v_request_key;
    insert into public.ct_factory_build_requests(
      project_id,request_key,source_type,source_ref,objective,requirements,requested_release_channel,priority,status,governance_class,evidence
    ) select p.id,v_request_key,'penta_wire_gap',b.service_id,v_objective,v_requirements,'production',v_priority,'queued','D2',
      jsonb_build_object('agent_id','ct.agent.penta-wire','founder_directive',true,'auto_generated',true,
        'exact_evidence_required',true,'provider_write_preapproved',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true)
    from public.ct_factory_projects p where p.project_key='crownthrive-os-v2-factory'
    on conflict(request_key) do update set
      objective=excluded.objective,requirements=excluded.requirements,priority=least(public.ct_factory_build_requests.priority,excluded.priority),
      status=case when public.ct_factory_build_requests.status in ('claimed','building','validating','approved','implemented') then public.ct_factory_build_requests.status else 'queued' end,
      evidence=public.ct_factory_build_requests.evidence||excluded.evidence,updated_at=now();
    if v_existing_state is null then v_created_requests:=v_created_requests+1; end if;
  end loop;

  return jsonb_build_object(
    'contract','ct.penta.wire.gap-factory-generation.v1',
    'eligible_gaps',(select count(*) from integration_control.penta_wire_service_bindings_v1 where gap_state in ('tool_contract_drift','exact_provider_contract_required')),
    'work_items_reconciled',v_reconciled_work,'new_factory_requests',v_created_requests,
    'queued_factory_requests',(select count(*) from public.ct_factory_build_requests where request_key like 'penta-wire:%' and status='queued'),
    'provider_write',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true,'authority_effect','none','at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.penta_wire_generate_gap_work_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.penta_wire_generate_gap_work_v1(integer) to service_role;

create or replace function public.ct_factory_internal_generate_tick_v1(p_limit integer default 2)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control'
as $function$
declare
  r record;
  v_result jsonb;
  v_results jsonb:='[]'::jsonb;
  v_processed integer:=0;
  v_passed integer:=0;
  v_held integer:=0;
  v_limit integer:=greatest(1,least(coalesce(p_limit,2),4));
begin
  if session_user <> 'postgres' and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-factory:internal-generate:v2',0)) then
    return jsonb_build_object('ok',true,'state','skipped_concurrent_run','processed',0);
  end if;

  for r in
    select w.id
    from public.ct_factory_work_units w
    join public.ct_factory_build_runs br on br.id=w.build_run_id
    join public.ct_factory_build_requests rq on rq.id=br.build_request_id
    join public.ct_factory_projects p on p.id=rq.project_id
    where w.lane='generate' and w.status='ready' and p.autonomy_enabled
      and (w.lease_until is null or w.lease_until<clock_timestamp())
      and rq.source_type='penta_certify'
      and coalesce(rq.requirements->>'work_type','')='provider_certification_software'
      and jsonb_typeof(rq.requirements->'compiler_spec')='object'
    order by rq.priority,rq.created_at,w.ordinal
    for update of w skip locked
    limit v_limit
  loop
    update public.ct_factory_work_units
    set status='running',attempts=attempts+1,
        started_at=coalesce(started_at,clock_timestamp()),
        lease_until=clock_timestamp()+interval '3 minutes'
    where id=r.id;

    begin
      v_result:=integration_control.penta_factory_compile_certification_spec_v2(r.id);
    exception when others then
      v_result:=jsonb_build_object(
        'ok',false,'work_unit_id',r.id,'reason','deterministic_compiler_exception',
        'error_class',sqlstate,
        'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),
        'automatic_retry',false,'candidate_only',true,'authority_created',false,'provider_write_performed',false
      );
      perform public.ct_factory_complete_work(r.id,'hold',v_result);
    end;

    v_processed:=v_processed+1;
    v_results:=v_results||jsonb_build_array(v_result);
    if coalesce((v_result->>'ok')::boolean,false) then v_passed:=v_passed+1; else v_held:=v_held+1; end if;
  end loop;

  if v_processed < v_limit then
    for r in
      select w.id
      from public.ct_factory_work_units w
      join public.ct_factory_build_runs br on br.id=w.build_run_id
      join public.ct_factory_build_requests rq on rq.id=br.build_request_id
      join public.ct_factory_projects p on p.id=rq.project_id
      where w.lane='generate' and w.status='ready' and p.autonomy_enabled
        and (w.lease_until is null or w.lease_until<clock_timestamp())
        and not (
          rq.source_type='penta_certify'
          and coalesce(rq.requirements->>'work_type','')='provider_certification_software'
          and jsonb_typeof(rq.requirements->'compiler_spec')='object'
        )
      order by rq.priority,rq.created_at,w.ordinal
      for update of w skip locked
      limit (v_limit-v_processed)
    loop
      update public.ct_factory_work_units
      set status='running',attempts=attempts+1,
          started_at=coalesce(started_at,clock_timestamp()),
          lease_until=clock_timestamp()+interval '3 minutes'
      where id=r.id;

      begin
        v_result:=integration_control.penta_factory_openai_generate_v2(r.id);
      exception when others then
        v_result:=jsonb_build_object(
          'ok',false,'work_unit_id',r.id,'reason','unhandled_exception',
          'error_class',sqlstate,
          'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),
          'automatic_retry',false
        );
        perform public.ct_factory_complete_work(
          r.id,'hold',v_result||jsonb_build_object(
            'generator_contract','ct.penta.factory.openai-generation.v2',
            'candidate_only',true,'automatic_retry',false
          )
        );
      end;

      v_processed:=v_processed+1;
      v_results:=v_results||jsonb_build_array(v_result);
      if coalesce((v_result->>'ok')::boolean,false) then v_passed:=v_passed+1; else v_held:=v_held+1; end if;
    end loop;
  end if;

  return jsonb_build_object(
    'ok',v_held=0,'processed',v_processed,'passed',v_passed,
    'held',v_held,'results',v_results,'observed_at',clock_timestamp(),
    'deterministic_certification_compiler_enabled',true,
    'materialization_contract','ct.penta.factory.certification-artifacts.v2'
  );
end;
$function$;

revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from public,anon,authenticated;
grant execute on function public.ct_factory_internal_generate_tick_v1(integer) to service_role;

drop function if exists integration_control.penta_factory_wire_generate_v1(uuid);
drop function if exists integration_control.penta_factory_wire_materialize_v1(uuid,jsonb);
