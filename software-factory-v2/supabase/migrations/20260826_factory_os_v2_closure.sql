-- CrownThrive Autonomous Software Factory v2 runtime closure

create or replace function os_v2.seed_tick_tasks()
returns jsonb
language plpgsql
security definer
set search_path to 'os_v2','pg_catalog'
as $$
declare
  v_now timestamptz:=clock_timestamp();
  v_min integer:=extract(minute from v_now)::integer;
  v_bucket text:=to_char(date_trunc('minute',v_now),'YYYYMMDDHH24MI');
  v_count integer:=0;
begin
  perform os_v2.enqueue_task('self_repair','osv2:self_repair:'||v_bucket,'{}','D1',95,3); v_count:=v_count+1;
  perform os_v2.enqueue_task('factory_tick','osv2:factory_tick:'||v_bucket,'{}','D1',92,3); v_count:=v_count+1;
  if mod(v_min,2)=0 then perform os_v2.enqueue_task('notification_flush','osv2:notification_flush:'||v_bucket,'{}','D0',100,5); v_count:=v_count+1; end if;
  if mod(v_min,5)=0 then perform os_v2.enqueue_task('system_health','osv2:system_health:'||v_bucket,'{}','D0',90,5); v_count:=v_count+1; end if;
  if mod(v_min,10)=0 then perform os_v2.enqueue_task('knowledge_projection','osv2:knowledge_projection:'||v_bucket,'{}','D0',65,5); v_count:=v_count+1; end if;
  if mod(v_min,15)=0 then perform os_v2.enqueue_task('commerce_mesh','osv2:commerce_mesh:'||v_bucket,'{}','D1',70,3); v_count:=v_count+1; end if;
  if mod(v_min,30)=0 then perform os_v2.enqueue_task('scheduler_reconcile','osv2:scheduler_reconcile:'||v_bucket,'{}','D1',85,3); v_count:=v_count+1; end if;
  return jsonb_build_object('state','seeded','candidate_count',v_count,'bucket',v_bucket,'factory_tick',true);
end $$;

create or replace function public.ct_factory_reconcile_run(p_run_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $$
declare
  v_total integer; v_passed integer; v_failed integer; v_hold integer;
  v_pkg_impl integer; v_dep_impl integer; v_status text;
begin
  select count(*), count(*) filter(where status in ('passed','skipped')), count(*) filter(where status='failed'), count(*) filter(where status='hold')
    into v_total,v_passed,v_failed,v_hold
  from public.ct_factory_work_units where build_run_id=p_run_id;
  select count(*) into v_pkg_impl from public.ct_factory_release_packages where build_run_id=p_run_id and channel='production' and status='implemented';
  select count(*) into v_dep_impl from public.ct_factory_deployments where build_run_id=p_run_id and state='implemented';
  if v_failed>0 then v_status:='failed';
  elsif v_hold>0 then v_status:='hold';
  elsif v_total>0 and v_total=v_passed and v_pkg_impl=1 and v_dep_impl>0 then v_status:='implemented';
  elsif exists(select 1 from public.ct_factory_work_units where build_run_id=p_run_id and lane='deploy' and status in ('ready','running','leased')) then v_status:='deploying';
  elsif exists(select 1 from public.ct_factory_work_units where build_run_id=p_run_id and lane='package' and status in ('ready','running','leased')) then v_status:='packaging';
  elsif exists(select 1 from public.ct_factory_work_units where build_run_id=p_run_id and lane='test' and status in ('ready','running','leased')) then v_status:='testing';
  else v_status:='building'; end if;
  update public.ct_factory_build_runs set status=v_status, completed_at=case when v_status in ('implemented','failed','hold') then coalesce(completed_at,now()) else null end where id=p_run_id;
  insert into public.ct_factory_events(event_type,entity_type,entity_id,payload)
  values('factory.run.reconciled','build_run',p_run_id,jsonb_build_object('status',v_status,'total',v_total,'passed',v_passed,'failed',v_failed,'hold',v_hold,'production_packages_implemented',v_pkg_impl,'deployments_implemented',v_dep_impl));
  return jsonb_build_object('run_id',p_run_id,'status',v_status,'total',v_total,'passed',v_passed,'failed',v_failed,'hold',v_hold,'production_packages_implemented',v_pkg_impl,'deployments_implemented',v_dep_impl);
end $$;

create or replace function public.ct_factory_complete_work(p_work_unit_id uuid, p_status text, p_output jsonb default '{}'::jsonb)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $$
declare v_run uuid; v_lane text; v_remaining integer; v_failed integer; v_reconcile jsonb;
begin
  if p_status not in ('passed','failed','hold','skipped') then raise exception 'invalid terminal status'; end if;
  update public.ct_factory_work_units set status=p_status,output=coalesce(p_output,'{}'::jsonb),completed_at=now(),lease_until=null
   where id=p_work_unit_id returning build_run_id,lane into v_run,v_lane;
  if v_run is null then raise exception 'work unit not found'; end if;
  insert into public.ct_factory_events(event_type,entity_type,entity_id,payload)
  values('factory.work.completed','work_unit',p_work_unit_id,jsonb_build_object('status',p_status,'lane',v_lane,'output',coalesce(p_output,'{}'::jsonb)));
  perform public.ct_factory_tick();
  select count(*) filter(where status not in ('passed','skipped')), count(*) filter(where status in ('failed','hold'))
    into v_remaining,v_failed from public.ct_factory_work_units where build_run_id=v_run;
  v_reconcile:=public.ct_factory_reconcile_run(v_run);
  return jsonb_build_object('run_id',v_run,'lane',v_lane,'status',p_status,'remaining',v_remaining,'reconcile',v_reconcile);
end $$;