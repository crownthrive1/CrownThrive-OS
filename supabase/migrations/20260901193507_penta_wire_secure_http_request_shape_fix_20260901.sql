do $migration$
declare
  v_def text;
  v_old text := $old$v_resp:=chlom_runtime.dail_http_v1(('GET'::extensions.http_method,v_url::varchar,v_headers,null::varchar,null::varchar)::extensions.http_request);$old$;
  v_new text := $new$v_resp:=chlom_runtime.dail_http_v1(('GET',v_url::varchar,v_headers,'application/json'::varchar,null::varchar)::extensions.http_request);$new$;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='penta_wire_thrivebase_secure_read_v1'
    and pg_get_function_identity_arguments(p.oid)='p_service_id text, p_operation_key text, p_params jsonb, p_invocation_kind text';
  if v_def is null then raise exception 'secure_executor_not_found'; end if;
  if position(v_old in v_def)=0 then raise exception 'http_request_anchor_not_found'; end if;
  execute replace(v_def,v_old,v_new);
end;
$migration$;
