-- Bind PentaWire factory materialization to fresh runtime service semantics and independent exact-contract certification.
-- No provider write, credential value, money movement, rights grant, or D3 authority.

create or replace function integration_control.penta_wire_safe_service_contract_v1(p_service_id text)
returns jsonb
language plpgsql
stable
security definer
set search_path='pg_catalog','integration_control','extensions'
as $function$
declare
  s integration_control.services%rowtype;
  v_safe_metadata jsonb;
  v_payload jsonb;
  v_sha text;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into s from integration_control.services where service_id=p_service_id;
  if not found then raise exception 'service_not_found'; end if;

  v_safe_metadata:=jsonb_strip_nulls(jsonb_build_object(
    'provider',s.metadata->'provider',
    'identifier_class',s.metadata->'identifier_class',
    'client_projection_allowed',s.metadata->'client_projection_allowed',
    'approved_surface',s.metadata->'approved_surface',
    'runtime_env_alias',s.metadata->'runtime_env_alias',
    'credential_broker',s.metadata->'credential_broker',
    'provider_restrictions_required',s.metadata->'provider_restrictions_required',
    'recommended_api_restriction',s.metadata->'recommended_api_restriction',
    'recommended_application_restriction',s.metadata->'recommended_application_restriction',
    'app_id_client_projection_allowed',s.metadata->'app_id_client_projection_allowed',
    'app_secret_client_projection_allowed',s.metadata->'app_secret_client_projection_allowed',
    'facebook_login_enabled',s.metadata->'facebook_login_enabled',
    'attribution_required',s.metadata->'attribution_required',
    'hotlink_required',s.metadata->'hotlink_required',
    'download_tracking_required',s.metadata->'download_tracking_required',
    'ai_training_allowed',s.metadata->'ai_training_allowed',
    'generic_scraping_allowed',s.metadata->'generic_scraping_allowed',
    'demo_hourly_limit',s.metadata->'demo_hourly_limit',
    'production_target_hourly_limit',s.metadata->'production_target_hourly_limit',
    'provider_throttles_still_apply',s.metadata->'provider_throttles_still_apply',
    'request_budget_policy_mode',s.metadata->'request_budget_policy_mode',
    'provider_limits_billing_quotas_separate',s.metadata->'provider_limits_billing_quotas_separate'
  ));

  v_payload:=jsonb_build_object(
    'contract','ct.penta.wire.safe-service-contract.v1',
    'service_id',s.service_id,
    'display_name',s.display_name,
    'base_url',s.base_url,
    'auth_scheme',s.auth_scheme,
    'credential_state',s.credential_state,
    'integration_state',s.integration_state,
    'write_gate',coalesce(s.write_gate,false),
    'safe_metadata',v_safe_metadata
  );
  v_sha:=encode(extensions.digest(convert_to(v_payload::text,'UTF8'),'sha256'),'hex');
  return v_payload||jsonb_build_object('contract_sha256',v_sha);
end
$function$;

revoke all on function integration_control.penta_wire_safe_service_contract_v1(text) from public,anon,authenticated;
grant execute on function integration_control.penta_wire_safe_service_contract_v1(text) to service_role;

create or replace function integration_control.penta_factory_wire_materialize_v1(
  p_work_unit_id uuid,
  p_generation jsonb
)
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public','extensions'
as $function$
declare
  w public.ct_factory_work_units%rowtype;
  br public.ct_factory_build_runs%rowtype;
  rq public.ct_factory_build_requests%rowtype;
  v_candidate jsonb;
  v_request_contract jsonb;
  v_current_contract jsonb;
  v_source_ok boolean:=false;
  v_evidence_verified boolean:=false;
  v_cert_exact_contract text;
  v_cert_evidence_sha text;
  v_cert_expires_at timestamptz;
  v_unresolved_count integer:=999;
  v_release_ready boolean:=false;
  v_content text;
  v_source_sha text;
  v_source_bytes integer;
  v_compiler jsonb;
  v_compiler_sha text;
  v_manifest jsonb;
  v_manifest_sha text;
  v_asset_base text;
  v_secret_pattern_hit boolean:=false;
