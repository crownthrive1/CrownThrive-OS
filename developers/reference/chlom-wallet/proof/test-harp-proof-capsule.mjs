import assert from 'node:assert/strict';
import {
  buildHarpCapsule,
  generateHarpProof,
  harpLeafDigest,
  verifyHarpCapsule,
  verifyHarpProof,
} from './harp-proof-capsule.mjs';
import { sha256Hex } from '../common/canonical-json.mjs';

const createdAt = '2026-08-22T07:00:00Z';
const scope = 'ct.wallet.proof.phase-c.synthetic';
const items = Array.from({ length: 4097 }, (_, index) => ({
  record_id: `ct.record.${String(index + 1).padStart(5, '0')}`,
  record_type: index % 4 === 0 ? 'wallet_event' : index % 4 === 1 ? 'rights_commitment' : index % 4 === 2 ? 'impact_obligation' : 'value_receipt',
  payload_digest: sha256Hex(`payload:${index}`),
  policy_digest: sha256Hex(`policy:${index % 7}`),
  occurred_at: `2026-08-22T${String(Math.floor(index / 3600) % 24).padStart(2, '0')}:${String(Math.floor(index / 60) % 60).padStart(2, '0')}:${String(index % 60).padStart(2, '0')}Z`,
  source_event_seq: index + 1,
  public_metadata: { lane: ['Money', 'Rights', 'Rewards', 'Impact'][index % 4], cohort: index % 13 },
}));

const forward = buildHarpCapsule({
  capsule_id: 'ct.harp.phase-c.synthetic.001',
  scope,
  policy_version: 'harp-v1-controlled-test',
  created_at: createdAt,
  items,
});
const reverse = buildHarpCapsule({
  capsule_id: 'ct.harp.phase-c.synthetic.001',
  scope,
  policy_version: 'harp-v1-controlled-test',
  created_at: createdAt,
  items: [...items].reverse(),
});
assert.equal(forward.capsule.root_digest, reverse.capsule.root_digest);
assert.equal(forward.capsule.manifest_digest, reverse.capsule.manifest_digest);
assert.equal(forward.capsule.leaf_count, 4097);
assert.equal(forward.capsule.raw_evidence_included, false);
assert.equal(forward.capsule.public_chain_broadcast, false);
assert.equal(forward.capsule.money_movement, false);
assert.deepEqual(verifyHarpCapsule(forward.capsule), {
  valid: true,
  root_valid: true,
  manifest_valid: true,
  computed_root_digest: forward.capsule.root_digest,
  computed_manifest_digest: forward.capsule.manifest_digest,
});

const targetIndexes = [0, 1, 2, 2048, 4095, 4096];
let state = 0x13579bdf;
for (let count = 0; count < 512; count++) {
  state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
  targetIndexes.push(state % items.length);
}
for (const index of targetIndexes) {
  const item = items[index];
  const proof = generateHarpProof(forward, item.record_id);
  const result = verifyHarpProof({ scope, item, proof: proof.proof, root_digest: forward.capsule.root_digest });
  assert.equal(result.valid, true, `proof must validate for ${item.record_id}`);
}

const target = items[2333];
const targetProof = generateHarpProof(forward, target.record_id);
const tamperedItem = { ...target, payload_digest: sha256Hex('tampered') };
assert.equal(verifyHarpProof({ scope, item: tamperedItem, proof: targetProof.proof, root_digest: forward.capsule.root_digest }).valid, false);
const tamperedProof = structuredClone(targetProof.proof);
tamperedProof[0].digest = sha256Hex('tampered-sibling');
assert.equal(verifyHarpProof({ scope, item: target, proof: tamperedProof, root_digest: forward.capsule.root_digest }).valid, false);
assert.equal(verifyHarpProof({ scope: `${scope}.wrong`, item: target, proof: targetProof.proof, root_digest: forward.capsule.root_digest }).valid, false);
assert.notEqual(harpLeafDigest(scope, target), harpLeafDigest(scope, { ...target, record_id: `${target.record_id}.copy` }));

assert.throws(() => buildHarpCapsule({
  capsule_id: 'ct.harp.duplicate', scope, policy_version: 'v1', created_at: createdAt,
  items: [items[0], { ...items[0] }],
}), /harp_duplicate_record_id/);
assert.throws(() => buildHarpCapsule({
  capsule_id: 'ct.harp.raw', scope, policy_version: 'v1', created_at: createdAt,
  items: [{ ...items[0], raw_payload: 'not-allowed' }],
}), /harp_item_key_not_allowed/);
assert.throws(() => buildHarpCapsule({
  capsule_id: 'ct.harp.secret', scope, policy_version: 'v1', created_at: createdAt,
  items: [{ ...items[0], public_metadata: { api_key: 'redacted' } }],
}), /public_metadata_forbidden_key/);

const tamperedCapsule = structuredClone(forward.capsule);
tamperedCapsule.commitments[5].leaf_digest = sha256Hex('tampered-leaf');
assert.equal(verifyHarpCapsule(tamperedCapsule).valid, false);

console.log(JSON.stringify({
  result: 'PASS_HARP_PROOF_CAPSULE',
  leaf_count: forward.capsule.leaf_count,
  inclusion_proofs_verified: targetIndexes.length,
  reorder_deterministic: true,
  odd_leaf_count_supported: true,
  duplicate_record_rejected: true,
  raw_evidence_field_rejected: true,
  metadata_secret_key_rejected: true,
  tamper_rejected: true,
  public_chain_broadcast: false,
  money_movement: false,
}));
