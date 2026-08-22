import { assertReadOnlyRpcMethod, normalizeAddress } from './entrypoint-profile-verifier.mjs';
import { hexToBytes, keccak256 } from './user-operation-intent.mjs';

const DEFAULT_TIMEOUT_MS = 10_000;

export function validateRpcUrl(value, { allowLocalhost = false } = {}) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error('invalid_rpc_url');
  }
  const local = ['127.0.0.1', 'localhost', '::1'].includes(url.hostname);
  if (url.protocol !== 'https:' && !(allowLocalhost && local && url.protocol === 'http:')) {
    throw new Error('rpc_url_must_use_https');
  }
  if (url.username || url.password) throw new Error('rpc_url_userinfo_forbidden');
  return url.toString();
}

export async function jsonRpcRead(url, method, params, { timeoutMs = DEFAULT_TIMEOUT_MS, allowLocalhost = false } = {}) {
  const safeUrl = validateRpcUrl(url, { allowLocalhost });
  assertReadOnlyRpcMethod(method);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(safeUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
      signal: controller.signal,
      redirect: 'error',
    });
    if (!response.ok) throw new Error(`rpc_http_${response.status}`);
    const body = await response.json();
    if (body?.error) throw new Error(`rpc_error_${body.error.code ?? 'unknown'}`);
    if (!Object.prototype.hasOwnProperty.call(body ?? {}, 'result')) throw new Error('rpc_result_missing');
    return body.result;
  } finally {
    clearTimeout(timer);
  }
}

export function normalizeHexQuantity(value) {
  if (typeof value !== 'string' || !/^0x[0-9a-fA-F]+$/.test(value)) throw new Error('invalid_hex_quantity');
  return `0x${BigInt(value).toString(16)}`;
}

export function normalizeRuntimeCode(value) {
  if (typeof value !== 'string' || !/^0x(?:[0-9a-fA-F]{2})*$/.test(value)) throw new Error('invalid_runtime_code');
  return value.toLowerCase();
}

export async function runReadOnlyCodePreflight({
  rpcUrl,
  expectedChainIdHex,
  address,
  expectedRuntimeCodehash = null,
  allowLocalhost = false,
  timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
  const normalizedAddress = normalizeAddress(address);
  const expectedChain = normalizeHexQuantity(expectedChainIdHex);
  const observedChain = normalizeHexQuantity(await jsonRpcRead(rpcUrl, 'eth_chainId', [], { timeoutMs, allowLocalhost }));
  if (observedChain !== expectedChain) {
    return {
      ok: false,
      disposition: 'HOLD_CHAIN_ID_MISMATCH',
      expected_chain_id_hex: expectedChain,
      observed_chain_id_hex: observedChain,
      address: normalizedAddress,
      rpc_methods_used: ['eth_chainId'],
      broadcast: false,
      money_movement: false,
    };
  }

  const code = normalizeRuntimeCode(await jsonRpcRead(
    rpcUrl,
    'eth_getCode',
    [normalizedAddress, 'latest'],
    { timeoutMs, allowLocalhost },
  ));
  if (code === '0x') {
    return {
      ok: false,
      disposition: 'HOLD_RUNTIME_CODE_MISSING',
      expected_chain_id_hex: expectedChain,
      observed_chain_id_hex: observedChain,
      address: normalizedAddress,
      observed_runtime_codehash: null,
      rpc_methods_used: ['eth_chainId', 'eth_getCode'],
      broadcast: false,
      money_movement: false,
    };
  }

  const observedHash = keccak256(hexToBytes(code)).toLowerCase();
  if (!expectedRuntimeCodehash) {
    return {
      ok: false,
      disposition: 'HOLD_CODEHASH_APPROVAL_REQUIRED',
      expected_chain_id_hex: expectedChain,
      observed_chain_id_hex: observedChain,
      address: normalizedAddress,
      observed_runtime_codehash: observedHash,
      runtime_code_bytes: (code.length - 2) / 2,
      rpc_methods_used: ['eth_chainId', 'eth_getCode'],
      broadcast: false,
      money_movement: false,
    };
  }

  const expectedHash = expectedRuntimeCodehash.toLowerCase();
  if (!/^0x[0-9a-f]{64}$/.test(expectedHash)) throw new Error('invalid_expected_runtime_codehash');
  const match = observedHash === expectedHash;
  return {
    ok: match,
    disposition: match ? 'PASS_READ_ONLY_CODEHASH_PREFLIGHT' : 'HOLD_RUNTIME_CODEHASH_MISMATCH',
    expected_chain_id_hex: expectedChain,
    observed_chain_id_hex: observedChain,
    address: normalizedAddress,
    expected_runtime_codehash: expectedHash,
    observed_runtime_codehash: observedHash,
    runtime_code_bytes: (code.length - 2) / 2,
    rpc_methods_used: ['eth_chainId', 'eth_getCode'],
    broadcast: false,
    money_movement: false,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const rpcUrl = process.env.CHLOM_READONLY_RPC_URL;
  const address = process.env.CHLOM_ENTRYPOINT_ADDRESS;
  const expectedChainIdHex = process.env.CHLOM_EXPECTED_CHAIN_ID_HEX;
  if (!rpcUrl || !address || !expectedChainIdHex) {
    console.error(JSON.stringify({
      result: 'HOLD_READ_ONLY_PREFLIGHT_CONFIGURATION_MISSING',
      required: ['CHLOM_READONLY_RPC_URL', 'CHLOM_ENTRYPOINT_ADDRESS', 'CHLOM_EXPECTED_CHAIN_ID_HEX'],
      broadcast: false,
      money_movement: false,
    }));
    process.exit(2);
  }
  const result = await runReadOnlyCodePreflight({
    rpcUrl,
    address,
    expectedChainIdHex,
    expectedRuntimeCodehash: process.env.CHLOM_EXPECTED_RUNTIME_CODEHASH || null,
  });
  console.log(JSON.stringify(result));
  if (!result.ok) process.exit(1);
}
