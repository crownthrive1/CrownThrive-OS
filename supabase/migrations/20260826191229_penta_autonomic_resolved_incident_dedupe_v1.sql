do $do$
declare
  v_def text;
  v_old text := E'  returning incident_id into v_incident_id;\n\n  insert into public.penta_flags_v1';
  v_new text := E'  returning incident_id into v_incident_id;\n\n  if exists (select 1 from public.penta_incidents_v1 where incident_id=v_incident_id and state=''resolved'') then\n    select report_id into v_report_id\n    from public.penta_reports_v1\n    where incident_id=v_incident_id and report_type=''after_action''\n    order by created_at asc\n    limit 1;\n    return jsonb_build_object(''state'',''resolved'',''incident_id'',v_incident_id,''report_id'',v_report_id,''deduped'',true,''reason'',''INCIDENT_ALREADY_RESOLVED'');\n  end if;\n\n  insert into public.penta_flags_v1';
begin
  select pg_get_functiondef('public.penta_incident_control_tick_v1()'::regprocedure) into v_def;
  if position(v_new in v_def)>0 then
    return;
  end if;
  if position(v_old in v_def)=0 then
    raise exception 'penta_incident_control_tick_v1 patch marker not found';
  end if;
  v_def := replace(v_def,v_old,v_new);
  execute v_def;
end
$do$;
