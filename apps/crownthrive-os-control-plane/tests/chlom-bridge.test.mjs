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

test('PentaFabric self-test callback ignores untrusted forwarding headers', async () => {
  const originalFetch = global.fetch;
  const requestedUrls = [];
  global.fetch = async (url) => {
    requestedUrls.push(url);
    return new Response(JSON.stringify({ status: 'PASS', pass_manufactured: false }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    const request = modernRequest('tools/call', 8, {
      name: 'run_pentafabric_self_test',
      arguments: {},
    });
    request.headers.host = 'attacker.example';
    request.headers['x-forwarded-host'] = '169.254.169.254';
    request.headers['x-forwarded-proto'] = 'http';
    const response = mockResponse();
    await mcpHandler(request, response);
    assert.equal(response.statusCode, 200);
    assert.equal(response.payload.result.isError, false);
    assert.deepEqual(requestedUrls, [
      'https://crown-thrive-os.vercel.app/api/penta?selftest=1',
    ]);
  } finally {
    global.fetch = originalFetch;
  }
});

test('gateway self-test holds when an exact generated deployment host is unavailable', async () => {
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    throw new Error('must not be called');
  };
  try {
    for (const vercelUrl of [undefined, 'crown-thrive-os.vercel.app']) {
      await withEnv({ VERCEL_URL: vercelUrl }, async () => {
        const response = mockResponse();
        await mcpHandler({
          method: 'GET',
          url: '/api/mcp?selftest=1',
          headers: {
            host: 'attacker.example',
            'x-forwarded-host': '169.254.169.254',
            'x-forwarded-proto': 'http',
          },
        }, response);
        assert.equal(response.statusCode, 503);
        assert.equal(response.payload.self_test.status, 'HOLD');
        assert.equal(response.payload.self_test.exact_deployment_origin, false);
        assert.match(response.payload.self_test.error, /generated VERCEL_URL host/i);
      });
    }
    assert.equal(calls, 0);
  } finally {
    global.fetch = originalFetch;
  }
});

test('gateway self-test rejects a same-size substituted tool catalog', async () => {
  const catalogResponse = mockResponse();
  await mcpHandler(modernRequest('tools/list'), catalogResponse);
  const tools = structuredClone(catalogResponse.payload.result.tools);
  tools[0].name = 'get_substituted_catalog_tool';
  const originalFetch = global.fetch;
  global.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    const result = body.method === 'server/discover'
      ? {
          supportedVersions: ['2026-07-28', '2025-11-25', '2025-06-18', '2025-03-26'],
          _meta: {
            'io.modelcontextprotocol/serverInfo': {
              name: 'crownthrive-vercel-fabric',
              version: '1.1.0',
            },
          },
        }
      : { tools };
    return new Response(JSON.stringify({ jsonrpc: '2.0', id: body.id, result }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv({ VERCEL_URL: 'crown-thrive-os-preview-abc123.vercel.app' }, async () => {
      const response = mockResponse();
      await mcpHandler({
        method: 'GET',
        url: '/api/mcp?selftest=1',
        headers: { host: 'crown-thrive-os.vercel.app' },
      }, response);
      assert.equal(response.statusCode, 503);
      assert.equal(response.payload.self_test.status, 'HOLD');
      assert.match(response.payload.self_test.error, /tool names did not exactly match/i);
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test('preview self-test callbacks bind to the validated candidate deployment', async () => {
  const catalogResponse = mockResponse();
  await mcpHandler(modernRequest('tools/list'), catalogResponse);
  const tools = catalogResponse.payload.result.tools;
  const originalFetch = global.fetch;
  const requestedUrls = [];
  global.fetch = async (url, options) => {
    requestedUrls.push(url);
    const body = JSON.parse(options.body);
    const result = body.method === 'server/discover'
      ? {
          supportedVersions: ['2026-07-28', '2025-11-25', '2025-06-18', '2025-03-26'],
          _meta: {
            'io.modelcontextprotocol/serverInfo': {
              name: 'crownthrive-vercel-fabric',
              version: '1.1.0',
            },
          },
        }
      : { tools };
    return new Response(JSON.stringify({ jsonrpc: '2.0', id: body.id, result }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };
  try {
    await withEnv({
      VERCEL_URL: 'crown-thrive-os-preview-abc123.vercel.app',
      VERCEL_GIT_COMMIT_SHA: 'a'.repeat(40),
    }, async () => {
      const response = mockResponse();
      await mcpHandler({
        method: 'GET',
        url: '/api/mcp?selftest=1',
        headers: {
          host: 'attacker.example',
          'x-forwarded-host': '169.254.169.254',
        },
      }, response);
      assert.equal(response.statusCode, 200);
      assert.equal(
        response.payload.self_test.callback_origin,
        'https://crown-thrive-os-preview-abc123.vercel.app',
      );
      assert.equal(response.payload.self_test.callback_build_sha, 'a'.repeat(40));
      assert.equal(response.payload.self_test.exact_deployment_origin, true);
      assert.deepEqual(requestedUrls, [
        'https://crown-thrive-os-preview-abc123.vercel.app/api/mcp',
        'https://crown-thrive-os-preview-abc123.vercel.app/api/mcp',
      ]);
    });
  } finally {
    global.fetch = originalFetch;
  }
});

test('unapproved candidate callback host fails closed without a request', async () => {
  const originalFetch = global.fetch;
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    throw new Error('must not be called');
  };
  try {
    await withEnv({ VERCEL_URL: 'attacker.vercel.app' }, async () => {
      const response = mockResponse();
      await mcpHandler({
        method: 'GET',
        url: '/api/mcp?selftest=1',
        headers: { host: 'attacker.example' },
      }, response);
      assert.equal(response.statusCode, 503);
      assert.equal(response.payload.self_test.status, 'HOLD');
      assert.equal(calls, 0);
    });
  } finally {
    global.fetch = originalFetch;
  }
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
