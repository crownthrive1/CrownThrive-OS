import assert from 'node:assert/strict';
import {
  DOMAIN_TYPEHASH,
  PACKED_USEROP_TYPEHASH,
  buildUserOperationIntent,
  keccak256,
  packHighLow128,
} from './user-operation-intent.mjs';

assert.equal(keccak256(new Uint8Array()), '0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470');
assert.equal(keccak256('abc'), '0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45');
assert.equal(PACKED_USEROP_TYPEHASH.length, 66);
assert.equal(DOMAIN_TYPEHASH.length, 66);
assert.equal(packHighLow128(1n, 2n), '0x0000000000000000000000000000000100000000000000000000000000000002');

const input = {
  intentId: 'ct.wallet.intent.test.001',
  chainId: 11155111n,
  entryPoint: '0x433709009B8330FDa32311DF1C2AFA402eD8D009',
  sender: '0x1111111111111111111111111111111111111111',
  nonce: 0n,
  initCode: '0x',
  callData: '0x',
  verificationGasLimit: 150000n,
  callGasLimit: 100000n,
  preVerificationGas: 50000n,
  maxPriorityFeePerGas: 1000000000n,
  maxFeePerGas: 2000000000n,
  paymasterAndData: '0x',
  signature: '0x',
};
const first = buildUserOperationIntent(input);
const second = buildUserOperationIntent(input);
assert.deepEqual(first, second);
assert.equal(first.gates.broadcast, false);
assert.equal(first.gates.deploy, false);
assert.equal(first.gates.money_movement, false);
assert.equal(first.gates.simulation_state, 'NOT_RUN');
assert.equal(first.gates.factory_state, 'UNSELECTED');
assert.equal(first.gates.eip7702_state, 'NOT_SUPPORTED');
assert.equal(first.gates.entrypoint_codehash_state, 'UNVERIFIED');
assert.equal(first.gates.call_data_semantic_review, 'EMPTY_NO_ACTION');
assert.match(first.intent_sha256, /^0x[0-9a-f]{64}$/);
assert.match(first.hashes.user_operation_hash, /^0x[0-9a-f]{64}$/);

const otherChain = buildUserOperationIntent({ ...input, chainId: 1n, intentId: 'ct.wallet.intent.test.002' });
assert.notEqual(otherChain.hashes.domain_separator, first.hashes.domain_separator);
assert.notEqual(otherChain.hashes.user_operation_hash, first.hashes.user_operation_hash);
const otherEntry = buildUserOperationIntent({ ...input, entryPoint: '0x4337084D9E255Ff0702461CF8895CE9E3b5Ff108', intentId: 'ct.wallet.intent.test.003' });
assert.notEqual(otherEntry.hashes.user_operation_hash, first.hashes.user_operation_hash);
const opaqueCall = buildUserOperationIntent({ ...input, callData: '0x1234', intentId: 'ct.wallet.intent.test.004' });
assert.equal(opaqueCall.gates.call_data_semantic_review, 'HOLD_OPAQUE_CALLDATA');
assert.throws(() => buildUserOperationIntent({ ...input, initCode: '0x12' }), /init_code_disabled/);
assert.throws(() => buildUserOperationIntent({ ...input, paymasterAndData: '0x12' }), /paymaster_disabled/);
assert.throws(() => buildUserOperationIntent({ ...input, signature: '0x12' }), /signature_must_be_empty/);
assert.throws(() => packHighLow128(1n << 128n, 0n), /uint_out_of_range/);

console.log(JSON.stringify({
  result: 'PASS_ERC4337_V09_INTENT',
  keccak_vectors: 2,
  deterministic: true,
  user_operation_hash: first.hashes.user_operation_hash,
  intent_sha256: first.intent_sha256,
  simulation_state: first.gates.simulation_state,
  broadcast: first.gates.broadcast,
  money_movement: first.gates.money_movement,
}));
