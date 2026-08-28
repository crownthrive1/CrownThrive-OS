-- Supporting indexes for every new PentaFactory foreign-key access path.
create index if not exists pentafactory_daily_fleet_runs_policy_idx
  on public.pentafactory_daily_fleet_runs_v1(policy_id);

create index if not exists pentafactory_daily_fleet_entities_policy_idx
  on public.pentafactory_daily_fleet_entities_v1(policy_id);

create index if not exists pentafactory_daily_fleet_entities_parent_idx
  on public.pentafactory_daily_fleet_entities_v1(parent_entity_ref)
  where parent_entity_ref is not null;
