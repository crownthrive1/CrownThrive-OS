import {
  collectVercelFabric,
  PROJECT_BINDINGS,
} from '../lib/vercel-fabric.js';
import {
  hasVercelOidcToken,
  requestHeader,
  requestQueryParam,
} from '../lib/vercel-oidc.js';
import {
  callChlomBridge,
  chlomBridgeState,
  fetchChlomHealth,
  normalizeChlomBridgeError,
  requireControlAuthorization,
  validateBridgeOrigin,
} from '../lib/chlom-fabric.js';

const MODERN_VERSION = '2026-07-28';
const LEGACY_VERSIONS = new Set([
  '2025-11-25',
  '2025-06-18',
  '2025-03-26',
]);
const SUPPORTED_VERSIONS = [MODERN_VERSION, ...LEGACY_VERSIONS];
const MCP_ERROR = Object.freeze({
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  HEADER_MISMATCH: -32020,
  MISSING_REQUIRED_CLIENT_CAPABILITY: -32021,
  UNSUPPORTED_PROTOCOL_VERSION: -32022,
  AUTHORIZATION_FAILED: -32030,
});
const CONTROL_PLANE_CANONICAL_ORIGIN = 'https://crown-thrive-os.vercel.app';
const CONTROL_PLANE_CANONICAL_HOST = 'crown-thrive-os.vercel.app';
const CONTROL_PLANE_DEPLOYMENT_HOST =
  /^crown-thrive-os-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.vercel\.app$/;
const SERVER_INFO = Object.freeze({
  name: 'crownthrive-vercel-fabric',
  title: 'CrownThrive Vercel + CHLOM Fabric',
  version: '1.1.0',
  description:
    'Read-only CrownThrive Vercel, PentaFabric, and governed CHLOM chain-evidence control surface.',
  websiteUrl: CONTROL_PLANE_CANONICAL_ORIGIN,
});

const READ_ONLY_TOOL = Object.freeze({
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false,
});

const TOOLS = Object.freeze([
  {
    name: 'get_vercel_fabric_health',
    title: 'Get Vercel Fabric Health',
    description:
      'Returns provider-verified health for the CrownThrive OS, PentaOS, PentaExecution, and CHLOM Vercel production planes.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: READ_ONLY_TOOL,
  },
  {
    name: 'get_crownthrive_control_plane_health',
    title: 'Get CrownThrive Control Plane Health',
    description:
      'Returns the public-safe provider state of the CrownThrive OS control-plane Vercel project.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: READ_ONLY_TOOL,
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
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: READ_ONLY_TOOL,
  },
  {
    name: 'run_pentafabric_self_test',
    title: 'Run PentaFabric Self-Test',
    description:
      'Runs the read-only PentaFabric packet integrity self-test and returns its provider response.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: READ_ONLY_TOOL,
  },
  {
    name: 'get_chlom_chain_evidence_health',
    title: 'Get CHLOM Chain Evidence Health',
    description:
      'Reads the canonical CHLOM Chain Evidence Fabric health endpoint and preserves provider build and readiness evidence.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: { ...READ_ONLY_TOOL, openWorldHint: true },
  },
  {
    name: 'get_chlom_bridge_contract',
    title: 'Get CHLOM Bridge Contract',
    description:
      'Returns the non-secret CrownThrive OS to CHLOM bridge configuration and authority boundaries.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: READ_ONLY_TOOL,
  },
  {
    name: 'run_chlom_chain_read',
    title: 'Run Governed CHLOM Chain Read',
    description:
      'Runs one allowlisted read-only JSON-RPC request through the canonical CHLOM runtime. Requires the CrownThrive internal control token.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['chain', 'method'],
      properties: {
        chain: {
          type: 'string',
          enum: ['base', 'base-sepolia', 'ethereum', 'arbitrum', 'avalanche', 'cronos', 'fantom', 'optimism', 'polygon'],
        },
        method: { type: 'string', minLength: 1, maxLength: 128 },
        params: { type: 'array', maxItems: 64, default: [] },
      },
    },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: { ...READ_ONLY_TOOL, openWorldHint: true },
  },
  {
    name: 'run_chlom_blockchain_analytics',
    title: 'Run CHLOM Google Blockchain Analytics',
    description:
      'Runs one bounded Google Blockchain Analytics query template through CHLOM. Requires the CrownThrive internal control token.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['chain', 'template'],
      properties: {
        chain: {
          type: 'string',
          enum: ['ethereum', 'arbitrum', 'avalanche', 'cronos', 'fantom', 'optimism', 'polygon', 'tron'],
        },
        template: {
          type: 'string',
          enum: ['latest_block', 'transaction_evidence', 'address_activity', 'contract_logs'],
        },
        transactionHash: { type: 'string', maxLength: 132 },
        address: { type: 'string', maxLength: 132 },
        lookbackDays: { type: 'integer', minimum: 1, maximum: 31, default: 7 },
        limit: { type: 'integer', minimum: 1, maximum: 250, default: 50 },
      },
    },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: { ...READ_ONLY_TOOL, openWorldHint: true },
  },
  {
    name: 'prepare_chlom_evidence_anchor',
    title: 'Prepare CHLOM Evidence Anchor',
    description:
      'Creates a deterministic non-broadcast anchor intent through CHLOM. Requires the CrownThrive internal control token.',
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['evidenceDigest', 'targetChain'],
      properties: {
        evidenceDigest: { type: 'string', pattern: '^[0-9a-f]{64}$' },
        targetChain: { type: 'string', enum: ['base', 'base-sepolia', 'ethereum'] },
      },
    },
    outputSchema: { type: 'object', additionalProperties: true },
    annotations: READ_ONLY_TOOL,
  },
]);

