import test from 'node:test';
import assert from 'node:assert/strict';

import handler from '../api/mcp-paddle.js';
import {
  PADDLE_OPERATIONS,
  paddleIntegrationStatus,
  routePaddleOperation,
} from '../lib/paddle-fabric.js';

function request({ method = 'POST', headers = {}, body = undefined } = {}) {
  return { method, headers, body, query: {} };
}

function response() {
  return {
    statusCode: 200,
    headers: {},
    body: undefined,
    setHeader(name, value) {
      this.headers[String(name).toLowerCase()] = value;
    },
    getHeader(name) {
      return this.headers[String(name).toLowerCase()];
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(value) {
      this.body = value;
      return this;
    },
    send(value) {
      this.body = value;
      return this;
    },
    end(value) {
      this.body = value;
      return this;
    },
  };
}

function rpc(id, method, params = {}) {
  return { jsonrpc: '2.0', id, method, params };
}

function modernRequest(id, name, args = {}) {
  return request({
    headers: {
      'mcp-protocol-version': '2026-07-28',
      'mcp-method': 'tools/call',
      'mcp-name': name,
    },
    body: rpc(id, 'tools/call', {
      name,
      arguments: args,
      _meta: {
        'io.modelcontextprotocol/protocolVersion': '2026-07-28',
        'io.modelcontextprotocol/clientInfo': { name: 'paddle-serving-test', version: '1.0.0' },
        'io.modelcontextprotocol/clientCapabilities': {},
      },
    }),
  });
}

test('Paddle source registry exposes exactly ten governed operations', () => {
  assert.equal(PADDLE_OPERATIONS.length, 10);
  assert.equal(PADDLE_OPERATIONS.includes('catalog_setup'), true);
  assert.equal(PADDLE_OPERATIONS.includes('webhooks'), true);
});

test('catalog setup deterministically routes to the pinned sandbox skill', () => {
  const result = routePaddleOperation({ operation: 'catalog_setup', task: 'Seed governed catalog' });
  assert.equal(result.required_skill, 'paddle-catalog-setup');
  assert.equal(result.mcp_server.id, 'paddle-sandbox');
  assert.equal(result.environment, 'sandbox');
  assert.equal(result.use_required, true);
  assert.equal(result.provider_contacted, false);
  assert.equal(result.side_effect_performed, false);
});

test('live routing remains fail-closed', () => {
  const result = routePaddleOperation({ operation: 'subscription_update', environment: 'live' });
  assert.equal(result.mcp_server.id, 'paddle-live');
  assert.match(result.state, /^HOLD_/);
  assert.equal(result.provider_contacted, false);
});

test('status does not expose credential values', () => {
  process.env.PADDLE_SANDBOX_API_KEY = 'pdl_sdbx_TEST_VALUE_MUST_NOT_APPEAR';
  const serialized = JSON.stringify(paddleIntegrationStatus());
  assert.equal(serialized.includes(process.env.PADDLE_SANDBOX_API_KEY), false);
  assert.equal(JSON.parse(serialized).upstream.skill_count, 10);
  delete process.env.PADDLE_SANDBOX_API_KEY;
});

test('GET descriptor preserves nine tools and adds all three Paddle tools', async () => {
  const res = response();
  await handler(request({ method: 'GET' }), res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.status, 'OPERATIONAL');
  assert.equal(res.body.tools.length, 12);
  assert.equal(res.body.tools.includes('get_vercel_fabric_health'), true);
  assert.equal(res.body.tools.includes('run_chlom_chain_read'), true);
  assert.equal(res.body.tools.includes('crownthrive_paddle_route'), true);
  assert.equal(res.body.tools.includes('crownthrive_paddle_integration_status'), true);
  assert.equal(res.body.tools.includes('crownthrive_paddle_preflight'), true);
  assert.equal(res.body.paddle_billing.skill_count, 10);
  assert.equal(res.body.write_tools, 0);
});

test('legacy tools/list returns twelve read-only tools', async () => {
  const res = response();
  await handler(request({ body: rpc('list-legacy', 'tools/list') }), res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.result.tools.length, 12);
  assert.equal(res.body.result.tools.every((tool) => tool.annotations?.readOnlyHint === true), true);
});

test('modern Paddle route call proves required skill and MCP lane', async () => {
  const res = response();
  await handler(modernRequest('route-modern', 'crownthrive_paddle_route', {
    operation: 'catalog_setup',
    task: 'Prepare Go Flipbooks catalog wave 001',
  }), res);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.result.resultType, 'complete');
  assert.equal(res.body.result.structuredContent.required_skill, 'paddle-catalog-setup');
  assert.equal(res.body.result.structuredContent.mcp_server.id, 'paddle-sandbox');
  assert.equal(res.body.result.structuredContent.side_effect_performed, false);
});

test('protected sandbox preflight reports local binding without returning the secret', async () => {
  process.env.CROWNTHRIVE_CONTROL_TOKEN = 'test-control-token';
  process.env.PADDLE_SANDBOX_API_KEY = 'pdl_sdbx_TEST_VALUE_MUST_NOT_APPEAR';
  const req = modernRequest('preflight-modern', 'crownthrive_paddle_preflight', {
    operation: 'sandbox_testing',
    environment: 'sandbox',
  });
  req.headers.authorization = 'Bearer test-control-token';
  const res = response();
  await handler(req, res);
  const serialized = JSON.stringify(res.body);
  assert.equal(res.statusCode, 200);
  assert.equal(res.body.result.structuredContent.state, 'READY_FOR_BOUNDED_SANDBOX_CALL');
  assert.equal(res.body.result.structuredContent.sandbox_credential_bound, true);
  assert.equal(serialized.includes(process.env.PADDLE_SANDBOX_API_KEY), false);
  delete process.env.CROWNTHRIVE_CONTROL_TOKEN;
  delete process.env.PADDLE_SANDBOX_API_KEY;
});

test('modern Mcp-Name mismatch fails closed', async () => {
  const req = modernRequest('mismatch', 'crownthrive_paddle_route', { operation: 'catalog_setup' });
  req.headers['mcp-name'] = 'different_tool';
  const res = response();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
  assert.equal(res.body.error.message, 'MCP_HEADER_METADATA_MISMATCH');
  assert.equal(res.body.error.data.state, 'HOLD');
});
