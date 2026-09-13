create or replace function public.chlom_ensure_public_identity(
  p_subject_id text,
  p_display_name text default null,
  p_public_metadata jsonb default '{}'::jsonb
) returns jsonb
language sql
volatile
security definer
set search_path = pg_catalog, chlom_identity
as $$
  select chlom_identity.ensure_public_identity(p_subject_id,p_display_name,p_public_metadata)
$$;

revoke all on function public.chlom_ensure_public_identity(text,text,jsonb) from public, anon, authenticated;
grant execute on function public.chlom_ensure_public_identity(text,text,jsonb) to service_role;