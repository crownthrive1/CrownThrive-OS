-- COS V1 Phase 00 blocker repair.
-- Production pre-state snapshot: integration_control.thrivebase_audit_snapshots_v1
-- snapshot_id: 25b8495b-3636-46cf-959c-698f3d50eeca
-- Historical receipt rows/epochs remain immutable. This only prevents future concurrent forks.

set lock_timeout='10s';
lock table public.penta_mail_outbox_v1 in access exclusive mode;
select pg_advisory_xact_lock(hashtext('integration_control.penta_mail_outbox_receipt_chain.v1'));

create or replace function integration_control.penta_mail_capture_outbox_v1()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog','public','integration_control','extensions'
as $function$
declare
  v_prev text;
  v_prev_created timestamptz;
  v_sources jsonb;
  v_payload jsonb;
  v_chain text;
  v_before text;
  v_event text;
  v_now timestamptz;
  v_created timestamptz;
begin
  perform pg_advisory_xact_lock(hashtext('integration_control.penta_mail_outbox_receipt_chain.v1'));

  select chain_sha256, created_at
    into v_prev, v_prev_created
  from integration_control.penta_mail_outbox_receipts_v1
  order by created_at desc, receipt_id desc
  limit 1;

  v_now := clock_timestamp();
  v_created := case
    when v_prev_created is null then v_now
    else greatest(v_now, v_prev_created + interval '1 microsecond')
  end;

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
$function$;

select integration_control.penta_mail_start_receipt_epoch_v2(
  'COS V1 Phase 00 concurrency repair: preserve historical fork evidence; begin zero-break epoch after timestamp assignment moved under the existing serialized chain lock.'
);
