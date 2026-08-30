-- Guarded rollback for the COS Phase 00 cron activation fence.
-- The fence cannot be removed while the exact COS build-session maintenance
-- event is still active.

begin;

do $$
declare
  v_state jsonb;
begin
  v_state := chlom_runtime.maintenance_state_v1();
  if coalesce((v_state->>'maintenance_active')::boolean,false)
     and coalesce(v_state->>'event_id','') = 'ct.maintenance.2026-08-29.cos-v1-interactive-build.v1' then
    raise exception 'rollback_blocked_active_cos_build_session';
  end if;
end
$$;

drop trigger if exists cos_build_session_cron_activation_fence_v1 on cron.job;
drop function if exists penta_dnd.cos_build_session_cron_activation_fence_v1();

commit;
