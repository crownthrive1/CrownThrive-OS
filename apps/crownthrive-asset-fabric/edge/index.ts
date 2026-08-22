import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
const MCP_VERSION = "2026-07-28";
const SERVER = { name: "CrownThrive Asset Fabric", version: "0.1.0" };
const RESOURCE_URI = "ui://crownthrive/asset-fabric-dashboard.html";
const MAX_BYTES = 196608;
const ADMIN_EMAILS = new Set(["contact@crownthrive.com", "jones.usmc.kj@gmail.com"]);
const ADMIN_ROLES = new Set(["founder", "super_admin", "asset_admin", "chlom_admin"]);
const WIDGET_HTML = await Deno.readTextFile(new URL("./widget.html", import.meta.url));

type Actor = { id: string; serviceRole: boolean; founder: boolean };
type Tool = { name: string; description: string; risk: "D0" | "D1" | "D2"; readOnly: boolean; widget?: boolean; inputSchema: Record<string, unknown> };
const closed = (properties: Record<string, unknown> = {}, required: string[] = []) => ({ type: "object", properties, required, additionalProperties: false });
const text = { type: "string" };
const limit = { type: "integer", minimum: 1, maximum: 500 };
const evidence = { type: "array", items: { type: "string" } };
const planSchema = closed({ asset_id: text, arguments: { type: "object" }, evidence_refs: evidence });
const TOOLS: Tool[] = [
  { name: "assets.status", description: "Read sanitized suite, catalog, validation, custody and lifecycle counts.", risk: "D0", readOnly: true, widget: true, inputSchema: closed() },
  { name: "assets.search", description: "Search candidates by query, pallet, type or deployment profile.", risk: "D0", readOnly: true, inputSchema: closed({ query: text, pallet_id: text, asset_type: text, deployment_profile: text, limit }) },
  { name: "assets.get", description: "Retrieve one public-safe asset contract by stable ID.", risk: "D0", readOnly: true, inputSchema: closed({ asset_id: text }, ["asset_id"]) },
  { name: "assets.pallets.list", description: "List pallet plugins and coverage counts.", risk: "D0", readOnly: true, inputSchema: closed({ pallet_id: text, limit }) },
  { name: "assets.kernels.list", description: "List kernel candidates and custody states.", risk: "D0", readOnly: true, inputSchema: closed({ limit }) },
  { name: "assets.plugins.list", description: "List root and pallet plugin candidates.", risk: "D0", readOnly: true, inputSchema: closed({ limit }) },
  { name: "assets.executables.list", description: "List executable candidates and gate states.", risk: "D0", readOnly: true, inputSchema: closed({ limit }) },
  { name: "assets.scripts.list", description: "List script candidates and gate states.", risk: "D0", readOnly: true, inputSchema: closed({ limit }) },
  { name: "assets.dependencies", description: "Resolve dependency and reverse-dependency graphs.", risk: "D1", readOnly: true, inputSchema: closed({ asset_id: text, direction: { type: "string", enum: ["dependencies", "reverse", "both"] } }, ["asset_id"]) },
  { name: "assets.generate.plan", description: "Create a non-executing deterministic generation plan.", risk: "D1", readOnly: false, inputSchema: planSchema },
  { name: "assets.materialize.plan", description: "Create a non-executing controlled materialization plan.", risk: "D1", readOnly: false, inputSchema: planSchema },
  { name: "assets.verify", description: "Validate structure, digests, dependencies, authority and owner/verifier separation.", risk: "D1", readOnly: false, inputSchema: closed({ asset_id: text }) },
  { name: "assets.scrutinize", description: "Run independent security, rights, test, custody and commercialization scrutiny.", risk: "D2", readOnly: false, widget: true, inputSchema: closed({ asset_id: text }) },
  { name: "assets.custody.status", description: "Read sanitized Vault, archive, fingerprint and recovery state.", risk: "D1", readOnly: true, inputSchema: closed() },
  { name: "assets.gaps.scan", description: "Find missing contracts, dependencies, tests, custody, rights and runtime gates.", risk: "D1", readOnly: false, inputSchema: closed() },
  { name: "assets.package.plan", description: "Plan plugin, pallet, executable, skill or customer-package assembly.", risk: "D1", readOnly: false, inputSchema: planSchema },
  { name: "assets.lifecycle.transition.plan", description: "Plan a lifecycle transition without performing it.", risk: "D1", readOnly: false, inputSchema: planSchema },
  { name: "assets.supersede.plan", description: "Plan versioned supersession while preserving predecessor history.", risk: "D1", readOnly: false, inputSchema: planSchema },
  { name: "assets.commercialization.plan", description: "Prepare research-only rights, pricing, fulfillment and support prerequisites.", risk: "D2", readOnly: false, inputSchema: planSchema },
  { name: "assets.receipts.list", description: "List sanitized generation, validation, scrutiny and lifecycle receipts.", risk: "D0", readOnly: true, inputSchema: closed({ asset_id: text, limit }) },
];

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "referrer-policy": "no-referrer" } });
}
function rpcResult(id: unknown, result: unknown): Response { return respond({ jsonrpc: "2.0", id, result }); }
function rpcError(id: unknown, code: number, message: string, status = 400): Response { return respond({ jsonrpc: "2.0", id, error: { code, message } }, status); }
async function rpc(name: string, body: Record<string, unknown> = {}) {
  if (!SUPABASE_URL || !SERVICE_ROLE) throw new Error("ASSET_FABRIC_RUNTIME_NOT_CONFIGURED");
  const result = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, { method: "POST", headers: { "content-type": "application/json", apikey: SERVICE_ROLE, authorization: `Bearer ${SERVICE_ROLE}` }, body: JSON.stringify(body) });
  const raw = await result.text();
  if (!result.ok) {
    let detail = `RPC_${name}_${result.status}`;
    try { const parsed = JSON.parse(raw); detail = String(parsed?.message ?? parsed?.hint ?? detail).slice(0, 240); } catch { /* no backend body reflection */ }
    throw new Error(detail);
  }
  return raw ? JSON.parse(raw) : null;
}
async function authorize(req: Request): Promise<{ ok: boolean; actor: Actor; reason?: string }> {
  const raw = req.headers.get("authorization") ?? "";
  const token = raw.toLowerCase().startsWith("bearer ") ? raw.slice(7).trim() : "";
  if (!token) return { ok: false, actor: { id: "anonymous", serviceRole: false, founder: false }, reason: "missing_bearer" };
  if (SERVICE_ROLE && token === SERVICE_ROLE) return { ok: true, actor: { id: "service_role", serviceRole: true, founder: true } };
  if (!SUPABASE_URL || !ANON_KEY) return { ok: false, actor: { id: "unknown", serviceRole: false, founder: false }, reason: "auth_runtime_unavailable" };
  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, { headers: { apikey: ANON_KEY, authorization: `Bearer ${token}` } });
  if (!response.ok) return { ok: false, actor: { id: "unknown", serviceRole: false, founder: false }, reason: "invalid_user_token" };
  const user: any = await response.json();
  const email = String(user?.email ?? "").toLowerCase();
  const roles: string[] = [];
  if (typeof user?.app_metadata?.role === "string") roles.push(user.app_metadata.role);
  if (Array.isArray(user?.app_metadata?.roles)) for (const role of user.app_metadata.roles) if (typeof role === "string") roles.push(role);
  const founder = ADMIN_EMAILS.has(email);
  const allowed = founder || roles.some((role) => ADMIN_ROLES.has(role));
  return allowed ? { ok: true, actor: { id: email || "asset_admin", serviceRole: false, founder } } : { ok: false, actor: { id: email || "authenticated", serviceRole: false, founder: false }, reason: "asset_admin_required" };
}
async function parse(req: Request) {
  const length = Number(req.headers.get("content-length") ?? 0);
  if (length > MAX_BYTES) throw new Error("request_too_large");
  const raw = await req.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_BYTES) throw new Error("request_too_large");
  return JSON.parse(raw);
}
function optional(value: unknown): string | null { return typeof value === "string" && value.trim() ? value.trim() : null; }
function need(args: any, key: string): string { const value = optional(args?.[key]); if (!value) throw new Error(`missing_${key}`); return value; }
function object(value: unknown): Record<string, unknown> { return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
function refs(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim()) : []; }
function requireGoverned(actor: Actor) { if (!actor.serviceRole && !actor.founder) throw new Error("founder_or_service_role_required"); }
function descriptor(tool: Tool) {
  return { name: tool.name, title: tool.name.replaceAll(".", " "), description: tool.description, inputSchema: tool.inputSchema, outputSchema: { type: "object" }, annotations: { readOnlyHint: tool.readOnly, destructiveHint: false, idempotentHint: true, openWorldHint: false }, _meta: tool.widget ? { "openai/outputTemplate": RESOURCE_URI, "openai/widgetAccessible": true, "openai/toolInvocation/invoking": "Loading CrownThrive Asset Fabric evidence…", "openai/toolInvocation/invoked": "Asset Fabric evidence loaded" } : {} };
}

