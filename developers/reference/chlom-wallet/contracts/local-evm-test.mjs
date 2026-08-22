import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ganache from 'ganache';
import { ethers } from 'ethers';
import solc from 'solc';

const ROOT = dirname(fileURLToPath(import.meta.url));
const contractFiles = [
  'ChlomAnchorRegistry.sol',
  'ChlomEntitlementRegistry.sol',
  'ChlomSplitPolicyRegistry.sol',
  'ThriveFundObligationRegistry.sol',
];
const sources = Object.fromEntries(contractFiles.map((file) => [file, { content: readFileSync(join(ROOT, file), 'utf8') }]));
const compilerInput = {
  language: 'Solidity',
  sources,
  settings: {
    optimizer: { enabled: true, runs: 200 },
    outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object', 'evm.deployedBytecode.object'] } },
  },
};
const compilerOutput = JSON.parse(solc.compile(JSON.stringify(compilerInput)));
const compilerErrors = (compilerOutput.errors ?? []).filter((entry) => entry.severity === 'error');
if (compilerErrors.length) throw new Error(compilerErrors.map((e) => e.formattedMessage).join('\n'));

function artifact(file, name) {
  const value = compilerOutput.contracts?.[file]?.[name];
  if (!value?.abi || !value?.evm?.bytecode?.object) throw new Error(`missing_artifact:${file}:${name}`);
  return { abi: value.abi, bytecode: `0x${value.evm.bytecode.object}`, deployedBytecode: `0x${value.evm.deployedBytecode.object}` };
}

const eip1193 = ganache.provider({
  logging: { quiet: true },
  chain: { chainId: 1337, hardfork: 'shanghai' },
  wallet: { totalAccounts: 4, deterministic: true },
  miner: { instamine: 'eager' },
});
const provider = new ethers.BrowserProvider(eip1193);
const admin = await provider.getSigner(0);
const operator = await provider.getSigner(1);
const unauthorized = await provider.getSigner(2);
const adminAddress = await admin.getAddress();
const operatorAddress = await operator.getAddress();

async function deploy(file, name) {
  const a = artifact(file, name);
  const factory = new ethers.ContractFactory(a.abi, a.bytecode, admin);
  const contract = await factory.deploy(adminAddress);
  await contract.waitForDeployment();
  const runtime = await provider.getCode(await contract.getAddress());
  assert.notEqual(runtime, '0x');
  return contract;
}
async function send(txPromise) {
  const tx = await txPromise;
  const receipt = await tx.wait();
  assert.equal(receipt.status, 1);
  return receipt;
}
let expectedReverts = 0;
async function expectRevert(promiseFactory, label) {
  try {
    const maybeTx = await promiseFactory();
    if (maybeTx && typeof maybeTx.wait === 'function') await maybeTx.wait();
    assert.fail(`expected_revert:${label}`);
  } catch (error) {
    if (String(error?.message ?? error).startsWith('expected_revert:')) throw error;
    expectedReverts++;
  }
}
const b32 = (value) => ethers.id(value);
const zero32 = ethers.ZeroHash;

const anchor = await deploy('ChlomAnchorRegistry.sol', 'ChlomAnchorRegistry');
await send(anchor.setOperator(operatorAddress));
const batch1 = b32('batch-1');
await send(anchor.connect(operator).anchor(batch1, b32('root-1'), b32('policy-1')));
const anchorRow = await anchor.getAnchor(batch1);
assert.equal(anchorRow.rootDigest, b32('root-1'));
assert.equal(anchorRow.policyDigest, b32('policy-1'));
assert.equal(anchorRow.committer.toLowerCase(), operatorAddress.toLowerCase());
await expectRevert(() => anchor.connect(operator).anchor(batch1, b32('root-duplicate'), b32('policy-duplicate')), 'duplicate_anchor');
await expectRevert(() => anchor.connect(unauthorized).anchor(b32('unauthorized'), b32('root'), b32('policy')), 'unauthorized_anchor');
await send(anchor.setPaused(true));
await expectRevert(() => anchor.connect(operator).anchor(b32('paused'), b32('root'), b32('policy')), 'paused_anchor');
await send(anchor.setPaused(false));
await expectRevert(() => anchor.connect(operator).anchor(zero32, b32('root'), b32('policy')), 'zero_anchor_id');

