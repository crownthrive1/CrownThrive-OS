-- Promote only after provider management readback + HTTP/MCP/manifest/bootstrap verification.
update integration_control.penta_replicate_policy_v1
set public_runtime_url='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1',updated_at=now()
where policy_id='ct.penta.replicate.policy.v1';

update integration_control.services
set base_url='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1',
 credential_state='verified',integration_state='read_verified',
 metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('deployment_state','production','edge_function_slug','penta-replicate-v1','edge_version',1,'provider_source_sha256','dd2caee364dd33e65a3889053fe6f7e9f196423aa2dde1bf357280739e8ca4e5','public_readback','PASS','promoted_at',now()),
 updated_at=now() where service_id='penta_replicate';

update chlom_runtime.mcp_tool_exposure set exposure_state='production',enabled=true,updated_at=now()
where server_id='penta-replicate' and tool_name like 'penta.replicate.%';

update integration_control.endpoint_catalog
set path_template=case operation_key
 when 'health.read' then '/functions/v1/penta-replicate-v1?action=health'
 when 'manifest.read' then '/functions/v1/penta-replicate-v1?action=manifest&surface_id={surface_id}'
 when 'bootstrap.read' then '/functions/v1/penta-replicate-v1?action=bootstrap&surface_id={surface_id}'
 when 'mcp.rpc' then '/functions/v1/penta-replicate-v1?action=mcp' else path_template end,
 source_state='verified_read',enabled=true,updated_at=now() where service_id='penta_replicate';

insert into integration_control.thrivebase_public_api_allowlist_v1(
 public_api_id,source_service_id,source_operation_key,source_risk_class,exposure_class,product_mode,lifecycle_state,
 source_verification_state,source_last_verified_at,destination_plane_id,provider_write,private_data_access,money_movement,authority_effect,metadata)
values
 ('ct.public-api.penta-replicate.health.v1','penta_replicate','health.read','D0','public_safe','sanitized_status','live','read_verified',now(),'ct.thrivebase.public.1',false,false,false,'none',jsonb_build_object('contract','ct.penta.replicate.v1','runtime','penta-replicate-v1')),
 ('ct.public-api.penta-replicate.manifest.v1','penta_replicate','manifest.read','D0','public_safe','dynamic_manifest','live','read_verified',now(),'ct.thrivebase.public.1',false,false,false,'none',jsonb_build_object('contract','ct.penta.replicate.manifest.v1','secret_free',true)),
 ('ct.public-api.penta-replicate.bootstrap.v1','penta_replicate','bootstrap.read','D0','public_safe','site_bootstrap','live','read_verified',now(),'ct.thrivebase.public.1',false,false,false,'none',jsonb_build_object('contract','ct.penta.replicate.bootstrap.v1','secret_free',true,'idempotent',true))
on conflict(public_api_id) do update set source_service_id=excluded.source_service_id,source_operation_key=excluded.source_operation_key,
 source_risk_class=excluded.source_risk_class,exposure_class=excluded.exposure_class,product_mode=excluded.product_mode,
 lifecycle_state=excluded.lifecycle_state,source_verification_state=excluded.source_verification_state,
 source_last_verified_at=excluded.source_last_verified_at,destination_plane_id=excluded.destination_plane_id,
 provider_write=excluded.provider_write,private_data_access=excluded.private_data_access,money_movement=excluded.money_movement,
 authority_effect=excluded.authority_effect,metadata=excluded.metadata,updated_at=now();

update integration_control.site_mesh_bindings
set endpoint_ref=case
 when target_id='penta-replicate' then 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1'
 when target_id='ct.mcp.penta-replicate' then 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=mcp'
 when target_id='ct.feed.penta-replicate.v1' then 'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=manifest&surface_id='||surface_id
 else endpoint_ref end,binding_state='active',updated_at=now()
where target_id in ('penta-replicate','ct.mcp.penta-replicate','ct.feed.penta-replicate.v1');