begin
  if session_user <> 'postgres'
     and coalesce(current_setting('request.jwt.claim.role',true),'') <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select * into w from public.ct_factory_work_units where id=p_work_unit_id for update;
  if not found then raise exception 'factory_work_unit_not_found'; end if;
  if w.lane<>'generate' then raise exception 'generate_lane_required'; end if;
  select * into br from public.ct_factory_build_runs where id=w.build_run_id;
  select * into rq from public.ct_factory_build_requests where id=br.build_request_id;
  if rq.source_type<>'penta_wire_gap' then raise exception 'penta_wire_gap_request_required'; end if;

  v_candidate:=coalesce(p_generation->'output',w.output,'{}'::jsonb);
  v_request_contract:=rq.requirements->'service_contract';
  v_current_contract:=integration_control.penta_wire_safe_service_contract_v1(rq.source_ref);

  v_source_ok:=
    jsonb_typeof(v_request_contract)='object'
    and coalesce(rq.requirements->>'source_semantics_authority','')='integration_control.services.current_runtime'
    and coalesce((rq.requirements->>'do_not_infer_authentication_beyond_source')::boolean,false)
    and coalesce((rq.requirements->>'do_not_infer_vault_reference_names')::boolean,false)
    and coalesce(v_request_contract->>'service_id','')=coalesce(rq.source_ref,'')
    and nullif(v_request_contract->>'contract_sha256','') is not null
    and v_request_contract->>'contract_sha256'=v_current_contract->>'contract_sha256';

  select c.exact_contract,c.evidence_sha256,c.expires_at
    into v_cert_exact_contract,v_cert_evidence_sha,v_cert_expires_at
  from integration_control.penta_wire_exact_contract_certifications_v2 c
  where c.service_id=rq.source_ref
    and c.decision='pass'
    and c.expires_at>clock_timestamp()
    and c.certified_by='penta.certify'
    and nullif(c.evidence_sha256,'') is not null
  order by c.certified_at desc
  limit 1;
  v_evidence_verified:=found;

  if jsonb_typeof(v_candidate->'unresolved_dependencies')='array' then
    v_unresolved_count:=jsonb_array_length(v_candidate->'unresolved_dependencies');
  end if;
  v_release_ready:=v_source_ok and v_evidence_verified and v_unresolved_count=0;

  v_content:=jsonb_pretty(jsonb_build_object(
    'contract','ct.penta.factory.wire-candidate-source.v1',
    'service_id',rq.source_ref,
    'source_semantics_authority',rq.requirements->>'source_semantics_authority',
    'service_contract',v_request_contract,
    'current_service_contract_sha256',v_current_contract->>'contract_sha256',
    'candidate',v_candidate,
    'candidate_only',true,
    'exact_provider_evidence_state',case when v_evidence_verified then 'verified' else 'unverified' end,
    'exact_provider_certification_source','integration_control.penta_wire_exact_contract_certifications_v2',
    'exact_provider_contract',v_cert_exact_contract,
    'exact_provider_evidence_sha256',v_cert_evidence_sha,
    'exact_provider_evidence_expires_at',v_cert_expires_at,
    'release_ready',v_release_ready,
    'provider_write',false,'money_movement',false,'checkout_activation',false,
    'd3_human_reserved',true,'authority_created',false
  ));

  v_secret_pattern_hit:=v_content ~* '(sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY)';
  if v_secret_pattern_hit then
    return jsonb_build_object(
      'ok',false,'state','hold','reason','candidate_secret_pattern_detected',
      'work_unit_id',p_work_unit_id,'service_id',rq.source_ref,
      'candidate_only',true,'source_semantics_present',v_source_ok,
      'release_ready',false,'provider_write',false,'authority_created',false
    );
  end if;

  v_asset_base:=regexp_replace(lower(coalesce(rq.source_ref,'service')),'[^a-z0-9._-]+','-','g');
  v_source_sha:=encode(extensions.digest(convert_to(v_content,'UTF8'),'sha256'),'hex');
  v_source_bytes:=octet_length(convert_to(v_content,'UTF8'));

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    w.build_run_id,'source_file',v_asset_base||'-exact-provider-candidate.json',
    'thrivebase://factory/'||w.build_run_id::text||'/penta-wire/'||v_asset_base||'/candidate-source',v_source_sha,
    jsonb_build_object(
      'kind','json_document','path','generated/penta-wire/'||v_asset_base||'.candidate.json',
      'content',v_content,'bytes',v_source_bytes,'candidate_only',true,
      'source_semantics_authority',rq.requirements->>'source_semantics_authority',
      'source_semantics_current',v_source_ok,'service_id',rq.source_ref,
      'release_ready',v_release_ready,'provider_write',false,'authority_created',false
    )
  ) on conflict(build_run_id,artifact_type,asset_key) do update
  set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  v_compiler:=jsonb_build_object(
    'contract','ct.compiler.v5.penta-wire-candidate.v1',
    'compiler','integration_control.penta_factory_wire_materialize_v1',
    'work_unit_id',p_work_unit_id,'build_run_id',w.build_run_id,'service_id',rq.source_ref,
    'source_file_count',1,'source_semantics_present',v_source_ok,
    'source_semantics_sha256',v_current_contract->>'contract_sha256',
    'unresolved_dependency_count',v_unresolved_count,
    'exact_provider_evidence_state',case when v_evidence_verified then 'verified' else 'unverified' end,
    'exact_provider_evidence_sha256',v_cert_evidence_sha,
    'release_ready',v_release_ready,'candidate_only',true,'provider_write',false,'authority_created',false,
    'observed_at',clock_timestamp()
  );
  v_compiler_sha:=encode(extensions.digest(convert_to(v_compiler::text,'UTF8'),'sha256'),'hex');

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    w.build_run_id,'compiler_report',v_asset_base||'-penta-wire-compiler-report.json',
    'thrivebase://factory/'||w.build_run_id::text||'/penta-wire/'||v_asset_base||'/compiler-report',v_compiler_sha,v_compiler
  ) on conflict(build_run_id,artifact_type,asset_key) do update
  set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  v_manifest:=jsonb_build_object(
    'contract','ct.penta.factory.wire-candidate-manifest.v1',
    'work_unit_id',p_work_unit_id,'build_run_id',w.build_run_id,'service_id',rq.source_ref,
    'source_sha256',v_source_sha,'compiler_sha256',v_compiler_sha,
    'source_semantics_present',v_source_ok,'source_semantics_sha256',v_current_contract->>'contract_sha256',
    'unresolved_dependency_count',v_unresolved_count,
    'exact_provider_evidence_state',case when v_evidence_verified then 'verified' else 'unverified' end,
    'exact_provider_evidence_sha256',v_cert_evidence_sha,
    'release_ready',v_release_ready,
    'hold_reason',case
      when not v_source_ok then 'authoritative_source_semantics_missing_or_stale'
      when not v_evidence_verified then 'independent_exact_provider_evidence_unverified'
      when v_unresolved_count<>0 then 'candidate_unresolved_dependencies'
      else null end,
    'candidate_only',true,'provider_write',false,'money_movement',false,'checkout_activation',false,
    'd3_human_reserved',true,'authority_created',false,'observed_at',clock_timestamp()
  );
  v_manifest_sha:=encode(extensions.digest(convert_to(v_manifest::text,'UTF8'),'sha256'),'hex');

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    w.build_run_id,'generated_manifest',v_asset_base||'-penta-wire-generated-manifest.json',
    'thrivebase://factory/'||w.build_run_id::text||'/penta-wire/'||v_asset_base||'/generated-manifest',v_manifest_sha,v_manifest
  ) on conflict(build_run_id,artifact_type,asset_key) do update
  set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  return jsonb_build_object(
    'ok',true,'state',case when v_release_ready then 'materialized_verified_candidate' else 'materialized_hold' end,
    'work_unit_id',p_work_unit_id,'build_run_id',w.build_run_id,'service_id',rq.source_ref,
    'source_sha256',v_source_sha,'compiler_sha256',v_compiler_sha,'manifest_sha256',v_manifest_sha,
    'source_semantics_present',v_source_ok,'source_semantics_sha256',v_current_contract->>'contract_sha256',
    'unresolved_dependency_count',v_unresolved_count,
    'exact_provider_evidence_state',case when v_evidence_verified then 'verified' else 'unverified' end,
    'exact_provider_evidence_sha256',v_cert_evidence_sha,'release_ready',v_release_ready,
    'candidate_only',true,'provider_write',false,'money_movement',false,'checkout_activation',false,
    'd3_human_reserved',true,'authority_created',false
  );
