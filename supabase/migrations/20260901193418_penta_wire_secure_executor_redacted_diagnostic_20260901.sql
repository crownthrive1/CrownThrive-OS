do $migration$
declare
  v_def text;
  v_old text := $old$'error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(coalesce(sqlerrm,''),'UTF8'),'sha256'),'hex'),
    'provider_write'$old$;
  v_new text := $new$'error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(coalesce(sqlerrm,''),'UTF8'),'sha256'),'hex'),
    'error_detail_redacted',left(case when coalesce(v_secret,'')<>'' then replace(sqlerrm,v_secret,'[REDACTED]') else sqlerrm end,240),
    'provider_write'$new$;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='penta_wire_thrivebase_secure_read_v1'
    and pg_get_function_identity_arguments(p.oid)='p_service_id text, p_operation_key text, p_params jsonb, p_invocation_kind text';
  if v_def is null then raise exception 'secure_executor_not_found'; end if;
  if position(v_old in v_def)=0 then raise exception 'diagnostic_anchor_not_found'; end if;
  execute replace(v_def,v_old,v_new);
end;
$migration$;
