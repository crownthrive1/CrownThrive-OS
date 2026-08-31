-- Deterministic Locticians persona BD priority promotion watcher.
-- No raw credential material is stored in source; runtime reads only named Vault aliases.
-- User-authorized intended order after permission readback:
-- Personas 1 Hot -> Personas 2 Warm -> Personas 3 Cold -> Emergency 1 -> Emergency 2 -> legacy/master fallback.

create or replace function integration_control.locticians_bd_persona_priority_promote_v1()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','vault','extensions','chlom_runtime'
as $function$
declare
  r record;
  v_token text;
  v_site integer;
  v_fields integer;
  v_categories integer;
  v_ready boolean;
  v_promoted integer:=0;
  v_held integer:=0;
  v_transient integer:=0;
  v_previous_primary text;
  v_new_primary text;
  v_event jsonb;
begin
  if session_user not in ('postgres','supabase_admin') and coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'') <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  select lane_id into v_previous_primary
  from integration_control.locticians_provider_key_lanes_v1
  where service_id='locticians' and enabled=true and dispatch_state='WARM_PRIMARY'
  order by priority limit 1;

  for r in
    select * from integration_control.locticians_provider_key_lanes_v1
    where lane_id like 'ct.locticians.bd.personas.%'
    order by priority
  loop
    v_token:=null; v_site:=599; v_fields:=599; v_categories:=599;
    select decrypted_secret into v_token from vault.decrypted_secrets where name=r.vault_alias limit 1;
    if v_token is null then
      update integration_control.locticians_provider_key_lanes_v1
      set enabled=false,provider_status='vault_secret_missing',dispatch_state='HOLD_VAULT_SECRET_MISSING',
          metadata=metadata||jsonb_build_object('failover_ready',false,'last_promotion_probe_at',now(),'secret_material_exposed',false),updated_at=now()
      where lane_id=r.lane_id;
      v_held:=v_held+1;
      continue;
    end if;

    begin
      v_site:=(chlom_runtime.dail_http_v1(('GET','https://www.locticians.com/api/v2/site_info/get',array[extensions.http_header('X-Api-Key',v_token),extensions.http_header('accept','application/json')],null,null)::extensions.http_request)).status;
      v_fields:=(chlom_runtime.dail_http_v1(('GET','https://www.locticians.com/api/v2/user/fields',array[extensions.http_header('X-Api-Key',v_token),extensions.http_header('accept','application/json')],null,null)::extensions.http_request)).status;
      v_categories:=(chlom_runtime.dail_http_v1(('GET','https://www.locticians.com/api/v2/data_categories/get?limit=1',array[extensions.http_header('X-Api-Key',v_token),extensions.http_header('accept','application/json')],null,null)::extensions.http_request)).status;
    exception when others then
      v_site:=599; v_fields:=599; v_categories:=599;
    end;

    v_ready:=v_site between 200 and 299 and v_fields between 200 and 299 and v_categories between 200 and 299;

    if v_ready then
      if not r.enabled or r.provider_status<>'provider_verified_operational' then v_promoted:=v_promoted+1; end if;
      update integration_control.locticians_provider_key_lanes_v1
      set enabled=true,provider_status='provider_verified_operational',
          permission_profile='bounded_reads_and_site_info_verified',dispatch_state='WARM_STANDBY',last_verified_at=now(),
          metadata=metadata||jsonb_build_object('authentication_verified',true,'user_fields_http_status',v_fields,'data_categories_http_status',v_categories,'site_info_http_status',v_site,'site_info_permission_pending',false,'failover_ready',true,'promotion_canary_passed',true,'last_promotion_probe_at',now(),'secret_material_exposed',false),updated_at=now()
      where lane_id=r.lane_id;
      update integration_control.credential_continuity_registry
      set continuity_state='verified_primary_only',last_verified_at=now(),
          recovery_note='Credential and required bounded provider permissions verified; lane eligible for priority routing.',updated_at=now()
      where credential_id=r.credential_id;
    elsif v_site=599 or v_fields=599 or v_categories=599 then
      update integration_control.locticians_provider_key_lanes_v1
      set metadata=metadata||jsonb_build_object('last_promotion_probe_at',now(),'promotion_probe_state','transient_deferred','site_info_http_status',v_site,'user_fields_http_status',v_fields,'data_categories_http_status',v_categories,'secret_material_exposed',false),updated_at=now()
      where lane_id=r.lane_id;
      v_transient:=v_transient+1;
    else
      update integration_control.locticians_provider_key_lanes_v1
      set enabled=false,
          provider_status=case when v_fields between 200 and 299 and v_categories between 200 and 299 and v_site=403 then 'provider_authenticated_pending_permission' else 'provider_verify_failed' end,
          permission_profile=case when v_fields between 200 and 299 and v_categories between 200 and 299 and v_site=403 then 'bounded_reads_verified_site_info_advanced_pending' else 'provider_verification_failed' end,
          dispatch_state=case when v_site=403 then 'HOLD_PENDING_PERMISSION' else 'HOLD_PROVIDER_VERIFY_FAILED' end,
          last_verified_at=now(),
          metadata=metadata||jsonb_build_object('user_fields_http_status',v_fields,'data_categories_http_status',v_categories,'site_info_http_status',v_site,'site_info_permission_pending',(v_site=403),'failover_ready',false,'promotion_canary_passed',false,'last_promotion_probe_at',now(),'secret_material_exposed',false),updated_at=now()
      where lane_id=r.lane_id;
      v_held:=v_held+1;
    end if;
  end loop;

  select lane_id into v_new_primary
  from integration_control.locticians_provider_key_lanes_v1
  where lane_id like 'ct.locticians.bd.personas.%' and enabled=true and provider_status='provider_verified_operational'
  order by priority limit 1;

  if v_new_primary is not null then
    update integration_control.locticians_provider_key_lanes_v1
    set dispatch_state='WARM_STANDBY',updated_at=now()
    where service_id='locticians' and enabled=true and lane_id in (
      'ct.locticians.bd.hot.a.v3',
      'ct.locticians.bd.personas.hot.v1','ct.locticians.bd.personas.warm.v1','ct.locticians.bd.personas.cold.v1',
      'ct.locticians.bd.personas.emergency.1.v1','ct.locticians.bd.personas.emergency.2.v1'
    );
    update integration_control.locticians_provider_key_lanes_v1 set dispatch_state='WARM_PRIMARY',updated_at=now() where lane_id=v_new_primary;
  else
    update integration_control.locticians_provider_key_lanes_v1 set dispatch_state='WARM_PRIMARY',updated_at=now()
    where lane_id='ct.locticians.bd.hot.a.v3' and enabled=true;
  end if;

  if v_promoted>0 or coalesce(v_previous_primary,'') is distinct from coalesce(v_new_primary,'') then
    v_event:=chlom_runtime.append_dail_event(
      'locticians.bd.persona_priority_promotion.v1','provider_credential_fabric','ct.locticians.bd.persona-priority-fabric.v1',
      jsonb_build_object('promoted_lanes',v_promoted,'held_lanes',v_held,'transient_deferred',v_transient,'previous_primary',v_previous_primary,'new_primary',coalesce(v_new_primary,'ct.locticians.bd.hot.a.v3'),'raw_secret_exposed',false,'shared_provider_quota',true,'switch_on_429',false,'authority_expansion',false),
      'PentaCredentials/PentaPersonas',null,'PentaCredentials','1.0.0','ct.locticians.bd.persona-priority-promote',null,'ct.locticians.brilliant-directories.api-fabric.v3',null,'restricted');
  end if;

  return jsonb_build_object('state',case when v_new_primary is null then 'pending_permission' else 'priority_fabric_active' end,'promoted_lanes',v_promoted,'held_lanes',v_held,'transient_deferred',v_transient,'previous_primary',v_previous_primary,'active_primary',coalesce(v_new_primary,'ct.locticians.bd.hot.a.v3'),'raw_secret_exposed',false,'observed_at',now());
