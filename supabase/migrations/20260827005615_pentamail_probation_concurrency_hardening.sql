-- PentaMail Mailgun probation concurrency hardening v1.3.0
-- Adds a provider-attempt linearization point, fail-closed readback semantics,
-- immutable attempt custody, and service-role mutation boundaries.

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'penta_mail_provider_control_hold_floor_v1') then
    alter table integration_control.penta_mail_provider_control_v1
      add constraint penta_mail_provider_control_hold_floor_v1
      check (hold_until >= hold_started_at + interval '3 hours');
  end if;
  if not exists (select 1 from pg_constraint where conname = 'penta_mail_provider_control_readback_boundary_v1') then
    alter table integration_control.penta_mail_provider_control_v1
      add constraint penta_mail_provider_control_readback_boundary_v1
      check (readback_required_after >= hold_until);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'penta_mail_provider_control_enabled_readback_v1') then
    alter table integration_control.penta_mail_provider_control_v1
      add constraint penta_mail_provider_control_enabled_readback_v1
      check (
        state <> 'controlled_release' or (
          enabled_readback_at is not null
          and enabled_readback_at >= readback_required_after
          and enabled_readback_at is not distinct from last_readback_at
          and last_readback_enabled is true
        )
      );
  end if;
  if not exists (select 1 from pg_constraint where conname = 'penta_mail_provider_control_release_evidence_v1') then
    alter table integration_control.penta_mail_provider_control_v1
      add constraint penta_mail_provider_control_release_evidence_v1
      check (
        state <> 'controlled_release' or (
          enabled_readback_at is not null
          and enabled_readback_at >= readback_required_after
          and enabled_readback_at is not distinct from last_readback_at
          and last_readback_enabled is true
        )
      );
  end if;
end
$$;

create table if not exists integration_control.penta_mail_provider_attempts_v1 (
  attempt_id uuid primary key,
  provider_route_id text not null default 'mailgun:relay.crownthrive.com',
  request_key text not null,
  trigger_ref text not null,
  payload_sha256 text not null check (payload_sha256 ~ '^[0-9a-f]{64}$'),
  started_at timestamptz not null default clock_timestamp(),
  authority_ref text not null default 'ct-founder-directive-pentamail-provider-probation-20260826-v1',
  unique (provider_route_id, request_key),
  foreign key (provider_route_id, request_key)
    references integration_control.penta_mail_rate_reservations_v1(provider_route_id, request_key)
);

create table if not exists integration_control.penta_mail_provider_attempt_outcomes_v1 (
  attempt_id uuid primary key
    references integration_control.penta_mail_provider_attempts_v1(attempt_id),
  outcome_state text not null check (
    outcome_state in ('provider_accepted','definitive_failure','probation_detected','ambiguous','reconciled')
  ),
  provider_http_status integer,
  provider_message_id text,
  response_sha256 text not null check (response_sha256 ~ '^[0-9a-f]{64}$'),
  details jsonb not null default '{}'::jsonb check (jsonb_typeof(details) = 'object'),
  recorded_at timestamptz not null default clock_timestamp()
);

create index if not exists penta_mail_provider_attempts_route_time_idx
  on integration_control.penta_mail_provider_attempts_v1(provider_route_id, started_at desc);
create index if not exists penta_mail_provider_attempts_trigger_time_idx
  on integration_control.penta_mail_provider_attempts_v1(trigger_ref, started_at desc);

alter table integration_control.penta_mail_provider_attempts_v1 enable row level security;
alter table integration_control.penta_mail_provider_attempt_outcomes_v1 enable row level security;
revoke all on integration_control.penta_mail_provider_attempts_v1 from public, anon, authenticated;
revoke all on integration_control.penta_mail_provider_attempt_outcomes_v1 from public, anon, authenticated;
grant select on integration_control.penta_mail_provider_attempts_v1 to service_role;
grant select on integration_control.penta_mail_provider_attempt_outcomes_v1 to service_role;

drop trigger if exists penta_mail_provider_attempts_append_only
  on integration_control.penta_mail_provider_attempts_v1;
create trigger penta_mail_provider_attempts_append_only
before update or delete on integration_control.penta_mail_provider_attempts_v1
for each row execute function integration_control.penta_mail_reject_evidence_mutation_v1();

