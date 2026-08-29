-- Locticians / Brilliant Directories independent warm failover v3
-- Provider keys remain secret. Public source contains only the custody/selection contract.

create table if not exists integration_control.locticians_bd_key_ingest_attempts_v3 (
  attempt_id uuid primary key default gen_random_uuid(),
  request_shape text not null,
  edge_http_status integer,
  edge_ok boolean,
  error_code text,
  response_sha256 text,
  attempted_at timestamptz not null default now()
);
alter table integration_control.locticians_bd_key_ingest_attempts_v3 enable row level security;
revoke all on integration_control.locticians_bd_key_ingest_attempts_v3 from public,anon,authenticated;
grant select,insert on integration_control.locticians_bd_key_ingest_attempts_v3 to service_role;
create policy locticians_bd_key_ingest_attempts_service_v3 on integration_control.locticians_bd_key_ingest_attempts_v3 for select to service_role using(true);
create policy locticians_bd_key_ingest_attempts_insert_service_v3 on integration_control.locticians_bd_key_ingest_attempts_v3 for insert to service_role with check(true);

create or replace function integration_control.store_locticians_bd_standby_secret_v3(
  p_provider_key_id integer,
  p_provider_name text,
  p_secret text
) returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_alias text;
  v_expected_name text;
  v_primary text;
  v_existing text;
  v_existing_id uuid;
  v_sha text;
  v_created boolean:=false;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then raise exception 'service_role_required'; end if;
  if p_provider_key_id=13 then
    v_alias:='locticians_brilliant_directories_pentamailer_v3';
    v_expected_name:='PentaMailer';
  elsif p_provider_key_id=14 then
    v_alias:='locticians_brilliant_directories_pentamailer_2_v3';
    v_expected_name:='PentaMailer 2';
  else
    raise exception 'provider_key_id_not_allowed';
  end if;
  if p_provider_name is distinct from v_expected_name then raise exception 'provider_key_name_mismatch'; end if;
  if p_secret is null or length(p_secret)<20 or length(p_secret)>500 then raise exception 'invalid_provider_secret_shape'; end if;

  select decrypted_secret into v_primary from vault.decrypted_secrets where name='locticians_brilliant_directories_api_key' limit 1;
  if v_primary is null then raise exception 'primary_bd_secret_unavailable'; end if;
  if p_secret=v_primary then raise exception 'standby_not_distinct_from_primary'; end if;

  select s.id,d.decrypted_secret into v_existing_id,v_existing
  from vault.secrets s join vault.decrypted_secrets d on d.id=s.id
  where s.name=v_alias limit 1;

  v_sha:=encode(extensions.digest(p_secret,'sha256'),'hex');
  if v_existing_id is null then
    perform vault.create_secret(
      p_secret,
      v_alias,
      format('Brilliant Directories independent standby; provider key ID %s (%s); restricted runtime custody; raw material must never be projected.',p_provider_key_id,p_provider_name),
      null
    );
    v_created:=true;
  elsif v_existing=p_secret then
    v_created:=false;
  else
    raise exception 'standby_alias_already_bound_to_different_material';
  end if;

  update integration_control.locticians_bd_failover_candidates_v3
     set vault_material_state='present',
         distinctness_state='distinct_from_primary',
         provider_verify_state='vaulted_pending_read_canary',
         failover_ready=false,
         metadata=metadata||jsonb_build_object('vault_alias',v_alias,'token_sha256',v_sha,'raw_secret_exposed',false,'vaulted_at',now()),
         updated_at=now()
   where provider_key_id=p_provider_key_id;

  return jsonb_build_object(
    'ok',true,
    'provider_key_id',p_provider_key_id,
    'provider_name',p_provider_name,
    'vault_alias',v_alias,
    'created',v_created,
    'token_sha256',v_sha,
    'raw_secret_exposed',false,
    'provider_canary_required',true
  );
end $$;

revoke all on function integration_control.store_locticians_bd_standby_secret_v3(integer,text,text) from public,anon,authenticated;
grant execute on function integration_control.store_locticians_bd_standby_secret_v3(integer,text,text) to service_role;

-- Promotion is performed by the restricted locticians-bd-key-promote-v3 edge:
-- 1. read provider records 13/14 with the canonical primary credential;
-- 2. prove exact ID/name/active state and token presence;
-- 3. prove 13 != primary, 14 != primary, and 13 != 14;
-- 4. call this service-role-only Vault writer;
-- 5. run integration_control.locticians_bd_warm_failover_reconcile_v3();
-- 6. return only hashes and safe receipts.

select cron.unschedule(jobid) from cron.job where jobname='ct-locticians-bd-failover-reconcile-v3';
select cron.schedule('ct-locticians-bd-failover-reconcile-v3','11 * * * *','select integration_control.locticians_bd_warm_failover_reconcile_v3();');
