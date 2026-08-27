import { createHash, timingSafeEqual } from 'node:crypto';

export const CHLOM_BRIDGE_SCHEMA = 'ct.penta.chlom.bridge.v1';
export const CHLOM_BRIDGE_RECEIPT_SCHEMA = 'ct.penta.chlom.bridge-receipt.v1';
export const CHLOM_PRODUCTION_BASE_URL = 'https://chlom-protocol.vercel.app';

const MAX_REQUEST_BYTES = 128 * 1024;
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;
const DEFAULT_TIMEOUT_MS = 15000;

const CHAIN_KEYS = new Set([
  'base',
  'base-sepolia',
  'ethereum',
  'arbitrum',
  'avalanche',
  'cronos',
  'fantom',
  'optimism',
  'polygon',
  'tron',
]);

const EVM_CHAIN_KEYS = new Set([...CHAIN_KEYS].filter((chain) => chain !== 'tron'));

const READ_ONLY_RPC_METHODS = new Set([
  'eth_chainId',
  'eth_blockNumber',
  'eth_getBalance',
  'eth_getBlockByHash',
  'eth_getBlockByNumber',
  'eth_getCode',
  'eth_getLogs',
  'eth_getStorageAt',
  'eth_getTransactionByBlockHashAndIndex',
  'eth_getTransactionByBlockNumberAndIndex',
  'eth_getTransactionByHash',
  'eth_getTransactionCount',
  'eth_getTransactionReceipt',
  'eth_call',
  'eth_estimateGas',
  'eth_feeHistory',
  'eth_gasPrice',
  'net_version',
  'web3_clientVersion',
]);

const ANALYTICS_TEMPLATES = new Set([
  'latest_block',
  'transaction_evidence',
  'address_activity',
  'contract_logs',
]);

const ACTION_PATHS = Object.freeze({
  rpc_read: '/api/v1/rpc',
  analytics: '/api/v1/analytics',
  attest: '/api/v1/attest',
});

export class ChlomBridgeError extends Error {
  constructor(code, message, status = 400, details = undefined) {
    super(message);
    this.name = 'ChlomBridgeError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') {
    return Object.keys(value)
      .sort()
      .reduce((result, key) => {
        result[key] = stable(value[key]);
        return result;
      }, {});
  }
  return value;
}

function digest(value) {
  return createHash('sha256')
    .update(JSON.stringify(stable(value)))
    .digest('hex');
}

function safeEqual(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string') return false;
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

function requireObject(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_INVALID_INPUT',
      `${label} must be an object.`,
      400,
    );
  }
  return value;
}

function requireString(value, label, maximum = 256) {
  if (typeof value !== 'string' || value.length < 1 || value.length > maximum) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_INVALID_INPUT',
      `${label} must be a non-empty string no longer than ${maximum} characters.`,
      400,
    );
  }
  return value;
}

function requestHeader(request, name) {
  const value = request?.headers?.[String(name).toLowerCase()];
  if (Array.isArray(value)) return value[0] || null;
  return typeof value === 'string' && value.length > 0 ? value : null;
}

export function chlomBaseUrl() {
  const configured = (process.env.CHLOM_BASE_URL || CHLOM_PRODUCTION_BASE_URL).replace(/\/$/, '');
  if (configured !== CHLOM_PRODUCTION_BASE_URL) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_BASE_URL_REJECTED',
      'CHLOM_BASE_URL must resolve to the canonical production CHLOM runtime.',
      503,
      { expected: CHLOM_PRODUCTION_BASE_URL },
    );
  }
  return configured;
}