drop trigger if exists penta_mail_provider_attempt_outcomes_append_only
  on integration_control.penta_mail_provider_attempt_outcomes_v1;
create trigger penta_mail_provider_attempt_outcomes_append_only
before update or delete on integration_control.penta_mail_provider_attempt_outcomes_v1
for each row execute function integration_control.penta_mail_reject_evidence_mutation_v1();

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

create or replace function public.penta_mail_accept_mailgun_probation_v2(
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
set search_path = pg_catalog, public, integration_control, os_v2
as $$
declare
  v_existing integration_control.penta_mail_provider_incidents_v1%rowtype;
  v_result jsonb;
  v_trigger text := btrim(coalesce(p_trigger_ref, ''));
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  select * into v_existing
  from integration_control.penta_mail_provider_incidents_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
    and provider_event_id = p_provider_event_id;
  if found and (
    v_existing.provider_event_sha256 <> p_provider_event_sha256
    or v_existing.trigger_ref <> v_trigger
    or v_existing.evidence_kind <> p_evidence_kind
    or v_existing.authority_ref <> p_authority_ref
  ) then
    raise exception 'PENTAMAIL_PROVIDER_EVENT_CONFLICT';
  end if;
  v_result := public.penta_mail_accept_mailgun_probation_v1(
    p_provider_event_id, p_provider_event_sha256, v_trigger,
    p_retry_after_seconds, p_evidence_kind, p_authority_ref
  );
  if coalesce((v_result ->> 'idempotent_replay')::boolean, false) is false then
    update integration_control.penta_mail_provider_control_v1
    set last_readback_at = null,
        last_readback_enabled = null,
        last_readback_http_status = null,
        last_readback_sha256 = null,
        enabled_readback_at = null,
        state = 'open',
        updated_at = clock_timestamp()
    where provider_route_id = 'mailgun:relay.crownthrive.com';
  end if;
  update os_v2.notifications n
  set available_at = greatest(n.available_at, p.probation_until),
      provider_receipt = coalesce(n.provider_receipt, '{}'::jsonb) || jsonb_build_object(
        'active_incident_id', p.active_incident_id,
        'deferred_until', p.probation_until
      )
  from integration_control.penta_mail_trigger_probation_v1 p
  where n.trigger_ref = p.trigger_ref
    and n.state = 'queued'
    and n.provider_receipt ->> 'control_kind' = 'trigger_probation_digest'
    and p.probation_until > clock_timestamp();
  return v_result;
end
$$;

create or replace function public.penta_mail_record_mailgun_readback_v2(
  p_readback_event_id text,
  p_enabled boolean,
  p_regular_disabled boolean,
  p_scheduled_disabled boolean,
  p_provider_http_status integer,
  p_response_sha256 text,
  p_adapter_context jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_result jsonb;
  v_incident_id uuid;
  v_verified boolean;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if jsonb_typeof(coalesce(p_adapter_context, '{}'::jsonb)) <> 'object'
    or p_adapter_context ->> 'provider_route_id' <> 'mailgun:relay.crownthrive.com'
    or p_adapter_context ->> 'domain' <> 'relay.crownthrive.com'
    or p_adapter_context ->> 'api_base' <> 'https://api.mailgun.net'
    or coalesce((p_adapter_context ->> 'provider_call_made')::boolean, false) is false then
    raise exception 'PENTAMAIL_INVALID_READBACK_ADAPTER_CONTEXT';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_result := public.penta_mail_record_mailgun_readback_v1(
    p_readback_event_id, p_enabled, p_regular_disabled, p_scheduled_disabled,
    p_provider_http_status, p_response_sha256
  );
  v_verified := coalesce(p_enabled, false)
    and coalesce(p_provider_http_status, 0) between 200 and 299
    and not coalesce(p_regular_disabled, true)
    and not coalesce(p_scheduled_disabled, true);
  if not v_verified then
    update integration_control.penta_mail_provider_control_v1
    set enabled_readback_at = null,
        state = case when clock_timestamp() < hold_until then 'open' else 'awaiting_provider_readback' end,
        updated_at = clock_timestamp()
    where provider_route_id = 'mailgun:relay.crownthrive.com';
  end if;
  select active_incident_id into v_incident_id
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  perform integration_control.penta_mail_append_control_event_v1(
    'readback:' || p_readback_event_id || ':adapter-context',
    'mail.provider_readback_adapter_context',
    v_incident_id,
    null,
    p_adapter_context || jsonb_build_object(
      'response_sha256', p_response_sha256,
      'provider_http_status', p_provider_http_status,
      'verified_enabled', v_verified,
      'raw_provider_body_retained', false
    ),
    'ct-founder-directive-pentamail-provider-probation-20260826-v1'
  );
  return public.penta_mail_provider_status_v1(null) ||
    (v_result - 'enabled_readback_at' - 'last_readback_enabled');
end
$$;

create or replace function public.penta_mail_reserve_mailgun_rate_v2(
  p_request_key text,
  p_trigger_ref text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_status jsonb;
  v_batch_count integer;
  v_batch_oldest timestamptz;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_status := public.penta_mail_provider_status_v1(p_trigger_ref);
  if v_status ->> 'route_state' = 'controlled_release' then
    select count(*)::integer, min(reserved_at)
    into v_batch_count, v_batch_oldest
    from integration_control.penta_mail_rate_reservations_v1
    where provider_route_id = 'mailgun:relay.crownthrive.com'
      and reserved_at > clock_timestamp() - interval '1 minute';
    if v_batch_count >= 2 then
      return jsonb_build_object(
        'allowed', false,
        'reason', 'controlled_release_batch_limit',
        'window_count', v_batch_count,
        'controlled_batch_size', 2,
        'retry_at', v_batch_oldest + interval '1 minute',
        'control', v_status
      );
    end if;
  end if;
  return public.penta_mail_reserve_mailgun_rate_v1(p_request_key, p_trigger_ref);
end
$$;

create or replace function public.penta_mail_claim_outbox_v3(p_limit integer default 2)
returns setof public.penta_mail_outbox_v1
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  return query select * from public.penta_mail_claim_outbox_v2(least(coalesce(p_limit, 2), 2));
end
$$;

create or replace function public.penta_mail_start_mailgun_attempt_v1(
  p_request_key text,
  p_trigger_ref text,
  p_payload_sha256 text,
  p_attempt_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, integration_control
as $$
declare
  v_status jsonb;
  v_reservation integration_control.penta_mail_rate_reservations_v1%rowtype;
  v_existing integration_control.penta_mail_provider_attempts_v1%rowtype;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if coalesce(p_payload_sha256, '') !~ '^[0-9a-f]{64}$' then
    raise exception 'PENTAMAIL_INVALID_PAYLOAD_SHA256';
  end if;
  perform pg_advisory_xact_lock(hashtext('mailgun:relay.crownthrive.com:send-control'));
  v_status := public.penta_mail_provider_status_v1(p_trigger_ref);
  if v_status ->> 'route_state' not in ('closed','controlled_release') then
    return jsonb_build_object('allowed', false, 'reason', 'provider_circuit_' || (v_status ->> 'route_state'), 'control', v_status);
  end if;
  if v_status ->> 'trigger_state' = 'probation' then
    return jsonb_build_object('allowed', false, 'reason', 'trigger_probation', 'control', v_status);
  end if;
  select * into v_reservation
  from integration_control.penta_mail_rate_reservations_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
    and request_key = p_request_key;
  if not found or v_reservation.trigger_ref <> p_trigger_ref then
    raise exception 'PENTAMAIL_RATE_RESERVATION_REQUIRED';
  end if;
  select * into v_existing
  from integration_control.penta_mail_provider_attempts_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com'
    and request_key = p_request_key;
  if found then
    if v_existing.trigger_ref <> p_trigger_ref
      or v_existing.payload_sha256 <> p_payload_sha256 then
      raise exception 'PENTAMAIL_PROVIDER_ATTEMPT_CONFLICT';
    end if;
    return jsonb_build_object(
      'allowed', false,
      'reason', 'request_already_started',
      'attempt_id', v_existing.attempt_id,
      'started_at', v_existing.started_at,
      'reconciliation_required', true
    );
  end if;
  insert into integration_control.penta_mail_provider_attempts_v1(
    attempt_id, provider_route_id, request_key, trigger_ref, payload_sha256
  ) values (
    p_attempt_id, 'mailgun:relay.crownthrive.com', p_request_key, p_trigger_ref, p_payload_sha256
  );
  return jsonb_build_object(
    'allowed', true,
    'attempt_id', p_attempt_id,
    'provider_started_at', clock_timestamp(),
    'linearization', 'provider_attempt_authorized_before_circuit'
  );
end
$$;

create or replace function public.penta_mail_record_mailgun_attempt_outcome_v1(
  p_attempt_id uuid,
  p_outcome_state text,
  p_provider_http_status integer,
  p_provider_message_id text,
  p_response_sha256 text,
  p_details jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_existing integration_control.penta_mail_provider_attempt_outcomes_v1%rowtype;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if p_outcome_state not in ('provider_accepted','definitive_failure','probation_detected','ambiguous','reconciled')
    or coalesce(p_response_sha256, '') !~ '^[0-9a-f]{64}$'
    or jsonb_typeof(coalesce(p_details, '{}'::jsonb)) <> 'object'
    or octet_length(coalesce(p_details, '{}'::jsonb)::text) > 8192 then
    raise exception 'PENTAMAIL_INVALID_PROVIDER_ATTEMPT_OUTCOME';
  end if;
  select * into v_existing
  from integration_control.penta_mail_provider_attempt_outcomes_v1
  where attempt_id = p_attempt_id;
  if found then
    if v_existing.outcome_state <> p_outcome_state
      or v_existing.response_sha256 <> p_response_sha256 then
      raise exception 'PENTAMAIL_PROVIDER_ATTEMPT_OUTCOME_CONFLICT';
    end if;
    return jsonb_build_object('recorded', false, 'idempotent_replay', true, 'attempt_id', p_attempt_id);
  end if;
  insert into integration_control.penta_mail_provider_attempt_outcomes_v1(
    attempt_id, outcome_state, provider_http_status, provider_message_id,
    response_sha256, details
  ) values (
    p_attempt_id, p_outcome_state, p_provider_http_status,
    left(nullif(p_provider_message_id, ''), 500), p_response_sha256,
    coalesce(p_details, '{}'::jsonb)
  );
  return jsonb_build_object('recorded', true, 'idempotent_replay', false, 'attempt_id', p_attempt_id);
end
$$;

create or replace function public.penta_mail_complete_outbox_v3(
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
  v_now timestamptz := clock_timestamp();
  v_attempts integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  if coalesce(p_error, '') like '%provider_outcome_unknown%'
    or coalesce(p_error, '') like '%request_already_reserved%'
    or coalesce(p_error, '') like '%request_already_started%'
    or coalesce(p_error, '') like '%"reconciliation_required":true%' then
    select * into v_row
    from public.penta_mail_outbox_v1
    where message_id = p_message_id
    for update;
    if not found or v_row.state <> 'dispatching' or v_row.lease_id is distinct from p_lease_id then
      raise exception 'PENTAMAIL_LEASE_MISMATCH';
    end if;
    v_attempts := v_row.attempt_count + case when coalesce(p_provider_call_made, false) then 1 else 0 end;
    update public.penta_mail_outbox_v1
    set state = 'reconciliation_required',
        attempt_count = v_attempts,
        lease_id = null,
        lease_expires_at = null,
        provider_http_status = p_provider_http_status,
        provider_message_id = left(nullif(p_provider_message_id, ''), 500),
        last_error = left(coalesce(p_error, 'provider_outcome_unknown'), 1000),
        metadata = metadata || jsonb_build_object(
          'provider_outcome', 'unknown',
          'automatic_retry_allowed', false,
          'reconciliation_required_at', v_now
        ),
        updated_at = v_now
    where message_id = p_message_id;
    return jsonb_build_object(
      'message_id', p_message_id,
      'state', 'reconciliation_required',
      'attempt_count', v_attempts,
      'provider_call_made', coalesce(p_provider_call_made, false),
      'automatic_retry_allowed', false
    );
  end if;
  return public.penta_mail_complete_outbox_v2(
    p_message_id, p_lease_id, p_ok, p_provider_call_made,
    p_provider_http_status, p_provider_message_id, p_error, p_retry_after_seconds
  );
end
$$;

create or replace function integration_control.penta_mail_preserve_active_lease_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  if old.state = 'dispatching'
    and old.lease_id is not null
    and new.state = 'held'
    and new.lease_id is not distinct from old.lease_id then
    new.state := old.state;
    new.trigger_ref := old.trigger_ref;
    new.metadata := old.metadata;
    new.available_at := old.available_at;
    new.lease_expires_at := old.lease_expires_at;
  end if;
  return new;
end
$$;

drop trigger if exists penta_mail_preserve_active_lease_v1
  on public.penta_mail_outbox_v1;
create trigger penta_mail_preserve_active_lease_v1
before update on public.penta_mail_outbox_v1
for each row execute function integration_control.penta_mail_preserve_active_lease_v1();

revoke insert, update, delete, truncate on integration_control.penta_mail_provider_incidents_v1 from service_role;
revoke insert, update, delete, truncate on integration_control.penta_mail_provider_control_v1 from service_role;
revoke insert, update, delete, truncate on integration_control.penta_mail_trigger_probation_v1 from service_role;
revoke insert, update, delete, truncate on integration_control.penta_mail_provider_events_v1 from service_role;
revoke insert, update, delete, truncate on integration_control.penta_mail_rate_reservations_v1 from service_role;
revoke insert, update, delete, truncate on integration_control.penta_mail_provider_attempts_v1 from service_role;
revoke insert, update, delete, truncate on integration_control.penta_mail_provider_attempt_outcomes_v1 from service_role;
revoke insert, update, delete, truncate on public.penta_mail_outbox_v1 from service_role;
grant select on integration_control.penta_mail_provider_incidents_v1 to service_role;
grant select on integration_control.penta_mail_provider_control_v1 to service_role;
grant select on integration_control.penta_mail_trigger_probation_v1 to service_role;
grant select on integration_control.penta_mail_provider_events_v1 to service_role;
grant select on integration_control.penta_mail_rate_reservations_v1 to service_role;
grant select on integration_control.penta_mail_provider_attempts_v1 to service_role;
grant select on integration_control.penta_mail_provider_attempt_outcomes_v1 to service_role;
grant select on public.penta_mail_outbox_v1 to service_role;

revoke execute on function public.penta_mail_accept_mailgun_probation_v1(text,text,text,integer,text,text) from service_role;
revoke execute on function public.penta_mail_record_mailgun_readback_v1(text,boolean,boolean,boolean,integer,text) from service_role;
revoke execute on function public.penta_mail_reserve_mailgun_rate_v1(text,text) from service_role;
revoke execute on function public.penta_mail_claim_outbox_v2(integer) from service_role;
revoke execute on function public.penta_mail_complete_outbox_v2(uuid,uuid,boolean,boolean,integer,text,text,integer) from service_role;

revoke all on function public.penta_mail_accept_mailgun_probation_v2(text,text,text,integer,text,text) from public, anon, authenticated;
revoke all on function public.penta_mail_record_mailgun_readback_v2(text,boolean,boolean,boolean,integer,text,jsonb) from public, anon, authenticated;
revoke all on function public.penta_mail_reserve_mailgun_rate_v2(text,text) from public, anon, authenticated;
revoke all on function public.penta_mail_claim_outbox_v3(integer) from public, anon, authenticated;
revoke all on function public.penta_mail_start_mailgun_attempt_v1(text,text,text,uuid) from public, anon, authenticated;
revoke all on function public.penta_mail_record_mailgun_attempt_outcome_v1(uuid,text,integer,text,text,jsonb) from public, anon, authenticated;
revoke all on function public.penta_mail_complete_outbox_v3(uuid,uuid,boolean,boolean,integer,text,text,integer) from public, anon, authenticated;

grant execute on function public.penta_mail_accept_mailgun_probation_v2(text,text,text,integer,text,text) to service_role;
grant execute on function public.penta_mail_record_mailgun_readback_v2(text,boolean,boolean,boolean,integer,text,jsonb) to service_role;
grant execute on function public.penta_mail_reserve_mailgun_rate_v2(text,text) to service_role;
grant execute on function public.penta_mail_claim_outbox_v3(integer) to service_role;
grant execute on function public.penta_mail_start_mailgun_attempt_v1(text,text,text,uuid) to service_role;
grant execute on function public.penta_mail_record_mailgun_attempt_outcome_v1(uuid,text,integer,text,text,jsonb) to service_role;
grant execute on function public.penta_mail_complete_outbox_v3(uuid,uuid,boolean,boolean,integer,text,text,integer) to service_role;

comment on function public.penta_mail_start_mailgun_attempt_v1(text,text,text,uuid) is
  'Linearizes a payload-bound provider attempt against probation acceptance. Attempts authorized first are in flight; attempts reaching this gate after a hold are denied.';
comment on table integration_control.penta_mail_provider_attempt_outcomes_v1 is
  'Append-only provider outcome custody. Ambiguous outcomes require reconciliation and are never automatically retried.';

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

do $$
declare
  v_trigger_ref constant text := 'db-trigger:public.ct_factory_adapter_certification_queue:trg_os_v2_notify_provider_cert_state_v1';
  v_probation_until timestamptz;
  v_incident_id uuid;
  v_pref os_v2.system_notification_preferences%rowtype;
  v_notification_id uuid;
  v_event_count integer;
  v_existing_count integer;
begin
  select probation_until, active_incident_id
  into v_probation_until, v_incident_id
  from integration_control.penta_mail_trigger_probation_v1
  where trigger_ref = v_trigger_ref and probation_until > clock_timestamp();
  if not found then
    return;
  end if;
  select count(*)::integer into v_event_count
  from os_v2.system_change_events
  where source_system = 'PentaCertify'
    and event_type = 'provider_certification_state_changed'
    and notification_id is null
    and details ->> 'notification_state' = 'suppressed_during_trigger_probation'
    and details ->> 'trigger_ref' = v_trigger_ref;
  if v_event_count = 0 then
    return;
  end if;
  perform pg_advisory_xact_lock(hashtext('os_v2:penta-certify-probation-digest'));
  select * into v_pref
  from os_v2.system_notification_preferences
  where preference_key = 'founder_primary' and enabled and immediate_material_changes;
  if not found then
    return;
  end if;
  select notification_id,
    case when coalesce(provider_receipt ->> 'deferred_event_count', '') ~ '^[0-9]+$'
      then (provider_receipt ->> 'deferred_event_count')::integer else 0 end
  into v_notification_id, v_existing_count
  from os_v2.notifications
  where trigger_ref = v_trigger_ref
    and state = 'queued'
    and provider_receipt ->> 'control_kind' = 'trigger_probation_digest'
  order by created_at
  limit 1
  for update;
  if found then
    update os_v2.notifications
    set available_at = greatest(available_at, v_probation_until),
        subject = '[CrownThrive System] PentaCertify changes held during trigger probation',
        body = format(
          'CrownThrive retained %s PentaCertify change notifications while the causal trigger is on probation. They are coalesced into this single digest until %s. No provider call is permitted before the governed release boundary.',
          v_existing_count + v_event_count, v_probation_until
        ),
        provider_receipt = coalesce(provider_receipt, '{}'::jsonb) || jsonb_build_object(
          'control_kind', 'trigger_probation_digest',
          'deferred_event_count', v_existing_count + v_event_count,
          'active_incident_id', v_incident_id,
          'deferred_until', v_probation_until,
          'historical_suppressed_events_coalesced', v_event_count,
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
        'CrownThrive retained %s PentaCertify change notifications while the causal trigger is on probation. They are coalesced into this single digest until %s. No provider call is permitted before the governed release boundary.',
        v_event_count, v_probation_until
      ),
      'critical', 'queued', v_probation_until,
      jsonb_build_object(
        'control_kind', 'trigger_probation_digest',
        'deferred_event_count', v_event_count,
        'active_incident_id', v_incident_id,
        'deferred_until', v_probation_until,
        'historical_suppressed_events_coalesced', v_event_count,
        'policy_id', 'ct.pentamailer.policy.mailgun-delivery-resilience.v1'
      ),
      v_trigger_ref
    ) returning notification_id into v_notification_id;
  end if;
  update os_v2.system_change_events
  set notification_id = v_notification_id
  where source_system = 'PentaCertify'
    and event_type = 'provider_certification_state_changed'
    and notification_id is null
    and details ->> 'notification_state' = 'suppressed_during_trigger_probation'
    and details ->> 'trigger_ref' = v_trigger_ref;
end
$$;
