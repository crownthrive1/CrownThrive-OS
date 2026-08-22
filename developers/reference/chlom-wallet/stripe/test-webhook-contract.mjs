import assert from 'node:assert/strict';
import {
  parseStripeSignature,
  signStripeStylePayload,
  verifyStripeStyleSignature,
  validateControlledStripeEvent,
  translateStripeEventForWallet,
} from './webhook-contract.mjs';

const secret = 'synthetic_controlled_test_signing_material_2026';
const now = 1_800_000_000;
const event = {
  id: 'evt_wallet_reference_001',
  object: 'event',
  created: now,
  livemode: false,
  type: 'payment_intent.succeeded',
  data: { object: { id: 'pi_wallet_reference_001', amount_received: 12345, currency: 'usd' } },
};
const raw = JSON.stringify(event);
const signature = signStripeStylePayload(raw, secret, now);

const parsed = parseStripeSignature(signature);
assert.equal(parsed.timestamp, now);
assert.equal(parsed.v1.length, 1);

const verified = verifyStripeStyleSignature(raw, signature, secret, { nowSeconds: now, toleranceSeconds: 300 });
assert.equal(verified.ok, true);
assert.equal(verified.signature_valid, true);
assert.equal(verified.timestamp_valid, true);
assert.equal(verified.payload_digest.length, 64);

const tampered = verifyStripeStyleSignature(`${raw} `, signature, secret, { nowSeconds: now, toleranceSeconds: 300 });
assert.equal(tampered.ok, false);
assert.equal(tampered.reason, 'signature_mismatch');

const staleHeader = signStripeStylePayload(raw, secret, now - 301);
const stale = verifyStripeStyleSignature(raw, staleHeader, secret, { nowSeconds: now, toleranceSeconds: 300 });
assert.equal(stale.ok, false);
assert.equal(stale.signature_valid, true);
assert.equal(stale.timestamp_valid, false);
assert.equal(stale.reason, 'timestamp_outside_tolerance');

const wrongSecret = verifyStripeStyleSignature(raw, signature, 'different_synthetic_signing_material_2026', { nowSeconds: now });
assert.equal(wrongSecret.ok, false);
assert.equal(wrongSecret.signature_valid, false);

const malformed = verifyStripeStyleSignature(raw, 'garbage', secret, { nowSeconds: now });
assert.equal(malformed.ok, false);

assert.equal(validateControlledStripeEvent(event).ok, true);
assert.equal(validateControlledStripeEvent({ ...event, livemode: true }).reason, 'live_event_not_armed');
assert.equal(validateControlledStripeEvent({ ...event, type: 'unknown.provider.event' }).reason, 'event_type_not_allowlisted');

const translated = translateStripeEventForWallet(event);
assert.equal(translated.value_class, 'Money');
assert.equal(translated.normalized_event, 'provider_payment_succeeded');
assert.equal(translated.fulfillment, 'HOLD');
assert.equal(translated.entitlement_inferred, false);
assert.equal(translated.rights_granted, false);

const lifecycleCases = [
  ['invoice.paid', 'provider_invoice_paid'],
  ['invoice.payment_failed', 'provider_invoice_payment_failed'],
  ['customer.subscription.created', 'provider_subscription_created'],
  ['customer.subscription.updated', 'provider_subscription_updated'],
  ['customer.subscription.deleted', 'provider_subscription_deleted'],
  ['charge.dispute.created', 'provider_dispute_observed'],
  ['charge.refunded', 'provider_refund_observed'],
  ['checkout.session.async_payment_succeeded', 'provider_checkout_async_succeeded'],
  ['checkout.session.async_payment_failed', 'provider_checkout_async_failed'],
];
for (const [type, normalized] of lifecycleCases) {
  const translatedLifecycle = translateStripeEventForWallet({ ...event, id: `evt_${type}`, type });
  assert.equal(translatedLifecycle.ok, true, `${type} must remain allowlisted`);
  assert.equal(translatedLifecycle.value_class, 'Money');
  assert.equal(translatedLifecycle.normalized_event, normalized);
  assert.equal(translatedLifecycle.fulfillment, 'HOLD');
  assert.equal(translatedLifecycle.entitlement_inferred, false);
  assert.equal(translatedLifecycle.rights_granted, false);
}

const liveTranslated = translateStripeEventForWallet({ ...event, livemode: true });
assert.equal(liveTranslated.fulfillment, 'HOLD');
assert.equal(liveTranslated.reason, 'live_event_not_armed');

console.log(JSON.stringify({
  result: 'PASS',
  signature_raw_body: true,
  stale_timestamp_rejected: true,
  tamper_rejected: true,
  live_event_gate: true,
  lifecycle_event_contracts: lifecycleCases.length,
  payment_to_entitlement_inference: false,
}));