export function chlomBridgeState() {
  let baseUrl = CHLOM_PRODUCTION_BASE_URL;
  let baseUrlValid = true;
  try {
    baseUrl = chlomBaseUrl();
  } catch {
    baseUrlValid = false;
  }
  return {
    schema: CHLOM_BRIDGE_SCHEMA,
    version: '1.0.0',
    status:
      baseUrlValid && process.env.CHLOM_API_TOKEN && process.env.CROWNTHRIVE_CONTROL_TOKEN
        ? 'BOUND'
        : 'CONFIGURATION_HOLD',
    base_url: baseUrl,
    base_url_valid: baseUrlValid,
    upstream_api_token_bound: Boolean(process.env.CHLOM_API_TOKEN),
    inbound_control_token_bound: Boolean(process.env.CROWNTHRIVE_CONTROL_TOKEN),
    allowed_actions: Object.keys(ACTION_PATHS),
    arbitrary_url_allowed: false,
    arbitrary_rpc_method_allowed: false,
    chain_broadcast_allowed: false,
    private_key_custody: false,
    dail_persistence_claimed: false,
    environment: process.env.VERCEL_ENV || 'local',
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || 'local-candidate',
  };
}

export function requireControlAuthorization(request) {
  const configured = process.env.CROWNTHRIVE_CONTROL_TOKEN;
  if (!configured) {
    throw new ChlomBridgeError(
      'CROWNTHRIVE_CONTROL_TOKEN_NOT_CONFIGURED',
      'The CrownThrive internal API perimeter is not configured.',
      503,
    );
  }
  const authorization = requestHeader(request, 'authorization') || '';
  const supplied = authorization.startsWith('Bearer ')
    ? authorization.slice(7).trim()
    : '';
  if (!supplied || !safeEqual(supplied, configured)) {
    throw new ChlomBridgeError(
      'CROWNTHRIVE_CONTROL_UNAUTHORIZED',
      'A valid CrownThrive control-plane bearer token is required.',
      401,
    );
  }
}

export function validateBridgeOrigin(request) {
  const origin = requestHeader(request, 'origin');
  if (!origin) return;
  const host =
    requestHeader(request, 'x-forwarded-host') ||
    requestHeader(request, 'host');
  const protocol = requestHeader(request, 'x-forwarded-proto') || 'https';
  const allowed = new Set(
    (process.env.CROWNTHRIVE_ALLOWED_ORIGINS || '')
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean),
  );
  if (host) allowed.add(`${protocol}://${host}`);
  if (!allowed.has(origin)) {
    throw new ChlomBridgeError(
      'CROWNTHRIVE_ORIGIN_REJECTED',
      'The request Origin is outside the CrownThrive control-plane perimeter.',
      403,
      { origin },
    );
  }
}

export function parseBridgeBody(request) {
  const length = Number(requestHeader(request, 'content-length') || 0);
  if (Number.isFinite(length) && length > MAX_REQUEST_BYTES) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_REQUEST_TOO_LARGE',
      'The CHLOM bridge request exceeds the governed payload limit.',
      413,
      { maximum_bytes: MAX_REQUEST_BYTES },
    );
  }
  if (request.body && typeof request.body === 'object' && !Buffer.isBuffer(request.body)) {
    return request.body;
  }
  if (Buffer.isBuffer(request.body)) {
    try {
      return JSON.parse(request.body.toString('utf8'));
    } catch {
      throw new ChlomBridgeError('CHLOM_BRIDGE_INVALID_JSON', 'Request body is not valid JSON.', 400);
    }
  }
  if (typeof request.body === 'string' && request.body.trim()) {
    try {
      return JSON.parse(request.body);
    } catch {
      throw new ChlomBridgeError('CHLOM_BRIDGE_INVALID_JSON', 'Request body is not valid JSON.', 400);
    }
  }
  throw new ChlomBridgeError('CHLOM_BRIDGE_BODY_REQUIRED', 'A JSON request body is required.', 400);
}

function boundedInteger(value, fallback, minimum, maximum, label) {
  const selected = value === undefined ? fallback : value;
  if (!Number.isInteger(selected) || selected < minimum || selected > maximum) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_INVALID_INPUT',
      `${label} must be an integer from ${minimum} through ${maximum}.`,
      400,
    );
  }
  return selected;
}

