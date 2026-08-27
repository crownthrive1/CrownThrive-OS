-- Production mirror of the applied ThriveBase migration.
-- Penta runtime control-plane tables are server-only; anon/authenticated are explicitly denied.

drop policy if exists penta_runtime_bindings_server_only on public.penta_runtime_bindings;
create policy penta_runtime_bindings_server_only on public.penta_runtime_bindings for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_runtime_routes_server_only on public.penta_runtime_routes;
create policy penta_runtime_routes_server_only on public.penta_runtime_routes for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_runtime_skills_server_only on public.penta_runtime_skills;
create policy penta_runtime_skills_server_only on public.penta_runtime_skills for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_runtime_activations_server_only on public.penta_runtime_activations;
create policy penta_runtime_activations_server_only on public.penta_runtime_activations for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_pm_provider_receipts_server_only on penta_runtime.penta_pm_github_provider_receipts;
create policy penta_pm_provider_receipts_server_only on penta_runtime.penta_pm_github_provider_receipts for all to anon, authenticated using (false) with check (false);

drop policy if exists penta_pm_provider_certifications_server_only on penta_runtime.penta_pm_provider_certifications;
create policy penta_pm_provider_certifications_server_only on penta_runtime.penta_pm_provider_certifications for all to anon, authenticated using (false) with check (false);