const PROTECTED_TOOLS = new Set([
  'run_chlom_chain_read',
  'run_chlom_blockchain_analytics',
  'prepare_chlom_evidence_anchor',
]);

function setCommonHeaders(request, response) {
  response.setHeader('Cache-Control', 'no-store, max-age=0');
  response.setHeader('Content-Type', 'application/json; charset=utf-8');
  const origin = requestHeader(request, 'origin');
  if (origin) response.setHeader('Access-Control-Allow-Origin', origin);
  response.setHeader('Vary', 'Origin');
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

function sendJson(request, response, status, payload) {
  setCommonHeaders(request, response);
  return response.status(status).json(payload);
}

function rpcResult(id, result, modern = false) {
  const normalized = modern
    ? { ...result, resultType: result.resultType || 'complete' }
    : result;
  return { jsonrpc: '2.0', id, result: normalized };
}

function rpcError(id, code, message, data) {
  return {
    jsonrpc: '2.0',
    id: id ?? null,
    error: { code, message, ...(data === undefined ? {} : { data }) },
  };
}

function parseBody(request) {
  const length = Number(requestHeader(request, 'content-length') || 0);
  if (Number.isFinite(length) && length > 131072) {
    throw new Error('MCP request exceeds the governed payload limit.');
  }
  if (request.body && typeof request.body === 'object' && !Buffer.isBuffer(request.body)) {
    return request.body;
  }
  if (Buffer.isBuffer(request.body)) return JSON.parse(request.body.toString('utf8'));
  if (typeof request.body === 'string' && request.body.trim()) return JSON.parse(request.body);
  return null;
}

function decodeMirroredHeader(value) {
  if (typeof value !== 'string') return value;
  const match = value.match(/^=\?base64\?([A-Za-z0-9+/=]+)\?=$/);
  if (!match) return value;
  return Buffer.from(match[1], 'base64').toString('utf8');
}

function requestProtocol(body) {
  return body?.params?._meta?.['io.modelcontextprotocol/protocolVersion'];
}

function validateModernMetadata(request, body) {
  const protocol = requestProtocol(body);
  const protocolHeader = requestHeader(request, 'mcp-protocol-version');
  const methodHeader = decodeMirroredHeader(requestHeader(request, 'mcp-method'));
  if (!protocolHeader || !methodHeader || protocolHeader !== protocol || methodHeader !== body.method) {
    const error = new Error('MCP routing headers must exactly match request metadata and method.');
    error.mcpCode = MCP_ERROR.HEADER_MISMATCH;
    error.status = 400;
    throw error;
  }
  if (body.method === 'tools/call') {
    const nameHeader = decodeMirroredHeader(requestHeader(request, 'mcp-name'));
    if (!nameHeader || nameHeader !== body.params?.name) {
      const error = new Error('Mcp-Name must exactly match params.name.');
      error.mcpCode = MCP_ERROR.HEADER_MISMATCH;
      error.status = 400;
      throw error;
    }
  }
  const clientInfo = body?.params?._meta?.['io.modelcontextprotocol/clientInfo'];
  if (
    !clientInfo ||
    typeof clientInfo !== 'object' ||
    Array.isArray(clientInfo) ||
    typeof clientInfo.name !== 'string' ||
    typeof clientInfo.version !== 'string'
  ) {
    const error = new Error('Modern MCP requests require clientInfo name and version.');
    error.mcpCode = MCP_ERROR.INVALID_PARAMS;
    error.status = 400;
    throw error;
  }
  const capabilities = body?.params?._meta?.['io.modelcontextprotocol/clientCapabilities'];
  if (!capabilities || typeof capabilities !== 'object' || Array.isArray(capabilities)) {
    const error = new Error('Modern MCP requests require clientCapabilities.');
    error.mcpCode = MCP_ERROR.MISSING_REQUIRED_CLIENT_CAPABILITY;
    error.status = 400;
    throw error;
  }
}

function classifyProtocol(request, body) {
  if (body.method === 'initialize') return 'legacy';
  const protocol = requestProtocol(body);
  if (!protocol) {
    const header = requestHeader(request, 'mcp-protocol-version');
    if (LEGACY_VERSIONS.has(header)) return 'legacy';
    const error = new Error('Non-initialize requests require an explicit supported protocol version.');
    error.mcpCode = MCP_ERROR.UNSUPPORTED_PROTOCOL_VERSION;
    error.status = 400;
    throw error;
  }
  if (!SUPPORTED_VERSIONS.includes(protocol)) {
    const error = new Error(`Unsupported MCP protocol version: ${protocol}`);
    error.mcpCode = MCP_ERROR.UNSUPPORTED_PROTOCOL_VERSION;
    error.status = 400;
    throw error;
  }
  if (protocol === MODERN_VERSION) {
    validateModernMetadata(request, body);
    return 'modern';
  }
  const header = requestHeader(request, 'mcp-protocol-version');
  if (header && header !== protocol) {
    const error = new Error('MCP-Protocol-Version does not match request metadata.');
    error.mcpCode = MCP_ERROR.HEADER_MISMATCH;
    error.status = 400;
    throw error;
  }
  return 'legacy';
}

function controlPlaneOrigin({ exactDeploymentRequired = false } = {}) {
  const deploymentHost = String(process.env.VERCEL_URL || '').trim().toLowerCase();
  if (!deploymentHost || deploymentHost === CONTROL_PLANE_CANONICAL_HOST) {
    if (exactDeploymentRequired) {
      throw new Error('MCP exact deployment callback requires a generated VERCEL_URL host.');
    }
    return CONTROL_PLANE_CANONICAL_ORIGIN;
  }
  if (!CONTROL_PLANE_DEPLOYMENT_HOST.test(deploymentHost)) {
    throw new Error('MCP candidate callback host is not an approved CrownThrive Vercel deployment.');
  }
  return `https://${deploymentHost}`;
}

function controlPlaneUrl(path, options = {}) {
  const origin = controlPlaneOrigin(options);
  const url = new URL(path, `${origin}/`);
  if (url.origin !== origin || url.username || url.password) {
    throw new Error('MCP internal callback URL must remain on the current control-plane deployment origin.');
  }
  return url.toString();
}

async function fetchJson(url, options = {}, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        Accept: 'application/json',
        'User-Agent': 'CrownThrive-MCP/1.1',
        ...(options.headers || {}),
      },
      cache: 'no-store',
      redirect: 'error',
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

function fabricOptions(request) {
  return { oidcTokenPresent: hasVercelOidcToken(request) };
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
    return toolResponse(await collectVercelFabric(fabricOptions(request)), modern);
  }
  if (name === 'get_crownthrive_control_plane_health') {
    const fabric = await collectVercelFabric(fabricOptions(request));
    const project = fabric.projects.find(
      (entry) => entry.project_id === 'prj_x6AcQaYdt6lkuyoWkdzv9TSL9lAN',
    );
    return toolResponse({
      schema: 'ct.penta.mcp.control-plane-health.v1',
      fabric_status: fabric.status,
      project,
      evidence: fabric.evidence,
      observed_at: fabric.observed_at,
    }, modern);
  }
  if (name === 'get_vercel_project_binding') {
    const binding = PROJECT_BINDINGS.find((project) => project.project_id === args?.project_id);
    if (!binding) throw new Error('Unknown or unauthorized Vercel project ID.');
    return toolResponse({
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
    }, modern);
  }
  if (name === 'run_pentafabric_self_test') {
    return toolResponse(await fetchJson(controlPlaneUrl('/api/penta?selftest=1')), modern);
  }
  if (name === 'get_chlom_chain_evidence_health') {
    return toolResponse(await fetchChlomHealth(), modern);
  }
  if (name === 'get_chlom_bridge_contract') {
    return toolResponse(chlomBridgeState(), modern);
  }
  if (PROTECTED_TOOLS.has(name)) requireControlAuthorization(request);
  if (name === 'run_chlom_chain_read') {
    return toolResponse(await callChlomBridge('rpc_read', args), modern);
  }
  if (name === 'run_chlom_blockchain_analytics') {
    return toolResponse(await callChlomBridge('analytics', args), modern);
  }
  if (name === 'prepare_chlom_evidence_anchor') {
    return toolResponse(await callChlomBridge('attest', args), modern);
  }
  throw new Error(`Unknown tool: ${name}`);
}

