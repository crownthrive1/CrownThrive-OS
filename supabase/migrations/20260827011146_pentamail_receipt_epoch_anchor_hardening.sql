-- Bind each PentaMail receipt-chain epoch to an immutable receipt/hash anchor.
-- The verification projection no longer trusts a caller-supplied future time.

create unique index if not exists penta_mail_receipt_anchor_uidx
  on integration_control.penta_mail_outbox_receipts_v1(receipt_id, chain_sha256);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'penta_mail_receipt_epoch_anchor_fk_v1'
  ) then
    alter table integration_control.penta_mail_receipt_chain_epochs_v1
      add constraint penta_mail_receipt_epoch_anchor_fk_v1
      foreign key (starts_after_receipt_id, starts_after_chain_sha256)
      references integration_control.penta_mail_outbox_receipts_v1(receipt_id, chain_sha256);
  end if;
end
$$;

create or replace function integration_control.penta_mail_validate_receipt_epoch_anchor_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_head integration_control.penta_mail_outbox_receipts_v1%rowtype;
  v_total integer;
  v_breaks integer;
begin
  perform pg_advisory_xact_lock(hashtext('integration_control.penta_mail_outbox_receipt_chain.v1'));
  select * into v_head
  from integration_control.penta_mail_outbox_receipts_v1
  order by created_at desc, receipt_id desc
  limit 1;
  if not found
    or new.starts_after_receipt_id is distinct from v_head.receipt_id
    or new.starts_after_chain_sha256 is distinct from v_head.chain_sha256 then
    raise exception 'PENTAMAIL_RECEIPT_EPOCH_ANCHOR_NOT_CURRENT_HEAD';
  end if;
  if new.started_at < v_head.created_at
    or new.started_at > clock_timestamp() + interval '1 minute' then
    raise exception 'PENTAMAIL_RECEIPT_EPOCH_TIME_INVALID';
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
  if new.historical_receipt_count <> v_total
    or new.observed_historical_order_breaks <> v_breaks then
    raise exception 'PENTAMAIL_RECEIPT_EPOCH_OBSERVATION_MISMATCH';
  end if;
  return new;
end
$$;

drop trigger if exists penta_mail_receipt_epoch_anchor_validation_v1
  on integration_control.penta_mail_receipt_chain_epochs_v1;
create trigger penta_mail_receipt_epoch_anchor_validation_v1
before insert on integration_control.penta_mail_receipt_chain_epochs_v1
for each row execute function integration_control.penta_mail_validate_receipt_epoch_anchor_v1();

create or replace function public.penta_mail_receipt_chain_epoch_status_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, integration_control
as $$
declare
  v_epoch integration_control.penta_mail_receipt_chain_epochs_v1%rowtype;
  v_anchor integration_control.penta_mail_outbox_receipts_v1%rowtype;
  v_historical_receipts integer;
  v_receipts integer;
  v_breaks integer;
begin
  perform integration_control.penta_mail_assert_service_role_v1();
  select * into v_epoch
  from integration_control.penta_mail_receipt_chain_epochs_v1
  order by started_at desc, epoch_id desc
  limit 1;
  if not found then
    return jsonb_build_object('state', 'unverified', 'reason', 'receipt_chain_epoch_missing');
  end if;
  select * into v_anchor
  from integration_control.penta_mail_outbox_receipts_v1
  where receipt_id = v_epoch.starts_after_receipt_id
    and chain_sha256 = v_epoch.starts_after_chain_sha256;
  if not found or v_epoch.started_at < v_anchor.created_at
    or v_epoch.started_at > clock_timestamp() + interval '1 minute' then
    return jsonb_build_object('state', 'unverified', 'reason', 'receipt_chain_epoch_anchor_invalid');
  end if;
  select count(*)::integer into v_historical_receipts
  from integration_control.penta_mail_outbox_receipts_v1 r
  where (r.created_at, r.receipt_id) <= (v_anchor.created_at, v_anchor.receipt_id);
  if v_historical_receipts <> v_epoch.historical_receipt_count then
    return jsonb_build_object(
      'state', 'unverified',
      'reason', 'receipt_chain_epoch_historical_count_mismatch',
      'expected_historical_receipts', v_epoch.historical_receipt_count,
      'observed_historical_receipts', v_historical_receipts
    );
  end if;
  with ordered as (
    select r.previous_chain_sha256,
      coalesce(
        lag(r.chain_sha256) over(order by r.created_at, r.receipt_id),
        v_anchor.chain_sha256
      ) expected_previous
    from integration_control.penta_mail_outbox_receipts_v1 r
    where (r.created_at, r.receipt_id) > (v_anchor.created_at, v_anchor.receipt_id)
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
    'anchor_sha256', v_epoch.starts_after_chain_sha256,
    'anchor_verified', true,
    'historical_receipt_count', v_epoch.historical_receipt_count,
    'historical_order_breaks_preserved', v_epoch.observed_historical_order_breaks,
    'epoch_receipt_count', v_receipts,
    'epoch_order_breaks', v_breaks,
    'historical_receipts_mutated', false,
    'as_of', clock_timestamp()
  );
end
$$;

revoke insert, update, delete, truncate
  on integration_control.penta_mail_receipt_chain_epochs_v1
  from service_role;
grant select on integration_control.penta_mail_receipt_chain_epochs_v1
  to service_role;

comment on table integration_control.penta_mail_receipt_chain_epochs_v1 is
  'Append-only receipt-chain epochs anchored by a composite foreign key to an immutable receipt ID and chain digest; direct service-role mutation is prohibited.';
