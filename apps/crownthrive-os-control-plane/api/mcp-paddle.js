import legacyMcpHandler from './mcp.js';
import {
  normalizeChlomBridgeError,
  requireControlAuthorization,
  validateBridgeOrigin,
} from '../lib/chlom-fabric.js';
import { requestHeader } from '../lib/vercel-oidc.js';
import {
  PADDLE_ENVIRONMENTS,
  PADDLE_OPERATIONS,
  paddleGatewayDescriptor,
  paddleIntegrationStatus,
  preflightPaddleOperation,
  routePaddleOperation,
} from '../lib/paddle-fabric.js';

const MODERN_PROTOCOL = '2026-07-28';
const LEGACY_PROTOCOLS = Object.freeze(['2025-11-25', '2025-06-18', '2025-03-26']);
const SERVER_INFO = Object.freeze({ name: 'crownthrive-vercel-fabric', version: '1.2.0' });
const SERVER_META_KEY = 'io.modelcontextprotocol/serverInfo';
const PROTOCOL_META_KEY = 'io.modelcontextprotocol/protocolVersion';

const PADDLE_TOOLS = Object.freeze([
  Object.freeze({
    name: 'crownthrive_paddle_route',
    title: 'Route a governed Paddle Billing operation',
    description: 'Select the exact pinned Paddle skill and MCP environment for a CrownThrive operation without contacting Paddle or granting provider authority.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        operation: { type: 'string', enum: PADDLE_OPERATIONS },
        environment: { type: 'string', enum: PADDLE_ENVIRONMENTS, default: 'sandbox' },
        task: { type: 'string', minLength: 1, maxLength: 2000 },
      },
      required: ['operation'],
    },
    annotations: { title: 'Route Paddle Billing work', readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }),
  Object.freeze({
    name: 'crownthrive_paddle_integration_status',
    title: 'Read Paddle Billing integration status',
    description: 'Return the public-safe pinned source, skill inventory, MCP topology, and remaining provider gates without exposing credentials.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    annotations: { title: 'Read Paddle integration status', readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }),
  Object.freeze({
    name: 'crownthrive_paddle_preflight',
    title: 'Preflight a Paddle Billing lane',
    description: 'Protected read-only check of the exact skill route, sandbox credential binding, and remaining live-authority gates without contacting Paddle.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        operation: { type: 'string', enum: PADDLE_OPERATIONS },
        environment: { type: 'string', enum: PADDLE_ENVIRONMENTS, default: 'sandbox' },
      },
      required: ['operation'],
    },
    annotations: { title: 'Preflight Paddle Billing work', readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
  }),
]);

const PADDLE_TOOL_NAMES = new Set(PADDLE_TOOLS.map((tool) => tool.name));
const PADDLE_PROTECTED_TOOLS = new Set(['crownthrive_paddle_preflight']);

function safeSetHeader(response, name, value) {
  try {
    response.setHeader(name, value);
  } catch {
    // Preserve response compatibility across Vercel and tests.
  }
}

function sendJson(response, statusCode, body, extraHeaders = {}) {
  const headers = {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    ...extraHeaders,
  };
  for (const [name, value] of Object.entries(headers)) safeSetHeader(response, name, value);
  return response.status(statusCode).json(body);
}

function captureResponse() {
  return {
    statusCode: 200,
    headers: new Map(),
    body: undefined,
    setHeader(name, value) {
      this.headers.set(String(name), value);
    },
    getHeader(name) {
      return this.headers.get(String(name));
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

function flushCaptured(captured, response, transform = (value) => value) {
  for (const [name, value] of captured.headers.entries()) safeSetHeader(response, name, value);
  const body = transform(captured.body);
  if (body === undefined) return response.status(captured.statusCode).end();
  if (typeof body === 'object' && body !== null) return response.status(captured.statusCode).json(body);
  return response.status(captured.statusCode).send(body);
}

function parseRpcRequest(request) {
  let body = request.body;
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body);
    } catch {
      throw Object.assign(new Error('The request body must be valid JSON.'), { statusCode: 400, code: 'INVALID_JSON' });
    }
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    throw Object.assign(new Error('The request body must be a JSON object.'), { statusCode: 400, code: 'INVALID_REQUEST' });
  }
  if (body.jsonrpc !== '2.0' || typeof body.method !== 'string') {
    throw Object.assign(new Error('A valid JSON-RPC 2.0 method is required.'), { statusCode: 400, code: 'INVALID_REQUEST' });
  }
  return body;
}

function protocolContext(request, rpcRequest) {
  const headerVersion = requestHeader(request, 'mcp-protocol-version') || '';
  const metadataVersion = rpcRequest?.params?._meta?.[PROTOCOL_META_KEY] || '';
  const requested = headerVersion || metadataVersion || '';
  const modern = requested === MODERN_PROTOCOL;
  const unsupported = Boolean(requested) && requested !== MODERN_PROTOCOL && !LEGACY_PROTOCOLS.includes(requested);
  if (unsupported) {
    throw Object.assign(new Error(`Unsupported MCP protocol version: ${requested}`), {
      statusCode: 400,
      code: 'UNSUPPORTED_PROTOCOL_VERSION',
    });
  }
  return { modern, headerVersion, metadataVersion };
}

