-- CrownThrive Lemon Squeezy integration v2
-- Secret material is never stored in source. Runtime expects Vault alias Penta_LemonSqueezy.

create or replace function integration_control.lemonsqueezy_secure_read_v1(
  p_operation_key text,
  p_params jsonb default '{}'::jsonb,
  p_invocation_kind text default 'manual'::text
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','extensions','vault','chlom_runtime','pg_temp'
as $function$
declare
  v_claims text := nullif(current_setting('request.jwt.claims',true),'');
  v_role text := '';
  v_secret text;
  v_route jsonb;
  v_url text;
  v_resp extensions.http_response;
  v_body jsonb := '{}'::jsonb;
  v_items jsonb := '[]'::jsonb;
  v_result jsonb := '{}'::jsonb;
  v_page_size integer := 50;
  v_page_number integer := 1;
  v_unknown_key text;
  v_now timestamptz := clock_timestamp();
begin
  if v_claims is not null and v_claims ~ '^\s*\{' then
    v_role := coalesce(v_claims::jsonb->>'role','');
  end if;
  if session_user not in ('postgres','supabase_admin')
     and current_user <> 'service_role' and v_role <> 'service_role' then
    raise exception 'service_role_required' using errcode='42501';
  end if;
  if jsonb_typeof(coalesce(p_params,'{}'::jsonb)) <> 'object' then
    raise exception 'params_must_be_object';
  end if;
  if p_invocation_kind not in ('manual','api','mcp','scheduled_canary','certification_canary') then
    raise exception 'invalid_invocation_kind';
  end if;

  if p_operation_key = 'auth.status' then
    if p_params <> '{}'::jsonb then raise exception 'auth_status_takes_no_params'; end if;
    v_url := 'https://api.lemonsqueezy.com/v1/users/me';
  elsif p_operation_key = 'stores.list' then
    if p_params <> '{}'::jsonb then raise exception 'stores_list_takes_no_params'; end if;
    v_url := 'https://api.lemonsqueezy.com/v1/stores';
  elsif p_operation_key = 'catalog.list' then
    select k into v_unknown_key from jsonb_object_keys(p_params) k
      where k not in ('page_size','page_number') limit 1;
    if v_unknown_key is not null then raise exception 'invalid_catalog_param'; end if;
    if p_params ? 'page_size' then
      if coalesce(p_params->>'page_size','') !~ '^[0-9]+$' then raise exception 'invalid_page_size'; end if;
      v_page_size := greatest(1,least(100,(p_params->>'page_size')::integer));
    end if;
    if p_params ? 'page_number' then
      if coalesce(p_params->>'page_number','') !~ '^[0-9]+$' then raise exception 'invalid_page_number'; end if;
      v_page_number := greatest(1,(p_params->>'page_number')::integer);
    end if;
    v_url := 'https://api.lemonsqueezy.com/v1/products?include=variants&page%5Bsize%5D='||v_page_size||'&page%5Bnumber%5D='||v_page_number;
  else
    raise exception 'unsupported_lemonsqueezy_operation';
  end if;

  v_route := integration_control.penta_wire_select_route_v3('lemonsqueezy_crownthrive',false);
  if coalesce(v_route->>'state','') <> 'SELECTED' then
    return jsonb_build_object(
      'state','HOLD_NO_USABLE_ROUTE','service_id','lemonsqueezy_crownthrive',
      'operation_key',p_operation_key,'provider_called',false,'provider_write',false,
      'credential_exposed',false,'credential_forwarded_to_caller',false,
      'authority_effect','none','route_state',coalesce(v_route->>'state','unknown'),'observed_at',v_now
    );
  end if;
  v_secret := public.get_runtime_secret(v_route->>'credential_reference');
  if coalesce(v_secret,'') = '' then
    return jsonb_build_object(
      'state','HOLD_CREDENTIAL_RESOLUTION_FAILED','service_id','lemonsqueezy_crownthrive',
      'operation_key',p_operation_key,'provider_called',false,'provider_write',false,
      'credential_exposed',false,'credential_forwarded_to_caller',false,
      'authority_effect','none','route_tier',v_route->>'route_tier','observed_at',v_now
    );
  end if;

  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','15000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  v_resp := chlom_runtime.dail_http_v1((row(
    'GET'::extensions.http_method,
    v_url::varchar,
    array[
      extensions.http_header('Authorization'::varchar,('Bearer '||v_secret)::varchar),
      extensions.http_header('Accept'::varchar,'application/vnd.api+json'::varchar),
      extensions.http_header('Content-Type'::varchar,'application/vnd.api+json'::varchar),
      extensions.http_header('User-Agent'::varchar,'CrownThrive-LemonSqueezy/1.0'::varchar)
    ]::extensions.http_header[],
    null::varchar,
    null::varchar
  )::extensions.http_request));

  begin v_body := coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body := '{}'::jsonb; end;

  if v_resp.status between 200 and 299 then
    if p_operation_key = 'auth.status' then
      v_result := jsonb_build_object(
        'state','PASS','service_id','lemonsqueezy_crownthrive','operation_key',p_operation_key,
        'http_status',v_resp.status,'authenticated',true,'account_id',v_body#>>'{data,id}',
        'route_tier',v_route->>'route_tier','provider_called',true,'provider_write',false,
        'credential_exposed',false,'credential_forwarded_to_caller',false,'authority_effect','none','observed_at',v_now
      );
    elsif p_operation_key = 'stores.list' then
      if jsonb_typeof(v_body->'data')='array' then
        select coalesce(jsonb_agg(jsonb_build_object(
          'id',e.value->>'id','name',e.value#>>'{attributes,name}','slug',e.value#>>'{attributes,slug}',
          'url',e.value#>>'{attributes,url}','status',e.value#>>'{attributes,status}',
          'currency',e.value#>>'{attributes,currency}','test_mode',coalesce((e.value#>>'{attributes,test_mode}')::boolean,false)
        )),'[]'::jsonb) into v_items from jsonb_array_elements(v_body->'data') e(value);
      end if;
      v_result := jsonb_build_object(
        'state','PASS','service_id','lemonsqueezy_crownthrive','operation_key',p_operation_key,
        'http_status',v_resp.status,'items',v_items,'returned_count',jsonb_array_length(v_items),
        'route_tier',v_route->>'route_tier','provider_called',true,'provider_write',false,
        'credential_exposed',false,'credential_forwarded_to_caller',false,'authority_effect','none','observed_at',v_now
      );
    else
      if jsonb_typeof(v_body->'data')='array' then
        select coalesce(jsonb_agg(jsonb_build_object(
          'id',e.value->>'id','name',e.value#>>'{attributes,name}','slug',e.value#>>'{attributes,slug}',
          'status',e.value#>>'{attributes,status}','price',e.value#>>'{attributes,price}',
          'from_price',e.value#>>'{attributes,from_price}','to_price',e.value#>>'{attributes,to_price}',
          'store_id',e.value#>>'{attributes,store_id}'
        ) order by e.value#>>'{attributes,name}'),'[]'::jsonb)
        into v_items from jsonb_array_elements(v_body->'data') e(value);
      end if;
      v_result := jsonb_build_object(
        'state','PASS','service_id','lemonsqueezy_crownthrive','operation_key',p_operation_key,
        'http_status',v_resp.status,'items',v_items,'returned_count',jsonb_array_length(v_items),
        'pagination',coalesce(v_body#>'{meta,page}','{}'::jsonb),'route_tier',v_route->>'route_tier',
        'provider_called',true,'provider_write',false,'credential_exposed',false,
        'credential_forwarded_to_caller',false,'authority_effect','none','observed_at',v_now
      );
    end if;
  else
    v_result := jsonb_build_object(
      'state','FAIL_PROVIDER_READ','service_id','lemonsqueezy_crownthrive','operation_key',p_operation_key,
      'http_status',v_resp.status,'error_code',coalesce(v_body#>>'{errors,0,title}',v_body#>>'{errors,0,detail}','lemonsqueezy_provider_read_failed'),
      'route_tier',v_route->>'route_tier','provider_called',true,'provider_write',false,
      'credential_exposed',false,'credential_forwarded_to_caller',false,'authority_effect','none','observed_at',v_now
    );
  end if;
  return v_result || jsonb_build_object('invocation_kind',p_invocation_kind,'secret_value_returned',false);
exception when others then
  if sqlstate='42501' then raise; end if;
  return jsonb_build_object(
    'state','FAIL_RUNTIME_EXCEPTION','service_id','lemonsqueezy_crownthrive','operation_key',p_operation_key,
    'error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(coalesce(sqlerrm,''),'UTF8'),'sha256'),'hex'),
    'error_detail_redacted',left(case when coalesce(v_secret,'')<>'' then replace(sqlerrm,v_secret,'[REDACTED]') else sqlerrm end,240),
    'provider_write',false,'credential_exposed',false,'credential_forwarded_to_caller',false,
    'authority_effect','none','observed_at',clock_timestamp()
  );
end;
$function$;

create or replace function public.ct_lemonsqueezy_api_v1(
  p_operation_key text,
  p_params jsonb default '{}'::jsonb
) returns jsonb
language sql
security definer
set search_path to 'pg_catalog','integration_control','public','pg_temp'
as $$
  select integration_control.lemonsqueezy_secure_read_v1(p_operation_key,coalesce(p_params,'{}'::jsonb),'api');
$$;

create or replace function public.ct_lemonsqueezy_mcp_call_v1(
  p_tool_name text,
  p_arguments jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','public','pg_temp'
as $function$
begin
  case p_tool_name
    when 'lemonsqueezy.auth.status' then return integration_control.lemonsqueezy_secure_read_v1('auth.status',coalesce(p_arguments,'{}'::jsonb),'mcp');
    when 'lemonsqueezy.stores.list' then return integration_control.lemonsqueezy_secure_read_v1('stores.list',coalesce(p_arguments,'{}'::jsonb),'mcp');
    when 'lemonsqueezy.catalog.list' then return integration_control.lemonsqueezy_secure_read_v1('catalog.list',coalesce(p_arguments,'{}'::jsonb),'mcp');
    else raise exception 'unsupported_lemonsqueezy_tool';
  end case;
end;
$function$;

revoke all on function integration_control.lemonsqueezy_secure_read_v1(text,jsonb,text) from public,anon,authenticated;
revoke all on function public.ct_lemonsqueezy_api_v1(text,jsonb) from public,anon,authenticated;
revoke all on function public.ct_lemonsqueezy_mcp_call_v1(text,jsonb) from public,anon,authenticated;
grant execute on function integration_control.lemonsqueezy_secure_read_v1(text,jsonb,text) to service_role;
grant execute on function public.ct_lemonsqueezy_api_v1(text,jsonb) to service_role;
grant execute on function public.ct_lemonsqueezy_mcp_call_v1(text,jsonb) to service_role;

-- Control-plane metadata. Fails closed when the Vault alias is absent.
do $block$
declare
  v_secret_id uuid;
  v_fp text;
  v_digest text;
begin
  select id, encode(extensions.digest(convert_to(secret,'UTF8'),'sha256'),'hex')
    into v_secret_id, v_fp
  from vault.decrypted_secrets
  where name='Penta_LemonSqueezy'
  order by updated_at desc
  limit 1;
  if v_secret_id is null then raise exception 'lemonsqueezy_vault_secret_missing'; end if;

  insert into integration_control.services(service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,write_gate,monthly_request_limit,timezone,metadata,updated_at)
  values ('lemonsqueezy_crownthrive','Lemon Squeezy — CrownThrive','https://api.lemonsqueezy.com/v1','https://docs.lemonsqueezy.com/api','bearer','Penta_LemonSqueezy','verified','read_verified',false,null,'UTC',jsonb_build_object('provider','Lemon Squeezy','store_id','74683','store_name','CrownThrive, LLC','store_slug','crownthrive','currency','USD','test_mode',false,'catalog_product_count',0,'stated_expiration','2127-03-01','product_creation_api_supported',false),now())
  on conflict (service_id) do update set display_name=excluded.display_name,base_url=excluded.base_url,docs_url=excluded.docs_url,auth_scheme=excluded.auth_scheme,credential_ref=excluded.credential_ref,credential_state=excluded.credential_state,integration_state=excluded.integration_state,write_gate=excluded.write_gate,metadata=excluded.metadata,updated_at=now();

  insert into integration_control.credential_continuity_registry(credential_id,service_id,credential_class,provider_system,provider_location_note,primary_vault_name,recovery_vault_name,primary_present,recovery_present,fingerprint_sha256,runtime_consumers,continuity_state,recovery_note,last_verified_at,updated_at)
  values ('ct.cred.lemonsqueezy.live.hot','lemonsqueezy_crownthrive','live_api_key','Lemon Squeezy','Founder-supplied live API key; plaintext restricted to Supabase Vault runtime resolution; stated expiration 2127-03-01.','Penta_LemonSqueezy',null,true,false,v_fp,'["CrownThrive IO","PentaMCP","PentaWire","PentaGreen","CHLOM Wallet"]'::jsonb,'verified_primary_only','No recovery credential supplied; fail closed rather than fabricate warm custody.',now(),now())
  on conflict (credential_id) do update set service_id=excluded.service_id,credential_class=excluded.credential_class,provider_system=excluded.provider_system,provider_location_note=excluded.provider_location_note,primary_vault_name=excluded.primary_vault_name,primary_present=true,fingerprint_sha256=excluded.fingerprint_sha256,runtime_consumers=excluded.runtime_consumers,continuity_state='verified_primary_only',last_verified_at=now(),updated_at=now();

  insert into integration_control.credential_custody_policy_v1(credential_id,founder_supplied,custody_mode,auto_rotate_allowed,auto_delete_allowed,silent_replace_allowed,api_mcp_autowire,required_fabrics,authority_note,updated_at)
  values ('ct.cred.lemonsqueezy.live.hot',true,'append_only',false,false,false,true,'["PentaCredentials","PentaFlex","PentaMCP","PentaWire","PentaCertify"]'::jsonb,'Vault-first least-privilege custody. Current Lemon Squeezy integration exposes verified reads only; provider mutation authority is not implied by credential presence.',now())
  on conflict (credential_id) do update set founder_supplied=true,custody_mode='append_only',auto_rotate_allowed=false,auto_delete_allowed=false,silent_replace_allowed=false,api_mcp_autowire=true,required_fabrics=excluded.required_fabrics,authority_note=excluded.authority_note,updated_at=now();

  insert into penta_docs.credential_reference_ledger_v1(chamber_id,stable_id,provider,service_id,credential_class,vault_secret_name,vault_secret_id,fingerprint_sha256,exposure_class,verification_state,runtime_consumers,alias_set,source_ref,raw_value_stored,metadata,updated_at)
  values ('ct.pentadocs.chamber.credential-custody-master','ct.cred.lemonsqueezy.live.hot','Lemon Squeezy','lemonsqueezy_crownthrive','live_api_key','Penta_LemonSqueezy',v_secret_id,v_fp,'restricted_metadata_only','provider_auth_verified','["CrownThrive IO","PentaMCP","PentaWire","PentaGreen","CHLOM Wallet"]'::jsonb,'["Penta_LemonSqueezy"]'::jsonb,'founder_supplied_chat_2026-09-04',false,jsonb_build_object('store_id','74683','store_name','CrownThrive, LLC','stated_expiration','2127-03-01','raw_secret_persisted_outside_vault',false),now())
  on conflict (chamber_id,stable_id) do update set provider=excluded.provider,service_id=excluded.service_id,credential_class=excluded.credential_class,vault_secret_name=excluded.vault_secret_name,vault_secret_id=excluded.vault_secret_id,fingerprint_sha256=excluded.fingerprint_sha256,exposure_class=excluded.exposure_class,verification_state=excluded.verification_state,runtime_consumers=excluded.runtime_consumers,alias_set=excluded.alias_set,source_ref=excluded.source_ref,raw_value_stored=false,metadata=excluded.metadata,updated_at=now();

  insert into integration_control.endpoint_catalog(endpoint_id,service_id,operation_key,http_method,path_template,risk_class,mutation,source_state,enabled,mcp_candidate,notes,updated_at)
  values
    ('ct.lemonsqueezy.auth.status.v1','lemonsqueezy_crownthrive','auth.status','GET','/users/me','D0',false,'verified_read',true,true,'Redacted authentication canary; returns account ID only.',now()),
    ('ct.lemonsqueezy.stores.list.v1','lemonsqueezy_crownthrive','stores.list','GET','/stores','D0',false,'verified_read',true,true,'Bounded store metadata read.',now()),
    ('ct.lemonsqueezy.catalog.list.v1','lemonsqueezy_crownthrive','catalog.list','GET','/products?include=variants','D0',false,'verified_read',true,true,'Bounded product catalog read; provider product creation is not exposed by Lemon Squeezy public API.',now())
  on conflict (endpoint_id) do update set service_id=excluded.service_id,operation_key=excluded.operation_key,http_method=excluded.http_method,path_template=excluded.path_template,risk_class=excluded.risk_class,mutation=false,source_state='verified_read',enabled=true,mcp_candidate=true,notes=excluded.notes,updated_at=now();

  insert into integration_control.mcp_tools(tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval,input_schema,output_schema,notes,updated_at)
  values
    ('lemonsqueezy.auth.status','lemonsqueezy_crownthrive','auth.status','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Service-role-only provider auth status; no credential material.',now()),
    ('lemonsqueezy.stores.list','lemonsqueezy_crownthrive','stores.list','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Service-role-only store metadata read.',now()),
    ('lemonsqueezy.catalog.list','lemonsqueezy_crownthrive','catalog.list','D0',true,false,'{"type":"object","properties":{"page_size":{"type":"integer","minimum":1,"maximum":100},"page_number":{"type":"integer","minimum":1}},"additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Service-role-only product catalog read.',now())
  on conflict (tool_name) do update set service_id=excluded.service_id,operation_key=excluded.operation_key,risk_class='D0',enabled=true,requires_human_approval=false,input_schema=excluded.input_schema,output_schema=excluded.output_schema,notes=excluded.notes,updated_at=now();

  insert into chlom_runtime.mcp_tool_exposure(tool_name,server_id,enabled,exposure_state,minimum_authority,updated_at)
  values
    ('lemonsqueezy.auth.status','ct.mcp.chlom-core',true,'production','D0',now()),
    ('lemonsqueezy.stores.list','ct.mcp.chlom-core',true,'production','D0',now()),
    ('lemonsqueezy.catalog.list','ct.mcp.chlom-core',true,'production','D0',now())
  on conflict (tool_name) do update set server_id='ct.mcp.chlom-core',enabled=true,exposure_state='production',minimum_authority='D0',updated_at=now();

  insert into integration_control.penta_wire_thrivebase_routes_v3(service_id,route_tier,selected_credential_id,provider_system,credential_reference,route_source,route_state,provider_state,credential_reference_state,selection_priority,check_interval,last_checked_at,next_check_at,consecutive_failures,source_fingerprint,metadata,updated_at)
  values ('lemonsqueezy_crownthrive','hot','ct.cred.lemonsqueezy.live.hot','Lemon Squeezy','Penta_LemonSqueezy','thrivebase_primary','ready','authenticated','verified',10,interval '1 hour',now(),now()+interval '1 hour',0,v_fp,jsonb_build_object('store_id','74683','store_name','CrownThrive, LLC','auth_http_status',200,'catalog_count',0,'provider_write',false),now())
  on conflict (service_id,route_tier) do update set selected_credential_id=excluded.selected_credential_id,provider_system=excluded.provider_system,credential_reference=excluded.credential_reference,route_source=excluded.route_source,route_state='ready',provider_state='authenticated',credential_reference_state='verified',selection_priority=excluded.selection_priority,check_interval=excluded.check_interval,last_checked_at=now(),next_check_at=now()+interval '1 hour',consecutive_failures=0,last_error_code=null,source_fingerprint=excluded.source_fingerprint,metadata=excluded.metadata,updated_at=now();

  insert into integration_control.penta_wire_read_adapters_v1(service_id,adapter_kind,exact_contract,transport_ref,allowed_operations,public_projection,provider_write,credential_forwarding,authority_effect,state,evidence,updated_at)
  values ('lemonsqueezy_crownthrive','SECURE_HTTP','integration_control.lemonsqueezy_secure_read_v1(text,jsonb,text)','chlom_runtime.dail_http_v1','["auth.status","stores.list","catalog.list"]'::jsonb,false,false,false,'none','active',jsonb_build_object('auth_http_status',200,'store_id','74683','catalog_count',0,'credential_exposed',false,'verified_at',now()),now())
  on conflict (service_id) do update set adapter_kind='SECURE_HTTP',exact_contract=excluded.exact_contract,transport_ref=excluded.transport_ref,allowed_operations=excluded.allowed_operations,public_projection=false,provider_write=false,credential_forwarding=false,authority_effect='none',state='active',evidence=excluded.evidence,updated_at=now();

  select encode(extensions.digest(convert_to(
    pg_get_functiondef('integration_control.lemonsqueezy_secure_read_v1(text,jsonb,text)'::regprocedure)||
    pg_get_functiondef('public.ct_lemonsqueezy_api_v1(text,jsonb)'::regprocedure)||
    pg_get_functiondef('public.ct_lemonsqueezy_mcp_call_v1(text,jsonb)'::regprocedure),'UTF8'),'sha256'),'hex') into v_digest;

  insert into integration_control.api_contract_versions(service_id,contract_version,protocol_version,deployment_version,runtime_digest_sha256,lifecycle_state,backward_compatible_with,mutation_tools_enabled,sovereign_vote_authority,notes,updated_at)
  values ('lemonsqueezy_crownthrive','1.0.0','lemonsqueezy-jsonapi-v1',1,v_digest,'active','[]'::jsonb,false,false,'Vault/PentaWire-backed verified read contract. Hot route selected through penta_wire_select_route_v3. Public provider API does not expose product/variant/price creation; no mutation tools enabled.',now())
  on conflict (service_id,contract_version) do update set protocol_version=excluded.protocol_version,deployment_version=excluded.deployment_version,runtime_digest_sha256=excluded.runtime_digest_sha256,lifecycle_state='active',mutation_tools_enabled=false,sovereign_vote_authority=false,notes=excluded.notes,updated_at=now();
end;
$block$;
