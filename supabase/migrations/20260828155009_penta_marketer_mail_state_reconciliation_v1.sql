create or replace function crm.penta_marketer_sync_mail_state_v1(
  p_message_id uuid,
  p_state text,
  p_provider_message_id text default null,
  p_error text default null
) returns boolean
language plpgsql
security definer
set search_path='pg_catalog','crm','public'
as $function$
declare
  v_requested text := lower(coalesce(p_state,''));
  v_outbox_state text;
  v_state text;
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if v_requested not in ('queued','dispatching','sent','failed','held','cancelled') then raise exception 'invalid_mail_state'; end if;

  select lower(state) into v_outbox_state
  from public.penta_mail_outbox_v1
  where message_id=p_message_id;

  v_state := case
    when v_outbox_state='sent' then 'sent'
    when v_outbox_state in ('queued','pending','retry') then 'queued'
    when v_outbox_state='dispatching' then 'dispatching'
    when v_outbox_state in ('held','reconciliation_required') then 'held'
    when v_outbox_state='failed' then 'failed'
    else v_requested
  end;

  update crm.penta_marketer_work_queue_v1
     set state=v_state,
         payload=payload||jsonb_strip_nulls(jsonb_build_object(
           'provider_message_id',nullif(p_provider_message_id,''),
           'last_mail_error',nullif(left(coalesce(p_error,''),1000),''),
           'mail_outbox_state',v_outbox_state,
           'mail_state_reconciled_at',now()
         )),
         updated_at=now()
   where penta_mail_message_id=p_message_id;
  return found;
end
$function$;
