import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  canonicalize,
  compilePolicyPackage,
  evaluateCompiledPolicy,
  runScenarioMatrix,
  sha256Hex,
} from './policy-engine.mjs';
import {
  LIMIT_SEMANTICS_VERSION,
  UsageLedger,
  calendarMonthWindow,
  evaluateUsageBudget,
  validateLicenseCandidate,
} from './metering-engine.mjs';
import { generatePolicyAdvisorProposal } from './policy-advisor.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const policy = JSON.parse(readFileSync(join(HERE, 'fixtures/walletkit-controlled-policy.v1.json'), 'utf8'));
const licenseSource = JSON.parse(readFileSync(join(HERE, 'fixtures/walletkit-synthetic-license.v1.json'), 'utf8'));

function action(overrides = {}) {
  return {
    category: 'policy_simulation',
    provider_write: false,
    money_movement: false,
    production_rights_grant: false,
    chain_broadcast: false,
    effective_offer_change: false,
    ...overrides,
  };
}

function context({ category = 'policy_simulation', evidence = {}, actionOverrides = {}, environment = 'CONTROLLED_TEST' } = {}) {
  return {
    environment,
    action: action({ category, ...actionOverrides }),
    evidence: {
      provider_signature_verified: false,
      independent_rights_active: false,
      ...evidence,
    },
  };
}

const artifact = compilePolicyPackage(policy);
const artifactReplay = compilePolicyPackage(JSON.parse(JSON.stringify(policy)));
assert.deepEqual(artifactReplay, artifact);
assert.match(artifact.source_digest_sha256, /^[0-9a-f]{64}$/);
assert.match(artifact.compiled_digest_sha256, /^[0-9a-f]{64}$/);
assert.equal(artifact.rules.length, 10);
assert.deepEqual(artifact.decision_precedence, ['DENY', 'HOLD', 'ALLOW']);
assert.equal(artifact.defaults.unknown, 'HOLD');
assert.ok(Object.values(artifact.hard_boundaries).every((value) => value === false));

const providerAllow = evaluateCompiledPolicy(artifact, context({
  category: 'provider_translation',
  evidence: { provider_signature_verified: true },
}));
assert.equal(providerAllow.decision, 'ALLOW');
assert.equal(providerAllow.reason_code, 'CONTROLLED_PROVIDER_TRANSLATION_ALLOWED');
assert.ok(Object.values(providerAllow.hard_boundaries).every((value) => value === false));

const providerHold = evaluateCompiledPolicy(artifact, context({
  category: 'provider_translation',
  evidence: { provider_signature_verified: false },
}));
assert.equal(providerHold.decision, 'HOLD');
assert.equal(providerHold.reason_code, 'PROVIDER_EVIDENCE_NOT_VERIFIED');

const providerUnknown = context({ category: 'provider_translation' });
delete providerUnknown.evidence.provider_signature_verified;
const providerUnknownReceipt = evaluateCompiledPolicy(artifact, providerUnknown);
assert.equal(providerUnknownReceipt.decision, 'HOLD');
assert.ok(['POLICY_INPUT_UNKNOWN', 'ALLOW_RULE_INPUT_UNKNOWN'].includes(providerUnknownReceipt.reason_code));

const providerWriteDeny = evaluateCompiledPolicy(artifact, context({
  category: 'provider_translation',
  evidence: { provider_signature_verified: true },
  actionOverrides: { provider_write: true },
}));
assert.equal(providerWriteDeny.decision, 'DENY');
assert.equal(providerWriteDeny.reason_code, 'LIVE_PROVIDER_WRITE_NOT_AUTHORIZED');

const moneyMovementDeny = evaluateCompiledPolicy(artifact, context({
  actionOverrides: { money_movement: true },
}));
assert.equal(moneyMovementDeny.decision, 'DENY');
assert.equal(moneyMovementDeny.reason_code, 'MONEY_MOVEMENT_NOT_AUTHORIZED');

const rightsHold = evaluateCompiledPolicy(artifact, context({
  category: 'rights_decision',
  evidence: { independent_rights_active: false },
}));
assert.equal(rightsHold.decision, 'HOLD');
assert.equal(rightsHold.reason_code, 'INDEPENDENT_RIGHTS_EVIDENCE_REQUIRED');

const rightsAllow = evaluateCompiledPolicy(artifact, context({
  category: 'rights_decision',
  evidence: { independent_rights_active: true },
}));
assert.equal(rightsAllow.decision, 'ALLOW');
assert.equal(rightsAllow.reason_code, 'CONTROLLED_RIGHTS_EVALUATION_ALLOWED');

