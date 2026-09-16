import { SCHEMA, object, projectStorage } from '../lib/storage-command-projection.js';

const ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const RPCS = ['ct_wasabi_status_v1', 'ct_storage_fabric_catalog_v1'];
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024;

export function createHandler({ env = process.env, fetcher = globalThis.fetch, now = () => new Date() } = {}) {
  async function read(name, key) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 9000);
    try {
      const upstream = await fetcher(`${ORIGIN}/rest/v1/rpc/${name}`, {
        method: 'POST', redirect: 'error', cache: 'no-store', signal: controller.signal,
        headers: { apikey: key, Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', Accept: 'application/json' },
        body: '{}',
      });
      if (!upstream.ok) throw new Error('upstream_unavailable');
      const declared = Number(upstream.headers?.get('content-length'));
      if (Number.isFinite(declared) && declared > MAX_RESPONSE_BYTES) throw new Error('upstream_oversize');
      const body = await upstream.text();
      if (Buffer.byteLength(body) > MAX_RESPONSE_BYTES) throw new Error('upstream_oversize');
      const parsed = JSON.parse(body);
      if (!object(parsed)) throw new Error('upstream_invalid');
      return parsed;
    } finally { clearTimeout(timer); }
  }
  return async function handler(request, response) {
    response.setHeader('Cache-Control', 'no-store, max-age=0');
    response.setHeader('Content-Type', 'application/json; charset=utf-8');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('X-CrownThrive-Storage-Contract', SCHEMA);
    const head = request.method === 'HEAD';
    const send = (code, value) => head ? response.status(code).end() : response.status(code).json(value);
    if (request.method !== 'GET' && !head) {
      response.setHeader('Allow', 'GET, HEAD');
      return send(405, { schema: SCHEMA, status: 'REJECTED', error: 'method_not_allowed' });
    }
    const supplied = env.SUPABASE_URL || env.NEXT_PUBLIC_SUPABASE_URL;
    const key = env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key || ![ORIGIN, `${ORIGIN}/`].includes(supplied)) {
      return send(503, { ...projectStorage(null, null, now().toISOString()), error: 'source_binding_unavailable' });
    }
    // Both RPCs are existing reads. No operator impersonation, account mutation, or provider tick.
    const results = await Promise.allSettled(RPCS.map((name) => read(name, key)));
    const values = results.map((result) => result.status === 'fulfilled' ? result.value : null);
    const payload = projectStorage(values[0], values[1], now().toISOString());
    return send(payload.status === 'UNAVAILABLE' ? 503 : 200, payload);
  };
}
export default createHandler();
