-- PentaCertifier deterministic compiler artifact materialization v2.
-- Materializes canonical source_file, compiler_report, and generated_manifest
-- artifacts required by ct.factory.test.v4 while preserving candidate-only,
-- fail-closed, service-only execution. No provider call or authority expansion.

create or replace function integration_control.penta_factory_render_cert_component_v2(
  p_component jsonb,
  p_package_name text
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','extensions','integration_control'
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true),'');
  v_kind text := coalesce(p_component->>'kind','');
  v_path text := coalesce(p_component->>'path','');
  v_content text;
  v_required jsonb := coalesce(p_component->'required_checks','[]'::jsonb);
  v_vars jsonb := '[]'::jsonb;
  v_paths jsonb := '{}'::jsonb;
  v_sha text;
  v_bytes integer;
  r record;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if nullif(btrim(coalesce(p_package_name,'')),'') is null then raise exception 'package_name_required'; end if;
  if nullif(btrim(v_path),'') is null or v_path like '/%' or v_path like '%..%' then raise exception 'unsafe_component_path'; end if;

  case v_kind
    when 'typescript_module' then
      v_content := format(
        'export const %I = %s as const;%s',
        coalesce(nullif(p_component->>'export_name',''),'serviceInfo'),
        jsonb_pretty(coalesce(p_component->'value','{}'::jsonb)),
        E'\n'
      );

    when 'certification_contract' then
      v_content :=
        'export type CertificationEvidence = Record<string, boolean | undefined>;' || E'\n' ||
        'export type CertificationRisk = "D0" | "D1" | "D2" | "D3";' || E'\n' ||
        'export type CertificationDecision = { allowed:boolean; state:"verified"|"incomplete"|"human_governance_required"|"forbidden"; missing:string[]; reason:string; };' || E'\n' ||
        'export const certificationContract = ' ||
        jsonb_pretty(jsonb_build_object(
          'contract','ct.penta.certify.evaluator.v1',
          'surface_id',coalesce(p_component->>'surface_id',''),
          'provider_system',coalesce(p_component->>'provider_system',''),
          'task_kind',coalesce(p_component->>'task_kind','inspect'),
          'risk_class',coalesce(p_component->>'risk_class','D2'),
          'required_checks',v_required,
          'operation_default','deny_until_certified',
          'universal_delete',false,
          'arbitrary_admin_mutation',false,
          'money_movement',false
        )) || ' as const;' || E'\n' ||
        'export function evaluateCertification(evidence: CertificationEvidence): CertificationDecision {' || E'\n' ||
        '  if (evidence.universal_delete_requested || evidence.arbitrary_admin_requested || evidence.money_movement_requested || evidence.destructive_action_requested) return {allowed:false,state:"forbidden",missing:[],reason:"prohibited_authority_requested"};' || E'\n' ||
        '  if (certificationContract.risk_class === "D3") return {allowed:false,state:"human_governance_required",missing:[],reason:"d3_human_governance_required"};' || E'\n' ||
        '  const missing = certificationContract.required_checks.filter((key) => evidence[String(key)] !== true);' || E'\n' ||
        '  if (missing.length) return {allowed:false,state:"incomplete",missing:missing.map(String),reason:"required_evidence_incomplete"};' || E'\n' ||
        '  return {allowed:true,state:"verified",missing:[],reason:"bounded_evidence_complete"};' || E'\n' ||
        '}' || E'\n';

    when 'certification_contract_test' then
      v_content :=
        'import { assertEquals } from "jsr:@std/assert";' || E'\n' ||
        'import { evaluateCertification } from "./' || replace(coalesce(nullif(p_component->>'target',''),'src/certification-contract.ts'),'"','') || '";' || E'\n' ||
        'const required: string[] = ' || coalesce(v_required,'[]'::jsonb)::text || ';' || E'\n' ||
        'Deno.test("certification fails closed with empty evidence",()=>{const d=evaluateCertification({});assertEquals(d.allowed,false);});' || E'\n' ||
        'Deno.test("certification rejects prohibited authority",()=>{const complete=Object.fromEntries(required.map((k)=>[k,true]));const d=evaluateCertification({...complete,universal_delete_requested:true});assertEquals(d.allowed,false);assertEquals(d.state,"forbidden");});' || E'\n' ||
        'Deno.test("certification passes complete bounded evidence",()=>{const complete=Object.fromEntries(required.map((k)=>[k,true]));const d=evaluateCertification(complete);assertEquals(d.allowed,true);assertEquals(d.state,"verified");});' || E'\n';

    when 'openapi_spec' then
      for r in
        select x.value as item
        from jsonb_array_elements(coalesce(p_component->'paths','[]'::jsonb)) x
      loop
        v_paths := v_paths || jsonb_build_object(
          r.item->>'path',
          jsonb_build_object(
            lower(coalesce(r.item->>'method','get')),
            jsonb_build_object(
              'operationId',coalesce(r.item->>'operation_id','status'),
              'summary',coalesce(r.item->>'summary','Certification endpoint'),
              'responses',jsonb_build_object(
                '200',jsonb_build_object(
                  'description','Success',
                  'content',jsonb_build_object(
                    'application/json',jsonb_build_object(
                      'schema',coalesce(r.item->'response_schema',jsonb_build_object('type','object'))
                    )
                  )
                )
              )
            )
          )
        );
      end loop;
      v_content := jsonb_pretty(jsonb_build_object(
        'openapi','3.1.0',
        'info',jsonb_build_object(
          'title',coalesce(p_component->>'title',p_package_name || ' Certification'),
          'version',coalesce(p_component->>'version','1.0.0')
        ),
        'paths',v_paths
      )) || E'\n';

    when 'edge_api' then
      v_content :=
        'import "jsr:@supabase/functions-js/edge-runtime.d.ts";' || E'\n' ||
        'const SERVICE=' || to_jsonb(coalesce(p_component->>'service',p_package_name || ' Certification'))::text || ';' || E'\n' ||
        'Deno.serve(async(req:Request)=>{const u=new URL(req.url);if(req.method==="GET"&&u.pathname.endsWith("/health"))return Response.json({ok:true,service:SERVICE,generated_by:"ct-factory-compiler.v5.1"});if(req.method!=="GET")return Response.json({error:"method_not_allowed"},{status:405});return Response.json({service:SERVICE,message:' ||
        to_jsonb(coalesce(p_component->>'message','Fail-closed certification package. Provider mutation authority is not implied.'))::text ||
        '});});' || E'\n';

    when 'env_contract' then
      select coalesce(jsonb_agg(value - 'value' - 'default' - 'example' order by ord),'[]'::jsonb)
      into v_vars
      from jsonb_array_elements(coalesce(p_component->'variables','[]'::jsonb)) with ordinality as t(value,ord);
      v_content := jsonb_pretty(jsonb_build_object(
        'contract','ct.env.v1',
        'package',p_package_name,
        'variables',v_vars,
        'values_included',false
      )) || E'\n';

    when 'event_contract' then
      v_content := jsonb_pretty(jsonb_build_object(
        '$schema','https://json-schema.org/draft/2020-12/schema',
        '$id','urn:crownthrive:event:' || coalesce(p_component->>'name','penta_certification_contract_evaluated'),
        'title',coalesce(p_component->>'name','penta_certification_contract_evaluated'),
        'type','object',
        'properties',coalesce(p_component->'properties','{}'::jsonb),
        'required',coalesce(p_component->'required','[]'::jsonb),
        'additionalProperties',false
      )) || E'\n';

    when 'policy_manifest' then
      v_content := jsonb_pretty(jsonb_build_object(
        'contract','ct.policy.v1',
        'policy_id',coalesce(p_component->>'policy_id','ct.penta.build.certification-contract.v3'),
        'risk_class',coalesce(p_component->>'risk_class','D2'),
        'authority',coalesce(p_component->>'authority','CHLOM'),
        'fail_closed',coalesce((p_component->>'fail_closed')::boolean,true),
        'required_evidence',coalesce(p_component->'required_evidence','[]'::jsonb),
        'rules',coalesce(p_component->'rules','[]'::jsonb)
      )) || E'\n';

    when 'github_workflow' then
      v_content :=
        'name: ' || replace(coalesce(p_component->>'name',p_package_name || ' Certification Verify'),E'\n',' ') || E'\n\n' ||
        'on: push' || E'\n\n' ||
        'permissions:' || E'\n' ||
        '  contents: read' || E'\n\n' ||
        'jobs:' || E'\n' ||
        '  verify:' || E'\n' ||
        '    runs-on: ubuntu-latest' || E'\n' ||
        '    steps:' || E'\n' ||
        '      - uses: actions/checkout@v4' || E'\n' ||
        '      - uses: denoland/setup-deno@v2' || E'\n' ||
        '        with:' || E'\n' ||
        '          deno-version: v2.x' || E'\n' ||
        '      - name: Deno check' || E'\n' ||
        '        run: deno check src/certification-contract.ts' || E'\n' ||
        '      - name: Deno test' || E'\n' ||
        '        run: deno test certification-contract.test.ts' || E'\n';

    when 'json_document' then
      v_content := jsonb_pretty(coalesce(p_component->'value','{}'::jsonb)) || E'\n';

    else
      raise exception 'unsupported_component_kind:%',v_kind;
  end case;

  v_sha := encode(extensions.digest(convert_to(v_content,'UTF8'),'sha256'),'hex');
  v_bytes := octet_length(convert_to(v_content,'UTF8'));

  return jsonb_build_object(
    'kind',v_kind,
    'path',v_path,
    'bytes',v_bytes,
    'sha256',v_sha,
    'content',v_content,
    'compiler','ct-factory-compiler.v5.1',
    'contract','ct.compiler.file.v3'
  );