const rightsGrantDeny = evaluateCompiledPolicy(artifact, context({
  category: 'rights_decision',
  evidence: { independent_rights_active: true },
  actionOverrides: { production_rights_grant: true },
}));
assert.equal(rightsGrantDeny.decision, 'DENY');
assert.equal(rightsGrantDeny.reason_code, 'PRODUCTION_RIGHTS_GRANT_NOT_AUTHORIZED');

const chainDeny = evaluateCompiledPolicy(artifact, context({
  actionOverrides: { chain_broadcast: true },
}));
assert.equal(chainDeny.decision, 'DENY');
assert.equal(chainDeny.reason_code, 'CHAIN_BROADCAST_NOT_AUTHORIZED');

const offerHold = evaluateCompiledPolicy(artifact, context({
  actionOverrides: { effective_offer_change: true },
}));
assert.equal(offerHold.decision, 'HOLD');
assert.equal(offerHold.reason_code, 'INDEPENDENT_PRICE_AND_RELEASE_REVIEW_REQUIRED');

for (const category of ['policy_simulation', 'usage_preview', 'advisor_preview']) {
  const receipt = evaluateCompiledPolicy(artifact, context({ category }));
  assert.equal(receipt.decision, 'ALLOW');
  assert.equal(receipt.reason_code, 'CONTROLLED_SIMULATION_ALLOWED');
}

const conflictPolicy = structuredClone(policy);
conflictPolicy.rules.push({
  ...structuredClone(conflictPolicy.rules[0]),
  rule_id: 'ct.rule.wallet.conflict-canary.v1',
  effect: 'ALLOW',
  reason_code: 'CONFLICT_CANARY_ALLOW',
});
assert.throws(() => compilePolicyPackage(conflictPolicy), /policy_compile_conflict/);

const scenarios = [];
for (let index = 0; index < 50_000; index += 1) {
  const selector = index % 10;
  if (selector === 0) scenarios.push(context({ category: 'provider_translation', evidence: { provider_signature_verified: true } }));
  else if (selector === 1) scenarios.push(context({ category: 'provider_translation', evidence: { provider_signature_verified: false } }));
  else if (selector === 2) scenarios.push(context({ category: 'rights_decision', evidence: { independent_rights_active: true } }));
  else if (selector === 3) scenarios.push(context({ category: 'rights_decision', evidence: { independent_rights_active: false } }));
  else if (selector === 4) scenarios.push(context({ actionOverrides: { provider_write: true } }));
  else if (selector === 5) scenarios.push(context({ actionOverrides: { money_movement: true } }));
  else if (selector === 6) scenarios.push(context({ actionOverrides: { production_rights_grant: true } }));
  else if (selector === 7) scenarios.push(context({ actionOverrides: { chain_broadcast: true } }));
  else if (selector === 8) scenarios.push(context({ actionOverrides: { effective_offer_change: true } }));
  else scenarios.push(context({ category: 'usage_preview' }));
}
const simulation = runScenarioMatrix(artifact, scenarios);
const simulationReplay = runScenarioMatrix(artifact, structuredClone(scenarios));
assert.deepEqual(simulationReplay, simulation);
assert.equal(simulation.scenario_count, 50_000);
assert.equal(simulation.decisions.ALLOW + simulation.decisions.HOLD + simulation.decisions.DENY, 50_000);
assert.equal(simulation.decisions.ALLOW, 15_000);
assert.equal(simulation.decisions.HOLD, 15_000);
assert.equal(simulation.decisions.DENY, 20_000);
assert.match(simulation.simulation_digest_sha256, /^[0-9a-f]{64}$/);
assert.ok(Object.values(simulation.hard_boundaries).every((value) => value === false));

assert.equal(LIMIT_SEMANTICS_VERSION, 'ct.limit-semantics.founder-override.v1');
const unlimited = evaluateUsageBudget({ limit: -1, used: 999, requested: 999 });
assert.equal(unlimited.disposition, 'ALLOW');
assert.equal(unlimited.reason_code, 'UNLIMITED_LOCAL_LIMIT');
assert.equal(unlimited.remaining_after_request, null);

const zeroDenied = evaluateUsageBudget({ limit: 0, used: 0, requested: 1 });
assert.equal(zeroDenied.disposition, 'DENY');
assert.equal(zeroDenied.reason_code, 'ZERO_LIMIT_DENIES_USAGE');
assert.equal(zeroDenied.remaining_after_request, 0);

const zeroRequest = evaluateUsageBudget({ limit: 0, used: 0, requested: 0 });
assert.equal(zeroRequest.disposition, 'ALLOW');
assert.equal(zeroRequest.reason_code, 'ZERO_REQUEST_WITH_ZERO_LIMIT');

