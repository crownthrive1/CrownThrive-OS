-- PentaWire/PentaFactory exact-provider candidate materialization hardening v1
-- Scope: internal D2 runtime only; no provider write, credential value, money movement, rights grant or D3 authority.

create or replace function integration_control.penta_factory_wire_materialize_v1(
  p_work_unit_id uuid,
  p_generation jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','integration_control','public','extensions'
as $function$
declare
  w public.ct_factory_work_units%rowtype;
  br public.ct_factory_build_runs%rowtype;
  rq public.ct_factory_build_requests%rowtype;
  v_candidate jsonb;
  v_service_contract jsonb;
  v_source_ok boolean := false;
  v_evidence_verified boolean := false;
  v_unresolved_count integer := 999;
  v_release_ready boolean := false;
  v_content text;
  v_source_sha text;
  v_source_bytes integer;
  v_compiler jsonb;
  v_compiler_sha text;
  v_manifest jsonb;
  v_manifest_sha text;
  v_asset_base text;
  v_secret_pattern_hit boolean := false;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into w from public.ct_factory_work_units where id=p_work_unit_id for update;
  if not found then raise exception 'factory_work_unit_not_found'; end if;
  if w.lane <> 'generate' then raise exception 'generate_lane_required'; end if;

  select * into br from public.ct_factory_build_runs where id=w.build_run_id;
  select * into rq from public.ct_factory_build_requests where id=br.build_request_id;
  if rq.source_type <> 'penta_wire_gap' then raise exception 'penta_wire_gap_request_required'; end if;

  v_candidate := coalesce(p_generation->'output', w.output, '{}'::jsonb);
  v_service_contract := rq.requirements->'service_contract';

  v_source_ok :=
    jsonb_typeof(v_service_contract)='object'
    and coalesce(rq.requirements->>'source_semantics_authority','')='integration_control.services.current_runtime'
    and coalesce((rq.requirements->>'do_not_infer_authentication_beyond_source')::boolean,false)
    and coalesce((rq.requirements->>'do_not_infer_vault_reference_names')::boolean,false)
    and coalesce(v_service_contract->>'service_id','')=coalesce(rq.source_ref,'')
    and nullif(v_service_contract->>'base_url','') is not null
    and nullif(v_service_contract->>'auth_scheme','') is not null;

  if jsonb_typeof(v_candidate->'unresolved_dependencies')='array' then
    v_unresolved_count := jsonb_array_length(v_candidate->'unresolved_dependencies');
  end if;

  v_evidence_verified := coalesce(rq.requirements->>'exact_provider_evidence_state','')='verified';
  v_release_ready := v_source_ok and v_evidence_verified and v_unresolved_count=0;

  v_content := jsonb_pretty(jsonb_build_object(
    'contract','ct.penta.factory.wire-candidate-source.v1',
    'service_id',rq.source_ref,
    'source_semantics_authority',rq.requirements->>'source_semantics_authority',
    'service_contract',v_service_contract,
    'candidate',v_candidate,
    'candidate_only',true,
    'exact_provider_evidence_state',coalesce(rq.requirements->>'exact_provider_evidence_state','unverified'),
    'release_ready',v_release_ready,
    'provider_write',false,
    'money_movement',false,
    'checkout_activation',false,
    'd3_human_reserved',true,
    'authority_created',false
  ));

  v_secret_pattern_hit := v_content ~* '(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY)';
  if v_secret_pattern_hit then
    return jsonb_build_object(
      'ok',false,'state','hold','reason','candidate_secret_pattern_detected',
      'work_unit_id',p_work_unit_id,'service_id',rq.source_ref,
      'candidate_only',true,'source_semantics_present',v_source_ok,
      'release_ready',false,'provider_write',false,'authority_created',false
    );
  end if;

  v_asset_base := regexp_replace(lower(coalesce(rq.source_ref,'service')),'[^a-z0-9._-]+','-','g');
  v_source_sha := encode(extensions.digest(convert_to(v_content,'UTF8'),'sha256'),'hex');
  v_source_bytes := octet_length(convert_to(v_content,'UTF8'));

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    w.build_run_id,'source_file',v_asset_base||'-exact-provider-candidate.json',
    'thrivebase://factory/'||w.build_run_id::text||'/penta-wire/'||v_asset_base||'/candidate-source',
    v_source_sha,
    jsonb_build_object(
      'kind','json_document',
      'path','generated/penta-wire/'||v_asset_base||'.candidate.json',
      'content',v_content,
      'bytes',v_source_bytes,
      'candidate_only',true,
      'source_semantics_authority',rq.requirements->>'source_semantics_authority',
      'service_id',rq.source_ref,
      'release_ready',v_release_ready,
      'provider_write',false,
      'authority_created',false
    )
  )
  on conflict(build_run_id,artifact_type,asset_key) do update
  set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  v_compiler := jsonb_build_object(
    'contract','ct.compiler.v5.penta-wire-candidate.v1',
    'compiler','integration_control.penta_factory_wire_materialize_v1',
    'work_unit_id',p_work_unit_id,
    'build_run_id',w.build_run_id,
    'service_id',rq.source_ref,
    'source_file_count',1,
    'source_semantics_present',v_source_ok,
    'unresolved_dependency_count',v_unresolved_count,
    'exact_provider_evidence_state',coalesce(rq.requirements->>'exact_provider_evidence_state','unverified'),
    'release_ready',v_release_ready,
    'candidate_only',true,
    'provider_write',false,
    'authority_created',false,
    'observed_at',clock_timestamp()
  );
  v_compiler_sha := encode(extensions.digest(convert_to(v_compiler::text,'UTF8'),'sha256'),'hex');

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    w.build_run_id,'compiler_report',v_asset_base||'-penta-wire-compiler-report.json',
    'thrivebase://factory/'||w.build_run_id::text||'/penta-wire/'||v_asset_base||'/compiler-report',
    v_compiler_sha,v_compiler
  )
  on conflict(build_run_id,artifact_type,asset_key) do update
  set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  v_manifest := jsonb_build_object(
    'contract','ct.penta.factory.wire-candidate-manifest.v1',
    'work_unit_id',p_work_unit_id,
    'build_run_id',w.build_run_id,
    'service_id',rq.source_ref,
    'source_sha256',v_source_sha,
    'compiler_sha256',v_compiler_sha,
    'source_semantics_present',v_source_ok,
    'unresolved_dependency_count',v_unresolved_count,
    'exact_provider_evidence_state',coalesce(rq.requirements->>'exact_provider_evidence_state','unverified'),
    'release_ready',v_release_ready,
    'hold_reason',case
      when not v_source_ok then 'authoritative_source_semantics_missing'
      when not v_evidence_verified then 'exact_provider_evidence_unverified'
      when v_unresolved_count<>0 then 'candidate_unresolved_dependencies'
      else null end,
    'candidate_only',true,
    'provider_write',false,
    'money_movement',false,
    'checkout_activation',false,
    'd3_human_reserved',true,
    'authority_created',false,
    'observed_at',clock_timestamp()
  );
  v_manifest_sha := encode(extensions.digest(convert_to(v_manifest::text,'UTF8'),'sha256'),'hex');

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    w.build_run_id,'generated_manifest',v_asset_base||'-penta-wire-generated-manifest.json',
    'thrivebase://factory/'||w.build_run_id::text||'/penta-wire/'||v_asset_base||'/generated-manifest',
    v_manifest_sha,v_manifest
  )
  on conflict(build_run_id,artifact_type,asset_key) do update
  set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  return jsonb_build_object(
    'ok',true,
    'state',case when v_release_ready then 'materialized_verified_candidate' else 'materialized_hold' end,
    'work_unit_id',p_work_unit_id,
    'build_run_id',w.build_run_id,
    'service_id',rq.source_ref,
    'source_sha256',v_source_sha,
    'compiler_sha256',v_compiler_sha,
    'manifest_sha256',v_manifest_sha,
    'source_semantics_present',v_source_ok,
    'unresolved_dependency_count',v_unresolved_count,
    'exact_provider_evidence_state',coalesce(rq.requirements->>'exact_provider_evidence_state','unverified'),
    'release_ready',v_release_ready,
    'candidate_only',true,
    'provider_write',false,
    'money_movement',false,
    'checkout_activation',false,
    'd3_human_reserved',true,
    'authority_created',false
  );
