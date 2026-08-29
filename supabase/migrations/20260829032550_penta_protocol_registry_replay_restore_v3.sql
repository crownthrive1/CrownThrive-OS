-- Complete the temporary replay window opened by 20260829032450.
-- No NULL verification timestamps may survive the Penta protocol installation.

update public.penta_system_registry
set last_verified_at = coalesce(last_verified_at, now()),
    updated_at = now()
where last_verified_at is null;

alter table public.penta_system_registry
  alter column last_verified_at set not null;

do $$
begin
  if exists(select 1 from public.penta_system_registry where last_verified_at is null) then
    raise exception 'penta_system_registry_last_verified_at_restore_failed';
  end if;
end $$;
