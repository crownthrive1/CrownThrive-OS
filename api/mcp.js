import { timingSafeEqual } from 'node:crypto';

const SERVER_INFO = Object.freeze({
  name: 'CrownThrive OS MCP',
  version: '3.16.0.0',
});

const MODERN_PROTOCOL = '2026-07-28';
const LEGACY_PROTOCOLS = Object.freeze([
  '2025-11-25',
  '2025-06-18',
  '2025-03-26',
  '2024-11-05',
]);
const ALL_PROTOCOLS = Object.freeze([MODERN_PROTOCOL, ...LEGACY_PROTOCOLS]);
const UPSTREAM_COMMIT = 'de7fcd3f6cc43bf87a65d6b2e65067611b47353c';
const CACHE_HINT = Object.freeze({ ttlMs: 60_000, cacheScope: 'private' });
const SERVER_META_KEY = 'io.modelcontextprotocol/serverInfo';
const PROTOCOL_META_KEY = 'io.modelcontextprotocol/protocolVersion';

const PADDLE_MCP = Object.freeze({
  docs: Object.freeze({ id: 'paddle-docs', url: 'https://paddlehq.mcp.kapa.ai' }),
  sandbox: Object.freeze({ id: 'paddle-sandbox', url: 'https://sandbox-mcp.paddle.com/mcp' }),
  live: Object.freeze({ id: 'paddle-live', url: 'https://mcp.paddle.com/mcp' }),
});

const PADDLE_SKILLS = Object.freeze({
  billing_history: Object.freeze({
    skill: 'paddle-billing-history',
    purpose: 'Authenticated customer transaction history and invoice downloads.',
  }),
  catalog_setup: Object.freeze({
    skill: 'paddle-catalog-setup',
    purpose: 'Products, prices, tax categories, billing intervals, and catalog seeding.',
  }),
  checkout_web: Object.freeze({
    skill: 'paddle-checkout-web',
    purpose: 'Paddle Checkout integration for web applications.',
  }),
  customer_portal: Object.freeze({
    skill: 'paddle-customer-portal',
    purpose: 'Authenticated customer portal sessions and self-service billing.',
  }),
  pricing_pages: Object.freeze({
    skill: 'paddle-pricing-pages',
    purpose: 'Localized pricing previews, currencies, and billing-frequency presentation.',
  }),
  sandbox_testing: Object.freeze({
    skill: 'paddle-sandbox-testing',
    purpose: 'End-to-end Paddle sandbox tests and integration canaries.',
  }),
  subscription_cancel: Object.freeze({
    skill: 'paddle-subscription-cancel',
    purpose: 'Authorized cancellation-at-period-end flows and reconciliation.',
  }),
  subscription_sync: Object.freeze({
    skill: 'paddle-subscription-sync',
    purpose: 'Webhook-driven customer and subscription state synchronization.',
  }),
  subscription_update: Object.freeze({
    skill: 'paddle-subscription-update',
    purpose: 'Authorized upgrades, downgrades, item changes, and proration handling.',
  }),
  webhooks: Object.freeze({
    skill: 'paddle-webhooks',
    purpose: 'Webhook receipt, signature verification, idempotency, retry, and reconciliation.',
  }),
});

const OPERATION_ENUM = Object.freeze(Object.keys(PADDLE_SKILLS));
const ENVIRONMENT_ENUM = Object.freeze(['docs', 'sandbox', 'live']);

