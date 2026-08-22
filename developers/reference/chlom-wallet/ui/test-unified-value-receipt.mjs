import assert from 'node:assert/strict';
import { buildUnifiedValueReceiptView, summarizeUnifiedValueReceipt } from './unified-value-receipt.mjs';

const receipt = buildUnifiedValueReceiptView({
  stable_id: 'ct.uvr.controlled-test-001',
  wallet_id: 'ct.wallet.controlled-test-001',
  source_event_ref: 'ct.event.controlled-test-001',
  money: { asset: 'USD', amount_minor: 4999, state: 'reconciled' },
  rights: { entitlement_ref: 'ct.entitlement.controlled-test-001', license_ref: 'ct.license.controlled-test-001', state: 'active' },
  rewards: { reward_ref: 'ct.reward.controlled-test-001', state: 'earned' },
  impact: { obligation_ref: 'ct.impact.controlled-test-001', state: 'calculated' },
  proof: { state: 'not_anchored' },
  policy_version: 'ct.policy.uvr.v1',
});

assert.equal(receipt.money.state, 'reconciled');
assert.equal(receipt.rights.state, 'active');
assert.equal(receipt.rewards.cash_equivalent_inferred, false);
assert.equal(receipt.impact.disbursement_inferred, false);
assert.equal(receipt.semantic_merge, false);
assert.equal(receipt.receipt_digest.length, 64);
assert.equal(buildUnifiedValueReceiptView({
  stable_id: 'ct.uvr.controlled-test-001',
  wallet_id: 'ct.wallet.controlled-test-001',
  source_event_ref: 'ct.event.controlled-test-001',
  money: { asset: 'USD', amount_minor: 4999, state: 'reconciled' },
  rights: { entitlement_ref: 'ct.entitlement.controlled-test-001', license_ref: 'ct.license.controlled-test-001', state: 'active' },
  rewards: { reward_ref: 'ct.reward.controlled-test-001', state: 'earned' },
  impact: { obligation_ref: 'ct.impact.controlled-test-001', state: 'calculated' },
  proof: { state: 'not_anchored' },
  policy_version: 'ct.policy.uvr.v1',
}).receipt_digest, receipt.receipt_digest);

const summary = summarizeUnifiedValueReceipt(receipt);
assert.equal(summary.sections.length, 5);
assert.equal(summary.title, 'CHLOM Value Receipt');

assert.throws(() => buildUnifiedValueReceiptView({
  stable_id: 'ct.uvr.bad-rights', wallet_id: 'ct.wallet.bad-rights', rights: { state: 'active' }, proof: { state: 'not_anchored' },
}), /active_rights_require_entitlement_ref/);

assert.throws(() => buildUnifiedValueReceiptView({
  stable_id: 'ct.uvr.bad-impact', wallet_id: 'ct.wallet.bad-impact', impact: { state: 'externally_settled' }, proof: { state: 'not_anchored' },
}), /settled_impact_requires_evidence/);

assert.throws(() => buildUnifiedValueReceiptView({
  stable_id: 'ct.uvr.bad-proof', wallet_id: 'ct.wallet.bad-proof', proof: { state: 'confirmed_test', digest: 'a'.repeat(64) },
}), /confirmed_proof_requires_digest_and_transaction/);

console.log(JSON.stringify({
  result: 'PASS',
  sections: 5,
  deterministic_receipt_digest: true,
  active_rights_gate: true,
  impact_settlement_evidence_gate: true,
  proof_confirmation_gate: true,
}));
