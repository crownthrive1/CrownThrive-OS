-- PentaCertifier deterministic compiler executor v1.
-- Closes the generate-lane routing gap for provider-certification software
-- without invoking an AI/provider generator or creating production authority.

create or replace function integration_control.penta_factory_compile_certification_spec_v1(
  p_work_unit_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','extensions','public','integration_control'
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true),'');
  v_source_type text;
  v_work_type text;
  v_request_id uuid;
  v_request_key text;
  v_request_status text;
  v_run_id uuid;
  v_work_status text;
  v_spec jsonb;
  v_components jsonb;
  v_component_count integer := 0;
  v_unsupported integer := 0;
  v_missing_paths integer := 0;
  v_duplicate_paths integer := 0;
  v_secret_values integer := 0;
  v_files jsonb := '[]'::jsonb;
  v_manifest jsonb := '[]'::jsonb;
  v_spec_sha256 text;
  v_output jsonb;
  v_complete jsonb;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select rq.id, rq.request_key, rq.status, rq.source_type,
         coalesce(rq.requirements->>'work_type',''), rq.requirements->'compiler_spec',
         br.id, w.status
    into v_request_id, v_request_key, v_request_status, v_source_type,
         v_work_type, v_spec, v_run_id, v_work_status
  from public.ct_factory_work_units w
  join public.ct_factory_build_runs br on br.id=w.build_run_id
  join public.ct_factory_build_requests rq on rq.id=br.build_request_id
  where w.id=p_work_unit_id and w.lane='generate'
  for update of w;

  if v_request_id is null then raise exception 'generate_work_unit_not_found'; end if;
  if v_work_status not in ('ready','running') then raise exception 'generate_work_unit_not_claimable'; end if;
  if v_source_type <> 'penta_certify' or v_work_type <> 'provider_certification_software' then
    raise exception 'not_penta_certification_software';
  end if;
  if jsonb_typeof(v_spec) <> 'object' or jsonb_typeof(v_spec->'components') <> 'array' then
    raise exception 'invalid_compiler_spec';
  end if;

  v_components := v_spec->'components';
  v_component_count := jsonb_array_length(v_components);
  if v_component_count < 1 or v_component_count > 100 then raise exception 'invalid_component_count'; end if;

  select count(*) into v_unsupported
  from jsonb_array_elements(v_components) c
  where coalesce(c->>'kind','') not in (
    'typescript_module','certification_contract','certification_contract_test',
    'openapi_spec','edge_api','env_contract','event_contract','policy_manifest',
    'github_workflow','json_document'
  );

  select count(*) into v_missing_paths
  from jsonb_array_elements(v_components) c
  where btrim(coalesce(c->>'path',''))=''
     or c->>'path' like '/%'
     or c->>'path' like '%..%';

  select count(*) - count(distinct c->>'path') into v_duplicate_paths
  from jsonb_array_elements(v_components) c;

  select count(*) into v_secret_values
  from jsonb_array_elements(v_components) c
  cross join lateral jsonb_array_elements(
    case when c->>'kind'='env_contract' and jsonb_typeof(c->'variables')='array'
         then c->'variables' else '[]'::jsonb end
  ) v
  where v->'secret'='true'::jsonb and (v ? 'value' or v ? 'default' or v ? 'example');

  if v_unsupported>0 or v_missing_paths>0 or v_duplicate_paths>0 or v_secret_values>0 then
    v_output := jsonb_build_object(
      'ok',false,
      'response_status','hold',
      'compiler_contract','ct-factory-compiler.v5.1',
      'generator_contract','ct.penta.factory.deterministic-certification-compiler.v1',
      'deterministic',true,
      'candidate_only',true,
      'authority_created',false,
      'production_deploy',false,
      'provider_write_performed',false,
      'secret_exposed',false,
      'validation',jsonb_build_object(
        'unsupported_components',v_unsupported,
        'missing_or_unsafe_paths',v_missing_paths,
        'duplicate_paths',v_duplicate_paths,
        'embedded_secret_values',v_secret_values
      )
    );
    perform public.ct_factory_complete_work(p_work_unit_id,'hold',v_output);
    return v_output;
  end if;

  select coalesce(jsonb_agg(c->>'path' order by c->>'path'),'[]'::jsonb)
    into v_files from jsonb_array_elements(v_components) c;

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'kind',c->>'kind',
      'path',c->>'path',
      'sha256',encode(extensions.digest(convert_to(c::text,'UTF8'),'sha256'),'hex')
    ) order by c->>'path'
  ),'[]'::jsonb)
    into v_manifest from jsonb_array_elements(v_components) c;

  v_spec_sha256 := encode(extensions.digest(convert_to(v_spec::text,'UTF8'),'sha256'),'hex');

  v_output := jsonb_build_object(
    'ok',true,
    'response_status','completed',
    'compiler_contract','ct-factory-compiler.v5.1',
    'generator_contract','ct.penta.factory.deterministic-certification-compiler.v1',
    'deterministic',true,
    'candidate_only',true,
    'authority_created',false,
    'production_deploy',false,
    'provider_write_performed',false,
    'secret_exposed',false,
    'request_id',v_request_id,
    'request_key',v_request_key,
    'build_run_id',v_run_id,
    'component_count',v_component_count,
    'files',v_files,
    'component_manifest',v_manifest,
    'artifact_sha256',v_spec_sha256,
    'validation',jsonb_build_object(
      'compiler_spec_object',true,
      'supported_component_kinds',true,
      'safe_relative_paths',true,
      'unique_paths',true,
      'embedded_secret_values',false
    ),
    'required_independent_lanes',jsonb_build_array('security','test','package','deploy','assurance')
  );

  v_complete := public.ct_factory_complete_work(p_work_unit_id,'passed',v_output);
  return v_output || jsonb_build_object('factory_completion',v_complete);
