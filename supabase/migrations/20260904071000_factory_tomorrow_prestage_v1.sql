create table if not exists integration_control.penta_factory_tomorrow_prestage_receipts_v1(
  run_id uuid primary key default gen_random_uuid(),
  target_date date not null,
  local_hour smallint not null,
  run_state text not null,
  daily_fleet jsonb not null default '{}'::jsonb,
  digital_products jsonb not null default '{}'::jsonb,
  pressure_queue jsonb not null default '{}'::jsonb,
  blocker_codes text[] not null default '{}'::text[],
  evidence_sha256 text not null,
  observed_at timestamptz not null default clock_timestamp()
);
create index if not exists penta_factory_tomorrow_prestage_target_idx
  on integration_control.penta_factory_tomorrow_prestage_receipts_v1(target_date,observed_at desc);

create or replace function public.penta_factory_tomorrow_prestage_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control','extensions'
as $$
declare
  v_now timestamptz:=clock_timestamp();
  v_hour integer:=extract(hour from clock_timestamp() at time zone 'America/New_York');
  v_target date:=(clock_timestamp() at time zone 'America/New_York')::date+1;
  v_daily jsonb:='{}'::jsonb;
  v_digital jsonb:='{}'::jsonb;
  v_pressure jsonb:='{}'::jsonb;
  v_blockers text[]:='{}'::text[];
  v_state text:='PASS';
  v_sha text;
  v_run uuid:=gen_random_uuid();
  v_dail_busy boolean:=false;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if v_hour>=8 and v_hour<18 then
    return jsonb_build_object('state','NOT_CLOSED_WINDOW','target_date',v_target,'local_hour',v_hour,'mutation',false,'observed_at',v_now);
  end if;
  if not pg_try_advisory_xact_lock(hashtextextended('ct:penta:factory-tomorrow-prestage:v1:'||v_target::text,0)) then
    return jsonb_build_object('state','DEFERRED_CONTENTION','target_date',v_target,'mutation',false,'observed_at',v_now);
  end if;

  begin
    v_digital:=public.locticians_digital_product_schedule_batch_v1(v_target,10);
  exception when others then
    v_digital:=jsonb_build_object('ok',false,'state','WORKING','error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(sqlstate||':'||sqlerrm,'UTF8'),'sha256'),'hex'));
    v_blockers:=array_append(v_blockers,'HOLD_TOMORROW_DIGITAL_BATCH');
    v_state:='WORKING';
  end;

  select exists(
    select 1 from pg_stat_activity a
    where a.datname=current_database() and a.pid<>pg_backend_pid()
      and (a.query ilike '%chlom_runtime.append_dail_event%' or (a.wait_event_type='Lock' and a.query ilike '%dail%'))
  ) into v_dail_busy;

  v_daily:=public.pentafactory_daily_fleet_status_v1(v_target);
  if coalesce(v_daily->>'state','hold') not in ('pass','ready','production_ready','active') then
    if v_dail_busy then
      v_daily:=v_daily||jsonb_build_object('prestage_state','DEFERRED_DAIL_CONTENTION','prestage_attempted',false);
      v_blockers:=array_append(v_blockers,'HOLD_DAIL_GLOBAL_LOCK_CONTENTION');
      v_state:='WORKING';
    else
      begin
        v_daily:=public.pentafactory_daily_fleet_tick_v1(v_target,false);
      exception when others then
        v_daily:=jsonb_build_object('ok',false,'state','WORKING','error_code',sqlstate,'error_sha256',encode(extensions.digest(convert_to(sqlstate||':'||sqlerrm,'UTF8'),'sha256'),'hex'),'raw_error_material',false);
        v_blockers:=array_append(v_blockers,'HOLD_TOMORROW_DAILY_FLEET_PRESTAGE');
        v_state:='WORKING';
      end;
    end if;
  end if;

  select jsonb_build_object(
    'queued_packets',count(*) filter(where packet_state='queued'),
    'retry_packets',count(*) filter(where packet_state='retry'),
    'queued_assets',coalesce(sum(asset_count) filter(where packet_state='queued'),0),
    'retry_assets',coalesce(sum(asset_count) filter(where packet_state='retry'),0),
    'leased_or_processing',count(*) filter(where packet_state in ('leased','processing')),
    'global_freeze',false
  ) into v_pressure
  from integration_control.penta_factory_pressure_packets_v1;

  v_sha:=encode(extensions.digest(convert_to(jsonb_build_object('target_date',v_target,'daily_fleet',v_daily,'digital_products',v_digital,'pressure_queue',v_pressure,'blocker_codes',v_blockers,'observed_at',v_now)::text,'UTF8'),'sha256'),'hex');
  insert into integration_control.penta_factory_tomorrow_prestage_receipts_v1(run_id,target_date,local_hour,run_state,daily_fleet,digital_products,pressure_queue,blocker_codes,evidence_sha256,observed_at)
  values(v_run,v_target,v_hour,v_state,v_daily,v_digital,v_pressure,v_blockers,v_sha,v_now);
  return jsonb_build_object('state',v_state,'run_id',v_run,'target_date',v_target,'local_hour',v_hour,'daily_fleet',v_daily,'digital_products',v_digital,'pressure_queue',v_pressure,'blocker_codes',v_blockers,'evidence_sha256',v_sha,'observed_at',v_now);
end;
$$;

select cron.schedule('ct-penta-factory-tomorrow-prestage-v1','43 * * * *','select public.penta_factory_tomorrow_prestage_v1();')
where not exists(select 1 from cron.job where jobname='ct-penta-factory-tomorrow-prestage-v1');