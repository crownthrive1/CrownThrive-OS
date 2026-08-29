-- Resolve Supabase pgcrypto from its installed `extensions` schema.
-- The final protocol hash function explicitly binds to extensions.digest so runtime
-- behavior does not depend on ambient search_path configuration.

create or replace function public.penta_protocol_sha256_v1(p_value jsonb)
returns text
language sql
immutable
set search_path = pg_catalog, public, extensions
as $$
  select encode(
    extensions.digest(
      convert_to(coalesce(p_value, '{}'::jsonb)::text, 'UTF8'),
      'sha256'
    ),
    'hex'
  );
$$;

revoke all on function public.penta_protocol_sha256_v1(jsonb) from public, anon, authenticated;
grant execute on function public.penta_protocol_sha256_v1(jsonb) to service_role;

-- The compatibility shim is needed only across the ordered migration window above.
-- Remove it once the stable hash function is explicitly bound to extensions.digest.
drop function if exists public.digest(bytea,text);
