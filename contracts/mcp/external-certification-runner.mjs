#!/usr/bin/env node
import fs from 'node:fs';
import crypto from 'node:crypto';

const manifestPath = new URL('./external-certification-plan.v1.json', import.meta.url);
const manifestBytes = fs.readFileSync(manifestPath);
const manifest = JSON.parse(manifestBytes.toString('utf8'));
const manifestSha256 = crypto.createHash('sha256').update(manifestBytes).digest('hex');
const live = process.env.MCP_CERTIFICATION_LIVE === 'true';
const allowProviderReads = process.env.MCP_CERTIFICATION_ALLOW_PROVIDER_READS === 'true';
const serverUrl = process.env.MCP_CERTIFICATION_SERVER_URL || manifest.server.production_url;
const bearer = process.env.MCP_CERTIFICATION_BEARER || '';
const protocolVersion = manifest.server.protocol_version;
const clientInfo = { name: 'CrownThrive External MCP Certifier', version: '1.0.0' };

const expectedTools = new Set([
  'crownthrive_io_get_user','crownthrive_io_list_data','crownthrive_io_list_domains','crownthrive_io_list_links',
  'crownthrive_io_list_my_team_memberships','crownthrive_io_list_notification_handlers','crownthrive_io_list_pixels',
  'crownthrive_io_list_projects','crownthrive_io_list_qr_codes','crownthrive_io_list_splash_pages','crownthrive_io_list_teams',
  'crownthrive_io_statistics','seo.archived_audits.list','seo.audits.list','seo.custom_domains.list',
  'seo.notification_handlers.list','seo.teams_member.read','seo.teams.list','seo.user.read','seo.websites.list'
]);
const results = [];
function assert(condition, id, detail) { if (!condition) throw new Error(`${id}: ${detail}`); results.push({ id, pass: true, detail }); }
function requiredMeta(extra = {}) { return { 'io.modelcontextprotocol/protocolVersion': protocolVersion, 'io.modelcontextprotocol/clientInfo': clientInfo, 'io.modelcontextprotocol/clientCapabilities': {}, ...extra }; }
function headers(method, name, overrides = {}) { const out = { 'content-type': 'application/json', 'authorization': `Bearer ${bearer}`, 'mcp-protocol-version': protocolVersion, 'mcp-method': method, 'x-crownthrive-certification-mode': live ? 'live-proof' : 'conformance', ...overrides }; if (name) out['mcp-name'] = name; return out; }
async function rawRequest({ body, requestHeaders, method = 'POST' }) { const response = await fetch(serverUrl, { method, headers: requestHeaders, body }); const text = await response.text(); let json = null; try { json = text ? JSON.parse(text) : null; } catch {} return { status: response.status, headers: Object.fromEntries(response.headers.entries()), text, json }; }
async function rpcRequest(id, method, params = {}, name = null, headerOverrides = {}) { return rawRequest({ requestHeaders: headers(method, name, headerOverrides), body: JSON.stringify({ jsonrpc: '2.0', id, method, params: { ...params, _meta: requiredMeta(params?._meta || {}) } }) }); }
function isGenericObjectSchema(schema) { if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return true; const keys = Object.keys(schema).filter((key) => key !== '$schema' && key !== 'description' && key !== 'title'); return keys.length === 1 && schema.type === 'object'; }
function boundedInputSchema(schema) { return Boolean(schema && typeof schema === 'object' && !Array.isArray(schema) && schema.type === 'object' && schema.additionalProperties === false); }
function boundedOutputSchema(schema) { if (!schema || typeof schema !== 'object' || Array.isArray(schema) || isGenericObjectSchema(schema)) return false; return Boolean(schema.properties || schema.required || schema.oneOf || schema.anyOf || schema.allOf || schema.$ref || schema.const !== undefined || schema.enum || schema.additionalProperties === false || schema.maxProperties !== undefined || schema.maxItems !== undefined); }

