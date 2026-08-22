import assert from 'node:assert/strict';
import {
  allocateLargestRemainder,
  compileReversalPlan,
  compileSettlementPlan,
} from './easor-settlement-plan.mjs';
import { sha256Hex } from '../common/canonical-json.mjs';

let seed = 0x9e3779b9;
const random = () => {
  seed ^= seed << 13;
  seed ^= seed >>> 17;
  seed ^= seed << 5;
  return seed >>> 0;
};
const shuffle = (values) => {
  const result = [...values];
  for (let index = result.length - 1; index > 0; index--) {
    const swap = random() % (index + 1);
    [result[index], result[swap]] = [result[swap], result[index]];
  }
  return result;
};

function composition(count) {
  const cuts = new Set([0, 10_000]);
  while (cuts.size < count + 1) cuts.add(random() % 10_001);
  const sorted = [...cuts].sort((a, b) => a - b);
  const parts = [];
  for (let index = 1; index < sorted.length; index++) parts.push(sorted[index] - sorted[index - 1]);
  while (parts.length < count) parts.push(0);
  return parts.slice(0, count - 1).concat(10_000 - parts.slice(0, count - 1).reduce((sum, value) => sum + value, 0));
}

const baseRules = [
  { leg_code: 'creator', bps: 6500, beneficiary_ref: 'ct.party.creator', leg_class: 'creator', settlement_mode: 'external_settlement_candidate' },
  { leg_code: 'platform', bps: 2000, beneficiary_ref: 'ct.party.crownthrive', leg_class: 'platform', settlement_mode: 'internal_obligation' },
  { leg_code: 'tax-reserve', bps: 1000, beneficiary_ref: 'ct.reserve.tax', leg_class: 'tax_reserve', settlement_mode: 'hold_only' },
  { leg_code: 'thrivefund', bps: 500, beneficiary_ref: 'ct.program.thrivefund', leg_class: 'impact_obligation', settlement_mode: 'hold_only', program_ref: 'ct.program.thrivefund' },
];

const canonicalPlan = compileSettlementPlan({
  plan_id: 'ct.easor.phase-c.synthetic.001',
  wallet_stable_id: 'ct.wallet.phase-c.synthetic',
  asset_code: 'USD',
  gross_minor: 12_345,
  rules: baseRules,
  rights: [{ entitlement_candidate_ref: 'ct.entitlement.synthetic.001', asset_ref: 'ct.asset.walletkit', terms_digest: sha256Hex('terms-v1') }],
  rewards: [{ program_ref: 'ct.program.crownrewards', unit_code: 'points', units: 123 }],
  policy_version: 'easor-v1-controlled-test',
  created_at: '2026-08-22T07:00:00Z',
});
const reorderedPlan = compileSettlementPlan({
  plan_id: canonicalPlan.plan_id,
  wallet_stable_id: canonicalPlan.wallet_stable_id,
  asset_code: canonicalPlan.asset_code,
  gross_minor: canonicalPlan.gross_minor,
  rules: [...baseRules].reverse(),
  rights: [...canonicalPlan.rights_obligations].map(({ state, rights_granted, ...right }) => right).reverse(),
  rewards: [...canonicalPlan.reward_obligations].map(({ state, cash_equivalent_inferred, ...reward }) => reward).reverse(),
  policy_version: canonicalPlan.policy_version,
  created_at: canonicalPlan.created_at,
});
assert.equal(canonicalPlan.plan_digest, reorderedPlan.plan_digest);
assert.equal(canonicalPlan.legs.reduce((sum, leg) => sum + leg.amount_minor, 0), canonicalPlan.gross_minor);
assert.equal(canonicalPlan.execution_state, 'PREVIEW_HOLD');
assert.equal(canonicalPlan.money_movement, false);
assert.equal(canonicalPlan.provider_write, false);
assert.equal(canonicalPlan.rights_granted, false);
assert.equal(canonicalPlan.rights_obligations[0].state, 'HOLD_INDEPENDENT_RIGHTS_REQUIRED');
assert.equal(canonicalPlan.reward_obligations[0].cash_equivalent_inferred, false);
assert.equal(canonicalPlan.impact_obligations[0].state, 'calculated_not_settled');
assert.equal(canonicalPlan.impact_obligations[0].impact_disbursed, false);

const tie = allocateLargestRemainder(1, [
  { leg_code: 'b', bps: 5000, beneficiary_ref: 'ct.b', leg_class: 'other', settlement_mode: 'hold_only' },
  { leg_code: 'a', bps: 5000, beneficiary_ref: 'ct.a', leg_class: 'other', settlement_mode: 'hold_only' },
]);
assert.deepEqual(tie.map((leg) => [leg.leg_code, leg.amount_minor]), [['a', 1], ['b', 0]]);

