import assert from 'node:assert/strict';
import test from 'node:test';
import commandHandler from '../api/command.js';

const SUPABASE_ORIGIN = 'https://tzajnzshmtzjenqulehq.supabase.co';
const SERVICE_ROLE_KEY = 'private-service-role-key-for-tests';
const PRIVATE_UPSTREAM_DETAIL = 'private actor payload and secret material';

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

function request(method = 'GET', query = {}) {
  return { method, url: '/api/command', headers: {}, query };
}

function boundEnv(url = SUPABASE_ORIGIN, publicFallback = false) {
  return {
    NEXT_PUBLIC_SUPABASE_URL: publicFallback ? url : undefined,
    SUPABASE_SERVICE_ROLE_KEY: SERVICE_ROLE_KEY,
    SUPABASE_URL: publicFallback ? undefined : url,
  };
}

function projection(status = 'OPERATIONAL') {
  return {
    schema: 'ct.crownthrive.command-status.v1',
    service: 'crownthrive-os-control-plane',
    status,
    wallet: {
      production_state: 'PRODUCTION_RESTRICTED_EXTERNAL_RAILS',
      enforcement_state: 'enforced',
      inventory: { active_wallets: 5, service_bindings: 630 },
    },
    dail: {
      assurance: {
        integrity_state: 'PASS_GLOBAL_COMPACT_CHAIN',
        current_head_sequence_id: 2323666,
        verified_through_sequence_id: 2323666,
        sequence_span_lag: 0,
      },
      primary_systems: [],
      supporting_systems: [],
      lanes: [{
        lane_key: 'human',
        recent: [{
          sequence_id: 2323540,
          event_type: 'internal.event',
          source_system: 'internal',
          entity_type: 'internal',
          authority_class: 'D2',
          event_hash_prefix: '884be61e62925066',
          payload_hash_prefix: 'c73a388ea90048ed',
        }],
      }],
    },
    privacy: {
      public_safe: true,
      actors_exposed: false,
      balances_exposed: false,
      payloads_exposed: false,
      wallet_identifiers_exposed: false,
    },
    pass_manufactured: false,
  };
}

