-- COS Phase 00 build-session scheduler activation fence — provider-compatible.
--
-- Supabase owns cron.job and does not permit CrownThrive to install triggers on it.
-- This migration therefore fences the CrownThrive scheduler materializers that
-- can create/restore pg_cron jobs. It preserves manual/on-demand executors and
-- refuses to patch if the observed runtime function bodies drift before apply.

begin;

do $$
declare
  v_assign_def text;
  v_reconcile_def text;
  v_assign_hash text;
  v_reconcile_hash text;
begin
  select pg_get_functiondef('pentatime.pentacrons_assign_operation_v1(text,text,text,text,text)'::regprocedure)
    into v_assign_def;
  select pg_get_functiondef('pentatime.reconcile_collision_domain_slots_v1(text)'::regprocedure)
    into v_reconcile_def;

  v_assign_hash:=encode(extensions.digest(convert_to(v_assign_def,'UTF8'),'sha256'),'hex');
  v_reconcile_hash:=encode(extensions.digest(convert_to(v_reconcile_def,'UTF8'),'sha256'),'hex');

  if v_assign_hash <> '3a1bec7e76e1f092c3b3d17890d7ffc33d8c401fb375908d4965550d022cf218' then
    raise exception 'pentacrons_assign_operation_v1_runtime_drift:%',v_assign_hash;
  end if;
  if v_reconcile_hash <> 'e1a5d0458df8da996a29719a80a990a34017370bd122161a99d021dab00048cd' then
    raise exception 'reconcile_collision_domain_slots_v1_runtime_drift:%',v_reconcile_hash;
  end if;

  if position('CREATE OR REPLACE FUNCTION pentatime.pentacrons_assign_operation_v1' in v_assign_def)=0 then
    raise exception 'pentacrons_assign_operation_v1_definition_shape_unknown';
  end if;
  if position('CREATE OR REPLACE FUNCTION pentatime.reconcile_collision_domain_slots_v1' in v_reconcile_def)=0 then
    raise exception 'reconcile_collision_domain_slots_v1_definition_shape_unknown';
  end if;

  execute replace(
    v_assign_def,
    'CREATE OR REPLACE FUNCTION pentatime.pentacrons_assign_operation_v1',
    'CREATE OR REPLACE FUNCTION pentatime.pentacrons_assign_operation_unfenced_v1'
  );
  execute replace(
    v_reconcile_def,
    'CREATE OR REPLACE FUNCTION pentatime.reconcile_collision_domain_slots_v1',
    'CREATE OR REPLACE FUNCTION pentatime.reconcile_collision_domain_slots_unfenced_v1'
  );
end
$$;

-- The unfenced implementations are private implementation details. The original
-- function identities remain the only supported service-role entrypoints.
revoke all on function pentatime.pentacrons_assign_operation_unfenced_v1(text,text,text,text,text)
  from public,anon,authenticated,service_role;
revoke all on function pentatime.reconcile_collision_domain_slots_unfenced_v1(text)
  from public,anon,authenticated,service_role;

create or replace function pentatime.pentacrons_assign_operation_v1(
  p_jobname text,
  p_schedule text,
  p_operation_key text,
  p_risk_class text default 'D1',
  p_source_ref text default 'ct.pentacrons.assign-operation.v1'
) returns jsonb
language plpgsql
security definer
set search_path to pg_catalog,pentatime,chlom_runtime,public
as $$
declare
  v_state jsonb;
  v_preflight jsonb;
begin
  v_state:=chlom_runtime.maintenance_state_v1();
  if coalesce((v_state->>'maintenance_active')::boolean,false)
     and coalesce(v_state->>'event_id','')='ct.maintenance.2026-08-29.cos-v1-interactive-build.v1' then
    return jsonb_build_object(
      'state','HOLD_COS_BUILD_SESSION_MAINTENANCE',
      'maintenance_event',v_state->>'event_id',
      'jobname',p_jobname,
      'operation_key',p_operation_key,
      'scheduled_execution_allowed',false,
      'manual_execution_preserved',true,
      'authority_created',false
    );
  end if;

  v_preflight:=public.penta_dnd_preflight_v1(
    'system_quiescence','ct.cos.v1','penta.crons','scheduler.assign.operation',true,false,false
  );
  if coalesce((v_preflight->>'allowed')::boolean,false) is not true then
    return coalesce(v_preflight,'{}'::jsonb)||jsonb_build_object(
      'state','HOLD_DND_SCHEDULER_ASSIGNMENT',
      'jobname',p_jobname,
      'operation_key',p_operation_key,
      'scheduled_execution_allowed',false,
      'manual_execution_preserved',true,
      'authority_created',false
    );
  end if;

  return pentatime.pentacrons_assign_operation_unfenced_v1(
    p_jobname,p_schedule,p_operation_key,p_risk_class,p_source_ref
  );
end
$$;

create or replace function pentatime.reconcile_collision_domain_slots_v1(
  p_domain_key text default 'ct:production-governance-write-lane'
) returns jsonb
language plpgsql
security definer
set search_path to pg_catalog,pentatime,chlom_runtime,public
as $$
declare
  v_state jsonb;
  v_preflight jsonb;
begin
  v_state:=chlom_runtime.maintenance_state_v1();
  if coalesce((v_state->>'maintenance_active')::boolean,false)
     and coalesce(v_state->>'event_id','')='ct.maintenance.2026-08-29.cos-v1-interactive-build.v1' then
    return jsonb_build_object(
      'state','HOLD_COS_BUILD_SESSION_MAINTENANCE',
      'maintenance_event',v_state->>'event_id',
      'domain_key',p_domain_key,
      'scheduled_execution_allowed',false,
      'authority_created',false
    );
  end if;

  v_preflight:=public.penta_dnd_preflight_v1(
    'system_quiescence','ct.cos.v1','penta.time','scheduler.reconcile.collision-domain',true,false,false
  );
  if coalesce((v_preflight->>'allowed')::boolean,false) is not true then
    return coalesce(v_preflight,'{}'::jsonb)||jsonb_build_object(
      'state','HOLD_DND_COLLISION_RECONCILIATION',
      'domain_key',p_domain_key,
      'scheduled_execution_allowed',false,
      'authority_created',false
    );
  end if;

  return pentatime.reconcile_collision_domain_slots_unfenced_v1(p_domain_key);
end
$$;

-- CREATE OR REPLACE preserves the existing original-function ACLs. Reassert the
-- public/client deny boundary without expanding service authority.
revoke all on function pentatime.pentacrons_assign_operation_v1(text,text,text,text,text)
  from public,anon,authenticated;
revoke all on function pentatime.reconcile_collision_domain_slots_v1(text)
  from public,anon,authenticated;

grant execute on function pentatime.pentacrons_assign_operation_v1(text,text,text,text,text) to service_role;
grant execute on function pentatime.reconcile_collision_domain_slots_v1(text) to service_role;

commit;
