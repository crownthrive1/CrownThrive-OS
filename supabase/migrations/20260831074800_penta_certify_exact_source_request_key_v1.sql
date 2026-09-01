-- PentaCertify exact-source request-key hardening.
-- Prevents a certification task for a new exact source head from reusing a factory
-- request created for a superseded source snapshot. This migration creates no
-- D3, provider-write, production-deploy, money-movement, or self-certification authority.

create or replace function integration_control.penta_certify_request_key_v1(
  p_task_kind text,
  p_surface_id text,
  p_source_certification_state text,
  p_software_generation integer,
  p_attempt integer,
  p_source_snapshot jsonb,
  p_read_mode boolean default false
)
returns text
language plpgsql
immutable
security invoker
set search_path to 'pg_catalog'
as $function$
declare
  v_source_fp text;
  v_head_sha text;
  v_key text;
begin
  if nullif(btrim(coalesce(p_task_kind,'')),'') is null then raise exception 'PENTA_CERTIFY_TASK_KIND_REQUIRED'; end if;
  if nullif(btrim(coalesce(p_surface_id,'')),'') is null then raise exception 'PENTA_CERTIFY_SURFACE_ID_REQUIRED'; end if;
  if nullif(btrim(coalesce(p_source_certification_state,'')),'') is null then raise exception 'PENTA_CERTIFY_SOURCE_STATE_REQUIRED'; end if;
  if coalesce(p_attempt,0) < 1 then raise exception 'PENTA_CERTIFY_ATTEMPT_INVALID'; end if;
  if not coalesce(p_read_mode,false) and coalesce(p_software_generation,0) < 1 then raise exception 'PENTA_CERTIFY_GENERATION_INVALID'; end if;

  v_source_fp := encode(extensions.digest(coalesce(p_source_snapshot,'{}'::jsonb)::text,'sha256'),'hex');
  v_head_sha := lower(coalesce(p_source_snapshot->>'head_sha',''));
  if v_head_sha <> '' and v_head_sha !~ '^[0-9a-f]{40}$' then
    raise exception 'PENTA_CERTIFY_SOURCE_HEAD_INVALID';
  end if;

  if coalesce(p_read_mode,false) then
    v_key := 'penta-certify:read:'||p_surface_id||':'||p_source_certification_state||':a'||p_attempt::text;
  else
    v_key := 'penta-build:'||p_task_kind||':'||p_surface_id||':'||p_source_certification_state||':g'||p_software_generation::text||':a'||p_attempt::text;
  end if;

  return v_key||':h'||coalesce(nullif(v_head_sha,''),'nohead')||':s'||v_source_fp;
end
$function$;

revoke all on function integration_control.penta_certify_request_key_v1(text,text,text,integer,integer,jsonb,boolean) from public, anon, authenticated;
grant execute on function integration_control.penta_certify_request_key_v1(text,text,text,integer,integer,jsonb,boolean) to service_role;

create or replace function integration_control.penta_certify_dispatch_v3(p_limit integer default 6)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'integration_control', 'public'
as $function$
declare
 r record; v_project uuid; v_request uuid; v_dispatched int:=0; v_wait int:=0; v_cred jsonb; v_key text; v_req jsonb; v_has_read_binding boolean; v_attempt integer; v_source_fp text;
