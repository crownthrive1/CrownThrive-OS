create or replace function public.penta_marketer_external_recipient_allowed_v1(
  p_recipient text,
  p_work_id uuid
) returns boolean
language sql
security definer
set search_path='pg_catalog','crm','public'
as $function$
  select crm.penta_marketer_external_recipient_allowed_v1(p_recipient,p_work_id);
$function$;

revoke all on function public.penta_marketer_external_recipient_allowed_v1(text,uuid) from public,anon,authenticated;
grant execute on function public.penta_marketer_external_recipient_allowed_v1(text,uuid) to service_role;
