begin;

create policy penta_mation_workflows_authenticated_internal_only
  on public.penta_mation_workflows
  for all
  to authenticated
  using (false)
  with check (false);

create policy penta_mation_runs_authenticated_internal_only
  on public.penta_mation_runs
  for all
  to authenticated
  using (false)
  with check (false);

create policy penta_hybrid_decisions_authenticated_internal_only
  on public.penta_hybrid_decisions
  for all
  to authenticated
  using (false)
  with check (false);

create policy penta_alumni_charters_authenticated_internal_only
  on public.penta_alumni_charters
  for all
  to authenticated
  using (false)
  with check (false);

create policy penta_institute_research_authenticated_internal_only
  on public.penta_institute_research
  for all
  to authenticated
  using (false)
  with check (false);

create policy penta_signal_observations_authenticated_internal_only
  on public.penta_signal_observations
  for all
  to authenticated
  using (false)
  with check (false);

create policy penta_assure_certifications_authenticated_internal_only
  on public.penta_assure_certifications
  for all
  to authenticated
  using (false)
  with check (false);

commit;