function runStaticPreflight() {
  assert(manifest.schema_version === '1.0.0', 'PRE-001', 'manifest schema version is pinned');
  assert(manifest.certification_id === 'CT-MCP-EXTCERT-001', 'PRE-002', 'certification id is stable');
  assert(manifest.server.protocol_version === '2026-07-28', 'PRE-003', 'protocol target is 2026-07-28');
  assert(manifest.server.provider_writes_enabled === false, 'PRE-004', 'provider writes remain disabled');
  assert(manifest.server.sovereign_vote_authority === false, 'PRE-005', 'certification runner has no sovereign vote authority');
  assert(manifest.server.expected_central_enabled_tool_count === 20, 'PRE-006', 'central enabled-tool expectation is 20');
  assert(manifest.founder_signature.required === true, 'PRE-007', 'founder signature is mandatory before final implementation');
  assert(manifest.founder_signature.state === 'awaiting_signature', 'PRE-008', 'pre-signature artifact is fail-closed');
  assert(manifest.state === 'prepared_awaiting_founder_signature', 'PRE-009', 'certification lifecycle is held before final implementation');
  assert(manifest.post_signature_execution.provider_read_budget.crownthrive_io === 13, 'PRE-010', 'CrownThrive IO total post-signature certification budget is 13 reads');
  assert(manifest.post_signature_execution.provider_read_budget.thrivetools_seo === 9, 'PRE-011', 'ThriveTools SEO total post-signature certification budget is 9 reads');
  assert(manifest.post_signature_execution.provider_read_budget.provider_writes === 0, 'PRE-012', 'provider write budget is zero');
  assert(Array.isArray(manifest.mandatory_acceptance) && manifest.mandatory_acceptance.length === 15, 'PRE-013', 'all 15 mandatory acceptance predicates are represented');
  const ids = manifest.mandatory_acceptance.map((x) => x.id);
  assert(new Set(ids).size === ids.length, 'PRE-014', 'acceptance predicate ids are unique');
  return { manifest_sha256: manifestSha256, mode: 'pre_signature_static', results };
}

