-- CrownThrive PentaFabric / DAIL evidence-ledger hardening.
-- The runtime persists through the vaulted Supabase service role. Browser-facing
-- anon and authenticated roles must remain explicitly denied, even if a future
-- grant is added accidentally.

revoke all on table public.pentafabric_events from anon, authenticated;

alter table public.pentafabric_events enable row level security;

drop policy if exists pentafabric_events_deny_public_clients
on public.pentafabric_events;

create policy pentafabric_events_deny_public_clients
on public.pentafabric_events
as restrictive
for all
to anon, authenticated
using (false)
with check (false);

comment on policy pentafabric_events_deny_public_clients
on public.pentafabric_events is
'PentaVault/DAIL evidence ledger is service-role-only. Public and authenticated client access is explicitly denied.';
