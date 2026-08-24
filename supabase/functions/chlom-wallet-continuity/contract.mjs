export const MCP_PROTOCOL_VERSION = '2026-07-28';
export const SERVER_INFO = Object.freeze({ name: 'chlom-wallet-continuity', version: '1.0.0' });
export const SERVER_INFO_META_KEY = 'io.modelcontextprotocol/serverInfo';

export const TOOL_CATALOG = Object.freeze([
  {
    name: 'chlom_wallet_continuity_status_v1',
    description: 'Read the exact-head CHLOM Wallet continuity status. Read-only; no provider, Rights, money, chain, checkout, credential, merge, or phase authority.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    rpc: 'chlom_wallet_continuity_runtime_status_v1',
    riskClass: 'D0'
  },
  {
    name: 'chlom_wallet_continuity_assets_v1',
    description: 'List sanitized exact-head continuity factory projections. Read-only and candidate-only.',
    inputSchema: {
      type: 'object', additionalProperties: false,
      properties: { limit: { type: 'integer', minimum: 1, maximum: 200 }, offset: { type: 'integer', minimum: 0 } }
    },
    rpc: 'chlom_wallet_continuity_runtime_assets_v1',
    riskClass: 'D0'
  },
  {
    name: 'chlom_wallet_continuity_dependencies_v1',
    description: 'Read the exact-head continuity dependency graph and fail-closed dependency requirements.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    rpc: 'chlom_wallet_continuity_runtime_dependencies_v1',
    riskClass: 'D0'
  },
  {
    name: 'chlom_wallet_continuity_expiry_evaluate_v1',
    description: 'Evaluate evidence freshness. Stale or unresolved evidence downgrades to HOLD; this tool cannot manufacture replacement evidence.',
    inputSchema: {
      type: 'object', additionalProperties: false, required: ['observed_at', 'ttl_seconds'],
      properties: {
        observed_at: { type: 'string', format: 'date-time' },
        ttl_seconds: { type: 'integer', minimum: 1, maximum: 31536000 },
        explicit_state: { type: 'string', enum: ['PASS', 'HOLD', 'DENY'] }
      }
    },
    rpc: 'chlom_wallet_continuity_runtime_expiry_v1',
    riskClass: 'D1'
  },
  {
    name: 'chlom_wallet_continuity_oracle_observe_v1',
    description: 'Record a sanitized read-only oracle observation by digest, freshness, and source confidence. Raw source payloads and credentials are prohibited.',
    inputSchema: {
      type: 'object', additionalProperties: false, required: ['oracle_id', 'observed_at', 'payload_digest', 'source_confidence'],
      properties: {
        oracle_id: { type: 'string', minLength: 1, maxLength: 200 },
        observed_at: { type: 'string', format: 'date-time' },
        payload_digest: { type: 'string', pattern: '^[a-fA-F0-9]{64}$' },
        source_confidence: { type: 'number', minimum: 0, maximum: 1 }
      }
    },
    rpc: 'chlom_wallet_continuity_runtime_oracle_observe_v1',
    riskClass: 'D1'
  },
  {
    name: 'chlom_wallet_continuity_recovery_plan_v1',
    description: 'Create a reversible, non-destructive continuity recovery plan. ECAC means plan-eligible only; never execution authorization.',
    inputSchema: {
      type: 'object', additionalProperties: false, required: ['incident_ref', 'backup_verified', 'rollback_verified', 'independent_review_state', 'source_head_match'],
      properties: {
        incident_ref: { type: 'string', minLength: 1, maxLength: 300 },
        backup_verified: { type: 'boolean' },
        rollback_verified: { type: 'boolean' },
        independent_review_state: { type: 'string', enum: ['ECAC', 'HOLD', 'DENY'] },
        source_head_match: { type: 'boolean' }
      }
    },
    rpc: 'chlom_wallet_continuity_runtime_recovery_plan_v1',
    riskClass: 'D2'
  },
  {
    name: 'chlom_wallet_continuity_truth_snapshot_v1',
    description: 'Run the private fail-closed continuity tick and append an institutional truth snapshot. It cannot fabricate missing heartbeats, reviewers, or oracle evidence.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    rpc: 'chlom_wallet_continuity_runtime_truth_snapshot_v1',
    riskClass: 'D1'
  },
  {
    name: 'chlom_wallet_continuity_factory_projection_v1',
    description: 'Read the deterministic continuity factory projection summary and root digest without advancing the proprietary-factory generation.',
    inputSchema: { type: 'object', additionalProperties: false, properties: {} },
    rpc: 'chlom_wallet_continuity_runtime_factory_projection_v1',
    riskClass: 'D1'
  }
]);

