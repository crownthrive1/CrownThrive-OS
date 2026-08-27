import { collectVercelFabric, PROJECT_BINDINGS } from '../lib/vercel-fabric.js';

const MODERN_VERSION = '2026-07-28';
const LEGACY_VERSIONS = new Set(['2025-06-18', '2025-03-26']);
const SERVER_INFO = Object.freeze({
  name: 'crownthrive-vercel-fabric',
  title: 'CrownThrive Vercel Fabric',
  version: '1.0.0',
});

const TOOLS = Object.freeze([
  {
    name: 'get_vercel_fabric_health',
    title: 'Get Vercel Fabric Health',
    description:
      'Returns provider-verified health for the CrownThrive OS, PentaOS, PentaExecution, and CHLOM Vercel production planes.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {},
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  {
    name: 'get_crownthrive_control_plane_health',
    title: 'Get CrownThrive Control Plane Health',
    description:
      'Returns the public-safe provider state of the CrownThrive OS control-plane Vercel project.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {},
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  {
    name: 'get_vercel_project_binding',
    title: 'Get Vercel Project Binding',
    description:
      'Returns a non-secret CrownThrive Vercel project binding by project ID.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['project_id'],
      properties: {
        project_id: {
          type: 'string',
          enum: PROJECT_BINDINGS.map((project) => project.project_id),
        },
      },
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
  {
    name: 'run_pentafabric_self_test',
    title: 'Run PentaFabric Self-Test',
    description:
      'Runs the read-only PentaFabric packet integrity self-test and returns its provider response.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {},
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
]);

function header(request, name) {
  const value = request.headers?.[name.toLowerCase()];
  return Array.isArray(value) ? value[0] : value || null;
}

function setCommonHeaders(response) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  response.setHeader(
    'Access-Control-Allow-Headers',
    'Content-Type, Accept, Authorization, MCP-Protocol-Version, Mcp-Method, Mcp-Name, Traceparent, Tracestate, Baggage',
  );
  response.setHeader('Access-Control-Expose-Headers', 'MCP-Protocol-Version');
  response.setHeader('MCP-Protocol-Version', MODERN_VERSION);
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'DENY');
  response.setHeader('Referrer-Policy', 'no-referrer');
}

function sendJson(response, status, payload) {
  setCommonHeaders(response);
  return response.status(status).json(payload);
}

function rpcResult(id, result, modern = false) {
  return {
    jsonrpc: '2.0',
    id,
    result: modern ? { ...result, resultType: result.resultType || 'complete' } : result,
  };
}

function rpcError(id, code, message, data) {
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

function parseBody(request) {
  if (request.body && typeof request.body === 'object') return request.body;
  if (typeof request.body === 'string' && request.body.trim()) return JSON.parse(request.body);
  return null;
}

function requestVersion(request, body) {
  return (
    header(request, 'mcp-protocol-version') ||
    body?.params?._meta?.['io.modelcontextprotocol/protocolVersion'] ||
    body?.params?.protocolVersion ||
    null
  );
}

function baseUrl(request) {
  const protocol = header(request, 'x-forwarded-proto') || 'https';
  const host = header(request, 'x-forwarded-host') || header(request, 'host');
  return `${protocol}://${host}`;
}

async function fetchJson(url, timeoutMs = 4000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      headers: { Accept: 'application/json', 'User-Agent': 'CrownThrive-MCP/1.0' },
      cache: 'no-store',
      signal: controller.signal,
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(`upstream ${response.status}: ${JSON.stringify(body).slice(0, 180)}`);
    }
    return body;
  } finally {
    clearTimeout(timer);
  }
}

function toolResponse(payload, modern) {
  const result = {
    content: [{ type: 'text', text: JSON.stringify(payload) }],
    structuredContent: payload,
    isError: false,
  };
  return modern ? { ...result, resultType: 'complete' } : result;
}

async function callTool(name, args, request, modern) {
  if (name === 'get_vercel_fabric_health') {
    return toolResponse(await collectVercelFabric(), modern);
  }

  if (name === 'get_crownthrive_control_plane_health') {
    const fabric = await collectVercelFabric();
    const controlPlane = fabric.projects.find(
      (project) => project.project_id === 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
    );
    return toolResponse(
      {
        schema: 'ct.penta.mcp.control-plane-health.v1',
        fabric_status: fabric.status,
        project: controlPlane,
        evidence: fabric.evidence,
        observed_at: fabric.observed_at,
      },
      modern,
    );
  }

  if (name === 'get_vercel_project_binding') {
    const projectId = args?.project_id;
    const binding = PROJECT_BINDINGS.find((project) => project.project_id === projectId);
    if (!binding) throw new Error('Unknown or unauthorized Vercel project ID.');
    return toolResponse(
      {
        schema: 'ct.penta.mcp.vercel-project-binding.v1',
        binding: {
          key: binding.key,
          service: binding.service,
          project_id: binding.project_id,
          repository: binding.repository,
          visibility: binding.visibility,
          required: binding.required,
          lanes: binding.lanes,
          contains_secret_material: false,
        },
      },
      modern,
    );
  }

  if (name === 'run_pentafabric_self_test') {
    return toolResponse(await fetchJson(`${baseUrl(request)}/api/penta?selftest=1`), modern);
  }

  throw new Error(`Unknown tool: ${name}`);
}

export default async function handler(request, response) {
  if (request.method === 'OPTIONS') {
    setCommonHeaders(response);
    return response.status(204).end();
  }

  if (request.method === 'GET') {
    return sendJson(response, 200, {
      schema: 'ct.crownthrive.mcp.gateway.20260827.v1',
      service: SERVER_INFO.name,
      status: 'OPERATIONAL',
      endpoint: '/api/mcp',
      transport: 'streamable_http_stateless',
      supported_versions: [MODERN_VERSION, ...LEGACY_VERSIONS],
      modern_profile: 'read_only_stateless_subset',
      tools: TOOLS.map((tool) => tool.name),
      write_tools: 0,
      authorization: 'public_safe_read_only_metadata',
      pass_manufactured: false,
    });
  }

  if (request.method !== 'POST') {
    setCommonHeaders(response);
    response.setHeader('Allow', 'GET, POST, OPTIONS');
    return response.status(405).json(rpcError(null, -32600, 'Method not allowed'));
  }

  let body;
  try {
    body = parseBody(request);
  } catch {
    return sendJson(response, 400, rpcError(null, -32700, 'Parse error'));
  }

  if (!body || body.jsonrpc !== '2.0' || typeof body.method !== 'string') {
    return sendJson(response, 400, rpcError(body?.id, -32600, 'Invalid Request'));
  }

  const version = requestVersion(request, body);
  const modern = version === MODERN_VERSION || body.method === 'server/discover';
  const legacy = LEGACY_VERSIONS.has(version) || body.method === 'initialize';

  if (!modern && !legacy) {
    return sendJson(
      response,
      400,
      rpcError(body.id, -32602, 'Unsupported MCP protocol version', {
        supportedVersions: [MODERN_VERSION, ...LEGACY_VERSIONS],
      }),
    );
  }

  if (modern) {
    const methodHeader = header(request, 'mcp-method');
    if (!methodHeader || methodHeader !== body.method) {
      return sendJson(
        response,
        400,
        rpcError(body.id, -32600, 'Mcp-Method header must match the JSON-RPC method'),
      );
    }
    if (body.method === 'tools/call') {
      const nameHeader = header(request, 'mcp-name');
      if (!nameHeader || nameHeader !== body.params?.name) {
        return sendJson(
          response,
          400,
          rpcError(body.id, -32600, 'Mcp-Name header must match params.name'),
        );
      }
    }
  }

  if (body.method === 'server/discover') {
    return sendJson(
      response,
      200,
      rpcResult(
        body.id,
        {
          supportedVersions: [MODERN_VERSION],
          capabilities: { tools: { listChanged: false } },
          instructions:
            'Read-only CrownThrive Vercel fabric and Penta provider evidence. No deployment, domain, environment, payment, credential, or rollback writes are exposed.',
          _meta: { 'io.modelcontextprotocol/serverInfo': SERVER_INFO },
          ttlMs: 60000,
          cacheScope: 'public',
          resultType: 'complete',
        },
        true,
      ),
    );
  }

  if (body.method === 'initialize') {
    const requested = body.params?.protocolVersion;
    const protocolVersion = LEGACY_VERSIONS.has(requested) ? requested : '2025-06-18';
    return sendJson(
      response,
      200,
      rpcResult(body.id, {
        protocolVersion,
        capabilities: { tools: { listChanged: false } },
        serverInfo: SERVER_INFO,
        instructions:
          'Read-only CrownThrive Vercel fabric and Penta provider evidence. Write operations are intentionally unavailable.',
      }),
    );
  }

  if (body.method === 'notifications/initialized') {
    setCommonHeaders(response);
    return response.status(202).end();
  }

  if (body.method === 'ping' && legacy) {
    return sendJson(response, 200, rpcResult(body.id, {}));
  }

  if (body.method === 'tools/list') {
    const result = {
      tools: TOOLS,
      ...(modern
        ? { ttlMs: 60000, cacheScope: 'public', resultType: 'complete' }
        : {}),
    };
    return sendJson(response, 200, rpcResult(body.id, result, modern));
  }

  if (body.method === 'tools/call') {
    const name = body.params?.name;
    const args = body.params?.arguments || {};
    if (typeof name !== 'string') {
      return sendJson(response, 400, rpcError(body.id, -32602, 'Missing tool name'));
    }
    try {
      return sendJson(response, 200, rpcResult(body.id, await callTool(name, args, request, modern), modern));
    } catch (error) {
      const result = {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              status: 'HOLD',
              error: String(error?.message || error).slice(0, 300),
              pass_manufactured: false,
            }),
          },
        ],
        isError: true,
        ...(modern ? { resultType: 'complete' } : {}),
      };
      return sendJson(response, 200, rpcResult(body.id, result, modern));
    }
  }

  return sendJson(response, 404, rpcError(body.id, -32601, 'Method not found'));
}
