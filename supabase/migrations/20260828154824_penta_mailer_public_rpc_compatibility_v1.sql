create or replace function public.penta_marketer_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language sql
security definer
set search_path='pg_catalog','crm','public'
as $function$
  select * from crm.penta_marketer_claim_outbox_v2(p_limit);
$function$;

create or replace function public.penta_marketer_sync_mail_state_v1(
  p_message_id uuid,
  p_state text,
  p_provider_message_id text default null,
  p_error text default null
) returns boolean
language sql
security definer
set search_path='pg_catalog','crm','public'
as $function$
  select crm.penta_marketer_sync_mail_state_v1(p_message_id,p_state,p_provider_message_id,p_error);
$function$;

revoke all on function public.penta_marketer_claim_outbox_v2(integer) from public,anon,authenticated;
revoke all on function public.penta_marketer_sync_mail_state_v1(uuid,text,text,text) from public,anon,authenticated;
grant execute on function public.penta_marketer_claim_outbox_v2(integer) to service_role;
grant execute on function public.penta_marketer_sync_mail_state_v1(uuid,text,text,text) to service_role;