function modernMeta() {
  return {
    'io.modelcontextprotocol/protocolVersion': MODERN_VERSION,
    'io.modelcontextprotocol/clientInfo': { name: 'CrownThrive-MCP-SelfTest', version: '1.1.0' },
    'io.modelcontextprotocol/clientCapabilities': {},
  };
}

async function postSelfTestRpc(method, id) {
  return fetchJson(controlPlaneUrl('/api/mcp', { exactDeploymentRequired: true }), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': MODERN_VERSION,
      'Mcp-Method': method,
    },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id,
      method,
      params: { _meta: modernMeta() },
    }),
  });
}

async function runGatewaySelfTest() {
  const callbackOrigin = controlPlaneOrigin({ exactDeploymentRequired: true });
  const exactDeploymentOrigin = CONTROL_PLANE_DEPLOYMENT_HOST.test(
    new URL(callbackOrigin).hostname,
  );
  if (!exactDeploymentOrigin) {
    throw new Error('MCP callback did not bind to an exact generated deployment origin.');
  }
  const discover = await postSelfTestRpc('server/discover', 'pentavercel-discover');
  const tools = await postSelfTestRpc('tools/list', 'pentavercel-tools');
  const returnedTools = tools?.result?.tools || [];
  const returnedNames = returnedTools.map((tool) => tool?.name).sort();
  const expectedNames = TOOLS.map((tool) => tool.name).sort();
  const discoveredServerInfo =
    discover?.result?._meta?.['io.modelcontextprotocol/serverInfo'];
  const failures = [];
  const discoveredVersions = [...(discover?.result?.supportedVersions || [])].sort();
  const expectedVersions = [...SUPPORTED_VERSIONS].sort();
  if (JSON.stringify(discoveredVersions) !== JSON.stringify(expectedVersions)) {
    failures.push('discovered protocol versions did not exactly match the local catalog');
  }
  if (
    discoveredServerInfo?.name !== SERVER_INFO.name ||
    discoveredServerInfo?.version !== SERVER_INFO.version
  ) {
    failures.push('discovered server identity did not exactly match the local server');
  }
  if (returnedTools.length !== TOOLS.length) {
    failures.push(`tool count ${returnedTools.length} does not equal ${TOOLS.length}`);
  }
  if (JSON.stringify(returnedNames) !== JSON.stringify(expectedNames)) {
    failures.push('returned tool names did not exactly match the local catalog');
  }
  if (returnedTools.some((tool) => tool?.annotations?.readOnlyHint !== true || tool?.annotations?.destructiveHint !== false)) {
    failures.push('one or more tools violated the read-only contract');
  }
  if (returnedTools.some((tool) => /broadcast|private_key|send_raw/i.test(tool.name))) {
    failures.push('a prohibited broadcast or private-key tool was exposed');
  }
  if (failures.length) throw new Error(failures.join('; '));
  return {
    status: 'PASS',
    protocol_version: MODERN_VERSION,
    server_name: SERVER_INFO.name,
    server_version: SERVER_INFO.version,
    tool_count: returnedTools.length,
    protected_tool_count: PROTECTED_TOOLS.size,
    write_tools: 0,
    read_only: true,
    callback_origin: callbackOrigin,
    callback_build_sha: process.env.VERCEL_GIT_COMMIT_SHA || null,
    callback_deployment_id: process.env.VERCEL_DEPLOYMENT_ID || null,
    exact_deployment_origin: exactDeploymentOrigin,
    pass_manufactured: false,
  };
}

