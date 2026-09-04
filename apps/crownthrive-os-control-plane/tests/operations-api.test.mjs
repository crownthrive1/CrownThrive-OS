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
  return { method: 'GET', url: '/api/operations', headers: {}, query: {} };
}

function boundEnv(url, publicFallback = false) {
  return {
    NEXT_PUBLIC_SUPABASE_URL: publicFallback ? url : undefined,
    SUPABASE_SERVICE_ROLE_KEY: SERVICE_ROLE_KEY,
    SUPABASE_URL: publicFallback ? undefined : url,
  };
}

function responseJson(payload) {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
  };
}

function livePayload() {
  return {
    schema: 'ct.crownthrive.os.live-readback.v1',
    status: 'OPERATIONAL',
    window_hours: 24,
    window_start: '2026-09-03T00:00:00.000Z',
    generated_at: '2026-09-04T00:00:00.000Z',
    stats: {
      penta_events_window: 1,
      penta_super_runs_window: 2,
      wake_requests_window: 3,
      remediation_window: 4,
      interventions_window: 5,
      registered_providers: 20,
      active_providers: 19,
      registered_routes: 1,
      active_routes: 1,
      dail_systems: 5,
      dail_active_systems: 5,
      operation_count: 32,
    },
    ledger: [{
      occurred_at: '2026-09-04T00:00:00.000Z',
      source: 'PentaRuntime',
      protocol: 'PentaSuperRun',
      route: 'runtime-key',
      lane: 'runtime',
      penta: null,
      trace: 'trace-1',
      state: 'SUCCEEDED',
      evidence: 'abcdef1234567890',
      authority: 'D2',
      visibility: 'internal',
    }],
    providers: [{ provider_key: 'vercel', state: 'production_verified', route_count: 1 }],
    routes: [{ route_key: 'ct.penta.pm.route.vercel.v1', provider_key: 'vercel', state: 'production_verified' }],
    operations: [{ operation_key: 'penta_tick', last_state: 'SUCCEEDED', run_count: 10 }],
    interventions: [{ id: 'window-intervention', stage: 'READBACK', state: 'OPERATIONAL' }],
    dail: [{ system_key: 'ct.dail.machine.v1', state: 'active', sequence_id: '123' }],
  };
}

function interventionPayload() {
  return {
    schema: 'ct.crownthrive.os.intervention-history.v1',
    status: 'OPERATIONAL',
    count: 2,
    generated_at: '2026-09-04T00:00:00.000Z',
    rows: [
      { id: 'intervention-1', stage: 'READBACK', state: 'VERIFIED', authority_class: 'D2' },
      { id: 'intervention-2', stage: 'PLAN', state: 'QUEUED', authority_class: 'D3' },
    ],
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
    assert.equal(response.payload.instrumentation.unobserved_activity_claimed, false);
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

test('canonical origins invoke only the exact unified readback RPCs and expose public-safe data', async () => {
  const originalFetch = global.fetch;
  try {
    for (const [url, publicFallback] of [
      [SUPABASE_ORIGIN, false],
      [`${SUPABASE_ORIGIN}/`, true],
    ]) {
      const requests = [];
      global.fetch = async (target, options) => {
        requests.push({ target, options });
        assert.equal(target.origin, SUPABASE_ORIGIN);
        assert.equal(options.method, 'POST');
        assert.equal(options.redirect, 'error');
        assert.equal(options.cache, 'no-store');
        assert.equal(options.headers.apikey, SERVICE_ROLE_KEY);
        assert.equal(options.headers.Authorization, `Bearer ${SERVICE_ROLE_KEY}`);
        assert.equal(options.headers['Content-Type'], 'application/json');
        if (target.pathname === '/rest/v1/rpc/crownthrive_os_live_readback_v1') {
          assert.deepEqual(JSON.parse(options.body), { p_window_hours: 24, p_limit: 200 });
          return responseJson(livePayload());
        }
        if (target.pathname === '/rest/v1/rpc/crownthrive_os_intervention_history_v1') {
          assert.deepEqual(JSON.parse(options.body), { p_limit: 500 });
          return responseJson(interventionPayload());
        }
        throw new Error(`unexpected target ${target}`);
      };

      const response = mockResponse();
      await withEnv(boundEnv(url, publicFallback), () => operationsHandler(request(), response));
      assert.equal(requests.length, 2);
      assert.equal(response.statusCode, 200);
      assert.equal(response.payload.status, 'OPERATIONAL');
      assert.equal(response.payload.source.state, 'BOUND');
      assert.equal(response.payload.activity.total_events, 15);
      assert.equal(response.payload.activity.recent[0].source, 'PentaRuntime');
      assert.equal(response.payload.intervention_history.count, 2);
      assert.equal(response.payload.interventions[1].authority_class, 'D3');
      assert.equal(response.payload.instrumentation.unobserved_activity_claimed, false);
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
