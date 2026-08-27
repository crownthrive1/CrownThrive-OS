import { createHash, createHmac, randomUUID, timingSafeEqual } from 'node:crypto';

export const PENTAFABRIC_VERSION = '1.0.0';
export const PENTAFABRIC_SCHEMA = 'crownthrive.pentafabric.v1';
export const PENTA_EVENT_CONTRACT = 'crownthrive.penta.event.v1';
export const CHLOM_BINDING = 'crownthrive.chlom.pentafabric.v1';

const signingSecret = () =>
  process.env.PENTAFABRIC_SIGNING_SECRET ||
  process.env.CHLOM_SIGNING_SECRET ||
  process.env.PENTA_SIGNING_SECRET ||
  null;

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

function canonicalBytes(event) {
  const { integrity: _integrity, ...unsigned } = event;
  return Buffer.from(JSON.stringify(stable(unsigned)), 'utf8');
}

function safeEqualHex(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string') return false;
  if (!/^[a-f0-9]+$/i.test(left) || !/^[a-f0-9]+$/i.test(right)) return false;
  const a = Buffer.from(left, 'hex');
  const b = Buffer.from(right, 'hex');
  return a.length === b.length && timingSafeEqual(a, b);
}

function slug(value) {
  const normalized = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  if (!normalized) throw new Error('protocol is required');
  return normalized.slice(0, 128);
}

function integer(value, fallback, min, max) {
  const parsed = Number.isInteger(value) ? value : fallback;
  if (parsed < min || parsed > max) throw new Error(`integer must be between ${min} and ${max}`);
  return parsed;
}

export function fabricState() {
  const secret = signingSecret();
  return {
    schema: PENTAFABRIC_SCHEMA,
    version: PENTAFABRIC_VERSION,
    event_contract: PENTA_EVENT_CONTRACT,
    chlom_binding: CHLOM_BINDING,
    signing: secret && Buffer.byteLength(secret, 'utf8') >= 32 ? 'HMAC_SHA256_BOUND' : 'SHA256_DIGEST_ONLY',
    secret_bound: Boolean(secret && Buffer.byteLength(secret, 'utf8') >= 32),
    environment: process.env.VERCEL_ENV || 'local',
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || 'local-candidate',
  };
}

export function emitPenta(input = {}) {
  const protocol = String(input.protocol || '').trim();
  const protocolSlug = slug(protocol);
  const source = String(input.source || `urn:crownthrive:protocol:${protocolSlug}`);
  const lane = input.lane || 'hot';
  if (!['hot', 'cold'].includes(lane)) throw new Error('lane must be hot or cold');
  const ttlSeconds = integer(input.ttl_seconds, 300, 1, 86400);
  const sequence = integer(input.sequence, 0, 0, Number.MAX_SAFE_INTEGER);
  const intentId = String(input.chlom_intent_id || '').trim();
  if (!intentId) throw new Error('chlom_intent_id is required');
  const now = new Date();
  const expires = new Date(now.getTime() + ttlSeconds * 1000);
  const event = {
    specversion: '1.0',
    id: `penta_${randomUUID()}`,
    source,
    type: String(input.type || 'penta.relay.forwarded'),
    subject: String(input.subject || protocolSlug),
    time: now.toISOString(),
    datacontenttype: 'application/json',
    data: {
      status: 'DELIVERED',
      protocol,
      payload: input.payload && typeof input.payload === 'object' && !Array.isArray(input.payload) ? input.payload : {},
    },
    trace: {
      trace_id: String(input.trace_id || `ptrace_${randomUUID()}`),
      sequence,
      causation_id: input.causation_id || null,
    },
    mesh: {
      contract: PENTA_EVENT_CONTRACT,
      family: 'PentaFamily',
      architecture_version: String(input.architecture_version || '1.2.0'),
      layer: 'interoperation',
      fabric: {
        schema: PENTAFABRIC_SCHEMA,
        name: 'PentaFabric',
        version: PENTAFABRIC_VERSION,
        protocol,
        lane,
        route: String(input.route || 'vercel'),
        corridor: String(input.corridor || 'default'),
        ttl_seconds: ttlSeconds,
        expires_at: expires.toISOString(),
      },
      chlom: {
        binding: CHLOM_BINDING,
        governed: true,
        intent_id: intentId,
        policy_refs: Array.isArray(input.chlom_policy_refs) ? input.chlom_policy_refs.map(String) : [],
        oracle_cookie_id: input.oracle_cookie_id || null,
        rights_scope: String(input.rights_scope || 'chlom-governed'),
      },
    },
  };

  const canonical = canonicalBytes(event);
  const digest = createHash('sha256').update(canonical).digest('hex');
  const secret = signingSecret();
  const secretReady = secret && Buffer.byteLength(secret, 'utf8') >= 32;
  event.integrity = {
    algorithm: secretReady ? 'HMAC-SHA256' : 'SHA-256',
    key_id: secretReady ? 'pentafabric-v1' : 'vercel-build-digest-v1',
    digest,
    signature: secretReady ? createHmac('sha256', secret).update(canonical).digest('hex') : null,
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
  };
  return event;
}

export function verifyPenta(event, { requireSignature = false } = {}) {
  if (!event || typeof event !== 'object' || Array.isArray(event)) throw new Error('Penta must be an object');
  if (event.specversion !== '1.0') throw new Error('specversion must be 1.0');
  if (!String(event.id || '').startsWith('penta_')) throw new Error('Penta id is invalid');
  if (!String(event.type || '').startsWith('penta.')) throw new Error('Penta type is invalid');
  if (event.datacontenttype !== 'application/json') throw new Error('datacontenttype must be application/json');
  if (event.mesh?.contract !== PENTA_EVENT_CONTRACT || event.mesh?.family !== 'PentaFamily') throw new Error('Penta event contract mismatch');
  if (event.mesh?.fabric?.schema !== PENTAFABRIC_SCHEMA || event.mesh?.fabric?.version !== PENTAFABRIC_VERSION) throw new Error('PentaFabric version mismatch');
  if (event.mesh?.chlom?.binding !== CHLOM_BINDING || event.mesh?.chlom?.governed !== true || !event.mesh?.chlom?.intent_id) throw new Error('CHLOM binding is missing or invalid');
  const expires = Date.parse(event.mesh?.fabric?.expires_at || '');
  if (!Number.isFinite(expires) || Date.now() > expires) throw new Error('Penta expired');
  const canonical = canonicalBytes(event);
  const expectedDigest = createHash('sha256').update(canonical).digest('hex');
  if (!safeEqualHex(String(event.integrity?.digest || ''), expectedDigest)) throw new Error('Penta digest mismatch');
  const secret = signingSecret();
  const secretReady = secret && Buffer.byteLength(secret, 'utf8') >= 32;
  if (requireSignature && !secretReady) throw new Error('PentaFabric signing secret is not bound');
  if (event.integrity?.algorithm === 'HMAC-SHA256') {
    if (!secretReady) throw new Error('HMAC Penta cannot be verified without signing secret');
    const expectedSignature = createHmac('sha256', secret).update(canonical).digest('hex');
    if (!safeEqualHex(String(event.integrity?.signature || ''), expectedSignature)) throw new Error('Penta signature mismatch');
  } else if (requireSignature) {
    throw new Error('signed Penta required');
  }
  return event;
}
