create index if not exists penta_marketer_team_registry_primary_agent_idx
  on crm.penta_marketer_team_registry_v1(primary_agent_id);
create index if not exists penta_marketer_team_registry_fallback_agent_idx
  on crm.penta_marketer_team_registry_v1(fallback_agent_id);
create index if not exists penta_marketer_work_queue_persona_idx
  on crm.penta_marketer_work_queue_v1(assigned_persona_id, state, created_at desc);
