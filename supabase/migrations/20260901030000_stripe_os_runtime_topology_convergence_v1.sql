create table if not exists integration_control.stripe_live_secret_lanes_v1 (
  lane_key text primary key,
  custody_role text not null check (custody_role in ('HOT','WARM','COLD','EMERGENCY','INTERNAL_ONLY')),
  priority integer not null,
  vault_alias text not null,
  authority_scope text not null,
  enabled boolean not null default true,
  platform_failover_eligible boolean not null default false,
  independent_material boolean not null default true,
  verification_state text not null default 'pending',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into integration_control.stripe_live_secret_lanes_v1(lane_key,custody_role,priority,vault_alias,authority_scope,enabled,platform_failover_eligible,independent_material,verification_state,metadata)
values
('cold_crown_affiliates','HOT',10,'crown_affiliates_stripe_live_secret_key','crownthrive_platform',true,true,true,'provider_live_verified_shared_account','{"provider_http_status":200,"account_identity_probe_required":true}'::jsonb),
('hot_primary','WARM',20,'stripe_server_api_key','crownthrive_platform',true,true,true,'canonical_binding_warm_standby','{"auto_rotate":false,"auto_delete":false,"silent_replace":false}'::jsonb),
('hot_recovery_alias','WARM',21,'stripe_server_api_key_recovery','crownthrive_platform',true,false,false,'same_material_recovery_alias','{"same_material":true,"independent_fallback":false}'::jsonb),
('warm_platform','COLD',30,'stripe_connect_live_secret_key_v1','crownthrive_platform',true,true,true,'provider_readback_verified_cold_standby','{"provider_account_probe_required":true}'::jsonb),
('secondary_connect_oauth','COLD',35,'stripe_connect_acct_1plvdlaffd6y22c1_access_token_v1','acct_1PlvdLAfFd6y22C1',true,true,true,'provider_live_verified_secondary_account','{"token_class":"connect_oauth_access_token","provider_http_status":200,"verified_account_ref":"acct_1PlvdLAfFd6y22C1","historical_hold_preserved":true}'::jsonb),
('emergency_setup','EMERGENCY',40,'stripe_setup_secret','crownthrive_platform',true,false,true,'pending_provider_same_account_verification','{"auto_promote":false}'::jsonb),
('internal_sync_worker','INTERNAL_ONLY',90,'stripe_sync_worker_secret','internal_worker_only',true,false,false,'excluded_from_provider_api_authority','{"provider_api_authority":false}'::jsonb)
on conflict(lane_key) do update set custody_role=excluded.custody_role,priority=excluded.priority,vault_alias=excluded.vault_alias,authority_scope=excluded.authority_scope,enabled=excluded.enabled,platform_failover_eligible=excluded.platform_failover_eligible,independent_material=excluded.independent_material,verification_state=excluded.verification_state,metadata=integration_control.stripe_live_secret_lanes_v1.metadata||excluded.metadata,updated_at=now();

update developer_commerce.stripe_connect_accounts
set connection_state='connected',last_refreshed_at=now(),metadata=metadata||jsonb_build_object('security_hold',false,'historical_security_hold_preserved',true,'current_provider_canary_http_status',200,'current_provider_account_verified',true,'current_provider_account_ref','acct_1PlvdLAfFd6y22C1','current_provider_runtime_route','secondary_connect_oauth','production_authority',true,'commerce_authority',true,'d3_authority',false,'money_movement_authority',false,'canonicalized_at',now())
where stripe_account_id='acct_1PlvdLAfFd6y22C1' and revoked_at is null;

update integration_control.stripe_os_accounts_v1 set provider_state='provider_live_verified_runtime',metadata=metadata||jsonb_build_object('runtime_credential_route','secondary_connect_oauth','runtime_provider_reverified',true),observed_at=now(),updated_at=now() where account_ref='acct_1PlvdLAfFd6y22C1';
update integration_control.stripe_os_accounts_v1 set provider_state='provider_live_verified_runtime',metadata=metadata||jsonb_build_object('runtime_credential_route','cold_crown_affiliates','runtime_provider_reverified',true),observed_at=now(),updated_at=now() where account_ref='acct_1MENDxCJFUeGxc8S';
update integration_control.stripe_os_adapter_registry_v1 set transport='ThriveBase server-side Stripe REST adapter',metadata=metadata||jsonb_build_object('implementation_function','integration_control.stripe_os_provider_request_v1','account_identity_probe','GET /v1/account before provider write','credential_policy','HOT/WARM/COLD with exact account match','reserved_effects_excluded',true),updated_at=now() where adapter_key='ct.adapter.stripe.runtime.v1';
update integration_control.crownthrive_partner_registry_v1 set drive_ref='gdrive:1ZbBG-D7Vp7eADYUnRwHlh-rYWRduL7Je8wikHtG53gU',metadata=metadata||jsonb_build_object('credential_ledger','gdrive:1ivPU83FUBOPFwkb2EzxaHKMJcLRsjhXNHncbccT1h6A','asset_registry','gdrive:1NH2yk1N6qK49zgcBDTbst08Djvh3ypkbHJN_YRyHQPg'),updated_at=now() where partner_key='ct.partner.stripe';

update integration_control.scheduler_desired_jobs_v2 set active=false,generation=202609010300,allow_auto_restore=false,source_ref='ct.binding.pentagreen-stripe-mesh.v3',metadata=metadata||jsonb_build_object('superseded',true,'superseded_by','ct-pentagreen-commerce-mesh-cycle-v1','behavior_changed',false,'cadence_preserved',true,'authority_created',false),updated_at=now() where jobname='ct-thriveevergreen-commerce-mesh-cycle-v1' and generation<=202609010300;
insert into integration_control.scheduler_desired_jobs_v2(jobname,schedule,command,database_name,username,active,generation,source_ref,desired_sha256,allow_auto_restore,metadata,created_at,updated_at)
values('ct-pentagreen-commerce-mesh-cycle-v1','5-50/15 * * * *','select integration_control.thriveevergreen_commerce_mesh_cycle_v1();','postgres','postgres',true,202609010300,'ct.binding.pentagreen-stripe-mesh.v3',encode(extensions.digest(convert_to('ct-pentagreen-commerce-mesh-cycle-v1|5-50/15 * * * *|select integration_control.thriveevergreen_commerce_mesh_cycle_v1();|postgres|postgres|true','UTF8'),'sha256'),'hex'),true,'{"canonical_clock":true,"supersedes":"ct-thriveevergreen-commerce-mesh-cycle-v1","sequence_family":"commerce","stripe_autowire":true,"commerce_binder":true,"single_clock_required":true,"behavior_changed":false,"cadence_preserved":true,"authority_created":false}'::jsonb,now(),now())
on conflict(jobname) do update set schedule=excluded.schedule,command=excluded.command,database_name=excluded.database_name,username=excluded.username,active=true,generation=greatest(integration_control.scheduler_desired_jobs_v2.generation,excluded.generation),source_ref=excluded.source_ref,desired_sha256=excluded.desired_sha256,allow_auto_restore=true,metadata=integration_control.scheduler_desired_jobs_v2.metadata||excluded.metadata,updated_at=now();

do $do$ declare r record; begin
  for r in select jobid from cron.job where active=true and command='select integration_control.thriveevergreen_commerce_mesh_cycle_v1();' and jobname<>'ct-pentagreen-commerce-mesh-cycle-v1' loop perform cron.unschedule(r.jobid); end loop;
  if not exists(select 1 from cron.job where active=true and jobname='ct-pentagreen-commerce-mesh-cycle-v1' and command='select integration_control.thriveevergreen_commerce_mesh_cycle_v1();') then perform cron.schedule('ct-pentagreen-commerce-mesh-cycle-v1','5-50/15 * * * *','select integration_control.thriveevergreen_commerce_mesh_cycle_v1();'); end if;
end $do$;

revoke all on integration_control.stripe_live_secret_lanes_v1 from public,anon,authenticated;
grant select on integration_control.stripe_live_secret_lanes_v1 to service_role;
