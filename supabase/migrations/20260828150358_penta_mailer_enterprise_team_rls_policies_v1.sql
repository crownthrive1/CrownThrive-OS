do $block$
begin
  if not exists(select 1 from pg_policies where schemaname='crm' and tablename='penta_marketer_team_registry_v1' and policyname='penta_marketer_team_registry_service_role_v1') then
    create policy penta_marketer_team_registry_service_role_v1
      on crm.penta_marketer_team_registry_v1
      for all to service_role
      using (true) with check (true);
  end if;
  if not exists(select 1 from pg_policies where schemaname='crm' and tablename='penta_marketer_work_queue_v1' and policyname='penta_marketer_work_queue_service_role_v1') then
    create policy penta_marketer_work_queue_service_role_v1
      on crm.penta_marketer_work_queue_v1
      for all to service_role
      using (true) with check (true);
  end if;
end
$block$;
