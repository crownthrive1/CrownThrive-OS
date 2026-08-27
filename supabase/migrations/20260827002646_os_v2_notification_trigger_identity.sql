-- Propagate causal trigger identity through the OS V2 notification queue so
-- a 72-hour probation remains scoped to the offending producer.

alter table os_v2.notifications
  add column if not exists trigger_ref text not null default 'os-v2:notification';

create index if not exists os_v2_notifications_trigger_dispatch_idx
  on os_v2.notifications(trigger_ref, state, available_at);

update os_v2.notifications n
set trigger_ref = 'db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1'
from os_v2.system_change_events e
where e.notification_id = n.notification_id
  and e.source_system = 'PentaCertify'
  and e.event_type = 'provider_certification_state_changed'
  and n.trigger_ref = 'os-v2:notification';

create or replace function os_v2.notify_provider_cert_state_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, os_v2, integration_control
as $$
declare
  v_sev text;
  v_title text;
  v_summary text;
  v_change jsonb;
  v_event_id uuid;
  v_notification_id uuid;
  v_probation_until timestamptz;
  v_active_incident_id uuid;
  v_pref os_v2.system_notification_preferences%rowtype;
  v_deferred_count integer;
  v_trigger_ref constant text := 'db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1';
begin
  if old.certification_state is not distinct from new.certification_state then
    return new;
  end if;
  v_sev := case
    when new.certification_state = 'certified' then 'info'
    when new.certification_state ilike '%blocked%' or new.certification_state ilike '%failed%' then 'critical'
    else 'info'
  end;
  v_title := case
    when new.certification_state = 'certified' then new.provider_system || ' provider capability certified'
    else new.provider_system || ' certification advanced to ' || new.certification_state
  end;
  v_summary := format(
    'Provider %s / surface %s moved from %s to %s. Remaining requirements: %s.',
    new.provider_system, new.surface_id, coalesce(old.certification_state, 'none'),
    new.certification_state, coalesce(new.missing_requirements::text, '[]')
  );
  select p.probation_until, p.active_incident_id
  into v_probation_until, v_active_incident_id
  from integration_control.penta_mail_trigger_probation_v1 p
  where p.trigger_ref = v_trigger_ref and p.probation_until > clock_timestamp();
  if found then
    insert into os_v2.system_change_events(
      source_system, event_type, entity_ref, severity, title, summary, details, dedupe_key
    ) values (
      'PentaCertify', 'provider_certification_state_changed', new.surface_id,
      v_sev, v_title, v_summary,
      jsonb_build_object(
        'provider_system', new.provider_system,
        'surface_id', new.surface_id,
        'from', old.certification_state,
        'to', new.certification_state,
        'missing_requirements', new.missing_requirements,
        'notification_state', 'coalesced_queued_during_trigger_probation',
        'deferred_until', v_probation_until,
        'trigger_ref', v_trigger_ref,
        'policy_id', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1',
        'policy_version', '1.0.0'
      ),
      'provider_cert:' || new.surface_id || ':' || new.certification_state || ':' ||
        extract(epoch from new.updated_at)::bigint::text
    ) on conflict (dedupe_key) do nothing
    returning event_id into v_event_id;
    if v_event_id is null then
      return new;
    end if;
    perform pg_advisory_xact_lock(hashtext('os_v2:penta-certify-probation-digest'));
    select * into v_pref
    from os_v2.system_notification_preferences
    where preference_key = 'founder_primary';
    if found and v_pref.enabled and v_pref.immediate_material_changes
      and os_v2.severity_rank(v_sev) >= os_v2.severity_rank(v_pref.minimum_severity) then
      select n.notification_id into v_notification_id
      from os_v2.notifications n
      where n.trigger_ref = v_trigger_ref
        and n.state = 'queued'
        and n.provider_receipt ->> 'control_kind' = 'trigger_probation_digest'
      order by n.created_at
      limit 1
      for update;
      if found then
        v_deferred_count := case
          when coalesce((select provider_receipt ->> 'deferred_event_count'
            from os_v2.notifications where notification_id = v_notification_id), '') ~ '^[0-9]+$'
          then (select (provider_receipt ->> 'deferred_event_count')::integer
            from os_v2.notifications where notification_id = v_notification_id)
          else 0
        end + 1;
        update os_v2.notifications
        set severity = case when v_sev = 'critical' or severity = 'critical' then 'critical' else severity end,
            subject = '[CrownThrive System] PentaCertify changes held during trigger probation',
            body = format(
              'CrownThrive retained %s PentaCertify change notifications while the causal trigger is on probation. They are coalesced into this single digest until %s. Latest change: %s No provider call is permitted before the governed release boundary.',
              v_deferred_count, v_probation_until, v_summary
            ),
            available_at = greatest(available_at, v_probation_until),
            provider_receipt = coalesce(provider_receipt, '{}'::jsonb) || jsonb_build_object(
              'control_kind', 'trigger_probation_digest',
              'deferred_event_count', v_deferred_count,
              'active_incident_id', v_active_incident_id,
              'latest_event_id', v_event_id,
              'deferred_until', v_probation_until,
              'policy_id', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1'
            )
        where notification_id = v_notification_id;
      else
        insert into os_v2.notifications(
          channel, recipient, subject, body, severity, state, available_at,
          provider_receipt, trigger_ref
        ) values (
          'email', v_pref.recipient,
          '[CrownThrive System] PentaCertify changes held during trigger probation',
          format(
            'CrownThrive retained one PentaCertify change notification while the causal trigger is on probation. It is coalesced into this digest until %s. Latest change: %s No provider call is permitted before the governed release boundary.',
            v_probation_until, v_summary
          ),
          v_sev, 'queued', v_probation_until,
          jsonb_build_object(
            'control_kind', 'trigger_probation_digest',
            'deferred_event_count', 1,
            'active_incident_id', v_active_incident_id,
            'latest_event_id', v_event_id,
            'deferred_until', v_probation_until,
            'policy_id', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1'
          ),
          v_trigger_ref
        ) returning notification_id into v_notification_id;
      end if;
      update os_v2.system_change_events
      set notification_id = v_notification_id
      where event_id = v_event_id;
    end if;
    return new;
  end if;
  v_change := os_v2.record_system_change(
    'PentaCertify',
    'provider_certification_state_changed',
    new.surface_id,
    v_sev,
    v_title,
    v_summary,
    jsonb_build_object(
      'provider_system', new.provider_system,
      'surface_id', new.surface_id,
      'from', old.certification_state,
      'to', new.certification_state,
      'missing_requirements', new.missing_requirements,
      'trigger_ref', v_trigger_ref
    ),
    'provider_cert:' || new.surface_id || ':' || new.certification_state || ':' ||
      extract(epoch from new.updated_at)::bigint::text
  );
  if nullif(v_change ->> 'notification_id', '') is not null then
    update os_v2.notifications
    set trigger_ref = v_trigger_ref
    where notification_id = (v_change ->> 'notification_id')::uuid;
  end if;
  return new;
end
$$;

create or replace function os_v2.mark_system_change_notification_sent_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, os_v2
as $$
begin
  if new.state = 'sent' and old.state is distinct from new.state then
    update os_v2.system_change_events
    set notified_at = coalesce(notified_at, new.sent_at, clock_timestamp())
    where notification_id = new.notification_id;
  end if;
  return new;
end
$$;

drop trigger if exists trg_os_v2_mark_system_change_notification_sent_v1
  on os_v2.notifications;
create trigger trg_os_v2_mark_system_change_notification_sent_v1
after update of state on os_v2.notifications
for each row execute function os_v2.mark_system_change_notification_sent_v1();

comment on column os_v2.notifications.trigger_ref is
  'Stable causal trigger identity propagated to the governed Mailgun relay; unrelated notification sources retain os-v2:notification.';
