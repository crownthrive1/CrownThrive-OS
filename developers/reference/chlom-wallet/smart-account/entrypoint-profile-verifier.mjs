import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const PROFILE_PATH = join(HERE, 'erc4337-entrypoint-v0.9.0-profile.json');

export const PINNED = Object.freeze({
  repository: 'eth-infinitism/account-abstraction',
  releaseTag: 'v0.9.0',
  releaseCommitSha: 'b36a1ed52ae00da6f8a4c8d50181e2877e4fa410',
  releaseTreeSha: 'f75688b14e23ebddb9b81011b036bab15de89089',
  artifactPath: 'deployments/ethereum/EntryPoint.json',
  artifactBlobSha1: '8a1309dedf556eda7f64e7922e57b33c2581bb9e',
  sourcePath: 'contracts/core/EntryPoint.sol',
  sourceBlobSha1: '3b4feb6ec0ed1cf41310b24858c81f5012572af9',
  releaseAddress: '0x433709009b8330fda32311df1c2afa402ed8d009',
  artifactAddress: '0x4337084d9e255ff0702461cf8895ce9e3b5ff108',
  caip2: 'eip155:11155111',
  observedRuntimeCodehash: '0x280d5c7c0de94b512401eb9c4b0ef0436275ff03627aad0ce1f93ab1627187a0',
  runtimeCodeBytes: 22425,
  providerCount: 2,
  observationRunId: 32567112049,
  observationHeadSha: '526bb49892dff48b7ae9a50c641186ca82aaab24',
});

const READ_ONLY_RPC_METHODS = new Set(['eth_chainId', 'eth_getCode']);
const WRITE_LIKE_PREFIXES = ['eth_send', 'personal_', 'wallet_', 'miner_', 'admin_', 'debug_'];

function sortValue(value) {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortValue(value[key])]));
  }
  return value;
}

export function canonicalize(value) {
  return JSON.stringify(sortValue(value));
}

export function sha256Hex(value) {
  return createHash('sha256').update(value).digest('hex');
}

export function normalizeAddress(value) {
  if (typeof value !== 'string' || !/^0x[0-9a-fA-F]{40}$/.test(value)) {
    throw new Error('invalid_evm_address');
  }
  return value.toLowerCase();
}

export function assertReadOnlyRpcMethod(method) {
  if (typeof method !== 'string') throw new Error('rpc_method_required');
  if (WRITE_LIKE_PREFIXES.some((prefix) => method.startsWith(prefix))) {
    throw new Error('rpc_write_method_forbidden');
  }
  if (!READ_ONLY_RPC_METHODS.has(method)) throw new Error('rpc_method_not_allowlisted');
  return method;
}

export function loadProfile(path = PROFILE_PATH) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

export function verifyPinnedProfile(profile) {
  const failures = [];
  const expect = (condition, code) => { if (!condition) failures.push(code); };
  const source = profile?.source ?? {};
  const release = profile?.release_claim ?? {};
  const artifact = profile?.tagged_deployment_artifact ?? {};
  const verification = profile?.verification ?? {};
  const boundaries = profile?.hard_boundaries ?? {};

  expect(profile?.schema_version === '1.1.0', 'schema_version_mismatch');
  expect(profile?.profile_id === 'ct.wallet.erc4337.entrypoint.v0.9.0', 'profile_id_mismatch');
  expect(profile?.state === 'SOURCE_RELEASE_AND_TAG_ARTIFACT_DIVERGENCE_REGISTERED_CHAIN_CODE_UNVERIFIED', 'state_mismatch');
  expect(source.repository === PINNED.repository, 'repository_mismatch');
  expect(source.release_tag === PINNED.releaseTag, 'release_tag_mismatch');
  expect(source.release_commit_sha === PINNED.releaseCommitSha, 'release_commit_sha_mismatch');
  expect(source.release_tree_sha === PINNED.releaseTreeSha, 'release_tree_sha_mismatch');
  expect(source.deployment_artifact_path === PINNED.artifactPath, 'artifact_path_mismatch');
  expect(source.deployment_artifact_git_blob_sha1 === PINNED.artifactBlobSha1, 'artifact_blob_mismatch');
  expect(source.entrypoint_source_path === PINNED.sourcePath, 'source_path_mismatch');
  expect(source.entrypoint_source_git_blob_sha1 === PINNED.sourceBlobSha1, 'source_blob_mismatch');
  expect(normalizeAddress(release.entrypoint_address) === PINNED.releaseAddress, 'release_address_mismatch');
  expect(normalizeAddress(artifact.entrypoint_address) === PINNED.artifactAddress, 'artifact_address_mismatch');
  expect(PINNED.releaseAddress !== PINNED.artifactAddress, 'source_divergence_missing');
  expect(profile?.target?.caip2 === PINNED.caip2, 'chain_id_mismatch');
  expect(verification.release_and_artifact_addresses_match === false, 'false_source_reconciliation_claim');
  expect(verification.external_read_only_chain_readback_completed === true, 'external_readback_missing');
  expect(verification.external_read_only_provider_count === PINNED.providerCount, 'provider_count_mismatch');
  expect(verification.external_read_only_provider_agreement === true, 'provider_agreement_missing');
  expect(verification.runtime_code_present === true, 'runtime_code_presence_missing');
  expect(verification.runtime_code_bytes === PINNED.runtimeCodeBytes, 'runtime_code_size_mismatch');
  expect(verification.observed_runtime_codehash === PINNED.observedRuntimeCodehash, 'observed_runtime_codehash_mismatch');
  expect(verification.approved_runtime_codehash === null, 'approved_codehash_must_remain_null');
  expect(verification.runtime_codehash_independently_approved === false, 'false_independent_approval_claim');
  expect(verification.runtime_codehash_verified === false, 'false_runtime_codehash_verification_claim');
  expect(verification.observation_workflow_run_id === PINNED.observationRunId, 'observation_run_mismatch');
  expect(verification.observation_head_sha === PINNED.observationHeadSha, 'observation_head_mismatch');
  expect(verification.disposition === 'HOLD_RUNTIME_CODEHASH_INDEPENDENT_APPROVAL_REQUIRED', 'disposition_mismatch');
  expect(Array.isArray(profile.allowed_rpc_methods) && profile.allowed_rpc_methods.length === 2, 'rpc_allowlist_shape');
  expect(profile.allowed_rpc_methods.every((method) => READ_ONLY_RPC_METHODS.has(method)), 'rpc_allowlist_mismatch');
  expect(Object.values(boundaries).every((value) => value === false), 'hard_boundary_armed');

  return {
    ok: failures.length === 0,
    failures,
    profile_digest_sha256: sha256Hex(canonicalize(profile)),
    release_address: PINNED.releaseAddress,
    artifact_address: PINNED.artifactAddress,
    source_divergence_registered: true,
    external_read_only_chain_readback_completed: true,
    provider_agreement: true,
    observed_runtime_codehash: PINNED.observedRuntimeCodehash,
    runtime_codehash_independently_approved: false,
    runtime_codehash_verified: false,
    testnet_broadcast_authorized: false,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const result = verifyPinnedProfile(loadProfile(process.argv[2]));
  if (!result.ok) {
    console.error(JSON.stringify(result));
    process.exit(1);
  }
  console.log(JSON.stringify({ result: 'PASS_ERC4337_V09_SOURCE_AND_OBSERVATION_PROFILE', ...result }));
}
