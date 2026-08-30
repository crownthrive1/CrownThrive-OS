-- Bind every new PentaFabric ledger row to the build SHA inside the signed
-- packet. Existing append-only history is intentionally not rewritten; the
-- NOT VALID constraints apply to new rows immediately and leave legacy rows
-- explicitly unvalidated until a separately governed reconciliation proves
-- their lineage.

begin;

do $pentafabric_build_binding$
begin
  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.pentafabric_events'::regclass
      and conname = 'pentafabric_signed_build_sha_match'
  ) then
    alter table public.pentafabric_events
      add constraint pentafabric_signed_build_sha_match
      check (
        build_sha is not distinct from
        (event #>> '{integrity,build_sha}')
      ) not valid;
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conrelid = 'public.pentafabric_events'::regclass
      and conname = 'pentafabric_signed_build_sha_shape'
  ) then
    alter table public.pentafabric_events
      add constraint pentafabric_signed_build_sha_shape
      check (build_sha is null or build_sha ~ '^[a-f0-9]{40}$')
      not valid;
  end if;
end;
$pentafabric_build_binding$;

comment on constraint pentafabric_signed_build_sha_match
on public.pentafabric_events is
'New ledger rows must copy build_sha exactly from the HMAC-bound event integrity payload. Legacy append-only rows remain unvalidated pending governed reconciliation.';

comment on constraint pentafabric_signed_build_sha_shape
on public.pentafabric_events is
'New non-null PentaFabric signing build identifiers must be canonical lowercase Git SHA-1 values.';

commit;
