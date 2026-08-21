#!/usr/bin/env node
import http from 'node:http';
import { pathToFileURL } from 'node:url';

const HARD_MAX_REQUEST_BYTES = 262_144;
const HARD_MAX_RESPONSE_BYTES = 1_048_576;
const HARD_MAX_TIMEOUT_MS = 15_000;

function boundedPositiveInteger(value, fallback, ceiling) {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 && parsed <= ceiling ? parsed : fallback;
}

async function readBounded(stream, limit, controller) {
  const chunks = [];
  let total = 0;
  for await (const chunk of stream) {
    total += chunk.length;
    if (total > limit) {
      controller?.abort('byte_limit');
      throw Object.assign(new Error('byte_limit'), { code: 'BYTE_LIMIT' });
    }
    chunks.push(chunk);
  }
  return chunks.length ? Buffer.concat(chunks, total) : Buffer.alloc(0);
}

export function createProxyServer(options = {}) {
  const target = options.target ?? process.env.MCP_CONFORMANCE_SERVER_URL;
  const requestLimit = boundedPositiveInteger(options.requestLimit ?? process.env.MCP_PROXY_REQUEST_BYTES_MAX, HARD_MAX_REQUEST_BYTES, HARD_MAX_REQUEST_BYTES);
  const responseLimit = boundedPositiveInteger(options.responseLimit ?? process.env.MCP_PROXY_RESPONSE_BYTES_MAX, HARD_MAX_RESPONSE_BYTES, HARD_MAX_RESPONSE_BYTES);
  const timeoutMs = boundedPositiveInteger(options.timeoutMs ?? process.env.MCP_PROXY_UPSTREAM_TIMEOUT_MS, HARD_MAX_TIMEOUT_MS, HARD_MAX_TIMEOUT_MS);
  if (!target) throw new Error('proxy target is required');

  return http.createServer(async (req, res) => {
    const controller = new AbortController();
    let timer;
    const abort = (reason) => { if (!controller.signal.aborted) controller.abort(reason); };
    req.on('aborted', () => abort('downstream_aborted'));
    res.on('close', () => { if (!res.writableEnded) abort('downstream_closed'); });

    try {
      const declared = Number(req.headers['content-length'] ?? 0);
      if (Number.isFinite(declared) && declared > requestLimit) {
        res.writeHead(413, { 'content-type': 'application/json', 'cache-control': 'no-store' });
        return res.end(JSON.stringify({ error: 'request_body_too_large' }));
      }
      const body = req.method === 'GET' || req.method === 'HEAD' ? undefined : await readBounded(req, requestLimit, controller);
      const headers = {
        ...req.headers,
        'x-crownthrive-certification-mode': 'conformance'
      };
      delete headers.host;
      delete headers['content-length'];
      delete headers.authorization;
      delete headers.cookie;

      timer = setTimeout(() => abort('upstream_timeout'), timeoutMs);
      const response = await fetch(target, { method: req.method, headers, body, redirect: 'manual', signal: controller.signal });
      const upstreamDeclared = Number(response.headers.get('content-length') ?? 0);
      if (Number.isFinite(upstreamDeclared) && upstreamDeclared > responseLimit) {
        abort('response_size_limit_declared');
        res.writeHead(502, { 'content-type': 'application/json', 'cache-control': 'no-store' });
        return res.end(JSON.stringify({ error: 'upstream_response_too_large' }));
      }
      const bytes = await readBounded(response.body ?? [], responseLimit, controller);
      res.statusCode = response.status;
      for (const [key, value] of response.headers.entries()) {
        if (key.toLowerCase() === 'content-length' || key.toLowerCase() === 'transfer-encoding') continue;
        try { res.setHeader(key, value); } catch {}
      }
      res.setHeader('content-length', String(bytes.length));
      res.end(bytes);
    } catch (error) {
      if (res.headersSent || res.writableEnded) return;
      const timedOut = controller.signal.reason === 'upstream_timeout';
      const tooLarge = error?.code === 'BYTE_LIMIT';
      res.writeHead(timedOut ? 504 : tooLarge ? 413 : 502, { 'content-type': 'application/json', 'cache-control': 'no-store' });
      res.end(JSON.stringify({ error: timedOut ? 'upstream_timeout' : tooLarge ? 'byte_limit' : 'certification_proxy_failure' }));
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