let planCases = 0;
let reversalCases = 0;
for (let caseIndex = 0; caseIndex < 20_000; caseIndex++) {
  const count = 2 + (random() % 7);
  const bps = composition(count);
  const rules = bps.map((basis, index) => ({
    leg_code: `leg-${String(index).padStart(2, '0')}`,
    bps: basis,
    beneficiary_ref: `ct.party.${index}`,
    leg_class: index === count - 1 && caseIndex % 5 === 0 ? 'impact_obligation' : 'other',
    settlement_mode: 'hold_only',
    ...(index === count - 1 && caseIndex % 5 === 0 ? { program_ref: `ct.program.${index}` } : {}),
  }));
  const gross = random() % 1_000_000_000;
  const id = `ct.easor.stress.${caseIndex}`;
  const input = {
    plan_id: id,
    wallet_stable_id: 'ct.wallet.stress',
    asset_code: 'USD',
    gross_minor: gross,
    rules,
    policy_version: 'easor-v1-controlled-test',
    created_at: '2026-08-22T07:00:00Z',
  };
  const planA = compileSettlementPlan(input);
  const planB = compileSettlementPlan({ ...input, rules: shuffle(rules) });
  assert.equal(planA.plan_digest, planB.plan_digest);
  assert.equal(planA.legs.reduce((sum, leg) => sum + leg.amount_minor, 0), gross);
  assert.equal(planA.money_movement, false);
  assert.equal(planA.rights_granted, false);
  planCases++;

  if (caseIndex % 4 === 0) {
    const reversalMinor = gross === 0 ? 0 : random() % (gross + 1);
    const reversal = compileReversalPlan({
      reversal_id: `ct.easor.reversal.${caseIndex}`,
      original_plan: planA,
      reversal_minor: reversalMinor,
      reason_digest: sha256Hex(`reason:${caseIndex}`),
      created_at: '2026-08-22T07:05:00Z',
    });
    assert.equal(reversal.reversal_legs.reduce((sum, leg) => sum + leg.reversal_amount_minor, 0), reversalMinor);
    for (const leg of reversal.reversal_legs) {
      const original = planA.legs.find((entry) => entry.leg_code === leg.leg_code);
      assert.ok(leg.reversal_amount_minor <= original.amount_minor);
    }
    assert.equal(reversal.money_movement, false);
    assert.equal(reversal.provider_write, false);
    reversalCases++;
  }
}

const fullReversal = compileReversalPlan({
  reversal_id: 'ct.easor.reversal.full',
  original_plan: canonicalPlan,
  reversal_minor: canonicalPlan.gross_minor,
  reason_digest: sha256Hex('full-refund'),
  created_at: '2026-08-22T07:05:00Z',
});
assert.deepEqual(fullReversal.reversal_legs.map((leg) => leg.reversal_amount_minor), canonicalPlan.legs.map((leg) => leg.amount_minor));

assert.throws(() => allocateLargestRemainder(100, [{ ...baseRules[0], bps: 9999 }]), /easor_allocation_bps_must_sum_to_10000/);
assert.throws(() => compileSettlementPlan({
  plan_id: 'ct.easor.duplicate', wallet_stable_id: 'ct.wallet.test', asset_code: 'USD', gross_minor: 1,
  rules: [baseRules[0], { ...baseRules[0], bps: 3500 }, { ...baseRules[1], bps: 0 }],
  policy_version: 'v1', created_at: '2026-08-22T07:00:00Z',
}), /easor_duplicate_leg_code|easor_allocation_bps/);
assert.throws(() => compileReversalPlan({
  reversal_id: 'ct.easor.reversal.excess', original_plan: canonicalPlan,
  reversal_minor: canonicalPlan.gross_minor + 1, reason_digest: sha256Hex('excess'), created_at: '2026-08-22T07:05:00Z',
}), /easor_reversal_exceeds_original/);
const tampered = structuredClone(canonicalPlan);
tampered.legs[0].amount_minor += 1;
assert.throws(() => compileReversalPlan({
  reversal_id: 'ct.easor.reversal.tampered', original_plan: tampered,
  reversal_minor: 1, reason_digest: sha256Hex('tampered'), created_at: '2026-08-22T07:05:00Z',
}), /easor_original_plan_tampered/);

console.log(JSON.stringify({
  result: 'PASS_EASOR_SETTLEMENT_COMPILER',
  plan_cases: planCases,
  reversal_cases: reversalCases,
  largest_remainder_order_independent: true,
  allocation_conservation: true,
  reversal_cap_enforced: true,
  rights_independence_preserved: true,
  rewards_cash_equivalence_inferred: false,
  impact_disbursed: false,
  provider_write: false,
  money_movement: false,
}));