function descriptor(selfTest = null) {
  return {
    schema: 'ct.crownthrive.mcp.gateway.20260827.v2',
    service: SERVER_INFO.name,
    status: 'OPERATIONAL',
    endpoint: '/api/mcp',
    transport: 'streamable_http_stateless',
    supported_versions: SUPPORTED_VERSIONS,
    modern_profile: 'mcp-2026-07-28-stateless',
    tools: TOOLS.map((tool) => tool.name),
    protected_tools: [...PROTECTED_TOOLS],
    write_tools: 0,
    authorization: {
      public: 'provider_health_and_contract_metadata',
      protected: 'CROWNTHRIVE_CONTROL_TOKEN',
    },
    chlom_bridge: chlomBridgeState(),
    pass_manufactured: false,
    ...(selfTest ? { self_test: selfTest } : {}),
  };
}

function exceptionResponse(error, id) {
  const normalized = normalizeChlomBridgeError(error);
  const code = error?.mcpCode ||
    (normalized.status === 401 || normalized.status === 403 || normalized.status === 503
      ? MCP_ERROR.AUTHORIZATION_FAILED
      : normalized.status === 400
        ? MCP_ERROR.INVALID_PARAMS
        : MCP_ERROR.INTERNAL_ERROR);
  return {
    status: error?.status || normalized.status || 500,
    payload: rpcError(id, code, normalized.message, {
      chlomCode: normalized.code,
      supportedVersions:
        code === MCP_ERROR.UNSUPPORTED_PROTOCOL_VERSION ? SUPPORTED_VERSIONS : undefined,
    }),
  };
}

