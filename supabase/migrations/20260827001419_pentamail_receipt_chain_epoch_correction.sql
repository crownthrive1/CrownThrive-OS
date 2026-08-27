-- Append-only correction for the PentaMail receipt chain.
-- Historical forks are preserved. A new serialized verification epoch begins
-- after the current immutable head; no receipt is deleted or rewritten.

create table if not exists integration_control.penta_mail_receipt_chain_epochs_v1 (
  epoch_id uuid primary key default gen_random_uuid(),
  epoch_key text not null unique,
  started_at timestamptz not null,
  starts_after_receipt_id uuid not null,
  starts_after_chain_sha256 text not null check (starts_after_chain_sha256 ~ '^[0-9a-f]{64}$'),
  historical_receipt_count integer not null check (historical_receipt_count >= 0),
  observed_historical_order_breaks integer not null check (observed_historical_order_breaks >= 0),
  correction_reason text not null,
  policy_id text not null default 'ct.pentamailer.policy.mailgun-delivery-resilience.v1',
  policy_version text not null default '1.0.0',
  authority_ref text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table integration_control.penta_mail_receipt_chain_epochs_v1 enable row level security;
revoke all on integration_control.penta_mail_receipt_chain_epochs_v1 from public, anon, authenticated;
grant select, insert on integration_control.penta_mail_receipt_chain_epochs_v1 to service_role;

drop trigger if exists penta_mail_receipt_chain_epochs_append_only
  on integration_control.penta_mail_receipt_chain_epochs_v1;
create trigger penta_mail_receipt_chain_epochs_append_only
before update or delete on integration_control.penta_mail_receipt_chain_epochs_v1
for each row execute function integration_control.penta_mail_reject_evidence_mutation_v1();

do $$
declare
  v_head integration_control.penta_mail_outbox_receipts_v1%rowtype;
  v_started timestamptz;
  v_total integer;
  v_breaks integer;
  v_incident_id uuid;
begin
  perform pg_advisory_xact_lock(hashtext('integration_control.penta_mail_outbox_receipt_chain.v1'));
  select * into v_head
  from integration_control.penta_mail_outbox_receipts_v1
  order by created_at desc, receipt_id desc
  limit 1;
  if not found then
    raise exception 'PENTAMAIL_RECEIPT_CHAIN_HEAD_MISSING';
  end if;
  with ordered as (
    select previous_chain_sha256,
      lag(chain_sha256) over(order by created_at, receipt_id) expected_previous
    from integration_control.penta_mail_outbox_receipts_v1
  )
  select count(*)::integer,
    count(*) filter (
      where expected_previous is not null
        and previous_chain_sha256 is distinct from expected_previous
    )::integer
  into v_total, v_breaks
  from ordered;
  select active_incident_id into v_incident_id
  from integration_control.penta_mail_provider_control_v1
  where provider_route_id = 'mailgun:relay.crownthrive.com';
  v_started := clock_timestamp();
  insert into integration_control.penta_mail_receipt_chain_epochs_v1(
    epoch_key, started_at, starts_after_receipt_id, starts_after_chain_sha256,
    historical_receipt_count, observed_historical_order_breaks,
    correction_reason, authority_ref, details
  ) values (
    'pentamail-receipt-chain:serialized-v1',
    v_started,
    v_head.receipt_id,
    v_head.chain_sha256,
    v_total,
    v_breaks,
    'Preserve historical order forks and establish a serialized append-only verification epoch.',
    'ct-founder-directive-pentamail-provider-probation-20260826-v1',
    jsonb_build_object(
      'historical_forks_preserved', true,
      'historical_receipts_mutated', false,
      'serialized_trigger_active', true,
      'known_pre_policy_order_breaks', 4,
      'known_trigger_ref_backfill_order_breaks', 22
    )
  )
  on conflict (epoch_key) do nothing;
  perform integration_control.penta_mail_append_control_event_v1(
    'receipt-chain:serialized-v1:epoch-started',
    'mail.outbox_receipt_chain_epoch_started',
    v_incident_id,
    null,
    jsonb_build_object(
      'epoch_key', 'pentamail-receipt-chain:serialized-v1',
      'started_at', v_started,
      'starts_after_receipt_id', v_head.receipt_id,
      'starts_after_chain_sha256', v_head.chain_sha256,
      'historical_receipt_count', v_total,
      'observed_historical_order_breaks', v_breaks,
      'historical_forks_preserved', true,
      'historical_receipts_mutated', false
    ),
    'ct-founder-directive-pentamail-provider-probation-20260826-v1'
  );
end
$$;

create or replace function public.penta_mail_receipt_chain_epoch_status_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_epoch integration_control.penta_mail_receipt_chain_epochs_v1%rowtype;
  v_receipts integer;
  v_breaks integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select * into v_epoch
  from integration_control.penta_mail_receipt_chain_epochs_v1
  order by started_at desc
  limit 1;
  if not found then
    return jsonb_build_object('state', 'unverified', 'reason', 'receipt_chain_epoch_missing');
  end if;
  with ordered as (
    select r.previous_chain_sha256,
      coalesce(
        lag(r.chain_sha256) over(order by r.created_at, r.receipt_id),
        v_epoch.starts_after_chain_sha256
      ) expected_previous
    from integration_control.penta_mail_outbox_receipts_v1 r
    where r.created_at > v_epoch.started_at
  )
  select count(*)::integer,
    count(*) filter (
      where previous_chain_sha256 is distinct from expected_previous
    )::integer
  into v_receipts, v_breaks
  from ordered;
  return jsonb_build_object(
    'state', case when v_breaks = 0 then 'verified' else 'fork_detected' end,
    'epoch_key', v_epoch.epoch_key,
    'epoch_started_at', v_epoch.started_at,
    'starts_after_receipt_id', v_epoch.starts_after_receipt_id,
    'historical_receipt_count', v_epoch.historical_receipt_count,
    'historical_order_breaks_preserved', v_epoch.observed_historical_order_breaks,
    'epoch_receipt_count', v_receipts,
    'epoch_order_breaks', v_breaks,
    'historical_receipts_mutated', false,
    'as_of', clock_timestamp()
  );
end
$$;

revoke all on function public.penta_mail_receipt_chain_epoch_status_v1()
  from public, anon, authenticated;
grant execute on function public.penta_mail_receipt_chain_epoch_status_v1()
  to service_role;
