import assert from 'node:assert/strict';
import { allocateMinorUnits, appendEvent, classifyProviderEvent, sha256 } from './chlom-wallet-kernel.mjs';

const rules = [
  { leg_code: 'operating', bps: 6111 },
  { leg_code: 'rights', bps: 2222 },
  { leg_code: 'thrivefund', bps: 1667 },
];

for (let i = 0; i < 10000; i++) {
  const gross = (i * 104729) % 9007199;
  const legs = allocateMinorUnits(gross, rules);
  assert.equal(legs.reduce((sum, x) => sum + x.amount_minor, 0), gross);
  assert.equal(legs.reduce((sum, x) => sum + x.bps, 0), 10000);
}
assert.throws(() => allocateMinorUnits(100, [{ leg_code: 'x', bps: 9999 }]), /allocation_bps/);
assert.throws(() => allocateMinorUnits(-1, rules), /nonnegative/);

let previous = null;
const hashes = new Set();
for (let i = 1; i <= 2000; i++) {
  const event = appendEvent(previous, {
    wallet_id: 'ct.wallet.test',
    event_type: 'stress.event',
    amount_minor: i,
    asset_code: 'USD',
    provider: 'synthetic',
    provider_ref: `synthetic-${i}`,
    correlation_id: 'corr-stress',
    idempotency_key: `idem-${i}`,
    occurred_at: `2026-08-21T00:${String(i % 60).padStart(2, '0')}:00Z`,
    metadata: { synthetic: true, i },
  });
  assert.equal(event.event_seq, i);
  if (previous) assert.equal(event.previous_chain_hash, previous.chain_hash);
  assert.equal(event.chain_hash.length, 64);
  hashes.add(event.chain_hash);
  previous = event;
}
assert.equal(hashes.size, 2000);
assert.equal(classifyProviderEvent('stripe', 'payment_intent.succeeded').fulfillment, 'HOLD');
assert.equal(classifyProviderEvent('stripe', 'unknown.event').state, 'provider_event_unmapped');
assert.equal(sha256('a').length, 64);
console.log(JSON.stringify({ result: 'PASS', allocation_cases: 10000, chained_events: 2000, distinct_chain_hashes: hashes.size }));