const exactOne = evaluateUsageBudget({ limit: 1, used: 0, requested: 1 });
assert.equal(exactOne.disposition, 'ALLOW');
assert.equal(exactOne.remaining_after_request, 0);
const overOne = evaluateUsageBudget({ limit: 1, used: 1, requested: 1 });
assert.equal(overOne.disposition, 'DENY');
assert.equal(overOne.reason_code, 'EXACT_LIMIT_EXCEEDED');
const unresolved = evaluateUsageBudget({ limit: null, used: 0, requested: 1 });
assert.equal(unresolved.disposition, 'HOLD');
assert.equal(unresolved.reason_code, 'LIMIT_UNRESOLVED_FAIL_CLOSED');
const negativeInvalid = evaluateUsageBudget({ limit: -2, used: 0, requested: 1 });
assert.equal(negativeInvalid.disposition, 'DENY');
assert.equal(negativeInvalid.reason_code, 'LIMIT_NEGATIVE_INVALID');
for (const receipt of [unlimited, zeroDenied, zeroRequest, exactOne, overOne, unresolved, negativeInvalid]) {
  assert.equal(receipt.provider_limits_still_authoritative, true);
  assert.ok(Object.values(receipt.hard_boundaries).every((value) => value === false));
}

const licenseCandidate = validateLicenseCandidate(licenseSource);
const licenseReplay = validateLicenseCandidate(structuredClone(licenseSource));
assert.deepEqual(licenseReplay, licenseCandidate);
assert.equal(licenseCandidate.limits['ct.meter.wallet.internal.simulation.monthly'], -1);
assert.equal(licenseCandidate.limits['ct.meter.wallet.chain.broadcast.monthly'], 0);
assert.equal(licenseCandidate.limits['ct.meter.wallet.api.requests.monthly'], 100);
assert.equal(licenseCandidate.limits['ct.meter.wallet.proof.anchor.monthly'], null);
assert.match(licenseCandidate.license_digest_sha256, /^[0-9a-f]{64}$/);

const invalidLicense = structuredClone(licenseSource);
invalidLicense.limits['ct.meter.wallet.api.requests.monthly'] = -2;
assert.throws(() => validateLicenseCandidate(invalidLicense), /license_limit_invalid/);
const liveLicense = structuredClone(licenseSource);
liveLicense.checkout_enabled = true;
assert.throws(() => validateLicenseCandidate(liveLicense), /license_candidate_boundary_must_be_false/);

const ledger = new UsageLedger();
const laterEvent = {
  event_id: 'ctue_later_event_000000000001',
  idempotency_key: 'ctik_later_event_000000000001',
  tenant_ref: 'ct.tenant.synthetic',
  wallet_stable_id: 'ct.wallet.synthetic.001',
  meter_id: 'ct.meter.wallet.api.requests.monthly',
  quantity: 2,
  occurred_at: '2026-08-22T12:00:00.000Z',
  source_ref: 'synthetic:policy-metering-test',
};
const earlierEvent = {
  event_id: 'ctue_earlier_event_0000000001',
  idempotency_key: 'ctik_earlier_event_0000000001',
  tenant_ref: 'ct.tenant.synthetic',
  wallet_stable_id: 'ct.wallet.synthetic.001',
  meter_id: 'ct.meter.wallet.api.requests.monthly',
  quantity: 1,
  occurred_at: '2026-08-01T00:00:01.000Z',
  source_ref: 'synthetic:policy-metering-test',
};
const firstRecord = ledger.record(laterEvent);
const duplicateRecord = ledger.record(laterEvent);
const earlierRecord = ledger.record(earlierEvent);
assert.equal(firstRecord.state, 'RECORDED_TEST');
assert.equal(duplicateRecord.state, 'DUPLICATE');
assert.equal(earlierRecord.state, 'RECORDED_TEST');
const collision = structuredClone(laterEvent);
collision.quantity = 3;
assert.throws(() => ledger.record(collision), /usage_idempotency_collision/);

const monthWindow = calendarMonthWindow('2026-08-22T12:00:00.000Z');
assert.deepEqual(monthWindow, {
  window_start: '2026-08-01T00:00:00.000Z',
  window_end: '2026-09-01T00:00:00.000Z',
});
const rollup = ledger.rollup({
  tenant_ref: 'ct.tenant.synthetic',
  wallet_stable_id: 'ct.wallet.synthetic.001',
  meter_id: 'ct.meter.wallet.api.requests.monthly',
  ...monthWindow,
});
const rollupReplay = ledger.rollup({
  tenant_ref: 'ct.tenant.synthetic',
  wallet_stable_id: 'ct.wallet.synthetic.001',
  meter_id: 'ct.meter.wallet.api.requests.monthly',
  ...monthWindow,
});
assert.deepEqual(rollupReplay, rollup);
assert.equal(rollup.event_count, 2);
assert.equal(rollup.quantity, 3);
assert.deepEqual(rollup.event_ids, [earlierEvent.event_id, laterEvent.event_id]);
assert.equal(rollup.out_of_order_event_time_preserved, true);
assert.ok(Object.values(rollup.hard_boundaries).every((value) => value === false));

