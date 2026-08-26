-- PentaContext v1 controlled rollback.
-- Production receipts and institutional history are intentionally preserved.

begin;

do $$
begin
  perform cron.unschedule('penta-context-maintenance-v1');
exception when others then null;
end $$;

update public.penta_mation_workflows
set status='disabled', updated_at=now()
where workflow_id='penta.context.maintenance' and version=1;

update public.penta_system_registry
set maturity='rolled_back',
    last_verified_at=now(),
    metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
      'operational_state','ROLLED_BACK',
      'rolled_back_at',now(),
      'rollback_preserves_receipts',true
    ),
    updated_at=now()
where system_key='penta.context';

revoke execute on function public.penta_context_ingest_v1(text,text,text,text,text,text,text[],jsonb,text,numeric,numeric,timestamptz,timestamptz,text) from service_role;
revoke execute on function public.penta_context_query_v1(text,text,integer,integer,text[],text,text) from service_role;
revoke execute on function public.penta_context_health_v1() from service_role;
revoke execute on function public.penta_context_maintenance_v1() from service_role;
revoke all on public.penta_context_sources_v1 from service_role;
revoke all on public.penta_context_records_v1 from service_role;
revoke all on public.penta_context_receipts_v1 from service_role;
revoke all on public.penta_context_status_v1 from service_role;

-- Destructive DROP statements are intentionally omitted from the default
-- rollback. A later governed decommission may remove runtime objects only
-- after consumers are detached and required evidence is archived.

commit;
