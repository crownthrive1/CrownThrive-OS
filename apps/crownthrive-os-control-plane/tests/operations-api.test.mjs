import assert from 'node:assert/strict';
import test from 'node:test';
import operationsHandler from '../api/operations.js';

const SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const SERVICE_ROLE_KEY = 'private-service-role-key-for-tests';
const RAW_UPSTREAM_BODY = 'private-upstream-detail service_role=should-never-be-public';

function withEnv(values, callback) {
  const previous = new Map();
  for (const [key, value] of Object.entries(values)) {
    previous.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  const restore = () => {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  try {
    const result = callback();
    if (result && typeof result.then === 'function') return result.finally(restore);
    restore();
    return result;
  } catch (error) {
    restore();
    throw error;
  }
}

function mockResponse() {
  return {
    headers: {},
    statusCode: null,
    payload: undefined,
    ended: false,
    setHeader(name, value) { this.headers[name.toLowerCase()] = value; },
    status(code) { this.statusCode = code; return this; },
    json(payload) { this.payload = payload; return this; },
    end() { this.ended = true; return this; },
  };
}

function request() {
  return { method: 'GET', url: '/api/operations', headers: {} };
}

function boundEnv(url, publicFallback = false) {
  return {
    NEXT_PUBLIC_SUPABASE_URL: publicFallback ? url : undefined,
    SUPABASE_SERVICE_ROLE_KEY: SERVICE_ROLE_KEY,
    SUPABASE_URL: publicFallback ? undefined : url,
  };
}

function jsonResponse(rows, contentRange = '0-0/1') {
  return {
    ok: true,
    status: 200,
    headers: { get: (name) => name.toLowerCase() === 'content-range' ? contentRange : null },
    json: async () => rows,
  };
}

test('unbound operations state does not claim provider readback', async () => {
  const originalFetch = global.fetch;
  let fetches = 0;
  global.fetch = async () => {
    fetches += 1;
    throw new Error('unbound state must not fetch');
  };
  try {
    const response = mockResponse();
    await withEnv({
      NEXT_PUBLIC_SUPABASE_URL: undefined,
      SUPABASE_SERVICE_ROLE_KEY: undefined,
      SUPABASE_URL: undefined,
    }, () => operationsHandler(request(), response));
    assert.equal(response.statusCode, 200);
    assert.equal(response.payload.status, 'PARTIAL');
    assert.equal(response.payload.source.state, 'UNBOUND');
    assert.equal(response.payload.instrumentation.vercel_provider_readback, 'UNBOUND');
    assert.equal(fetches, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('hostile Supabase URL variants fail before any credentialed fetch', async () => {
  const hostileUrls = [
    `http://${new URL(SUPABASE_ORIGIN).host}`,
    `${SUPABASE_ORIGIN}//`,
    `${SUPABASE_ORIGIN}/rest/v1`,
    `${SUPABASE_ORIGIN}?redirect=https://attacker.example`,
    `${SUPABASE_ORIGIN}#fragment`,
    `https://user:password@${new URL(SUPABASE_ORIGIN).host}`,
    `https://prefix.${new URL(SUPABASE_ORIGIN).host}`,
    `${SUPABASE_ORIGIN}.attacker.example`,
    `${SUPABASE_ORIGIN}:443`,
    SUPABASE_ORIGIN.toUpperCase(),
    ` ${SUPABASE_ORIGIN}`,
    `${SUPABASE_ORIGIN} `,
  ];
  const originalFetch = global.fetch;
  let fetches = 0;
  global.fetch = async () => {
    fetches += 1;
    throw new Error('fetch must not run for a hostile origin');
  };
  try {
    for (const url of hostileUrls) {
      const response = mockResponse();
      await withEnv(boundEnv(url), () => operationsHandler(request(), response));
      assert.equal(response.statusCode, 503, url);
      assert.equal(response.payload.error, 'operations_readback_failed', url);
      assert.equal('detail' in response.payload, false, url);
      assert.equal(JSON.stringify(response.payload).includes(url), false, url);
    }
    assert.equal(fetches, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('canonical origins build the exact request and expose only signing_build_sha', async () => {
  const originalFetch = global.fetch;
  try {
    for (const [url, publicFallback] of [
      [SUPABASE_ORIGIN, false],
      [`${SUPABASE_ORIGIN}/`, true],
    ]) {
      let fetches = 0;
      global.fetch = async (target, options) => {
        fetches += 1;
        assert.equal(target.origin, SUPABASE_ORIGIN);
        assert.equal(target.pathname, '/rest/v1/pentafabric_events');
        assert.equal(
          target.searchParams.get('select'),
          'penta_id,trace_id,protocol,lane,route,chlom_binding,build_sha,received_at',
        );
        assert.equal(target.searchParams.get('limit'), '250');
        assert.match(target.searchParams.get('received_at'), /^gte\./);
        assert.equal(target.searchParams.get('order'), 'received_at.desc');
        assert.equal(options.method, 'GET');
        assert.equal(options.redirect, 'error');
        assert.equal(options.cache, 'no-store');
        assert.equal(options.headers.apikey, SERVICE_ROLE_KEY);
        assert.equal(options.headers.Authorization, `Bearer ${SERVICE_ROLE_KEY}`);
        assert.equal(options.headers.Prefer, 'count=exact');
        assert.equal(options.headers.Range, '0-249');
        assert.equal(options.headers['Range-Unit'], 'items');
        return jsonResponse([{
          penta_id: 'penta-1',
          trace_id: 'trace-1',
          protocol: 'Pentas',
          lane: 'hot',
          route: 'system',
          chlom_binding: 'chlom-1',
          build_sha: 'signed-build-abc',
          received_at: '2026-08-30T00:00:00.000Z',
        }]);
      };

      const response = mockResponse();
      await withEnv(boundEnv(url, publicFallback), () => operationsHandler(request(), response));
      assert.equal(fetches, 1);
      assert.equal(response.statusCode, 200);
      const row = response.payload.activity.recent[0];
      assert.equal(row.signing_build_sha, 'signed-build-abc');
      assert.equal('build_sha' in row, false);
      assert.equal(JSON.stringify(response.payload).includes(SERVICE_ROLE_KEY), false);
    }
  } finally {
    global.fetch = originalFetch;
  }
});

test('upstream bodies and thrown private details are suppressed from public errors', async () => {
  const originalFetch = global.fetch;
  let textReads = 0;
  try {
    global.fetch = async (_target, options) => {
      assert.equal(options.redirect, 'error');
      return {
        ok: false,
        status: 500,
        text: async () => {
          textReads += 1;
          return RAW_UPSTREAM_BODY;
        },
      };
    };
    const response = mockResponse();
    await withEnv(boundEnv(SUPABASE_ORIGIN), () => operationsHandler(request(), response));
    assert.equal(response.statusCode, 503);
    assert.equal(textReads, 0);
    assert.deepEqual(response.payload.error, 'operations_readback_failed');
    assert.equal('detail' in response.payload, false);
    assert.equal(JSON.stringify(response.payload).includes(RAW_UPSTREAM_BODY), false);

    global.fetch = async () => {
      throw new Error(`${RAW_UPSTREAM_BODY} ${SERVICE_ROLE_KEY}`);
    };
    const thrownResponse = mockResponse();
    await withEnv(boundEnv(SUPABASE_ORIGIN), () => operationsHandler(request(), thrownResponse));
    const publicBody = JSON.stringify(thrownResponse.payload);
    assert.equal(thrownResponse.statusCode, 503);
    assert.equal(publicBody.includes(RAW_UPSTREAM_BODY), false);
    assert.equal(publicBody.includes(SERVICE_ROLE_KEY), false);
    assert.equal('detail' in thrownResponse.payload, false);
  } finally {
    global.fetch = originalFetch;
  }
});