const advisor = generatePolicyAdvisorProposal({
  policy_id: artifact.policy_id,
  compiled_digest_sha256: artifact.compiled_digest_sha256,
  simulation_summary: simulation,
  meter_snapshots: [
    { meter_id: 'ct.meter.wallet.api.requests.monthly', limit: 100, used: 85 },
    { meter_id: 'ct.meter.wallet.chain.broadcast.monthly', limit: 0, used: 1 },
    { meter_id: 'ct.meter.wallet.proof.anchor.monthly', limit: null, used: 0 },
    { meter_id: 'ct.meter.wallet.internal.simulation.monthly', limit: -1, used: 1_000_000 },
  ],
  risk_signals: [
    { signal_type: 'UNMAPPED_CONSEQUENTIAL_ACTION', action: 'testnet_deploy', signal_digest_sha256: '7'.repeat(64) },
    { signal_type: 'UNCOVERED_RULE_PATH', rule_id: 'ct.rule.wallet.synthetic-uncovered.v1' },
  ],
});
const advisorReplay = generatePolicyAdvisorProposal({
  policy_id: artifact.policy_id,
  compiled_digest_sha256: artifact.compiled_digest_sha256,
  simulation_summary: structuredClone(simulation),
  meter_snapshots: [
    { meter_id: 'ct.meter.wallet.api.requests.monthly', limit: 100, used: 85 },
    { meter_id: 'ct.meter.wallet.chain.broadcast.monthly', limit: 0, used: 1 },
    { meter_id: 'ct.meter.wallet.proof.anchor.monthly', limit: null, used: 0 },
    { meter_id: 'ct.meter.wallet.internal.simulation.monthly', limit: -1, used: 1_000_000 },
  ],
  risk_signals: [
    { signal_type: 'UNMAPPED_CONSEQUENTIAL_ACTION', action: 'testnet_deploy', signal_digest_sha256: '7'.repeat(64) },
    { signal_type: 'UNCOVERED_RULE_PATH', rule_id: 'ct.rule.wallet.synthetic-uncovered.v1' },
  ],
});
assert.deepEqual(advisorReplay, advisor);
assert.equal(advisor.proposal_state, 'SUGGESTION_ONLY');
assert.equal(advisor.external_model_call_performed, false);
assert.ok(advisor.proposals.length >= 4);
assert.equal(advisor.proposals[0].proposal_type, 'ADD_EXPLICIT_DENY_RULE');
assert.match(advisor.proposal_digest_sha256, /^[0-9a-f]{64}$/);
assert.ok(Object.values(advisor.authority).every((value) => value === false));

const manifestSeed = {
  artifact_digest: artifact.compiled_digest_sha256,
  simulation_digest: simulation.simulation_digest_sha256,
  license_digest: licenseCandidate.license_digest_sha256,
  rollup_digest: rollup.rollup_digest_sha256,
  advisor_digest: advisor.proposal_digest_sha256,
};
assert.equal(sha256Hex(canonicalize(manifestSeed)), sha256Hex(canonicalize(structuredClone(manifestSeed))));

console.log(JSON.stringify({
  result: 'PASS_CHLOM_WALLET_POLICY_METERING_ENGINE',
  policy_id: artifact.policy_id,
  compiler_version: artifact.compiler_version,
  rule_count: artifact.rules.length,
  source_digest_sha256: artifact.source_digest_sha256,
  compiled_digest_sha256: artifact.compiled_digest_sha256,
  simulation_scenarios: simulation.scenario_count,
  simulation_decisions: simulation.decisions,
  simulation_digest_sha256: simulation.simulation_digest_sha256,
  exact_limit_semantics: {
    unlimited: -1,
    zero: 0,
    positive_integer: 'EXACT_LIMIT',
    unresolved: null,
    unresolved_disposition: 'HOLD_FAIL_CLOSED',
    provider_limits_still_authoritative: true,
  },
  usage_event_count: ledger.events().length,
  usage_quantity: rollup.quantity,
  out_of_order_rollup_passed: true,
  duplicate_replay_passed: true,
  idempotency_collision_rejected: true,
  license_digest_sha256: licenseCandidate.license_digest_sha256,
  advisor_proposal_count: advisor.proposals.length,
  advisor_proposal_digest_sha256: advisor.proposal_digest_sha256,
  external_model_call_performed: false,
  auto_apply: false,
  effective_offer: false,
  public_price: false,
  stripe_objects_created: false,
  checkout_enabled: false,
  provider_write: false,
  production_rights_grant: false,
  credential_activation: false,
  chain_broadcast: false,
  custody: false,
  token_issuance: false,
  money_movement: false,
  phase_advancement: false,
  merge_authorized: false,
}));