export default async function handler(request, response) {
  try {
    validateBridgeOrigin(request);
  } catch (error) {
    const result = exceptionResponse(error, null);
    return sendJson(request, response, result.status, result.payload);
  }

  if (request.method === 'OPTIONS') {
    setCommonHeaders(request, response);
    return response.status(204).end();
  }

  if (request.method === 'GET') {
    const selfTestRequested = requestQueryParam(request, 'selftest') === '1';
    if (!selfTestRequested) return sendJson(request, response, 200, descriptor());
    try {
      return sendJson(request, response, 200, descriptor(await runGatewaySelfTest()));
    } catch (error) {
      return sendJson(request, response, 503, {
        ...descriptor(),
        status: 'DEGRADED',
        self_test: {
          status: 'HOLD',
          error: String(error?.message || error).slice(0, 300),
          exact_deployment_origin: false,
          pass_manufactured: false,
        },
      });
    }
  }

  if (request.method !== 'POST') {
    setCommonHeaders(request, response);
    response.setHeader('Allow', 'GET, POST, OPTIONS');
    return response.status(405).json(rpcError(null, MCP_ERROR.INVALID_REQUEST, 'Method not allowed'));
  }

  let body;
  try {
    body = parseBody(request);
  } catch {
    return sendJson(request, response, 400, rpcError(null, MCP_ERROR.PARSE_ERROR, 'Parse error'));
  }
  if (!body || body.jsonrpc !== '2.0' || typeof body.method !== 'string') {
    return sendJson(request, response, 400, rpcError(body?.id, MCP_ERROR.INVALID_REQUEST, 'Invalid Request'));
  }

  let era;
  try {
    era = classifyProtocol(request, body);
  } catch (error) {
    const result = exceptionResponse(error, body.id);
    return sendJson(request, response, result.status, result.payload);
  }
  const modern = era === 'modern';

  if (body.method === 'initialize') {
    const requested = body.params?.protocolVersion;
    const selected = SUPPORTED_VERSIONS.includes(requested) ? requested : '2025-11-25';
    return sendJson(request, response, 200, rpcResult(body.id, {
      protocolVersion: selected,
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
      instructions:
        'CrownThrive Vercel and CHLOM evidence tools are read-only. Protected CHLOM calls require the internal control token. No private-key or broadcast tool exists.',
    }));
  }
  if (body.method === 'notifications/initialized') {
    setCommonHeaders(request, response);
    return response.status(202).end();
  }
  if (body.method === 'server/discover') {
    if (!modern) {
      return sendJson(request, response, 404, rpcError(body.id, MCP_ERROR.METHOD_NOT_FOUND, 'Method not found'));
    }
    return sendJson(request, response, 200, rpcResult(body.id, {
      supportedVersions: SUPPORTED_VERSIONS,
      capabilities: { tools: {} },
      instructions:
        'Use CrownThrive tools for provider, PentaFabric, and CHLOM read-only evidence. Arbitrary URLs, arbitrary SQL, private keys, deployment writes, and chain broadcast are not exposed.',
      _meta: { 'io.modelcontextprotocol/serverInfo': SERVER_INFO },
      ttlMs: 60000,
      cacheScope: 'private',
      resultType: 'complete',
    }, true));
  }
  if (body.method === 'ping') {
    return sendJson(request, response, 200, rpcResult(body.id, modern ? { resultType: 'complete' } : {}, modern));
  }
  if (body.method === 'tools/list') {
    return sendJson(request, response, 200, rpcResult(body.id, {
      tools: TOOLS,
      ...(modern ? { ttlMs: 60000, cacheScope: 'private', resultType: 'complete' } : {}),
    }, modern));
  }
  if (body.method === 'tools/call') {
    const name = body.params?.name;
    if (typeof name !== 'string') {
      return sendJson(request, response, 400, rpcError(body.id, MCP_ERROR.INVALID_PARAMS, 'Missing tool name'));
    }
    try {
      return sendJson(request, response, 200, rpcResult(body.id, await callTool(
        name,
        body.params?.arguments || {},
        request,
        modern,
      ), modern));
    } catch (error) {
      const normalized = normalizeChlomBridgeError(error);
      const result = {
        content: [{
          type: 'text',
          text: JSON.stringify({
            status: 'HOLD',
            error: normalized.message.slice(0, 300),
            code: normalized.code,
            pass_manufactured: false,
          }),
        }],
        structuredContent: {
          status: 'HOLD',
          error: { code: normalized.code, message: normalized.message.slice(0, 300) },
          pass_manufactured: false,
        },
        isError: true,
        ...(modern ? { resultType: 'complete' } : {}),
      };
      return sendJson(request, response, 200, rpcResult(body.id, result, modern));
    }
  }

  return sendJson(
    request,
    response,
    modern ? 404 : 200,
    rpcError(body.id, MCP_ERROR.METHOD_NOT_FOUND, 'Method not found'),
  );
}
