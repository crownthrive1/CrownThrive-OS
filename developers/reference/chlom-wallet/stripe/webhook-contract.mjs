import { createHmac, createHash, timingSafeEqual } from 'node:crypto';

// CONTROLLED-TEST REFERENCE CONTRACT.
// This module verifies and normalizes provider evidence only. It does not move money,
// issue entitlements, grant rights, or activate fulfillment.

export const STRIPE_EVENT_ALLOWLIST = Object.freeze(new Set([
  'checkout.session.completed',
  'checkout.session.async_payment_succeeded',
  'checkout.session.async_payment_failed',
  'payment_intent.succeeded',
  'payment_intent.payment_failed',
  'charge.refunded',
  'charge.dispute.created',
  'invoice.paid',
  'invoice.payment_failed',
  'customer.subscription.created',
  'customer.subscription.updated',
  'customer.subscription.deleted',
]));

export const sha256Hex = (value) => createHash('sha256').update(value).digest('hex');

export function parseStripeSignature(header) {
  if (typeof header !== 'string' || header.length < 3 || header.length > 8192) {
    throw new Error('stripe_signature_header_invalid');
  }
  let timestamp = null;
  const v1 = [];
  for (const rawPart of header.split(',')) {
    const part = rawPart.trim();
    const index = part.indexOf('=');
    if (index <= 0) continue;
    const key = part.slice(0, index);
    const value = part.slice(index + 1);
    if (key === 't' && timestamp === null && /^\d{1,20}$/.test(value)) timestamp = Number(value);
    if (key === 'v1' && /^[0-9a-f]{64}$/i.test(value)) v1.push(value.toLowerCase());
  }
  if (!Number.isSafeInteger(timestamp) || v1.length === 0) throw new Error('stripe_signature_components_missing');
  return { timestamp, v1 };
}

function constantTimeHexEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  const left = Buffer.from(a, 'hex');
  const right = Buffer.from(b, 'hex');
  if (left.length !== right.length) return false;
  return timingSafeEqual(left, right);
}

export function signStripeStylePayload(rawBody, secret, timestamp = Math.floor(Date.now() / 1000)) {
  if (typeof rawBody !== 'string' || Buffer.byteLength(rawBody) > 262_144) throw new Error('raw_body_invalid');
  if (typeof secret !== 'string' || secret.length < 16) throw new Error('signing_secret_invalid');
  if (!Number.isSafeInteger(timestamp) || timestamp < 1) throw new Error('timestamp_invalid');
  const signature = createHmac('sha256', secret).update(`${timestamp}.${rawBody}`).digest('hex');
  return `t=${timestamp},v1=${signature}`;
}

export function verifyStripeStyleSignature(rawBody, signatureHeader, secret, options = {}) {
  if (typeof rawBody !== 'string' || Buffer.byteLength(rawBody) > 262_144) {
    return { ok: false, reason: 'raw_body_invalid', signature_valid: false, timestamp_valid: false };
  }
  if (typeof secret !== 'string' || secret.length < 16) {
    return { ok: false, reason: 'signing_secret_invalid', signature_valid: false, timestamp_valid: false };
  }
  const toleranceSeconds = options.toleranceSeconds ?? 300;
  const nowSeconds = options.nowSeconds ?? Math.floor(Date.now() / 1000);
  if (!Number.isSafeInteger(toleranceSeconds) || toleranceSeconds < 0 || toleranceSeconds > 3600) {
    return { ok: false, reason: 'tolerance_invalid', signature_valid: false, timestamp_valid: false };
  }
  let parsed;
  try { parsed = parseStripeSignature(signatureHeader); }
  catch (error) {
    return { ok: false, reason: error instanceof Error ? error.message : 'signature_parse_failed', signature_valid: false, timestamp_valid: false };
  }
  const expected = createHmac('sha256', secret).update(`${parsed.timestamp}.${rawBody}`).digest('hex');
  const signatureValid = parsed.v1.some((candidate) => constantTimeHexEqual(expected, candidate));
  const ageSeconds = Math.abs(nowSeconds - parsed.timestamp);
  const timestampValid = ageSeconds <= toleranceSeconds;
  return {
    ok: signatureValid && timestampValid,
    reason: signatureValid && timestampValid ? 'verified' : (!signatureValid ? 'signature_mismatch' : 'timestamp_outside_tolerance'),
    signature_valid: signatureValid,
    timestamp_valid: timestampValid,
    age_seconds: ageSeconds,
    payload_digest: sha256Hex(rawBody),
  };
}

export function validateControlledStripeEvent(event) {
  if (!event || typeof event !== 'object') return { ok: false, state: 'REJECTED', reason: 'event_object_required' };
  if (event.object !== 'event' || typeof event.id !== 'string' || typeof event.type !== 'string') {
    return { ok: false, state: 'REJECTED', reason: 'event_identity_invalid' };
  }
  if (event.livemode === true) return { ok: false, state: 'HOLD', reason: 'live_event_not_armed' };
  if (!STRIPE_EVENT_ALLOWLIST.has(event.type)) return { ok: false, state: 'HOLD', reason: 'event_type_not_allowlisted' };
  return { ok: true, state: 'CONTROLLED_TEST_ACCEPTABLE', reason: 'event_envelope_valid' };
}

export function translateStripeEventForWallet(event) {
  const checked = validateControlledStripeEvent(event);
  if (!checked.ok) return { ...checked, fulfillment: 'HOLD' };
  const map = new Map([
    ['checkout.session.completed', ['Money', 'provider_checkout_completed']],
    ['checkout.session.async_payment_succeeded', ['Money', 'provider_checkout_async_succeeded']],
    ['checkout.session.async_payment_failed', ['Money', 'provider_checkout_async_failed']],
    ['payment_intent.succeeded', ['Money', 'provider_payment_succeeded']],
    ['payment_intent.payment_failed', ['Money', 'provider_payment_failed']],
    ['charge.refunded', ['Money', 'provider_refund_observed']],
    ['charge.dispute.created', ['Money', 'provider_dispute_observed']],
    ['invoice.paid', ['Money', 'provider_invoice_paid']],
    ['invoice.payment_failed', ['Money', 'provider_invoice_payment_failed']],
    ['customer.subscription.created', ['Money', 'provider_subscription_created']],
    ['customer.subscription.updated', ['Money', 'provider_subscription_updated']],
    ['customer.subscription.deleted', ['Money', 'provider_subscription_deleted']],
  ]);
  const [valueClass, normalizedEvent] = map.get(event.type) ?? ['Money', 'provider_event_unmapped'];
  return {
    ok: true,
    state: 'PROVIDER_EVIDENCE_ONLY',
    value_class: valueClass,
    normalized_event: normalizedEvent,
    provider_event_id: event.id,
    fulfillment: 'HOLD',
    entitlement_inferred: false,
    rights_granted: false,
  };
}
