create or replace function integration_control.penta_ads_self_serve_control_invoke_v1(p_action text,p_session text,p_run_id text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions'
as $function$
declare v_resp extensions.http_response; v_body jsonb; v_payload jsonb;
begin
  if p_action not in ('analyze','status','deploy_demo','rollback_demo','zone_catalog','zone_lab_start','zone_lab_complete') then raise exception 'penta_ads_self_serve_control_action_invalid'; end if;
  if length(coalesce(p_session,'')) < 32 then raise exception 'penta_ads_self_serve_control_session_invalid'; end if;
  if p_run_id is not null and p_run_id !~ '^[0-9a-fA-F-]{36}$' then raise exception 'penta_ads_self_serve_control_run_invalid'; end if;
  v_payload:=jsonb_build_object('action',p_action,'session',p_session);
  if p_run_id is not null then v_payload:=v_payload||jsonb_build_object('run_id',p_run_id); end if;
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','120000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  v_resp:=chlom_runtime.dail_http_v1(('POST','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/pentaads-self-serve-control',array[extensions.http_header('Content-Type','application/json')]::extensions.http_header[],'application/json',v_payload::text)::extensions.http_request);
  begin v_body:=coalesce(v_resp.content,'{}')::jsonb; exception when others then v_body:=jsonb_build_object('state','error','reason','edge_non_json_response'); end;
  return v_body||jsonb_build_object('edge_http_status',v_resp.status,'secret_exported',false);
end;
$function$;
revoke all on function integration_control.penta_ads_self_serve_control_invoke_v1(text,text,text) from public;
grant execute on function integration_control.penta_ads_self_serve_control_invoke_v1(text,text,text) to service_role;