const TOOLS = Object.freeze([
  Object.freeze({
    name: 'crownthrive_paddle_route',
    title: 'Route a governed Paddle Billing operation',
    description:
      'Selects the exact pinned Paddle skill and MCP environment for a CrownThrive operation. This is read-only and never grants provider authority.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        operation: { type: 'string', enum: OPERATION_ENUM },
        environment: { type: 'string', enum: ENVIRONMENT_ENUM, default: 'sandbox' },
        task: { type: 'string', minLength: 1, maxLength: 2000 },
      },
      required: ['operation'],
    },
    annotations: {
      title: 'Route Paddle Billing work',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  }),
  Object.freeze({
    name: 'crownthrive_paddle_integration_status',
    title: 'Read Paddle integration status',
    description:
      'Returns public-safe source, route, credential-binding, and production-gate status for the CrownThrive Paddle Billing integration.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {},
    },
    annotations: {
      title: 'Read Paddle integration status',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  }),
  Object.freeze({
    name: 'crownthrive_paddle_preflight',
    title: 'Preflight a Paddle Billing lane',
    description:
      'Checks the selected skill, MCP route, local credential binding, and remaining authority/readback gates without contacting Paddle or causing a side effect.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        operation: { type: 'string', enum: OPERATION_ENUM },
        environment: { type: 'string', enum: ENVIRONMENT_ENUM, default: 'sandbox' },
      },
      required: ['operation'],
    },
    annotations: {
      title: 'Preflight Paddle Billing work',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  }),
]);

const RESOURCES = Object.freeze([
  Object.freeze({
    uri: 'crownthrive://integrations/paddle-billing',
    name: 'paddle-billing-integration',
    title: 'Paddle Billing integration contract',
    description: 'Pinned provider, MCP, skill, environment, and truth-boundary metadata.',
    mimeType: 'application/json',
  }),
  Object.freeze({
    uri: 'crownthrive://skills/paddle-billing-governed-routing',
    name: 'paddle-billing-governed-routing',
    title: 'Paddle Billing governed routing',
    description: 'Maps CrownThrive Paddle work to the exact required upstream skill and MCP lane.',
    mimeType: 'application/json',
  }),
  Object.freeze({
    uri: 'crownthrive://mcp/topology',
    name: 'crownthrive-mcp-topology',
    title: 'CrownThrive MCP topology',
    description: 'Public-safe MCP route inventory and credential-binding model.',
    mimeType: 'application/json',
  }),
]);

const PROMPTS = Object.freeze([
  Object.freeze({
    name: 'paddle_governed_operation',
    title: 'Execute a governed Paddle Billing operation',
    description: 'Builds an execution prompt that requires the exact Paddle skill and environment.',
    arguments: [
      { name: 'operation', description: `One of: ${OPERATION_ENUM.join(', ')}`, required: true },
      { name: 'task', description: 'The bounded CrownThrive task to perform.', required: true },
      { name: 'environment', description: 'docs, sandbox, or live. Defaults to sandbox.', required: false },
    ],
  }),
]);

function getHeader(req, name) {
  const headers = req?.headers || {};
  const value = headers[name.toLowerCase()] ?? headers[name] ?? headers[name.toUpperCase()];
  return Array.isArray(value) ? value[0] : value;
}

