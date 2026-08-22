import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { setTimeout as sleep } from 'node:timers/promises';
import { runReadOnlyCodePreflight } from './read-only-chain-code-preflight.mjs';

const TARGET = Object.freeze({
  chain_id_caip2: 'eip155:11155111',
  chain_id_hex: '0xaa36a7',
  entrypoint_address: '0x433709009B8330FDa32311DF1C2AFA402eD8D009',
});
const PROVIDER_QUORUM_REQUIRED = 2;
const MAX_ATTEMPTS_PER_PROVIDER = 3;

const PROVIDERS = Object.freeze([
  {
    provider_id: 'publicnode',
    endpoint: 'https://ethereum-sepolia-rpc.publicnode.com',
    source: 'https://ethereum-sepolia-rpc.publicnode.com/',
  },
  {
    provider_id: '1rpc',
    endpoint: 'https://public.1rpc.io/sepolia',
    source: 'https://docs.1rpc.io/using-the-web3-api/networks',
  },
  {
    provider_id: 'sepolia-dev',
    endpoint: 'https://rpc.sepolia.dev',
    source: 'https://sepolia.dev/',
  },
]);

function canonicalize(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function sha256Hex(value) {
  return createHash('sha256').update(value).digest('hex');
}

function safeErrorCode(error) {
  const value = error instanceof Error ? error.message : String(error);
  return value.replace(/[^A-Za-z0-9_:-]/g, '_').slice(0, 120) || 'unknown_provider_error';
}

async function observeProvider(provider) {
  let lastError = 'provider_not_attempted';
  for (let attempt = 1; attempt <= MAX_ATTEMPTS_PER_PROVIDER; attempt += 1) {
    try {
      const result = await runReadOnlyCodePreflight({
        rpcUrl: provider.endpoint,
        expectedChainIdHex: TARGET.chain_id_hex,
        address: TARGET.entrypoint_address,
        expectedRuntimeCodehash: null,
        timeoutMs: 20_000,
      });
      assert.equal(result.ok, false);
      assert.equal(result.disposition, 'HOLD_CODEHASH_APPROVAL_REQUIRED');
      assert.equal(result.expected_chain_id_hex, TARGET.chain_id_hex);
      assert.equal(result.observed_chain_id_hex, TARGET.chain_id_hex);
      assert.equal(result.address, TARGET.entrypoint_address.toLowerCase());
      assert.match(result.observed_runtime_codehash, /^0x[0-9a-f]{64}$/);
      assert.ok(Number.isSafeInteger(result.runtime_code_bytes) && result.runtime_code_bytes > 0);
      assert.deepEqual(result.rpc_methods_used, ['eth_chainId', 'eth_getCode']);
      assert.equal(result.broadcast, false);
      assert.equal(result.money_movement, false);
      return {
        ok: true,
        observation: {
          provider_id: provider.provider_id,
          endpoint_origin: new URL(provider.endpoint).origin,
          endpoint_source: provider.source,
          attempts: attempt,
          observed_chain_id_hex: result.observed_chain_id_hex,
          entrypoint_address: result.address,
          runtime_code_bytes: result.runtime_code_bytes,
          observed_runtime_codehash: result.observed_runtime_codehash,
          rpc_methods_used: result.rpc_methods_used,
        },
      };
    } catch (error) {
      lastError = safeErrorCode(error);
      if (attempt < MAX_ATTEMPTS_PER_PROVIDER) await sleep(attempt * 750);
    }
  }
  return {
    ok: false,
    failure: {
      provider_id: provider.provider_id,
      endpoint_origin: new URL(provider.endpoint).origin,
      endpoint_source: provider.source,
      attempts: MAX_ATTEMPTS_PER_PROVIDER,
      error_code: lastError,
    },
  };
}

const providerResults = await Promise.all(PROVIDERS.map(observeProvider));
const observations = providerResults.filter((item) => item.ok).map((item) => item.observation);
const failures = providerResults.filter((item) => !item.ok).map((item) => item.failure);

const boundary = {
  runtime_codehash_independently_approved: false,
  source_profile_promoted: false,
  account_implementation_selected: false,
  factory_selected: false,
  signer_used: false,
  user_operation_created: false,
  simulation_completed: false,
  broadcast_performed: false,
  deployment_performed: false,
  custody: false,
  money_movement: false,
  phase_advancement: false,
};

if (observations.length < PROVIDER_QUORUM_REQUIRED) {
  console.log(JSON.stringify({
    result: 'HOLD_EXTERNAL_READ_ONLY_PROVIDER_QUORUM_NOT_MET',
    evidence_contract: 'ct.wallet.erc4337.multi-provider-readonly-observation.v2',
    target: TARGET,
    provider_quorum_required: PROVIDER_QUORUM_REQUIRED,
    provider_attempted_count: PROVIDERS.length,
    provider_success_count: observations.length,
    provider_failure_count: failures.length,
    providers: observations,
    provider_failures: failures,
    ...boundary,
  }));
  process.exitCode = 1;
} else {
  const codehashes = new Set(observations.map((item) => item.observed_runtime_codehash));
  const codeSizes = new Set(observations.map((item) => item.runtime_code_bytes));
  if (codehashes.size !== 1 || codeSizes.size !== 1) {
    console.log(JSON.stringify({
      result: 'HOLD_EXTERNAL_READ_ONLY_PROVIDER_DISAGREEMENT',
      evidence_contract: 'ct.wallet.erc4337.multi-provider-readonly-observation.v2',
      target: TARGET,
      provider_quorum_required: PROVIDER_QUORUM_REQUIRED,
      provider_attempted_count: PROVIDERS.length,
      provider_success_count: observations.length,
      provider_failure_count: failures.length,
      providers: observations,
      provider_failures: failures,
      ...boundary,
    }));
    process.exitCode = 1;
  } else {
    const observedRuntimeCodehash = observations[0].observed_runtime_codehash;
    const runtimeCodeBytes = observations[0].runtime_code_bytes;
    const evidenceBody = {
      evidence_contract: 'ct.wallet.erc4337.multi-provider-readonly-observation.v2',
      target: TARGET,
      provider_quorum_required: PROVIDER_QUORUM_REQUIRED,
      provider_attempted_count: PROVIDERS.length,
      provider_success_count: observations.length,
      provider_failure_count: failures.length,
      providers: observations,
      provider_failures: failures,
      provider_agreement: true,
      observed_runtime_codehash: observedRuntimeCodehash,
      runtime_code_bytes: runtimeCodeBytes,
      ...boundary,
    };
    const evidenceDigest = sha256Hex(canonicalize(evidenceBody));
    console.log(JSON.stringify({
      result: 'PASS_EXTERNAL_READ_ONLY_MULTI_PROVIDER_QUORUM_OBSERVATION',
      ...evidenceBody,
      evidence_digest_sha256: evidenceDigest,
    }));
  }
}
