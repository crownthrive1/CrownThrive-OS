-- Factory v4 provider reconciliation and autonomous surface-binding refresh.

insert into public.ct_factory_provider_adapters(adapter_key,provider,mode,function_slug,enabled,read_after_write_required,rollback_required,configuration,verification_state,updated_at)
values
('ct.adapter.sites.surface.v2','Sites','dynamic_feed','ct-factory-sites-surface-adapter',true,true,true,'{"scope":"single_surface","provider_native_write":false,"transport":"governed dynamic feed"}'::jsonb,'verified',now()),
('ct.adapter.external.surface.v1','External Surface','fail_closed_unbound','ct-factory-external-surface-adapter',true,false,false,'{"scope":"registry_binding","mutation":"fail_closed_until_provider_certified"}'::jsonb,'blocked',now())
on conflict(adapter_key) do update set provider=excluded.provider,mode=excluded.mode,function_slug=excluded.function_slug,enabled=excluded.enabled,read_after_write_required=excluded.read_after_write_required,rollback_required=excluded.rollback_required,configuration=excluded.configuration,verification_state=excluded.verification_state,updated_at=now();

create or replace function public.ct_factory_provider_job_implemented(p_job_id uuid,p_response jsonb,p_readback jsonb,p_rollback_ref text)
returns jsonb language plpgsql security definer set search_path='public' as $$
declare v_run uuid;v_target uuid;v_assurance uuid;
begin
 update public.ct_factory_provider_jobs set state='implemented',response=coalesce(p_response,'{}'::jsonb),readback=coalesce(p_readback,'{}'::jsonb),rollback_ref=p_rollback_ref,completed_at=now(),updated_at=now(),last_error=null where id=p_job_id returning build_run_id,target_id into v_run,v_target;
 if v_run is null then raise exception 'provider job not found';end if;
 if v_target is not null then
   insert into public.ct_factory_deployments(build_run_id,target_id,state,evidence) values(v_run,v_target,'implemented',jsonb_build_object('provider_job_id',p_job_id,'response',coalesce(p_response,'{}'::jsonb),'readback',coalesce(p_readback,'{}'::jsonb),'rollback_ref',p_rollback_ref,'implemented_at',now()))
   on conflict(build_run_id,target_id) do update set state='implemented',evidence=excluded.evidence,updated_at=now();
 end if;
 select id into v_assurance from public.ct_factory_work_units where build_run_id=v_run and lane='assurance' limit 1;
 if v_assurance is not null and public.ct_factory_required_deployments_satisfied(v_run)
    and not exists(select 1 from public.ct_factory_provider_jobs where build_run_id=v_run and state not in ('implemented','rolled_back')) then
   update public.ct_factory_work_units set status='ready',completed_at=null,output='{}'::jsonb where id=v_assurance and status in ('hold','failed','queued');
   update public.ct_factory_build_runs set status='deploying',completed_at=null where id=v_run;
   perform public.ct_factory_tick();
 end if;
 return jsonb_build_object('job_id',p_job_id,'build_run_id',v_run,'target_id',v_target,'state','implemented','required_deployments_satisfied',public.ct_factory_required_deployments_satisfied(v_run));
end;$$;

-- The installed production cron is idempotently reconciled by deployment automation:
-- job name: ct-factory-surface-binding-sync-v4
-- schedule: */15 * * * *
-- command: select public.ct_factory_sync_surface_bindings('crownthrive-os-v2-factory');
