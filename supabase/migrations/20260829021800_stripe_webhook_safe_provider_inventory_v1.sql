create table if not exists integration_control.stripe_webhook_provider_inventory_v1 (
  observation_id uuid primary key default gen_random_uuid(),
  observed_at timestamptz not null default now(),
  secret_alias text not null,
  key_fingerprint text not null,
  key_mode text not null,
  provider_http_status integer not null,
  endpoint_id text,
  endpoint_url text,
  endpoint_status text,
  livemode boolean,
  api_version text,
  enabled_events jsonb not null default '[]'::jsonb,
  response_sha256 text,
  error_class text,
  created_at timestamptz not null default now()
);

alter table integration_control.stripe_webhook_provider_inventory_v1 enable row level security;
revoke all on integration_control.stripe_webhook_provider_inventory_v1 from public, anon, authenticated;
grant select, insert on integration_control.stripe_webhook_provider_inventory_v1 to service_role;

drop policy if exists stripe_webhook_provider_inventory_service_role_v1 on integration_control.stripe_webhook_provider_inventory_v1;
create policy stripe_webhook_provider_inventory_service_role_v1
  on integration_control.stripe_webhook_provider_inventory_v1
  for select to service_role using (true);
create policy stripe_webhook_provider_inventory_insert_service_role_v1
  on integration_control.stripe_webhook_provider_inventory_v1
  for insert to service_role with check (true);

create or replace function integration_control.stripe_webhook_inventory_refresh_v1()
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  s record;
  r extensions.http_response;
  j jsonb;
  e jsonb;
  v_key_fp text;
  v_count int := 0;
  v_keys int := 0;
  v_errors int := 0;
begin
  if session_user not in ('postgres','supabase_admin') and v_role <> 'service_role' then
    raise exception 'service_role_required';
  end if;

  for s in
    select name,decrypted_secret
    from vault.decrypted_secrets
    where decrypted_secret like 'sk_live\_%' escape '\'
       or decrypted_secret like 'sk_test\_%' escape '\'
       or decrypted_secret like 'rk_live\_%' escape '\'
       or decrypted_secret like 'rk_test\_%' escape '\'
  loop
    v_keys := v_keys + 1;
    v_key_fp := encode(extensions.digest(s.decrypted_secret,'sha256'),'hex');
    begin
      r := extensions.http((
        'GET'::extensions.http_method,
        'https://api.stripe.com/v1/webhook_endpoints?limit=100'::varchar,
        array[
          row('Authorization','Bearer '||s.decrypted_secret)::extensions.http_header,
          row('Stripe-Version','2024-06-20')::extensions.http_header,
          row('accept','application/json')::extensions.http_header
        ],
        null::varchar,
        null::varchar
      )::extensions.http_request);
      j := case when r.content is null or r.content='' then '{}'::jsonb else r.content::jsonb end;

      if r.status between 200 and 299 then
        for e in select value from jsonb_array_elements(coalesce(j->'data','[]'::jsonb)) loop
          insert into integration_control.stripe_webhook_provider_inventory_v1(
            secret_alias,key_fingerprint,key_mode,provider_http_status,
            endpoint_id,endpoint_url,endpoint_status,livemode,api_version,
            enabled_events,response_sha256
          ) values (
            s.name,
            v_key_fp,
            case when s.decrypted_secret like '%_live_%' then 'live' else 'test' end,
            r.status,
            e->>'id',
            e->>'url',
            e->>'status',
            coalesce((e->>'livemode')::boolean,false),
            e->>'api_version',
            coalesce(e->'enabled_events','[]'::jsonb),
            encode(extensions.digest(r.content,'sha256'),'hex')
          );
          v_count := v_count + 1;
        end loop;
      else
        insert into integration_control.stripe_webhook_provider_inventory_v1(
          secret_alias,key_fingerprint,key_mode,provider_http_status,response_sha256,error_class
        ) values (
          s.name,
          v_key_fp,
          case when s.decrypted_secret like '%_live_%' then 'live' else 'test' end,
          r.status,
          encode(extensions.digest(coalesce(r.content,''),'sha256'),'hex'),
          'provider_http_'||r.status
        );
        v_errors := v_errors + 1;
      end if;
    exception when others then
      insert into integration_control.stripe_webhook_provider_inventory_v1(
        secret_alias,key_fingerprint,key_mode,provider_http_status,error_class
      ) values (
        s.name,
        v_key_fp,
        case when s.decrypted_secret like '%_live_%' then 'live' else 'test' end,
        599,
        'transport_or_parse_failure'
      );
      v_errors := v_errors + 1;
    end;
  end loop;

  return jsonb_build_object(
    'keys_checked',v_keys,
    'endpoints_observed',v_count,
    'errors',v_errors,
    'raw_credentials_exposed',false,
    'observed_at',now()
  );
end $$;

revoke all on function integration_control.stripe_webhook_inventory_refresh_v1() from public, anon, authenticated;
grant execute on function integration_control.stripe_webhook_inventory_refresh_v1() to service_role;
