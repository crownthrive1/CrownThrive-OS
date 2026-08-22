import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ganache from 'ganache';
import { ethers } from 'ethers';
import solc from 'solc';
import { buildUserOperationIntent } from './user-operation-intent.mjs';

const ROOT = dirname(fileURLToPath(import.meta.url));
const sourceName = 'UserOpHashV09Harness.sol';
const source = readFileSync(join(ROOT, sourceName), 'utf8');
const input = {
  language: 'Solidity',
  sources: { [sourceName]: { content: source } },
  settings: {
    optimizer: { enabled: true, runs: 200 },
    outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } },
  },
};
const output = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (output.errors ?? []).filter((item) => item.severity === 'error');
if (errors.length) throw new Error(errors.map((item) => item.formattedMessage).join('\n'));
const artifact = output.contracts?.[sourceName]?.UserOpHashV09Harness;
if (!artifact?.abi || !artifact?.evm?.bytecode?.object) throw new Error('harness_artifact_missing');

const eip1193 = ganache.provider({
  logging: { quiet: true },
  chain: { chainId: 1337, hardfork: 'shanghai' },
  wallet: { totalAccounts: 2, deterministic: true },
  miner: { instamine: 'eager' },
});
const provider = new ethers.BrowserProvider(eip1193);
const signer = await provider.getSigner(0);
const factory = new ethers.ContractFactory(artifact.abi, `0x${artifact.evm.bytecode.object}`, signer);
const harness = await factory.deploy();
await harness.waitForDeployment();

const candidate = {
  intentId: 'ct.wallet.intent.crosscheck.001',
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
const intent = buildUserOperationIntent(candidate);
const solidityOperation = {
  sender: intent.packed_user_operation.sender,
  nonce: BigInt(intent.packed_user_operation.nonce),
  initCode: intent.packed_user_operation.initCode,
  callData: intent.packed_user_operation.callData,
  accountGasLimits: intent.packed_user_operation.accountGasLimits,
  preVerificationGas: BigInt(intent.packed_user_operation.preVerificationGas),
  gasFees: intent.packed_user_operation.gasFees,
  paymasterAndData: intent.packed_user_operation.paymasterAndData,
  signature: intent.packed_user_operation.signature,
};
const solidityHash = await harness.getUserOpHash(solidityOperation, candidate.chainId, candidate.entryPoint);
const solidityStructHash = await harness.getStructHash(solidityOperation);
const solidityDomainSeparator = await harness.getDomainSeparator(candidate.chainId, candidate.entryPoint);

assert.equal(solidityHash.toLowerCase(), intent.hashes.user_operation_hash);
assert.equal(solidityStructHash.toLowerCase(), intent.hashes.struct_hash);
assert.equal(solidityDomainSeparator.toLowerCase(), intent.hashes.domain_separator);
assert.equal(await provider.getBalance(await harness.getAddress()), 0n);
assert.equal(intent.gates.broadcast, false);
assert.equal(intent.gates.deploy, false);
assert.equal(intent.gates.money_movement, false);
assert.equal(intent.gates.simulation_state, 'NOT_RUN');

console.log(JSON.stringify({
  result: 'PASS_ERC4337_V09_SOLIDITY_CROSSCHECK',
  compiler_version: solc.version(),
  local_chain_id: Number((await provider.getNetwork()).chainId),
  user_operation_hash: solidityHash.toLowerCase(),
  struct_hash: solidityStructHash.toLowerCase(),
  domain_separator: solidityDomainSeparator.toLowerCase(),
  native_value_held_wei: 0,
  external_rpc_used: false,
  production_signer_used: false,
  simulation_state: intent.gates.simulation_state,
  broadcast: false,
  money_movement: false,
  audit_claimed: false,
}));
await eip1193.disconnect();
