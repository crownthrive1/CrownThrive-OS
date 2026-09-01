import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const BASE = "https://locticians.com/api/v2";
const VERSION = "6.0.0";
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_PROVIDER_BYTES = 2 * 1024 * 1024;
const TIMEOUT_MS = 20_000;

const ALLOWED_ALIASES = new Set([
  "locticians_bd_personas_hot_v1",
  "locticians_bd_personas_warm_v1",
  "locticians_bd_personas_cold_v1",
  "locticians_bd_personas_emergency_1_v1",
  "locticians_bd_personas_emergency_2_v1",
  "locticians_brilliant_directories_api_key",
  "locticians_brilliant_directories_api_key_recovery",
  "LOCTICIANS_BD_API_KEY_COLD_PENTA",
  "locticians_brilliant_directories_pentamailer_v3",
  "locticians_brilliant_directories_pentamailer_2_v3",
  "locticians_bd_legacy_master_archived_v1",
]);

function out(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
    },
  });
}

async function boundedJson(req: Request) {
  const declared = Number(req.headers.get("content-length") || "0");
  if (declared > MAX_REQUEST_BYTES) throw new Error("request_too_large");
  if (!req.body) return {};
  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (true) {
    const p = await reader.read();
    if (p.done) break;
    if (!p.value) continue;
    total += p.value.byteLength;
    if (total > MAX_REQUEST_BYTES) throw new Error("request_too_large");
    chunks.push(p.value);
  }
  const buf = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) { buf.set(c, off); off += c.byteLength; }
  const text = new TextDecoder().decode(buf);
  if (!text) return {};
  try { return JSON.parse(text); } catch { throw new Error("invalid_json"); }
}

