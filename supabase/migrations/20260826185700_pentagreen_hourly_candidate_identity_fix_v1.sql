do $do$
declare
  v_def text;
  v_old text := 'v_snapshot->>''candidate_type'',nullif(v_snapshot->>''candidate_ref'','''')';
  v_new text := 'v_snapshot->>''candidate_type'',case when v_snapshot->>''candidate_type''=''proprietary_product_candidate'' then nullif(v_snapshot->>''candidate_ref'','''') else null end';
begin
  select pg_get_functiondef('integration_control.run_thriveevergreen_hourly_product_cycle_v1(timestamptz,text,boolean)'::regprocedure)
    into v_def;

  if position(v_old in v_def) = 0 then
    raise exception 'target candidate_ref insert expression not found';
  end if;

  v_def := replace(v_def, v_old, v_new);
  execute v_def;
end
$do$;
