-- PentaSuper full acceptance matrix v3.2 repair.
-- Root cause: the synthetic collision stale-owner test attempted to move expires_at
-- before acquired_at, correctly triggering the lease chronology constraint.
-- Preserve the constraint; age the synthetic lease chronology instead.

do $penta_super_acceptance_expiry_fix$
declare
  v_def text;
  v_fixed text;
  v_needle text := 'update institutional_federation.collision_domain_leases_v2 set expires_at=clock_timestamp()-interval ''1 second'',updated_at=clock_timestamp() where lease_id=(v_exp_la->>''lease_id'')::uuid;';
  v_replacement text := 'update institutional_federation.collision_domain_leases_v2 set acquired_at=clock_timestamp()-interval ''10 minutes'',renewed_at=clock_timestamp()-interval ''10 minutes'',expires_at=clock_timestamp()-interval ''1 second'',updated_at=clock_timestamp() where lease_id=(v_exp_la->>''lease_id'')::uuid;';
  v_occurrences integer;
begin
  select pg_get_functiondef('penta_task_runtime.run_full_acceptance_matrix_v3(text)'::regprocedure) into v_def;
  v_occurrences := (length(v_def)-length(replace(v_def,v_needle,'')))/length(v_needle);
  if v_occurrences <> 1 then
    raise exception 'unexpected_collision_expiry_literal_count:%',v_occurrences;
  end if;
  v_fixed := replace(v_def,v_needle,v_replacement);
  execute v_fixed;
end
$penta_super_acceptance_expiry_fix$;

select chlom_runtime.append_dail_event(
  'penta.super.full-acceptance-matrix.v3_2.fixed',
  'penta_super_runtime',
  'ct.penta.task-runtime-family.v1',
  jsonb_build_object(
    'root_cause','synthetic lease expiry violated expires_at_gt_acquired_at chronology constraint',
    'fix','age synthetic acquired_at and renewed_at before setting synthetic expires_at in the past',
    'lease_chronology_constraint_weakened',false,
    'production_certified',false,
    'independent_certification_required',true,
    'three_dail_logical_phase','DAIL-EXECUTION',
    'source_pr',1388
  ),
  'ct.automation.penta-super-build',null,'PentaSuper','1.0.4',
  'ctcorr:penta-super:full-matrix-v3-2-fix',null,'D2',null,'internal'
);