end;
$$;

revoke all on function integration_control.penta_factory_compile_certification_spec_v1(uuid) from public;
revoke all on function integration_control.penta_factory_compile_certification_spec_v1(uuid) from anon;
revoke all on function integration_control.penta_factory_compile_certification_spec_v1(uuid) from authenticated;
grant execute on function integration_control.penta_factory_compile_certification_spec_v1(uuid) to service_role;

create or replace function public.ct_factory_internal_generate_tick_v1(p_limit integer default 2)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','public','integration_control'
as $$
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

  -- First consume deterministic PentaCertifier compiler specs. These are internal
  -- structured builds and must not be sent to the AI/provider generator.
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
      v_result:=integration_control.penta_factory_compile_certification_spec_v1(r.id);
    exception when others then
      v_result:=jsonb_build_object(
        'ok',false,'work_unit_id',r.id,'reason','deterministic_compiler_exception',
        'error_class',sqlstate,
        'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),
        'automatic_retry',false,
        'candidate_only',true,
        'authority_created',false,
        'provider_write_performed',false
      );
      perform public.ct_factory_complete_work(r.id,'hold',v_result);
    end;

    v_processed:=v_processed+1;
    v_results:=v_results||jsonb_build_array(v_result);
    if coalesce((v_result->>'ok')::boolean,false) then v_passed:=v_passed+1; else v_held:=v_held+1; end if;
  end loop;

  -- Preserve the existing OpenAI generator for ordinary factory requests.
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
    'deterministic_certification_compiler_enabled',true
  );
end;
$$;

revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from public;
revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from anon;
revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from authenticated;
grant execute on function public.ct_factory_internal_generate_tick_v1(integer) to service_role;

comment on function integration_control.penta_factory_compile_certification_spec_v1(uuid) is
'Deterministically compiles governed PentaCertifier compiler_spec requests into candidate-only factory manifests. No AI/provider call, provider write, credential value, production deployment, certification, or D3 authority is created.';
