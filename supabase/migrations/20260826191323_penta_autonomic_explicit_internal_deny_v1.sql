begin;

do $do$
declare
  t text;
begin
  foreach t in array array[
    'penta_incidents_v1','penta_flags_v1','penta_tags_v1','penta_harvest_events_v1','penta_backup_receipts_v1',
    'penta_restore_receipts_v1','penta_flush_receipts_v1','penta_remediation_actions_v1','penta_reports_v1','penta_redblue_exercises_v1'
  ] loop
    execute format('drop policy if exists %I on public.%I',t||'_authenticated_internal_only',t);
    execute format('create policy %I on public.%I for all to authenticated using (false) with check (false)',t||'_authenticated_internal_only',t);
  end loop;
end
$do$;

commit;
