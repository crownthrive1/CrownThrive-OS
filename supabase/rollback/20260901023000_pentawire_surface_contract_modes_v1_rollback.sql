-- Roll back PentaWire surface-contract classification v1.
-- Re-derives binding state through the pre-existing base scan after removing the additive mode layer.

create or replace function integration_control.penta_wire_tick_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare v_scan jsonb; v_probe jsonb; v_close jsonb; v_work jsonb;
begin
 v_scan:=integration_control.penta_wire_scan_v1();
 v_probe:=integration_control.penta_wire_probe_public_v1();
 v_close:=integration_control.penta_wire_close_resolved_gap_work_v1();
 v_work:=integration_control.penta_wire_generate_gap_work_v1(100);
 return jsonb_build_object(
  'state',case when coalesce((v_probe->>'fail')::int,0)>0 then 'hold' else 'pass' end,
  'scan',v_scan,'public_probe',v_probe,'resolved_work_closeout',v_close,'gap_work',v_work,
  'agent_id','ct.agent.penta-wire','fabrics',jsonb_build_array('PentaMesh','PentaFabric','PentaFactory','PentaCertify','PentaStatus','PentaPolice'),
  'external_scheduler_slot_delta',0,'provider_write',false,'money_movement',false,'checkout_activation',false,'d3_human_reserved',true,'at',clock_timestamp());
end
$function$;

revoke all on function integration_control.penta_wire_tick_v1() from public,anon,authenticated;
grant execute on function integration_control.penta_wire_tick_v1() to service_role;

drop function if exists integration_control.penta_wire_reconcile_surface_modes_v1();
drop function if exists integration_control.penta_wire_record_surface_mode_certification_v1(text,text,text,text,text,jsonb,jsonb,text,text,timestamptz);
drop function if exists integration_control.penta_wire_surface_mode_status_v1();

drop trigger if exists penta_wire_surface_mode_certification_immutable_v1
  on integration_control.penta_wire_surface_mode_certifications_v1;
drop function if exists integration_control.penta_wire_surface_mode_certification_immutable_v1();
drop table if exists integration_control.penta_wire_surface_mode_certifications_v1;
drop table if exists integration_control.penta_wire_surface_contract_modes_v1;

-- Re-read the original deterministic scanner so any mode-layer projections are superseded
-- by the pre-change binding rules instead of being left stale.
select integration_control.penta_wire_scan_v1();
