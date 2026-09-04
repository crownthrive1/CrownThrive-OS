import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import postgres from "npm:postgres@3.4.5";

const sql = postgres(Deno.env.get("SUPABASE_DB_URL")!, { max: 2, prepare: false });
const VERSION = "1.0.0";
const CONTRACT = "ct.penta.replicate.v1";
const MCP_PROTOCOL = "2025-03-26";
const SUPPORTED_PROTOCOLS = ["2025-03-26", "2024-11-05"];
const encoder = new TextEncoder();

type Rpc = { jsonrpc?: string; id?: string | number | null; method?: string; params?: any };

function cors(req: Request): Headers {
  const h = new Headers();
  h.set("access-control-allow-origin", req.headers.get("origin") || "*");
  h.set("access-control-allow-methods", "GET,POST,OPTIONS");
  h.set("access-control-allow-headers", "content-type,authorization,mcp-session-id,x-request-id");
  h.set("access-control-expose-headers", "mcp-session-id,x-penta-replicate-version,x-penta-replicate-sha256,x-request-id");
  h.set("cache-control", "no-store");
  h.set("vary", "Origin, Accept");
  h.set("x-content-type-options", "nosniff");
  h.set("x-penta-replicate-version", VERSION);
  h.set("x-request-id", req.headers.get("x-request-id")?.slice(0, 120) || crypto.randomUUID());
  return h;
}

async function sha256(value: string): Promise<string> {
  const d = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

async function respond(req: Request, body: unknown, status = 200, contentType = "application/json; charset=utf-8", session?: string) {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  const h = cors(req);
  h.set("content-type", contentType);
  h.set("x-penta-replicate-sha256", await sha256(text));
  if (session) h.set("mcp-session-id", session);
  return new Response(text, { status, headers: h });
}

function cleanSurface(value: unknown): string {
  const v = String(value ?? "").trim();
  if (!v || v.length > 240 || !/^[A-Za-z0-9._:-]+$/.test(v)) throw new Error("invalid_surface_id");
  return v;
}

async function status() {
  const rows = await sql<Array<{ v: any }>>`select integration_control.penta_replicate_status_v1() as v`;
  return rows[0]?.v || { state: "ERROR", reason: "status_unavailable" };
}

async function manifest(surfaceId: string) {
  const rows = await sql<Array<{ v: any }>>`select integration_control.penta_replicate_manifest_v1(${surfaceId}) as v`;
  return rows[0]?.v || { state: "ERROR", reason: "manifest_unavailable" };
}

async function targets(limit = 100) {
  const lim = Math.max(1, Math.min(Number(limit) || 100, 100));
  const rows = await sql<Array<any>>`
    select surface_id, canonical_url, provider_system, update_mode, auto_update_enabled,
           provider_connection_state, health_state, eligibility_state, authority_ceiling,
           last_manifest_sha256, last_applied_sha256, last_applied_at, failure_count
    from integration_control.penta_replicate_targets_v1
    order by surface_id limit ${lim}`;
  return { state: "PASS", count: rows.length, items: rows, provider_credentials_exposed: false };
}

async function drift(surfaceId?: string) {
  if (surfaceId) {
    const sid = cleanSurface(surfaceId);
    const rows = await sql<Array<any>>`
      select surface_id, eligibility_state, last_manifest_sha256, last_applied_sha256, last_manifest_at, last_applied_at,
             (last_manifest_sha256 is distinct from last_applied_sha256) as drift
      from integration_control.penta_replicate_targets_v1 where surface_id=${sid}`;
    return { state: "PASS", items: rows, provider_credentials_exposed: false };
  }
  const rows = await sql<Array<any>>`
    select surface_id, eligibility_state, last_manifest_sha256, last_applied_sha256, last_manifest_at, last_applied_at
    from integration_control.penta_replicate_targets_v1
    where last_manifest_sha256 is distinct from last_applied_sha256
    order by updated_at desc limit 100`;
  return { state: "PASS", count: rows.length, items: rows, provider_credentials_exposed: false };
}

function bootstrapSource(surfaceId: string, origin: string): string {
  const manifestUrl = `${origin}/functions/v1/penta-replicate/manifest?surface_id=${encodeURIComponent(surfaceId)}`;
  const mcpUrl = `${origin}/functions/v1/penta-replicate/mcp`;
  return `(()=>{const k="CrownThrivePentaReplicate",sid=${JSON.stringify(surfaceId)},manifestUrl=${JSON.stringify(manifestUrl)},mcpUrl=${JSON.stringify(mcpUrl)};if(window[k]&&window[k].surfaceId===sid){window[k].refresh?.();return;}const state={contract:"ct.penta.replicate.bootstrap.v1",version:"1.0.0",surfaceId:sid,manifestUrl,mcpUrl,registry:null,lastRefresh:null,providerCredentialsExposed:false,providerWrite:false,async refresh(){const r=await fetch(manifestUrl,{headers:{accept:"application/json"},cache:"no-store"});if(!r.ok)throw new Error("penta_replicate_manifest_"+r.status);this.registry=await r.json();this.lastRefresh=new Date().toISOString();window.dispatchEvent(new CustomEvent("crownthrive:penta-replicated",{detail:{surfaceId:sid,manifestSha256:this.registry?.manifest_sha256}}));return this.registry;}};window[k]=state;let meta=document.querySelector('meta[name="crownthrive:penta-replicate"]');if(!meta){meta=document.createElement("meta");meta.name="crownthrive:penta-replicate";document.head?.appendChild(meta);}meta.content="1.0.0|"+sid;state.refresh().catch(e=>console.warn("PentaReplicate",e?.message||e));})();`;
}

const tools = [
  { name: "penta.replicate.status", description: "Read PentaReplicate fleet status.", inputSchema: { type: "object", properties: {}, additionalProperties: false }, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true } },
  { name: "penta.replicate.manifest", description: "Read one secret-free surface replication manifest.", inputSchema: { type: "object", properties: { surface_id: { type: "string" } }, required: ["surface_id"], additionalProperties: false }, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true } },
  { name: "penta.replicate.targets", description: "List PentaReplicate targets and eligibility.", inputSchema: { type: "object", properties: { limit: { type: "integer", minimum: 1, maximum: 100 } }, additionalProperties: false }, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true } },
  { name: "penta.replicate.drift", description: "Read manifest/application drift without provider mutation.", inputSchema: { type: "object", properties: { surface_id: { type: "string" } }, additionalProperties: false }, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true } },
];

