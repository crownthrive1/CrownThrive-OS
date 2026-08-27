-- PentaMail Mailgun probation queue control v1.2.0
-- Founder acceptance: ct-founder-directive-pentamail-provider-probation-20260826-v1
-- Policy: hold the Mailgun route for at least three hours, require an enabled
-- provider readback, then release at two messages per dispatch and ten per
-- rolling hour. The causal trigger remains quarantined for 72 hours.

create schema if not exists integration_control;

create table if not exists integration_control.penta_mail_provider_incidents_v1 (
  incident_id uuid primary key default gen_random_uuid(),
  provider_route_id text not null default 'mailgun:relay.crownthrive.com',
  provider_event_id text not null,
  provider_event_sha256 text not null check (provider_event_sha256 ~ '^[0-9a-f]{64}$'),
  incident_type text not null default 'account_probation_temporary_disable'
    check (incident_type = 'account_probation_temporary_disable'),
  evidence_kind text not null
    check (evidence_kind in ('signed_webhook','authenticated_provider_response','founder_accepted_notice')),
  trigger_ref text not null,
  retry_after_seconds integer check (retry_after_seconds between 1 and 86400),
  observed_at timestamptz not null,
  provider_enable_estimate timestamptz,
  hold_until timestamptz not null,
  probation_until timestamptz not null,
  authority_ref text not null,
  policy_version text not null default '1.0.0',
  created_at timestamptz not null default now(),
  unique (provider_route_id, provider_event_id),
  check (hold_until >= observed_at + interval '3 hours'),
  check (probation_until >= observed_at + interval '72 hours')
);

create table if not exists integration_control.penta_mail_provider_control_v1 (
  provider_route_id text primary key,
  state text not null check (state in ('open','awaiting_provider_readback','controlled_release','closed')),
  active_incident_id uuid references integration_control.penta_mail_provider_incidents_v1(incident_id),
  hold_started_at timestamptz not null,
  hold_until timestamptz not null,
  readback_required_after timestamptz not null,
  enabled_readback_at timestamptz,
  last_readback_at timestamptz,
  last_readback_enabled boolean,
  last_readback_http_status integer,
  last_readback_sha256 text check (last_readback_sha256 is null or last_readback_sha256 ~ '^[0-9a-f]{64}$'),
  updated_at timestamptz not null default now(),
  check (hold_until >= hold_started_at + interval '3 hours'),
  check (readback_required_after >= hold_until),
  check (enabled_readback_at is null or enabled_readback_at >= readback_required_after),
  check (
    state <> 'controlled_release' or (
      enabled_readback_at is not null
      and last_readback_enabled is true
      and last_readback_at is not distinct from enabled_readback_at
    )
  )
);

create table if not exists integration_control.penta_mail_trigger_probation_v1 (
  trigger_ref text primary key,
  active_incident_id uuid not null references integration_control.penta_mail_provider_incidents_v1(incident_id),
  started_at timestamptz not null,
  probation_until timestamptz not null,
  reason_code text not null default 'mailgun_account_probation',
  policy_version text not null default '1.0.0',
  updated_at timestamptz not null default now(),
  check (probation_until >= started_at + interval '72 hours')
);

create table if not exists integration_control.penta_mail_provider_events_v1 (
  event_key text primary key,
  event_type text not null,
  incident_id uuid references integration_control.penta_mail_provider_incidents_v1(incident_id),
  trigger_ref text,
  payload jsonb not null default '{}'::jsonb,
  event_sha256 text not null check (event_sha256 ~ '^[0-9a-f]{64}$'),
  authority_ref text not null,
  created_at timestamptz not null default now()
);

create table if not exists integration_control.penta_mail_rate_reservations_v1 (
  reservation_id uuid primary key default gen_random_uuid(),
  provider_route_id text not null default 'mailgun:relay.crownthrive.com',
  request_key text not null,
  trigger_ref text not null,
  reserved_at timestamptz not null default clock_timestamp(),
  unique (provider_route_id, request_key)
);

create index if not exists penta_mail_provider_incidents_route_time_idx
  on integration_control.penta_mail_provider_incidents_v1(provider_route_id, observed_at desc);
create index if not exists penta_mail_trigger_probation_until_idx
  on integration_control.penta_mail_trigger_probation_v1(probation_until);
create index if not exists penta_mail_rate_reservations_window_idx
  on integration_control.penta_mail_rate_reservations_v1(provider_route_id, reserved_at);

alter table integration_control.penta_mail_provider_incidents_v1 enable row level security;
alter table integration_control.penta_mail_provider_control_v1 enable row level security;
alter table integration_control.penta_mail_trigger_probation_v1 enable row level security;
alter table integration_control.penta_mail_provider_events_v1 enable row level security;
alter table integration_control.penta_mail_rate_reservations_v1 enable row level security;

revoke all on integration_control.penta_mail_provider_incidents_v1 from public, anon, authenticated;
revoke all on integration_control.penta_mail_provider_control_v1 from public, anon, authenticated;
revoke all on integration_control.penta_mail_trigger_probation_v1 from public, anon, authenticated;
revoke all on integration_control.penta_mail_provider_events_v1 from public, anon, authenticated;
revoke all on integration_control.penta_mail_rate_reservations_v1 from public, anon, authenticated;
grant select on integration_control.penta_mail_provider_incidents_v1 to service_role;
grant select on integration_control.penta_mail_provider_control_v1 to service_role;
grant select on integration_control.penta_mail_trigger_probation_v1 to service_role;
grant select on integration_control.penta_mail_provider_events_v1 to service_role;
grant select on integration_control.penta_mail_rate_reservations_v1 to service_role;

