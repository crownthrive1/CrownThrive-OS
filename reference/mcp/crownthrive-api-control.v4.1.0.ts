import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import Ajv2020 from "npm:ajv@8.17.1/dist/2020.js";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
const IO_BASE = "https://crownthrive.io/api";
const SEO_BASE = "https://seo.thrivetools.io/api";
const MCP_VERSION = "2026-07-28";
const MCP_SERVER = { name: "CrownThrive API Control", version: "4.1.0" };
const ADMIN_EMAILS = new Set(["contact@crownthrive.com", "jones.usmc.kj@gmail.com"]);
const ADMIN_ROLES = new Set(["founder", "super_admin", "integration_admin"]);
const MAX_REQUEST_BYTES = 262_144;
const MAX_IO_PROVIDER_BYTES = 1_000_000;
const MAX_SEO_PROVIDER_BYTES = 3_000_000;
const IO_TIMEOUT_MS = 8_000;
const SEO_TIMEOUT_MS = 10_000;
const GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com";
const GITHUB_OIDC_AUDIENCE = "crownthrive-mcp-certification";
const GITHUB_CERT_REPOSITORY = "crownthrive1/CrownThrive-Support";
const GITHUB_CERT_REPOSITORY_ID = "1336348391";
const GITHUB_CERT_OWNER = "crownthrive1";
const GITHUB_CERT_REF = "refs/heads/main";
const GITHUB_CERT_WORKFLOW_REF = "crownthrive1/CrownThrive-Support/.github/workflows/mcp-external-certification.yml@refs/heads/main";
const GITHUB_CERT_EVENT = "workflow_dispatch";
const GITHUB_JWKS_URL = "https://token.actions.githubusercontent.com/.well-known/jwks";
const ajv = new Ajv2020({ allErrors: true, strict: false, validateFormats: false });

type Risk = "D0" | "D1";
type Operation = { path: string; method: "GET"; risk: Risk };
type Actor = { id: string; founder: boolean; serviceRole: boolean; certifier: boolean; workflowSha?: string };
type JsonRpcId = string | number | null;
type EndpointPolicy = { service_id: string; operation_key: string; http_method: string; path_template: string; risk_class: string; mutation: boolean; source_state: string; enabled: boolean };
type CertMode = "none" | "conformance" | "schema-capture" | "live-proof";

const IO_OPS: Record<string, Operation> = {
  "user.read": { path: "/user", method: "GET", risk: "D0" },
  "links.list": { path: "/links/", method: "GET", risk: "D0" },
  "statistics.read": { path: "/statistics/", method: "GET", risk: "D0" },
  "projects.list": { path: "/projects/", method: "GET", risk: "D0" },
  "pixels.list": { path: "/pixels/", method: "GET", risk: "D0" },
  "splash_pages.list": { path: "/splash-pages/", method: "GET", risk: "D0" },
  "qr_codes.list": { path: "/qr-codes/", method: "GET", risk: "D0" },
  "data.list": { path: "/data/", method: "GET", risk: "D0" },
  "notification_handlers.list": { path: "/notification-handlers/", method: "GET", risk: "D0" },
  "domains.list": { path: "/domains/", method: "GET", risk: "D0" },
  "teams.list": { path: "/teams/", method: "GET", risk: "D0" },
  "teams_member.list": { path: "/teams-member/", method: "GET", risk: "D0" },
  "payments.list": { path: "/payments/", method: "GET", risk: "D1" },
  "logs.list": { path: "/logs/", method: "GET", risk: "D1" },
};
const SEO_OPS: Record<string, Operation> = {
  "user.read": { path: "/user", method: "GET", risk: "D0" },
  "websites.list": { path: "/websites", method: "GET", risk: "D0" },
  "audits.list": { path: "/audits", method: "GET", risk: "D0" },
  "audits.archived.list": { path: "/archived-audits", method: "GET", risk: "D0" },
  "notification_handlers.list": { path: "/notification-handlers", method: "GET", risk: "D0" },
  "custom_domains.list": { path: "/domains", method: "GET", risk: "D0" },
  "teams.list": { path: "/teams", method: "GET", risk: "D0" },
  "teams_member.read": { path: "/teams-member", method: "GET", risk: "D0" },
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" } });
}
function rpcError(id: JsonRpcId, code: number, message: string, status = 400, data?: unknown) {
  return json({ jsonrpc: "2.0", id, error: { code, message, ...(data === undefined ? {} : { data }) } }, status);
}
function rpcResult(id: JsonRpcId, result: unknown, status = 200) { return json({ jsonrpc: "2.0", id, result }, status); }
async function rpc(name: string, body: Record<string, unknown> = {}) {
  if (!SUPABASE_URL || !SERVICE_ROLE) throw new Error("SUPABASE_RUNTIME_NOT_CONFIGURED");
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, { method: "POST", headers: { "content-type": "application/json", "apikey": SERVICE_ROLE, "authorization": `Bearer ${SERVICE_ROLE}` }, body: JSON.stringify(body) });
  const text = await response.text();
  if (!response.ok) throw new Error(`RPC_${name}_${response.status}`);
  try { return text ? JSON.parse(text) : null; } catch { return text; }
}
async function runtimeSecret(name: string): Promise<string> {
  const value = await rpc("get_runtime_secret", { secret_name: name });
  return typeof value === "string" ? value : "";
}

