-- Evidence-preserving rollback for Locticians native DAIL terminal gate v1.
-- Existing DAIL receipts and binding columns are intentionally preserved.

drop trigger if exists locticians_native_dail_terminal_assert_v1 on crm.locticians_native_action_queue_v1;
drop trigger if exists locticians_native_complete_dail_bind_v1 on crm.locticians_native_action_queue_v1;

drop function if exists crm.locticians_native_dail_terminal_assert_v1();
drop function if exists crm.locticians_native_complete_dail_trigger_v1();
drop function if exists crm.locticians_native_dail_backfill_v1(integer);
drop function if exists crm.locticians_native_bind_dail_action_v1(uuid,text);
drop function if exists crm.locticians_native_dail_status_v1();

-- Do not drop dail_event_id/dail_event_hash/dail_bound_at/dail_evidence_state.
-- Those fields preserve institutional evidence and remain readable after rollback.
