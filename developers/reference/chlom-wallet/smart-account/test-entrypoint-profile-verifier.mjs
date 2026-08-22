import assert from 'node:assert/strict';
import {
  assertReadOnlyRpcMethod,
  loadProfile,
  normalizeAddress,
  verifyPinnedProfile,
} from './entrypoint-profile-verifier.mjs';

const profile = loadProfile();
const verified = verifyPinnedProfile(profile);
assert.equal(verified.ok, true, JSON.stringify(verified.failures));
assert.equal(verified.failures.length, 0);
assert.equal(verified.profile_digest_sha256.length, 64);
assert.equal(verified.source_divergence_registered, true);
assert.equal(verified.chain_code_verified, false);
assert.equal(verified.testnet_broadcast_authorized, false);
assert.notEqual(verified.release_address, verified.artifact_address);
assert.equal(normalizeAddress(profile.release_claim.entrypoint_address), verified.release_address);

assert.equal(assertReadOnlyRpcMethod('eth_chainId'), 'eth_chainId');
assert.equal(assertReadOnlyRpcMethod('eth_getCode'), 'eth_getCode');
assert.throws(() => assertReadOnlyRpcMethod('eth_sendRawTransaction'), /rpc_write_method_forbidden/);
assert.throws(() => assertReadOnlyRpcMethod('personal_sign'), /rpc_write_method_forbidden/);
assert.throws(() => assertReadOnlyRpcMethod('eth_getBalance'), /rpc_method_not_allowlisted/);

const falseChainClaim = structuredClone(profile);
falseChainClaim.verification.runtime_codehash_verified = true;
assert.equal(verifyPinnedProfile(falseChainClaim).ok, false);
assert.ok(verifyPinnedProfile(falseChainClaim).failures.includes('false_runtime_codehash_claim'));

const armed = structuredClone(profile);
armed.hard_boundaries.testnet_broadcast = true;
assert.equal(verifyPinnedProfile(armed).ok, false);
assert.ok(verifyPinnedProfile(armed).failures.includes('hard_boundary_armed'));

const collapsed = structuredClone(profile);
collapsed.tagged_deployment_artifact.entrypoint_address = collapsed.release_claim.entrypoint_address;
assert.equal(verifyPinnedProfile(collapsed).ok, false);
assert.ok(verifyPinnedProfile(collapsed).failures.includes('artifact_address_mismatch'));

console.log(JSON.stringify({
  result: 'PASS_ERC4337_V09_SOURCE_PROFILE',
  profile_digest_sha256: verified.profile_digest_sha256,
  official_release_pinned: true,
  tagged_artifact_pinned: true,
  source_divergence_registered: true,
  chain_runtime_code_verified: false,
  rpc_write_methods_rejected: true,
  testnet_broadcast_authorized: false,
}));