export function validateBridgeAction(action, rawInput) {
  if (!Object.hasOwn(ACTION_PATHS, action)) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_ACTION_NOT_ALLOWLISTED',
      `Unsupported CHLOM bridge action: ${String(action)}`,
      403,
    );
  }
  const input = requireObject(rawInput, 'input');

  if (action === 'rpc_read') {
    const chain = requireString(input.chain, 'chain', 64);
    if (!EVM_CHAIN_KEYS.has(chain)) {
      throw new ChlomBridgeError('CHLOM_BRIDGE_CHAIN_NOT_ALLOWLISTED', `Unsupported EVM chain: ${chain}`, 400);
    }
    const method = requireString(input.method, 'method', 128);
    if (!READ_ONLY_RPC_METHODS.has(method)) {
      throw new ChlomBridgeError(
        'CHLOM_BRIDGE_RPC_METHOD_NOT_ALLOWLISTED',
        `RPC method is not approved for the CrownThrive read bridge: ${method}`,
        403,
      );
    }
    const params = input.params === undefined ? [] : input.params;
    if (!Array.isArray(params) || params.length > 64) {
      throw new ChlomBridgeError(
        'CHLOM_BRIDGE_INVALID_INPUT',
        'params must be an array with no more than 64 entries.',
        400,
      );
    }
    return { chain, method, params };
  }

  if (action === 'analytics') {
    const chain = requireString(input.chain, 'chain', 64);
    if (!CHAIN_KEYS.has(chain)) {
      throw new ChlomBridgeError('CHLOM_BRIDGE_CHAIN_NOT_ALLOWLISTED', `Unsupported analytics chain: ${chain}`, 400);
    }
    const template = requireString(input.template, 'template', 64);
    if (!ANALYTICS_TEMPLATES.has(template)) {
      throw new ChlomBridgeError(
        'CHLOM_BRIDGE_ANALYTICS_TEMPLATE_NOT_ALLOWLISTED',
        `Analytics template is not approved: ${template}`,
        403,
      );
    }
    return {
      chain,
      template,
      ...(input.transactionHash === undefined
        ? {}
        : { transactionHash: requireString(input.transactionHash, 'transactionHash', 132) }),
      ...(input.address === undefined
        ? {}
        : { address: requireString(input.address, 'address', 132) }),
      lookbackDays: boundedInteger(input.lookbackDays, 7, 1, 31, 'lookbackDays'),
      limit: boundedInteger(input.limit, 50, 1, 250, 'limit'),
    };
  }

  const evidenceDigest = requireString(input.evidenceDigest, 'evidenceDigest', 64);
  if (!/^[0-9a-f]{64}$/.test(evidenceDigest)) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_INVALID_INPUT',
      'evidenceDigest must be a lowercase SHA-256 digest.',
      400,
    );
  }
  const targetChain = requireString(input.targetChain, 'targetChain', 64);
  if (!new Set(['base', 'base-sepolia', 'ethereum']).has(targetChain)) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_ANCHOR_CHAIN_NOT_ALLOWLISTED',
      `Evidence anchor preparation is not approved for ${targetChain}.`,
      403,
    );
  }
  return { evidenceDigest, targetChain };
}

async function readBoundedJson(response) {
  const raw = await response.text();
  if (Buffer.byteLength(raw, 'utf8') > MAX_RESPONSE_BYTES) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_RESPONSE_TOO_LARGE',
      'The upstream CHLOM response exceeded the governed response limit.',
      502,
      { maximum_bytes: MAX_RESPONSE_BYTES },
    );
  }
  try {
    return raw ? JSON.parse(raw) : null;
  } catch {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_INVALID_UPSTREAM_RESPONSE',
      'The upstream CHLOM runtime returned a non-JSON response.',
      502,
      { status: response.status },
    );
  }
}

async function fetchWithTimeout(url, options, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      ...options,
      cache: 'no-store',
      signal: controller.signal,
    });
  } catch (error) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_UPSTREAM_UNREACHABLE',
      'The canonical CHLOM runtime could not be reached.',
      502,
      { reason: String(error?.message || error).slice(0, 240) },
    );
  } finally {
    clearTimeout(timer);
  }
}

