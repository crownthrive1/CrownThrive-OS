-- Guarded rollback for the provider-compatible COS Phase 00 scheduler fence.
-- Rollback is prohibited while the exact COS build-session maintenance event
-- remains active. Once maintenance is closed, restore the exact pre-fence
-- function bodies from the private unfenced clones, then remove the clones.

begin;

do $$
declare
  v_state jsonb;
  v_assign_def text;
  v_reconcile_def text;
begin
  v_state:=chlom_runtime.maintenance_state_v1();
  if coalesce((v_state->>'maintenance_active')::boolean,false)
     and coalesce(v_state->>'event_id','')='ct.maintenance.2026-08-29.cos-v1-interactive-build.v1' then
    raise exception 'rollback_blocked_active_cos_build_session';
  end if;

  select pg_get_functiondef('pentatime.pentacrons_assign_operation_unfenced_v1(text,text,text,text,text)'::regprocedure)
    into v_assign_def;
  select pg_get_functiondef('pentatime.reconcile_collision_domain_slots_unfenced_v1(text)'::regprocedure)
    into v_reconcile_def;

  if v_assign_def is null or v_reconcile_def is null then
    raise exception 'rollback_source_clone_missing';
  end if;

  execute replace(
    v_assign_def,
    'CREATE OR REPLACE FUNCTION pentatime.pentacrons_assign_operation_unfenced_v1',
    'CREATE OR REPLACE FUNCTION pentatime.pentacrons_assign_operation_v1'
  );
  execute replace(
    v_reconcile_def,
    'CREATE OR REPLACE FUNCTION pentatime.reconcile_collision_domain_slots_unfenced_v1',
    'CREATE OR REPLACE FUNCTION pentatime.reconcile_collision_domain_slots_v1'
  );
end
$$;

drop function if exists pentatime.pentacrons_assign_operation_unfenced_v1(text,text,text,text,text);
drop function if exists pentatime.reconcile_collision_domain_slots_unfenced_v1(text);

commit;
