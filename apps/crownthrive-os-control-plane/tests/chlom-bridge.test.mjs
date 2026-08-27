import assert from 'node:assert/strict';
import test from 'node:test';
import {
  CHLOM_PRODUCTION_BASE_URL,
  callChlomBridge,
  chlomBaseUrl,
  chlomBridgeState,
  fetchChlomHealth,
  requireControlAuthorization,
  validateBridgeAction,
} from '../lib/chlom-fabric.js';
import mcpHandler from '../api/mcp.js';

function withEnv(values, callback) {
  const previous = new Map();
  for (const [key, value] of Object.entries(values)) {
    previous.set(key, process.env[key]);
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  const finish = () => {
    for (const [key, value] of previous) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  try {
    const result = callback();
    if (result && typeof result.then === 'function') return result.finally(finish);
    finish();
    return result;
  } catch (error) {
    finish();
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

function modernMeta({ capabilities = {} } = {}) {
  return {
    'io.modelcontextprotocol/protocolVersion': '2026-07-28',
    'io.modelcontextprotocol/clientInfo': { name: 'test-client', version: '1.0.0' },
    ...(capabilities === null ? {} : { 'io.modelcontextprotocol/clientCapabilities': capabilities }),
  };
}

function modernRequest(method, id = 1, params = {}) {
  return {
    method: 'POST',
    url: '/api/mcp',
    headers: {
      host: 'crown-thrive-os.vercel.app',
      'x-forwarded-proto': 'https',
      'content-type': 'application/json',
      'mcp-protocol-version': '2026-07-28',
      'mcp-method': method,
      ...(method === 'tools/call' ? { 'mcp-name': params.name } : {}),
    },
    body: {
      jsonrpc: '2.0',
      id,
      method,
      params: { ...params, _meta: modernMeta() },
    },
  };
}

test('canonical CHLOM base URL is fixed and arbitrary override fails closed', () => {
  withEnv({ CHLOM_BASE_URL: undefined }, () => {
    assert.equal(chlomBaseUrl(), CHLOM_PRODUCTION_BASE_URL);
  });
  withEnv({ CHLOM_BASE_URL: 'https://attacker.example' }, () => {
    assert.throws(() => chlomBaseUrl(), /canonical production CHLOM runtime/i);
  });
});

test('bridge state truthfully reports configuration hold', () => {
  withEnv({ CHLOM_API_TOKEN: undefined, CROWNTHRIVE_CONTROL_TOKEN: undefined }, () => {
    const state = chlomBridgeState();
    assert.equal(state.status, 'CONFIGURATION_HOLD');
    assert.equal(state.chain_broadcast_allowed, false);
    assert.equal(state.private_key_custody, false);
  });
});

test('RPC bridge permits read methods and rejects raw broadcast', () => {
  assert.deepEqual(validateBridgeAction('rpc_read', {
    chain: 'ethereum',
    method: 'eth_getTransactionReceipt',
    params: ['0xabc'],
  }), {
    chain: 'ethereum',
    method: 'eth_getTransactionReceipt',
    params: ['0xabc'],
  });
  assert.throws(() => validateBridgeAction('rpc_read', {
    chain: 'ethereum',
    method: 'eth_sendRawTransaction',
    params: ['0xdeadbeef'],
  }), /not approved/i);
});

test('control authorization is independently fail-closed', () => {
  withEnv({ CROWNTHRIVE_CONTROL_TOKEN: undefined }, () => {
    assert.throws(() => requireControlAuthorization({ headers: {} }), /not configured/i);
  });
  withEnv({ CROWNTHRIVE_CONTROL_TOKEN: 'internal-secret' }, () => {
    assert.throws(() => requireControlAuthorization({ headers: { authorization: 'Bearer wrong' } }), /valid CrownThrive/i);
    assert.doesNotThrow(() => requireControlAuthorization({ headers: { authorization: 'Bearer internal-secret' } }));
  });
});

test('health bridge preserves upstream deployment evidence', async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    assert.equal(url, `${CHLOM_PRODUCTION_BASE_URL}/api/health`);
    return new Response(JSON.stringify({
      status: 'OPERATIONAL',
      readinessStatus: 'CONFIGURATION_HOLD',
      buildSha: 'build-123',
      deploymentId: 'dpl_123',
    }), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  try {
    const result = await fetchChlomHealth();
    assert.equal(result.status, 'OPERATIONAL');
    assert.equal(result.readiness_status, 'CONFIGURATION_HOLD');
    assert.equal(result.evidence.upstream_build_sha, 'build-123');
    assert.match(result.evidence.readback_digest, /^[0-9a-f]{64}$/);
  } finally {
    global.fetch = originalFetch;
  }
});

test('authenticated bridge forwards only the canonical read endpoint and preserves evidence digest', async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url, options) => {
    assert.equal(url, `${CHLOM_PRODUCTION_BASE_URL}/api/v1/rpc`);
    assert.equal(options.headers.Authorization, 'Bearer upstream-secret');
    const body = JSON.parse(options.body);
    assert.equal(body.method, 'eth_blockNumber');
    return new Response(JSON.stringify({
      ok: true,
      envelope: {
        evidenceDigest: 'b'.repeat(64),
        requestDigest: 'c'.repeat(64),
        payloadDigest: 'd'.repeat(64),
        dailProjection: { idempotencyKey: 'b'.repeat(64) },
      },
    }), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  try {
    const result = await withEnv({ CHLOM_API_TOKEN: 'upstream-secret' }, () =>
      callChlomBridge('rpc_read', {
        chain: 'ethereum',
        method: 'eth_blockNumber',
        params: [],
      }),
    );
    assert.equal(result.receipt.upstream.evidence_digest, 'b'.repeat(64));
    assert.equal(result.receipt.penta_projection.chain_broadcast_claimed, false);
    assert.equal(result.receipt.penta_projection.dail_persistence_claimed, false);
  } finally {
    global.fetch = originalFetch;
  }
});

test('modern MCP discovery validates current protocol metadata', async () => {
  const response = mockResponse();
  await mcpHandler(modernRequest('server/discover'), response);
  assert.equal(response.statusCode, 200);
  assert.ok(response.payload.result.supportedVersions.includes('2026-07-28'));
  assert.equal(response.payload.result.resultType, 'complete');
});

test('modern MCP rejects missing client capabilities with -32021', async () => {
  const request = modernRequest('tools/list');
  delete request.body.params._meta['io.modelcontextprotocol/clientCapabilities'];
  const response = mockResponse();
  await mcpHandler(request, response);
  assert.equal(response.statusCode, 400);
  assert.equal(response.payload.error.code, -32021);
});

test('MCP tool catalog hardwires CHLOM without exposing broadcast or private keys', async () => {
  const response = mockResponse();
  await mcpHandler(modernRequest('tools/list'), response);
  const names = response.payload.result.tools.map((tool) => tool.name);
  assert.ok(names.includes('get_chlom_chain_evidence_health'));
  assert.ok(names.includes('run_chlom_chain_read'));
  assert.ok(names.includes('run_chlom_blockchain_analytics'));
  assert.ok(names.includes('prepare_chlom_evidence_anchor'));
  assert.equal(names.some((name) => /broadcast|private_key|send_raw/i.test(name)), false);
  assert.equal(response.payload.result.tools.every((tool) => tool.annotations.readOnlyHint === true), true);
});

test('protected CHLOM MCP tool remains hold without the inbound control binding', async () => {
  await withEnv({ CROWNTHRIVE_CONTROL_TOKEN: undefined }, async () => {
    const request = modernRequest('tools/call', 7, {
      name: 'run_chlom_chain_read',
      arguments: { chain: 'ethereum', method: 'eth_blockNumber', params: [] },
    });
    const response = mockResponse();
    await mcpHandler(request, response);
    assert.equal(response.statusCode, 200);
    assert.equal(response.payload.result.isError, true);
    assert.equal(response.payload.result.structuredContent.status, 'HOLD');
  });
});

test('legacy initialize fallback remains available', async () => {
  const response = mockResponse();
  await mcpHandler({
    method: 'POST',
    url: '/api/mcp',
    headers: { host: 'crown-thrive-os.vercel.app' },
    body: {
      jsonrpc: '2.0',
      id: 9,
      method: 'initialize',
      params: {
        protocolVersion: '2025-11-25',
        capabilities: {},
        clientInfo: { name: 'legacy', version: '1' },
      },
    },
  }, response);
  assert.equal(response.statusCode, 200);
  assert.equal(response.payload.result.protocolVersion, '2025-11-25');
});
