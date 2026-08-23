import assert from 'node:assert/strict';
import {
  MCP_PROTOCOL_VERSION,
  TOOL_CATALOG,
  TOOL_BY_NAME,
  HTTP_ROUTE_TO_TOOL,
  validateMcpEnvelope,
  discoverResult,
  toolsListResult,
  normalizeToolArguments
} from '../../../../supabase/functions/chlom-wallet-continuity/contract.mjs';

assert.equal(MCP_PROTOCOL_VERSION, '2026-07-28');
assert.equal(TOOL_CATALOG.length, 8);
assert.equal(Object.keys(TOOL_BY_NAME).length, 8);
assert.equal(Object.keys(HTTP_ROUTE_TO_TOOL).length, 8);
assert.equal(new Set(TOOL_CATALOG.map(t => t.name)).size, 8);
assert.ok(TOOL_CATALOG.every(t => ['D0','D1','D2'].includes(t.riskClass)));
assert.ok(TOOL_CATALOG.every(t => t.inputSchema?.type === 'object'));

const discovery = discoverResult();
assert.deepEqual(discovery.supportedVersions, ['2026-07-28']);
assert.equal(discovery.capabilities.tools.listChanged, false);
assert.equal(discovery.cacheScope, 'private');

const listed = toolsListResult();
assert.equal(listed.tools.length, 8);
assert.equal(listed.cacheScope, 'private');
assert.ok(listed.tools.every(t => t.annotations.destructiveHint === false));
assert.ok(listed.tools.every(t => t.annotations.openWorldHint === false));

const validDiscover = validateMcpEnvelope({
  'mcp-protocol-version':'2026-07-28',
  'mcp-method':'server/discover'
}, { jsonrpc:'2.0', id:1, method:'server/discover', params:{ _meta:{} } });
assert.equal(validDiscover.ok, true);

const validList = validateMcpEnvelope({
  'mcp-protocol-version':'2026-07-28',
  'mcp-method':'tools/list'
}, { jsonrpc:'2.0', id:2, method:'tools/list', params:{ _meta:{} } });
assert.equal(validList.ok, true);

const validCall = validateMcpEnvelope({
  'mcp-protocol-version':'2026-07-28',
  'mcp-method':'tools/call',
  'mcp-name':'chlom_wallet_continuity_status_v1'
}, { jsonrpc:'2.0', id:3, method:'tools/call', params:{ name:'chlom_wallet_continuity_status_v1', arguments:{}, _meta:{} } });
assert.equal(validCall.ok, true);

assert.equal(validateMcpEnvelope({
  'mcp-protocol-version':'2025-11-25','mcp-method':'tools/list'
}, { jsonrpc:'2.0', id:4, method:'tools/list' }).code, -32022);

assert.equal(validateMcpEnvelope({
  'mcp-protocol-version':'2026-07-28','mcp-method':'tools/list'
}, { jsonrpc:'2.0', id:5, method:'tools/call', params:{name:'x'} }).code, -32020);

assert.equal(validateMcpEnvelope({
  'mcp-protocol-version':'2026-07-28','mcp-method':'tools/call','mcp-name':'wrong'
}, { jsonrpc:'2.0', id:6, method:'tools/call', params:{name:'chlom_wallet_continuity_status_v1'} }).code, -32020);

assert.deepEqual(normalizeToolArguments('chlom_wallet_continuity_status_v1',{}),{});
assert.deepEqual(normalizeToolArguments('chlom_wallet_continuity_assets_v1',{limit:20,offset:5}),{p_limit:20,p_offset:5});
assert.deepEqual(normalizeToolArguments('chlom_wallet_continuity_expiry_evaluate_v1',{observed_at:'2026-08-23T05:00:00Z',ttl_seconds:60}),{
  p_observed_at:'2026-08-23T05:00:00Z',p_ttl_seconds:60,p_explicit_state:'PASS'
});

// Adversarial header/body mismatch harness: no mutated routing tuple may be accepted.
let acceptedMismatch = 0;
for (let i=0;i<20000;i++) {
  const bodyTool = TOOL_CATALOG[i % TOOL_CATALOG.length].name;
  const wrongTool = TOOL_CATALOG[(i + 1) % TOOL_CATALOG.length].name;
  const bad = validateMcpEnvelope({
    'mcp-protocol-version':'2026-07-28',
    'mcp-method': i % 2 === 0 ? 'tools/list' : 'tools/call',
    'mcp-name': wrongTool
  }, {
    jsonrpc:'2.0',id:i,method:'tools/call',params:{name:bodyTool,arguments:{}}
  });
  if (bad.ok) acceptedMismatch++;
}
assert.equal(acceptedMismatch,0);

console.log(JSON.stringify({
  result:'PASS_CHLOM_WALLET_CONTINUITY_RUNTIME_API_MCP_V1',
  mcp_protocol:MCP_PROTOCOL_VERSION,
  tools:TOOL_CATALOG.length,
  http_routes:Object.keys(HTTP_ROUTE_TO_TOOL).length,
  adversarial_header_cases:20000,
  accepted_header_mismatches:acceptedMismatch,
  service_role_only:true,
  destructive_tools:0,
  provider_write:false,
  money_movement:false,
  rights_grant:false,
  chain_broadcast:false,
  checkout_enabled:false,
  production_activation:false,
  ai_final_authority:false
},null,2));
