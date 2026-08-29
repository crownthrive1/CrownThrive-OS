-- Penta protocol pgcrypto bootstrap shim.
-- Supabase installs pgcrypto.digest in the `extensions` schema. The base Penta protocol
-- migration originally creates a string-body SQL wrapper whose body is parsed on first
-- execution. This private temporary wrapper closes the inter-migration race before the
-- final function is rebound directly to extensions.digest and this shim is removed.

create or replace function public.digest(p_data bytea, p_type text)
returns bytea
language sql
immutable
strict
security definer
set search_path = pg_catalog, extensions
as $$
  select extensions.digest(p_data,p_type);
$$;

revoke all on function public.digest(bytea,text) from public, anon, authenticated, service_role;
