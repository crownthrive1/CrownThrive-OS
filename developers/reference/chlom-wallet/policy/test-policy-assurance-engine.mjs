import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  ALGORITHMS,
  ENGINE_ID,
  ENGINE_VERSION,
  assessWalletIntent,
  buildPolicyAssuranceStatus,
  canonicalize,
  compileRulepack,
  sha256Hex,
  verifyDecisionReceipt,
} from './chlom-wallet-policy-assurance.mjs';

const rulepack = JSON.parse(readFileSync(new URL('./baseline-rulepack.v1.json', import.meta.url), 'utf8'));
const compiled = compileRulepack(rulepack);

assert.equal(compiled.compiler_id, ALGORITHMS.CAPS.id);
assert.equal(compiled.rulepack_id, 'ct.rulepack.chlom-wallet.policy-assurance.v1');
assert.match(compiled.rulepack_sha256, /^[0-9a-f]{64}$/);
assert.deepEqual(compileRulepack(rulepack), compiled);
assert.throws(() => compileRulepack({ ...rulepack, client_secret: 'forbidden' }), /forbidden_field/);
assert.throws(() => compileRulepack({ ...rulepack, allowed_actions: [...rulepack.allowed_actions, rulepack.allowed_actions[0]] }), /duplicate/);

const evidence = (...types) => types.map((evidence_type) => ({
  evidence_type,
  state: 'verified',
  digest_sha256: sha256Hex(`evidence:${evidence_type}`),
  source_ref: `test:${evidence_type}`,
}));

const baseIntent = (overrides = {}) => ({
  intent_id: 'ct.wallet.intent.test.base',
  action_type: 'provider_event_translate',
  value_class: 'money',
  environment: 'controlled_test',
  authority: {
    agent_id: 'ct.agent.chlom-wallet-settlement',
    autonomy_class: 'A2',
    decision_class: 'D2',
    self_approval: false,
    vote_effect: 'none',
    heartbeat_fresh: true,
    exact_head_bound: true,
  },
  evidence: evidence('provider_signature_verified', 'replay_state_verified', 'provider_event_allowlisted'),
  requested_effects: {
    production_activation: false,
    provider_write: false,
    custody: false,
    token_issuance: false,
    money_movement: false,
    production_rights_grant: false,
    chain_broadcast: false,
    effective_price_publication: false,
    checkout_activation: false,
    phase_advancement: false,
    merge_authorized: false,
  },
  provider: {
    livemode: false,
    signature_verified: true,
    exact_replay: false,
    replay_state: 'UNIQUE',
  },
  semantics: {},
  passkey: {},
  chain: {},
  governance: {
    independent_review_required: false,
    phase_gate_required: false,
    rollback_plan_present: true,
    evidence_digest_bound: true,
  },
  ...overrides,
});

const ecac = assessWalletIntent(baseIntent(), compiled);
assert.equal(ecac.engine_id, ENGINE_ID);
assert.equal(ecac.engine_version, ENGINE_VERSION);
assert.equal(ecac.disposition, 'ECAC');
assert.equal(ecac.risk_score, 0);
assert.equal(ecac.risk_band, 'LOW');
assert.deepEqual(ecac.hard_denials, []);
assert.deepEqual(ecac.hold_reasons, []);
assert.equal(verifyDecisionReceipt(ecac).valid, true);
assert.deepEqual(assessWalletIntent(baseIntent(), compiled), ecac);

const paymentRights = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.payment-rights',
  action_type: 'entitlement_evaluate',
  value_class: 'rights',
  evidence: evidence('rights_evidence_present', 'terms_version_exact'),
  semantics: { payment_only: true, provider_payment_is_rights_evidence: true },
}), compiled);
assert.equal(paymentRights.disposition, 'DENY');
assert.ok(paymentRights.hard_denials.includes('PAYMENT_ONLY_ENTITLEMENT_FORBIDDEN'));
assert.ok(paymentRights.hard_denials.includes('PAYMENT_EVIDENCE_CANNOT_CREATE_RIGHTS'));