function rpcResult(id: Rpc["id"], result: unknown) { return { jsonrpc: "2.0", id: id ?? null, result }; }
function rpcError(id: Rpc["id"], code: number, message: string) { return { jsonrpc: "2.0", id: id ?? null, error: { code, message } }; }
function toolResult(value: unknown, isError = false) { return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }], structuredContent: value, isError }; }

async function callTool(name: string, args: any) {
  switch (name) {
    case "penta.replicate.status": return status();
    case "penta.replicate.manifest": return manifest(cleanSurface(args?.surface_id));
    case "penta.replicate.targets": return targets(args?.limit);
    case "penta.replicate.drift": return drift(args?.surface_id);
    default: throw new Error("tool_not_found");
  }
}

function isServiceRole(req: Request): boolean {
  const auth = req.headers.get("authorization") || "";
  const expected = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
  return expected.length > 20 && auth === `Bearer ${expected}`;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
  try {
    const url = new URL(req.url);
    const path = url.pathname;
    const origin = `${url.protocol}//${url.host}`;

    if (req.method === "GET" && (path.endsWith("/health") || path.endsWith("/penta-replicate"))) {
      return respond(req, { state: "PASS", service: "penta-replicate", version: VERSION, contract: CONTRACT, status: await status(), public_reads: true, provider_write_direct: false, provider_credentials_exposed: false, checked_at: new Date().toISOString() });
    }
    if (req.method === "GET" && path.endsWith("/manifest")) {
      return respond(req, await manifest(cleanSurface(url.searchParams.get("surface_id"))));
    }
    if (req.method === "GET" && path.endsWith("/bootstrap.js")) {
      const sid = cleanSurface(url.searchParams.get("surface_id"));
      return respond(req, bootstrapSource(sid, origin), 200, "application/javascript; charset=utf-8");
    }
    if (req.method === "POST" && path.endsWith("/cycle")) {
      if (!isServiceRole(req)) return respond(req, { state: "DENY", reason: "service_role_required" }, 403);
      const body = await req.json().catch(() => ({}));
      const force = body?.force === true;
      const rows = await sql<Array<{ v: any }>>`select integration_control.penta_replicate_cycle_v1(${force}) as v`;
      return respond(req, rows[0]?.v || { state: "ERROR", reason: "cycle_unavailable" });
    }
    if (req.method === "POST" && path.endsWith("/mcp")) {
      const rpc: Rpc = await req.json().catch(() => ({}));
      if (rpc.jsonrpc !== "2.0" || !rpc.method) return respond(req, rpcError(rpc.id, -32600, "Invalid Request"), 400);
      const session = req.headers.get("mcp-session-id") || crypto.randomUUID();
      if (rpc.method === "initialize") {
        const requested = String(rpc.params?.protocolVersion || MCP_PROTOCOL);
        const selected = SUPPORTED_PROTOCOLS.includes(requested) ? requested : MCP_PROTOCOL;
        return respond(req, rpcResult(rpc.id, { protocolVersion: selected, capabilities: { tools: { listChanged: false } }, serverInfo: { name: "PentaReplicate", version: VERSION }, instructions: "Read-only CrownThrive replication discovery. Provider writes and credentials are not exposed through this MCP." }), 200, "application/json; charset=utf-8", session);
      }
      if (rpc.method === "notifications/initialized" || rpc.method === "notifications/cancelled") return new Response(null, { status: 202, headers: cors(req) });
      if (rpc.method === "ping") return respond(req, rpcResult(rpc.id, {}), 200, "application/json; charset=utf-8", session);
      if (rpc.method === "tools/list") return respond(req, rpcResult(rpc.id, { tools }), 200, "application/json; charset=utf-8", session);
      if (rpc.method === "tools/call") {
        const name = String(rpc.params?.name || "");
        if (!tools.some((t) => t.name === name)) return respond(req, rpcError(rpc.id, -32602, "Unknown tool"), 200, "application/json; charset=utf-8", session);
        try { return respond(req, rpcResult(rpc.id, toolResult(await callTool(name, rpc.params?.arguments || {}))), 200, "application/json; charset=utf-8", session); }
        catch (e) { return respond(req, rpcResult(rpc.id, toolResult({ state: "ERROR", reason: e instanceof Error ? e.message : String(e), provider_credentials_exposed: false }, true)), 200, "application/json; charset=utf-8", session); }
      }
      return respond(req, rpcError(rpc.id, -32601, "Method not found"), 200, "application/json; charset=utf-8", session);
    }
    return respond(req, { state: "NOT_FOUND", service: "penta-replicate" }, 404);
  } catch (e) {
    console.error("penta-replicate", e);
    return respond(req, { state: "ERROR", reason: e instanceof Error ? e.message : String(e), provider_credentials_exposed: false }, 500);
  }
});