function base64UrlBytes(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}
function decodeJwtPart(value: string): any {
  return JSON.parse(new TextDecoder().decode(base64UrlBytes(value)));
}
function audienceMatches(aud: unknown): boolean {
  return aud === GITHUB_OIDC_AUDIENCE || (Array.isArray(aud) && aud.includes(GITHUB_OIDC_AUDIENCE));
}
async function verifyGitHubCertifierJwt(token: string): Promise<Actor | null> {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  let header: any, claims: any;
  try { header = decodeJwtPart(parts[0]); claims = decodeJwtPart(parts[1]); } catch { return null; }
  if (header?.alg !== "RS256" || typeof header?.kid !== "string") return null;
  if (claims?.iss !== GITHUB_OIDC_ISSUER || !audienceMatches(claims?.aud)) return null;
  const now = Math.floor(Date.now() / 1000);
  if (typeof claims?.exp !== "number" || claims.exp < now - 30) return null;
  if (typeof claims?.nbf === "number" && claims.nbf > now + 30) return null;
  if (typeof claims?.iat !== "number" || claims.iat > now + 30 || claims.iat < now - 900) return null;
  if (claims?.repository !== GITHUB_CERT_REPOSITORY || String(claims?.repository_id ?? "") !== GITHUB_CERT_REPOSITORY_ID) return null;
  if (claims?.repository_owner !== GITHUB_CERT_OWNER || claims?.ref !== GITHUB_CERT_REF || claims?.ref_type !== "branch") return null;
  if (claims?.workflow_ref !== GITHUB_CERT_WORKFLOW_REF || claims?.event_name !== GITHUB_CERT_EVENT) return null;
  if (claims?.repository_visibility !== "public") return null;
  if (typeof claims?.workflow_sha !== "string" || !/^[0-9a-f]{40}$/.test(claims.workflow_sha)) return null;
  const jwksResponse = await fetch(GITHUB_JWKS_URL, { headers: { "accept": "application/json" } });
  if (!jwksResponse.ok) return null;
  const jwks: any = await jwksResponse.json();
  const jwk = Array.isArray(jwks?.keys) ? jwks.keys.find((key: any) => key?.kid === header.kid && key?.kty === "RSA") : null;
  if (!jwk) return null;
  let key: CryptoKey;
  try { key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]); } catch { return null; }
  const signingInput = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  let valid = false;
  try { valid = await crypto.subtle.verify({ name: "RSASSA-PKCS1-v1_5" }, key, base64UrlBytes(parts[2]), signingInput); } catch { return null; }
  if (!valid) return null;
  return { id: `github-actions:${claims.run_id ?? "unknown"}:${claims.run_attempt ?? "1"}`, founder: false, serviceRole: false, certifier: true, workflowSha: claims.workflow_sha };
}
async function authorize(req: Request): Promise<{ ok: boolean; actor: Actor; reason?: string }> {
  const auth = req.headers.get("authorization") ?? "";
  const token = auth.toLowerCase().startsWith("bearer ") ? auth.slice(7).trim() : "";
  if (!token) return { ok: false, actor: { id: "anonymous", founder: false, serviceRole: false, certifier: false }, reason: "missing_bearer" };
  if (SERVICE_ROLE && token === SERVICE_ROLE) return { ok: true, actor: { id: "service_role", founder: true, serviceRole: true, certifier: false } };
  try {
    const parts = token.split(".");
    if (parts.length === 3) {
      const claims = decodeJwtPart(parts[1]);
      if (claims?.iss === GITHUB_OIDC_ISSUER) {
        const certifier = await verifyGitHubCertifierJwt(token);
        return certifier ? { ok: true, actor: certifier } : { ok: false, actor: { id: "github-actions-rejected", founder: false, serviceRole: false, certifier: false }, reason: "invalid_certifier_oidc" };
      }
    }
  } catch {}
  if (!SUPABASE_URL || !ANON_KEY) return { ok: false, actor: { id: "unknown", founder: false, serviceRole: false, certifier: false }, reason: "auth_runtime_unavailable" };
  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, { headers: { "apikey": ANON_KEY, "authorization": `Bearer ${token}` } });
  if (!response.ok) return { ok: false, actor: { id: "unknown", founder: false, serviceRole: false, certifier: false }, reason: "invalid_user_token" };
  const user: any = await response.json();
  const email = String(user?.email ?? "").toLowerCase();
  const roles = new Set<string>();
  if (typeof user?.app_metadata?.role === "string") roles.add(user.app_metadata.role);
  if (Array.isArray(user?.app_metadata?.roles)) for (const role of user.app_metadata.roles) if (typeof role === "string") roles.add(role);
  const founder = ADMIN_EMAILS.has(email);
  const allowed = founder || [...roles].some((r) => ADMIN_ROLES.has(r));
  return allowed ? { ok: true, actor: { id: email || "integration_admin", founder, serviceRole: false, certifier: false } } : { ok: false, actor: { id: email || "authenticated", founder: false, serviceRole: false, certifier: false }, reason: "admin_required" };
}