create or replace function integration_control.penta_mail_reject_evidence_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  raise exception 'PENTAMAIL_CONTROL_EVIDENCE_APPEND_ONLY';
end
$$;

drop trigger if exists penta_mail_incidents_append_only on integration_control.penta_mail_provider_incidents_v1;
create trigger penta_mail_incidents_append_only
before update or delete on integration_control.penta_mail_provider_incidents_v1
for each row execute function integration_control.penta_mail_reject_evidence_mutation_v1();

drop trigger if exists penta_mail_provider_events_append_only on integration_control.penta_mail_provider_events_v1;
create trigger penta_mail_provider_events_append_only
before update or delete on integration_control.penta_mail_provider_events_v1
for each row execute function integration_control.penta_mail_reject_evidence_mutation_v1();

drop trigger if exists penta_mail_rate_reservations_append_only on integration_control.penta_mail_rate_reservations_v1;
create trigger penta_mail_rate_reservations_append_only
before update or delete on integration_control.penta_mail_rate_reservations_v1
for each row execute function integration_control.penta_mail_reject_evidence_mutation_v1();

alter table public.penta_mail_outbox_v1
  add column if not exists trigger_ref text,
  add column if not exists lease_id uuid,
  add column if not exists lease_expires_at timestamptz;

alter table integration_control.penta_mail_outbox_receipts_v1
  add column if not exists trigger_ref text,
  add column if not exists available_at timestamptz,
  add column if not exists lease_id uuid,
  add column if not exists lease_expires_at timestamptz;

create index if not exists penta_mail_outbox_trigger_state_idx
  on public.penta_mail_outbox_v1(trigger_ref, state, available_at);
create index if not exists penta_mail_outbox_lease_idx
  on public.penta_mail_outbox_v1(lease_expires_at)
  where state = 'dispatching';

create or replace function integration_control.penta_mail_assert_service_role_v1()
returns void
language plpgsql
security definer
set search_path = pg_catalog
as $$
declare
  v_role text := coalesce(current_setting('request.jwt.claim.role', true), '');
begin
  if session_user not in ('postgres','service_role') and v_role <> 'service_role' then
    raise exception 'PENTAMAIL_SERVICE_ROLE_REQUIRED';
  end if;
end
$$;

create or replace function integration_control.penta_mail_resolve_trigger_ref_v1(
  p_metadata jsonb,
  p_message_type text
)
returns text
language sql
immutable
set search_path = pg_catalog
as $$
  select left(coalesce(
    nullif(btrim(p_metadata ->> 'trigger_ref'), ''),
    nullif(btrim(p_metadata ->> 'trigger_key'), ''),
    nullif(btrim(p_metadata ->> 'condition_key'), ''),
    nullif(btrim(p_metadata ->> 'source_schedule'), ''),
    'message-type:' || lower(coalesce(nullif(btrim(p_message_type), ''), 'system'))
  ), 200)
$$;

update public.penta_mail_outbox_v1
set trigger_ref = integration_control.penta_mail_resolve_trigger_ref_v1(metadata, message_type),
    metadata = metadata || jsonb_build_object(
      'trigger_ref', integration_control.penta_mail_resolve_trigger_ref_v1(metadata, message_type),
      'trigger_ref_backfilled_by', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
    ),
    updated_at = now()
where trigger_ref is null;

alter table public.penta_mail_outbox_v1 alter column trigger_ref set not null;

create or replace function integration_control.penta_mail_capture_outbox_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control, extensions
as $$
declare
  v_prev text;
  v_sources jsonb;
  v_payload jsonb;
  v_chain text;
  v_before text;
  v_event text;
  v_created timestamptz := clock_timestamp();
begin
  perform pg_advisory_xact_lock(hashtext('integration_control.penta_mail_outbox_receipt_chain.v1'));
  select chain_sha256 into v_prev
  from integration_control.penta_mail_outbox_receipts_v1
  order by created_at desc, receipt_id desc
  limit 1;
  v_sources := integration_control.penta_mail_source_pentas_v1(new.metadata, new.message_type);
  if tg_op = 'INSERT' then
    v_before := null;
    v_event := 'queued';
  else
    v_before := old.state;
    v_event := 'state_transition';
  end if;
  v_payload := jsonb_build_object(
    'message_id', new.message_id,
    'message_type', new.message_type,
    'severity', new.severity,
    'recipient', new.recipient,
    'subject', new.subject,
    'dedupe_key', new.dedupe_key,
    'trigger_ref', new.trigger_ref,
    'state_before', v_before,
    'state_after', new.state,
    'attempt_count', new.attempt_count,
    'available_at', new.available_at,
    'lease_id', new.lease_id,
    'lease_expires_at', new.lease_expires_at,
    'provider_message_id', new.provider_message_id,
    'provider_http_status', new.provider_http_status,
    'sent_at', new.sent_at,
    'last_error', new.last_error,
    'source_pentas', v_sources,
    'body_sha256', encode(extensions.digest(convert_to(new.body_text, 'UTF8'), 'sha256'), 'hex'),
    'metadata', new.metadata
  );
  v_chain := encode(extensions.digest(convert_to(
    coalesce(v_prev, 'GENESIS') || '|' || new.message_id::text || '|' || v_event || '|' ||
    v_payload::text || '|' || v_created::text, 'UTF8'), 'sha256'), 'hex');
  insert into integration_control.penta_mail_outbox_receipts_v1(
    message_id, event_kind, message_type, severity, recipient, subject, dedupe_key,
    source_pentas, trigger_ref, state_before, state_after, attempt_count, available_at,
    lease_id, lease_expires_at, provider_message_id, provider_http_status, sent_at,
    last_error, metadata, previous_chain_sha256, chain_sha256, created_at
  ) values (
    new.message_id, v_event, new.message_type, new.severity, new.recipient, new.subject,
    new.dedupe_key, v_sources, new.trigger_ref, v_before, new.state, new.attempt_count,
    new.available_at, new.lease_id, new.lease_expires_at, new.provider_message_id,
    new.provider_http_status, new.sent_at, new.last_error, new.metadata, v_prev, v_chain, v_created
  );
  return new;
