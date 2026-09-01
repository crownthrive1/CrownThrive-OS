create or replace function integration_control.penta_ads_production_stable_110_certifier_invoke_v1(p_head_sha text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','vault','extensions'
as $function$
declare v_jwt text; v_control text; v_resp extensions.http_response; v_body jsonb;
begin
  if p_head_sha !~ '^[a-f0-9]{40}$' then raise exception 'penta_ads_110_head_sha_invalid'; end if;
  select decrypted_secret into v_jwt from vault.decrypted_secrets where name='PENTA_ADS_EDGE_INVOKE_JWT' limit 1;
  select decrypted_secret into v_control from vault.decrypted_secrets where name='PENTA_ADS_CPANEL_RUNTIME_CONTROL' limit 1;
  if nullif(v_jwt,'') is null or nullif(v_control,'') is null then raise exception 'penta_ads_110_certifier_control_missing'; end if;
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','120000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  v_resp:=chlom_runtime.dail_http_v1(('POST','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentaads-production-stable-110-certifier',array[extensions.http_header('Authorization','Bearer '||v_jwt),extensions.http_header('X-CT-Control',v_control),extensions.http_header('Content-Type','application/json')]::extensions.http_header[],'application/json',jsonb_build_object('head_sha',p_head_sha)::text)::extensions.http_request);
  begin v_body:=coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body:=jsonb_build_object('state','error','reason','edge_non_json_response'); end;
  return v_body||jsonb_build_object('edge_http_status',v_resp.status,'secret_exported',false);
end;
$function$;
revoke all on function integration_control.penta_ads_production_stable_110_certifier_invoke_v1(text) from public;
grant execute on function integration_control.penta_ads_production_stable_110_certifier_invoke_v1(text) to service_role;