end
$function$;

revoke all on function integration_control.penta_factory_wire_materialize_v1(uuid,jsonb) from public,anon,authenticated;
grant execute on function integration_control.penta_factory_wire_materialize_v1(uuid,jsonb) to service_role;

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
  v_service_contract jsonb;
  v_evidence_verified boolean;
begin
  p_limit:=greatest(1,least(coalesce(p_limit,100),200));
  for b in
    select w.*,s.display_name
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

    v_service_contract:=integration_control.penta_wire_safe_service_contract_v1(b.service_id);
    select exists(
      select 1 from integration_control.penta_wire_exact_contract_certifications_v2 c
      where c.service_id=b.service_id and c.decision='pass' and c.expires_at>clock_timestamp()
        and c.certified_by='penta.certify' and nullif(c.evidence_sha256,'') is not null
    ) into v_evidence_verified;

    v_requirements:=jsonb_build_object(
      'contract','ct.penta.wire.gap-work.v3','work_type','penta_wire_exact_contract',
      'service_id',b.service_id,'gap_state',b.gap_state,'display_name',b.display_name,
      'direct_tool_count',b.direct_tool_count,'enabled_tool_count',b.enabled_tool_count,
      'closed_input_tool_count',b.closed_input_tool_count,'integration_state',b.current_integration_state,
      'source_semantics_authority','integration_control.services.current_runtime',
      'service_contract',v_service_contract,
      'do_not_infer_authentication_beyond_source',true,'do_not_infer_vault_reference_names',true,
      'model_candidate_is_not_evidence',true,
      'exact_provider_certification_source','integration_control.penta_wire_exact_contract_certifications_v2',
      'exact_provider_evidence_state',case when v_evidence_verified then 'verified' else 'unverified' end,
      'required_outputs',case when b.gap_state='tool_contract_drift' then jsonb_build_array(
        'exact_operation_inventory','closed_input_schemas','bounded_output_schemas','enabled_disabled_rationale',
        'provider_or_runtime_readback','mesh_binding','regression_tests','certification_receipt') else jsonb_build_array(
        'exact_provider_or_runtime_contract','authentication_class_without_secret_value','read_operation_inventory',
        'provider_limits_and_rate_controls','closed_mcp_schemas','credential_vault_reference_name_only',
        'provider_read_canary','mesh_binding','security_tests','certification_receipt') end,
      'prohibited',jsonb_build_array(
        'credential_value_exposure','authentication_inference_beyond_authoritative_source','invented_vault_reference',
        'inferred_provider_write','delete','money_movement','checkout_activation','D3_auto','self_approval'),
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
      jsonb_build_object(
        'penta_wire',true,'service_id',b.service_id,'gap_state',b.gap_state,'mesh_api_url',b.mesh_api_url,
        'source_semantics_authority','integration_control.services.current_runtime',
        'source_semantics_sha256',v_service_contract->>'contract_sha256',
        'provider_write',false,'authority_effect','none','d3_human_reserved',true,'created_from_scan',true)
    ) on conflict(work_id) do update set
      priority=excluded.priority,required_outputs=excluded.required_outputs,
      evidence=chlom_runtime.construction_work_queue.evidence||excluded.evidence,
      state=case when chlom_runtime.construction_work_queue.state='done' then 'done' else 'ready' end,
      blocker_reason=null,updated_at=now();
    v_reconciled_work:=v_reconciled_work+1;

    select status into v_existing_state from public.ct_factory_build_requests where request_key=v_request_key;
    insert into public.ct_factory_build_requests(
      project_id,request_key,source_type,source_ref,objective,requirements,requested_release_channel,priority,status,governance_class,evidence
    ) select p.id,v_request_key,'penta_wire_gap',b.service_id,v_objective,v_requirements,'production',v_priority,'queued','D2',
      jsonb_build_object(
        'agent_id','ct.agent.penta-wire','founder_directive',true,'auto_generated',true,
        'exact_evidence_required',true,'source_semantics_authority','integration_control.services.current_runtime',
        'source_semantics_sha256',v_service_contract->>'contract_sha256',
        'provider_write_preapproved',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true)
    from public.ct_factory_projects p where p.project_key='crownthrive-os-v2-factory'
    on conflict(request_key) do update set
      objective=excluded.objective,requirements=excluded.requirements,
      priority=least(public.ct_factory_build_requests.priority,excluded.priority),
      status=case when public.ct_factory_build_requests.status in ('claimed','building','validating','approved','implemented')
        then public.ct_factory_build_requests.status else 'queued' end,
      evidence=public.ct_factory_build_requests.evidence||excluded.evidence,updated_at=now();
    if v_existing_state is null then v_created_requests:=v_created_requests+1; end if;
  end loop;

  return jsonb_build_object(
    'contract','ct.penta.wire.gap-factory-generation.v3',
    'eligible_gaps',(select count(*) from integration_control.penta_wire_service_bindings_v1 where gap_state in ('tool_contract_drift','exact_provider_contract_required')),
    'work_items_reconciled',v_reconciled_work,'new_factory_requests',v_created_requests,
    'queued_factory_requests',(select count(*) from public.ct_factory_build_requests where request_key like 'penta-wire:%' and status='queued'),
    'source_semantics_authority','integration_control.services.current_runtime',
    'exact_provider_certification_source','integration_control.penta_wire_exact_contract_certifications_v2',
    'provider_write',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true,
    'authority_effect','none','at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.penta_wire_generate_gap_work_v1(integer) from public,anon,authenticated;
grant execute on function integration_control.penta_wire_generate_gap_work_v1(integer) to service_role;

comment on function integration_control.penta_wire_safe_service_contract_v1(text) is
'Returns the current whitelisted non-secret PentaWire service contract plus a deterministic digest for stale-source detection.';
comment on function integration_control.penta_factory_wire_materialize_v1(uuid,jsonb) is
'Materializes PentaWire model candidates only when bound to fresh runtime semantics; independent PentaCertify exact-contract evidence is authoritative for verification state.';