end
$function$;

create or replace function integration_control.locticians_bd_select_warm_credential_v3(p_failure_class text default 'none'::text)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','integration_control','vault'
as $function$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_failure text := lower(coalesce(p_failure_class,'none'));
  v_row record;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if v_failure in ('429','rate_limit','quota','provider_global','provider_cooldown') then
    return jsonb_build_object('action','provider_route_hold','switch_key',false,'reason','shared_provider_quota_or_cooldown','authority','ct.locticians.brilliant-directories.api-fabric.v3');
  end if;

  if v_failure in ('vault_alias_unavailable','vault_read_failure','401','403','credential_auth_failure','credential_revoked','credential_permission_failure') then
    select lane_id,vault_alias,coalesce((metadata->>'independent_credential')::boolean,false) as independent into v_row
    from integration_control.locticians_provider_key_lanes_v1
    where service_id='locticians' and enabled=true and dispatch_state='WARM_STANDBY' and provider_status='provider_verified_operational'
    order by priority limit 1;
    if found then return jsonb_build_object('action','use_credential','lane_id',v_row.lane_id,'vault_alias',v_row.vault_alias,'failover_mode','priority_standby','independent_provider_credential',v_row.independent,'switch_key',true); end if;
    if v_failure in ('vault_alias_unavailable','vault_read_failure') then
      if exists(select 1 from vault.secrets where name='locticians_brilliant_directories_api_key_recovery') then
        return jsonb_build_object('action','use_credential','lane_id','ct.locticians.bd.hot.a.v3','vault_alias','locticians_brilliant_directories_api_key_recovery','failover_mode','custody_copy','independent_provider_credential',false,'switch_key',false);
      elsif exists(select 1 from vault.secrets where name='LOCTICIANS_BD_API_KEY_COLD_PENTA') then
        return jsonb_build_object('action','use_credential','lane_id','ct.locticians.bd.hot.a.v3','vault_alias','LOCTICIANS_BD_API_KEY_COLD_PENTA','failover_mode','custody_copy','independent_provider_credential',false,'switch_key',false);
      end if;
    end if;
    return jsonb_build_object('action','provider_route_hold','switch_key',false,'reason','no_verified_priority_standby');
  end if;

  select lane_id,vault_alias,coalesce((metadata->>'independent_credential')::boolean,false) as independent into v_row
  from integration_control.locticians_provider_key_lanes_v1
  where service_id='locticians' and enabled=true and dispatch_state='WARM_PRIMARY' and provider_status='provider_verified_operational'
  order by priority limit 1;
  if found then return jsonb_build_object('action','use_credential','lane_id',v_row.lane_id,'vault_alias',v_row.vault_alias,'failover_mode','primary','independent_provider_credential',v_row.independent,'switch_key',false); end if;
  return jsonb_build_object('action','provider_route_hold','switch_key',false,'reason','warm_primary_unavailable');
end
$function$;

do $do$
begin
  if not exists(select 1 from cron.job where jobname='ct-locticians-bd-persona-permission-promote-v1') then
    perform cron.schedule('ct-locticians-bd-persona-permission-promote-v1','*/5 * * * *','select integration_control.locticians_bd_persona_priority_promote_v1();');
  end if;
end
$do$;
