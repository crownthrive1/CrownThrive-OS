-- Governed external recipient authority for the single PentaMail transport boundary.

create or replace function crm.penta_marketer_external_recipient_allowed_v1(
  p_recipient text,
  p_work_id uuid
) returns boolean
language plpgsql
stable
security definer
set search_path='pg_catalog','crm','public'
as $function$
declare
  v_recipient text := lower(btrim(coalesce(p_recipient,'')));
  v_required integer;
  v_ceiling integer;
begin
  if current_user not in ('postgres','service_role') then return false; end if;
  if v_recipient !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then return false; end if;
  if public.penta_marketer_suppressed_v1(v_recipient) then return false; end if;

  select substring(w.authority_class from 2)::integer,
         substring(a.risk_ceiling from 2)::integer
    into v_required,v_ceiling
  from crm.penta_marketer_work_queue_v1 w
  join crm.penta_marketer_agents_v2 a on a.agent_id=w.assigned_agent_id
  join crm.penta_marketer_personas_v1 p on p.persona_id=w.assigned_persona_id
  where w.work_id=p_work_id
    and lower(w.recipient)=v_recipient
    and w.channel='email'
    and w.state in ('routed','queued','dispatching')
    and w.authority_class in ('D0','D1','D2')
    and a.enabled=true and a.state='active'
    and p.state='approved'
  limit 1;

  if v_required is null or v_ceiling is null then return false; end if;
  return v_required <= v_ceiling;
end
$function$;

create or replace function crm.penta_marketer_sync_mail_state_v1(
  p_message_id uuid,
  p_state text,
  p_provider_message_id text default null,
  p_error text default null
) returns boolean
language plpgsql
security definer
set search_path='pg_catalog','crm'
as $function$
declare
  v_state text := lower(coalesce(p_state,''));
begin
  if current_user not in ('postgres','service_role') then raise exception 'service_role_required'; end if;
  if v_state not in ('queued','dispatching','sent','failed','held','cancelled') then raise exception 'invalid_mail_state'; end if;

  update crm.penta_marketer_work_queue_v1
     set state=v_state,
         payload=payload||jsonb_strip_nulls(jsonb_build_object(
           'provider_message_id',nullif(p_provider_message_id,''),
           'last_mail_error',nullif(left(coalesce(p_error,''),1000),'')
         )),
         updated_at=now()
   where penta_mail_message_id=p_message_id;
  return found;
end
$function$;

create or replace function public.penta_mail_enqueue_v1(
  p_message_type text,
  p_severity text,
  p_subject text,
  p_body_text text,
  p_dedupe_key text default null,
  p_metadata jsonb default '{}'::jsonb,
  p_recipient text default null
) returns uuid
language plpgsql
security definer
set search_path='pg_catalog','public','integration_control','crm'
as $function$
declare
  v_id uuid;
  v_trigger text;
  v_status jsonb;
  v_state text;
  v_recipient text := lower(nullif(btrim(coalesce(p_recipient, '')), ''));
  v_available_at timestamptz := clock_timestamp();
  v_metadata jsonb := coalesce(p_metadata, '{}'::jsonb);
  v_work_id uuid;
  v_internal_allowed boolean := false;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if v_recipient is null then v_recipient := public.penta_mail_notification_recipient_v1(); end if;

  v_internal_allowed := public.penta_mail_recipient_allowed_v1(v_recipient);
  if not v_internal_allowed then
    if lower(coalesce(v_metadata->>'origin_penta','')) <> 'pentamarketer' then
      raise exception 'PENTAMAIL_RECIPIENT_NOT_ALLOWLISTED';
    end if;
    begin
      v_work_id := nullif(v_metadata->>'work_id','')::uuid;
    exception when others then
      v_work_id := null;
    end;
    if v_work_id is null or not crm.penta_marketer_external_recipient_allowed_v1(v_recipient,v_work_id) then
      raise exception 'PENTAMAIL_EXTERNAL_RECIPIENT_NOT_AUTHORIZED';
    end if;
    v_metadata:=v_metadata||jsonb_build_object('recipient_scope','governed_external','recipient_authority','PentaMarketer');
  else
    v_metadata:=v_metadata||jsonb_build_object('recipient_scope','internal_allowlist');
  end if;

  if length(coalesce(p_subject,''))=0 or length(p_subject)>180 then raise exception 'PENTAMAIL_INVALID_SUBJECT'; end if;
  if length(coalesce(p_body_text,''))=0 or length(p_body_text)>60000 then raise exception 'PENTAMAIL_INVALID_BODY'; end if;
  v_trigger := integration_control.penta_mail_resolve_trigger_ref_v1(v_metadata,p_message_type);
  if v_trigger !~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$' then raise exception 'PENTAMAIL_INVALID_TRIGGER_REF'; end if;
  v_status := public.penta_mail_provider_status_v1(v_trigger);
  v_state := case when v_status->>'route_state' in ('closed','controlled_release') and v_status->>'trigger_state'='eligible' then 'queued' else 'held' end;
  if v_status->>'route_state' not in ('closed','controlled_release') then v_available_at:=greatest(v_available_at,coalesce((v_status->>'hold_until')::timestamptz,v_available_at)); end if;
  if v_status->>'trigger_state'='probation' then v_available_at:=greatest(v_available_at,(v_status->>'trigger_probation_until')::timestamptz); end if;
  v_metadata:=v_metadata||jsonb_build_object('trigger_ref',v_trigger,'provider_control_state_at_enqueue',v_status->>'route_state','provider_hold_policy',case when v_state='held' then 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0' else null end,'body_limit_chars',60000);
  insert into public.penta_mail_outbox_v1(message_type,severity,recipient,subject,body_text,dedupe_key,metadata,trigger_ref,state,available_at)
  values(lower(coalesce(p_message_type,'system')),upper(coalesce(p_severity,'INFO')),v_recipient,p_subject,p_body_text,p_dedupe_key,v_metadata,v_trigger,v_state,v_available_at)
  on conflict(dedupe_key) where dedupe_key is not null do update set
    metadata=case when public.penta_mail_outbox_v1.state in('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.metadata else public.penta_mail_outbox_v1.metadata||excluded.metadata end,
    trigger_ref=case when public.penta_mail_outbox_v1.state in('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.trigger_ref else excluded.trigger_ref end,
    state=case when public.penta_mail_outbox_v1.state in('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.state when excluded.state='held' then 'held' else public.penta_mail_outbox_v1.state end,
    available_at=case when public.penta_mail_outbox_v1.state in('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.available_at else greatest(public.penta_mail_outbox_v1.available_at,excluded.available_at) end,
    updated_at=case when public.penta_mail_outbox_v1.state in('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.updated_at else clock_timestamp() end
  returning message_id into v_id;
  return v_id;
end
$function$;

revoke all on function crm.penta_marketer_external_recipient_allowed_v1(text,uuid) from public,anon,authenticated;
revoke all on function crm.penta_marketer_sync_mail_state_v1(uuid,text,text,text) from public,anon,authenticated;
grant execute on function crm.penta_marketer_external_recipient_allowed_v1(text,uuid) to service_role;
grant execute on function crm.penta_marketer_sync_mail_state_v1(uuid,text,text,text) to service_role;
