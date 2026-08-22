import assert from 'node:assert/strict';
import { createWalletShellModel, renderWalletShell } from './wallet-shell.mjs';

const receipt = {
  stable_id: 'ct.uvr.shell-controlled-test-001',
  receipt_digest: 'a'.repeat(64),
  money: { asset: 'USD', amount_minor: 4999, state: 'reconciled', provider_ref: 'must-not-render' },
  rights: { entitlement_ref: 'ct.entitlement.shell-controlled-test-001', license_ref: 'ct.license.shell-controlled-test-001', state: 'active' },
  rewards: { reward_ref: 'ct.reward.shell-controlled-test-001', state: 'earned' },
  impact: { obligation_ref: 'ct.impact.shell-controlled-test-001', state: 'calculated' },
  proof: { state: 'not_anchored' },
  private_evidence: { forbidden: true },
};

const model = createWalletShellModel({
  wallet_id: 'ct.wallet.shell-controlled-test-001',
  title: 'CHLOM Wallet',
  receipts: [receipt],
});
assert.equal(model.money.display, '$49.99');
assert.equal(model.rights.state, 'active');
assert.equal(model.rewards.cash_equivalent_inferred, false);
assert.equal(model.impact.disbursement_inferred, false);
assert.equal(model.provider_details_exposed, false);
assert.equal(model.private_evidence_exposed, false);
assert.equal(model.semantic_merge, false);

const html = renderWalletShell(model);
assert.match(html, /<main[^>]+aria-labelledby="wallet-title"/);
assert.match(html, /Money/);
assert.match(html, /Rights/);
assert.match(html, /Rewards/);
assert.match(html, /Impact/);
assert.match(html, /Proof/);
assert.match(html, /aria-live="polite"/);
assert.doesNotMatch(html, /must-not-render/);
assert.doesNotMatch(html, /private_evidence/);
assert.doesNotMatch(html, /forbidden/);

assert.throws(() => createWalletShellModel({
  wallet_id: 'ct.wallet.shell-bad-rights',
  receipts: [{ money: { state: 'held' }, rights: { state: 'active' }, rewards: { state: 'not_applicable' }, impact: { state: 'not_applicable' } }],
}), /active_rights_require_entitlement_ref/);

assert.throws(() => createWalletShellModel({
  wallet_id: 'ct.wallet.shell-bad-impact',
  receipts: [{ money: { state: 'held' }, rights: { state: 'not_applicable' }, rewards: { state: 'not_applicable' }, impact: { state: 'externally_settled' } }],
}), /settled_impact_requires_evidence/);

console.log(JSON.stringify({
  result: 'PASS',
  unified_shell_sections: 5,
  provider_detail_leak: false,
  private_evidence_leak: false,
  semantic_merge: false,
  accessibility_landmarks_present: true,
}));
