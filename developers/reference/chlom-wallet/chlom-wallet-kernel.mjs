import { createHash } from 'node:crypto';

// CONTROLLED-TEST REFERENCE IMPLEMENTATION.
// No custody, live money movement, rights grant or production-chain authority.

export const sha256 = (value) => createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex');

export function allocateMinorUnits(grossMinor, rules) {
  if (!Number.isSafeInteger(grossMinor) || grossMinor < 0) throw new Error('gross_minor_must_be_nonnegative_safe_integer');
  if (!Array.isArray(rules) || rules.length < 1 || rules.length > 64) throw new Error('rules_count_invalid');
  const seen = new Set();
  let totalBps = 0;
  for (const rule of rules) {
    if (!rule || typeof rule.leg_code !== 'string' || !/^[A-Za-z0-9._-]{1,64}$/.test(rule.leg_code)) throw new Error('leg_code_invalid');
    if (seen.has(rule.leg_code)) throw new Error('duplicate_leg_code');
    seen.add(rule.leg_code);
    if (!Number.isInteger(rule.bps) || rule.bps < 0 || rule.bps > 10000) throw new Error('bps_invalid');
    totalBps += rule.bps;
  }
  if (totalBps !== 10000) throw new Error('allocation_bps_must_sum_to_10000');

  let running = 0;
  return rules.map((rule, index) => {
    const amount_minor = index === rules.length - 1
      ? grossMinor - running
      : Math.floor((grossMinor * rule.bps) / 10000);
    running += amount_minor;
    return { ...rule, amount_minor };
  });
}

export function appendEvent(previous, input) {
  if (!input?.wallet_id || !input?.event_type || !input?.correlation_id || !input?.idempotency_key || !input?.occurred_at) {
    throw new Error('required_field_missing');
  }
  const event_seq = previous ? previous.event_seq + 1 : 1;
  const payload = {
    wallet_id: input.wallet_id,
    event_seq,
    event_type: input.event_type,
    asset_code: input.asset_code ?? null,
    amount_minor: input.amount_minor ?? null,
    provider: input.provider ?? null,
    provider_ref: input.provider_ref ?? null,
    schedule_ref: input.schedule_ref ?? null,
    entitlement_ref: input.entitlement_ref ?? null,
    correlation_id: input.correlation_id,
    idempotency_key: input.idempotency_key,
    occurred_at: input.occurred_at,
    metadata: input.metadata ?? {},
  };
  const payload_digest = sha256(payload);
  const previous_chain_hash = previous?.chain_hash ?? null;
  const chain_hash = sha256(`${previous_chain_hash ?? 'GENESIS'}|${payload_digest}`);
  return { ...payload, payload_digest, previous_chain_hash, chain_hash };
}

export function normalizeCaip2(namespace, reference) {
  const value = `${namespace}:${reference}`;
  if (!/^[-a-z0-9]{3,8}:[-_a-zA-Z0-9]{1,32}$/.test(value)) throw new Error('invalid_caip2_candidate');
  return value;
}

export function normalizeCaip10(chainId, accountAddress) {
  const value = `${chainId}:${accountAddress}`;
  if (value.length > 128 || !chainId.includes(':') || !accountAddress) throw new Error('invalid_caip10_candidate');
  return value;
}

export function classifyProviderEvent(provider, eventType) {
  if (provider !== 'stripe') return { state: 'provider_evidence_received', fulfillment: 'HOLD' };
  const map = new Map([
    ['checkout.session.completed', 'provider_checkout_completed'],
    ['payment_intent.succeeded', 'provider_payment_succeeded'],
    ['payment_intent.payment_failed', 'provider_payment_failed'],
    ['charge.refunded', 'provider_refund_observed'],
    ['charge.dispute.created', 'provider_dispute_observed'],
    ['invoice.paid', 'provider_invoice_paid'],
    ['invoice.payment_failed', 'provider_invoice_payment_failed'],
  ]);
  return { state: map.get(eventType) ?? 'provider_event_unmapped', fulfillment: 'HOLD' };
}