const impactFalseSettlement = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.impact-false-settlement',
  action_type: 'thrivefund_obligation',
  value_class: 'impact',
  evidence: evidence('impact_policy_exact', 'obligation_evidence_present'),
  semantics: { external_settlement_claimed: true },
}), compiled);
assert.equal(impactFalseSettlement.disposition, 'DENY');
assert.ok(impactFalseSettlement.hard_denials.includes('IMPACT_SETTLEMENT_REQUIRES_EXTERNAL_EVIDENCE'));

const providerMissingSignature = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.provider-missing-signature',
  evidence: evidence('replay_state_verified', 'provider_event_allowlisted'),
  provider: { livemode: false, signature_verified: false, exact_replay: false, replay_state: 'UNIQUE' },
}), compiled);
assert.equal(providerMissingSignature.disposition, 'HOLD');
assert.ok(providerMissingSignature.hold_reasons.some((reason) => reason.startsWith('REQUIRED_EVIDENCE_MISSING:')));
assert.ok(providerMissingSignature.hold_reasons.includes('PROVIDER_SIGNATURE_NOT_VERIFIED'));

const chainMismatch = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.chain-mismatch',
  action_type: 'smart_account_intent',
  value_class: 'proof',
  environment: 'testnet',
  evidence: evidence('entrypoint_source_pinned', 'chain_codehash_observed', 'unsigned_intent_exact'),
  chain: {
    runtime_codehash_match: false,
    source_profile_pinned: true,
    signature_present: false,
    paymaster_present: false,
  },
  governance: {
    independent_review_required: true,
    independent_review_state: 'PASS',
    phase_gate_required: true,
    phase_gate_state: 'PASS',
    rollback_plan_present: true,
    evidence_digest_bound: true,
  },
}), compiled);
assert.equal(chainMismatch.disposition, 'DENY');
assert.ok(chainMismatch.hard_denials.includes('ENTRYPOINT_RUNTIME_CODEHASH_MISMATCH'));

const chainReviewHold = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.chain-review-hold',
  action_type: 'smart_account_intent',
  value_class: 'proof',
  environment: 'testnet',
  evidence: evidence('entrypoint_source_pinned', 'chain_codehash_observed', 'unsigned_intent_exact'),
  chain: {
    runtime_codehash_match: true,
    source_profile_pinned: true,
    signature_present: false,
    paymaster_present: false,
  },
  governance: {
    independent_review_required: true,
    independent_review_state: 'HOLD',
    phase_gate_required: true,
    phase_gate_state: 'HOLD',
    rollback_plan_present: true,
    evidence_digest_bound: true,
  },
}), compiled);
assert.equal(chainReviewHold.disposition, 'HOLD');
assert.ok(chainReviewHold.hold_reasons.includes('INDEPENDENT_REVIEW_NOT_PASSED'));
assert.ok(chainReviewHold.hold_reasons.includes('PHASE_GATE_NOT_PASSED'));

const passkeyEcac = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.passkey-registration',
  action_type: 'passkey_registration',
  value_class: 'identity',
  evidence: evidence('challenge_bound', 'origin_bound', 'rp_id_bound', 'public_key_only'),
  passkey: {
    private_key_present: false,
    private_jwk_present: false,
    production_activation: false,
    smart_account_binding: false,
  },
}), compiled);
assert.equal(passkeyEcac.disposition, 'ECAC');

const passkeyPrivate = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.passkey-private',
  action_type: 'passkey_registration',
  value_class: 'identity',
  evidence: evidence('challenge_bound', 'origin_bound', 'rp_id_bound', 'public_key_only'),
  passkey: { private_jwk_present: true, production_activation: false },
}), compiled);
assert.equal(passkeyPrivate.disposition, 'DENY');
assert.ok(passkeyPrivate.hard_denials.includes('PASSKEY_PRIVATE_KEY_MATERIAL_FORBIDDEN'));

