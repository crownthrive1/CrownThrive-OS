#!/usr/bin/env node
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createProxyServer } from './external-certification-auth-proxy.mjs';

function run(script, args = [], env = {}) {
  return spawnSync(process.execPath, [script, ...args], { encoding: 'utf8', env: { ...process.env, ...env } });
}
function listen(server) { return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server.address().port))); }
function close(server) { return new Promise((resolve) => server.close(resolve)); }
async function request(port, { method = 'POST', path = '/mcp', body = '{"method":"ping"}' } = {}) {
  const response = await fetch(`http://127.0.0.1:${port}${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: method === 'GET' || method === 'HEAD' ? undefined : body,
    redirect: 'manual'
  });
  const text = await response.text();
  let json;
  try { json = JSON.parse(text); } catch { json = null; }
  return { status: response.status, headers: response.headers, json, text };
}

const staticRun = run('contracts/mcp/external-certification-runner.mjs');
assert.equal(staticRun.status, 0, staticRun.stderr);
assert.equal(JSON.parse(staticRun.stdout).state, 'security_hold_replacement_required');
assert.notEqual(run('contracts/mcp/external-certification-runner.mjs', [], { MCP_CERTIFICATION_LIVE: 'true' }).status, 0);
assert.notEqual(run('contracts/mcp/capture-mcp-output-shapes.mjs').status, 0);
assert.notEqual(run('contracts/mcp/verify-founder-signature-envelope.mjs', ['--require-signed']).status, 0);
assert.equal(run('contracts/mcp/verify-founder-signature-envelope.mjs').status, 0);

const correctionContract = 'contracts/mcp/oidc-immutable-subject-correction.v1.json';
const correctionEnvelope = 'contracts/mcp/oidc-immutable-subject-correction-signature-envelope.v1.json';
assert.equal(existsSync(correctionContract), false, 'public correction contract must remain removed');
assert.equal(existsSync(correctionEnvelope), false, 'public correction signature envelope must remain removed');
const reconciliation = JSON.parse(readFileSync('contracts/mcp/external-certification-security-hold-reconciliation.v1.json', 'utf8'));
assert.equal(reconciliation.canonical_main_before_reconciliation, '0ccc6fac3d7b7028f4bd48b095c6cb4c30fe263d');
assert.equal(reconciliation.historical_payloads[1].sha256, 'e0f403326e9dab954a323d032686f7044393b5f85fa5053b73afa36a1dec07cf');
assert.equal(reconciliation.current_authority.execution_enabled, false);
assert.equal(reconciliation.current_authority.oidc_minting_enabled, false);
const envelope = JSON.parse(readFileSync('contracts/mcp/founder-signature-envelope.v1.json', 'utf8'));
assert.equal(envelope.replacement_authorized_payload_sha256, null);
assert.equal(envelope.superseded_correction_payload_sha256, 'e0f403326e9dab954a323d032686f7044393b5f85fa5053b73afa36a1dec07cf');
assert.equal(envelope.observed_execution.replay_authorized, false);

assert.throws(
  () => createProxyServer({ target: 'https://example.com/mcp' }),
  /public security-hold proxy target must be loopback/,
  'public security-hold relay must reject remote targets'
);

let upstreamHits = 0;
const upstream = http.createServer((req, res) => { upstreamHits += 1; res.end('{}'); });
const upstreamPort = await listen(upstream);
const proxy = createProxyServer({ target: `http://127.0.0.1:${upstreamPort}/mcp`, requestLimit: 32, responseLimit: 64, timeoutMs: 500 });
const proxyPort = await listen(proxy);
const oversized = await request(proxyPort, { body: 'x'.repeat(33) });
assert.equal(oversized.status, 413);
assert.equal(upstreamHits, 0);
assert.equal((await request(proxyPort, { method: 'GET' })).status, 405);
assert.equal((await request(proxyPort, { path: '/other' })).status, 405);
assert.equal((await request(proxyPort, { body: '{"method":"tools/call"}' })).status, 403);
assert.equal((await request(proxyPort, { body: '{"method":"unknown/read"}' })).status, 403);
assert.equal((await request(proxyPort, { body: '{not-json' })).status, 400);
assert.equal(upstreamHits, 0, 'rejected requests must never reach upstream');
assert.equal((await request(proxyPort)).status, 200);
assert.equal(upstreamHits, 1, 'allowlisted provider-free operation should reach loopback upstream');
await close(proxy);
await close(upstream);

const largeUpstream = http.createServer((req, res) => res.end('x'.repeat(65)));
const largePort = await listen(largeUpstream);
const largeProxy = createProxyServer({ target: `http://127.0.0.1:${largePort}/mcp`, requestLimit: 32, responseLimit: 64, timeoutMs: 500 });
const largeProxyPort = await listen(largeProxy);
const declaredOversized = await request(largeProxyPort);
assert.equal(declaredOversized.status, 502);
assert.equal(declaredOversized.json.error, 'upstream_response_too_large');
await close(largeProxy);
await close(largeUpstream);

const chunkedUpstream = http.createServer((req, res) => {
  res.write('x'.repeat(40));
  res.end('x'.repeat(40));
});
const chunkedPort = await listen(chunkedUpstream);
const chunkedProxy = createProxyServer({ target: `http://127.0.0.1:${chunkedPort}/mcp`, requestLimit: 32, responseLimit: 64, timeoutMs: 500 });
const chunkedProxyPort = await listen(chunkedProxy);
const chunkedOversized = await request(chunkedProxyPort);
assert.equal(chunkedOversized.status, 502);
assert.equal(chunkedOversized.json.error, 'upstream_response_too_large');
await close(chunkedProxy);
await close(chunkedUpstream);

const headerUpstream = http.createServer((req, res) => {
  res.setHeader('set-cookie', 'private=1');
  res.setHeader('www-authenticate', 'Bearer realm="private"');
  res.setHeader('proxy-authenticate', 'Basic realm="private"');
  res.setHeader('authentication-info', 'nextnonce="private"');
  res.setHeader('location', 'https://private.example/');
  res.setHeader('refresh', '0; url=https://private.example/');
  res.setHeader('x-public-safe', 'yes');
  res.end('{}');
});
const headerPort = await listen(headerUpstream);
const headerProxy = createProxyServer({ target: `http://127.0.0.1:${headerPort}/mcp`, requestLimit: 32, responseLimit: 64, timeoutMs: 500 });
const headerProxyPort = await listen(headerProxy);
const headerResponse = await request(headerProxyPort);
assert.equal(headerResponse.status, 200);
for (const header of ['set-cookie', 'www-authenticate', 'proxy-authenticate', 'authentication-info', 'location', 'refresh']) {
  assert.equal(headerResponse.headers.get(header), null, `${header} must not cross the relay boundary`);
}
assert.equal(headerResponse.headers.get('x-public-safe'), 'yes');
await close(headerProxy);
await close(headerUpstream);

const slowUpstream = http.createServer((req, res) => setTimeout(() => res.end('{}'), 250));
const slowPort = await listen(slowUpstream);
const slowProxy = createProxyServer({ target: `http://127.0.0.1:${slowPort}/mcp`, requestLimit: 32, responseLimit: 64, timeoutMs: 50 });
const slowProxyPort = await listen(slowProxy);
assert.equal((await request(slowProxyPort)).status, 504);
await close(slowProxy);
await close(slowUpstream);

console.log(JSON.stringify({
  security_hold: 'PASS',
  live_execution_rejected: true,
  signature_reuse_rejected: true,
  remote_target_rejected: true,
  method_path_allowlist_enforced: true,
  operation_allowlist_enforced: true,
  oversized_request_rejected: true,
  declared_oversized_response_rejected: true,
  chunked_oversized_response_rejected: true,
  sensitive_response_headers_stripped: true,
  timeout_cancellation: true,
  current_main_reconciled: true,
  correction_artifacts_removed: true
}, null, 2));