function validateOrigin(req: Request): boolean {
  const origin = req.headers.get("origin");
  if (!origin) return true;
  try {
    const u = new URL(origin);
    if (u.protocol !== "https:") return false;
    return u.hostname === "crownthrive.com" || u.hostname.endsWith(".crownthrive.com") || u.hostname === "crownthrive.io" || u.hostname.endsWith(".crownthrive.io");
  } catch { return false; }
}
function requestMediaType(req: Request): string { return (req.headers.get("content-type") ?? "").split(";", 1)[0].trim().toLowerCase(); }
function declaredLength(req: Request): number | null { const value = req.headers.get("content-length"); if (!value) return null; const parsed = Number(value); return Number.isFinite(parsed) && parsed >= 0 ? parsed : null; }
async function readBoundedBytes(stream: ReadableStream<Uint8Array> | null, maxBytes: number): Promise<Uint8Array> {
  if (!stream) return new Uint8Array();
  const reader = stream.getReader(); const chunks: Uint8Array[] = []; let total = 0;
  try { while (true) { const { value, done } = await reader.read(); if (done) break; if (!value) continue; total += value.byteLength; if (total > maxBytes) { try { await reader.cancel("body_size_limit"); } catch {} throw new Error("BODY_SIZE_LIMIT"); } chunks.push(value); } }
  finally { try { reader.releaseLock(); } catch {} }
  const out = new Uint8Array(total); let offset = 0; for (const chunk of chunks) { out.set(chunk, offset); offset += chunk.byteLength; } return out;
}
async function parseBoundedJson(req: Request): Promise<{ ok: true; input: any } | { ok: false; kind: "too_large" | "invalid_json" }> {
  const length = declaredLength(req); if (length !== null && length > MAX_REQUEST_BYTES) return { ok: false, kind: "too_large" };
  try { const bytes = await readBoundedBytes(req.body, MAX_REQUEST_BYTES); const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); return { ok: true, input: JSON.parse(text) }; }
  catch (error) { return { ok: false, kind: error instanceof Error && error.message === "BODY_SIZE_LIMIT" ? "too_large" : "invalid_json" }; }
}
function safeParams(input: unknown): URLSearchParams {
  const params = new URLSearchParams(); if (!input || typeof input !== "object" || Array.isArray(input)) return params;
  for (const [key, value] of Object.entries(input as Record<string, unknown>).slice(0, 20)) { if (!/^[A-Za-z0-9_\-]+$/.test(key)) continue; if (value === null || value === undefined) continue; if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") { const s = String(value); if (s.length <= 500) params.set(key, s); } }
  return params;
}
function sanitize(value: unknown, depth = 0): unknown {
  if (depth > 16) return "[depth-limited]";
  if (Array.isArray(value)) return value.slice(0, 500).map((v) => sanitize(v, depth + 1));
  if (value && typeof value === "object") { const out: Record<string, unknown> = {}; for (const [key, child] of Object.entries(value as Record<string, unknown>)) { if (/password|secret|api[_-]?key|authorization|access[_-]?token|refresh[_-]?token|anti[_-]?phishing/i.test(key)) { out[key] = "[redacted]"; continue; } if (key.toLowerCase() === "billing") { out[key] = "[restricted]"; continue; } out[key] = sanitize(child, depth + 1); } return out; }
  if (typeof value === "string" && value.length > 100_000) return value.slice(0, 100_000) + "…[truncated]";
  return value;
}
async function sha256Bytes(bytes: Uint8Array): Promise<string> { const digest = await crypto.subtle.digest("SHA-256", bytes); return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join(""); }
async function recordRequest(args: { service: string; operation: string; method: string; path: string; status: number; success: boolean; actor: string; latency: number; responseHash: string; notes?: string }) {
  try { await rpc("integration_record_request", { p_service_id: args.service, p_operation_key: args.operation, p_http_method: args.method, p_path_template: args.path, p_http_status: args.status, p_success: args.success, p_actor: args.actor, p_latency_ms: args.latency, p_response_sha256: args.responseHash, p_notes: args.notes ?? null }); } catch {}
}
async function rateAllowed(service: string, actor: string, maxRequests = 30) { try { const result: any = await rpc("integration_rate_check", { p_service_id: service, p_actor: actor, p_window_seconds: 60, p_max_requests: maxRequests }); return Boolean(result?.allowed); } catch { return false; } }
async function endpointPolicy(service: string, operation: string): Promise<EndpointPolicy | null> { try { const value: any = await rpc("integration_endpoint_policy_check", { p_service_id: service, p_operation_key: operation }); return value && typeof value === "object" ? value as EndpointPolicy : null; } catch { return null; } }
function catalogAllows(policy: EndpointPolicy | null, service: string, operationKey: string, op: Operation): boolean { return Boolean(policy && policy.service_id === service && policy.operation_key === operationKey && policy.enabled === true && policy.mutation === false && policy.http_method === op.method && policy.path_template === op.path && policy.risk_class === op.risk && policy.source_state === "verified_read"); }
function makeAbortSignal(timeoutMs: number): { signal: AbortSignal; clear: () => void } { const controller = new AbortController(); const timer = setTimeout(() => controller.abort("provider_timeout"), timeoutMs); return { signal: controller.signal, clear: () => clearTimeout(timer) }; }

async function providerReadData(service: "crownthrive_io" | "thrivetools_seo", operationKey: string, paramsInput: unknown, actor: Actor) {
  const isSeo = service === "thrivetools_seo"; const ops = isSeo ? SEO_OPS : IO_OPS; const op = ops[operationKey];
  if (!op) return { protocolError: { code: -32602, message: `Unknown operation: ${operationKey}` } };
  const policy = await endpointPolicy(service, operationKey);
  if (!catalogAllows(policy, service, operationKey, op)) return { toolError: `Governed endpoint policy blocks ${service}:${operationKey}.` };
  if (op.risk === "D1" && !actor.founder && !actor.serviceRole) return { toolError: "Restricted read requires founder or service-role authority." };
  if (!(await rateAllowed(service, actor.id, isSeo ? 60 : 30))) return { toolError: `Rate limit reached for ${service}. Retry later.` };
  const apiKey = await runtimeSecret(isSeo ? "thrivetools_seo_api_key" : "crownthrive_io_api_key");
  if (!apiKey) return { toolError: `${service} credential access is blocked.` };
  const params = safeParams(paramsInput); const base = isSeo ? SEO_BASE : IO_BASE; const url = `${base}${op.path}${params.toString() ? `?${params.toString()}` : ""}`;
  const start = performance.now(); const timeout = makeAbortSignal(isSeo ? SEO_TIMEOUT_MS : IO_TIMEOUT_MS); let response: Response;
  try { response = await fetch(url, { method: "GET", signal: timeout.signal, headers: { "accept": "application/json", "authorization": `Bearer ${apiKey}` } }); }
  catch (error) { timeout.clear(); const latency = Math.round(performance.now() - start); const timedOut = error instanceof DOMException && error.name === "AbortError"; await recordRequest({ service, operation: operationKey, method: "GET", path: op.path, status: 0, success: false, actor: actor.id, latency, responseHash: "", notes: timedOut ? "provider_timeout" : "network_error" }); return { toolError: timedOut ? `${service} provider request timed out.` : `${service} network request failed.` }; }
  timeout.clear(); const latency = Math.round(performance.now() - start); const maxBytes = isSeo ? MAX_SEO_PROVIDER_BYTES : MAX_IO_PROVIDER_BYTES;
  const contentLength = Number(response.headers.get("content-length") ?? ""); if (Number.isFinite(contentLength) && contentLength > maxBytes) { await recordRequest({ service, operation: operationKey, method: "GET", path: op.path, status: response.status, success: false, actor: actor.id, latency, responseHash: "", notes: "response_size_limit_declared" }); return { toolError: "Provider response exceeded the control-plane size limit." }; }
  let bytes: Uint8Array; try { bytes = await readBoundedBytes(response.body, maxBytes); } catch { await recordRequest({ service, operation: operationKey, method: "GET", path: op.path, status: response.status, success: false, actor: actor.id, latency, responseHash: "", notes: "response_size_limit_stream" }); return { toolError: "Provider response exceeded the control-plane size limit." }; }
  const hash = await sha256Bytes(bytes); const mediaType = (response.headers.get("content-type") ?? "").split(";", 1)[0].trim().toLowerCase();
  if (!response.ok || mediaType !== "application/json") { await recordRequest({ service, operation: operationKey, method: "GET", path: op.path, status: response.status, success: false, actor: actor.id, latency, responseHash: hash, notes: "non_json_or_non_2xx_provider_response" }); return { toolError: `${service} returned an uncertified provider response.`, value: { service, operation: operationKey, provider_status: response.status, ok: false, evidence: { response_sha256: hash, latency_ms: latency, retrieved_at: new Date().toISOString(), timezone: "UTC" } } }; }
  let parsed: unknown; try { const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); parsed = text ? JSON.parse(text) : null; } catch { await recordRequest({ service, operation: operationKey, method: "GET", path: op.path, status: response.status, success: false, actor: actor.id, latency, responseHash: hash, notes: "invalid_json_provider_response" }); return { toolError: `${service} returned malformed JSON.`, value: { service, operation: operationKey, provider_status: response.status, ok: false, evidence: { response_sha256: hash, latency_ms: latency, retrieved_at: new Date().toISOString(), timezone: "UTC" } } }; }
  const data = sanitize(parsed); const payload = { service, operation: operationKey, provider_status: response.status, ok: true, data, evidence: { response_sha256: hash, latency_ms: latency, retrieved_at: new Date().toISOString(), timezone: "UTC" } };
  await recordRequest({ service, operation: operationKey, method: "GET", path: op.path, status: response.status, success: true, actor: actor.id, latency, responseHash: hash }); return { value: payload };
}