begin
 select id into v_project from public.ct_factory_projects where project_key='crownthrive-os-v2-factory' and autonomy_enabled=true limit 1;
 if v_project is null then raise exception 'PENTA_FACTORY_PROJECT_UNAVAILABLE'; end if;
 begin v_cred:=integration_control.run_credential_custody_health(); exception when others then v_cred:=jsonb_build_object('state','unavailable','error',sqlerrm); end;

 for r in
   select * from integration_control.penta_certify_tasks_v3
   where state in ('queued','waiting') and available_at<=now() and attempt_count<max_attempts and risk_class<>'D3'
   order by case risk_class when 'D0' then 0 when 'D1' then 1 else 2 end, software_generation desc, created_at
   for update skip locked limit greatest(1,least(coalesce(p_limit,6),16))
 loop
   v_attempt:=r.attempt_count+1;
   v_source_fp:=encode(extensions.digest(coalesce(r.source_snapshot,'{}'::jsonb)::text,'sha256'),'hex');
   update integration_control.penta_certify_tasks_v3 set lease_owner='ct.penta.certify.v3',lease_expires_at=now()+interval '15 minutes',attempt_count=v_attempt,updated_at=now() where task_id=r.task_id;

   if r.task_kind='credential_readiness' then
     if exists(select 1 from integration_control.provider_write_certifications_v3 c where c.service_id=r.provider_system and c.credential_state='verified') then
       update integration_control.penta_certify_tasks_v3 set state='completed',completed_at=now(),lease_owner=null,lease_expires_at=null,evidence=evidence||jsonb_build_object('credential_state','verified','custody_health',v_cred,'verified_at',now()),updated_at=now() where task_id=r.task_id;
       insert into integration_control.penta_certify_receipts_v3(task_id,event_type,state,evidence) values(r.task_id,'penta.credentials.ready','completed',jsonb_build_object('provider_system',r.provider_system,'secret_material_exposed',false));v_dispatched:=v_dispatched+1;
     else
       update integration_control.penta_certify_tasks_v3 set state='waiting',available_at=now()+interval '15 minutes',lease_owner=null,lease_expires_at=null,last_error='credential_verification_not_yet_evidenced',evidence=evidence||jsonb_build_object('custody_health',v_cred,'secret_material_exposed',false,'checked_at',now()),updated_at=now() where task_id=r.task_id;
       insert into integration_control.penta_certify_receipts_v3(task_id,event_type,state,evidence) values(r.task_id,'penta.credentials.waiting','waiting',jsonb_build_object('provider_system',r.provider_system,'reason','credential_verification_not_yet_evidenced'));v_wait:=v_wait+1;
     end if;continue;
   end if;

   if r.task_kind='bind_runtime' then
     if exists(select 1 from public.ct_factory_adapter_certification_queue q where q.surface_id=r.surface_id and q.runtime_adapter_key is not null) then
       update integration_control.penta_certify_tasks_v3 set state='completed',completed_at=now(),lease_owner=null,lease_expires_at=null,evidence=evidence||jsonb_build_object('runtime_binding','present','checked_at',now()),updated_at=now() where task_id=r.task_id;v_dispatched:=v_dispatched+1;
     else update integration_control.penta_certify_tasks_v3 set state='waiting',available_at=now()+interval '10 minutes',lease_owner=null,lease_expires_at=null,last_error='runtime_adapter_binding_missing',updated_at=now() where task_id=r.task_id;v_wait:=v_wait+1;end if;continue;
   end if;

   select exists(select 1 from public.ct_factory_provider_control_bindings b where b.surface_id=r.surface_id and b.enabled and b.read_control_slug is not null) into v_has_read_binding;
   if r.task_kind='certify_read' and v_has_read_binding then
     v_key:=integration_control.penta_certify_request_key_v1(r.task_kind,r.surface_id,r.source_certification_state,r.software_generation,v_attempt,r.source_snapshot,true);
     v_req:=jsonb_build_object('work_type','provider_adapter_certification','surface_id',r.surface_id,'provider_system',r.provider_system,'source_snapshot',r.source_snapshot,'source_snapshot_sha256',v_source_fp,'source_head_sha',r.source_snapshot->>'head_sha','deployment_scope','certification_only','target_surface_ids','[]'::jsonb,'target_types',jsonb_build_array('__penta_certify_none__'),'production_deploy',false,'authority_ceiling','D2','source_task_id',r.task_id,'certification_attempt',v_attempt,'fail_closed',true);
   else
     v_key:=integration_control.penta_certify_request_key_v1(r.task_kind,r.surface_id,r.source_certification_state,r.software_generation,v_attempt,r.source_snapshot,false);
     v_req:=jsonb_build_object('work_type','provider_certification_software','task_kind',r.task_kind,'surface_id',r.surface_id,'provider_system',r.provider_system,'source_snapshot',r.source_snapshot,'source_snapshot_sha256',v_source_fp,'source_head_sha',r.source_snapshot->>'head_sha','software_generation',r.software_generation,'certification_attempt',v_attempt,'compiler_contract','ct-factory-compiler.v5.1','planner_contract','ct.blueprint.plan.v4.1','deployment_scope','certification_only','target_surface_ids','[]'::jsonb,'target_types',jsonb_build_array('__penta_build_none__'),'production_deploy',false,'authority_ceiling',case when r.risk_class='D2' then 'D2' else 'D1' end,'source_task_id',r.task_id,'required_outputs',jsonb_build_array('certification_contract','certification_contract_test','policy_manifest','evidence_context','ci_verification'),'prohibited',jsonb_build_array('universal_delete','arbitrary_admin_mutation','credential_invention','d3_autopromotion','money_movement','arbitrary_source','arbitrary_sql','arbitrary_shell'));
   end if;

   v_request:=null;
   insert into public.ct_factory_build_requests(project_id,request_key,source_type,source_ref,objective,requirements,requested_release_channel,priority,status,governance_class,evidence)
   values(v_project,v_key,'penta_certify',r.surface_id,case when r.task_kind='certify_read' and v_has_read_binding then 'Certify safe provider read capability for '||r.surface_id else 'Build executable bounded certification contract for '||r.surface_id||' / '||r.task_kind end,v_req,'staging',10,'queued',case when r.risk_class='D2' then 'D2' else 'D1' end,jsonb_build_object('penta_certify_task_id',r.task_id,'software_generation',r.software_generation,'certification_attempt',v_attempt,'source_snapshot_sha256',v_source_fp,'source_head_sha',r.source_snapshot->>'head_sha','queued_at',now(),'production_deploy',false,'generation_retry_protocol','v3.1','request_key_contract','ct.penta.certify.request-key.v1'))
   on conflict(request_key) do update set
     requirements=excluded.requirements,
     objective=excluded.objective,
     status=case when public.ct_factory_build_requests.status in ('failed','hold','cancelled') then 'queued' else public.ct_factory_build_requests.status end,
     evidence=public.ct_factory_build_requests.evidence||excluded.evidence,
     updated_at=now()
   where coalesce(public.ct_factory_build_requests.requirements->>'source_snapshot_sha256','')=coalesce(excluded.requirements->>'source_snapshot_sha256','')
   returning id into v_request;
   if v_request is null then raise exception 'PENTA_CERTIFY_REQUEST_KEY_SOURCE_COLLISION'; end if;

   update integration_control.penta_certify_tasks_v3 set state='dispatched',build_request_id=v_request,lease_owner=null,lease_expires_at=null,last_error=null,evidence=evidence||jsonb_build_object('factory_request_id',v_request,'factory_request_key',v_key,'source_snapshot_sha256',v_source_fp,'source_head_sha',r.source_snapshot->>'head_sha','software_generation',r.software_generation,'certification_attempt',v_attempt,'dispatched_at',now(),'compiler_contract','ct-factory-compiler.v5.1','request_key_contract','ct.penta.certify.request-key.v1'),updated_at=now() where task_id=r.task_id;
   insert into integration_control.penta_certify_receipts_v3(task_id,event_type,state,evidence) values(r.task_id,case when r.owner_component_key='penta.build' then 'penta.build.dispatched' else 'penta.certify.dispatched' end,'dispatched',jsonb_build_object('build_request_id',v_request,'request_key',v_key,'source_snapshot_sha256',v_source_fp,'source_head_sha',r.source_snapshot->>'head_sha','software_generation',r.software_generation,'certification_attempt',v_attempt,'production_deploy',false,'compiler_contract','ct-factory-compiler.v5.1','request_key_contract','ct.penta.certify.request-key.v1'));v_dispatched:=v_dispatched+1;
 end loop;
 return jsonb_build_object('service','ct.penta.certify.dispatch.v3','dispatched',v_dispatched,'waiting',v_wait,'penta_build_min_generation',3,'compiler','ct-factory-compiler.v5.1','planner','ct.blueprint.plan.v4.1','attempt_scoped_retries',true,'generation_retry_protocol','v3.1','request_key_contract','ct.penta.certify.request-key.v1','request_key_source_bound',true,'credential_health',v_cred,'at',now());
end
$function$;
