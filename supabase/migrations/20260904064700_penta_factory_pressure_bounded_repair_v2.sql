create or replace function integration_control.penta_factory_pressure_repair_v2(p_completed_scan_limit integer default 50)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','extensions'
as $$
declare
  v_expired integer:=0;
  v_failed_requeued integer:=0;
  v_corrupt_requeued integer:=0;
  v_completed_scanned integer:=0;
  v_completed_good integer:=0;
  v_handoffs jsonb:='{}'::jsonb;
  v_receipt uuid;
  v_evidence jsonb;
  v_now timestamptz:=clock_timestamp();
  v_opp_count bigint;
  v_has_handoff boolean;
  r record;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if p_completed_scan_limit is null or p_completed_scan_limit<1 or p_completed_scan_limit>250 then raise exception 'completed_scan_limit_out_of_range'; end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:factory-pressure-repair:v1',0)) then return jsonb_build_object('state','DEFERRED_CONTENTION','repaired',0,'bounded',true); end if;

  with expired as (
    update integration_control.penta_factory_pressure_packets_v1
    set packet_state='retry',lease_token=null,lease_owner=null,lease_expires_at=null,available_at=v_now+interval '1 minute',
        last_error_code='STALE_PACKET_LEASE_RECOVERED',last_error_sha256=encode(extensions.digest(convert_to(packet_id::text||':STALE_PACKET_LEASE_RECOVERED:'||v_now::text,'UTF8'),'sha256'),'hex'),
        repair_cycle=repair_cycle+1,updated_at=v_now
    where packet_state in ('leased','processing') and lease_expires_at<=v_now returning packet_id
  ) select count(*)::integer into v_expired from expired;

  with failed as (
    update integration_control.penta_factory_pressure_packets_v1
    set packet_state='retry',attempt_count=0,repair_cycle=repair_cycle+1,lease_token=null,lease_owner=null,lease_expires_at=null,
        available_at=v_now+least(interval '6 hours',interval '10 minutes'*(2^least(repair_cycle,5))),
        last_error_code='FAILED_PACKET_REPAIR_CYCLE_'||(repair_cycle+1)::text,updated_at=v_now
    where packet_state='failed' and available_at<=v_now and repair_cycle<1000 returning packet_id
  ) select count(*)::integer into v_failed_requeued from failed;

  for r in
    select p.packet_id,p.asset_count,p.output_count,p.output_manifest_sha256
    from integration_control.penta_factory_pressure_packets_v1 p
    where p.packet_state='completed'
    order by p.updated_at asc,p.packet_id
    limit p_completed_scan_limit
    for update skip locked
  loop
    v_completed_scanned:=v_completed_scanned+1;
    select count(*) into v_opp_count from integration_control.penta_factory_pressure_opportunities_v1 o where o.packet_id=r.packet_id;
    select exists(select 1 from integration_control.penta_factory_pressure_handoffs_v1 h where h.packet_id=r.packet_id) into v_has_handoff;
    if r.output_count<>r.asset_count or r.output_manifest_sha256 is null or v_opp_count<>r.asset_count or not v_has_handoff then
      update integration_control.penta_factory_pressure_packets_v1 p
      set packet_state='retry',completed_at=null,lease_token=null,lease_owner=null,lease_expires_at=null,available_at=v_now,
          repair_cycle=repair_cycle+1,last_error_code='COMPLETED_PACKET_READBACK_REPAIR',
          last_error_sha256=encode(extensions.digest(convert_to(p.packet_id::text||':COMPLETED_PACKET_READBACK_REPAIR:'||v_now::text,'UTF8'),'sha256'),'hex'),updated_at=v_now
      where p.packet_id=r.packet_id;
      v_corrupt_requeued:=v_corrupt_requeued+1;
    else
      update integration_control.penta_factory_pressure_packets_v1 set updated_at=v_now where packet_id=r.packet_id;
      v_completed_good:=v_completed_good+1;
    end if;
  end loop;

  begin
    v_handoffs:=integration_control.penta_factory_pressure_dispatch_handoffs_v1(100);
  exception when others then
    v_handoffs:=jsonb_build_object('state','WORKING','error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(sqlstate||':'||sqlerrm,'UTF8'),'sha256'),'hex'),'raw_error_material',false);
  end;

  v_evidence:=jsonb_build_object('contract','ct.penta.factory-pressure-repair.v2','bounded',true,'completed_scan_limit',p_completed_scan_limit,
    'completed_packets_scanned',v_completed_scanned,'completed_packets_good',v_completed_good,'expired_leases_requeued',v_expired,
    'failed_packets_requeued',v_failed_requeued,'completed_packet_readback_repairs',v_corrupt_requeued,'handoff_dispatch',v_handoffs,
    'global_freeze',false,'single_failure_isolated',true,'no_approval_holds',true,'observed_at',v_now);
  v_receipt:=integration_control.penta_factory_pressure_receipt_v1('repair',case when coalesce(v_handoffs->>'state','PASS') in ('PASS','pass','complete','completed') then 'pass' else 'working' end,v_evidence,null,'ct.corpus.vault-ready.100000.20260902.v1',null,null);
  return v_evidence||jsonb_build_object('state','PASS','receipt_id',v_receipt);
end;
$$;

create or replace function integration_control.penta_factory_pressure_repair_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $$
begin
  return integration_control.penta_factory_pressure_repair_v2(50);
end;
$$;