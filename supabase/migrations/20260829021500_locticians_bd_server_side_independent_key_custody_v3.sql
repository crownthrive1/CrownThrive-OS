create or replace function integration_control.locticians_bd_store_provider_key_v3(
  p_provider_key_id integer,
  p_provider_key_name text,
  p_token text,
  p_provider_status text,
  p_response_sha256 text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_alias text;
  v_lane text;
  v_expected_name text;
  v_primary text;
  v_peer text;
  v_secret_id uuid;
  v_token_sha text;
  v_created boolean := false;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;

  if p_provider_key_id=13 then
    v_expected_name := 'PentaMailer';
    v_alias := 'locticians_brilliant_directories_pentamailer_v3';
    v_lane := 'ct.locticians.bd.hot.b.v3';
  elsif p_provider_key_id=14 then
    v_expected_name := 'PentaMailer 2';
    v_alias := 'locticians_brilliant_directories_pentamailer_2_v3';
    v_lane := 'ct.locticians.bd.cold.reserve.v3';
  else
    raise exception 'provider_key_id_not_allowed';
  end if;

  if p_provider_key_name is distinct from v_expected_name then raise exception 'provider_key_name_mismatch'; end if;
  if p_provider_status not in ('1','active','enabled') then raise exception 'provider_key_not_active'; end if;
  if p_token is null or length(p_token)<20 or length(p_token)>4096 then raise exception 'invalid_provider_token_shape'; end if;

  select decrypted_secret into v_primary from vault.decrypted_secrets where name='locticians_brilliant_directories_api_key' limit 1;
  if v_primary is null then raise exception 'primary_provider_key_missing'; end if;
  if p_token=v_primary then raise exception 'candidate_not_independent_from_primary'; end if;

  if p_provider_key_id=13 then
    select decrypted_secret into v_peer from vault.decrypted_secrets where name='locticians_brilliant_directories_pentamailer_2_v3' limit 1;
  else
    select decrypted_secret into v_peer from vault.decrypted_secrets where name='locticians_brilliant_directories_pentamailer_v3' limit 1;
  end if;
  if v_peer is not null and p_token=v_peer then raise exception 'candidate_not_independent_from_peer'; end if;

  v_token_sha := encode(extensions.digest(p_token,'sha256'),'hex');
  select id into v_secret_id from vault.secrets where name=v_alias limit 1;
  if v_secret_id is null then
    perform vault.create_secret(
      p_token,
      v_alias,
      format('Brilliant Directories independent provider credential ID %s (%s). Restricted CrownThrive V3 runtime custody; raw material must never be projected.',p_provider_key_id,p_provider_key_name),
      null
    );
    v_created := true;
  else
    perform vault.update_secret(
      v_secret_id,
      p_token,
      v_alias,
      format('Brilliant Directories independent provider credential ID %s (%s). Restricted CrownThrive V3 runtime custody; raw material must never be projected.',p_provider_key_id,p_provider_key_name),
      null
    );
  end if;

  update integration_control.locticians_bd_failover_candidates_v3
     set provider_inventory_state='provider_issued_vaulted',
         vault_material_state='present',
         distinctness_state='distinct_from_primary',
         provider_verify_state='vaulted_pending_live_canary',
         failover_ready=false,
         last_provider_http_status=200,
         last_reconciled_at=now(),
         metadata=metadata||jsonb_build_object(
           'provider_response_sha256',p_response_sha256,
           'vault_alias',v_alias,
           'token_sha256',v_token_sha,
           'raw_token_exposed',false,
           'vaulted_at',now()
         ),
         updated_at=now()
   where provider_key_id=p_provider_key_id;

  update integration_control.locticians_provider_key_lanes_v1
     set credential_id=case when p_provider_key_id=13 then 'locticians_bd_pentamailer_v3' else 'locticians_bd_pentamailer_2_v3' end,
         provider_key_name=p_provider_key_name,
         vault_alias=v_alias,
         enabled=false,
         provider_status='vaulted_pending_live_canary',
         dispatch_state='VERIFYING',
         metadata=metadata||jsonb_build_object(
           'provider_key_id',p_provider_key_id,
           'token_sha256',v_token_sha,
           'raw_token_exposed',false,
           'independent_credential',true,
           'switch_on_429',false
         ),
         updated_at=now()
   where lane_id=v_lane;

  return jsonb_build_object(
    'stored',true,
    'created',v_created,
    'provider_key_id',p_provider_key_id,
    'provider_key_name',p_provider_key_name,
    'vault_alias',v_alias,
    'lane_id',v_lane,
    'token_sha256',v_token_sha,
    'raw_token_exposed',false,
    'provider_response_sha256',p_response_sha256
  );
end $$;

revoke all on function integration_control.locticians_bd_store_provider_key_v3(integer,text,text,text,text) from public,anon,authenticated;
grant execute on function integration_control.locticians_bd_store_provider_key_v3(integer,text,text,text,text) to service_role;
