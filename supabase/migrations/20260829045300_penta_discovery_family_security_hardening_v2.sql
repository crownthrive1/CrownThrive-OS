do $hardening$
declare
  v_target text;
  v_schema text;
  v_table text;
  v_targets text[] := array[
    'chlom_runtime.penta_route_economic_bindings_v2',
    'penta_discovery.entities_v1',
    'penta_discovery.family_registry_v1',
    'penta_discovery.handoffs_v1',
    'penta_discovery.observations_v1',
    'penta_runtime.penta_discovery_certifications_v1',
    'penta_runtime.penta_discovery_certifications_v2',
    'penta_runtime.penta_discovery_runtime_receipts_v2',
    'penta_runtime.penta_packet_economic_bindings_v2',
    'penta_runtime.penta_pay_route_compensation_policy_v1',
    'penta_runtime.penta_route_abuse_state_v1',
    'penta_runtime.penta_route_anti_abuse_policy_v2',
    'penta_runtime.penta_route_duplicate_receipts_v2',
    'penta_runtime.penta_route_dynamic_signals_v2',
    'penta_runtime.penta_route_governance_reconciliations_v1',
    'penta_runtime.penta_route_pay_bridge_config_v2',
    'penta_runtime.penta_route_pay_obligations_v1',
    'penta_runtime.penta_route_quotes_v1',
    'penta_runtime.penta_route_rate_policy_v1',
    'penta_runtime.penta_route_receipts_v1',
    'penta_runtime.penta_route_reservations_v1',
    'penta_runtime.penta_route_usage_corrections_v2',
    'penta_runtime.penta_route_usage_events_v1',
    'penta_runtime.penta_route_work_cost_links_v1',
    'public.penta_discovery_cases_v1',
    'public.penta_protocol_cookie_mutations_v1',
    'public.penta_protocol_cookies_v1',
    'public.penta_protocol_registry_v1',
    'public.pentas_packet_deliveries_v1',
    'public.pentas_packet_receipts_v1',
    'public.pentas_packets_v1'
  ];
begin
  foreach v_target in array v_targets loop
    v_schema := split_part(v_target, '.', 1);
    v_table := split_part(v_target, '.', 2);

    if to_regclass(format('%I.%I', v_schema, v_table)) is null then
      raise exception 'PENTA_DISCOVERY_SECURITY_TARGET_MISSING: %', v_target;
    end if;

    execute format('alter table %I.%I enable row level security', v_schema, v_table);
    execute format('revoke all on table %I.%I from public, anon, authenticated', v_schema, v_table);
    execute format('drop policy if exists server_only_deny_all_v2 on %I.%I', v_schema, v_table);
    execute format(
      'create policy server_only_deny_all_v2 on %I.%I as restrictive for all to public using (false) with check (false)',
      v_schema,
      v_table
    );
  end loop;
end
$hardening$;

revoke all on function chlom_runtime.reject_penta_route_economic_binding_mutation_v2() from public, anon, authenticated;
revoke all on function penta_runtime.penta_packet_work_cost_projection_trigger_v2() from public, anon, authenticated;
revoke all on function penta_runtime.pentas_delivery_economic_event_v2() from public, anon, authenticated;
revoke all on function penta_runtime.pentas_economic_after_transition_v2() from public, anon, authenticated;
revoke all on function penta_runtime.pentas_economic_before_transition_v2() from public, anon, authenticated;

comment on function chlom_runtime.reject_penta_route_economic_binding_mutation_v2() is
'Trigger-only append/immutability guard. Direct API execution is prohibited.';
comment on function penta_runtime.penta_packet_work_cost_projection_trigger_v2() is
'Trigger-only work-cost projection routine. Direct API execution is prohibited.';
comment on function penta_runtime.pentas_delivery_economic_event_v2() is
'Trigger-only delivery economics routine. Direct API execution is prohibited.';
comment on function penta_runtime.pentas_economic_after_transition_v2() is
'Trigger-only post-transition economics routine. Direct API execution is prohibited.';
comment on function penta_runtime.pentas_economic_before_transition_v2() is
'Trigger-only pre-transition economics routine. Direct API execution is prohibited.';
