-- COS 1.8 PostgreSQL compatibility repair.
-- PostgreSQL exposes jsonb_object_keys(jsonb), not jsonb_object_length(jsonb).
-- This narrowly scoped immutable helper satisfies the immediately following
-- constitutional-kernel migration without granting end-user access.
begin;

create or replace function public.jsonb_object_length(p_object jsonb)
returns integer
language sql
immutable
strict
parallel safe
set search_path = pg_catalog
as $$
  select count(*)::integer
  from pg_catalog.jsonb_object_keys(p_object);
$$;

comment on function public.jsonb_object_length(jsonb) is
  'Internal COS 1.8 compatibility helper; counts top-level JSONB object keys via pg_catalog.jsonb_object_keys.';

revoke all on function public.jsonb_object_length(jsonb) from public, anon, authenticated;
grant execute on function public.jsonb_object_length(jsonb) to service_role;

commit;
