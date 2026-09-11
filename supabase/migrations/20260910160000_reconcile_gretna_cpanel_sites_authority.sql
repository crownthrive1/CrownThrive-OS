-- CrownThrive OS / ThriveBase
-- Gretna Junction cPanel reconciliation — 2026-09-10
-- Sites remains the publication/maintenance authority for ct.surface.gretna-junction.production.
-- cPanel is a secondary hosting/domain-control service only.
-- The founder-added Vault alias is intentionally preserved exactly as entered: `Gretne Junction cPanel`.
-- Never place the underlying secret value in source, logs, MCP output, or public projections.

do $block$
declare
  v_secret_id uuid;
  v_fp text;
  v_warm_fp text:=encode(extensions.digest(convert_to('cpanel_gretna_junction:no_independent_warm_credential','UTF8'),'sha256'),'hex');
begin
  select id,encode(extensions.digest(convert_to(secret,'UTF8'),'sha256'),'hex') into v_secret_id,v_fp
  from vault.decrypted_secrets where name='Gretne Junction cPanel' order by updated_at desc limit 1;
  if v_secret_id is null then raise exception 'gretna_manual_vault_secret_not_found'; end if;

  insert into integration_control.services(service_id,display_name,base_url,docs_url,auth_scheme,credential_ref,credential_state,integration_state,write_gate,monthly_request_limit,timezone,metadata,updated_at)
  values('cpanel_gretna_junction','Gretna Junction cPanel — Secondary Hosting/Domain Control','https://s882.use1.mysecurecloudhost.com:2083','https://api.docs.cpanel.net/openapi/cpanel/overview/','cPanel UAPI token via Supabase Vault','Gretne Junction cPanel','verified','read_verified',false,-1,'UTC',jsonb_build_object('provider','cPanel','account_username','gretnajunction','target_domain','gretnajunction.com','site_publication_authority','Sites','site_surface_id','ct.surface.gretna-junction.production','role','secondary_hosting_domain_control','vault_alias','Gretne Junction cPanel','provider_write',false,'raw_secret_export',false,'provider_throttles_still_apply',true),now())
  on conflict(service_id) do update set display_name=excluded.display_name,base_url=excluded.base_url,docs_url=excluded.docs_url,auth_scheme=excluded.auth_scheme,credential_ref=excluded.credential_ref,credential_state='verified',integration_state='read_verified',write_gate=false,monthly_request_limit=-1,metadata=coalesce(integration_control.services.metadata,'{}'::jsonb)||excluded.metadata,updated_at=now();

  update integration_control.credential_continuity_registry
  set service_id='cpanel_gretna_junction',primary_vault_name='Gretne Junction cPanel',primary_present=true,recovery_vault_name=null,recovery_present=false,fingerprint_sha256=v_fp,continuity_state='verified_primary_only',recovery_note='Founder-added Gretna cPanel credential verified from Supabase Vault on 2026-09-10. Alias preserved exactly as entered. Sites remains publication authority; cPanel is secondary hosting/domain control.',runtime_consumers='["cpanel_gretna_junction","cpanel_account_control_mesh","cpanel_account_partner_mcp","PentaCredentials","PentaWire","PentaCertify","PentaFabric","PentaMesh","ct.platform.gretna-junction","Sites"]'::jsonb,last_verified_at=now(),updated_at=now()
  where credential_id='ct.cred.cpanel.gretna-junction.penta-api.01';

  insert into integration_control.credential_custody_policy_v1(credential_id,founder_supplied,custody_mode,auto_rotate_allowed,auto_delete_allowed,silent_replace_allowed,api_mcp_autowire,required_fabrics,authority_note,updated_at)
  values('ct.cred.cpanel.gretna-junction.penta-api.01',true,'append_only',false,false,false,true,'["PentaCredentials","PentaFlex","PentaMCP","PentaWire","PentaCertify","PentaFabric","PentaMesh"]'::jsonb,'Founder-supplied production cPanel token; Vault-only secret custody. Sites is publication authority. cPanel is secondary read/control and does not supersede Sites.',now())
  on conflict(credential_id) do update set founder_supplied=true,custody_mode='append_only',auto_rotate_allowed=false,auto_delete_allowed=false,silent_replace_allowed=false,api_mcp_autowire=true,required_fabrics=excluded.required_fabrics,authority_note=excluded.authority_note,updated_at=now();

  insert into penta_docs.credential_reference_ledger_v1(chamber_id,stable_id,provider,service_id,credential_class,vault_secret_name,vault_secret_id,fingerprint_sha256,exposure_class,verification_state,runtime_consumers,alias_set,source_ref,raw_value_stored,metadata,updated_at)
  values('ct.pentadocs.chamber.credential-custody-master','ct.cred.cpanel.gretna-junction.penta-api.01','cPanel','cpanel_gretna_junction','hot_account_api_unrestricted','Gretne Junction cPanel',v_secret_id,v_fp,'restricted_metadata_only','provider_auth_verified','["cpanel_gretna_junction","cpanel_account_control_mesh","cpanel_account_partner_mcp","PentaCredentials","PentaWire","PentaCertify","PentaFabric","PentaMesh","ct.platform.gretna-junction","Sites"]'::jsonb,'["Gretne Junction cPanel"]'::jsonb,'founder_manual_vault_2026-09-09',false,jsonb_build_object('account_username','gretnajunction','target_domain','gretnajunction.com','site_authority','Sites','role','secondary_hosting_domain_control','raw_secret_persisted_outside_vault',false),now())
  on conflict(chamber_id,stable_id) do update set provider=excluded.provider,service_id=excluded.service_id,credential_class=excluded.credential_class,vault_secret_name=excluded.vault_secret_name,vault_secret_id=excluded.vault_secret_id,fingerprint_sha256=excluded.fingerprint_sha256,exposure_class=excluded.exposure_class,verification_state=excluded.verification_state,runtime_consumers=excluded.runtime_consumers,alias_set=excluded.alias_set,source_ref=excluded.source_ref,raw_value_stored=false,metadata=excluded.metadata,updated_at=now();

  insert into integration_control.penta_wire_thrivebase_routes_v3(service_id,route_tier,selected_credential_id,provider_system,credential_reference,route_source,route_state,provider_state,credential_reference_state,selection_priority,check_interval,last_checked_at,next_check_at,consecutive_failures,source_fingerprint,metadata,updated_at)
  values
    ('cpanel_gretna_junction','hot','ct.cred.cpanel.gretna-junction.penta-api.01','cPanel','Gretne Junction cPanel','thrivebase_primary','ready','authenticated','verified',10,interval '1 hour',now(),now()+interval '1 hour',0,v_fp,jsonb_build_object('site_authority','Sites','role','secondary_hosting_domain_control','provider_write',false),now()),
    ('cpanel_gretna_junction','warm',null,'cPanel',null,'controlled_reconcile','blocked','unavailable','missing',20,interval '6 hours',now(),now()+interval '6 hours',0,v_warm_fp,jsonb_build_object('reason','no independently issued warm credential','fingerprint_semantics','non_secret_route_descriptor'),now()),
    ('cpanel_gretna_junction','cold','ct.cred.cpanel.gretna-junction.penta-api.01','cPanel','Gretne Junction cPanel','thrivebase_catalog_reference','sealed','rehydration_only','verified',30,interval '24 hours',now(),now()+interval '24 hours',0,v_fp,jsonb_build_object('activation','explicit_rehydration_only','same_provider_credential_reference',true,'provider_write',false),now())
  on conflict(service_id,route_tier) do update set selected_credential_id=excluded.selected_credential_id,provider_system=excluded.provider_system,credential_reference=excluded.credential_reference,route_source=excluded.route_source,route_state=excluded.route_state,provider_state=excluded.provider_state,credential_reference_state=excluded.credential_reference_state,selection_priority=excluded.selection_priority,check_interval=excluded.check_interval,last_checked_at=now(),next_check_at=excluded.next_check_at,consecutive_failures=0,last_error_code=null,source_fingerprint=excluded.source_fingerprint,metadata=excluded.metadata,updated_at=now();

  update integration_control.website_surfaces
  set provider_system='Sites',provider_connection_state='verified',health_state='healthy',metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('site_maintenance_authority','Sites','supporting_cpanel_control',jsonb_build_object('service_id','cpanel_gretna_junction','role','secondary_hosting_domain_control','vault_alias','Gretne Junction cPanel','vault_bind_state','VERIFIED','provider_write',false,'raw_secret_exported',false,'reconciled_at',clock_timestamp()),'custom_domain_control_20260909',coalesce(metadata->'custom_domain_control_20260909','{}'::jsonb)||jsonb_build_object('vault_alias','Gretne Junction cPanel','vault_bind_state','VERIFIED','cpanel_control_service','cpanel_gretna_junction','sites_activation_state','SITES_PRIMARY_MAINTAINER','cpanel_provider_readback','PASS_2026-09-10','raw_secret_exported',false,'reconciled_at',clock_timestamp())),updated_at=now()
  where surface_id='ct.surface.gretna-junction.production';
