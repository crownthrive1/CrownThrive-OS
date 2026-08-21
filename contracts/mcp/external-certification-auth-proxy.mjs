#!/usr/bin/env node
import http from 'node:http';

const target = process.env.MCP_CONFORMANCE_SERVER_URL;
const bearer = process.env.MCP_CERTIFICATION_BEARER;
const port = Number(process.env.MCP_CONFORMANCE_PROXY_PORT || 8787);
if (!target || !bearer) {
  console.error('MCP_CONFORMANCE_SERVER_URL and MCP_CERTIFICATION_BEARER are required');
  process.exit(2);
}

const server = http.createServer(async (req, res) => {
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? Buffer.concat(chunks) : undefined;
    const headers = { ...req.headers, authorization: `Bearer ${bearer}` };
    delete headers.host;
    delete headers['content-length'];
    const response = await fetch(target, {
      method: req.method,
      headers,
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : body,
      redirect: 'manual'
    });
    res.statusCode = response.status;
    for (const [key, value] of response.headers.entries()) {
      if (key.toLowerCase() === 'content-length' || key.toLowerCase() === 'transfer-encoding') continue;
      try { res.setHeader(key, value); } catch {}
    }
    const bytes = new Uint8Array(await response.arrayBuffer());
    res.setHeader('content-length', String(bytes.byteLength));
    res.end(Buffer.from(bytes));
  } catch (error) {
    res.statusCode = 502;
    res.setHeader('content-type', 'application/json');
    res.end(JSON.stringify({ error: 'certification_proxy_failure', detail: error instanceof Error ? error.message : String(error) }));
  }
});

server.listen(port, '127.0.0.1', () => {
  console.log(`MCP certification auth proxy listening on http://127.0.0.1:${port}/mcp`);
});