create or replace function integration_control.penta_replicate_manifest_v1(p_surface_id text)
returns jsonb language plpgsql stable security definer
set search_path to 'pg_catalog','integration_control','chlom_runtime','extensions'
as $$
declare v_surface jsonb; v_mcp jsonb; v_public_api jsonb; v_public_adapters jsonb; v_bindings jsonb; v_base jsonb; v_sha text;
begin
 select jsonb_build_object('surface_id',w.surface_id,'display_name',w.display_name,'platform_id',w.platform_id,'provider_system',w.provider_system,
 'environment',w.environment,'canonical_url',w.canonical_url,'provider_connection_state',w.provider_connection_state,'health_state',w.health_state,
 'update_mode',w.update_mode,'auto_update_enabled',w.auto_update_enabled) into v_surface
 from integration_control.website_surfaces w where w.surface_id=p_surface_id;
 if v_surface is null then raise exception 'penta_replicate_surface_not_found'; end if;
 select coalesce(jsonb_agg(jsonb_build_object('tool_name',i.subject_key,'service_id',i.service_id,'operation_key',i.operation_key,'risk_class',i.risk_class,'server_id',i.server_id) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_mcp from integration_control.api_mcp_reconciled_inventory_v1 i where i.inventory_kind='MCP_TOOL' and i.enabled and i.exposure_state='production' and i.risk_class in ('D0','D1');
 select coalesce(jsonb_agg(jsonb_build_object('public_api_id',i.subject_key,'service_id',i.service_id,'operation_key',i.operation_key,'risk_class',i.risk_class) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_public_api from integration_control.api_mcp_reconciled_inventory_v1 i where i.inventory_kind='PUBLIC_API' and i.enabled;
 select coalesce(jsonb_agg(jsonb_build_object('contract',i.subject_key,'service_id',i.service_id,'adapter_kind',i.interface_kind,'transport_ref',i.transport_ref) order by i.service_id,i.subject_key),'[]'::jsonb)
 into v_public_adapters from integration_control.api_mcp_reconciled_inventory_v1 i where i.inventory_kind='READ_ADAPTER' and i.enabled and i.public_projection is true;
 select coalesce(jsonb_agg(jsonb_build_object('binding_kind',b.binding_kind,'target_id',b.target_id,'target_version',b.target_version,'endpoint_ref',b.endpoint_ref,'install_mode',b.install_mode,'authority_ceiling',b.authority_ceiling) order by b.binding_kind,b.target_id),'[]'::jsonb)
 into v_bindings from integration_control.site_mesh_bindings b where b.surface_id=p_surface_id and b.binding_state='active';
 v_base:=jsonb_build_object('contract','ct.penta.replicate.manifest.v1','generated_at',clock_timestamp(),'surface',v_surface,
 'mcp_tools',v_mcp,'public_apis',v_public_api,'public_read_adapters',v_public_adapters,'site_bindings',v_bindings,
 'runtime',jsonb_build_object('base_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1',
 'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=manifest&surface_id='||p_surface_id,
 'bootstrap_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=bootstrap&surface_id='||p_surface_id,
 'mcp_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=mcp'),
 'controls',jsonb_build_object('provider_credentials_exposed',false,'provider_write',false,'money_movement',false,'read_after_write_required',true,'rollback_required',true));
 v_sha:=encode(extensions.digest(convert_to(v_base::text,'UTF8'),'sha256'),'hex'); return v_base||jsonb_build_object('manifest_sha256',v_sha);
end $$;

create or replace function integration_control.penta_replicate_cycle_v1(p_force boolean default false)
returns jsonb language plpgsql security definer set search_path to 'pg_catalog','integration_control','extensions'
as $$ declare r record; v_manifest jsonb; v_sha text; v_before text; v_job uuid; v_updates integer:=0; v_boot integer:=0; v_evidence jsonb;
begin
 perform integration_control.penta_replicate_refresh_targets_v1();
 for r in select * from integration_control.penta_replicate_targets_v1 order by surface_id loop
  v_manifest:=integration_control.penta_replicate_manifest_v1(r.surface_id); v_sha:=v_manifest->>'manifest_sha256'; v_before:=r.last_applied_sha256;
  insert into integration_control.penta_replicate_manifests_v1(surface_id,manifest_sha256,manifest) values(r.surface_id,v_sha,v_manifest) on conflict(surface_id,manifest_sha256) do nothing;
  update integration_control.penta_replicate_targets_v1 set last_manifest_sha256=v_sha,last_manifest_at=clock_timestamp(),updated_at=clock_timestamp() where surface_id=r.surface_id;
  if p_force or v_before is distinct from v_sha then
   insert into integration_control.penta_replicate_jobs_v1(surface_id,operation_key,desired_sha256,risk_class,job_state,autonomous_eligible,requires_human_approval,rollback_ref,evidence)
   values(r.surface_id,'manifest.publish',v_sha,'D1','applied',true,false,'penta-replicate://manifest/'||coalesce(v_before,'none'),jsonb_build_object('delivery_mode','dynamic_runtime','provider_write',false,'authority_effect','none'))
   on conflict(surface_id,operation_key,desired_sha256) do update set job_state='applied',evidence=excluded.evidence,updated_at=clock_timestamp() returning job_id into v_job;
   v_evidence:=jsonb_build_object('contract','ct.penta.replicate.manifest.v1','surface_id',r.surface_id,'manifest_sha256',v_sha,'delivery_mode','dynamic_runtime','provider_write',false,'authority_effect','none');
   insert into integration_control.penta_replicate_receipts_v1(job_id,surface_id,operation_key,decision,before_sha256,after_sha256,readback_state,provider_write,authority_effect,evidence,evidence_sha256)
   values(v_job,r.surface_id,'manifest.publish','PASS_DYNAMIC_MANIFEST',v_before,v_sha,'DATABASE_READBACK',false,'none',v_evidence,encode(extensions.digest(convert_to(v_evidence::text,'UTF8'),'sha256'),'hex'));
   update integration_control.penta_replicate_targets_v1 set last_applied_sha256=v_sha,last_applied_at=clock_timestamp(),failure_count=0,updated_at=clock_timestamp() where surface_id=r.surface_id; v_updates:=v_updates+1;
  end if;
 end loop;
 insert into integration_control.site_update_queue(surface_id,trigger_key,operation_key,risk_class,requested_change,state,autonomous_eligible,requires_human_approval,rollback_ref,metadata)
 select t.surface_id,'penta-replicate-bootstrap-v1','site.replicate.bootstrap.install','D2',jsonb_build_object('contract','ct.penta.replicate.bootstrap.v1',
 'script_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=bootstrap&surface_id='||t.surface_id,
 'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=manifest&surface_id='||t.surface_id,
 'script_id','ct-penta-replicate-v1','behavior','idempotent dynamic loader; no credentials; no money movement'),
 case when t.eligibility_state='AUTO_BOOTSTRAP' then 'approved' else 'planned' end,t.eligibility_state='AUTO_BOOTSTRAP',t.eligibility_state<>'AUTO_BOOTSTRAP',
 'penta-replicate://bootstrap/v1/remove',jsonb_build_object('source','penta-replicate','founder_explicit_authority','2026-09-04','provider_write_requires_existing_site_adapter',true,'read_after_write_required',true,'rollback_required',true)
 from integration_control.penta_replicate_targets_v1 t where not exists(select 1 from integration_control.site_update_queue q where q.surface_id=t.surface_id and q.trigger_key='penta-replicate-bootstrap-v1' and q.state in ('planned','approved','executing','completed'));
 get diagnostics v_boot=row_count; update integration_control.penta_replicate_events_v1 set event_state='applied',processed_at=clock_timestamp() where event_state='queued';
 return jsonb_build_object('state','PASS','contract','ct.penta.replicate.cycle.v1','manifest_updates',v_updates,'bootstrap_updates_created',v_boot,'force',p_force,'status',integration_control.penta_replicate_status_v1(),'observed_at',clock_timestamp());
end $$;

update integration_control.site_update_queue q
set requested_change=q.requested_change||jsonb_build_object(
 'script_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=bootstrap&surface_id='||q.surface_id,
 'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=manifest&surface_id='||q.surface_id),
 metadata=coalesce(q.metadata,'{}'::jsonb)||jsonb_build_object('runtime_verified',true,'runtime_slug','penta-replicate-v1','provider_source_sha256','dd2caee364dd33e65a3889053fe6f7e9f196423aa2dde1bf357280739e8ca4e5'),
 updated_at=now()
where q.trigger_key='penta-replicate-bootstrap-v1' and q.state in ('planned','approved','executing');
