import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { assessWalletIntent, compileRulepack, sha256Hex, verifyDecisionReceipt } from './chlom-wallet-policy-assurance.mjs';

const CASES = Number(process.env.CHLOM_WALLET_POLICY_FUZZ_CASES ?? 50000);
if (!Number.isInteger(CASES) || CASES < 1000 || CASES > 200000) throw new Error('fuzz_case_count_invalid');

const rulepack = JSON.parse(readFileSync(new URL('./baseline-rulepack.v1.json', import.meta.url), 'utf8'));
const compiled = compileRulepack(rulepack);

function mulberry32(seed) {
  return function next() {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const random = mulberry32(0x43484C4F);
const choose = (items) => items[Math.floor(random() * items.length)];
const chance = (probability) => random() < probability;
const actions = rulepack.allowed_actions;
const valueClasses = rulepack.allowed_value_classes;
const required = rulepack.required_evidence;
const counts = { ECAC: 0, HOLD: 0, DENY: 0 };
const reasons = new Map();
let invariantFailures = 0;
let determinismChecks = 0;
let receiptChecks = 0;
let paymentRightsCases = 0;
let impactSettlementCases = 0;
let secretCases = 0;
let broadcastCases = 0;
let staleCases = 0;

for (let index = 0; index < CASES; index += 1) {
  const action = choose(actions);
  const valueClass = choose(valueClasses);
  const requiredEvidence = required[action] ?? [];
  const evidence = requiredEvidence.map((evidence_type) => ({
    evidence_type,
    state: chance(0.08) ? 'stale' : chance(0.04) ? 'invalid' : chance(0.12) ? 'missing' : 'verified',
    digest_sha256: sha256Hex(`${index}:${evidence_type}`),
    source_ref: `chaos:${index}:${evidence_type}`,
  })).filter((item) => item.state !== 'missing');

  const paymentOnlyRights = action === 'entitlement_evaluate' && chance(0.22);
  const impactSettlement = valueClass === 'impact' && chance(0.18);
  const privateSecret = chance(0.015);
  const chainBroadcast = chance(0.02);
  const staleHeartbeat = chance(0.08);
  const selfApproval = chance(0.015);
  const codeMismatch = action === 'smart_account_intent' && chance(0.1);
  const independentReviewPassed = chance(0.65);
  const phaseGatePassed = chance(0.5);

  const intent = {
    intent_id: `ct.wallet.intent.chaos.${index.toString().padStart(6, '0')}`,
    action_type: action,
    value_class: valueClass,
    environment: action === 'smart_account_intent' && chance(0.7) ? 'testnet' : 'controlled_test',
    authority: {
      agent_id: 'ct.agent.chlom-wallet-settlement',
      autonomy_class: chance(0.005) ? 'A3' : 'A2',
      decision_class: chance(0.005) ? 'D3' : 'D2',
      self_approval: selfApproval,
      vote_effect: 'none',
      heartbeat_fresh: !staleHeartbeat,
      exact_head_bound: !chance(0.04),
    },
    evidence,
    requested_effects: {
      production_activation: chance(0.005),
      provider_write: chance(0.01),
      custody: chance(0.005),
      token_issuance: chance(0.002),
      money_movement: chance(0.01),
      production_rights_grant: chance(0.007),
      chain_broadcast: chainBroadcast,
      effective_price_publication: chance(0.006),
      checkout_activation: chance(0.006),
      phase_advancement: chance(0.003),
      merge_authorized: chance(0.003),
    },
    provider: {
      livemode: chance(0.01),
      signature_verified: !chance(0.1),
      exact_replay: chance(0.05),
      replay_state: chance(0.95) ? 'UNIQUE' : 'DUPLICATE',
    },
    semantics: {
      payment_only: paymentOnlyRights,
      provider_payment_is_rights_evidence: paymentOnlyRights && chance(0.7),
      external_settlement_claimed: impactSettlement,
      cash_equivalent_claimed: valueClass === 'rewards' && chance(0.15),
      protected_evidence_body_onchain: valueClass === 'proof' && chance(0.08),
    },
    passkey: {
      private_key_present: action.startsWith('passkey_') && chance(0.04),
      private_jwk_present: action.startsWith('passkey_') && chance(0.04),
      production_activation: action.startsWith('passkey_') && chance(0.02),
      smart_account_binding: action.startsWith('passkey_') && chance(0.05),
    },
    chain: {
      runtime_codehash_match: !codeMismatch,
      source_profile_pinned: !chance(0.07),
      signature_present: action === 'smart_account_intent' && chance(0.02),
      paymaster_present: action === 'smart_account_intent' && chance(0.02),
      factory_selected: action === 'smart_account_intent' && chance(0.05),
      factory_reviewed: chance(0.5),
      account_implementation_selected: action === 'smart_account_intent' && chance(0.05),
      account_implementation_reviewed: chance(0.5),
      simulation_completed: action === 'smart_account_intent' && chance(0.05),
      simulation_evidence_present: chance(0.5),
    },
    governance: {
      independent_review_required: ['smart_account_intent', 'pricing_candidate', 'proof_anchor_prepare'].includes(action),
      independent_review_state: independentReviewPassed ? 'PASS' : 'HOLD',
      phase_gate_required: action === 'smart_account_intent',
      phase_gate_state: phaseGatePassed ? 'PASS' : 'HOLD',
      rollback_plan_present: !chance(0.08),
      evidence_digest_bound: !chance(0.05),
    },
  };
  if (privateSecret) intent.metadata = { client_secret: `secret-${index}` };

  const receipt = assessWalletIntent(intent, compiled);
  counts[receipt.disposition] += 1;
  for (const reason of [...receipt.hard_denials, ...receipt.hold_reasons]) {
    reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
  }

  if (paymentOnlyRights) {
    paymentRightsCases += 1;
    if (receipt.disposition !== 'DENY' || !receipt.hard_denials.includes('PAYMENT_ONLY_ENTITLEMENT_FORBIDDEN')) invariantFailures += 1;
  }
  if (impactSettlement && valueClass === 'impact' && !evidence.some((item) => item.evidence_type === 'external_settlement_evidence' && item.state === 'verified')) {
    impactSettlementCases += 1;
    if (receipt.disposition !== 'DENY') invariantFailures += 1;
  }
  if (privateSecret) {
    secretCases += 1;
    if (receipt.disposition !== 'DENY') invariantFailures += 1;
  }
  if (chainBroadcast) {
    broadcastCases += 1;
    if (receipt.disposition !== 'DENY' || receipt.execution_envelope.chain_broadcast !== false) invariantFailures += 1;
  }
  if (staleHeartbeat) {
    staleCases += 1;
    if (receipt.disposition === 'ECAC') invariantFailures += 1;
  }
  if (receipt.disposition === 'ECAC') {
    if (receipt.hard_denials.length || receipt.hold_reasons.length) invariantFailures += 1;
    if (Object.entries(receipt.execution_envelope).some(([key, value]) => key !== 'controlled_test_only' && value !== false)) invariantFailures += 1;
  }
  if (!verifyDecisionReceipt(receipt).valid) invariantFailures += 1;
  receiptChecks += 1;

  if (index % 997 === 0) {
    const replay = assessWalletIntent(intent, compiled);
    if (JSON.stringify(replay) !== JSON.stringify(receipt)) invariantFailures += 1;
    determinismChecks += 1;
  }
}

assert.equal(invariantFailures, 0, `invariant_failures:${invariantFailures}`);
assert.equal(counts.ECAC + counts.HOLD + counts.DENY, CASES);
assert.ok(counts.ECAC > 0);
assert.ok(counts.HOLD > 0);
assert.ok(counts.DENY > 0);
assert.ok(paymentRightsCases > 0);
assert.ok(impactSettlementCases > 0);
assert.ok(secretCases > 0);
assert.ok(broadcastCases > 0);
assert.ok(staleCases > 0);

const topReasons = [...reasons.entries()]
  .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  .slice(0, 20)
  .map(([reason, count]) => ({ reason, count }));

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_POLICY_CHAOS_FUZZ',
  algorithm_id: 'ct.algorithm.wallet.chaos.v1',
  seed: '0x43484C4F',
  cases: CASES,
  dispositions: counts,
  invariant_failures: invariantFailures,
  receipt_checks: receiptChecks,
  determinism_checks: determinismChecks,
  payment_only_rights_cases: paymentRightsCases,
  impact_false_settlement_cases: impactSettlementCases,
  forbidden_secret_cases: secretCases,
  broadcast_attempt_cases: broadcastCases,
  stale_heartbeat_cases: staleCases,
  top_reason_codes: topReasons,
  production_activation: false,
  provider_write: false,
  custody: false,
  token_issuance: false,
  money_movement: false,
  production_rights_grant: false,
  chain_broadcast: false,
  effective_price_publication: false,
  phase_advancement: false,
}));