async function snapshot() { return await rpc("integration_control_snapshot", {}); }
function titleFromName(name: string) { return name.split(/[_\.\-]+/).filter(Boolean).map((v) => v.charAt(0).toUpperCase() + v.slice(1)).join(" "); }
function decodeMcpHeader(value: string | null): string | null { if (value === null) return null; if (value.startsWith("=?base64?") && value.endsWith("?=")) { try { const bin = atob(value.slice(9, -2)); return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))); } catch { return null; } } return value; }
function mcpVersionFromBody(input: any): string | null { const meta = input?.params?._meta; return typeof meta?.["io.modelcontextprotocol/protocolVersion"] === "string" ? meta["io.modelcontextprotocol/protocolVersion"] : null; }
function hasClientCapabilities(input: any): boolean { const caps = input?.params?._meta?.["io.modelcontextprotocol/clientCapabilities"]; return Boolean(caps && typeof caps === "object" && !Array.isArray(caps)); }
function validateMcpHeaders(req: Request, input: any): Response | null {
  const id: JsonRpcId = input?.id ?? null; const protocolHeader = req.headers.get("mcp-protocol-version"); const methodHeader = req.headers.get("mcp-method"); const bodyVersion = mcpVersionFromBody(input); const bodyMethod = typeof input?.method === "string" ? input.method : null; const bodyName = input?.method === "tools/call" && typeof input?.params?.name === "string" ? input.params.name : null; const nameHeader = decodeMcpHeader(req.headers.get("mcp-name"));
  if (!protocolHeader || !methodHeader || (bodyName !== null && nameHeader === null)) return rpcError(id, -32020, "Header mismatch: required MCP request metadata header is missing or malformed.", 400);
  if (protocolHeader !== bodyVersion || methodHeader !== bodyMethod || (bodyName !== null && nameHeader !== bodyName)) return rpcError(id, -32020, "Header mismatch: MCP request headers do not match the JSON-RPC body.", 400);
  if (protocolHeader !== MCP_VERSION) return rpcError(id, -32022, `Unsupported protocol version: ${protocolHeader}`, 400, { supported: [MCP_VERSION] });
  if (!hasClientCapabilities(input)) return rpcError(id, -32602, "Invalid params: required clientCapabilities metadata is missing.", 400);
  return null;
}
function isMcp(input: any, req: Request) { return req.headers.has("mcp-protocol-version") || req.headers.has("mcp-method") || typeof input?.method === "string"; }
function isMcpPreparse(req: Request) { return req.headers.has("mcp-protocol-version") || req.headers.has("mcp-method") || req.headers.has("mcp-name"); }
function isCentralDispatchService(serviceId: unknown): serviceId is "crownthrive_io" | "thrivetools_seo" { return serviceId === "crownthrive_io" || serviceId === "thrivetools_seo"; }
function certificationMode(req: Request, actor: Actor): CertMode {
  if (!actor.certifier) return "none";
  const value = (req.headers.get("x-crownthrive-certification-mode") ?? "conformance").trim().toLowerCase();
  return value === "schema-capture" || value === "live-proof" || value === "conformance" ? value : "conformance";
}
function certifierAllowsProviderDispatch(mode: CertMode, toolName: string): boolean {
  if (mode === "schema-capture") return true;
  if (mode === "live-proof") return toolName === "crownthrive_io_get_user" || toolName === "seo.user.read";
  return false;
}
async function mcpToolsList(id: JsonRpcId) {
  const state: any = await snapshot(); const rows = Array.isArray(state?.mcp_tools) ? state.mcp_tools : [];
  const tools = rows.filter((t: any) => t?.enabled === true && t?.requires_human_approval !== true && isCentralDispatchService(t?.service_id)).sort((a: any, b: any) => String(a.tool_name).localeCompare(String(b.tool_name))).map((t: any) => ({ name: String(t.tool_name), title: titleFromName(String(t.tool_name)), description: String(t.notes ?? `CrownThrive governed tool for ${t.operation_key}`), inputSchema: t.input_schema && typeof t.input_schema === "object" ? t.input_schema : { type: "object", additionalProperties: false }, outputSchema: t.output_schema && typeof t.output_schema === "object" ? t.output_schema : { type: "object" } }));
  return rpcResult(id, { resultType: "complete", tools, ttlMs: 60_000, cacheScope: "private" });
}
async function mcpToolCall(id: JsonRpcId, toolName: string, args: unknown, actor: Actor, mode: CertMode) {
  const state: any = await snapshot(); const rows = Array.isArray(state?.mcp_tools) ? state.mcp_tools : []; const tool = rows.find((t: any) => t?.tool_name === toolName);
  if (!tool || tool.enabled !== true || !isCentralDispatchService(tool.service_id)) return rpcError(id, -32602, `Unknown tool: ${toolName}`, 400);
  if (tool.requires_human_approval === true) return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: "Human approval is required before this tool can run." }], isError: true });
  const schema = tool.input_schema && typeof tool.input_schema === "object" ? tool.input_schema : { type: "object" }; let valid = false;
  try { valid = ajv.compile(schema)(args ?? {}); } catch { return rpcError(id, -32602, `Tool ${toolName} has an invalid input schema.`, 400); }
  if (!valid) return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: "Tool arguments failed schema validation." }], isError: true });
  if (actor.certifier && !certifierAllowsProviderDispatch(mode, toolName)) return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: "Certification conformance mode does not dispatch provider reads." }], structuredContent: { service: tool.service_id, operation: tool.operation_key, ok: false, certification_mode: mode, provider_dispatch: false }, isError: true });
  const result: any = await providerReadData(tool.service_id, String(tool.operation_key), args ?? {}, actor);
  if (result.protocolError) return rpcError(id, result.protocolError.code, result.protocolError.message, 400);
  if (result.toolError) { const structured = result.value ?? { service: tool.service_id, operation: tool.operation_key, ok: false, error: result.toolError }; return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: JSON.stringify(structured) }], structuredContent: structured, isError: true }); }
  const outputSchema = tool.output_schema && typeof tool.output_schema === "object" ? tool.output_schema : { type: "object" }; let outputValid = false;
  try { outputValid = ajv.compile(outputSchema)(result.value); } catch { return rpcError(id, -32603, `Tool ${toolName} has an invalid output schema.`, 500); }
  if (!outputValid) return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: "Provider output failed governed output-schema validation." }], isError: true });
  return rpcResult(id, { resultType: "complete", content: [{ type: "text", text: JSON.stringify(result.value) }], structuredContent: result.value, isError: false });
}
async function handleMcp(req: Request, input: any, actor: Actor) {
  const headerError = validateMcpHeaders(req, input); if (headerError) return headerError;
  const id: JsonRpcId = input?.id ?? null;
  if (input?.jsonrpc !== "2.0" || !(typeof input?.id === "string" || typeof input?.id === "number")) return rpcError(id, -32600, "Invalid Request", 400);
  if (input.method === "server/discover") return rpcResult(id, { resultType: "complete", supportedVersions: [MCP_VERSION], capabilities: { tools: {} }, _meta: { "io.modelcontextprotocol/serverInfo": MCP_SERVER }, instructions: "CrownThrive internal API control plane v4.1 candidate. Only governed, enabled, read-only central tools are exposed. GitHub OIDC certification authority is D0-only, workflow/ref/repository bound, non-sovereign, and provider-dispatch-disabled unless an explicit certification mode is selected. Dedicated CHLOM tools remain on the separate CHLOM MCP server. Mutating tools remain gated.", ttlMs: 60_000, cacheScope: "private" });
  if (input.method === "tools/list") return await mcpToolsList(id);
  if (input.method === "tools/call") { const name = input?.params?.name; if (typeof name !== "string" || !name) return rpcError(id, -32602, "Invalid params: tool name is required.", 400); return await mcpToolCall(id, name, input?.params?.arguments ?? {}, actor, certificationMode(req, actor)); }
  return rpcError(id, -32601, `Method not found: ${String(input?.method ?? "")}`, 200);
}