const pricingHold = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.pricing-hold',
  action_type: 'pricing_candidate',
  value_class: 'money',
  evidence: evidence('candidate_snapshot_frozen'),
  governance: {
    independent_review_required: true,
    independent_review_state: 'HOLD',
    phase_gate_required: false,
    rollback_plan_present: true,
    evidence_digest_bound: true,
  },
}), compiled);
assert.equal(pricingHold.disposition, 'HOLD');
assert.ok(pricingHold.missing_evidence.includes('independent_price_review_requested'));

const selfApproval = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.self-approval',
  authority: { ...baseIntent().authority, self_approval: true },
}), compiled);
assert.equal(selfApproval.disposition, 'DENY');
assert.ok(selfApproval.hard_denials.includes('ORIGINATOR_SELF_APPROVAL_FORBIDDEN'));

const staleAuthority = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.stale-authority',
  authority: { ...baseIntent().authority, heartbeat_fresh: false },
}), compiled);
assert.equal(staleAuthority.disposition, 'HOLD');
assert.ok(staleAuthority.hold_reasons.includes('AUTHORITY_HEARTBEAT_STALE_OR_MISSING'));

const secretLeak = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.secret-leak',
  metadata: { client_secret: 'not-allowed' },
}), compiled);
assert.equal(secretLeak.disposition, 'DENY');
assert.ok(secretLeak.hard_denials.some((reason) => reason.startsWith('FORBIDDEN_SECRET_BEARING_FIELD:')));

const moneyMovement = assessWalletIntent(baseIntent({
  intent_id: 'ct.wallet.intent.test.money-movement',
  requested_effects: { ...baseIntent().requested_effects, money_movement: true },
}), compiled);
assert.equal(moneyMovement.disposition, 'DENY');
assert.ok(moneyMovement.hard_denials.includes('MONEY_MOVEMENT_NOT_AUTHORIZED'));

const tampered = structuredClone(ecac);
tampered.disposition = 'DENY';
assert.equal(verifyDecisionReceipt(tampered).valid, false);

const status = buildPolicyAssuranceStatus(compiled, {
  compiled_rulepacks: 1,
  decision_receipts: 12,
  chaos_cases: 50000,
  invariant_failures: 0,
});
assert.equal(status.contract, 'ct.wallet.policy-assurance-status.v1');
assert.equal(status.metrics.chaos_cases, 50000);
assert.equal(status.hard_boundaries.money_movement, false);
assert.match(status.status_sha256, /^[0-9a-f]{64}$/);
assert.equal(sha256Hex(JSON.parse(JSON.stringify(rulepack))), sha256Hex(rulepack));
assert.equal(canonicalize({ b: 2, a: 1 }), '{"a":1,"b":2}');

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_POLICY_ASSURANCE_ENGINE',
  rulepack_id: compiled.rulepack_id,
  rulepack_sha256: compiled.rulepack_sha256,
  algorithms: Object.fromEntries(Object.entries(ALGORITHMS).map(([key, value]) => [key, value.id])),
  deterministic_receipt: true,
  scenarios: 12,
  ecac_scenarios: [ecac.intent_id, passkeyEcac.intent_id],
  hold_scenarios: [providerMissingSignature.intent_id, chainReviewHold.intent_id, pricingHold.intent_id, staleAuthority.intent_id],
  deny_scenarios: [paymentRights.intent_id, impactFalseSettlement.intent_id, chainMismatch.intent_id, passkeyPrivate.intent_id, selfApproval.intent_id, secretLeak.intent_id, moneyMovement.intent_id],
  receipt_tamper_rejected: true,
  private_secret_field_rejected: true,
  provider_write: false,
  custody: false,
  money_movement: false,
  production_rights_grant: false,
  chain_broadcast: false,
  phase_advancement: false,
}));
