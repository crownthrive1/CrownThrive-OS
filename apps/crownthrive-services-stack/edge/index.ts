import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
const MCP_VERSION = "2026-07-28";
const SERVER = { name: "CrownThrive Services Stack", version: "0.1.0" };
const RESOURCE_URI = "ui://crownthrive/services-stack-dashboard.html";
const MAX_BYTES = 196608;
const ADMIN_EMAILS = new Set(["contact@crownthrive.com", "jones.usmc.kj@gmail.com"]);
const ADMIN_ROLES = new Set(["founder", "super_admin", "css_admin", "integration_admin", "chlom_admin"]);
const WIDGET_HTML = await Deno.readTextFile(new URL("./widget.html", import.meta.url));

type Actor = { id: string; serviceRole: boolean; founder: boolean };
type Tool = { name: string; description: string; risk: "D0" | "D1" | "D2"; readOnly: boolean; widget?: boolean; inputSchema: Record<string, unknown> };
const closed = (properties: Record<string, unknown> = {}, required: string[] = []) => ({ type: "object", properties, required, additionalProperties: false });
const text = { type: "string" };
const limit = { type: "integer", minimum: 1, maximum: 500 };
const evidence = { type: "array", items: { type: "string" } };
const TOOLS: Tool[] = [
  { name: "css.status", description: "Return sanitized shared-service, CHLOM CaaS, provider, contract, route, asset, and certification state.", risk: "D0", readOnly: true, widget: true, inputSchema: closed() },
  { name: "css.services.list", description: "List the fourteen CSS lanes and lifecycle states.", risk: "D0", readOnly: true, widget: true, inputSchema: closed({ state: text, limit }) },
  { name: "css.services.get", description: "Read one lane with dependencies, provider candidates, controls, routes, and candidate SLO state.", risk: "D0", readOnly: true, inputSchema: closed({ lane_id: text }, ["lane_id"]) },
  { name: "css.providers.list", description: "List replaceable provider bindings and evidence state. Provider capability is not CrownThrive deployment.", risk: "D0", readOnly: true, inputSchema: closed({ lane_id: text, limit }) },
  { name: "css.contracts.list", description: "List public-safe exact-version CSS contracts and digests.", risk: "D0", readOnly: true, inputSchema: closed({ lane_id: text, limit }) },
  { name: "css.controls.list", description: "List CHLOM CaaS controls and evidence classes. These are not professional certifications.", risk: "D0", readOnly: true, inputSchema: closed({ lane_id: text, limit }) },
  { name: "css.routes.list", description: "List sanitized routes, provider bindings, failover candidates, rollback, readback, and certification states.", risk: "D0", readOnly: true, inputSchema: closed({ lane_id: text, limit }) },
  { name: "css.readiness.evaluate", description: "Evaluate system and evidence readiness with Vault-protected scoring. It does not create legal or professional certification.", risk: "D1", readOnly: false, inputSchema: closed({ lane_id: text, features: { type: "object" } }, ["lane_id", "features"]) },
  { name: "css.controls.map", description: "Map CHLOM CaaS controls and evidence to a lane without provider execution.", risk: "D2", readOnly: false, inputSchema: closed({ lane_id: text, control_ids: { type: "array", items: text }, owner_agent_id: text, verifier_agent_id: text, evidence_refs: evidence }, ["lane_id", "control_ids", "owner_agent_id", "verifier_agent_id"]) },
  { name: "css.gaps.scan", description: "Detect missing provider, contract, control, evidence, route, continuity, asset, and certification gates.", risk: "D1", readOnly: false, widget: true, inputSchema: closed() },
  { name: "css.bind.plan", description: "Create a non-executing provider-binding plan with exact contract and evidence requirements.", risk: "D2", readOnly: false, inputSchema: closed({ lane_id: text, candidate_service_id: text, contract_id: text, owner_agent_id: text, verifier_agent_id: text, evidence_refs: evidence }, ["lane_id", "candidate_service_id", "owner_agent_id", "verifier_agent_id"]) },
  { name: "css.failover.plan", description: "Create a bounded failover, rollback, compensation, and readback plan. It never silently reroutes a service.", risk: "D2", readOnly: false, inputSchema: closed({ lane_id: text, source_binding_id: text, target_binding_id: text, owner_agent_id: text, verifier_agent_id: text, evidence_refs: evidence }, ["lane_id", "source_binding_id", "target_binding_id", "owner_agent_id", "verifier_agent_id"]) },
  { name: "css.certification.submit", description: "Submit independent system/evidence certification for a CSS subject. It is not legal, regulatory, tax, accessibility, cybersecurity, or other professional certification.", risk: "D2", readOnly: false, inputSchema: closed({ subject_kind: { type: "string", enum: ["lane", "contract", "provider_binding", "route", "control_map", "plugin"] }, subject_id: text, subject_version: text, features: { type: "object" }, evidence_refs: evidence, verifier_agent_id: text, requested_state: text }, ["subject_kind", "subject_id", "subject_version", "features", "evidence_refs", "verifier_agent_id"]) },
  { name: "css.receipts.list", description: "List sanitized append-only CSS and CaaS receipts.", risk: "D0", readOnly: true, inputSchema: closed({ subject_id: text, limit }) }
];

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff", "referrer-policy": "no-referrer" } });
}
function rpcResult(id: unknown, result: unknown): Response { return respond({ jsonrpc: "2.0", id, result }); }
function rpcError(id: unknown, code: number, message: string, status = 400): Response { return respond({ jsonrpc: "2.0", id, error: { code, message } }, status); }
async function rpc(name: string, body: Record<string, unknown> = {}) {
  if (!SUPABASE_URL || !SERVICE_ROLE) throw new Error("CSS_RUNTIME_NOT_CONFIGURED");
  const result = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, { method: "POST", headers: { "content-type": "application/json", apikey: SERVICE_ROLE, authorization: `Bearer ${SERVICE_ROLE}` }, body: JSON.stringify(body) });
  const raw = await result.text();
  if (!result.ok) {
    let detail = `RPC_${name}_${result.status}`;
    try { const parsed = JSON.parse(raw); detail = String(parsed?.message ?? parsed?.hint ?? detail).slice(0, 240); } catch { /* do not reflect arbitrary backend body */ }
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
  const result = await fetch(`${SUPABASE_URL}/auth/v1/user`, { headers: { apikey: ANON_KEY, authorization: `Bearer ${token}` } });
  if (!result.ok) return { ok: false, actor: { id: "unknown", serviceRole: false, founder: false }, reason: "invalid_user_token" };
  const user: any = await result.json();
  const email = String(user?.email ?? "").toLowerCase();
  const roles: string[] = [];
  if (typeof user?.app_metadata?.role === "string") roles.push(user.app_metadata.role);
  if (Array.isArray(user?.app_metadata?.roles)) for (const role of user.app_metadata.roles) if (typeof role === "string") roles.push(role);
  const founder = ADMIN_EMAILS.has(email);
  const allowed = founder || roles.some((role) => ADMIN_ROLES.has(role));
  return allowed ? { ok: true, actor: { id: email || "css_admin", serviceRole: false, founder } } : { ok: false, actor: { id: email || "authenticated", serviceRole: false, founder: false }, reason: "css_admin_required" };
}
async function parse(req: Request) {
  const length = Number(req.headers.get("content-length") ?? 0);
  if (length > MAX_BYTES) throw new Error("request_too_large");
  const raw = await req.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_BYTES) throw new Error("request_too_large");
  return JSON.parse(raw);
}
const optional = (value: unknown): string | null => typeof value === "string" && value.trim() ? value.trim() : null;
function need(args: any, key: string): string { const value = optional(args?.[key]); if (!value) throw new Error(`missing_${key}`); return value; }
const object = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const refs = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim()) : [];
function governed(actor: Actor) { if (!actor.serviceRole && !actor.founder) throw new Error("founder_or_service_role_required"); }
function descriptor(tool: Tool) {
  return { name: tool.name, title: tool.name.replaceAll(".", " "), description: tool.description, inputSchema: tool.inputSchema, outputSchema: { type: "object" }, annotations: { readOnlyHint: tool.readOnly, destructiveHint: false, idempotentHint: true, openWorldHint: false }, _meta: tool.widget ? { "openai/outputTemplate": RESOURCE_URI, "openai/widgetAccessible": true, "openai/toolInvocation/invoking": "Loading CrownThrive shared-service evidence…", "openai/toolInvocation/invoked": "Services Stack evidence loaded" } : {} };
}

