import {
  MCP_PROTOCOL_VERSION,
  SERVER_INFO,
  TOOL_BY_NAME,
  HTTP_ROUTE_TO_TOOL,
  jsonRpcError,
  jsonRpcResult,
  validateMcpEnvelope,
  discoverResult,
  toolsListResult,
  normalizeToolArguments
} from './contract.mjs';

const encoder = new TextEncoder();

type JsonRecord = Record<string, unknown>;
type ReceiptInput = {
  transport: 'HTTP' | 'MCP';
  method: string;
  toolName: string | null;
  requestBody: unknown;
  responseBody: unknown;
  disposition: 'ECAC' | 'HOLD' | 'DENY';
};

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function json(body: unknown, status = 200, extraHeaders: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      ...extraHeaders
    }
  });
}

async function sha256Hex(value: unknown): Promise<string> {
  const bytes = encoder.encode(typeof value === 'string' ? value : JSON.stringify(value));
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return [...digest].map(b => b.toString(16).padStart(2, '0')).join('');
}

function timingSafeEqualText(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function isServiceRoleRequest(req: Request, serviceRoleKey: string): boolean {
  const auth = req.headers.get('authorization') ?? '';
  const bearer = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : '';
  const apiKey = req.headers.get('apikey') ?? '';
  return timingSafeEqualText(bearer, serviceRoleKey) || timingSafeEqualText(apiKey, serviceRoleKey);
}

function normalizedPath(req: Request): string {
  const url = new URL(req.url);
  const marker = '/chlom-wallet-continuity';
  const idx = url.pathname.lastIndexOf(marker);
  const suffix = idx >= 0 ? url.pathname.slice(idx + marker.length) : url.pathname;
  return suffix || '/';
}

async function rpc(name: string, args: JsonRecord = {}): Promise<any> {
  const supabaseUrl = Deno.env.get('SUPABASE_URL');
  const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');
  if (!supabaseUrl || !serviceRoleKey) throw new Error('runtime_environment_missing');
  const response = await fetch(`${supabaseUrl}/rest/v1/rpc/${name}`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'apikey': serviceRoleKey,
      'authorization': `Bearer ${serviceRoleKey}`,
      'x-client-info': 'chlom-wallet-continuity-edge/1.0.0'
    },
    body: JSON.stringify(args)
  });
  const text = await response.text();
  let body: unknown;
  try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
  if (!response.ok) throw new Error(`rpc_failed:${name}:${response.status}`);
  return body;
}

function deriveTransportDisposition(result: any): 'ECAC' | 'HOLD' | 'DENY' {
  const candidates = [
    result?.disposition,
    result?.tick?.disposition,
    result?.latest_truth?.disposition,
    result?.status?.latest_truth?.disposition
  ];
  return candidates.find(v => ['ECAC', 'HOLD', 'DENY'].includes(v)) ?? 'ECAC';
}

async function recordReceipt(input: ReceiptInput): Promise<unknown> {
  const requestSha = await sha256Hex(input.requestBody ?? {});
  const responseSha = await sha256Hex(input.responseBody ?? {});
  return rpc('chlom_wallet_continuity_runtime_record_request_v1', {
    p_transport: input.transport,
    p_method: input.method,
    p_tool_name: input.toolName,
    p_request_sha256: requestSha,
    p_response_sha256: responseSha,
    p_disposition: input.disposition,
    p_protocol_version: input.transport === 'MCP' ? MCP_PROTOCOL_VERSION : 'HTTP/1.1'
  });
}

async function callTool(toolName: string, args: JsonRecord, transport: 'HTTP' | 'MCP', method: string, rawRequest: unknown): Promise<{ result: any; disposition: 'ECAC' | 'HOLD' | 'DENY' }> {
  const tool = TOOL_BY_NAME[toolName];
  if (!tool) throw new Error('unknown_tool');
  const rpcArgs = normalizeToolArguments(toolName, args ?? {});
  const result = await rpc(tool.rpc, rpcArgs);
  const disposition = deriveTransportDisposition(result);
  await recordReceipt({ transport, method, toolName, requestBody: rawRequest, responseBody: result, disposition });
  return { result, disposition };
}