test('unbound state stays public-safe and does not call Supabase', async () => {
  const originalFetch = global.fetch;
  let fetches = 0;
  global.fetch = async () => {
    fetches += 1;
    throw new Error('unbound state must not fetch');
  };
  try {
    const response = mockResponse();
    await withEnv({ SUPABASE_URL: undefined, NEXT_PUBLIC_SUPABASE_URL: undefined, SUPABASE_SERVICE_ROLE_KEY: undefined }, () => commandHandler(request(), response));
    assert.equal(response.statusCode, 200);
    assert.equal(response.payload.status, 'PARTIAL');
    assert.equal(response.payload.source.state, 'UNBOUND');
    assert.equal(response.payload.controls.economic_mutations_exposed, false);
    assert.equal(response.payload.privacy.wallet_identifiers_exposed, false);
    assert.equal(response.payload.pass_manufactured, false);
    assert.equal(fetches, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('non-canonical Supabase URLs fail closed before credentialed fetch', async () => {
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
    throw new Error('fetch must not run for hostile origin');
  };
  try {
    for (const url of hostileUrls) {
      const response = mockResponse();
      await withEnv(boundEnv(url), () => commandHandler(request(), response));
      assert.equal(response.statusCode, 503, url);
      assert.equal(response.payload.error, 'command_projection_configuration_hold', url);
      assert.equal(JSON.stringify(response.payload).includes(url), false, url);
      assert.equal(JSON.stringify(response.payload).includes(SERVICE_ROLE_KEY), false, url);
    }
    assert.equal(fetches, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('bound canonical origin calls only the aggregate RPC and clamps event limits', async () => {
  const originalFetch = global.fetch;
  try {
    for (const [query, expectedLimit] of [[{}, 12], [{ limit: '1' }, 3], [{ limit: '99' }, 25], [{ limit: '7' }, 7]]) {
      const requests = [];
      global.fetch = async (target, options) => {
        requests.push({ target, options });
        assert.equal(target.origin, SUPABASE_ORIGIN);
        assert.equal(target.pathname, '/rest/v1/rpc/crownthrive_command_status_v1');
        assert.equal(options.method, 'POST');
        assert.equal(options.redirect, 'error');
        assert.equal(options.cache, 'no-store');
        assert.equal(options.headers.apikey, SERVICE_ROLE_KEY);
        assert.equal(options.headers.Authorization, `Bearer ${SERVICE_ROLE_KEY}`);
        assert.deepEqual(JSON.parse(options.body), { p_event_limit: expectedLimit });
        return { ok: true, status: 200, json: async () => projection() };
      };
      const response = mockResponse();
      await withEnv(boundEnv(), () => commandHandler(request('GET', query), response));
      assert.equal(requests.length, 1);
      assert.equal(response.statusCode, 200);
      assert.equal(response.payload.schema, 'ct.crownthrive.command-api.v1');
      assert.equal(response.payload.upstream_schema, 'ct.crownthrive.command-status.v1');
      assert.equal(response.payload.event_limit, expectedLimit);
      assert.equal(response.payload.source.state, 'BOUND');
      assert.equal(response.payload.source.secret_material_exposed, false);
      assert.equal(response.payload.pass_manufactured, false);
      assert.equal(JSON.stringify(response.payload).includes(SERVICE_ROLE_KEY), false);
    }
  } finally {
    global.fetch = originalFetch;
  }
});

test('degraded projection returns 503 without manufacturing a pass', async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => ({ ok: true, status: 200, json: async () => projection('DEGRADED') });
  try {
    const response = mockResponse();
    await withEnv(boundEnv(), () => commandHandler(request(), response));
    assert.equal(response.statusCode, 503);
    assert.equal(response.payload.status, 'DEGRADED');
    assert.equal(response.payload.pass_manufactured, false);
    assert.equal(response.headers['x-crownthrive-command-state'], 'DEGRADED');
  } finally {
    global.fetch = originalFetch;
  }
});

test('upstream errors never disclose body, thrown details, or credentials', async () => {
  const originalFetch = global.fetch;
  let bodyReads = 0;
  try {
    global.fetch = async () => ({
      ok: false,
      status: 500,
      text: async () => { bodyReads += 1; return PRIVATE_UPSTREAM_DETAIL; },
    });
    const response = mockResponse();
    await withEnv(boundEnv(), () => commandHandler(request(), response));
    assert.equal(response.statusCode, 503);
    assert.equal(response.payload.error, 'command_projection_readback_failed');
    assert.equal(bodyReads, 0);
    assert.equal(JSON.stringify(response.payload).includes(PRIVATE_UPSTREAM_DETAIL), false);

    global.fetch = async () => { throw new Error(`${PRIVATE_UPSTREAM_DETAIL} ${SERVICE_ROLE_KEY}`); };
    const thrown = mockResponse();
    await withEnv(boundEnv(), () => commandHandler(request(), thrown));
    const publicBody = JSON.stringify(thrown.payload);
    assert.equal(thrown.statusCode, 503);
    assert.equal(publicBody.includes(PRIVATE_UPSTREAM_DETAIL), false);
    assert.equal(publicBody.includes(SERVICE_ROLE_KEY), false);
  } finally {
    global.fetch = originalFetch;
  }
});

test('HEAD returns headers only and unsupported methods are rejected', async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => ({ ok: true, status: 200, json: async () => projection() });
  try {
    const head = mockResponse();
    await withEnv(boundEnv(), () => commandHandler(request('HEAD'), head));
    assert.equal(head.statusCode, 200);
    assert.equal(head.ended, true);
    assert.equal(head.payload, undefined);
    assert.equal(head.headers['cache-control'], 'no-store, max-age=0');

    const post = mockResponse();
    await withEnv(boundEnv(), () => commandHandler(request('POST'), post));
    assert.equal(post.statusCode, 405);
    assert.equal(post.headers.allow, 'GET, HEAD');
    assert.equal(post.payload.error, 'method_not_allowed');
  } finally {
    global.fetch = originalFetch;
  }
});