function secureEqual(left, right) {
  const a = Buffer.from(String(left || ''), 'utf8');
  const b = Buffer.from(String(right || ''), 'utf8');
  if (a.length === 0 || a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

function authenticate(req) {
  const expected = process.env.CROWNTHRIVE_CONTROL_TOKEN;
  if (!expected) return { ok: false, status: 503, code: 'MCP_CONTROL_TOKEN_UNBOUND' };
  const authorization = String(getHeader(req, 'authorization') || '');
  const match = /^Bearer\s+(.+)$/i.exec(authorization);
  if (!match || !secureEqual(match[1], expected)) {
    return { ok: false, status: 401, code: 'UNAUTHORIZED' };
  }
  return { ok: true };
}

function parseBody(req) {
  const body = req?.body;
  if (body && typeof body === 'object' && !Buffer.isBuffer(body)) return body;
  if (Buffer.isBuffer(body)) return JSON.parse(body.toString('utf8'));
  if (typeof body === 'string' && body.trim()) return JSON.parse(body);
  throw new Error('EMPTY_OR_INVALID_JSON_BODY');
}

function serverMeta() {
  return { [SERVER_META_KEY]: SERVER_INFO };
}

function isModernRequest(req, payload) {
  const headerVersion = String(getHeader(req, 'mcp-protocol-version') || '');
  const metaVersion = String(payload?.params?._meta?.[PROTOCOL_META_KEY] || '');
  return (
    payload?.method === 'server/discover' ||
    headerVersion === MODERN_PROTOCOL ||
    metaVersion === MODERN_PROTOCOL ||
    (Boolean(headerVersion) && !LEGACY_PROTOCOLS.includes(headerVersion)) ||
    (Boolean(metaVersion) && !LEGACY_PROTOCOLS.includes(metaVersion))
  );
}

function jsonRpcError(id, code, message, data) {
  return {
    jsonrpc: '2.0',
    id: id ?? null,
    error: {
      code,
      message,
      ...(data === undefined ? {} : { data }),
    },
  };
}

function completeResult(id, result, modern) {
  const normalized = modern
    ? {
        resultType: 'complete',
        ...result,
        _meta: { ...(result?._meta || {}), ...serverMeta() },
      }
    : result;
  return { jsonrpc: '2.0', id, result: normalized };
}

function validateModernEnvelope(req, payload) {
  const headerVersion = String(getHeader(req, 'mcp-protocol-version') || '');
  const metaVersion = String(payload?.params?._meta?.[PROTOCOL_META_KEY] || '');
  if (headerVersion && !ALL_PROTOCOLS.includes(headerVersion)) {
    return {
      status: 400,
      body: jsonRpcError(payload?.id, -32022, 'Unsupported protocol version', {
        supported: ALL_PROTOCOLS,
        requested: headerVersion,
      }),
    };
  }
  if (headerVersion !== MODERN_PROTOCOL || metaVersion !== MODERN_PROTOCOL) {
    return {
      status: 400,
      body: jsonRpcError(payload?.id, -32020, 'Modern MCP protocol header or metadata mismatch', {
        expected: MODERN_PROTOCOL,
        header: headerVersion || null,
        metadata: metaVersion || null,
      }),
    };
  }

  const methodHeader = String(getHeader(req, 'mcp-method') || '');
  if (!methodHeader || methodHeader !== payload.method) {
    return {
      status: 400,
      body: jsonRpcError(payload?.id, -32020, 'Mcp-Method header mismatch', {
        header: methodHeader || null,
        body: payload.method || null,
      }),
    };
  }

  const names = {
    'tools/call': payload?.params?.name,
    'resources/read': payload?.params?.uri,
    'prompts/get': payload?.params?.name,
  };
  if (Object.prototype.hasOwnProperty.call(names, payload.method)) {
    const nameHeader = String(getHeader(req, 'mcp-name') || '');
    const bodyName = String(names[payload.method] || '');
    if (!nameHeader || nameHeader !== bodyName) {
      return {
        status: 400,
        body: jsonRpcError(payload?.id, -32020, 'Mcp-Name header mismatch', {
          header: nameHeader || null,
          body: bodyName || null,
        }),
      };
    }
  }
  return null;
}

function assertObject(value, field) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${field} must be an object`);
  }
}

function assertEnum(value, allowed, field) {
  if (!allowed.includes(value)) {
    throw new TypeError(`${field} must be one of: ${allowed.join(', ')}`);
  }
}

export function routePaddleOperation(args = {}) {
  assertObject(args, 'arguments');
  const operation = args.operation;
  assertEnum(operation, OPERATION_ENUM, 'operation');
  const environment = args.environment || 'sandbox';
  assertEnum(environment, ENVIRONMENT_ENUM, 'environment');

  const selected = PADDLE_SKILLS[operation];
  const mcp = PADDLE_MCP[environment];
  const routeState =
    environment === 'live'
      ? 'HOLD_EXACT_LIVE_OPERATION_AUTHORITY_REQUIRED'
      : environment === 'sandbox'
        ? 'ROUTED_SANDBOX_PROVIDER_AUTH_AND_READBACK_REQUIRED'
        : 'ROUTED_DOCUMENTATION_AUTH_MAY_BE_REQUIRED';

  return {
    state: routeState,
    operation,
    task: typeof args.task === 'string' ? args.task.slice(0, 2000) : null,
    required_skill: selected.skill,
    skill_purpose: selected.purpose,
    upstream_source: {
      repository: 'PaddleHQ/paddle-agent-skills',
      commit: UPSTREAM_COMMIT,
      plugin: 'paddle',
    },
    mcp_server: mcp,
    environment,
    use_required: true,
    side_effect_performed: false,
    next_control:
      environment === 'live'
        ? 'Resolve eligible operator OAuth, provider write scope, exact-operation authority, idempotency, rollback, and provider readback.'
        : environment === 'sandbox'
          ? 'Load the required skill, verify PADDLE_SANDBOX_API_KEY binding, call paddle-sandbox, and preserve sanitized provider readback.'
          : 'Load the required skill and use paddle-docs to resolve current provider semantics before implementation.',
    truth_boundary:
      'Routing selects an implementation skill and MCP lane; it does not authenticate Paddle, grant authority, perform a provider action, or certify production.',
  };
}

export function paddleIntegrationStatus() {
  return {
    state: 'CONTROLLED_TEST',
    handler_state: 'SOURCE_HANDLER_EXECUTING',
    production_state: 'HOLD',
    server: SERVER_INFO,
    supported_protocols: ALL_PROTOCOLS,
    upstream: {
      repository: 'PaddleHQ/paddle-agent-skills',
      commit: UPSTREAM_COMMIT,
      plugin: 'paddle',
      skill_count: OPERATION_ENUM.length,
    },
    mcp_servers: PADDLE_MCP,
    credential_bindings: {
      control_token: { bound: Boolean(process.env.CROWNTHRIVE_CONTROL_TOKEN), secret_exposed: false },
      paddle_sandbox: { bound: Boolean(process.env.PADDLE_SANDBOX_API_KEY), secret_exposed: false },
      paddle_live: { mode: 'eligible-operator OAuth at client', bound_here: false, secret_exposed: false },
    },
    skills: OPERATION_ENUM.map((operation) => ({ operation, ...PADDLE_SKILLS[operation] })),
    provider_readback: 'NOT_PERFORMED_BY_THIS_STATUS_TOOL',
    side_effect_performed: false,
    truth_boundary:
      'This status proves the authenticated CrownThrive OS MCP handler executed. It does not prove Paddle authentication, provider availability, settlement, entitlement, revenue, or production certification.',
  };
}

export function paddlePreflight(args = {}) {
  const route = routePaddleOperation(args);
  const blockers = [];
  if (route.environment === 'sandbox' && !process.env.PADDLE_SANDBOX_API_KEY) {
    blockers.push('PADDLE_SANDBOX_API_KEY_NOT_BOUND');
  }
  if (route.environment === 'live') {
    blockers.push('ELIGIBLE_OPERATOR_OAUTH_NOT_PROVABLE_AT_SERVER');
    blockers.push('EXACT_LIVE_OPERATION_AUTHORITY_REQUIRED');
    blockers.push('PROVIDER_WRITE_SCOPE_AND_READBACK_REQUIRED');
  }
  if (route.environment === 'docs') {
    blockers.push('INTERACTIVE_PROVIDER_AUTH_MAY_BE_REQUIRED');
  }

  return {
    state: blockers.length === 0 ? 'READY_FOR_BOUNDED_SANDBOX_CALL' : 'HOLD',
    route,
    blockers,
    checked_at: new Date().toISOString(),
    provider_contacted: false,
    side_effect_performed: false,
  };
}

function resourcePayload(uri) {
  if (uri === 'crownthrive://integrations/paddle-billing') return paddleIntegrationStatus();
  if (uri === 'crownthrive://skills/paddle-billing-governed-routing') {
    return {
      name: 'paddle-billing-governed-routing',
      default_environment: 'sandbox',
      upstream_commit: UPSTREAM_COMMIT,
      routes: OPERATION_ENUM.map((operation) => ({ operation, ...PADDLE_SKILLS[operation] })),
      invariant:
        'Load the exact matching paddle-* skill before implementation; use paddle-docs for current semantics; never infer live authority.',
    };
  }
  if (uri === 'crownthrive://mcp/topology') {
    return {
      crownthrive_os: { endpoint: '/api/mcp', authentication: 'CROWNTHRIVE_CONTROL_TOKEN bearer' },
      paddle: PADDLE_MCP,
      secret_values_exposed: false,
      source_commit: process.env.VERCEL_GIT_COMMIT_SHA || null,
      deployment_url: process.env.VERCEL_URL || null,
    };
  }
  return null;
}

function callTool(name, args) {
  if (name === 'crownthrive_paddle_route') return routePaddleOperation(args);
  if (name === 'crownthrive_paddle_integration_status') return paddleIntegrationStatus();
  if (name === 'crownthrive_paddle_preflight') return paddlePreflight(args);
  throw new TypeError(`Unknown tool: ${name}`);
}

function listResult(key, values, modern) {
  return modern ? { [key]: values, ...CACHE_HINT } : { [key]: values };
}

function handleRpc(req, payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || payload.jsonrpc !== '2.0' || typeof payload.method !== 'string') {
    return { status: 400, body: jsonRpcError(payload?.id, -32600, 'Invalid Request') };
  }

  const modern = isModernRequest(req, payload);
  if (modern) {
    const invalidEnvelope = validateModernEnvelope(req, payload);
    if (invalidEnvelope) return invalidEnvelope;
  }

  const id = payload.id;
  const params = payload.params || {};

  try {
    switch (payload.method) {
      case 'server/discover':
        return {
          status: 200,
          body: completeResult(
            id,
            {
              supportedVersions: [MODERN_PROTOCOL],
              capabilities: {
                tools: { listChanged: false },
                resources: { subscribe: false, listChanged: false },
                prompts: { listChanged: false },
              },
              instructions:
                'Use CrownThrive Paddle routing tools before Paddle Billing work. Default to sandbox. Live operations remain fail-closed until exact authority and provider readback are present.',
              ...CACHE_HINT,
            },
            true,
          ),
        };
      case 'initialize': {
        const requested = String(params.protocolVersion || LEGACY_PROTOCOLS[0]);
        const selected = LEGACY_PROTOCOLS.includes(requested) ? requested : LEGACY_PROTOCOLS[0];
        return {
          status: 200,
          body: completeResult(
            id,
            {
              protocolVersion: selected,
              capabilities: {
                tools: { listChanged: false },
                resources: { subscribe: false, listChanged: false },
                prompts: { listChanged: false },
              },
              serverInfo: SERVER_INFO,
              instructions:
                'Use CrownThrive Paddle routing tools before Paddle Billing work. Default to sandbox and preserve provider readback.',
            },
            false,
          ),
        };
      }
      case 'notifications/initialized':
        return { status: 202, notification: true };
      case 'ping':
        return { status: 200, body: completeResult(id, {}, modern) };
      case 'tools/list':
        return { status: 200, body: completeResult(id, listResult('tools', TOOLS, modern), modern) };
      case 'tools/call': {
        const name = params.name;
        const result = callTool(name, params.arguments || {});
        return {
          status: 200,
          body: completeResult(
            id,
            {
              content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
              structuredContent: result,
              isError: false,
            },
            modern,
          ),
        };
      }
      case 'resources/list':
        return { status: 200, body: completeResult(id, listResult('resources', RESOURCES, modern), modern) };
      case 'resources/read': {
        const data = resourcePayload(params.uri);
        if (!data) return { status: 404, body: jsonRpcError(id, -32602, 'Unknown resource URI') };
        const result = {
          contents: [
            {
              uri: params.uri,
              mimeType: 'application/json',
              text: JSON.stringify(data, null, 2),
            },
          ],
          ...(modern ? CACHE_HINT : {}),
        };
        return { status: 200, body: completeResult(id, result, modern) };
      }
      case 'prompts/list':
        return { status: 200, body: completeResult(id, listResult('prompts', PROMPTS, modern), modern) };
      case 'prompts/get': {
        if (params.name !== 'paddle_governed_operation') {
          return { status: 404, body: jsonRpcError(id, -32602, 'Unknown prompt') };
        }
        const promptArgs = params.arguments || {};
        const operation = promptArgs.operation;
        const task = promptArgs.task;
        if (!operation || !task) throw new TypeError('operation and task are required');
        const route = routePaddleOperation({
          operation,
          environment: promptArgs.environment || 'sandbox',
          task,
        });
        const text = [
          `Perform this CrownThrive Paddle Billing task: ${task}`,
          `Required skill: ${route.required_skill}`,
          `Required MCP server: ${route.mcp_server.id}`,
          `Environment: ${route.environment}`,
          'Use paddle-docs first when current provider semantics are material.',
          'Do not infer live authority. Preserve sanitized provider readback and downstream reconciliation evidence.',
          `Current route state: ${route.state}`,
        ].join('\n');
        return {
          status: 200,
          body: completeResult(
            id,
            {
              description: 'Governed CrownThrive Paddle Billing operation',
              messages: [{ role: 'user', content: { type: 'text', text } }],
            },
            modern,
          ),
        };
      }
      default:
        return { status: 404, body: jsonRpcError(id, -32601, 'Method not found') };
    }
  } catch (error) {
    return {
      status: 400,
      body: jsonRpcError(id, -32602, 'Invalid params', { detail: String(error?.message || error) }),
    };
  }
}

function setSecurityHeaders(res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'; base-uri 'none'");
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Referrer-Policy', 'no-referrer');
}

export default async function handler(req, res) {
  setSecurityHeaders(res);

  if (req.method === 'OPTIONS') {
    res.setHeader('Allow', 'GET, POST, OPTIONS');
    return res.status(204).end();
  }

  if (!['GET', 'POST'].includes(req.method)) {
    res.setHeader('Allow', 'GET, POST, OPTIONS');
    return res.status(405).json({ error: 'METHOD_NOT_ALLOWED' });
  }

  const auth = authenticate(req);
  if (!auth.ok) {
    if (auth.status === 401) res.setHeader('WWW-Authenticate', 'Bearer realm="CrownThrive OS MCP"');
    return res.status(auth.status).json({
      error: auth.code,
      secret_exposed: false,
      production_state: 'HOLD',
    });
  }

  if (req.method === 'GET') {
    return res.status(200).json({
      state: 'PASS_AUTHENTICATED_HANDLER_READBACK',
      service: SERVER_INFO.name,
      version: SERVER_INFO.version,
      supported_protocols: ALL_PROTOCOLS,
      tool_count: TOOLS.length,
      resource_count: RESOURCES.length,
      prompt_count: PROMPTS.length,
      paddle_skill_count: OPERATION_ENUM.length,
      paddle_mcp_servers: Object.values(PADDLE_MCP).map((server) => server.id),
      source_commit: process.env.VERCEL_GIT_COMMIT_SHA || null,
      deployment_url: process.env.VERCEL_URL || null,
      production_state: 'HOLD_PROVIDER_AUTH_AND_READBACK',
      secret_exposed: false,
    });
  }

  let payload;
  try {
    payload = parseBody(req);
  } catch (error) {
    return res.status(400).json(jsonRpcError(null, -32700, 'Parse error', { detail: String(error?.message || error) }));
  }

  if (Array.isArray(payload)) {
    return res.status(400).json(jsonRpcError(null, -32600, 'JSON-RPC batching is not supported'));
  }

  const response = handleRpc(req, payload);
  if (response.notification) return res.status(response.status).end();
  return res.status(response.status).json(response.body);
}
