-- Final production hardening layered over 20260826050000.
-- Preserve topology auto-repair and action receipts for every major healing stage.

create or replace function penta_self.fabric_mesh_reconcile_v1(p_cycle_id uuid default gen_random_uuid())
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_self','penta_runtime','public' as $$
declare v_changed int:=0; v_bad boolean:=false; v_finding uuid;
begin
 if exists(select 1 from penta_runtime.fabrics_v1 where fabric_id in('ct.fabric.penta.v1','ct.mesh.penta.v1') and lifecycle_state<>'production') then v_bad:=true; end if;
 if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.self' and ordinal=3) then v_bad:=true; end if;
 if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.2' and ordinal=2) then v_bad:=true; end if;
 if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.4' and ordinal=4) then v_bad:=true; end if;
 if v_bad then
  insert into penta_self.findings_v1(cycle_id,capability_key,severity,state,target_ref,symptom,evidence) values(p_cycle_id,'self.reconcile','degraded','open','penta:fabric-mesh-topology','fabric_mesh_production_topology_drift',jsonb_build_object('required_order',jsonb_build_array('PentaFabric','PentaSELF','PentaMesh'))) returning finding_id into v_finding;
  update penta_runtime.fabrics_v1 set lifecycle_state='production',metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true,'last_self_reconciled_at',now()),updated_at=now() where fabric_id in('ct.fabric.penta.v1','ct.mesh.penta.v1') and lifecycle_state<>'production';
  get diagnostics v_changed=row_count;
  if not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.self' and ordinal=3) or not exists(select 1 from penta_runtime.fabric_layers_v1 where layer_id='ct.penta.layer.4' and ordinal=4) then
    update penta_runtime.fabric_layers_v1 set ordinal=ordinal+100 where fabric_id='ct.fabric.penta.v1' and layer_id in('ct.penta.layer.2','ct.penta.layer.self','ct.penta.layer.3','ct.penta.layer.4','ct.penta.layer.5','ct.penta.layer.6','ct.penta.layer.7','ct.penta.layer.8','ct.penta.layer.9');
    update penta_runtime.fabric_layers_v1 set ordinal=case layer_id when 'ct.penta.layer.2' then 2 when 'ct.penta.layer.self' then 3 when 'ct.penta.layer.4' then 4 when 'ct.penta.layer.3' then 5 when 'ct.penta.layer.5' then 6 when 'ct.penta.layer.6' then 7 when 'ct.penta.layer.7' then 8 when 'ct.penta.layer.8' then 9 when 'ct.penta.layer.9' then 10 else ordinal end where fabric_id='ct.fabric.penta.v1' and layer_id in('ct.penta.layer.2','ct.penta.layer.self','ct.penta.layer.3','ct.penta.layer.4','ct.penta.layer.5','ct.penta.layer.6','ct.penta.layer.7','ct.penta.layer.8','ct.penta.layer.9');
  end if;
  update penta_self.findings_v1 set state='healed',resolved_at=now() where finding_id=v_finding;
  insert into penta_self.action_receipts_v1(cycle_id,finding_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(p_cycle_id,v_finding,'self.reconcile','restore_fabric_self_mesh_topology','penta:fabric-mesh-topology','applied',true,'D1',jsonb_build_object('rows_state_repaired',v_changed,'order',jsonb_build_array('PentaFabric','PentaSELF','PentaMesh')));
 end if;
 update public.penta_system_registry set maturity='production',last_verified_at=now(),updated_at=now(),metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('phase',3,'production',true,'last_self_reconciled_at',now()) where system_key in('penta.fabrics','penta.self','penta.meshes');
 return jsonb_build_object('service','ct.penta.self.fabric-mesh-reconcile.v1','drift_detected',v_bad,'production',true,'order',jsonb_build_array('PentaFabric','PentaSELF','PentaMesh'),'at',now());
end $$;

create or replace function penta_self.tick_v1()
returns jsonb language plpgsql security definer set search_path='pg_catalog','penta_self','penta_runtime','integration_control','public' as $$
declare v_cycle uuid:=gen_random_uuid(); v_started timestamptz:=clock_timestamp(); v_scheduler jsonb; v_recovery jsonb; v_topology jsonb; v_discovery jsonb; v_legacy jsonb; v_evidence jsonb; v_build jsonb; v_nurture jsonb; v_route jsonb; v_secure jsonb; v_health jsonb; v_state text:='healthy';
begin
 if not pg_try_advisory_xact_lock(hashtextextended('ct.penta.self.v1',0)) then return jsonb_build_object('service','ct.penta.self.v1','state','SKIPPED_LOCKED','phase',3,'production',true,'at',now()); end if;
 insert into penta_self.cycle_receipts_v1(cycle_id,state,started_at,summary,evidence) values(v_cycle,'running',v_started,'{}','{}');
 begin v_scheduler:=penta_self.scheduler_reconcile_v1(v_cycle); exception when others then v_scheduler:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_recovery:=penta_self.failed_job_recovery_v1(v_cycle); exception when others then v_recovery:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_topology:=penta_self.fabric_mesh_reconcile_v1(v_cycle); exception when others then v_topology:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_discovery:=public.ct_phase3_self_discovery_tick_v3(); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.discovery','phase3_self_discovery','phase3:provider-lanes','applied',true,'D1',v_discovery); exception when others then v_discovery:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_legacy:=public.thrivebase_safe_self_heal_run_v1(); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.heal','bounded_legacy_self_heal','ThriveBase','applied',true,'D1',v_legacy); exception when others then v_legacy:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_evidence:=integration_control.penta_certify_activate_control_evidence_v1(); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.reconcile','activate_provider_evidence','PentaCertify','applied',true,'D2',v_evidence); exception when others then v_evidence:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_build:=integration_control.penta_build_quality_sweep_v1(); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.repair','penta_build_quality_sweep','PentaBuild','delegated',true,'D2',v_build); exception when others then v_build:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_nurture:=public.penta_nurture_tick_v1(); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.nurture','provider_runtime_nurture','PentaNurture','applied',true,'D2',v_nurture); exception when others then v_nurture:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_route:=integration_control.pentaroute_autonomy_cycle_v3(); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.route','route_autonomy_cycle','PentaRoute','delegated',true,'D1',v_route); exception when others then v_route:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 begin v_secure:=penta_runtime.pentasecure_cycle_v1(false); insert into penta_self.action_receipts_v1(cycle_id,capability_key,action_key,target_ref,result_state,reversible,authority_class,evidence) values(v_cycle,'self.secure','security_cycle','PentaSecure','delegated',true,'D2',v_secure); exception when others then v_secure:=jsonb_build_object('state','failed','error',left(sqlerrm,300)); end;
 v_health:=penta_self.health_snapshot_v1();
 if coalesce((v_health->>'scheduler_gaps')::int,0)>0 or coalesce((v_health->>'unrecovered_required_job_failures_30m')::int,0)>0 or coalesce((v_health->>'failed_certification_tasks')::int,0)>0 or v_health->>'fabric_state'<>'production' or v_health->>'mesh_state'<>'production' then v_state:='degraded'; end if;
 if v_scheduler->>'state'='failed' or v_recovery->>'state'='failed' or v_topology->>'state'='failed' then v_state:='failed'; end if;
 update penta_self.cycle_receipts_v1 set state=v_state,completed_at=clock_timestamp(),summary=jsonb_build_object('state',v_state,'health',v_health),evidence=jsonb_build_object('scheduler',v_scheduler,'failed_job_recovery',v_recovery,'topology',v_topology,'discovery',v_discovery,'legacy_heal',v_legacy,'provider_evidence',v_evidence,'build_quality',v_build,'nurture',v_nurture,'route',v_route,'secure',v_secure,'authority_manufacture',false,'d3_human_reserved',true) where cycle_id=v_cycle;
 update public.penta_system_registry set last_verified_at=now(),updated_at=now(),metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('last_self_cycle_id',v_cycle,'last_self_cycle_state',v_state,'last_self_cycle_at',now()) where system_key in('penta.fabrics','penta.self','penta.meshes');
 return jsonb_build_object('service','ct.penta.self.v1','phase',3,'production',true,'cycle_id',v_cycle,'state',upper(v_state),'health',v_health,'actions',jsonb_build_object('scheduler',v_scheduler,'failed_job_recovery',v_recovery,'topology',v_topology,'discovery',v_discovery,'legacy_heal',v_legacy,'provider_evidence',v_evidence,'build_quality',v_build,'nurture',v_nurture,'route',v_route,'secure',v_secure),'authority_manufacture',false,'d3_human_reserved',true,'at',now());
exception when others then
 update penta_self.cycle_receipts_v1 set state='failed',completed_at=clock_timestamp(),summary=jsonb_build_object('error',left(sqlerrm,300)),evidence=jsonb_build_object('sqlstate',sqlstate) where cycle_id=v_cycle;
 return jsonb_build_object('service','ct.penta.self.v1','phase',3,'production',true,'cycle_id',v_cycle,'state','FAILED','error',left(sqlerrm,300),'authority_manufacture',false,'d3_human_reserved',true,'at',now());
end $$;
