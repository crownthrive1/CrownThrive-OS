-- Applied to production as migration 20260826230754.
create policy penta_context_sources_explicit_client_deny_v1 on public.penta_context_sources_v1 for all to anon, authenticated using (false) with check (false);
create policy penta_context_records_explicit_client_deny_v1 on public.penta_context_records_v1 for all to anon, authenticated using (false) with check (false);
create policy penta_context_receipts_explicit_client_deny_v1 on public.penta_context_receipts_v1 for all to anon, authenticated using (false) with check (false);

comment on policy penta_context_sources_explicit_client_deny_v1 on public.penta_context_sources_v1 is 'PentaContext is service-role-only; explicit deny removes ambiguous no-policy posture.';
comment on policy penta_context_records_explicit_client_deny_v1 on public.penta_context_records_v1 is 'PentaContext is service-role-only; explicit deny removes ambiguous no-policy posture.';
comment on policy penta_context_receipts_explicit_client_deny_v1 on public.penta_context_receipts_v1 is 'PentaContext is service-role-only; explicit deny removes ambiguous no-policy posture.';
