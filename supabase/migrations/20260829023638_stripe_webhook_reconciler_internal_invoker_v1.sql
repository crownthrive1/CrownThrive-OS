create or replace function integration_control.stripe_webhook_reconcile_invoke_v1(p_binding_key text default null)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,integration_control,vault,extensions
as $$
declare
  v_role text := coalesce((nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'role'),'');
  v_control text;
  v_response extensions.http_response;
  v_body text;
begin
  if session_user not in ('postgres','supabase_admin') and v_role<>'service_role' then raise exception 'service_role_required'; end if;
  select decrypted_secret into v_control from vault.decrypted_secrets where name='stripe_production_control_gateway_secret_v1' order by created_at desc limit 1;
  if v_control is null then raise exception 'stripe_control_secret_missing'; end if;
  v_body:=case when p_binding_key is null then '{}' else jsonb_build_object('binding_key',p_binding_key)::text end;
  select extensions.http((
    'POST'::extensions.http_method,
    'https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/stripe-webhook-reconciler-v1'::varchar,
    array[row('x-ct-stripe-control-secret',v_control)::extensions.http_header,row('content-type','application/json')::extensions.http_header],
    'application/json'::varchar,
    v_body::varchar
  )::extensions.http_request) into v_response;
  return jsonb_build_object('http_status',v_response.status,'response',case when v_response.content is null or v_response.content='' then '{}'::jsonb else v_response.content::jsonb end,'secret_exposed',false);
end $$;
revoke all on function integration_control.stripe_webhook_reconcile_invoke_v1(text) from public,anon,authenticated;
grant execute on function integration_control.stripe_webhook_reconcile_invoke_v1(text) to service_role;