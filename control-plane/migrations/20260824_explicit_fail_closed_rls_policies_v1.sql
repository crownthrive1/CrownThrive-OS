-- CrownThrive THRIVEBASE production-readiness hardening
-- Source-controls the already-applied migration: explicit_fail_closed_rls_policies_v1.
-- Purpose: make implicit RLS deny behavior explicit without widening access.
-- Pre-apply live evidence established that target tables had RLS enabled, zero policies,
-- and no anon/authenticated/PUBLIC table grants. This migration remains fail-closed.

do $$
declare
  r record;
begin
  for r in
    select n.nspname as schema_name, c.relname as table_name
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where c.relkind='r'
      and c.relrowsecurity
      and n.nspname not in ('pg_catalog','information_schema','auth','storage','realtime','extensions','vault')
      and not exists (select 1 from pg_policy p where p.polrelid=c.oid)
    order by n.nspname,c.relname
  loop
    execute format('revoke all privileges on table %I.%I from anon, authenticated', r.schema_name, r.table_name);
    execute format(
      'create policy %I on %I.%I as restrictive for all to anon, authenticated using (false) with check (false)',
      'ct_fail_closed_anon_authenticated_v1',
      r.schema_name,
      r.table_name
    );
  end loop;
end $$;

-- Required post-apply readback:
-- 1. Supabase security advisor has zero rls_enabled_no_policy findings for these objects.
-- 2. No anon/authenticated/PUBLIC access is added.
-- 3. Existing privileged internal/service execution remains separately governed.
