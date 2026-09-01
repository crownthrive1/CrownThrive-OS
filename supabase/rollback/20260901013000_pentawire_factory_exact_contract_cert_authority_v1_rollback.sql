-- Finalize rollback of the layered PentaWire exact-contract source-authority hardening.
-- Required order: first apply 20260901011500_pentawire_factory_exact_contract_materialization_v1_rollback.sql,
-- then apply this file. Fail closed if the v1 materializer/wrapper still exists.

do $rollback_guard$
begin
  if to_regprocedure('integration_control.penta_factory_wire_generate_v1(uuid)') is not null
     or to_regprocedure('integration_control.penta_factory_wire_materialize_v1(uuid,jsonb)') is not null then
    raise exception 'apply_20260901011500_feature_rollback_first';
  end if;
end
$rollback_guard$;

drop function if exists integration_control.penta_wire_safe_service_contract_v1(text);
