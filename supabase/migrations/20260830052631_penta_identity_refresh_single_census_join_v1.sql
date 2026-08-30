do $migration$
declare
  v_def text;
  v_old constant text := 'left join integration_control.penta_census_entities_v1 e on e.entity_key=c.penta_identity and e.current';
  v_new constant text := $replacement$left join lateral (
      select e.canonical_name, e.entity_kind, e.lifecycle_state, e.attributes
      from integration_control.penta_census_entities_v1 e
      where e.entity_key=c.penta_identity and e.current
      order by case when e.entity_kind in ('penta_identity','penta_candidate') then 0 else 1 end,
               e.last_seen_at desc,
               e.entity_kind
      limit 1
    ) e on true$replacement$;
begin
  v_def := pg_get_functiondef('integration_control.penta_identity_refresh_v1(text)'::regprocedure);
  if strpos(v_def, v_old) = 0 then
    raise exception 'penta_identity_refresh_v1 expected join not found; refusing drifted migration';
  end if;
  execute replace(v_def, v_old, v_new);
end
$migration$;