end
$$;

drop trigger if exists penta_mail_outbox_update_capture on public.penta_mail_outbox_v1;
create trigger penta_mail_outbox_update_capture
after update on public.penta_mail_outbox_v1
for each row when (
  old.state is distinct from new.state
  or old.attempt_count is distinct from new.attempt_count
  or old.available_at is distinct from new.available_at
  or old.trigger_ref is distinct from new.trigger_ref
  or old.lease_id is distinct from new.lease_id
  or old.lease_expires_at is distinct from new.lease_expires_at
  or old.provider_message_id is distinct from new.provider_message_id
  or old.provider_http_status is distinct from new.provider_http_status
  or old.sent_at is distinct from new.sent_at
  or old.last_error is distinct from new.last_error
  or old.metadata is distinct from new.metadata
)
execute function integration_control.penta_mail_capture_outbox_v1();

create or replace function integration_control.penta_mail_append_control_event_v1(
  p_event_key text,
  p_event_type text,
  p_incident_id uuid,
  p_trigger_ref text,
  p_payload jsonb,
  p_authority_ref text
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, extensions, integration_control, chlom_runtime
as $$
declare
  v_sha text;
  v_existing text;
begin
  if length(coalesce(p_event_key, '')) = 0 or length(p_event_key) > 300 then
    raise exception 'PENTAMAIL_INVALID_CONTROL_EVENT_KEY';
  end if;
  v_sha := encode(extensions.digest(convert_to(
    p_event_key || '|' || p_event_type || '|' || coalesce(p_payload, '{}'::jsonb)::text,
    'UTF8'), 'sha256'), 'hex');
  select event_sha256 into v_existing
  from integration_control.penta_mail_provider_events_v1
  where event_key = p_event_key;
  if found then
    if v_existing <> v_sha then
      raise exception 'PENTAMAIL_CONTROL_EVENT_CONFLICT';
    end if;
    return false;
  end if;
  insert into integration_control.penta_mail_provider_events_v1(
    event_key, event_type, incident_id, trigger_ref, payload, event_sha256, authority_ref
  ) values (
    p_event_key, p_event_type, p_incident_id, p_trigger_ref,
    coalesce(p_payload, '{}'::jsonb), v_sha, p_authority_ref
  );
  perform chlom_runtime.append_dail_event(
    p_event_type => p_event_type,
    p_entity_type => 'penta_mail_provider_control',
    p_entity_id => coalesce(p_trigger_ref, 'mailgun:relay.crownthrive.com'),
    p_payload => coalesce(p_payload, '{}'::jsonb) || jsonb_build_object('control_event_sha256', v_sha),
    p_actor_ref => 'ct.penta.mail.v1',
    p_agent_id => 'penta-mail',
    p_entity_version => '1.2.0',
    p_correlation_id => p_incident_id::text,
    p_authority_basis => p_authority_ref,
    p_approval_id => 'ct-founder-directive-pentamail-provider-probation-20260826-v1',
    p_visibility_class => 'internal'
  );
  return true;
end
$$;

create or replace function public.penta_mail_provider_status_v1(p_trigger_ref text default null)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_control integration_control.penta_mail_provider_control_v1%rowtype;
  v_probation_until timestamptz;
  v_now timestamptz := clock_timestamp();
  v_state text;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  if not found then
    v_state := 'closed';
  elsif v_now < v_control.hold_until then
    v_state := 'open';
  elsif v_control.state <> 'controlled_release'
    or v_control.last_readback_enabled is not true
    or v_control.enabled_readback_at is null
    or v_control.enabled_readback_at < v_control.readback_required_after
    or v_control.last_readback_at is distinct from v_control.enabled_readback_at then
    v_state := 'awaiting_provider_readback';
  else
    v_state := 'controlled_release';
  end if;
  if nullif(btrim(coalesce(p_trigger_ref, '')), '') is not null then
    select probation_until into v_probation_until
    from integration_control.penta_mail_trigger_probation_v1
    where trigger_ref = p_trigger_ref and probation_until > v_now;
  end if;
  return jsonb_build_object(
    'provider_route_id', 'mailgun:relay.crownthrive.com',
    'route_state', v_state,
    'active_incident_id', v_control.active_incident_id,
    'hold_until', v_control.hold_until,
    'readback_required_after', v_control.readback_required_after,
    'enabled_readback_at', v_control.enabled_readback_at,
    'last_readback_at', v_control.last_readback_at,
    'last_readback_enabled', v_control.last_readback_enabled,
    'seconds_until_hold_boundary', greatest(0, ceil(extract(epoch from (coalesce(v_control.hold_until, v_now) - v_now)))::integer),
    'provider_readback_required', v_state = 'awaiting_provider_readback',
    'trigger_ref', p_trigger_ref,
    'trigger_state', case when v_probation_until is not null then 'probation' else 'eligible' end,
    'trigger_probation_until', v_probation_until,
    'controlled_batch_size', 2,
    'rolling_hour_limit', 10,
    'policy_id', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1',
    'policy_version', '1.0.0',
    'as_of', v_now
  );
end
$$;

create or replace function public.penta_mail_accept_mailgun_probation_v1(
  p_provider_event_id text,
  p_provider_event_sha256 text,
  p_trigger_ref text,
  p_retry_after_seconds integer default null,
  p_evidence_kind text default 'authenticated_provider_response',
  p_authority_ref text default 'ct-founder-directive-pentamail-provider-probation-20260826-v1'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_existing integration_control.penta_mail_provider_incidents_v1%rowtype;
  v_incident_id uuid := gen_random_uuid();
  v_now timestamptz := clock_timestamp();
  v_retry integer;
  v_provider_estimate timestamptz;
  v_hold_until timestamptz;
  v_probation_until timestamptz;
  v_trigger text := btrim(coalesce(p_trigger_ref, ''));
  v_enforced_triggers text[];
  v_enforced_trigger text;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if length(coalesce(p_provider_event_id, '')) = 0 or length(p_provider_event_id) > 240 then
    raise exception 'PENTAMAIL_INVALID_PROVIDER_EVENT_ID';
  end if;
  if coalesce(p_provider_event_sha256, '') !~ '^[0-9a-f]{64}$' then
    raise exception 'PENTAMAIL_INVALID_PROVIDER_EVENT_SHA256';
  end if;
  if v_trigger !~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$' then
    raise exception 'PENTAMAIL_INVALID_TRIGGER_REF';
  end if;
  if p_evidence_kind not in ('signed_webhook','authenticated_provider_response','founder_accepted_notice') then
    raise exception 'PENTAMAIL_INVALID_EVIDENCE_KIND';
  end if;
  v_enforced_triggers := case
    when v_trigger in (
      'mailgun-relay:notifications',
      'db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1'
    ) then array[
      'mailgun-relay:notifications',
      'db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1'
    ]::text[]
    else array[v_trigger]::text[]
  end;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:probation-control'));
  select * into v_existing
  from integration_control.penta_mail_provider_incidents_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
    and provider_event_id = p_provider_event_id;
  if found then
    if v_existing.provider_event_sha256 <> p_provider_event_sha256
      or v_existing.trigger_ref <> v_trigger
      or v_existing.evidence_kind <> p_evidence_kind
      or v_existing.authority_ref <> p_authority_ref then
      raise exception 'PENTAMAIL_PROVIDER_EVENT_CONFLICT';
    end if;
    return public.penta_mail_provider_status_v1(v_trigger) || jsonb_build_object(
      'incident_id', v_existing.incident_id,
      'idempotent_replay', true
    );
  end if;
  v_retry := case when p_retry_after_seconds is null then null
    else greatest(1, least(p_retry_after_seconds, 86400)) end;
  v_provider_estimate := case when v_retry is null then null
    else v_now + make_interval(secs => v_retry) end;
  v_hold_until := greatest(v_now + interval '3 hours', coalesce(v_provider_estimate, v_now));
  v_probation_until := v_now + interval '72 hours';
  insert into integration_control.penta_mail_provider_incidents_v1(
    incident_id, provider_route_id, provider_event_id, provider_event_sha256,
    evidence_kind, trigger_ref, retry_after_seconds, observed_at,
    provider_enable_estimate, hold_until, probation_until, authority_ref
  ) values (
    v_incident_id, 'mailgun:relay.crownthrive.com', p_provider_event_id,
    p_provider_event_sha256, p_evidence_kind, v_trigger, v_retry, v_now,
    v_provider_estimate, v_hold_until, v_probation_until, p_authority_ref
  );
  insert into integration_control.penta_mail_provider_control_v1(
    provider_route_id, state, active_incident_id, hold_started_at, hold_until,
    readback_required_after, enabled_readback_at, updated_at
  ) values (
    'mailgun:relay.crownthrive.com', 'open', v_incident_id, v_now, v_hold_until,
    v_hold_until, null, v_now
  )
  on conflict (provider_route_id) do update set
    state = 'open',
    active_incident_id = excluded.active_incident_id,
    hold_started_at = least(integration_control.penta_mail_provider_control_v1.hold_started_at, excluded.hold_started_at),
    hold_until = greatest(integration_control.penta_mail_provider_control_v1.hold_until, excluded.hold_until),
    readback_required_after = greatest(integration_control.penta_mail_provider_control_v1.readback_required_after, excluded.readback_required_after),
    enabled_readback_at = null,
    last_readback_at = null,
    last_readback_enabled = null,
    last_readback_http_status = null,
    last_readback_sha256 = null,
    updated_at = excluded.updated_at;
  foreach v_enforced_trigger in array v_enforced_triggers loop
    insert into integration_control.penta_mail_trigger_probation_v1(
      trigger_ref, active_incident_id, started_at, probation_until, updated_at
    ) values (v_enforced_trigger, v_incident_id, v_now, v_probation_until, v_now)
    on conflict (trigger_ref) do update set
      active_incident_id = excluded.active_incident_id,
      started_at = least(integration_control.penta_mail_trigger_probation_v1.started_at, excluded.started_at),
      probation_until = greatest(integration_control.penta_mail_trigger_probation_v1.probation_until, excluded.probation_until),
      updated_at = excluded.updated_at;
  end loop;
  update public.penta_mail_outbox_v1
  set state = 'held',
      available_at = greatest(available_at, v_hold_until),
      lease_id = null,
      lease_expires_at = null,
      metadata = metadata || jsonb_build_object(
        'trigger_ref', trigger_ref,
        'provider_hold_policy', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0',
        'provider_hold_reason', 'mailgun_account_probation',
        'provider_hold_until', v_hold_until,
        'provider_incident_id', v_incident_id
      ),
      updated_at = v_now
  where state in ('queued','pending','retry','held');
  perform integration_control.penta_mail_append_control_event_v1(
    'incident:' || v_incident_id::text || ':accepted',
    'mailgun.probation.accepted',
    v_incident_id,
    v_trigger,
    jsonb_build_object(
      'provider_route_id', 'mailgun:relay.crownthrive.com',
      'evidence_kind', p_evidence_kind,
      'provider_event_sha256', p_provider_event_sha256,
      'retry_after_seconds', v_retry,
      'hold_until', v_hold_until,
      'probation_until', v_probation_until,
      'enforced_trigger_refs', to_jsonb(v_enforced_triggers),
      'raw_provider_body_retained', false
    ),
    p_authority_ref
  );
  perform integration_control.penta_mail_append_control_event_v1(
    'incident:' || v_incident_id::text || ':route-hold',
    'mail.queue.hold_started',
    v_incident_id,
    v_trigger,
    jsonb_build_object('hold_until', v_hold_until, 'minimum_hold_seconds', 10800),
    p_authority_ref
  );
  return public.penta_mail_provider_status_v1(v_trigger) || jsonb_build_object(
    'incident_id', v_incident_id,
    'idempotent_replay', false,
    'provider_enable_estimate', v_provider_estimate,
    'trigger_probation_until', v_probation_until
  );
end
$$;

create or replace function public.penta_mail_record_mailgun_readback_v1(
  p_readback_event_id text,
  p_enabled boolean,
  p_regular_disabled boolean,
  p_scheduled_disabled boolean,
  p_provider_http_status integer,
  p_response_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_control integration_control.penta_mail_provider_control_v1%rowtype;
  v_now timestamptz := clock_timestamp();
  v_verified_enabled boolean;
  v_new_event boolean;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if length(coalesce(p_readback_event_id, '')) = 0 or length(p_readback_event_id) > 240 then
    raise exception 'PENTAMAIL_INVALID_READBACK_EVENT_ID';
  end if;
  if coalesce(p_response_sha256, '') !~ '^[0-9a-f]{64}$' then
    raise exception 'PENTAMAIL_INVALID_READBACK_SHA256';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:probation-control'));
  select * into v_control
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
  for update;
  if not found then
    return public.penta_mail_provider_status_v1(null) || jsonb_build_object('readback_recorded', false, 'reason', 'no_active_control');
  end if;
  v_verified_enabled := coalesce(p_enabled, false)
    and coalesce(p_provider_http_status, 0) between 200 and 299
    and not coalesce(p_regular_disabled, true)
    and not coalesce(p_scheduled_disabled, true);
  v_new_event := integration_control.penta_mail_append_control_event_v1(
    'readback:' || p_readback_event_id,
    'mail.provider_readback',
    v_control.active_incident_id,
    null,
    jsonb_build_object(
      'provider_route_id', 'mailgun:relay.crownthrive.com',
      'enabled', v_verified_enabled,
      'regular_disabled', p_regular_disabled,
      'scheduled_disabled', p_scheduled_disabled,
      'provider_http_status', p_provider_http_status,
      'response_sha256', p_response_sha256,
      'raw_provider_body_retained', false
    ),
    'ct-founder-directive-pentamail-provider-probation-20260826-v1'
  );
  if not v_new_event then
    return public.penta_mail_provider_status_v1(null) || jsonb_build_object('readback_recorded', false, 'idempotent_replay', true);
  end if;
  update integration_control.penta_mail_provider_control_v1
  set last_readback_at = v_now,
      last_readback_enabled = v_verified_enabled,
      last_readback_http_status = p_provider_http_status,
      last_readback_sha256 = p_response_sha256,
      enabled_readback_at = case
        when v_verified_enabled and v_now >= readback_required_after then v_now
        else null
      end,
      state = case
        when v_now < hold_until then 'open'
        when v_verified_enabled and v_now >= readback_required_after then 'controlled_release'
        else 'awaiting_provider_readback'
      end,
      updated_at = v_now
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  if v_verified_enabled and v_now >= v_control.readback_required_after then
    update public.penta_mail_outbox_v1 o
    set state = case when exists (
          select 1 from integration_control.penta_mail_trigger_probation_v1 p
          where p.trigger_ref = o.trigger_ref and p.probation_until > v_now
        ) then 'held' else 'queued' end,
        available_at = case when exists (
          select 1 from integration_control.penta_mail_trigger_probation_v1 p
          where p.trigger_ref = o.trigger_ref and p.probation_until > v_now
        ) then greatest(o.available_at, (
          select p.probation_until from integration_control.penta_mail_trigger_probation_v1 p
          where p.trigger_ref = o.trigger_ref
        )) else greatest(o.available_at, v_now) end,
        metadata = o.metadata || jsonb_build_object(
          'provider_release_readback_at', v_now,
          'provider_release_readback_sha256', p_response_sha256,
          'provider_release_mode', 'controlled'
        ),
        updated_at = v_now
    where o.state = 'held'
      and o.metadata ->> 'provider_hold_policy' = 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0';
    perform integration_control.penta_mail_append_control_event_v1(
      'readback:' || p_readback_event_id || ':controlled-release',
      'mail.controlled_release_started',
      v_control.active_incident_id,
      null,
      jsonb_build_object('batch_size', 2, 'rolling_hour_limit', 10, 'enabled_readback_at', v_now),
      'ct-founder-directive-pentamail-provider-probation-20260826-v1'
    );
  end if;
  return public.penta_mail_provider_status_v1(null) || jsonb_build_object('readback_recorded', true, 'verified_enabled', v_verified_enabled);
end
$$;

create or replace function integration_control.penta_mail_reconcile_trigger_probation_v1()
returns integer
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_row record;
  v_count integer := 0;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  for v_row in
    select p.trigger_ref, p.active_incident_id, p.probation_until
    from integration_control.penta_mail_trigger_probation_v1 p
    where p.probation_until <= clock_timestamp()
  loop
    if integration_control.penta_mail_append_control_event_v1(
      'probation:' || v_row.trigger_ref || ':' || extract(epoch from v_row.probation_until)::bigint::text || ':expired',
      'mail.trigger_probation_expired',
      v_row.active_incident_id,
      v_row.trigger_ref,
      jsonb_build_object('probation_until', v_row.probation_until),
      'ct-founder-directive-pentamail-provider-probation-20260826-v1'
    ) then
      v_count := v_count + 1;
    end if;
  end loop;
  return v_count;
end
$$;

create or replace function public.penta_mail_reserve_mailgun_rate_v1(
  p_request_key text,
  p_trigger_ref text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_status jsonb;
  v_count integer;
  v_oldest timestamptz;
  v_now timestamptz := clock_timestamp();
  v_existing timestamptz;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  if length(coalesce(p_request_key, '')) = 0 or length(p_request_key) > 240 then
    raise exception 'PENTAMAIL_INVALID_RATE_REQUEST_KEY';
  end if;
  if coalesce(p_trigger_ref, '') !~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$' then
    raise exception 'PENTAMAIL_INVALID_TRIGGER_REF';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:rolling-hour-rate'));
  v_status := public.penta_mail_provider_status_v1(p_trigger_ref);
  if v_status ->> 'route_state' <> 'controlled_release' and v_status ->> 'route_state' <> 'closed' then
    return jsonb_build_object(
      'allowed', false,
      'reason', 'provider_circuit_' || (v_status ->> 'route_state'),
      'retry_at', v_status ->> 'hold_until',
      'control', v_status
    );
  end if;
  if v_status ->> 'trigger_state' = 'probation' then
    return jsonb_build_object(
      'allowed', false,
      'reason', 'trigger_probation',
      'retry_at', v_status ->> 'trigger_probation_until',
      'control', v_status
    );
  end if;
  select reserved_at into v_existing
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com' and request_key = p_request_key;
  if found then
    return jsonb_build_object('allowed', false, 'reason', 'request_already_reserved', 'reserved_at', v_existing);
  end if;
  select count(*)::integer, min(reserved_at)
  into v_count, v_oldest
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
    and reserved_at > v_now - interval '1 hour';
  if v_count >= 10 then
    return jsonb_build_object(
      'allowed', false,
      'reason', 'rolling_hour_limit',
      'window_count', v_count,
      'rolling_hour_limit', 10,
      'retry_at', v_oldest + interval '1 hour'
    );
  end if;
  insert into integration_control.penta_mail_rate_reservations_v1(
    provider_route_id, request_key, trigger_ref, reserved_at
  ) values ('mailgun:relay.crownthrive.com', p_request_key, p_trigger_ref, v_now);
  return jsonb_build_object(
    'allowed', true,
    'window_count', v_count + 1,
    'remaining', 9 - v_count,
    'rolling_hour_limit', 10,
    'window_seconds', 3600,
    'reserved_at', v_now
  );
end
$$;

create or replace function public.penta_mail_claim_outbox_v2(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_status jsonb;
  v_now timestamptz := clock_timestamp();
  v_limit integer := greatest(1, least(coalesce(p_limit, 2), 2));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('public.penta_mail_claim_outbox_v2'));
  perform integration_control.penta_mail_reconcile_trigger_probation_v1();
  v_status := public.penta_mail_provider_status_v1(null);
  if v_status ->> 'route_state' not in ('closed','controlled_release') then
    return;
  end if;
  update public.penta_mail_outbox_v1 o
  set state = 'queued',
      available_at = greatest(o.available_at, v_now),
      metadata = o.metadata || jsonb_build_object(
        'provider_release_mode', 'controlled',
        'trigger_probation_expired_at', v_now
      ),
      updated_at = v_now
  where o.state = 'held'
    and o.metadata ->> 'provider_hold_policy' = 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0'
    and not exists (
      select 1 from integration_control.penta_mail_trigger_probation_v1 p
      where p.trigger_ref = o.trigger_ref and p.probation_until > v_now
    );
  update public.penta_mail_outbox_v1
  set state = 'retry', lease_id = null, lease_expires_at = null,
      available_at = greatest(available_at, v_now),
      metadata = metadata || jsonb_build_object('lease_recovered_at', v_now),
      updated_at = v_now
  where state = 'dispatching' and lease_expires_at <= v_now;
  return query
  with candidates as (
    select o.message_id
    from public.penta_mail_outbox_v1 o
    where o.state in ('queued','pending','retry')
      and o.available_at <= v_now
      and not exists (
        select 1 from integration_control.penta_mail_trigger_probation_v1 p
        where p.trigger_ref = o.trigger_ref and p.probation_until > v_now
      )
    order by case upper(o.severity)
      when 'CRITICAL' then 1 when 'HIGH' then 2 when 'MEDIUM' then 3 else 4 end,
      o.created_at asc
    for update skip locked
    limit v_limit
  ), leases as (
    select message_id, gen_random_uuid() as lease_id from candidates
  )
  update public.penta_mail_outbox_v1 o
  set state = 'dispatching',
      lease_id = l.lease_id,
      lease_expires_at = v_now + interval '5 minutes',
      metadata = o.metadata || jsonb_build_object(
        'claimed_at', v_now,
        'controlled_release_batch_limit', 2
      ),
      updated_at = v_now
  from leases l
  where o.message_id = l.message_id
  returning o.*;
end
$$;

create or replace function public.penta_mail_complete_outbox_v2(
  p_message_id uuid,
  p_lease_id uuid,
  p_ok boolean,
  p_provider_call_made boolean,
  p_provider_http_status integer default null,
  p_provider_message_id text default null,
  p_error text default null,
  p_retry_after_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_row public.penta_mail_outbox_v1%rowtype;
  v_status jsonb;
  v_now timestamptz := clock_timestamp();
  v_attempts integer;
  v_state text;
  v_next timestamptz;
  v_trigger_until timestamptz;
  v_retry integer := greatest(60, least(coalesce(p_retry_after_seconds, 300), 86400));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select * into v_row
  from public.penta_mail_outbox_v1
  where message_id = p_message_id
  for update;
  if not found or v_row.state <> 'dispatching' or v_row.lease_id is distinct from p_lease_id then
    raise exception 'PENTAMAIL_LEASE_MISMATCH';
  end if;
  v_attempts := v_row.attempt_count + case when coalesce(p_provider_call_made, false) then 1 else 0 end;
  v_status := public.penta_mail_provider_status_v1(v_row.trigger_ref);
  select probation_until into v_trigger_until
  from integration_control.penta_mail_trigger_probation_v1
  where trigger_ref = v_row.trigger_ref and probation_until > v_now;
  if coalesce(p_ok, false) then
    v_state := 'sent';
    v_next := v_now;
  elsif v_status ->> 'route_state' not in ('closed','controlled_release') or v_trigger_until is not null then
    v_state := 'held';
    v_next := greatest(
      v_now + make_interval(secs => v_retry),
      coalesce((v_status ->> 'hold_until')::timestamptz, v_now),
      coalesce(v_trigger_until, v_now)
    );
  elsif coalesce(p_provider_call_made, false) and v_attempts >= v_row.max_attempts then
    v_state := 'failed';
    v_next := v_now;
  else
    v_state := 'retry';
    v_next := v_now + make_interval(secs => v_retry);
  end if;
  update public.penta_mail_outbox_v1
  set state = v_state,
      attempt_count = v_attempts,
      available_at = v_next,
      lease_id = null,
      lease_expires_at = null,
      provider_message_id = left(nullif(p_provider_message_id, ''), 500),
      provider_http_status = p_provider_http_status,
      sent_at = case when v_state = 'sent' then v_now else sent_at end,
      last_error = case when v_state = 'sent' then null else left(coalesce(p_error, 'delivery_not_accepted'), 1000) end,
      metadata = metadata || jsonb_build_object(
        'last_provider_call_made', coalesce(p_provider_call_made, false),
        'last_completion_at', v_now,
        'last_control_state', v_status ->> 'route_state'
      ),
      updated_at = v_now
  where message_id = p_message_id;
  return jsonb_build_object(
    'message_id', p_message_id,
    'state', v_state,
    'attempt_count', v_attempts,
    'available_at', v_next,
    'provider_call_made', coalesce(p_provider_call_made, false),
    'control', v_status
  );
end
$$;

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
  if not public.penta_mail_recipient_allowed_v1(v_recipient) then raise exception 'PENTAMAIL_RECIPIENT_NOT_ALLOWLISTED'; end if;
  if length(coalesce(p_subject,'')) = 0 or length(p_subject) > 180 then raise exception 'PENTAMAIL_INVALID_SUBJECT'; end if;
  if length(coalesce(p_body_text,'')) = 0 or length(p_body_text) > 12000 then raise exception 'PENTAMAIL_INVALID_BODY'; end if;
  v_trigger := integration_control.penta_mail_resolve_trigger_ref_v1(v_metadata, p_message_type);
  if v_trigger !~ '^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$' then raise exception 'PENTAMAIL_INVALID_TRIGGER_REF'; end if;
  v_status := public.penta_mail_provider_status_v1(v_trigger);
  v_state := case when v_status ->> 'route_state' in ('closed','controlled_release')
    and v_status ->> 'trigger_state' = 'eligible' then 'queued' else 'held' end;
  if v_status ->> 'route_state' not in ('closed','controlled_release') then
    v_available_at := greatest(v_available_at, coalesce((v_status ->> 'hold_until')::timestamptz, v_available_at));
  end if;
  if v_status ->> 'trigger_state' = 'probation' then
    v_available_at := greatest(v_available_at, (v_status ->> 'trigger_probation_until')::timestamptz);
  end if;
  v_metadata := v_metadata || jsonb_build_object(
    'trigger_ref', v_trigger,
    'provider_control_state_at_enqueue', v_status ->> 'route_state',
    'provider_hold_policy', case when v_state = 'held' then 'ct.pentamailer.policy.mailgun-delivery-resilience.v1@1.0.0' else null end
  );
  insert into public.penta_mail_outbox_v1(
    message_type, severity, recipient, subject, body_text, dedupe_key, metadata,
    trigger_ref, state, available_at
  ) values (
    lower(coalesce(p_message_type,'system')), upper(coalesce(p_severity,'INFO')),
    v_recipient, p_subject, p_body_text, p_dedupe_key, v_metadata,
    v_trigger, v_state, v_available_at
  )
  on conflict(dedupe_key) where dedupe_key is not null do update set
    metadata = case when public.penta_mail_outbox_v1.state in ('dispatching','reconciliation_required')
      then public.penta_mail_outbox_v1.metadata
      else public.penta_mail_outbox_v1.metadata || excluded.metadata end,
    trigger_ref = case when public.penta_mail_outbox_v1.state in ('dispatching','reconciliation_required')
      then public.penta_mail_outbox_v1.trigger_ref else excluded.trigger_ref end,
    state = case
      when public.penta_mail_outbox_v1.state in ('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.state
      when excluded.state = 'held' then 'held'
      else public.penta_mail_outbox_v1.state
    end,
    available_at = case
      when public.penta_mail_outbox_v1.state in ('sent','failed','dispatching','reconciliation_required') then public.penta_mail_outbox_v1.available_at
      else greatest(public.penta_mail_outbox_v1.available_at, excluded.available_at)
    end,
    updated_at = now()
  returning message_id into v_id;
  return v_id;
end
$$;

revoke all on function public.penta_mail_provider_status_v1(text) from public, anon, authenticated;
revoke all on function public.penta_mail_accept_mailgun_probation_v1(text,text,text,integer,text,text) from public, anon, authenticated;
revoke all on function public.penta_mail_record_mailgun_readback_v1(text,boolean,boolean,boolean,integer,text) from public, anon, authenticated;
revoke all on function public.penta_mail_reserve_mailgun_rate_v1(text,text) from public, anon, authenticated;
revoke all on function public.penta_mail_claim_outbox_v2(integer) from public, anon, authenticated;
revoke all on function public.penta_mail_complete_outbox_v2(uuid,uuid,boolean,boolean,integer,text,text,integer) from public, anon, authenticated;
revoke all on function public.penta_mail_notification_recipient_v1() from public, anon, authenticated;
revoke all on function public.penta_mail_recipient_allowed_v1(text) from public, anon, authenticated;
revoke all on function public.penta_mail_admin_allowed_v1(text) from public, anon, authenticated;
revoke all on function public.penta_mail_enqueue_v1(text,text,text,text,text,jsonb,text) from public, anon, authenticated;
grant execute on function public.penta_mail_provider_status_v1(text) to service_role;
grant execute on function public.penta_mail_accept_mailgun_probation_v1(text,text,text,integer,text,text) to service_role;
grant execute on function public.penta_mail_record_mailgun_readback_v1(text,boolean,boolean,boolean,integer,text) to service_role;
grant execute on function public.penta_mail_reserve_mailgun_rate_v1(text,text) to service_role;
grant execute on function public.penta_mail_claim_outbox_v2(integer) to service_role;
grant execute on function public.penta_mail_complete_outbox_v2(uuid,uuid,boolean,boolean,integer,text,text,integer) to service_role;
grant execute on function public.penta_mail_notification_recipient_v1() to service_role;
grant execute on function public.penta_mail_recipient_allowed_v1(text) to service_role;
grant execute on function public.penta_mail_admin_allowed_v1(text) to service_role;
grant execute on function public.penta_mail_enqueue_v1(text,text,text,text,text,jsonb,text) to service_role;

revoke all on function integration_control.penta_mail_assert_service_role_v1() from public, anon, authenticated;
revoke all on function integration_control.penta_mail_append_control_event_v1(text,text,uuid,text,jsonb,text) from public, anon, authenticated;
revoke all on function integration_control.penta_mail_resolve_trigger_ref_v1(jsonb,text) from public, anon, authenticated;
revoke all on function integration_control.penta_mail_reconcile_trigger_probation_v1() from public, anon, authenticated;

insert into developer_commerce.founder_directives(
  directive_id, founder_ref, directive_class, scope, source_sha256,
  authority_effect, independent_evidence_substitution_allowed
) values (
  'ct-founder-directive-pentamail-provider-probation-20260826-v1',
  'Kavonte Jones Sr.',
  'business_policy',
  jsonb_build_object(
    'lane', 'pentamail_mailgun_delivery_resilience',
    'provider', 'Mailgun',
    'provider_route_id', 'mailgun:relay.crownthrive.com',
    'qualifying_notice', 'account probation with temporary disablement',
    'minimum_route_hold_seconds', 10800,
    'causal_trigger_probation_seconds', 259200,
    'current_causal_trigger_ref', 'db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1',
    'current_origin_job_ref', 'pg_cron:ct-penta-self-v1',
    'relay_enforcement_alias', 'mailgun-relay:notifications',
    'controlled_release_batch_size', 2,
    'rolling_hour_limit', 10,
    'provider_enabled_readback_required', true,
    'source_context', 'Founder instruction in authenticated ChatGPT work session on 2026-08-26',
    'authority_ceiling', 'D1_OPERATIONAL_POLICY',
    'raw_secret_exposure_allowed', false
  ),
  '402c9107402a369222a8dc38dc3d63003bc310122ee7077968502e7153f06c77',
  'Accept and enforce a minimum three-hour Mailgun route hold after authoritative probation or temporary-disable evidence, require provider-enabled readback before a bounded release, and quarantine only the causal trigger for 72 hours under an atomic ten-message rolling-hour ceiling.',
  false
)
on conflict (directive_id) do nothing;

-- Causal notification identity and coalesced probation-digest behavior are
-- installed by 20260827002646_os_v2_notification_trigger_identity.sql and
-- hardened for live reconciliation by the later concurrency migration.

comment on table integration_control.penta_mail_provider_incidents_v1 is
  'Append-only accepted Mailgun probation incidents, including founder-authorized protective activation; no raw provider body or secret is retained.';
comment on table integration_control.penta_mail_rate_reservations_v1 is
  'Append-only atomic global Mailgun send reservations enforcing 10 requests per rolling hour.';
comment on function public.penta_mail_accept_mailgun_probation_v1(text,text,text,integer,text,text) is
  'Idempotently opens the Mailgun route for at least three hours and places only the causal trigger on 72-hour probation.';