function validateModernEnvelope(request, rpcRequest, context) {
  if (!context.modern) return;
  if (context.headerVersion !== MODERN_PROTOCOL || context.metadataVersion !== MODERN_PROTOCOL) {
    throw Object.assign(new Error('The modern MCP protocol header and request metadata must both identify 2026-07-28.'), {
      statusCode: 400,
      code: 'MCP_HEADER_METADATA_MISMATCH',
    });
  }
  const methodHeader = requestHeader(request, 'mcp-method') || '';
  if (methodHeader !== rpcRequest.method) {
    throw Object.assign(new Error('The Mcp-Method header must match the JSON-RPC method.'), {
      statusCode: 400,
      code: 'MCP_HEADER_METADATA_MISMATCH',
    });
  }
  if (rpcRequest.method === 'tools/call') {
    const nameHeader = requestHeader(request, 'mcp-name') || '';
    if (nameHeader !== rpcRequest?.params?.name) {
      throw Object.assign(new Error('The Mcp-Name header must match the requested tool name.'), {
        statusCode: 400,
        code: 'MCP_HEADER_METADATA_MISMATCH',
      });
    }
  }
}

function completeToolResult(id, payload, modern) {
  const result = {
    content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
    structuredContent: payload,
    isError: false,
  };
  if (modern) {
    result.resultType = 'complete';
    result._meta = { [SERVER_META_KEY]: SERVER_INFO };
  }
  return { jsonrpc: '2.0', id, result };
}

function buildErrorData(request, error, normalized) {
  return {
    state: 'HOLD',
    code: normalized.code,
    error: error instanceof Error ? error.message : String(error),
    request_id: requestHeader(request, 'x-vercel-id') || null,
    deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
    build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
    pass_manufactured: false,
  };
}

function augmentDescriptor(descriptor) {
  if (!descriptor || typeof descriptor !== 'object') return descriptor;
  const existingTools = Array.isArray(descriptor.tools) ? descriptor.tools : [];
  const existingProtected = Array.isArray(descriptor.protected_tools) ? descriptor.protected_tools : [];
  return {
    ...descriptor,
    tools: [...new Set([...existingTools, ...PADDLE_TOOLS.map((tool) => tool.name)])],
    protected_tools: [...new Set([...existingProtected, ...PADDLE_PROTECTED_TOOLS])],
    authorization: {
      ...(descriptor.authorization || {}),
      public: 'provider_health_contract_and_paddle_routing_metadata',
      protected: 'CROWNTHRIVE_CONTROL_TOKEN',
    },
    paddle_billing: paddleGatewayDescriptor(),
    write_tools: 0,
    pass_manufactured: false,
  };
}

function augmentToolList(body) {
  if (!body || typeof body !== 'object' || body.error || !body.result || !Array.isArray(body.result.tools)) return body;
  const names = new Set(body.result.tools.map((tool) => tool?.name));
  const additions = PADDLE_TOOLS.filter((tool) => !names.has(tool.name));
  return {
    ...body,
    result: {
      ...body.result,
      tools: [...body.result.tools, ...additions],
    },
  };
}

function callPaddleTool(request, name, args) {
  if (name === 'crownthrive_paddle_route') return routePaddleOperation(args);
  if (name === 'crownthrive_paddle_integration_status') return paddleIntegrationStatus();
  if (name === 'crownthrive_paddle_preflight') {
    requireControlAuthorization(request);
    return preflightPaddleOperation(args);
  }
  throw Object.assign(new Error(`Unknown Paddle tool: ${name}`), { statusCode: 404, code: 'UNKNOWN_TOOL' });
}

export default async function handler(request, response) {
  if (request.method === 'GET') {
    const captured = captureResponse();
    await legacyMcpHandler(request, captured);
    return flushCaptured(captured, response, augmentDescriptor);
  }

  if (request.method !== 'POST') {
    return legacyMcpHandler(request, response);
  }

  let rpcRequest;
  try {
    rpcRequest = parseRpcRequest(request);
  } catch {
    return legacyMcpHandler(request, response);
  }

  if (rpcRequest.method === 'tools/list') {
    const captured = captureResponse();
    await legacyMcpHandler(request, captured);
    return flushCaptured(captured, response, augmentToolList);
  }

  const toolName = rpcRequest?.params?.name;
  if (rpcRequest.method !== 'tools/call' || !PADDLE_TOOL_NAMES.has(toolName)) {
    return legacyMcpHandler(request, response);
  }

  try {
    validateBridgeOrigin(request);
    const context = protocolContext(request, rpcRequest);
    validateModernEnvelope(request, rpcRequest, context);
    const payload = callPaddleTool(request, toolName, rpcRequest?.params?.arguments || {});
    return sendJson(response, 200, completeToolResult(rpcRequest.id ?? null, payload, context.modern));
  } catch (error) {
    const normalized = normalizeChlomBridgeError(error);
    return sendJson(
      response,
      normalized.statusCode,
      {
        jsonrpc: '2.0',
        id: rpcRequest?.id ?? null,
        error: {
          code: normalized.statusCode === 401 ? -32001 : normalized.statusCode === 403 ? -32003 : -32000,
          message: normalized.code,
          data: buildErrorData(request, error, normalized),
        },
      },
      normalized.statusCode === 401 ? { 'WWW-Authenticate': 'Bearer realm="CrownThrive OS MCP"' } : {},
    );
  }
}