end;
$$;

revoke all on function integration_control.penta_factory_render_cert_component_v2(jsonb,text) from public;
revoke all on function integration_control.penta_factory_render_cert_component_v2(jsonb,text) from anon;
revoke all on function integration_control.penta_factory_render_cert_component_v2(jsonb,text) from authenticated;
grant execute on function integration_control.penta_factory_render_cert_component_v2(jsonb,text) to service_role;

create or replace function integration_control.penta_factory_compile_certification_spec_v2(
  p_work_unit_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = 'pg_catalog','extensions','public','integration_control'
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true),'');
  v_request_id uuid;
  v_request_key text;
  v_request_status text;
  v_source_type text;
  v_work_type text;
  v_run_id uuid;
  v_work_status text;
  v_objective text;
  v_requirements jsonb;
  v_spec jsonb;
  v_components jsonb;
  v_package_name text;
  v_project jsonb;
  v_component_count integer := 0;
  v_unsupported integer := 0;
  v_missing_paths integer := 0;
  v_duplicate_paths integer := 0;
  v_embedded_values integer := 0;
  v_files jsonb := '[]'::jsonb;
  v_file_rows jsonb := '[]'::jsonb;
  v_compiler jsonb;
  v_compiler_sha text;
  v_manifest jsonb;
  v_manifest_sha text;
  v_factory jsonb;
  v_generated jsonb;
  v_output jsonb;
  v_complete jsonb;
  v_component jsonb;
  v_rendered jsonb;