end;
$block$;

create or replace function integration_control.cpanel_gretna_junction_secure_read_v1(p_operation text,p_args jsonb default '{}'::jsonb,p_invocation_kind text default 'manual') returns jsonb
language plpgsql security definer
set search_path to 'pg_catalog','integration_control','public','extensions','vault','chlom_runtime','pg_temp'
as $function$
declare
  v_claims text:=nullif(current_setting('request.jwt.claims',true),'');
  v_role text:='';
  v_secret text;
  v_url text;
  v_resp extensions.http_response;
  v_body jsonb:='{}'::jsonb;
  v_ok boolean:=false;
  v_found boolean:=false;
  v_provider_status integer:=0;
  v_sanitized jsonb;
begin
  if v_claims is not null and v_claims ~ '^\s*\{' then v_role:=coalesce(v_claims::jsonb->>'role',''); end if;
  if session_user not in ('postgres','supabase_admin') and current_user<>'service_role' and v_role<>'service_role' then raise exception 'service_role_required' using errcode='42501'; end if;
  if coalesce(p_args,'{}'::jsonb)<>'{}'::jsonb then raise exception 'gretna_cpanel_read_takes_no_args'; end if;
  if p_invocation_kind not in ('manual','api','mcp','scheduled_canary','certification_canary') then raise exception 'invalid_invocation_kind'; end if;
  v_secret:=public.get_runtime_secret('Gretne Junction cPanel');

  if p_operation='health.status' then
    v_ok:=coalesce(length(v_secret),0)>20;
    return jsonb_build_object('state',case when v_ok then 'PASS' else 'HOLD_CREDENTIAL_UNAVAILABLE' end,'service_id','cpanel_gretna_junction','operation_key',p_operation,'site_publication_authority','Sites','role','secondary_hosting_domain_control','credential_state',case when v_ok then 'verified' else 'missing' end,'provider_called',false,'provider_write',false,'credential_exposed',false,'secret_value_returned',false,'authority_effect','none','observed_at',clock_timestamp());
  elsif p_operation='target_domain.status' then
    v_url:='https://s882.use1.mysecurecloudhost.com:2083/execute/DomainInfo/list_domains';
  elsif p_operation='disk_usage.status' then
    v_url:='https://s882.use1.mysecurecloudhost.com:2083/execute/StatsBar/get_stats?display=diskusage';
  else
    raise exception 'unsupported_gretna_cpanel_operation';
  end if;

  if coalesce(v_secret,'')='' then
    return jsonb_build_object('state','HOLD_CREDENTIAL_UNAVAILABLE','service_id','cpanel_gretna_junction','operation_key',p_operation,'provider_called',false,'provider_write',false,'credential_exposed',false,'secret_value_returned',false,'authority_effect','none','observed_at',clock_timestamp());
  end if;

  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','15000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  v_resp:=chlom_runtime.dail_http_v1((row('GET'::extensions.http_method,v_url::varchar,array[
    extensions.http_header('Authorization'::varchar,('cpanel gretnajunction:'||v_secret)::varchar),
    extensions.http_header('Accept'::varchar,'application/json'::varchar),
    extensions.http_header('User-Agent'::varchar,'CrownThrive-PentaWire-Gretna/1.0'::varchar)
  ]::extensions.http_header[],null::varchar,null::varchar)::extensions.http_request));

  begin v_body:=coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body:='{}'::jsonb; end;
  v_provider_status:=coalesce((v_body->>'status')::int,0);
  if p_operation='target_domain.status' then
    v_found:=coalesce(v_body#>>'{data,main_domain}','')='gretnajunction.com'
      or exists(select 1 from jsonb_array_elements_text(coalesce(v_body#>'{data,addon_domains}','[]'::jsonb)) x where x='gretnajunction.com')
      or exists(select 1 from jsonb_array_elements_text(coalesce(v_body#>'{data,parked_domains}','[]'::jsonb)) x where x='gretnajunction.com')
      or exists(select 1 from jsonb_array_elements_text(coalesce(v_body#>'{data,sub_domains}','[]'::jsonb)) x where x='gretnajunction.com');
    v_ok:=v_resp.status between 200 and 299 and v_provider_status=1 and v_found;
  else
    v_ok:=v_resp.status between 200 and 299 and v_provider_status=1;
  end if;
  v_sanitized:=jsonb_build_object('state',case when v_ok then 'PASS' else 'FAIL_PROVIDER_READ' end,'service_id','cpanel_gretna_junction','operation_key',p_operation,'http_status',v_resp.status,'provider_uapi_status',v_provider_status,'target_domain_found',case when p_operation='target_domain.status' then v_found else null end,'site_publication_authority','Sites','role','secondary_hosting_domain_control','provider_called',true,'provider_write',false,'credential_exposed',false,'secret_value_returned',false,'response_body_stored',false,'authority_effect','none','observed_at',clock_timestamp());
  return v_sanitized||jsonb_build_object('evidence_sha256',encode(extensions.digest(convert_to(v_sanitized::text,'UTF8'),'sha256'),'hex'));
exception when others then
  if sqlstate='42501' then raise; end if;
  return jsonb_build_object('state','FAIL_RUNTIME_EXCEPTION','service_id','cpanel_gretna_junction','operation_key',p_operation,'error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(sqlerrm,'UTF8'),'sha256'),'hex'),'provider_write',false,'credential_exposed',false,'secret_value_returned',false,'authority_effect','none','observed_at',clock_timestamp());
end;
$function$;

create or replace function public.ct_cpanel_gretna_junction_api_v1(p_operation text,p_params jsonb default '{}'::jsonb) returns jsonb
language sql security definer set search_path to 'pg_catalog','integration_control','public','pg_temp'
as $$select integration_control.cpanel_gretna_junction_secure_read_v1(p_operation,coalesce(p_params,'{}'::jsonb),'api');$$;

create or replace function public.ct_cpanel_gretna_junction_mcp_call_v1(p_tool_name text,p_arguments jsonb default '{}'::jsonb) returns jsonb
language plpgsql security definer set search_path to 'pg_catalog','integration_control','public','pg_temp'
as $function$
begin
  case p_tool_name
    when 'cpanel_gretna_junction_health_status' then return integration_control.cpanel_gretna_junction_secure_read_v1('health.status',coalesce(p_arguments,'{}'::jsonb),'mcp');
    when 'cpanel_gretna_junction_target_domain_status' then return integration_control.cpanel_gretna_junction_secure_read_v1('target_domain.status',coalesce(p_arguments,'{}'::jsonb),'mcp');
    when 'cpanel_gretna_junction_disk_usage_status' then return integration_control.cpanel_gretna_junction_secure_read_v1('disk_usage.status',coalesce(p_arguments,'{}'::jsonb),'mcp');
    else raise exception 'unsupported_gretna_cpanel_tool';
  end case;
end;
$function$;

revoke all on function integration_control.cpanel_gretna_junction_secure_read_v1(text,jsonb,text) from public,anon,authenticated;
revoke all on function public.ct_cpanel_gretna_junction_api_v1(text,jsonb) from public,anon,authenticated;
revoke all on function public.ct_cpanel_gretna_junction_mcp_call_v1(text,jsonb) from public,anon,authenticated;
grant execute on function integration_control.cpanel_gretna_junction_secure_read_v1(text,jsonb,text) to service_role;
grant execute on function public.ct_cpanel_gretna_junction_api_v1(text,jsonb) to service_role;
grant execute on function public.ct_cpanel_gretna_junction_mcp_call_v1(text,jsonb) to service_role;

insert into integration_control.endpoint_catalog(endpoint_id,service_id,operation_key,http_method,path_template,risk_class,mutation,source_state,enabled,mcp_candidate,notes,updated_at)
values
 ('ct.cpanel.gretna.health.v1','cpanel_gretna_junction','health.status','GET','/internal/health','D0',false,'verified_read',true,true,'Vault/config health only; Sites remains site publication authority.',now()),
 ('ct.cpanel.gretna.domain.v1','cpanel_gretna_junction','target_domain.status','GET','/execute/DomainInfo/list_domains','D0',false,'verified_read',true,true,'Live provider canary HTTP 200/UAPI 1; gretnajunction.com found.',now()),
 ('ct.cpanel.gretna.disk.v1','cpanel_gretna_junction','disk_usage.status','GET','/execute/StatsBar/get_stats?display=diskusage','D0',false,'verified_read',true,true,'Live provider canary HTTP 200/UAPI 1.',now())
on conflict(service_id,operation_key) do update set http_method=excluded.http_method,path_template=excluded.path_template,risk_class='D0',mutation=false,source_state='verified_read',enabled=true,mcp_candidate=true,notes=excluded.notes,updated_at=now();

insert into integration_control.mcp_tools(tool_name,service_id,operation_key,risk_class,enabled,requires_human_approval,input_schema,output_schema,notes,updated_at)
values
 ('cpanel_gretna_junction_health_status','cpanel_gretna_junction','health.status','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Read-only canonical Vault/config status; no secret return.',now()),
 ('cpanel_gretna_junction_target_domain_status','cpanel_gretna_junction','target_domain.status','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Read-only cPanel domain presence; Sites remains publication authority.',now()),
 ('cpanel_gretna_junction_disk_usage_status','cpanel_gretna_junction','disk_usage.status','D0',true,false,'{"type":"object","additionalProperties":false}'::jsonb,'{"type":"object"}'::jsonb,'Read-only cPanel disk status; Sites remains publication authority.',now())
on conflict(tool_name) do update set service_id=excluded.service_id,operation_key=excluded.operation_key,risk_class='D0',enabled=true,requires_human_approval=false,input_schema=excluded.input_schema,output_schema=excluded.output_schema,notes=excluded.notes,updated_at=now();

insert into chlom_runtime.mcp_tool_exposure(tool_name,server_id,enabled,exposure_state,minimum_authority,updated_at)
values
 ('cpanel_gretna_junction_health_status','ct.mcp.chlom-core',true,'production','D0',now()),
 ('cpanel_gretna_junction_target_domain_status','ct.mcp.chlom-core',true,'production','D0',now()),
 ('cpanel_gretna_junction_disk_usage_status','ct.mcp.chlom-core',true,'production','D0',now())
on conflict(tool_name) do update set server_id='ct.mcp.chlom-core',enabled=true,exposure_state='production',minimum_authority='D0',updated_at=now();

insert into integration_control.penta_wire_read_adapters_v1(service_id,adapter_kind,exact_contract,transport_ref,allowed_operations,public_projection,provider_write,credential_forwarding,authority_effect,state,evidence,updated_at)
values('cpanel_gretna_junction','SECURE_HTTP','integration_control.cpanel_gretna_junction_secure_read_v1(text,jsonb,text)','chlom_runtime.dail_http_v1 -> cPanel UAPI','["health.status","target_domain.status","disk_usage.status"]'::jsonb,false,false,false,'none','active',jsonb_build_object('site_authority','Sites','role','secondary_hosting_domain_control','vault_alias','Gretne Junction cPanel','provider_write',false,'credential_exposed',false),now())
on conflict(service_id) do update set adapter_kind='SECURE_HTTP',exact_contract=excluded.exact_contract,transport_ref=excluded.transport_ref,allowed_operations=excluded.allowed_operations,public_projection=false,provider_write=false,credential_forwarding=false,authority_effect='none',state='active',evidence=excluded.evidence,updated_at=now();
