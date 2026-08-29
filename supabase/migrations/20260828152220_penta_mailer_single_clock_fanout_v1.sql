create or replace function public.penta_mail_dispatch_edge_v1(p_action text default 'process_outbox')
returns jsonb
language plpgsql
security definer
set search_path='pg_catalog','public','vault','net'
as $function$
declare
  v_token text;
  v_req_core bigint;
  v_req_marketer bigint;
  v_action text:=coalesce(nullif(btrim(p_action),''),'process_outbox');
begin
  select decrypted_secret into v_token
    from vault.decrypted_secrets
   where name='penta_mail_dispatch_token_v1'
   order by created_at desc limit 1;
  if v_token is null then raise exception 'PENTAMAIL_DISPATCH_TOKEN_MISSING'; end if;

  v_req_core:=net.http_post(
    url:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-mail',
    headers:=jsonb_build_object('content-type','application/json','x-penta-mail-token',v_token),
    body:=jsonb_build_object('action',v_action),
    timeout_milliseconds:=120000
  );

  if v_action='process_outbox' then
    v_req_marketer:=net.http_post(
      url:='https://tzajnzshmtzjenqulehq.supabase.co/functions/v1/penta-mail-marketer-dispatch',
      headers:=jsonb_build_object('content-type','application/json','x-penta-mail-token',v_token),
      body:=jsonb_build_object('action','process_outbox','batch',2),
      timeout_milliseconds:=120000
    );
  end if;

  return jsonb_build_object(
    'state','requested',
    'action',v_action,
    'transport_owner','PentaMail',
    'core_request_id',v_req_core,
    'governed_external_request_id',v_req_marketer,
    'communication_control_plane','PentaMarketer',
    'at',now()
  );
end
$function$;
