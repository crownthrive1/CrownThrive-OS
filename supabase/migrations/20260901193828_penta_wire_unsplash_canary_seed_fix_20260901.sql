do $migration$
declare
  v_def text;
  v_old text := $old$when 'unsplash_crownthrive_studios' then '{"query":"CrownThrive","per_page":1,"content_filter":"high"}'::jsonb$old$;
  v_new text := $new$when 'unsplash_crownthrive_studios' then '{"query":"nature","per_page":1,"content_filter":"high"}'::jsonb$new$;
begin
  select pg_get_functiondef(p.oid) into v_def
  from pg_proc p
  join pg_namespace n on n.oid=p.pronamespace
  where n.nspname='integration_control'
    and p.proname='penta_wire_secure_due_check_v1'
    and pg_get_function_identity_arguments(p.oid)='p_limit integer, p_force boolean';
  if v_def is null then raise exception 'secure_due_check_not_found'; end if;
  if position(v_old in v_def)=0 then raise exception 'unsplash_canary_anchor_not_found'; end if;
  execute replace(v_def,v_old,v_new);
end;
$migration$;
