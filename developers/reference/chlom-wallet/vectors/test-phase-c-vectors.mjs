import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildHarpCapsule, generateHarpProof, verifyHarpProof } from '../proof/harp-proof-capsule.mjs';
import { compileSettlementPlan, compileReversalPlan } from '../settlement/easor-settlement-plan.mjs';
import { buildPortableWalletCapsule, planProviderRemap, verifyPortableWalletCapsule } from '../portability/portable-wallet-capsule.mjs';

const vectors = JSON.parse(readFileSync(new URL('./phase-c-test-vectors.json', import.meta.url), 'utf8'));
assert.equal(vectors.schema_version, '1.0.0');
assert.equal(vectors.state, 'CONTROLLED_TEST');
assert.equal(vectors.production_activation, false);

const harp = buildHarpCapsule(vectors.harp.input);
assert.equal(harp.capsule.root_digest, vectors.harp.expected.root_digest);
assert.equal(harp.capsule.manifest_digest, vectors.harp.expected.manifest_digest);
assert.deepEqual(harp.capsule.commitments, vectors.harp.expected.commitments);
const generatedProof = generateHarpProof(harp, 'ct.record.002');
assert.deepEqual(generatedProof, vectors.harp.expected.proof_record_002);
const proofItem = vectors.harp.input.items.find((item) => item.record_id === 'ct.record.002');
assert.equal(verifyHarpProof({ scope: vectors.harp.input.scope, item: proofItem, proof: generatedProof.proof, root_digest: generatedProof.root_digest }).valid, true);

const plan = compileSettlementPlan(vectors.easor.input);
assert.equal(plan.plan_digest, vectors.easor.expected.plan_digest);
assert.deepEqual(plan.legs, vectors.easor.expected.legs);
assert.deepEqual(plan.impact_obligations, vectors.easor.expected.impact_obligations);
assert.deepEqual(plan.rights_obligations, vectors.easor.expected.rights_obligations);
assert.deepEqual(plan.reward_obligations, vectors.easor.expected.reward_obligations);
const reversal = compileReversalPlan({ ...vectors.easor.reversal_input, original_plan: plan });
assert.equal(reversal.reversal_digest, vectors.easor.reversal_expected.reversal_digest);
assert.deepEqual(reversal.reversal_legs, vectors.easor.reversal_expected.reversal_legs);

const capsule = buildPortableWalletCapsule(vectors.portable_wallet.input);
assert.equal(capsule.capsule_digest, vectors.portable_wallet.expected.capsule_digest);
assert.equal(capsule.chain_head, vectors.portable_wallet.expected.chain_head);
assert.equal(capsule.event_count, vectors.portable_wallet.expected.event_count);
assert.equal(verifyPortableWalletCapsule(capsule).valid, true);
assert.deepEqual(planProviderRemap(capsule, vectors.portable_wallet.remap_input), vectors.portable_wallet.remap_expected);

for (const [key, value] of Object.entries(vectors.boundaries)) assert.equal(value, false, `${key}_must_remain_false`);

console.log(JSON.stringify({
  result: 'PASS_PHASE_C_TEST_VECTORS',
  vector_set_id: vectors.vector_set_id,
  harp_root_digest: harp.capsule.root_digest,
  easor_plan_digest: plan.plan_digest,
  portable_capsule_digest: capsule.capsule_digest,
  production_activation: false,
  public_chain_broadcast: false,
  provider_write: false,
  money_movement: false,
}));