const entitlement = await deploy('ChlomEntitlementRegistry.sol', 'ChlomEntitlementRegistry');
await send(entitlement.setOperator(operatorAddress));
const entitlementId = b32('entitlement-1');
await send(entitlement.connect(operator).record(entitlementId, b32('subject-1'), b32('asset-1'), b32('terms-1'), 100, 1000));
assert.equal(await entitlement.isActive(entitlementId, 100), true);
assert.equal(await entitlement.isActive(entitlementId, 999), true);
assert.equal(await entitlement.isActive(entitlementId, 1000), false);
await expectRevert(() => entitlement.connect(unauthorized).revoke(entitlementId, b32('reason')), 'unauthorized_revoke');
await expectRevert(() => entitlement.connect(operator).revoke(entitlementId, zero32), 'zero_revoke_reason');
await send(entitlement.connect(operator).revoke(entitlementId, b32('reason-1')));
assert.equal(await entitlement.isActive(entitlementId, 500), false);
await expectRevert(() => entitlement.connect(operator).revoke(entitlementId, b32('reason-2')), 'double_revoke');
await expectRevert(() => entitlement.connect(operator).record(entitlementId, b32('subject-1'), b32('asset-1'), b32('terms-1'), 100, 1000), 'duplicate_entitlement');

const split = await deploy('ChlomSplitPolicyRegistry.sol', 'ChlomSplitPolicyRegistry');
await send(split.setOperator(operatorAddress));
const policy1 = b32('policy-1');
const policy2 = b32('policy-2');
assert.equal(await split.validateBps([7000, 2000, 1000]), true);
assert.equal(await split.validateBps([7000, 2000, 999]), false);
await expectRevert(() => split.connect(operator).record(b32('bad-policy'), b32('bad-schedule'), [7000, 2000, 999]), 'invalid_bps');
await send(split.connect(operator).record(policy1, b32('schedule-1'), [7000, 2000, 1000]));
await send(split.connect(operator).record(policy2, b32('schedule-2'), [6000, 3000, 1000]));
await send(split.connect(operator).supersede(policy1, policy2));
assert.equal((await split.get(policy1)).superseded, true);
await expectRevert(() => split.connect(operator).supersede(policy2, policy2), 'self_replacement');
await expectRevert(() => split.connect(operator).supersede(policy2, b32('missing-policy')), 'missing_replacement');

const thrive = await deploy('ThriveFundObligationRegistry.sol', 'ThriveFundObligationRegistry');
await send(thrive.setOperator(operatorAddress));
const obligation1 = b32('obligation-1');
await expectRevert(() => thrive.connect(operator).record(b32('zero-obligation'), b32('source'), b32('program'), b32('asset'), 0), 'zero_obligation');
await send(thrive.connect(operator).record(obligation1, b32('source-1'), b32('program-1'), b32('usd'), 12345));
assert.equal((await thrive.get(obligation1)).amountMinor, 12345n);
await expectRevert(() => thrive.connect(operator).markSettledExternally(obligation1, zero32), 'zero_settlement_evidence');
await send(thrive.connect(operator).markSettledExternally(obligation1, b32('external-settlement-receipt')));
assert.equal((await thrive.get(obligation1)).state, 2n);
await expectRevert(() => thrive.connect(operator).markSettledExternally(obligation1, b32('again')), 'double_settlement');
await send(thrive.connect(operator).reverse(obligation1, b32('reversal-evidence')));
assert.equal((await thrive.get(obligation1)).state, 3n);
await expectRevert(() => thrive.connect(operator).reverse(obligation1, b32('again')), 'double_reversal');

const deployed = [anchor, entitlement, split, thrive];
for (const contract of deployed) {
  assert.equal(await provider.getBalance(await contract.getAddress()), 0n, 'controlled-test registry must not hold native value');
}

console.log(JSON.stringify({
  result: 'PASS_LOCAL_EVM_EXECUTION',
  chain_id: Number((await provider.getNetwork()).chainId),
  compiler_version: solc.version(),
  contracts_deployed: deployed.length,
  expected_reverts: expectedReverts,
  native_value_held_wei: 0,
  external_rpc_used: false,
  production_signer_used: false,
  audit_claimed: false,
  mainnet_deployment: false,
}));
await eip1193.disconnect();