end
$function$;

revoke all on function integration_control.penta_factory_wire_materialize_v1(uuid,jsonb) from public,anon,authenticated;
grant execute on function integration_control.penta_factory_wire_materialize_v1(uuid,jsonb) to service_role;

create or replace function integration_control.penta_factory_wire_generate_v1(p_work_unit_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','integration_control','public'
as $function$
declare
  w public.ct_factory_work_units%rowtype;
  br public.ct_factory_build_runs%rowtype;
  rq public.ct_factory_build_requests%rowtype;
  v_generation jsonb;
  v_materialization jsonb;
  v_reconcile jsonb;
  v_hold_reason text;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into w from public.ct_factory_work_units where id=p_work_unit_id for update;
  if not found then raise exception 'factory_work_unit_not_found'; end if;
  select * into br from public.ct_factory_build_runs where id=w.build_run_id;
  select * into rq from public.ct_factory_build_requests where id=br.build_request_id;
  if rq.source_type <> 'penta_wire_gap' then raise exception 'penta_wire_gap_request_required'; end if;

  v_generation := integration_control.penta_factory_openai_generate_v2(p_work_unit_id);
  if coalesce((v_generation->>'ok')::boolean,false) is not true then
    return v_generation;
  end if;

  v_materialization := integration_control.penta_factory_wire_materialize_v1(p_work_unit_id,v_generation);

  if coalesce((v_materialization->>'ok')::boolean,false) is not true
     or coalesce((v_materialization->>'release_ready')::boolean,false) is not true then
    v_hold_reason := coalesce(v_materialization->>'reason',
      case
        when coalesce((v_materialization->>'source_semantics_present')::boolean,false) is not true
          then 'authoritative_source_semantics_missing'
        when coalesce(v_materialization->>'exact_provider_evidence_state','') <> 'verified'
          then 'exact_provider_evidence_unverified'
        else 'candidate_unresolved_dependencies'
      end
    );

    update public.ct_factory_work_units
    set status='hold',
        output=coalesce(output,'{}'::jsonb)||jsonb_build_object(
          'factory_materialization_contract','ct.penta.factory.wire-candidate-materialization.v1',
          'materialization',v_materialization,
          'release_gate_state','hold_exact_provider_evidence',
          'hold_reason',v_hold_reason,
          'candidate_only',true,
          'provider_write',false,
          'authority_created',false
        ),
        completed_at=clock_timestamp(),
        lease_until=null
    where id=p_work_unit_id;

    update public.ct_factory_work_units
    set status='queued',started_at=null,completed_at=null,lease_until=null,
        output=case when status in ('ready','running') then '{}'::jsonb else output end
    where build_run_id=w.build_run_id
      and ordinal>w.ordinal
      and status in ('ready','running');

    insert into public.ct_factory_events(event_type,entity_type,entity_id,payload)
    values(
      'factory.work.semantic_hold','work_unit',p_work_unit_id,
      jsonb_build_object(
        'contract','ct.penta.factory.wire-semantic-hold.v1',
        'service_id',rq.source_ref,
        'reason',v_hold_reason,
        'materialization',v_materialization,
        'supersedes_candidate_generation_pass',true,
        'candidate_only',true,
        'provider_write',false,
        'money_movement',false,
        'authority_created',false
      )
    );

    begin
      v_reconcile:=public.ct_factory_reconcile_run(w.build_run_id);
    exception when others then
      v_reconcile:=jsonb_build_object(
        'state','DEFERRED_RECONCILIATION',
        'error_class',sqlstate,
        'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),
        'retry_owner','PentaFactory/PentaTime'
      );
    end;

    return jsonb_build_object(
      'ok',false,'state','hold','reason',v_hold_reason,
      'work_unit_id',p_work_unit_id,'build_run_id',w.build_run_id,'service_id',rq.source_ref,
      'generation_candidate_created',true,'materialization',v_materialization,
      'reconcile',v_reconcile,
      'candidate_only',true,'automatic_retry',false,
      'provider_write',false,'money_movement',false,'checkout_activation',false,
      'd3_human_reserved',true,'authority_created',false
    );
  end if;

  return v_generation||jsonb_build_object(
    'wire_materialization',v_materialization,
    'wire_exact_provider_evidence_verified',true
  );
end
$function$;

revoke all on function integration_control.penta_factory_wire_generate_v1(uuid) from public,anon,authenticated;
grant execute on function integration_control.penta_factory_wire_generate_v1(uuid) to service_role;

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
  v_safe_metadata jsonb;
begin
  p_limit:=greatest(1,least(coalesce(p_limit,100),200));
  for b in
    select w.*,s.display_name,s.base_url,s.auth_scheme,s.credential_state,s.write_gate,s.metadata as service_metadata
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

    v_safe_metadata:=jsonb_strip_nulls(jsonb_build_object(
      'provider',b.service_metadata->'provider',
      'identifier_class',b.service_metadata->'identifier_class',
      'client_projection_allowed',b.service_metadata->'client_projection_allowed',
      'approved_surface',b.service_metadata->'approved_surface',
      'runtime_env_alias',b.service_metadata->'runtime_env_alias',
      'credential_broker',b.service_metadata->'credential_broker',
      'provider_restrictions_required',b.service_metadata->'provider_restrictions_required',
      'recommended_api_restriction',b.service_metadata->'recommended_api_restriction',
      'recommended_application_restriction',b.service_metadata->'recommended_application_restriction',
      'app_id_client_projection_allowed',b.service_metadata->'app_id_client_projection_allowed',
      'app_secret_client_projection_allowed',b.service_metadata->'app_secret_client_projection_allowed',
      'facebook_login_enabled',b.service_metadata->'facebook_login_enabled',
      'attribution_required',b.service_metadata->'attribution_required',
      'hotlink_required',b.service_metadata->'hotlink_required',
      'download_tracking_required',b.service_metadata->'download_tracking_required',
      'ai_training_allowed',b.service_metadata->'ai_training_allowed',
      'generic_scraping_allowed',b.service_metadata->'generic_scraping_allowed',
      'demo_hourly_limit',b.service_metadata->'demo_hourly_limit',
      'production_target_hourly_limit',b.service_metadata->'production_target_hourly_limit',
      'provider_throttles_still_apply',b.service_metadata->'provider_throttles_still_apply',
      'request_budget_policy_mode',b.service_metadata->'request_budget_policy_mode',
      'provider_limits_billing_quotas_separate',b.service_metadata->'provider_limits_billing_quotas_separate'
    ));

    v_requirements:=jsonb_build_object(
      'contract','ct.penta.wire.gap-work.v2',
      'work_type','penta_wire_exact_contract',
      'service_id',b.service_id,
      'gap_state',b.gap_state,
      'display_name',b.display_name,
      'direct_tool_count',b.direct_tool_count,
      'enabled_tool_count',b.enabled_tool_count,
      'closed_input_tool_count',b.closed_input_tool_count,
      'integration_state',b.current_integration_state,
      'source_semantics_authority','integration_control.services.current_runtime',
      'service_contract',jsonb_build_object(
        'service_id',b.service_id,
        'display_name',b.display_name,
        'base_url',b.base_url,
        'auth_scheme',b.auth_scheme,
        'credential_state',b.credential_state,
        'integration_state',b.current_integration_state,
        'write_gate',coalesce(b.write_gate,false),
        'safe_metadata',v_safe_metadata
      ),
      'do_not_infer_authentication_beyond_source',true,
      'do_not_infer_vault_reference_names',true,
      'model_candidate_is_not_evidence',true,
      'exact_provider_evidence_state','unverified',
      'required_outputs',case when b.gap_state='tool_contract_drift' then jsonb_build_array(
        'exact_operation_inventory','closed_input_schemas','bounded_output_schemas','enabled_disabled_rationale',
        'provider_or_runtime_readback','mesh_binding','regression_tests','certification_receipt') else jsonb_build_array(
        'exact_provider_or_runtime_contract','authentication_class_without_secret_value','read_operation_inventory',
        'provider_limits_and_rate_controls','closed_mcp_schemas','credential_vault_reference_name_only',
        'provider_read_canary','mesh_binding','security_tests','certification_receipt') end,
      'prohibited',jsonb_build_array(
        'credential_value_exposure','authentication_inference_beyond_authoritative_source','invented_vault_reference',
        'inferred_provider_write','delete','money_movement','checkout_activation','D3_auto','self_approval'),
      'provider_write',false,
      'money_movement',false,
      'checkout_activation',false,
      'd3_human_reserved',true,
      'authority_ceiling','D2',
      'release_only_after_exact_evidence',true,
      'source','PentaWire autonomous convergence'
    );

    insert into chlom_runtime.construction_work_queue(
      work_id,workstream,canonical_name,scope_type,scope_id,priority,owner_agent_id,verifier_agent_id,
      depends_on,closes_gates,required_outputs,state,blocker_reason,evidence
    ) values(
      v_work_id,'PentaWire API/MCP convergence',v_objective,'platform',b.service_id,v_priority,
      'ct.agent.penta-wire','ct.agent.factory.api-mcp-packaging','{}'::text[],array['api_mcp_mesh_convergence'],
      v_requirements,'ready',null,
      jsonb_build_object(
        'penta_wire',true,'service_id',b.service_id,'gap_state',b.gap_state,'mesh_api_url',b.mesh_api_url,
        'source_semantics_authority','integration_control.services.current_runtime',
        'provider_write',false,'authority_effect','none','d3_human_reserved',true,'created_from_scan',true)
    ) on conflict(work_id) do update set
      priority=excluded.priority,
      required_outputs=excluded.required_outputs,
      evidence=chlom_runtime.construction_work_queue.evidence||excluded.evidence,
      state=case when chlom_runtime.construction_work_queue.state='done' then 'done' else 'ready' end,
      blocker_reason=null,
      updated_at=now();
    v_reconciled_work:=v_reconciled_work+1;

    select status into v_existing_state from public.ct_factory_build_requests where request_key=v_request_key;
    insert into public.ct_factory_build_requests(
      project_id,request_key,source_type,source_ref,objective,requirements,requested_release_channel,priority,status,governance_class,evidence
    ) select p.id,v_request_key,'penta_wire_gap',b.service_id,v_objective,v_requirements,'production',v_priority,'queued','D2',
      jsonb_build_object(
        'agent_id','ct.agent.penta-wire','founder_directive',true,'auto_generated',true,
        'exact_evidence_required',true,'source_semantics_authority','integration_control.services.current_runtime',
        'provider_write_preapproved',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true)
    from public.ct_factory_projects p where p.project_key='crownthrive-os-v2-factory'
    on conflict(request_key) do update set
      objective=excluded.objective,
      requirements=excluded.requirements,
      priority=least(public.ct_factory_build_requests.priority,excluded.priority),
      status=case when public.ct_factory_build_requests.status in ('claimed','building','validating','approved','implemented')
        then public.ct_factory_build_requests.status else 'queued' end,
      evidence=public.ct_factory_build_requests.evidence||excluded.evidence,
      updated_at=now();
    if v_existing_state is null then v_created_requests:=v_created_requests+1; end if;
  end loop;

  return jsonb_build_object(
    'contract','ct.penta.wire.gap-factory-generation.v2',
    'eligible_gaps',(select count(*) from integration_control.penta_wire_service_bindings_v1
      where gap_state in ('tool_contract_drift','exact_provider_contract_required')),
    'work_items_reconciled',v_reconciled_work,
    'new_factory_requests',v_created_requests,
    'queued_factory_requests',(select count(*) from public.ct_factory_build_requests
      where request_key like 'penta-wire:%' and status='queued'),
    'source_semantics_authority','integration_control.services.current_runtime',
    'provider_write',false,'money_movement',false,'checkout_activation',false,
    'd3_human_reserved',true,'authority_effect','none','at',clock_timestamp()
  );
end
$function$;

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
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta-factory:internal-generate:v3',0)) then
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
      select w.id,rq.source_type
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
        if r.source_type='penta_wire_gap' then
          v_result:=integration_control.penta_factory_wire_generate_v1(r.id);
        else
          v_result:=integration_control.penta_factory_openai_generate_v2(r.id);
        end if;
      exception when others then
        v_result:=jsonb_build_object(
          'ok',false,'work_unit_id',r.id,'reason','unhandled_exception',
          'error_class',sqlstate,
          'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),
          'automatic_retry',false
        );
        perform public.ct_factory_complete_work(
          r.id,'hold',v_result||jsonb_build_object(
            'generator_contract',case when r.source_type='penta_wire_gap'
              then 'ct.penta.factory.wire-generation.v1'
              else 'ct.penta.factory.openai-generation.v2' end,
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
    'penta_wire_exact_contract_materialization_enabled',true,
    'materialization_contract','ct.penta.factory.certification-artifacts.v2+ct.penta.factory.wire-candidate-materialization.v1'
  );
end;
$function$;

revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from public,anon,authenticated;
grant execute on function public.ct_factory_internal_generate_tick_v1(integer) to service_role;

comment on function integration_control.penta_factory_wire_materialize_v1(uuid,jsonb) is
'Materializes PentaWire exact-provider model candidates into deterministic factory artifacts using current runtime service semantics; never certifies or releases unverified provider evidence.';
comment on function integration_control.penta_factory_wire_generate_v1(uuid) is
'PentaWire-specific factory generator wrapper. Candidate generation may succeed, but the lane is forced to HOLD until authoritative source semantics, exact provider evidence, and zero unresolved dependencies are all proven.';
comment on function integration_control.penta_wire_generate_gap_work_v1(integer) is
'Generates PentaWire gap work with safe authoritative runtime service semantics and explicit no-inference boundaries.';