export const TOOL_BY_NAME = Object.freeze(Object.fromEntries(TOOL_CATALOG.map(t => [t.name, t])));

export const HTTP_ROUTE_TO_TOOL = Object.freeze({
  'GET /api/status': 'chlom_wallet_continuity_status_v1',
  'GET /api/assets': 'chlom_wallet_continuity_assets_v1',
  'GET /api/dependencies': 'chlom_wallet_continuity_dependencies_v1',
  'POST /api/evaluate-expiry': 'chlom_wallet_continuity_expiry_evaluate_v1',
  'POST /api/observe-oracle': 'chlom_wallet_continuity_oracle_observe_v1',
  'POST /api/plan-recovery': 'chlom_wallet_continuity_recovery_plan_v1',
  'POST /api/truth-snapshot': 'chlom_wallet_continuity_truth_snapshot_v1',
  'POST /api/factory-projection': 'chlom_wallet_continuity_factory_projection_v1'
});

export function jsonRpcError(id, code, message, data = undefined) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  return { jsonrpc: '2.0', id: id ?? null, error, _meta: { [SERVER_INFO_META_KEY]: SERVER_INFO } };
}

export function jsonRpcResult(id, result) {
  return { jsonrpc: '2.0', id: id ?? null, result: { ...result, _meta: { ...(result?._meta ?? {}), [SERVER_INFO_META_KEY]: SERVER_INFO } } };
}

export function validateMcpEnvelope(headers, body) {
  if (!body || body.jsonrpc !== '2.0' || typeof body.method !== 'string') {
    return { ok: false, code: -32600, message: 'Invalid Request' };
  }
  const protocol = headers['mcp-protocol-version'];
  if (protocol !== MCP_PROTOCOL_VERSION) {
    return { ok: false, code: -32022, message: 'Unsupported protocol version', data: { supported: [MCP_PROTOCOL_VERSION] } };
  }
  const methodHeader = headers['mcp-method'];
  if (methodHeader !== body.method) {
    return { ok: false, code: -32020, message: 'HeaderMismatch', data: { header: 'Mcp-Method' } };
  }
  if (body.method === 'tools/call') {
    const name = body?.params?.name;
    if (typeof name !== 'string' || !name) return { ok: false, code: -32602, message: 'Invalid params' };
    if (headers['mcp-name'] !== name) {
      return { ok: false, code: -32020, message: 'HeaderMismatch', data: { header: 'Mcp-Name' } };
    }
  }
  return { ok: true };
}

export function discoverResult() {
  return {
    supportedVersions: [MCP_PROTOCOL_VERSION],
    capabilities: { tools: { listChanged: false } },
    instructions: 'Private CrownThrive CHLOM Wallet continuity MCP. Continuity may observe, downgrade, plan reversible recovery, and append evidence. It may never manufacture authority, reviewers, heartbeats, provider writes, money movement, Rights, chain broadcasts, pricing, checkout, destructive recovery, merge authorization, or phase advancement.',
    ttlMs: 300000,
    cacheScope: 'private'
  };
}

export function toolsListResult() {
  return {
    tools: TOOL_CATALOG.map(({ rpc, riskClass, ...tool }) => ({ ...tool, annotations: { readOnlyHint: riskClass === 'D0', destructiveHint: false, idempotentHint: riskClass === 'D0', openWorldHint: false } })),
    ttlMs: 300000,
    cacheScope: 'private'
  };
}

export function normalizeToolArguments(toolName, args = {}) {
  if (!TOOL_BY_NAME[toolName]) throw new Error('unknown_tool');
  if (args === null || typeof args !== 'object' || Array.isArray(args)) throw new Error('invalid_arguments');
  if (toolName === 'chlom_wallet_continuity_assets_v1') {
    return { p_limit: Number.isInteger(args.limit) ? args.limit : 100, p_offset: Number.isInteger(args.offset) ? args.offset : 0 };
  }
  if (toolName === 'chlom_wallet_continuity_expiry_evaluate_v1') {
    return { p_observed_at: args.observed_at, p_ttl_seconds: args.ttl_seconds, p_explicit_state: args.explicit_state ?? 'PASS' };
  }
  if (toolName === 'chlom_wallet_continuity_oracle_observe_v1') {
    return { p_oracle_id: args.oracle_id, p_observed_at: args.observed_at, p_payload_digest: args.payload_digest, p_source_confidence: args.source_confidence };
  }
  if (toolName === 'chlom_wallet_continuity_recovery_plan_v1') {
    return {
      p_incident_ref: args.incident_ref,
      p_backup_verified: args.backup_verified,
      p_rollback_verified: args.rollback_verified,
      p_independent_review_state: args.independent_review_state,
      p_source_head_match: args.source_head_match
    };
  }
  return {};
}
