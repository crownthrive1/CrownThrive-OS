do $migration$
declare
  v_def text;
  v_old text := $old$    elsif v_unresolved>0 then
$old$;
  v_new text := $new$    elsif v_unresolved>0 and not (v_adapter_kind='SECURE_HTTP' and v_adapter_state='active') then
$new$;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='penta_wire_scan_v1'
    and pg_get_function_identity_arguments(p.oid)='';
  if v_def is null then raise exception 'penta_wire_scan_v1_not_found'; end if;
  if position(v_old in v_def)=0 then raise exception 'secure_completion_precedence_anchor_not_found'; end if;
  execute replace(v_def,v_old,v_new);
end;
$migration$;
