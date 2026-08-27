-- PentaMail notification-recipient privacy boundary v1.0.0
-- Keep private recipient identities in the governed database preference record,
-- never in public source, Edge bundles, logs, or client-visible status output.

create or replace function public.penta_mail_notification_recipient_v1()
returns text
language plpgsql
security definer
set search_path = pg_catalog, os_v2, integration_control
as $$
declare
  v_recipient text;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select lower(btrim(p.recipient)) into v_recipient
  from os_v2.system_notification_preferences p
  where p.preference_key = 'founder_primary' and p.enabled
  limit 1;
  if v_recipient is null then
    raise exception 'PENTAMAIL_NOTIFICATION_RECIPIENT_UNAVAILABLE';
  end if;
  return v_recipient;
end
$$;

create or replace function public.penta_mail_recipient_allowed_v1(p_recipient text)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, os_v2, integration_control
as $$
declare
  v_recipient text := lower(nullif(btrim(coalesce(p_recipient, '')), ''));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  return v_recipient = 'contact@crownthrive.com' or exists (
    select 1 from os_v2.system_notification_preferences p
    where p.enabled and lower(btrim(p.recipient)) = v_recipient
  );
end
$$;

create or replace function public.penta_mail_admin_allowed_v1(p_recipient text)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, os_v2, integration_control
as $$
declare
  v_recipient text := lower(nullif(btrim(coalesce(p_recipient, '')), ''));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  return v_recipient = 'contact@crownthrive.com' or exists (
    select 1 from os_v2.system_notification_preferences p
    where p.preference_key = 'founder_primary'
      and p.enabled
      and lower(btrim(p.recipient)) = v_recipient
  );
end
$$;

create or replace function public.penta_mail_enqueue_v1(
  p_message_type text,
  p_severity text,
  p_subject text,
  p_body_text text,
  p_dedupe_key text default null,
  p_metadata jsonb default '{}'::jsonb,
  p_recipient text default null
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_id uuid;
  v_trigger text;
  v_status jsonb;
  v_state text;
  v_recipient text := lower(nullif(btrim(coalesce(p_recipient, '')), ''));
  v_available_at timestamptz := clock_timestamp();
  v_metadata jsonb := coalesce(p_metadata, '{}'::jsonb);
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if v_recipient is null then
    v_recipient := public.penta_mail_notification_recipient_v1();
  end if;
  if not public.penta_mail_recipient_allowed_v1(v_recipient) then
    raise exception 'PENTAMAIL_RECIPIENT_NOT_ALLOWLISTED';
  end if;
  if length(coalesce(p_subject, '')) = 0 or length(p_subject) > 180 then
    raise exception 'PENTAMAIL_INVALID_SUBJECT';
  end if;
  if length(coalesce(p_body_text, '')) = 0 or length(p_body_text) > 12000 then
    raise exception 'PENTAMAIL_INVALID_BODY';
  end if;
  v_trigger := integration_control.penta_mail_resolve_trigger_ref_v1(v_metadata, p_message_type);
  if v_trigger !~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$' then
    raise exception 'PENTAMAIL_INVALID_TRIGGER_REF';
  end if;
  v_status := public.penta_mail_provider_status_v1(v_trigger);
  v_state := case when v_status ->> 'route_state' in ('closed', 'controlled_release')
    and v_status ->> 'trigger_state' = 'eligible' then 'queued' else 'held' end;
  if v_status ->> 'route_state' not in ('closed', 'controlled_release') then
    v_available_at := greatest(
      v_available_at,
      coalesce((v_status ->> 'hold_until')::timestamptz, v_available_at)
    );
  end if;
  if v_status ->> 'trigger_state' = 'probation' then
    v_available_at := greatest(
      v_available_at,
      (v_status ->> 'trigger_probation_until')::timestamptz
    );
  end if;
  v_metadata := v_metadata || jsonb_build_object(
    'trigger_ref', v_trigger,
    'provider_control_state_at_enqueue', v_status ->> 'route_state',
    'provider_hold_policy', case when v_state = 'held'
      then 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
      else null end
  );
  insert into public.penta_mail_outbox_v1(
    message_type, severity, recipient, subject, body_text, dedupe_key, metadata,
    trigger_ref, state, available_at
  ) values (
    lower(coalesce(p_message_type, 'system')), upper(coalesce(p_severity, 'INFO')),
    v_recipient, p_subject, p_body_text, p_dedupe_key, v_metadata,
    v_trigger, v_state, v_available_at
  )
  on conflict(dedupe_key) where dedupe_key is not null do update set
    metadata = case when public.penta_mail_outbox_v1.state in ('dispatching', 'reconciliation_required')
      then public.penta_mail_outbox_v1.metadata
      else public.penta_mail_outbox_v1.metadata || excluded.metadata end,
    trigger_ref = case when public.penta_mail_outbox_v1.state in ('dispatching', 'reconciliation_required')
      then public.penta_mail_outbox_v1.trigger_ref else excluded.trigger_ref end,
    state = case
      when public.penta_mail_outbox_v1.state in ('sent', 'failed', 'dispatching', 'reconciliation_required')
        then public.penta_mail_outbox_v1.state
      when excluded.state = 'held' then 'held'
      else public.penta_mail_outbox_v1.state
    end,
    available_at = case
      when public.penta_mail_outbox_v1.state in ('sent', 'failed', 'dispatching', 'reconciliation_required')
        then public.penta_mail_outbox_v1.available_at
      else greatest(public.penta_mail_outbox_v1.available_at, excluded.available_at)
    end,
    updated_at = now()
  returning message_id into v_id;
  return v_id;
end
$$;

revoke all on function public.penta_mail_notification_recipient_v1()
  from public, anon, authenticated;
revoke all on function public.penta_mail_recipient_allowed_v1(text)
  from public, anon, authenticated;
revoke all on function public.penta_mail_admin_allowed_v1(text)
  from public, anon, authenticated;
revoke all on function public.penta_mail_enqueue_v1(text,text,text,text,text,jsonb,text)
  from public, anon, authenticated;

grant execute on function public.penta_mail_notification_recipient_v1()
  to service_role;
grant execute on function public.penta_mail_recipient_allowed_v1(text)
  to service_role;
grant execute on function public.penta_mail_admin_allowed_v1(text)
  to service_role;
grant execute on function public.penta_mail_enqueue_v1(text,text,text,text,text,jsonb,text)
  to service_role;

comment on function public.penta_mail_notification_recipient_v1() is
  'Service-role-only resolution of the active founder notification recipient from a private governed preference.';
comment on function public.penta_mail_recipient_allowed_v1(text) is
  'Service-role-only recipient allowlist check backed by private governed notification preferences.';
comment on function public.penta_mail_admin_allowed_v1(text) is
  'Service-role-only relay administrator check backed by the founder notification preference.';
