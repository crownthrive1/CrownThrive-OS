import assert from 'node:assert/strict';
import test from 'node:test';
import handler, { paddleIntegrationStatus, routePaddleOperation } from '../api/mcp.js';

const TOKEN = 'test-control-token-not-a-provider-secret';

function request({ method = 'POST', headers = {}, body } = {}) {
  return { method, headers, body, query: {} };
}

function response() {
  return {
    statusCode: 200,
    headers: {},
    payload: undefined,
    ended: false,
    setHeader(name, value) {
      this.headers[String(name).toLowerCase()] = value;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(value) {
      this.payload = value;
      return this;
    },
    end(value) {
      this.payload = value;
      this.ended = true;
      return this;
    },
  };
}

function legacyBody(id, method, params = {}) {
  return { jsonrpc: '2.0', id, method, params };
}

function modernRequest(id, method, params = {}, name = null) {
  const modernParams = {
    ...params,
    _meta: {
      ...(params._meta || {}),
      'io.modelcontextprotocol/protocolVersion': '2026-07-28',
      'io.modelcontextprotocol/clientInfo': { name: 'test-client', version: '1.0.0' },
      'io.modelcontextprotocol/clientCapabilities': {},
    },
  };
  const headers = {
    authorization: `Bearer ${TOKEN}`,
    'mcp-protocol-version': '2026-07-28',
    'mcp-method': method,
  };
  if (name) headers['mcp-name'] = name;
  return request({ method: 'POST', headers, body: legacyBody(id, method, modernParams) });
}

process.env.CROWNTHRIVE_CONTROL_TOKEN = TOKEN;
delete process.env.PADDLE_SANDBOX_API_KEY;

test('route selects the exact catalog skill and defaults to sandbox', () => {
  const result = routePaddleOperation({ operation: 'catalog_setup', task: 'Seed controlled catalog' });
  assert.equal(result.required_skill, 'paddle-catalog-setup');
  assert.equal(result.mcp_server.id, 'paddle-sandbox');
  assert.equal(result.environment, 'sandbox');
  assert.equal(result.use_required, true);
  assert.equal(result.side_effect_performed, false);
});

test('live routing remains fail-closed', () => {
  const result = routePaddleOperation({ operation: 'subscription_update', environment: 'live' });
  assert.match(result.state, /^HOLD_/);
  assert.equal(result.mcp_server.id, 'paddle-live');
  assert.equal(result.side_effect_performed, false);
});

test('status never exposes credential values', () => {
  process.env.PADDLE_SANDBOX_API_KEY = 'pdl_sdbx_TEST_VALUE_MUST_NOT_APPEAR';
  const serialized = JSON.stringify(paddleIntegrationStatus());
  assert.equal(serialized.includes(process.env.PADDLE_SANDBOX_API_KEY), false);
  assert.equal(JSON.parse(serialized).credential_bindings.paddle_sandbox.bound, true);
  delete process.env.PADDLE_SANDBOX_API_KEY;
});

test('unauthenticated request is rejected before MCP dispatch', async () => {
  const res = response();
  await handler(request({ method: 'GET' }), res);
  assert.equal(res.statusCode, 401);
  assert.equal(res.payload.error, 'UNAUTHORIZED');
});

test('authenticated GET proves handler and Paddle inventory', async () => {
  const res = response();
  await handler(request({ method: 'GET', headers: { authorization: `Bearer ${TOKEN}` } }), res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.payload.state, 'PASS_AUTHENTICATED_HANDLER_READBACK');
  assert.equal(res.payload.tool_count, 3);
  assert.equal(res.payload.paddle_skill_count, 10);
  assert.deepEqual(res.payload.paddle_mcp_servers, ['paddle-docs', 'paddle-sandbox', 'paddle-live']);
});

test('modern server discovery advertises current protocol and cache controls', async () => {
  const req = modernRequest('discover-1', 'server/discover');
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 200);
  assert.deepEqual(res.payload.result.supportedVersions, ['2026-07-28']);
  assert.equal(res.payload.result.resultType, 'complete');
  assert.equal(res.payload.result.cacheScope, 'private');
  assert.equal(res.payload.result._meta['io.modelcontextprotocol/serverInfo'].name, 'CrownThrive OS MCP');
});

test('modern tools/list exposes governed Paddle tools', async () => {
  const req = modernRequest('list-1', 'tools/list');
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.payload.result.tools.length, 3);
  assert.equal(res.payload.result.tools[0].name, 'crownthrive_paddle_route');
  assert.equal(res.payload.result.ttlMs, 60_000);
});

test('modern route tool call uses paddle-catalog-setup and paddle-sandbox', async () => {
  const params = {
    name: 'crownthrive_paddle_route',
    arguments: { operation: 'catalog_setup', task: 'Prepare Go Flipbooks catalog wave 001' },
  };
  const req = modernRequest('call-1', 'tools/call', params, params.name);
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.payload.result.structuredContent.required_skill, 'paddle-catalog-setup');
  assert.equal(res.payload.result.structuredContent.mcp_server.id, 'paddle-sandbox');
  assert.equal(res.payload.result.structuredContent.side_effect_performed, false);
});

test('modern header/body mismatch is rejected with MCP header error', async () => {
  const req = modernRequest('call-2', 'tools/call', {
    name: 'crownthrive_paddle_route',
    arguments: { operation: 'catalog_setup' },
  }, 'different_tool');
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
  assert.equal(res.payload.error.code, -32020);
});

test('legacy initialize remains compatible through 2025-11-25', async () => {
  const req = request({
    method: 'POST',
    headers: { authorization: `Bearer ${TOKEN}` },
    body: legacyBody('init-1', 'initialize', {
      protocolVersion: '2025-11-25',
      capabilities: {},
      clientInfo: { name: 'legacy-test', version: '1.0.0' },
    }),
  });
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.payload.result.protocolVersion, '2025-11-25');
  assert.equal(res.payload.result.serverInfo.name, 'CrownThrive OS MCP');
});

test('unsupported protocol version returns the negotiated-version error', async () => {
  const req = request({
    method: 'POST',
    headers: {
      authorization: `Bearer ${TOKEN}`,
      'mcp-protocol-version': '2027-01-01',
      'mcp-method': 'tools/list',
    },
    body: legacyBody('unsupported-1', 'tools/list', {
      _meta: { 'io.modelcontextprotocol/protocolVersion': '2027-01-01' },
    }),
  });
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
  assert.equal(res.payload.error.code, -32022);
  assert.deepEqual(res.payload.error.data.supported, [
    '2026-07-28',
    '2025-11-25',
    '2025-06-18',
    '2025-03-26',
    '2024-11-05',
  ]);
});
