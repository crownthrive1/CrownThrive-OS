-- Rollback for PentaHelp independent-gate exact-review node bootstrap v1.
-- Delete only unused nodes introduced by this migration. If a node already has delivery
-- lineage, retire it and preserve the historical address instead of breaking evidence/FKs.

do $rollback$
declare
  r record;
begin
  for r in
    select node_id
      from pentas.nodes_v2
     where metadata->>'introduced_by'='ct.penta.help.independent-gate-review-nodes.v1'
  loop
    if exists(select 1 from pentas.deliveries_v2 d where d.target_node_id=r.node_id) then
      update pentas.nodes_v2
         set lifecycle_state='retired',
             health_state='held',
             endpoint_ref=null,
             metadata=metadata||jsonb_build_object(
               'rollback_state','RETIRED_WITH_PRESERVED_DELIVERY_LINEAGE',
               'rolled_back_at',clock_timestamp()),
             updated_at=clock_timestamp()
       where node_id=r.node_id;
    else
      delete from pentas.nodes_v2 where node_id=r.node_id;
    end if;
  end loop;
end
$rollback$;

drop function if exists public.penta_help_independent_gate_review_preflight_v1(uuid,text);
