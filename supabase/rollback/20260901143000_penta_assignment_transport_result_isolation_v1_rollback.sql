-- Fail-closed recovery for PentaAssignment transport/result isolation v1.
-- The predecessor behavior can convert transport completion into a semantic owner PASS.
-- That is a known governance defect and must never be restored by rollback. If the forward
-- reconciler must be withdrawn, disable automated owner-result reconciliation until a
-- governed successor is deployed.

create or replace function integration_control.penta_assignment_reconcile_owner_dispatches_v1(
  p_assignment_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control'
as $function$
declare
  v_role text:=coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  a integration_control.penta_assignment_contracts_v1%rowtype;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then
    raise exception 'service_role_required';
  end if;

  select * into a
  from integration_control.penta_assignment_contracts_v1
  where assignment_id=p_assignment_id;
  if not found then raise exception 'assignment_not_found'; end if;

  return jsonb_build_object(
    'assignment_id',a.assignment_id,
    'state','SUCCESS_HOLD',
    'hold_code','HOLD_ASSIGNMENT_OWNER_RECONCILIATION_DISABLED_FAIL_CLOSED',
    'reason','transport completion cannot synthesize semantic owner PASS; automated reconciliation disabled in recovery mode',
    'new_pass_results',0,
    'holds',1,
    'transport_completion_is_not_owner_pass',true,
    'semantic_owner_result_required',true,
    'authority_created',false,
    'authority_expansion',false,
    'observed_at',clock_timestamp()
  );
end
$function$;

revoke all on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid)
  from public,anon,authenticated;
grant execute on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid)
  to service_role;

comment on function integration_control.penta_assignment_reconcile_owner_dispatches_v1(uuid) is
'Fail-closed recovery mode. Automated owner-result reconciliation is disabled; transport completion cannot create semantic PASS.';
