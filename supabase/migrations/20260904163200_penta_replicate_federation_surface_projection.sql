update integration_control.website_surfaces w
set metadata=coalesce(w.metadata,'{}'::jsonb)||jsonb_build_object(
 'penta_replicate',jsonb_build_object(
   'contract','ct.penta.replicate.v1',
   'runtime','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1',
   'manifest_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=manifest&surface_id='||w.surface_id,
   'bootstrap_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=bootstrap&surface_id='||w.surface_id,
   'mcp_url','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=mcp',
   'dynamic_binding_state','ACTIVE','public_manifest_class','PUBLIC_SAFE',
   'native_bootstrap_state',case
     when exists(select 1 from integration_control.site_update_queue q where q.surface_id=w.surface_id and q.trigger_key='penta-replicate-bootstrap-v1' and q.state='approved') then 'APPROVED_PENDING_CERTIFIED_PROVIDER_SCRIPT_ADAPTER'
     when exists(select 1 from integration_control.site_update_queue q where q.surface_id=w.surface_id and q.trigger_key='penta-replicate-bootstrap-v1' and q.state='planned') then 'PLANNED_PENDING_PROVIDER_SCRIPT_ADAPTER'
     else 'NOT_QUEUED' end,
   'provider_write_direct',false,'read_after_write_required',true,'rollback_required',true,'updated_at',now()),
 'mcp_api_replication_state','PENTAREPLICATE_ACTIVE'),updated_at=now()
where w.environment='production';

insert into public.penta_federation_system_state(system_key,name,version,status,parent_federation,canonical_repo_parent,authority_ceiling,charter,last_verified_at)
values('ct.system.penta-replicate','PentaReplicate','1.0.0','OPERATIONAL_BOUNDED','PentaFabric','crownthrive1/CrownThrive-OS','D2/A2',jsonb_build_object(
 'mission','continuous governed replication of approved MCP/API/public-site integration contracts across CrownThrive surfaces',
 'source_of_truth','integration_control.api_mcp_reconciled_inventory_v1','dynamic_manifest_contract','ct.penta.replicate.manifest.v1',
 'bootstrap_contract','ct.penta.replicate.bootstrap.v1','public_manifest_class','PUBLIC_SAFE','automatic_authority_ceiling','D1',
 'native_provider_write_class','D2','direct_provider_write',false,'provider_credentials_exposed',false,'money_movement',false,
 'read_after_write_required',true,'rollback_required',true,'no_self_approval',true,'fail_closed',true,
 'production_surfaces',35,'active_mesh_bindings',105,'scheduler','ct-penta-replicate-v1'),now())
on conflict(system_key) do update set name=excluded.name,version=excluded.version,status=excluded.status,parent_federation=excluded.parent_federation,
 canonical_repo_parent=excluded.canonical_repo_parent,authority_ceiling=excluded.authority_ceiling,charter=excluded.charter,last_verified_at=now(),updated_at=now();

insert into public.penta_federation_bindings(binding_key,target_type,target_id,role,mode,authority_ceiling,capability_ceiling,binding_state,source_ref,metadata,last_verified_at)
values
 ('penta-replicate:thrivebase','runtime','CrownThrive/ThriveBase','system-of-record-and-reconciliation-source','native','D2/A2',jsonb_build_object('read',true,'write','internal state only','provider_write',false),'verified','ct.system.penta-replicate',jsonb_build_object('project_ref','tzajnzshmtzjenqulehq','tables',jsonb_build_array('penta_replicate_policy_v1','penta_replicate_events_v1','penta_replicate_targets_v1','penta_replicate_manifests_v1','penta_replicate_jobs_v1','penta_replicate_receipts_v1')),now()),
 ('penta-replicate:mcp','mcp','penta-replicate-v1','cross-ecosystem read-only replication discovery','public_read_only','D1/A1',jsonb_build_object('tools',4,'provider_credentials',false,'provider_write',false),'verified','ct.system.penta-replicate',jsonb_build_object('endpoint','https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-replicate-v1?action=mcp','protocol','2025-03-26'),now()),
 ('penta-replicate:sites-mesh','mesh','ct.mcp.crownthrive-sites-mesh','website-surface propagation and native-install planning','bounded','D2/A2',jsonb_build_object('dynamic_binding',true,'native_write','separately certified provider adapter only','read_after_write',true,'rollback',true),'verified','ct.system.penta-replicate',jsonb_build_object('production_surfaces',35,'active_bindings',105,'native_bootstrap_approved_pending_adapter',10,'native_bootstrap_planned_pending_adapter',25),now()),
 ('penta-replicate:canonical-source','repository_package','github:crownthrive1/CrownThrive-OS','canonical source and replay custody','exact_sha_federated','D2/A2',jsonb_build_object('migrations',true,'edge_runtime',true,'mcp_registration',true,'federation_manifest',true),'bound_partial','github:crownthrive1/CrownThrive-OS#PR3242',jsonb_build_object('pr_number',3242,'branch','penta-replicate-v1-20260904','merge_required_for_terminal_verified_state',true),now())
on conflict(binding_key) do update set target_type=excluded.target_type,target_id=excluded.target_id,role=excluded.role,mode=excluded.mode,
 authority_ceiling=excluded.authority_ceiling,capability_ceiling=excluded.capability_ceiling,binding_state=excluded.binding_state,
 source_ref=excluded.source_ref,metadata=excluded.metadata,last_verified_at=now(),updated_at=now();