async function execute(name: string, args: any, actor: Actor) {
  switch (name) {
    case "assets.status": return await rpc("crownthrive_asset_fabric_status");
    case "assets.search": return await rpc("crownthrive_asset_fabric_search", { p_query: optional(args?.query), p_pallet_id: optional(args?.pallet_id), p_asset_type: optional(args?.asset_type), p_deployment_profile: optional(args?.deployment_profile), p_limit: Number(args?.limit ?? 50) });
    case "assets.get": return await rpc("crownthrive_asset_fabric_get", { p_asset_id: need(args, "asset_id") });
    case "assets.pallets.list": return await rpc("crownthrive_asset_fabric_list", { p_dimension: "pallets", p_value: optional(args?.pallet_id), p_limit: Number(args?.limit ?? 500) });
    case "assets.kernels.list": return await rpc("crownthrive_asset_fabric_list", { p_dimension: "kernels", p_value: null, p_limit: Number(args?.limit ?? 500) });
    case "assets.plugins.list": return await rpc("crownthrive_asset_fabric_list", { p_dimension: "plugins", p_value: null, p_limit: Number(args?.limit ?? 500) });
    case "assets.executables.list": return await rpc("crownthrive_asset_fabric_list", { p_dimension: "executables", p_value: null, p_limit: Number(args?.limit ?? 500) });
    case "assets.scripts.list": return await rpc("crownthrive_asset_fabric_list", { p_dimension: "scripts", p_value: null, p_limit: Number(args?.limit ?? 500) });
    case "assets.dependencies": return await rpc("crownthrive_asset_fabric_dependencies", { p_asset_id: need(args, "asset_id"), p_direction: optional(args?.direction) ?? "both" });
    case "assets.verify": requireGoverned(actor); return await rpc("crownthrive_asset_fabric_verify", { p_asset_id: optional(args?.asset_id) });
    case "assets.scrutinize": requireGoverned(actor); return await rpc("crownthrive_asset_fabric_scrutinize", { p_asset_id: optional(args?.asset_id) });
    case "assets.custody.status": return await rpc("crownthrive_asset_fabric_custody_status");
    case "assets.gaps.scan": requireGoverned(actor); return await rpc("crownthrive_asset_fabric_gap_scan");
    case "assets.receipts.list": return await rpc("crownthrive_asset_fabric_receipts", { p_subject_id: optional(args?.asset_id), p_limit: Number(args?.limit ?? 100) });
    case "assets.generate.plan":
    case "assets.materialize.plan":
    case "assets.package.plan":
    case "assets.lifecycle.transition.plan":
    case "assets.supersede.plan":
    case "assets.commercialization.plan": {
      requireGoverned(actor);
      const operations: Record<string, string> = { "assets.generate.plan": "generate", "assets.materialize.plan": "materialize", "assets.package.plan": "package", "assets.lifecycle.transition.plan": "lifecycle_transition", "assets.supersede.plan": "supersede", "assets.commercialization.plan": "commercialization" };
      return await rpc("crownthrive_asset_fabric_plan", { p_operation: operations[name], p_asset_id: optional(args?.asset_id), p_arguments: object(args?.arguments), p_evidence_refs: refs(args?.evidence_refs) });
    }
    default: throw new Error("unknown_tool");
  }
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return respond({ error: "method_not_allowed" }, 405);
    const auth = await authorize(req);
    if (!auth.ok) return respond({ error: auth.reason }, 403);
    const input = await parse(req);
    if (input?.jsonrpc === "2.0") {
      const id = input.id ?? null;
      if (input.method === "server/discover") return rpcResult(id, { resultType: "complete", supportedVersions: [MCP_VERSION], capabilities: { tools: {}, resources: {} }, _meta: { "io.modelcontextprotocol/serverInfo": SERVER }, instructions: "JWT/admin-only CrownThrive Asset Fabric. It exposes sanitized package contracts, plans, verification and scrutiny. It never returns credentials, private identities, protected bodies or D3/sovereign/provider-write authority.", ttlMs: 30000, cacheScope: "private" });
      if (input.method === "tools/list") return rpcResult(id, { resultType: "complete", tools: TOOLS.map(descriptor), ttlMs: 30000, cacheScope: "private" });
      if (input.method === "resources/list") return rpcResult(id, { resultType: "complete", resources: [{ uri: RESOURCE_URI, name: "CrownThrive Asset Fabric Dashboard", description: "Public-safe controlled-test asset inventory and hold dashboard.", mimeType: "text/html+skybridge", _meta: { "openai/widgetDescription": "Displays sanitized CrownThrive asset-catalog counts and lifecycle holds.", "openai/widgetPrefersBorder": true, "openai/widgetCSP": { connect_domains: [], resource_domains: [] } } }], ttlMs: 30000, cacheScope: "private" });
      if (input.method === "resources/read") { const uri = String(input?.params?.uri ?? ""); if (uri !== RESOURCE_URI) return rpcError(id, -32602, "Unknown widget resource", 404); return rpcResult(id, { contents: [{ uri: RESOURCE_URI, mimeType: "text/html+skybridge", text: WIDGET_HTML, _meta: { "openai/widgetDescription": "Displays sanitized CrownThrive asset-catalog counts and lifecycle holds.", "openai/widgetPrefersBorder": true, "openai/widgetCSP": { connect_domains: [], resource_domains: [] } } }] }); }
      if (input.method === "tools/call") { const name = String(input?.params?.name ?? ""); if (!TOOLS.some((tool) => tool.name === name)) return rpcError(id, -32602, "Unknown Asset Fabric tool", 400); const value = await execute(name, input?.params?.arguments ?? {}, auth.actor); return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: JSON.stringify(value) }], structuredContent: value, isError: false, _meta: { actor: auth.actor.id, secretExposed: false, privateIdentityExposed: false, providerWritePerformed: false, D3Auto: false, sovereignVoteEffect: false } }); }
      return rpcError(id, -32601, "Method not found", 404);
    }
    if (input?.action === "health") return respond({ service: "ct.mcp.crownthrive-asset-fabric", version: "0.1.0", stage: "controlled_test", authenticated_actor: auth.actor.id, candidate_asset_records: 5760, tools: TOOLS.map((tool) => tool.name), resources: [RESOURCE_URI], installed: false, submitted: false, published: false, provider_write_enabled: false, checkout_enabled: false, entitlement_active: false, secret_exposed: false, private_identity_exposed: false, D3_auto: false, sovereign_vote_effect: false });
    return respond({ error: "unknown_action" }, 400);
  } catch (error) {
    const message = error instanceof Error ? error.message : "asset_fabric_control_error";
    return respond({ error: message.slice(0, 240), provider_write_enabled: false, checkout_enabled: false, entitlement_active: false, secret_exposed: false, private_identity_exposed: false, D3_auto: false, sovereign_vote_effect: false }, message === "request_too_large" ? 413 : 400);
  }
});
