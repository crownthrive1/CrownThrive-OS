#!/usr/bin/env node
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawnSync } from 'node:child_process';
import { createProxyServer } from './external-certification-auth-proxy.mjs';

function run(script, args = [], env = {}) {
  return spawnSync(process.execPath, [script, ...args], { encoding: 'utf8', env: { ...process.env, ...env } });
}
function listen(server) { return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port))); }
function close(server) { return new Promise((resolve) => server.close(resolve)); }
async function request(port, body) {
  const response = await fetch(`http://127.0.0.1:${port}/mcp`, { method: 'POST', headers: { 'content-type': 'application/json' }, body });
  return { status: response.status, json: await response.json() };
}

const staticRun = run('contracts/mcp/external-certification-runner.mjs');
assert.equal(staticRun.status, 0, staticRun.stderr);
assert.equal(JSON.parse(staticRun.stdout).state, 'security_hold_replacement_required');
assert.notEqual(run('contracts/mcp/external-certification-runner.mjs', [], { MCP_CERTIFICATION_LIVE: 'true' }).status, 0);
assert.notEqual(run('contracts/mcp/capture-mcp-output-shapes.mjs').status, 0);
assert.notEqual(run('contracts/mcp/verify-founder-signature-envelope.mjs', ['--require-signed']).status, 0);
assert.equal(run('contracts/mcp/verify-founder-signature-envelope.mjs').status, 0);

let upstreamHits = 0;
const upstream = http.createServer((req, res) => { upstreamHits += 1; res.end('{}'); });
const upstreamPort = await listen(upstream);
const proxy = createProxyServer({ target: `http://127.0.0.1:${upstreamPort}`, requestLimit: 32, responseLimit: 64, timeoutMs: 500 });
const proxyPort = await listen(proxy);
const oversized = await request(proxyPort, 'x'.repeat(33));
assert.equal(oversized.status, 413);
assert.equal(upstreamHits, 0);
await close(proxy);
await close(upstream);

const largeUpstream = http.createServer((req, res) => res.end('x'.repeat(65)));
const largePort = await listen(largeUpstream);
const largeProxy = createProxyServer({ target: `http://127.0.0.1:${largePort}`, requestLimit: 32, responseLimit: 64, timeoutMs: 500 });
const largeProxyPort = await listen(largeProxy);
assert.equal((await request(largeProxyPort, '{}')).status, 502);
await close(largeProxy);
await close(largeUpstream);

const slowUpstream = http.createServer((req, res) => setTimeout(() => res.end('{}'), 250));
const slowPort = await listen(slowUpstream);
const slowProxy = createProxyServer({ target: `http://127.0.0.1:${slowPort}`, requestLimit: 32, responseLimit: 64, timeoutMs: 50 });
const slowProxyPort = await listen(slowProxy);
assert.equal((await request(slowProxyPort, '{}')).status, 504);
await close(slowProxy);
await close(slowUpstream);

console.log(JSON.stringify({ security_hold: 'PASS', live_execution_rejected: true, signature_reuse_rejected: true, oversized_request_rejected: true, oversized_response_rejected: true, timeout_cancellation: true }, null, 2));
