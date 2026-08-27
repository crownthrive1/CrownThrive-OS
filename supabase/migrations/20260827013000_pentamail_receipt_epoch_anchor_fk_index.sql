-- Cover the composite receipt/hash epoch foreign key used by anchor verification.

create index if not exists penta_mail_receipt_epoch_anchor_idx
  on integration_control.penta_mail_receipt_chain_epochs_v1(
    starts_after_receipt_id,
    starts_after_chain_sha256
  );
