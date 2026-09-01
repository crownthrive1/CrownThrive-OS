create or replace function integration_control.penta_ads_stable_deployer_invoke_v1(p_action text, p_property_key text, p_source_sha text, p_run_id text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','vault','extensions'
as $function$
declare
  v_jwt text;
  v_control text;
  v_resp extensions.http_response;
  v_body jsonb;
  v_payload jsonb;
begin
  if p_action not in ('preflight','install','status','rollback') then raise exception 'penta_ads_stable_deployer_action_invalid'; end if;
  if p_source_sha !~ '^[a-f0-9]{40}$' then raise exception 'penta_ads_stable_deployer_source_sha_invalid'; end if;
  if not exists(select 1 from integration_control.penta_ads_property_bindings_v1 where property_key=p_property_key and state='active') then raise exception 'penta_ads_stable_deployer_property_binding_missing'; end if;
  if p_run_id is not null and p_run_id !~ '^[0-9a-fA-F-]{36}$' then raise exception 'penta_ads_stable_deployer_run_id_invalid'; end if;
  select decrypted_secret into v_jwt from vault.decrypted_secrets where name='PENTA_ADS_EDGE_INVOKE_JWT' limit 1;
  select decrypted_secret into v_control from vault.decrypted_secrets where name='PENTA_ADS_CPANEL_RUNTIME_CONTROL' limit 1;
  if nullif(v_jwt,'') is null or nullif(v_control,'') is null then raise exception 'penta_ads_stable_deployer_control_missing'; end if;
  v_payload:=jsonb_build_object('action',p_action,'property_key',p_property_key,'source_sha',p_source_sha);
  if p_run_id is not null then v_payload:=v_payload||jsonb_build_object('run_id',p_run_id); end if;
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','120000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  v_resp:=chlom_runtime.dail_http_v1((
    'POST',
    'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentaads-stable-cpanel-deployer',
    array[
      extensions.http_header('Authorization','Bearer '||v_jwt),
      extensions.http_header('X-CT-Control',v_control),
      extensions.http_header('Content-Type','application/json')
    ]::extensions.http_header[],
    'application/json',
    v_payload::text
  )::extensions.http_request);
  begin v_body:=coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body:=jsonb_build_object('state','error','reason','edge_non_json_response'); end;
  return v_body||jsonb_build_object('edge_http_status',v_resp.status,'secret_exported',false);
end;
$function$;
revoke all on function integration_control.penta_ads_stable_deployer_invoke_v1(text,text,text,text) from public;
grant execute on function integration_control.penta_ads_stable_deployer_invoke_v1(text,text,text,text) to service_role;
