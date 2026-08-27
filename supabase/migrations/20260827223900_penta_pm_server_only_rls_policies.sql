-- Production mirror of the applied ThriveBase PentaPM security migration.
-- Internal PentaPM control-plane tables are server-only; anon/authenticated are explicitly denied.

drop policy if exists penta_pm_milestones_server_only on penta_pm.milestones;
create policy penta_pm_milestones_server_only on penta_pm.milestones for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_pm_projects_server_only on penta_pm.projects;
create policy penta_pm_projects_server_only on penta_pm.projects for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_pm_provider_outbox_server_only on penta_pm.provider_outbox;
create policy penta_pm_provider_outbox_server_only on penta_pm.provider_outbox for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_pm_work_items_server_only on penta_pm.work_items;
create policy penta_pm_work_items_server_only on penta_pm.work_items for all to anon, authenticated using (false) with check (false);
