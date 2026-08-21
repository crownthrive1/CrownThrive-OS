#!/usr/bin/env node
import http from 'node:http';
import { pathToFileURL } from 'node:url';

const HARD_MAX_REQUEST_BYTES = 262_144;
const HARD_MAX_RESPONSE_BYTES = 1_048_576;
const HARD_MAX_TIMEOUT_MS = 15_000;
const ALLOWED_OPERATIONS = new Set([
  'initialize',
  'notifications/initialized',
  'ping',
  'tools/list',
  'resources/list',
  'resources/templates/list',
  'prompts/list',
  'logging/setLevel'
]);
const BLOCKED_RESPONSE_HEADERS = new Set([
  'authentication-info',
  'location',
  'proxy-authenticate',
  'proxy-authentication-info',
  'refresh',
  'set-cookie',
  'set-cookie2',
  'www-authenticate'
]);

function boundedPositiveInteger(value, fallback, ceiling) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 && parsed <= ceiling ? parsed : fallback;
}

function requireLoopbackTarget(value) {
  const target = new URL(value);
  if (!['http:', 'https:'].includes(target.protocol)) throw new Error('proxy target protocol is not allowed');
  if (!['127.0.0.1', '::1', '[::1]', 'localhost'].includes(target.hostname)) {
    throw new Error('public security-hold proxy target must be loopback');
  }
  target.username = '';
  target.password = '';
  return target;
}

async function readBounded(stream, limit, controller, code) {
  const chunks = [];
  let total = 0;
  for await (const chunk of stream) {
    total += chunk.length;
    if (total > limit) {
      controller?.abort(code);
      throw Object.assign(new Error(code), { code });
    }
    chunks.push(chunk);
  }
  return chunks.length ? Buffer.concat(chunks, total) : Buffer.alloc(0);
}

function requestOperations(body) {
  let payload;
  try {
    payload = JSON.parse(body.toString('utf8'));
  } catch {
    return { ok: false, status: 400, error: 'invalid_json' };
  }
  const messages = Array.isArray(payload) ? payload : [payload];
  if (messages.length === 0 || messages.some((message) => !message || typeof message !== 'object' || Array.isArray(message) || typeof message.method !== 'string')) {
    return { ok: false, status: 400, error: 'invalid_jsonrpc_request' };
  }
  if (messages.some((message) => !ALLOWED_OPERATIONS.has(message.method))) {
    return { ok: false, status: 403, error: 'operation_not_allowed' };
  }
  return { ok: true };
}

function respondJson(res, status, error) {
  res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
  res.end(JSON.stringify({ error }));
}

export function createProxyServer(options = {}) {
  const configuredTarget = options.target ?? process.env.MCP_CONFORMANCE_SERVER_URL;
  const requestLimit = boundedPositiveInteger(options.requestLimit ?? process.env.MCP_PROXY_REQUEST_BYTES_MAX, HARD_MAX_REQUEST_BYTES, HARD_MAX_REQUEST_BYTES);
  const responseLimit = boundedPositiveInteger(options.responseLimit ?? process.env.MCP_PROXY_RESPONSE_BYTES_MAX, HARD_MAX_RESPONSE_BYTES, HARD_MAX_RESPONSE_BYTES);
  const timeoutMs = boundedPositiveInteger(options.timeoutMs ?? process.env.MCP_PROXY_UPSTREAM_TIMEOUT_MS, HARD_MAX_TIMEOUT_MS, HARD_MAX_TIMEOUT_MS);
  if (!configuredTarget) throw new Error('proxy target is required');
  const target = requireLoopbackTarget(configuredTarget);

  return http.createServer(async (req, res) => {
    const controller = new AbortController();
    let timer;
    const abort = (reason) => { if (!controller.signal.aborted) controller.abort(reason); };
    req.on('aborted', () => abort('downstream_aborted'));
    res.on('close', () => { if (!res.writableEnded) abort('downstream_closed'); });

    try {
      if (req.method !== 'POST' || req.url !== '/mcp') {
        res.setHeader('allow', 'POST');
        return respondJson(res, 405, 'method_or_path_not_allowed');
      }
      const declared = Number(req.headers['content-length'] ?? 0);
      if (Number.isFinite(declared) && declared > requestLimit) return respondJson(res, 413, 'request_body_too_large');
      const body = await readBounded(req, requestLimit, controller, 'REQUEST_BODY_TOO_LARGE');
      const operationCheck = requestOperations(body);
      if (!operationCheck.ok) return respondJson(res, operationCheck.status, operationCheck.error);

      const headers = {
        ...req.headers,
        'x-crownthrive-certification-mode': 'conformance'
      };
      delete headers.host;
      delete headers['content-length'];
      delete headers.authorization;
      delete headers.cookie;
      delete headers['proxy-authorization'];

      timer = setTimeout(() => abort('upstream_timeout'), timeoutMs);
      const response = await fetch(target, { method: 'POST', headers, body, redirect: 'manual', signal: controller.signal });
      const upstreamDeclared = Number(response.headers.get('content-length') ?? 0);
      if (Number.isFinite(upstreamDeclared) && upstreamDeclared > responseLimit) {
        abort('UPSTREAM_RESPONSE_TOO_LARGE');
        return respondJson(res, 502, 'upstream_response_too_large');
      }
      const bytes = await readBounded(response.body ?? [], responseLimit, controller, 'UPSTREAM_RESPONSE_TOO_LARGE');
      res.statusCode = response.status;
      for (const [key, value] of response.headers.entries()) {
        const normalized = key.toLowerCase();
        if (normalized === 'content-length' || normalized === 'transfer-encoding' || BLOCKED_RESPONSE_HEADERS.has(normalized)) continue;
        try { res.setHeader(key, value); } catch {}
      }
      res.setHeader('content-length', String(bytes.length));
      res.end(bytes);
    } catch (error) {
      if (res.headersSent || res.writableEnded) return;
      const timedOut = controller.signal.reason === 'upstream_timeout';
      const requestTooLarge = error?.code === 'REQUEST_BODY_TOO_LARGE';
      const upstreamTooLarge = error?.code === 'UPSTREAM_RESPONSE_TOO_LARGE';
      respondJson(res, timedOut ? 504 : requestTooLarge ? 413 : 502, timedOut ? 'upstream_timeout' : requestTooLarge ? 'request_body_too_large' : upstreamTooLarge ? 'upstream_response_too_large' : 'certification_proxy_failure');
    } finally {
      if (timer) clearTimeout(timer);
    }
  });
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  try {
    const port = boundedPositiveInteger(process.env.MCP_CONFORMANCE_PROXY_PORT, 8787, 65_535);
    const server = createProxyServer();
    server.listen(port, '127.0.0.1', () => console.log(JSON.stringify({ state: 'listening', port, request_bytes_max: HARD_MAX_REQUEST_BYTES, response_bytes_max: HARD_MAX_RESPONSE_BYTES, timeout_ms_max: HARD_MAX_TIMEOUT_MS })));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(2);
  }
}
