-- Fragment 5/5: institutional schedule, pg_cron clock, permissions, and PentaPolice reconcile.
insert into chlom_runtime.agent_schedule_definitions as s(
  schedule_id,suite_id,canonical_name,timezone,ical,timing_mode,skill_name,agent_ids,execution_state,
  external_task_id,source_ref,metadata
) values('ct.schedule.pentafactory.daily-agent-fleet.10x100.v1','ct.agent-suite.pentafactory-daily-fleet.v1',
  'PentaFactory Daily Governed Fleet 10x100','America/New_York',
  E'BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nDTSTART:20260828T040500\nRRULE:FREQ=DAILY\nSUMMARY:PentaFactory Daily Fleet 10x100\nEND:VEVENT\nEND:VCALENDAR',
  'exact_schedule','public.pentafactory_daily_fleet_tick_v1',
  array['ct.agent.factory.orchestrator','ct.agent.factory.independent-verification','ct.agent.penta-police','ct.subagent.d-surrogate.ct-agent-factory-orchestrator'],
  'active','pgcron:pentafactory-daily-agent-fleet-10x100-v1',
  'supabase/migrations/20260828150000_pentafactory_daily_agent_fleet_10x100_v1.sql',
  jsonb_build_object('policy_id','ct.pentafactory.daily-agent-fleet.10x100.v1','cron_utc','5 8 * * *',
    'database_native_clock',true,'external_scheduler_slot_delta',0,'d3_human_reserved',true))
on conflict(schedule_id) do update set suite_id=excluded.suite_id,canonical_name=excluded.canonical_name,
  timezone=excluded.timezone,ical=excluded.ical,timing_mode=excluded.timing_mode,skill_name=excluded.skill_name,
  agent_ids=excluded.agent_ids,execution_state='active',external_task_id=excluded.external_task_id,
  source_ref=excluded.source_ref,metadata=s.metadata||excluded.metadata,updated_at=now();

do $b$ begin
  if exists(select 1 from cron.job where jobname='pentafactory-daily-agent-fleet-10x100-v1') then
    perform cron.unschedule('pentafactory-daily-agent-fleet-10x100-v1'); end if;
  perform cron.schedule('pentafactory-daily-agent-fleet-10x100-v1','5 8 * * *',
    'select public.pentafactory_daily_fleet_tick_v1();');
end $b$;

revoke all on function public.pentafactory_force_nonvoting_membership_v1() from public,anon,authenticated;
revoke all on function public.pentafactory_materialize_daily_entity_v1(date,text,text,text,text,int,int,text,text,text,text,text,text,uuid,timestamptz) from public,anon,authenticated;
revoke all on function public.pentafactory_retire_daily_fleet_v1(date) from public,anon,authenticated;
revoke all on function public.pentafactory_daily_fleet_status_v1(date) from public,anon,authenticated;
revoke all on function public.pentafactory_daily_fleet_tick_v1(date,boolean) from public,anon,authenticated;
grant execute on function public.pentafactory_retire_daily_fleet_v1(date) to service_role;
grant execute on function public.pentafactory_daily_fleet_status_v1(date) to service_role;
grant execute on function public.pentafactory_daily_fleet_tick_v1(date,boolean) to service_role;
select integration_control.penta_police_reconcile_v1();