async function handleHttpApi(req: Request, path: string): Promise<Response> {
  const key = `${req.method.toUpperCase()} ${path}`;
  const toolName = HTTP_ROUTE_TO_TOOL[key];
  if (!toolName) return json({ error: 'not_found' }, 404);

  let args: JsonRecord = {};
  if (req.method.toUpperCase() === 'GET') {
    const url = new URL(req.url);
    if (toolName === 'chlom_wallet_continuity_assets_v1') {
      const limitRaw = Number(url.searchParams.get('limit') ?? '100');
      const offsetRaw = Number(url.searchParams.get('offset') ?? '0');
      args = {
        limit: Number.isInteger(limitRaw) ? Math.min(Math.max(limitRaw, 1), 200) : 100,
        offset: Number.isInteger(offsetRaw) ? Math.max(offsetRaw, 0) : 0
      };
    }
  } else {
    try {
      const parsed = await req.json();
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return json({ error: 'invalid_json_object' }, 400);
      args = parsed as JsonRecord;
    } catch {
      return json({ error: 'invalid_json' }, 400);
    }
  }

  try {
    const { result, disposition } = await callTool(toolName, args, 'HTTP', key, { path, args });
    return json({
      api: 'ct.api.chlom-wallet.continuity.v1',
      state: 'CONTROLLED_TEST',
      tool: toolName,
      disposition,
      result,
      authority_granted: false,
      production_activation: false
    }, 200, { 'x-chlom-disposition': disposition });
  } catch (error) {
    return json({ error: 'continuity_api_failure', detail: errorMessage(error) }, 500);
  }
}

async function handleMcp(req: Request): Promise<Response> {
  let body: any;
  try { body = await req.json(); } catch { return json(jsonRpcError(null, -32700, 'Parse error'), 400); }

  const headers: Record<string, string> = {};
  for (const [k, v] of req.headers.entries()) headers[k.toLowerCase()] = v;
  const validation = validateMcpEnvelope(headers, body);
  if (!validation.ok) {
    return json(jsonRpcError(body?.id, validation.code, validation.message, validation.data), 400, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION });
  }

  try {
    if (body.method === 'server/discover') {
      const result = discoverResult();
      await recordReceipt({ transport: 'MCP', method: body.method, toolName: null, requestBody: body, responseBody: result, disposition: 'ECAC' });
      return json(jsonRpcResult(body.id, result), 200, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION });
    }

    if (body.method === 'tools/list') {
      const result = toolsListResult();
      await recordReceipt({ transport: 'MCP', method: body.method, toolName: null, requestBody: body, responseBody: result, disposition: 'ECAC' });
      return json(jsonRpcResult(body.id, result), 200, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION });
    }

    if (body.method === 'tools/call') {
      const toolName = body.params?.name;
      if (typeof toolName !== 'string' || !TOOL_BY_NAME[toolName]) return json(jsonRpcError(body.id, -32602, 'Unknown tool'), 400, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION });
      const toolArgs = body.params?.arguments && typeof body.params.arguments === 'object' && !Array.isArray(body.params.arguments)
        ? body.params.arguments as JsonRecord
        : {};
      const { result, disposition } = await callTool(toolName, toolArgs, 'MCP', body.method, body);
      const mcpResult = {
        content: [{ type: 'text', text: JSON.stringify(result) }],
        structuredContent: result,
        isError: false,
        _meta: { 'crownthrive/disposition': disposition }
      };
      return json(jsonRpcResult(body.id, mcpResult), 200, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION, 'x-chlom-disposition': disposition });
    }

    return json(jsonRpcError(body.id, -32601, 'Method not found'), 404, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION });
  } catch (error) {
    return json(jsonRpcError(body?.id, -32603, 'Internal error', { detail: errorMessage(error) }), 500, { 'MCP-Protocol-Version': MCP_PROTOCOL_VERSION });
  }
}

Deno.serve(async (req: Request): Promise<Response> => {
  const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
  if (!serviceRoleKey) return json({ error: 'runtime_environment_missing' }, 500);
  if (!isServiceRoleRequest(req, serviceRoleKey)) return json({ error: 'forbidden_service_role_required' }, 403);

  const path = normalizedPath(req);
  if (path === '/' || path === '/health') {
    const health = {
      service: SERVER_INFO,
      state: 'CONTROLLED_TEST',
      mcp_protocol: MCP_PROTOCOL_VERSION,
      authorization: 'SERVICE_ROLE_ONLY',
      provider_write: false,
      money_movement: false,
      rights_grant: false,
      chain_broadcast: false,
      destructive_recovery: false,
      checkout_enabled: false,
      production_activation: false,
      ai_final_authority: false
    };
    try {
      await recordReceipt({ transport: 'HTTP', method: 'GET /health', toolName: null, requestBody: { path }, responseBody: health, disposition: 'ECAC' });
    } catch (error) {
      return json({ error: 'health_receipt_failure', detail: errorMessage(error) }, 500);
    }
    return json(health);
  }

  if (path === '/mcp') {
    if (req.method.toUpperCase() !== 'POST') return json({ error: 'method_not_allowed' }, 405);
    return handleMcp(req);
  }

  if (path.startsWith('/api/')) return handleHttpApi(req, path);
  return json({ error: 'not_found' }, 404);
});