async function runLive() {
  if (manifest.founder_signature.state !== 'signed') throw new Error('LIVE-000: founder signature state is not signed');
  if (!bearer) throw new Error('LIVE-000: MCP_CERTIFICATION_BEARER is required');
  const discover = await rpcRequest('discover-1', 'server/discover');
  assert(discover.status === 200, 'EXT-001A', `server/discover HTTP ${discover.status}`);
  assert(discover.json?.jsonrpc === '2.0' && discover.json?.result, 'EXT-001B', 'server/discover returns JSON-RPC result');
  assert(Array.isArray(discover.json.result.supportedVersions) && discover.json.result.supportedVersions.includes(protocolVersion), 'EXT-001C', 'server/discover advertises 2026-07-28');
  assert(discover.json.result.capabilities?.tools !== undefined, 'EXT-001D', 'server/discover advertises tools capability');
  assert(discover.json.result.cacheScope === 'private' && Number(discover.json.result.ttlMs) > 0, 'EXT-001E', 'server/discover returns private cache hints');
  const list1 = await rpcRequest('tools-1', 'tools/list'); const list2 = await rpcRequest('tools-2', 'tools/list');
  assert(list1.status === 200 && list2.status === 200, 'EXT-002A', 'tools/list succeeds twice');
  const tools1 = list1.json?.result?.tools; const tools2 = list2.json?.result?.tools;
  assert(Array.isArray(tools1) && tools1.length === manifest.server.expected_central_enabled_tool_count, 'EXT-002B', `tools/list exposes exactly ${manifest.server.expected_central_enabled_tool_count} tools`);
  assert(JSON.stringify(tools1) === JSON.stringify(tools2), 'EXT-002C', 'tools/list is deterministic across repeated reads');
  assert(list1.json?.result?.cacheScope === 'private' && Number(list1.json?.result?.ttlMs) > 0, 'EXT-002D', 'tools/list returns private cache hints');
  const names = tools1.map((t) => t.name);
  assert(names.every((name, index) => index === 0 || names[index - 1].localeCompare(name) <= 0), 'EXT-002E', 'tool order is deterministic lexicographic order');
  assert(names.length === expectedTools.size && names.every((name) => expectedTools.has(name)), 'EXT-002F', 'advertised tools match the certified central allowlist');
  assert(tools1.every((t) => boundedInputSchema(t.inputSchema)), 'EXT-008', 'all enabled central input schemas reject undeclared properties');
  assert(tools1.every((t) => boundedOutputSchema(t.outputSchema)), 'EXT-009', 'all enabled central output schemas are non-generic bounded contracts');
  const malformed = await rawRequest({ requestHeaders: headers('tools/list'), body: '{"jsonrpc":' });
  assert(malformed.status === 400 && malformed.json?.error?.code === -32700 && malformed.json?.id === null, 'EXT-003', 'malformed MCP JSON returns -32700 with null id');
  const wrongType = await rawRequest({ requestHeaders: { ...headers('tools/list'), 'content-type': 'text/plain' }, body: '{}' });
  assert(wrongType.status === 415, 'EXT-004', 'non-application/json MCP request is rejected with HTTP 415');
  const mismatch = await rpcRequest('mismatch-1', 'tools/list', {}, null, { 'mcp-method': 'server/discover' });
  assert(mismatch.status === 400 && mismatch.json?.error?.code === -32020, 'EXT-005', 'MCP routing header/body mismatch returns -32020');
  const unsupported = await rawRequest({ requestHeaders: { ...headers('tools/list'), 'mcp-protocol-version': '1900-01-01' }, body: JSON.stringify({ jsonrpc: '2.0', id: 'version-1', method: 'tools/list', params: { _meta: { ...requiredMeta(), 'io.modelcontextprotocol/protocolVersion': '1900-01-01' } } }) });
  assert(unsupported.status === 400 && unsupported.json?.error?.code === -32022 && Array.isArray(unsupported.json?.error?.data?.supported), 'EXT-006', 'unsupported protocol version returns -32022 with supported versions');
  const unknown = await rpcRequest('unknown-1', 'crownthrive/unknown');
  assert(unknown.status === 200 && unknown.json?.error?.code === -32601, 'EXT-007', 'unknown method returns in-band JSON-RPC -32601');
  if (!allowProviderReads) results.push({ id: 'EXT-013', pass: false, skipped: true, detail: 'provider-read proof held because MCP_CERTIFICATION_ALLOW_PROVIDER_READS is not true' });
  else {
    const io = await rpcRequest('io-live-1', 'tools/call', { name: 'crownthrive_io_get_user', arguments: {} }, 'crownthrive_io_get_user', { 'x-crownthrive-certification-mode': 'live-proof' });
    assert(io.status === 200 && io.json?.result?.isError === false && io.json?.result?.structuredContent?.ok === true, 'EXT-013A', 'external CrownThrive IO D0 tool call succeeds with structuredContent');
    const seo = await rpcRequest('seo-live-1', 'tools/call', { name: 'seo.user.read', arguments: {} }, 'seo.user.read', { 'x-crownthrive-certification-mode': 'live-proof' });
    assert(seo.status === 200 && seo.json?.result?.isError === false && seo.json?.result?.structuredContent?.ok === true, 'EXT-013B', 'external ThriveTools SEO D0 tool call succeeds with structuredContent');
  }
  return { manifest_sha256: manifestSha256, mode: 'external_live', server_url: serverUrl, results };
}

try { const report = live ? await runLive() : runStaticPreflight(); process.stdout.write(`${JSON.stringify(report, null, 2)}\n`); if (report.results.some((r) => r.pass === false && !r.skipped)) process.exit(1); }
catch (error) { process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`); process.exit(1); }