function bridgeReceipt(action, input, upstreamStatus, upstreamBody) {
  const observedAt = new Date().toISOString();
  const envelope = upstreamBody?.envelope || null;
  const upstreamEvidenceDigest =
    envelope?.evidenceDigest ||
    upstreamBody?.anchorIntent?.anchorDigest ||
    null;
  const inputDigest = digest(input);
  const bridgeDigest = digest({
    schema: CHLOM_BRIDGE_RECEIPT_SCHEMA,
    action,
    input_digest: inputDigest,
    upstream_status: upstreamStatus,
    upstream_evidence_digest: upstreamEvidenceDigest,
    observed_at: observedAt,
  });
  return {
    schema: CHLOM_BRIDGE_RECEIPT_SCHEMA,
    status: upstreamStatus >= 200 && upstreamStatus < 300 ? 'DELIVERED' : 'UPSTREAM_REJECTED',
    action,
    input_digest: inputDigest,
    bridge_digest: bridgeDigest,
    upstream: {
      service: 'CHLOM Chain Evidence Fabric',
      base_url: CHLOM_PRODUCTION_BASE_URL,
      http_status: upstreamStatus,
      evidence_digest: upstreamEvidenceDigest,
      request_digest: envelope?.requestDigest || null,
      payload_digest: envelope?.payloadDigest || null,
      dail_projection: envelope?.dailProjection || null,
    },
    penta_projection: {
      protocol: 'CHLOMChainEvidenceBridge',
      route: 'crownthrive-os-to-chlom',
      lane: 'hot',
      chlom_governed: true,
      dail_persistence_claimed: false,
      chain_broadcast_claimed: false,
      idempotency_key: bridgeDigest,
    },
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
    deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
    observed_at: observedAt,
    pass_manufactured: false,
  };
}

export async function fetchChlomHealth() {
  const url = `${chlomBaseUrl()}/api/health`;
  const response = await fetchWithTimeout(url, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      'User-Agent': 'CrownThrive-OS-CHLOM-Bridge/1.0',
    },
  }, 6000);
  const upstream = await readBoundedJson(response);
  if (!response.ok) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_HEALTH_REJECTED',
      'The CHLOM health endpoint rejected the bridge readback.',
      502,
      { upstream_status: response.status },
    );
  }
  return {
    schema: 'ct.penta.chlom.health-bridge.v1',
    status: upstream?.status === 'OPERATIONAL' ? 'OPERATIONAL' : 'DEGRADED',
    readiness_status: upstream?.readinessStatus || 'UNKNOWN',
    upstream,
    bridge: chlomBridgeState(),
    evidence: {
      upstream_build_sha: upstream?.buildSha || null,
      upstream_deployment_id: upstream?.deploymentId || null,
      readback_digest: digest(upstream),
      persistence_claimed: false,
    },
    observed_at: new Date().toISOString(),
    pass_manufactured: false,
  };
}

export async function callChlomBridge(action, rawInput) {
  const token = process.env.CHLOM_API_TOKEN;
  if (!token) {
    throw new ChlomBridgeError(
      'CHLOM_API_TOKEN_NOT_CONFIGURED',
      'The CrownThrive OS to CHLOM service credential is not configured.',
      503,
    );
  }
  const input = validateBridgeAction(action, rawInput);
  const path = ACTION_PATHS[action];
  const response = await fetchWithTimeout(`${chlomBaseUrl()}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      'User-Agent': 'CrownThrive-OS-CHLOM-Bridge/1.0',
    },
    body: JSON.stringify(input),
  });
  const upstream = await readBoundedJson(response);
  const receipt = bridgeReceipt(action, input, response.status, upstream);
  if (!response.ok) {
    throw new ChlomBridgeError(
      'CHLOM_BRIDGE_UPSTREAM_REJECTED',
      upstream?.error?.message || 'The CHLOM runtime rejected the bridge request.',
      response.status >= 400 && response.status < 500 ? response.status : 502,
      {
        upstream_status: response.status,
        upstream_code: upstream?.error?.code || null,
        receipt,
      },
    );
  }
  return { upstream, receipt };
}

export function normalizeChlomBridgeError(error) {
  if (error instanceof ChlomBridgeError) return error;
  return new ChlomBridgeError(
    'CHLOM_BRIDGE_INTERNAL_ERROR',
    String(error?.message || error),
    500,
  );
}