async function rpc(name: string, body: Record<string, unknown> = {}) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: SERVICE,
      authorization: `Bearer ${SERVICE}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  let data: any = text;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (!r.ok) throw new Error(`rpc_${name}_${r.status}`);
  return data;
}

async function secret(name: string) {
  if (!ALLOWED_ALIASES.has(name)) throw new Error("credential_alias_not_allowed");
  const v = await rpc("get_runtime_secret", { secret_name: name });
  if (typeof v !== "string" || !v) throw new Error(`secret_unbound_${name}`);
  return v;
}

async function authActor(req: Request) {
  const auth = req.headers.get("authorization") ?? "";
  const token = auth.replace(/^Bearer\s+/i, "").trim();
  if (!token) throw new Error("unauthorized");
  if (token === SERVICE) return { actor: "service_role", service: true, admin: true };
  const r = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { authorization: auth, apikey: SERVICE },
  });
  if (!r.ok) throw new Error("unauthorized");
  const user = await r.json();
  const m = user?.app_metadata ?? {};
  const role = String(m.role ?? m.crownthrive_role ?? "").toLowerCase();
  const admin = m.crownthrive_admin === true || ["founder", "admin", "super_admin"].includes(role);
  return { actor: `user:${String(user?.id ?? "unknown")}`, service: false, admin };
}

function cleanObject(x: any, maxKeys = 100, maxValue = 100000) {
  if (x === undefined || x === null) return {};
  if (typeof x !== "object" || Array.isArray(x)) throw new Error("object_required");
  const y: Record<string, string> = {};
  const entries = Object.entries(x);
  if (entries.length > maxKeys) throw new Error("too_many_fields");
  for (const [k, v] of entries) {
    if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(k)) throw new Error(`invalid_field:${k}`);
    if (/include_user_token/i.test(k)) throw new Error("sensitive_user_token_capability_closed");
    const s = String(v ?? "");
    if (s.length > maxValue) throw new Error(`field_too_large:${k}`);
    y[k] = s;
  }
  return y;
}

function safePath(template: string, concrete: string) {
  if (!template.startsWith("/api/v2/") || !concrete.startsWith("/api/v2/")) throw new Error("invalid_path");
  if (template.length > 500 || concrete.length > 1000 || concrete.includes("..") || concrete.includes("\\")) throw new Error("invalid_path");
  const tParts = template.split("/");
  const cParts = concrete.split("/");
  if (tParts.length !== cParts.length) throw new Error("concrete_path_does_not_match_template");
  for (let i = 0; i < tParts.length; i++) {
    const t = tParts[i], c = cParts[i];
    if (/^\{[A-Za-z0-9_]+\}$/.test(t)) {
      if (!c || /[?#]/.test(c)) throw new Error("invalid_path_parameter");
    } else if (t !== c) throw new Error("concrete_path_does_not_match_template");
  }
  return concrete.slice(7);
}

async function digest(bytes: Uint8Array) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return [...d].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function provider(method: string, path: string, query: Record<string, string>, body: Record<string, string>, key: string, actor: string, operation: string, lane: string, mode: string) {
  const u = new globalThis.URL(BASE + path);
  for (const [k, v] of Object.entries(query)) u.searchParams.set(k, v);
  const headers: Record<string, string> = { "X-Api-Key": key, accept: "application/json" };
  let encoded: string | undefined;
  if (["POST", "PUT", "DELETE"].includes(method)) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(body)) q.set(k, v);
    encoded = q.toString();
    headers["content-type"] = "application/x-www-form-urlencoded";
  }
  const started = Date.now();
  let status = 0, total = 0;
  let sha: string | null = null;
  try {
    const r = await fetch(u, { method, headers, body: encoded, redirect: "error", signal: AbortSignal.timeout(TIMEOUT_MS) });
    status = r.status;
    const reader = r.body?.getReader();
    const chunks: Uint8Array[] = [];
    if (reader) while (true) {
      const p = await reader.read();
      if (p.done) break;
      if (!p.value) continue;
      total += p.value.byteLength;
      if (total > MAX_PROVIDER_BYTES) {
        try { await reader.cancel(); } catch {}
        throw new Error("provider_response_too_large");
      }
      chunks.push(p.value);
    }
    const buf = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) { buf.set(c, off); off += c.byteLength; }
    sha = await digest(buf);
    const text = new TextDecoder().decode(buf);
    let data: any = text;
    try { data = text ? JSON.parse(text) : null; } catch { if (r.ok) throw new Error("provider_invalid_json"); }
    try {
      await rpc("integration_record_request", {
        p_service_id: "locticians",
        p_operation_key: operation,
        p_http_method: method,
        p_path_template: path,
        p_http_status: r.status,
        p_success: r.ok,
        p_actor: "locticians-bd-router-v2",
        p_latency_ms: Date.now() - started,
        p_response_sha256: sha,
        p_notes: `caller=${actor}; lane=${lane}; failover_mode=${mode}; router=${VERSION}; d3_dispatch=false`,
      });
    } catch {}
    return { ok: r.ok, status: r.status, data, bytes: total, sha256: sha, lane, mode };
  } catch (e) {
    try {
      await rpc("integration_record_request", {
        p_service_id: "locticians",
        p_operation_key: operation,
        p_http_method: method,
        p_path_template: path,
        p_http_status: status || 599,
        p_success: false,
        p_actor: "locticians-bd-router-v2",
        p_latency_ms: Date.now() - started,
        p_response_sha256: sha,
        p_notes: `caller=${actor}; lane=${lane}; failover_mode=${mode}; router=${VERSION}; transport_error=true; d3_dispatch=false`,
      });
    } catch {}
    throw e;
  }
}

async function selectCredential(failureClass: string) {
  const s = await rpc("locticians_bd_select_warm_credential_v3", { p_failure_class: failureClass });
  if (!s || typeof s !== "object") throw new Error("credential_selector_unavailable");
  return s;
}

async function resolveCredential() {
  let s = await selectCredential("none");
  if (s?.action !== "use_credential" || !s?.vault_alias) throw new Error("warm_primary_unavailable");
  try { return { selection: s, key: await secret(String(s.vault_alias)) }; }
  catch {
    s = await selectCredential("vault_alias_unavailable");
    if (s?.action !== "use_credential" || !s?.vault_alias) throw new Error("credential_custody_unavailable");
    return { selection: s, key: await secret(String(s.vault_alias)) };
  }
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") return out(405, { ok: false, error: "POST_required", version: VERSION });
    const actor = await authActor(req);
    const input: any = await boundedJson(req);
    const op = String(input?.operation ?? "");
    if (op === "discover") {
      const data = await rpc("locticians_bd_discover_v3", {
        p_query: input?.query ? String(input.query) : null,
        p_method: input?.method ? String(input.method) : null,
        p_tier: input?.tier ? String(input.tier) : null,
        p_limit: Math.min(Math.max(Number(input?.limit ?? 100), 1), 500),
      });
      return out(200, { ok: true, service: "locticians", provider: "Brilliant Directories", capabilities: data, authority_note: "Reference/provider permission does not create execution authority. DELETE/D3 requires explicit governed authority.", version: VERSION });
    }
    if (op !== "route.execute") return out(400, { ok: false, error: "unknown_operation", allowed: ["discover", "route.execute"], version: VERSION });
    if (!actor.service && !actor.admin) return out(403, { ok: false, error: "admin_or_service_authority_required", provider_dispatch: false });
    const method = String(input?.method ?? "").toUpperCase();
    if (!["GET", "POST", "PUT", "DELETE"].includes(method)) return out(400, { ok: false, error: "invalid_method" });
    const template = String(input?.route_template ?? "");
    const concrete = String(input?.concrete_path ?? template);
    const path = safePath(template, concrete);
    if (method === "DELETE") return out(409, { ok: false, error: "D3_FOUNDER_APPROVAL_REQUIRED", risk_class: "D3", provider_dispatch: false, route_template: template, version: VERSION });
    const decision = await rpc("locticians_bd_route_decision_v3", { p_http_method: method, p_path: template, p_has_d3: false });
    if (!decision) return out(404, { ok: false, error: "route_not_registered", provider_dispatch: false, route_template: template });
    if (decision?.requires_d3 === true || decision?.risk_class === "D3") return out(409, { ok: false, error: "D3_FOUNDER_APPROVAL_REQUIRED", decision, provider_dispatch: false });
    if (decision?.execution_allowed !== true) return out(403, { ok: false, error: String(decision?.decision ?? "route_not_certified"), decision, provider_dispatch: false });
    const rate = await rpc("locticians_bd_sitewide_rate_check_v3", {});
    if (rate?.allowed !== true) return out(429, { ok: false, error: "LOCTICIANS_SITEWIDE_RATE_BUDGET_HOLD", rate, provider_dispatch: false, retry_policy: "cool provider route; do not key-hop on 429" });
    const query = cleanObject(input?.query ?? {}, 50, 4000);
    const body = cleanObject(input?.body ?? {}, 100, 100000);
    const resolved = await resolveCredential();
    let selection = resolved.selection;
    let r = await provider(method, path, query, body, resolved.key, actor.actor, String(decision?.capability_key ?? `${method}:${template}`), String(selection.lane_id ?? "unknown"), String(selection.failover_mode ?? "primary"));
    if (r.status === 429) return out(429, { ok: false, error: "PROVIDER_RATE_LIMIT", provider_status: 429, lane: r.lane, retry_policy: "cool entire Brilliant Directories route; credential switching forbidden for quota bypass", provider_dispatch: true, evidence: { bytes: r.bytes, sha256: r.sha256 } });
    if (r.status === 401 || r.status === 403) {
      const alt = await selectCredential("credential_auth_failure");
      if (alt?.action !== "use_credential" || !alt?.vault_alias || String(alt.vault_alias) === String(selection.vault_alias)) return out(502, { ok: false, error: "PRIMARY_CREDENTIAL_AUTH_FAILURE_NO_VERIFIED_INDEPENDENT_STANDBY", provider_status: r.status, lane: r.lane, provider_dispatch: true, failover_ready: false, version: VERSION });
      const altKey = await secret(String(alt.vault_alias));
      selection = alt;
      r = await provider(method, path, query, body, altKey, actor.actor, String(decision?.capability_key ?? `${method}:${template}`), String(alt.lane_id ?? "unknown"), String(alt.failover_mode ?? "independent_warm_standby"));
      if (r.status === 429) return out(429, { ok: false, error: "PROVIDER_RATE_LIMIT", provider_status: 429, lane: r.lane, retry_policy: "cool entire Brilliant Directories route; no further key switching", provider_dispatch: true, evidence: { bytes: r.bytes, sha256: r.sha256 } });
    }
    return out(r.ok ? 200 : r.status, { ok: r.ok, provider_status: r.status, lane: r.lane, failover_mode: r.mode, data: r.data, evidence: { bytes: r.bytes, sha256: r.sha256 }, decision, version: VERSION });
  } catch (e) {
    const m = e instanceof Error ? e.message : String(e);
    const status = m === "unauthorized" ? 401 : m === "request_too_large" ? 413 : 400;
    return out(status, { ok: false, error: m, provider_dispatch: false, version: VERSION });
  }
});
