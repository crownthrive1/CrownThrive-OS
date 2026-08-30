-- COS Phase 00 build-session cron activation fence.
-- While the exact interactive COS maintenance event is active, no pg_cron row
-- may be inserted or reactivated with active=true. Manual/on-demand functions
-- remain available; this fence only blocks scheduled execution authority.

begin;

create or replace function penta_dnd.cos_build_session_cron_activation_fence_v1()
returns trigger
language plpgsql
security definer
set search_path to pg_catalog,chlom_runtime,penta_dnd
as $$
declare
  v_state jsonb;
begin
  v_state := chlom_runtime.maintenance_state_v1();

  if coalesce((v_state->>'maintenance_active')::boolean,false)
     and coalesce(v_state->>'event_id','') = 'ct.maintenance.2026-08-29.cos-v1-interactive-build.v1'
     and coalesce(new.active,false) is true then
    new.active := false;
  end if;

  return new;
end
$$;

revoke all on function penta_dnd.cos_build_session_cron_activation_fence_v1()
from public,anon,authenticated,service_role;

drop trigger if exists cos_build_session_cron_activation_fence_v1 on cron.job;
create trigger cos_build_session_cron_activation_fence_v1
before insert or update of active on cron.job
for each row
execute function penta_dnd.cos_build_session_cron_activation_fence_v1();

commit;