begin
  if session_user <> 'postgres' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;

  select rq.id, rq.request_key, rq.status, rq.source_type,
         coalesce(rq.requirements->>'work_type',''), rq.objective, rq.requirements,
         rq.requirements->'compiler_spec', br.id, w.status,
         jsonb_build_object(
           'project_key',p.project_key,
           'name',p.name,
           'repo_full_name',p.repo_full_name,
           'default_branch',p.default_branch,
           'asset_scope',p.asset_scope,
           'build_contract',p.build_contract,
           'deployment_contract',p.deployment_contract,
           'production_enabled',p.production_enabled
         )
    into v_request_id,v_request_key,v_request_status,v_source_type,
         v_work_type,v_objective,v_requirements,v_spec,v_run_id,v_work_status,v_project
  from public.ct_factory_work_units w
  join public.ct_factory_build_runs br on br.id=w.build_run_id
  join public.ct_factory_build_requests rq on rq.id=br.build_request_id
  join public.ct_factory_projects p on p.id=rq.project_id
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

  v_package_name := coalesce(nullif(v_spec->>'package_name',''),'penta-certification-package');
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

  select count(*) into v_embedded_values
  from jsonb_array_elements(v_components) c
  cross join lateral jsonb_array_elements(
    case when c->>'kind'='env_contract' and jsonb_typeof(c->'variables')='array'
         then c->'variables' else '[]'::jsonb end
  ) v
  where v ? 'value' or v ? 'default' or v ? 'example';

  if v_unsupported>0 or v_missing_paths>0 or v_duplicate_paths>0 or v_embedded_values>0 then
    v_output := jsonb_build_object(
      'ok',false,
      'response_status','hold',
      'compiler_contract','ct-factory-compiler.v5.1',
      'generator_contract','ct.penta.factory.deterministic-certification-compiler.v2',
      'deterministic',true,
      'candidate_only',true,
      'authority_created',false,
      'production_deploy',false,
      'provider_write_performed',false,
      'protected_values_included',false,
      'validation',jsonb_build_object(
        'unsupported_components',v_unsupported,
        'missing_or_unsafe_paths',v_missing_paths,
        'duplicate_paths',v_duplicate_paths,
        'embedded_values',v_embedded_values
      )
    );
    perform public.ct_factory_complete_work(p_work_unit_id,'hold',v_output);
    return v_output;
  end if;

  for v_component in select value from jsonb_array_elements(v_components)
  loop
    v_rendered := integration_control.penta_factory_render_cert_component_v2(v_component,v_package_name);

    insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
    values(
      v_run_id,
      'source_file',
      v_rendered->>'path',
      'thrivebase://factory/'||v_run_id::text||'/source/'||
        replace(replace(replace(v_rendered->>'path','%','%25'),'/','%2F'),' ','%20'),
      v_rendered->>'sha256',
      jsonb_build_object(
        'kind',v_rendered->>'kind',
        'path',v_rendered->>'path',
        'bytes',(v_rendered->>'bytes')::integer,
        'content',v_rendered->>'content',
        'compiler','ct-factory-compiler.v5.1',
        'contract','ct.compiler.file.v3'
      )
    )
    on conflict (build_run_id,artifact_type,asset_key) do update
      set uri=excluded.uri,
          sha256=excluded.sha256,
          metadata=excluded.metadata;

    v_files := v_files || jsonb_build_array(v_rendered->>'path');
    v_file_rows := v_file_rows || jsonb_build_array(
      jsonb_build_object(
        'kind',v_rendered->>'kind',
        'path',v_rendered->>'path',
        'bytes',(v_rendered->>'bytes')::integer,
        'sha256',v_rendered->>'sha256'
      )
    );
  end loop;

  v_compiler := jsonb_build_object(
    'ok',true,
    'files',v_file_rows,
    'compiler','ct-factory-compiler.v5.1',
    'package_name',v_package_name,
    'component_kinds',(select coalesce(jsonb_agg(value->>'kind'),'[]'::jsonb) from jsonb_array_elements(v_components)),
    'contract','ct.compiler.v5.1',
    'deterministic',true,
    'structured_blueprints',true,
    'arbitrary_source',false,
    'arbitrary_sql',false,
    'arbitrary_shell',false,
    'protected_values',false,
    'component_count',v_component_count
  );
  v_compiler_sha := encode(extensions.digest(convert_to(v_compiler::text,'UTF8'),'sha256'),'hex');
  v_compiler := v_compiler || jsonb_build_object('report_sha256',v_compiler_sha);

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    v_run_id,'compiler_report',v_package_name||'-compiler-report.json',
    'thrivebase://factory/'||v_run_id::text||'/compiler-report',
    v_compiler_sha,v_compiler
  )
  on conflict (build_run_id,artifact_type,asset_key) do update
    set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  v_factory := jsonb_build_object(
    'owner','CrownThrive, LLC',
    'stages',jsonb_build_array('plan','build','verify','package','release'),
    'canonical_name','PentaFactory',
    'product_contract','ct.pentaframework-factory.v1',
    'compatibility_contract','ct.factory.v4'
  );

  v_manifest := jsonb_build_object(
    'run',v_run_id,
    'layers',jsonb_build_array('source','database','edge_functions','workflows','api_contracts','mcp_contracts','events','tests','docs','assets','governance','routing','rollback'),
    'rights',jsonb_build_object('owner','CrownThrive, LLC','registration_claim',false),
    'factory',v_factory,
    'planner',jsonb_build_object('mode','passthrough','name','ct-factory-blueprint-planner.v4.1','report',null),
    'project',v_project,
    'compiler',v_compiler,
    'contract','ct.factory.v4',
    'objective',v_objective,
    'requirements',v_requirements,
    'product_contract','ct.pentaframework-factory.v1',
    'candidate_only',true,
    'production_deploy',false,
    'authority_expansion',false
  );
  v_manifest_sha := encode(extensions.digest(convert_to(v_manifest::text,'UTF8'),'sha256'),'hex');

  insert into public.ct_factory_artifacts(build_run_id,artifact_type,asset_key,uri,sha256,metadata)
  values(
    v_run_id,'generated_manifest',v_package_name||'-generated-manifest.json',
    'thrivebase://factory/'||v_run_id::text||'/generated-manifest',
    v_manifest_sha,v_manifest
  )
  on conflict (build_run_id,artifact_type,asset_key) do update
    set uri=excluded.uri,sha256=excluded.sha256,metadata=excluded.metadata;

  v_generated := jsonb_build_object(
    'ok',true,
    'sha256',v_manifest_sha,
    'factory',v_factory,
    'planner','passthrough',
    'compiler',v_compiler,
    'manifest',v_manifest,
    'contract','ct.factory.v4',
    'objective',v_objective,
    'requirements',v_requirements,
    'product_contract','ct.pentaframework-factory.v1'
  );

  v_output := jsonb_build_object(
    'generated',v_generated,
    'asset_key',v_package_name||'-generated-manifest.json',
    'generator','ct.penta.factory.deterministic-certification-compiler.v2',
    'response_status','completed',
    'deterministic',true,
    'candidate_only',true,
    'authority_created',false,
    'production_deploy',false,
    'provider_write_performed',false,
    'protected_values_included',false,
    'request_id',v_request_id,
    'request_key',v_request_key,
    'build_run_id',v_run_id,
    'component_count',v_component_count,
    'files',v_files,
    'artifact_sha256',v_manifest_sha,
    'required_independent_lanes',jsonb_build_array('security','test','package','deploy','assurance')
  );

  v_complete := public.ct_factory_complete_work(p_work_unit_id,'passed',v_output);
  return v_output || jsonb_build_object('factory_completion',v_complete);
end;
$$;

revoke all on function integration_control.penta_factory_compile_certification_spec_v2(uuid) from public;
revoke all on function integration_control.penta_factory_compile_certification_spec_v2(uuid) from anon;
revoke all on function integration_control.penta_factory_compile_certification_spec_v2(uuid) from authenticated;
grant execute on function integration_control.penta_factory_compile_certification_spec_v2(uuid) to service_role;

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
$$;

revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from public;
revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from anon;
revoke all on function public.ct_factory_internal_generate_tick_v1(integer) from authenticated;
grant execute on function public.ct_factory_internal_generate_tick_v1(integer) to service_role;

comment on function integration_control.penta_factory_compile_certification_spec_v2(uuid) is
'Deterministically renders and materializes governed PentaCertifier compiler_spec source artifacts, compiler report, and generated manifest for canonical factory testing. Candidate-only; no provider call, production deployment, certification, credential value, or D3 authority.';
