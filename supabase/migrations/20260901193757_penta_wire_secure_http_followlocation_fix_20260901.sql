do $migration$
declare
  v_def text;
  v_old text := $old$  perform extensions.http_set_curlopt('CURLOPT_FOLLOWLOCATION','0');
$old$;
  v_new text := $new$  -- FOLLOWLOCATION is intentionally not configured: pgsql-http does not expose it at runtime.
$new$;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='penta_wire_thrivebase_secure_read_v1'
    and pg_get_function_identity_arguments(p.oid)='p_service_id text, p_operation_key text, p_params jsonb, p_invocation_kind text';
  if v_def is null then raise exception 'secure_executor_not_found'; end if;
  if position(v_old in v_def)=0 then raise exception 'followlocation_anchor_not_found'; end if;
  execute replace(v_def,v_old,v_new);
end;
$migration$;
