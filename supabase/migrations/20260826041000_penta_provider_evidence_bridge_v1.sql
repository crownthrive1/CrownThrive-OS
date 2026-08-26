-- Penta provider evidence bridge v1
-- Promotes already-verified live provider-control receipts into the adapter
-- certification registry. This does not manufacture certification evidence.

create or replace function integration_control.penta_certify_activate_control_evidence_v1()
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','integration_control','public'
as $$
declare v_read int:=0; v_write int:=0; v_readback int:=0; v_rollback int:=0; v_queue jsonb;
begin
  with x as (
    select q.candidate_adapter_key,b.read_state,b.evidence,b.last_checked_at
    from public.ct_factory_adapter_certification_queue q
    join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled
    where q.candidate_adapter_key is not null
  ), u as (
    update integration_control.site_provider_adapters a
       set read_capability_state='pass',
           evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_live_read',x.evidence->'latest_read_certification','penta_certify_live_read_at',x.last_checked_at),
           updated_at=now()
      from x
     where a.adapter_id=x.candidate_adapter_key and x.read_state='pass'
       and coalesce((x.evidence->'latest_read_certification'->>'passed')::boolean,false)=true
       and a.read_capability_state<>'pass'
    returning 1
  ) select count(*) into v_read from u;

  with x as (
    select q.candidate_adapter_key,b.write_state,b.evidence,b.last_checked_at
    from public.ct_factory_adapter_certification_queue q
    join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled
    where q.candidate_adapter_key is not null
  ), u as (
    update integration_control.site_provider_adapters a
       set write_canary_state='pass',
           evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_write_canary',x.evidence,'penta_certify_write_canary_at',x.last_checked_at),
           updated_at=now()
      from x where a.adapter_id=x.candidate_adapter_key and x.write_state='pass' and a.write_canary_state<>'pass'
    returning 1
  ) select count(*) into v_write from u;

  with x as (
    select q.candidate_adapter_key,b.readback_state,b.evidence,b.last_checked_at
    from public.ct_factory_adapter_certification_queue q
    join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled
    where q.candidate_adapter_key is not null
  ), u as (
    update integration_control.site_provider_adapters a
       set read_after_write_state='pass',supports_read_after_write=true,
           evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_readback',x.evidence,'penta_certify_readback_at',x.last_checked_at),updated_at=now()
      from x where a.adapter_id=x.candidate_adapter_key and x.readback_state='pass' and a.read_after_write_state<>'pass'
    returning 1
  ) select count(*) into v_readback from u;

  with x as (
    select q.candidate_adapter_key,b.rollback_state,b.evidence,b.last_checked_at
    from public.ct_factory_adapter_certification_queue q
    join public.ct_factory_provider_control_bindings b on b.surface_id=q.surface_id and b.enabled
    where q.candidate_adapter_key is not null
  ), u as (
    update integration_control.site_provider_adapters a
       set rollback_canary_state='pass',supports_rollback=true,
           evidence=coalesce(a.evidence,'{}'::jsonb)||jsonb_build_object('penta_certify_rollback',x.evidence,'penta_certify_rollback_at',x.last_checked_at),updated_at=now()
      from x where a.adapter_id=x.candidate_adapter_key and x.rollback_state='pass' and a.rollback_canary_state<>'pass'
    returning 1
  ) select count(*) into v_rollback from u;

  v_queue:=public.ct_factory_reconcile_adapter_certifications();
  return jsonb_build_object('service','ct.penta.certify.evidence-bridge.v1','read_promoted',v_read,'write_promoted',v_write,'readback_promoted',v_readback,'rollback_promoted',v_rollback,'queue_reconcile',v_queue,'at',now());
end $$;
revoke all on function integration_control.penta_certify_activate_control_evidence_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_certify_activate_control_evidence_v1() to service_role;

select integration_control.penta_certify_activate_control_evidence_v1();