async function execute(name: string, args: any, actor: Actor) {
  switch (name) {
    case "css.status": return await rpc("crownthrive_css_status");
    case "css.services.list": return { services: await rpc("crownthrive_css_services", { p_state: optional(args?.state), p_limit: Number(args?.limit ?? 100) }) };
    case "css.services.get": return await rpc("crownthrive_css_service_get", { p_lane_id: need(args, "lane_id") });
    case "css.providers.list": return { providers: await rpc("crownthrive_css_providers", { p_lane_id: optional(args?.lane_id), p_limit: Number(args?.limit ?? 200) }) };
    case "css.contracts.list": return { contracts: await rpc("crownthrive_css_contracts", { p_lane_id: optional(args?.lane_id), p_limit: Number(args?.limit ?? 200) }) };
    case "css.controls.list": return { controls: await rpc("crownthrive_css_controls", { p_lane_id: optional(args?.lane_id), p_limit: Number(args?.limit ?? 200) }) };
    case "css.routes.list": return { routes: await rpc("crownthrive_css_routes", { p_lane_id: optional(args?.lane_id), p_limit: Number(args?.limit ?? 200) }) };
    case "css.readiness.evaluate": governed(actor); return await rpc("crownthrive_css_readiness_evaluate", { p_lane_id: need(args, "lane_id"), p_features: object(args?.features) });
    case "css.controls.map": governed(actor); return await rpc("crownthrive_css_controls_map", { p_lane_id: need(args, "lane_id"), p_control_ids: refs(args?.control_ids), p_owner_agent_id: need(args, "owner_agent_id"), p_verifier_agent_id: need(args, "verifier_agent_id"), p_evidence_refs: refs(args?.evidence_refs) });
    case "css.gaps.scan": governed(actor); return { gaps: await rpc("crownthrive_css_gap_scan") };
    case "css.bind.plan": governed(actor); return await rpc("crownthrive_css_bind_plan", { p_lane_id: need(args, "lane_id"), p_candidate_service_id: need(args, "candidate_service_id"), p_contract_id: optional(args?.contract_id), p_owner_agent_id: need(args, "owner_agent_id"), p_verifier_agent_id: need(args, "verifier_agent_id"), p_evidence_refs: refs(args?.evidence_refs) });
    case "css.failover.plan": governed(actor); return await rpc("crownthrive_css_failover_plan", { p_lane_id: need(args, "lane_id"), p_source_binding_id: need(args, "source_binding_id"), p_target_binding_id: need(args, "target_binding_id"), p_owner_agent_id: need(args, "owner_agent_id"), p_verifier_agent_id: need(args, "verifier_agent_id"), p_evidence_refs: refs(args?.evidence_refs) });
    case "css.certification.submit": governed(actor); { const evidenceRefs = refs(args?.evidence_refs); if (!evidenceRefs.length) throw new Error("evidence_refs_required"); return await rpc("crownthrive_css_certification_submit", { p_subject_kind: need(args, "subject_kind"), p_subject_id: need(args, "subject_id"), p_subject_version: need(args, "subject_version"), p_features: object(args?.features), p_evidence_refs: evidenceRefs, p_verifier_agent_id: need(args, "verifier_agent_id"), p_requested_state: optional(args?.requested_state) ?? "verified" }); }
    case "css.receipts.list": return { receipts: await rpc("crownthrive_css_receipts", { p_subject_id: optional(args?.subject_id), p_limit: Number(args?.limit ?? 100) }) };
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
      if (input.method === "server/discover") return rpcResult(id, { resultType: "complete", supportedVersions: [MCP_VERSION], capabilities: { tools: {}, resources: {} }, _meta: { "io.modelcontextprotocol/serverInfo": SERVER }, instructions: "JWT/admin-only CrownThrive Services Stack. It exposes sanitized shared-service contracts, provider bindings, CHLOM CaaS controls, readiness, plans, and receipts. It never returns credentials, private identities, protected algorithms, private evidence, D3 authority, sovereign votes, or inherited provider-write authority.", ttlMs: 30000, cacheScope: "private" });
      if (input.method === "tools/list") return rpcResult(id, { resultType: "complete", tools: TOOLS.map(descriptor), ttlMs: 30000, cacheScope: "private" });
      if (input.method === "resources/list") return rpcResult(id, { resultType: "complete", resources: [{ uri: RESOURCE_URI, name: "CrownThrive Services Stack Dashboard", description: "Public-safe controlled-test dashboard for CSS lanes, providers, contracts, CaaS controls, routes, and evidence gaps.", mimeType: "text/html+skybridge", _meta: { "openai/widgetDescription": "Displays sanitized CrownThrive Services Stack and CHLOM CaaS evidence.", "openai/widgetPrefersBorder": true, "openai/widgetCSP": { connect_domains: [], resource_domains: [] } } }], ttlMs: 30000, cacheScope: "private" });
      if (input.method === "resources/read") { const uri = String(input?.params?.uri ?? ""); if (uri !== RESOURCE_URI) return rpcError(id, -32602, "Unknown widget resource", 404); return rpcResult(id, { contents: [{ uri: RESOURCE_URI, mimeType: "text/html+skybridge", text: WIDGET_HTML, _meta: { "openai/widgetDescription": "Displays sanitized CrownThrive Services Stack and CHLOM CaaS evidence.", "openai/widgetPrefersBorder": true, "openai/widgetCSP": { connect_domains: [], resource_domains: [] } } }] }); }
      if (input.method === "tools/call") { const name = String(input?.params?.name ?? ""); if (!TOOLS.some((tool) => tool.name === name)) return rpcError(id, -32602, "Unknown CSS tool", 400); const value = await execute(name, input?.params?.arguments ?? {}, auth.actor); return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: JSON.stringify(value) }], structuredContent: value, isError: false, _meta: { actor: auth.actor.id, secretExposed: false, privateIdentityExposed: false, protectedImplementationExposed: false, providerWritePerformed: false, professionalCertification: false, D3Auto: false, sovereignVoteEffect: false } }); }
      return rpcError(id, -32601, "Method not found", 404);
    }
    if (input?.action === "health") return respond({ service: "ct.mcp.crownthrive-services-stack", version: "0.1.0", stage: "controlled_test", authenticated_actor: auth.actor.id, service_lanes: 14, caas_controls: 28, tools: TOOLS.map((tool) => tool.name), resources: [RESOURCE_URI], installed: false, submitted: false, published: false, provider_write_enabled: false, checkout_enabled: false, entitlement_active: false, professional_certification: false, secret_exposed: false, private_identity_exposed: false, protected_implementation_exposed: false, D3_auto: false, sovereign_vote_effect: false });
    return respond({ error: "unknown_action" }, 400);
  } catch (error) {
    const message = error instanceof Error ? error.message : "css_runtime_error";
    return respond({ error: message.slice(0, 240), provider_write_enabled: false, checkout_enabled: false, entitlement_active: false, professional_certification: false, secret_exposed: false, private_identity_exposed: false, protected_implementation_exposed: false, D3_auto: false, sovereign_vote_effect: false }, message === "request_too_large" ? 413 : 400);
  }
});
