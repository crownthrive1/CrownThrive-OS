-- PentaSuite v1.0.2: fail-closed RPC privilege boundary.
-- RLS tables remain private; authenticated operators enter through the JWT-gated Edge control plane.

do $$
declare r record;
begin
  for r in
    select p.oid::regprocedure as signature
    from pg_proc p
    join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='public'
      and (p.proname like 'pentasuite_%' or p.proname like 'pentarfa_%')
  loop
    execute format('revoke all on function %s from PUBLIC, anon, authenticated', r.signature);
    execute format('grant execute on function %s to service_role', r.signature);
  end loop;
end $$;