Deno.serve(async (req: Request) => {
  if (!validateOrigin(req)) return rpcError(null, -32020, "Forbidden origin.", 403);
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  const mcpPreparse = isMcpPreparse(req);
  if (requestMediaType(req) !== "application/json") return mcpPreparse ? rpcError(null, -32600, "Unsupported Media Type: application/json required.", 415) : json({ error: "unsupported_media_type", required: "application/json" }, 415);
  const authz = await authorize(req); if (!authz.ok) return json({ error: authz.reason ?? "unauthorized" }, 403);
  const parsed = await parseBoundedJson(req);
  if (!parsed.ok) { if (parsed.kind === "too_large") return mcpPreparse ? rpcError(null, -32600, "Request body exceeds the control-plane byte limit.", 413) : json({ error: "request_body_too_large" }, 413); return mcpPreparse ? rpcError(null, -32700, "Parse error", 400) : json({ error: "invalid_json" }, 400); }
  const input = parsed.input;
  try {
    if (authz.actor.certifier && !isMcp(input, req)) return json({ error: "certifier_mcp_only" }, 403);
    if (isMcp(input, req)) return await handleMcp(req, input, authz.actor);
    if (input?.action === "health") { const state = await snapshot(); return json({ service: "ct.integration.api-control.v4.1", actor: authz.actor.id, mcp_protocol: MCP_VERSION, mcp_server_version: MCP_SERVER.version, json_schema_dialect: "https://json-schema.org/draft/2020-12/schema", mode: "admin_read_control_plane", dispatchable_services: ["crownthrive_io", "thrivetools_seo"], dedicated_mcp_services: ["chlom_core"], write_operations_enabled: false, output_schema_validation: true, request_byte_bounding: true, provider_byte_bounding: true, provider_timeout_cancellation: true, endpoint_catalog_enforcement: true, strict_provider_json: true, github_oidc_certifier: "candidate_not_active_until_founder_signature", state }); }
    if (input?.action === "io_read") { const result: any = await providerReadData("crownthrive_io", String(input?.operation ?? ""), input?.params ?? {}, authz.actor); if (result.protocolError) return json({ error: result.protocolError.message }, 400); if (result.toolError) return json({ error: result.toolError, ...(result.value ? { evidence: result.value } : {}) }, 502); return json(result.value); }
    if (input?.action === "seo_read") { const result: any = await providerReadData("thrivetools_seo", String(input?.operation ?? ""), input?.params ?? {}, authz.actor); if (result.protocolError) return json({ error: result.protocolError.message }, 400); if (result.toolError) return json({ error: result.toolError, ...(result.value ? { evidence: result.value } : {}) }, 502); return json(result.value); }
    if (input?.action === "list_mcp_tools") { const state: any = await snapshot(); return json({ tools: Array.isArray(state?.mcp_tools) ? state.mcp_tools : [], central_dispatchable_services: ["crownthrive_io", "thrivetools_seo"], preserved_dedicated_services: ["chlom_core"] }); }
    return json({ error: "unknown_action" }, 400);
  } catch (error) { return json({ error: error instanceof Error ? error.message : "unknown_error" }, 500); }
});
